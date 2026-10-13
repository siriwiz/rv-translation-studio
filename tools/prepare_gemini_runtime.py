"""Bundle the unmodified official Gemini CLI and a local Node runtime."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
target=root/'assets/gemini/runtime'
parser=argparse.ArgumentParser();parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
if not args.check_only:
    package=root/'tools/gemini/node_modules/@google/gemini-cli'
    metadata=json.loads((package/'package.json').read_text(encoding='utf-8'))
    if metadata['version']!='0.63.0':raise RuntimeError('Install pinned @google/gemini-cli@0.63.0 in tools/gemini.')
    node=Path(shutil.which('node.exe') or shutil.which('node') or '')
    if not node.is_file():raise RuntimeError('Node.js 20+ is required at build time.')
    target.mkdir(parents=True,exist_ok=True)
    shutil.copy2(node,target/'node.exe')
    shutil.copytree(package/'bundle',target/'cli/bundle',dirs_exist_ok=True)
    for name in ('package.json','LICENSE','README.md'):shutil.copy2(package/name,target/'cli'/name)
    license_file=node.parent/'LICENSE'
    if license_file.is_file():shutil.copy2(license_file,target/'Node-LICENSE.txt')
    files={str(p.relative_to(target)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in target.rglob('*') if p.is_file() and p.name!='manifest.json'}
    (target/'manifest.json').write_text(json.dumps(dict(cli_version='0.63.0',node_version=subprocess.check_output([str(node),'--version'],text=True).strip(),files=files),indent=2),encoding='utf-8')
manifest=json.loads((target/'manifest.json').read_text(encoding='utf-8'))
for name,digest in manifest['files'].items():
    path=target/name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise RuntimeError('Missing/damaged Gemini runtime: '+name)
print('Verified official Gemini CLI',manifest['cli_version'],'and Node',manifest['node_version'])
