"""Stage an explicit source-only allowlist for review before a GitHub upload."""
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'artifacts/release-2.10.0/repository'
PATTERNS = (
    'main.py', 'build.ps1', 'requirements-desktop.txt', 'README.md', 'CHANGELOG.md',
    'THIRD_PARTY_NOTICES.md', '.gitignore', '.gitattributes',
    'Sarabun-Regular.ttf', 'PlaypenSansThai-Light.ttf',
    'desktop/*.py', 'desktop/ocr.ps1', 'tests/*.py',
    'ui/src/*', 'ui/package.json', 'ui/package-lock.json',
    'tools/*.py', 'tools/hooks/*.py', 'tools/argos/downloads.json',
    'assets/app.ico', 'assets/version-info.txt', 'assets/branding/*', 'assets/artwork/*',
    'assets/ocr/manifest.json', 'assets/ocr/NOTICE.txt',
    'assets/ocr/licenses/*', 'assets/argos/manifest.json', 'assets/argos/*.txt',
    'assets/fonts/*.txt', 'docs/*.md', 'docs/assets/*', 'sample/*.png',
)
EXCLUDED = {'tools/diagnose_connection.py'}
SECRET_PATTERNS = (
    re.compile(r'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}'),
    re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}'),
    re.compile(r'\bgithub_pat_[A-Za-z0-9_]{30,}'),
    re.compile(r'\bAIza[A-Za-z0-9_-]{30,}'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
)

def main():
    files = {p for pattern in PATTERNS for p in ROOT.glob(pattern) if p.is_file()}
    files = sorted(p for p in files if p.relative_to(ROOT).as_posix() not in EXCLUDED)
    STAGE.mkdir(parents=True, exist_ok=True)
    records = []
    selected = {p.relative_to(ROOT).as_posix() for p in files}
    for old in STAGE.rglob('*'):
        if old.is_file() and old.relative_to(STAGE).as_posix() not in selected:
            raise RuntimeError('Unexpected file in existing publication stage: ' + str(old.relative_to(STAGE)))
    for source in files:
        relative = source.relative_to(ROOT)
        body = source.read_bytes()
        if len(body) > 5 * 1024 * 1024:
            raise RuntimeError('Unexpected large source file: ' + relative.as_posix())
        if source.suffix.lower() in ('.py', '.js', '.json', '.md', '.txt', '.ps1', '.html', '.toml', '.css'):
            text = body.decode('utf-8-sig')
            if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                raise RuntimeError('Potential credential in: ' + relative.as_posix())
        output = STAGE / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, output)
        records.append(dict(path=relative.as_posix(), bytes=len(body), sha256=hashlib.sha256(body).hexdigest()))
    # Check relative Markdown destinations without depending on remote badge availability.
    for source in files:
        if source.suffix != '.md':
            continue
        text = source.read_text(encoding='utf-8-sig')
        for target in re.findall(r'\]\(([^)]+)\)|(?:src|href)="([^"]+)"', text):
            link = next(value for value in target if value).split('#')[0]
            if not link or '://' in link or link.startswith('mailto:'):
                continue
            destination = (source.parent / link).resolve()
            if not destination.exists():
                raise RuntimeError('Broken documentation link: ' + str(source.relative_to(ROOT)) + ' -> ' + link)
            if destination.is_file() and destination.relative_to(ROOT).as_posix() not in selected:
                raise RuntimeError('Documentation links to excluded file: ' + link)
    manifest = STAGE.parent / 'manifest.json'
    manifest.write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(json.dumps(dict(files=len(records), bytes=sum(item['bytes'] for item in records),
        largest=max(records, key=lambda item: item['bytes']), stage=str(STAGE))))

if __name__ == '__main__':
    main()
