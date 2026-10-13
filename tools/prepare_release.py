"""Prepare split, hash-verified Windows release assets below GitHub's file limit."""
import argparse
import hashlib
import json
import re
from pathlib import Path

CHUNK_SIZE = 8 * 1024 * 1024
PART_SIZE = 1800 * 1024 * 1024


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b''):
            result.update(chunk)
    return result.hexdigest()


def assembler(version, expected, parts):
    name = f'RVTranslationStudio-{version}.exe'
    checks = '\n'.join(f'if not exist "{part.name}" goto missing' for part in parts)
    source = '+'.join(f'"{part.name}"' for part in parts)
    verify = lambda filename: f'powershell.exe -NoLogo -NoProfile -Command "$stream=[IO.File]::OpenRead(\'{filename}\'); try {{$sha=[Security.Cryptography.SHA256]::Create(); $actual=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace(\'-\',\'\'); if($actual -ne \'{expected}\'){{exit 1}}}} finally {{$stream.Dispose()}}"'
    return f'''@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
if exist "{name}" goto existing
{checks}
echo Rebuilding RV Translation Studio {version}...
copy /b /y {source} "{name}.assembling" >nul
if errorlevel 1 goto failed
echo Verifying SHA-256. Please wait...
{verify(name + '.assembling')}
if errorlevel 1 goto failed
if exist "{name}" goto failed
ren "{name}.assembling" "{name}"
if errorlevel 1 goto failed
goto success
:existing
echo Checking the existing executable...
{verify(name)}
if errorlevel 1 goto different
goto success
:missing
echo ERROR: Download every .part file into this folder before running this helper.
goto failed
:different
echo ERROR: An executable with this name already exists and has a different hash.
echo It has been preserved. Use an empty folder for this release.
goto failed
:failed
echo Assembly failed. Keep all downloaded files and check their SHA-256 values.
set result=1
goto done
:success
echo Ready: {name}
echo SHA-256 verified. Double-click the executable to open the application.
echo The part files are kept so you can verify or assemble the release again.
set result=0
:done
popd
if /I not "%~1"=="/quiet" pause
exit /b %result%
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+', args.version):
        raise ValueError('Use a numeric major.minor.patch version')
    expected_name = f'RVTranslationStudio-{args.version}.exe'
    if args.input.name != expected_name or not args.input.is_file():
        raise ValueError('Input must be the matching versioned executable')
    args.output.mkdir(parents=True, exist_ok=True)
    full_hash = hashlib.sha256()
    parts = []
    with args.input.open('rb') as stream:
        index = 1
        while True:
            first = stream.read(min(CHUNK_SIZE, PART_SIZE))
            if not first:
                break
            path = args.output / f'{expected_name}.part{index}'
            if path.exists():
                raise FileExistsError('Use a fresh release output directory: ' + str(path))
            part_hash = hashlib.sha256()
            written = 0
            with path.open('wb') as out:
                chunk = first
                while chunk:
                    out.write(chunk)
                    part_hash.update(chunk)
                    full_hash.update(chunk)
                    written += len(chunk)
                    if written == PART_SIZE:
                        break
                    chunk = stream.read(min(CHUNK_SIZE, PART_SIZE - written))
            parts.append(path)
            print(f'Prepared {path.name}: {written:,} bytes', flush=True)
            assert written < 2 * 1024**3
            index += 1
    if full_hash.hexdigest() != digest(args.input):
        raise RuntimeError('Input changed during packaging')
    helper = args.output / f'Assemble-RVTranslationStudio-{args.version}.cmd'
    helper.write_text(assembler(args.version, full_hash.hexdigest(), parts), encoding='ascii', newline='\r\n')
    readme = args.output / 'READ-ME-FIRST.txt'
    readme.write_text(f'''RV TRANSLATION STUDIO {args.version} - WINDOWS DOWNLOAD

The complete offline executable is larger than GitHub's 2 GiB per-asset limit.
This release contains exact binary parts of the verified executable.

1. Download ALL {len(parts)} files ending in .part1, .part2, etc.
2. Download {helper.name}.
3. Put the files in one folder and double-click the .cmd helper.
4. The helper checks SHA-256 and creates {expected_name}.
5. Open the resulting .exe. No Python, Node.js, or archive utility is required.

The part files are not programs and cannot be opened individually. Keep them
until assembly completes. The helper preserves downloads and does not replace
an existing executable with a different hash.

Final executable size: {args.input.stat().st_size:,} bytes
Final executable SHA-256: {full_hash.hexdigest()}

Requirements: Windows 10/11 x64; PowerShell is included with Windows.
The first launch extracts the bundled offline models and can take time.
Providers: ChatGPT account sign-in and Argos Local. Gemini has been removed.
Shortcuts: release F1 to translate; F2 clears; Esc cancels crop selection.

User guide: https://github.com/siriwiz/rv-translation-studio/blob/main/docs/USER_GUIDE.md
''', encoding='utf-8', newline='\r\n')
    records = [dict(name=p.name, bytes=p.stat().st_size, sha256=digest(p)) for p in [*parts, helper, readme]]
    sums = args.output / 'SHA256SUMS.txt'
    sums.write_text('\n'.join(f"{row['sha256']}  {row['name']}" for row in records) +
                    f'\n{full_hash.hexdigest()}  {expected_name}\n', encoding='ascii')
    records.append(dict(name=sums.name, bytes=sums.stat().st_size, sha256=digest(sums)))
    manifest = dict(version=args.version, executable=dict(name=expected_name,
        bytes=args.input.stat().st_size, sha256=full_hash.hexdigest()), assets=records)
    (args.output / 'release-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Release assets prepared and checksummed.', flush=True)


if __name__ == '__main__':
    main()
