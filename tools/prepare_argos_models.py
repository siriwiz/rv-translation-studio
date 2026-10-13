"""Prepare official Argos model payloads; every bundled file is hash checked."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path,PurePosixPath

root=Path(__file__).resolve().parents[1];target=root/'assets/argos'
parser=argparse.ArgumentParser();parser.add_argument('--check-only',action='store_true');parser.add_argument('--pairs',nargs='+');args=parser.parse_args()
languages={'en':'English','th':'Thai','zh':'Chinese (Simplified)','ja':'Japanese','ko':'Korean','fr':'French','de':'German','es':'Spanish','vi':'Vietnamese','ru':'Russian'}
default_pairs=[f'en_{code}' for code in languages if code!='en']+[f'{code}_en' for code in languages if code!='en']

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()

if not args.check_only:
    target.mkdir(parents=True,exist_ok=True);models=[];used=set()
    downloads=root/'tools/argos/downloads.json'
    upstream={m['pair']:m for m in json.loads(downloads.read_text())} if downloads.exists() else {}
    for pair in args.pairs or default_pairs:
        source,destination=pair.split('_');archive_path=root/'tools/argos'/f'{pair}.argosmodel'
        package_hash=digest(archive_path)
        if pair in upstream and package_hash!=upstream[pair]['sha256']:raise RuntimeError('Argos package checksum mismatch: '+pair)
        directory=target/'models'/pair;directory.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                relative=PurePosixPath(member.filename)
                if relative.is_absolute() or '..' in relative.parts:raise RuntimeError('Unsafe model archive path')
                parts=relative.parts[1:]
                if not parts or member.is_dir():continue
                name='/'.join(parts)
                # Sentence splitting is performed by Studio; no Stanza or executable payloads.
                if not (name in ('metadata.json','sentencepiece.model','bpe.model','README.md','LICENSE') or (name.startswith('model/') and name.endswith(('.bin','.json','.txt')))):continue
                output=directory.joinpath(*parts);output.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(member) as stream,output.open('wb') as out:shutil.copyfileobj(stream,out)
        metadata=json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
        if (metadata['from_code'],metadata['to_code'])!=(source,destination):raise RuntimeError('Argos language metadata mismatch')
        if not (directory/'model/model.bin').is_file() or not any((directory/n).exists() for n in ('sentencepiece.model','bpe.model')):raise RuntimeError('Incomplete Argos model')
        used.update((source,destination))
        models.append(dict(source=source,target=destination,directory='models/'+pair,version=metadata['package_version'],package_sha256=package_hash,
            url=upstream.get(pair,{}).get('url','https://data.argosopentech.com/argospm/v1/'),
            files={str(p.relative_to(target)).replace('\\','/'):digest(p) for p in directory.rglob('*') if p.is_file()}))
        print('Prepared',pair,flush=True)
    (target/'manifest.json').write_text(json.dumps(dict(argos_version='1.11.0',languages={k:v for k,v in languages.items() if k in used},models=models),indent=2),encoding='utf-8')
manifest=json.loads((target/'manifest.json').read_text(encoding='utf-8'))
for model in manifest['models']:
    for filename,expected in model['files'].items():
        path=target/filename
        if not path.is_file() or digest(path)!=expected:raise RuntimeError('Missing/damaged Argos payload: '+filename)
print('Verified',len(manifest['models']),'Argos models for',len(manifest['languages']),'languages')
