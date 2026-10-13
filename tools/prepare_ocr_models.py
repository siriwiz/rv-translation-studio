"""Build-time only: fetch pinned, hash-checked ONNX models for offline OCR."""
import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / '.build-tools'))
target = root / 'assets/ocr'
manifest_path = target / 'manifest.json'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def prepare(entry, check_only):
    path = target / entry['file']
    if path.is_file() and digest(path) == entry['SHA256']:
        return f'Verified {path.name}'
    if check_only:
        raise RuntimeError(f'Missing or damaged bundled model: {path.name}. Run tools/prepare_ocr_models.py.')
    request = Request(entry['model_dir'], headers={'User-Agent': 'RVTranslationStudio-Build/2.7'})
    temp = path.with_suffix('.download')
    with urlopen(request, timeout=120) as source, temp.open('wb') as output:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            output.write(chunk)
    if digest(temp) != entry['SHA256']:
        raise RuntimeError(f'Hash mismatch: {path.name}')
    temp.replace(path)
    return f'Prepared {path.name} ({path.stat().st_size / 1048576:.1f} MiB)'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    target.mkdir(parents=True, exist_ok=True)
    if not manifest_path.exists():
        import yaml
        import rapidocr
        from importlib.metadata import version
        if version('rapidocr') != '3.10.0':
            raise RuntimeError('Install pinned rapidocr==3.10.0 before preparing models.')
        config = yaml.safe_load((Path(rapidocr.__file__).parent / 'default_models.yaml').read_text(encoding='utf-8'))
        models = config['onnxruntime']['PP-OCRv5']
        profiles = ('ch', 'korean', 'latin', 'en', 'th', 'el', 'arabic', 'cyrillic', 'devanagari', 'ta', 'te')
        entries = [dict(models['det']['ch_PP-OCRv5_det_mobile'], file='ch_PP-OCRv5_det_mobile.onnx')]
        entries += [dict(models['rec'][f'{p}_PP-OCRv5_rec_mobile'], file=f'{p}_PP-OCRv5_rec_mobile.onnx') for p in profiles]
        manifest_path.write_text(json.dumps(dict(rapidocr='3.10.0', version='PP-OCRv5', models=entries), indent=2), encoding='utf-8')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    with ThreadPoolExecutor(max_workers=3) as executor:
        for result in executor.map(lambda entry: prepare(entry, args.check_only), manifest['models']):
            print(result, flush=True)
