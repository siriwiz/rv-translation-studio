# Run and build on Windows

## Requirements

- Windows 10/11, 64-bit. Development has been exercised with Python 3.10 x64.
- Current Microsoft Visual C++ 2015–2022 x64 runtime.
- Node.js 20+ and npm for building the embedded UI only. Node.js is not bundled with the application. End users of a prepared `.exe` do not need Python or Node installed.
- Disk space for dependencies, eighteen Argos models, twelve OCR ONNX files, staging, and the final executable. The all-model single-file build is approximately 2.5 GB.
- Network access during dependency/model preparation. Argos + RapidOCR can operate offline afterward.

The repository contains source, pinned model metadata, and notices. Large model payloads, dependency directories, compiled UI output, and executables are excluded.

## Prepare Python dependencies

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\.build-tools"
$studioRequirements = Get-Content requirements-desktop.txt | Where-Object { $_ -and $_ -notmatch '^argostranslate==' }
$studioRequirements | Set-Content -Encoding utf8 requirements-build.tmp.txt
python -m pip install --target .build-tools -r requirements-build.tmp.txt
python -m pip install --target .build-tools --no-deps argostranslate==1.11.0
```

Argos is installed without its optional heavyweight sentence-splitting stack. Studio uses its tokenizer components with CTranslate2, Lingua, and pySBD, already listed in `requirements-desktop.txt`. Keep the shared Windows runtime bootstrap in `desktop/__init__.py` intact when importing Qt and ONNX Runtime together.

## Prepare UI and model payloads

```powershell
npm.cmd ci --prefix ui
python tools/build_ui.py
python tools/prepare_ocr_models.py
python tools/download_argos_models.py
python tools/prepare_argos_models.py
```

The Argos download helper reads the pinned HTTPS URLs in `tools/argos/downloads.json` and verifies SHA-256 before accepting each archive. OCR preparation also checks pinned hashes. Downloads are a build-time step, not a runtime requirement for a packaged local engine.

## Launch and validate

```powershell
python main.py
python -m unittest discover -s tests -q
```

Some tests require prepared OCR and Argos assets. For desktop acceptance, use the relevant `tools/verify_*.py` scripts; they create isolated artifacts. The 2.10.0 source suite passes 60 regression tests. Desktop acceptance also checks both providers, generated images, real Argos translation, and responsive layouts. These checks do not establish that every third-party game or cloud account will work.

## Build the executable

```powershell
.\build.ps1 -AppName RVTranslationStudio-2.10.0
```

The script rebuilds the local UI, verifies model/runtime manifests, and invokes the runtime-aware PyInstaller wrapper. The executable is written under `dist/`. Do not bypass `tools/build_executable.py`: the Qt, ONNX, and tokenizer import order and shared MSVC runtime handling are intentional.

The single-file executable extracts its payload before starting. Bundling many offline models increases file size and cold-launch time. A built artifact must be smoke-tested separately before distribution; a local verified build is separate from publishing a downloadable GitHub Release.

## Prepare GitHub Release assets

GitHub limits each release asset to less than 2 GiB. The all-model 2.10.0 executable is larger, so the release uses exact binary parts and a Windows assembly helper. After verifying the executable, choose a fresh output directory:

```powershell
python tools/prepare_release.py --input dist/RVTranslationStudio-2.10.0.exe --version 2.10.0 --output artifacts/release-2.10.0/github-assets
```

The tool creates 1,800 MiB parts, `Assemble-RVTranslationStudio-2.10.0.cmd`, `READ-ME-FIRST.txt`, `SHA256SUMS.txt`, and a local `release-manifest.json`. Upload the parts, helper, readme, and checksum list as release assets. Keep the manifest as local verification evidence.

Before publishing, run the generated helper with `/quiet`, check its exit code, and compare the assembled executable's SHA-256 with the verified build. The helper uses Windows PowerShell's built-in .NET hashing support, keeps the downloads, and refuses to replace an existing executable whose hash differs. Verify GitHub's reported asset sizes and SHA-256 digests against the manifest after upload. The packaging tool prepares files; it does not publish a release or handle credentials.

## Repository layout

```text
main.py                    Desktop entry point
desktop/                   Native capture, OCR, auth, translation, overlay, bridge
ui/src/                    Local daisyUI/Tailwind dashboard
assets/                    Icons, manifests, model and third-party notices
tools/                     Preparation, packaging, acceptance, and benchmark scripts
tests/                     Python regression tests
docs/                      User guide, build guide, privacy, measured performance
```

The UI runs inside Qt WebEngine and communicates through Qt WebChannel. There is no Next.js server or CDN requirement. Browser assets are compiled into the desktop package.
