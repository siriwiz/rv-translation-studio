"""Download pinned official Argos archives with bounded memory and SHA-256 checks."""
import argparse
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    folder = ROOT / 'tools/argos'
    records = json.loads((folder / 'downloads.json').read_text(encoding='utf-8'))
    for record in records:
        pair = record['pair']
        if not all(part.isalpha() for part in pair.split('_')) or len(pair.split('_')) != 2:
            raise ValueError('Invalid language pair in manifest')
        path = folder / (pair + '.argosmodel')
        if path.is_file() and digest(path) == record['sha256']:
            print('Verified', pair, flush=True)
            continue
        if args.check_only:
            raise RuntimeError('Missing or damaged Argos archive: ' + pair)
        url = record['url']
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != 'data.argosopentech.com':
            raise ValueError('Unexpected model source')
        temporary = path.with_suffix('.download')
        print('Downloading', pair, flush=True)
        with urllib.request.urlopen(url, timeout=120) as response:
            if urllib.parse.urlparse(response.url).scheme != 'https':
                raise ValueError('Model download redirected outside HTTPS')
            with temporary.open('wb') as output:
                for chunk in iter(lambda: response.read(1024 * 1024), b''):
                    output.write(chunk)
        if digest(temporary) != record['sha256']:
            raise RuntimeError('Argos archive checksum mismatch: ' + pair)
        temporary.replace(path)
        print('Verified', pair, flush=True)

if __name__ == '__main__':
    main()
