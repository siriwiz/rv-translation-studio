# Run and build on Windows

## Requirements

- Windows 10/11, 64-bit. Development has been exercised with Python 3.10 x64.
- Current Microsoft Visual C++ 2015–2022 x64 runtime.
- Node.js 20+ and npm for building the embedded UI and optional bundled Gemini CLI runtime. End users of a prepared `.exe` do not need Python or Node installed.
- Disk space for dependencies, eighteen Argos models, twelve OCR ONNX files, staging, and the final executable. The all-model single-file build is approximately 2.6 GB.
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

The current executable recipe also bundles the retained Gemini CLI organization integration:

```powershell
npm.cmd ci --prefix tools/gemini --ignore-scripts --no-audit --no-fund
python tools/prepare_gemini_runtime.py
```

Use an official Node.js distribution with its LICENSE beside `node.exe` so the preparation tool can preserve that notice. Personal Gemini users should select API key mode; packaging the CLI does not grant an entitlement to use it.

## Launch and validate

```powershell
python main.py
python -m unittest discover -s tests -q
```

Some tests require prepared OCR and Argos assets. For desktop acceptance, use the relevant `tools/verify_*.py` scripts; they create isolated artifacts. The source suite had 70 passing tests at the 2.9.3 preview checkpoint. These checks do not establish that every third-party game or cloud account will work.

## Build the executable

```powershell
.\build.ps1 -AppName RVTranslationStudio-2.9.3
```

The script rebuilds the local UI, verifies model/runtime manifests, and invokes the runtime-aware PyInstaller wrapper. The executable is written under `dist/`. Do not bypass `tools/build_executable.py`: the Qt, ONNX, and tokenizer import order and shared MSVC runtime handling are intentional.

The single-file executable extracts its payload before starting. Bundling many offline models increases file size and cold-launch time. A built artifact must be smoke-tested separately before distribution; the source preview version is not a published, verified GitHub release.

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
