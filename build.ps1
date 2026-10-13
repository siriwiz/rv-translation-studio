param([string]$AppName = 'RVTranslationStudio')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONPATH = "$PSScriptRoot\.build-tools"
$pythonBuildExe = (Get-Command python).Source
& $pythonBuildExe tools/build_ui.py
if ($LASTEXITCODE -ne 0) { throw 'Dashboard build failed' }
& $pythonBuildExe tools/prepare_ocr_models.py --check-only
if ($LASTEXITCODE -ne 0) { throw 'Bundled OCR model verification failed' }
& $pythonBuildExe tools/prepare_argos_models.py --check-only
if ($LASTEXITCODE -ne 0) { throw 'Argos model verification failed' }
$rapidOcrPackageRoot = & $pythonBuildExe -c "import rapidocr; from pathlib import Path; print(Path(rapidocr.__file__).parent)"
if ($LASTEXITCODE -ne 0) { throw 'RapidOCR build dependency is unavailable' }
$previousBuildPath = $env:PATH
try {
    # Avoid accidentally bundling old C runtimes from unrelated tools on PATH.
    $env:PATH = "$(Split-Path $pythonBuildExe);$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\WindowsPowerShell\v1.0"
    $runtimeArgs = @()
    foreach ($runtimeName in @('msvcp140.dll','msvcp140_1.dll','msvcp140_2.dll','msvcp140_atomic_wait.dll','msvcp140_codecvt_ids.dll','vcruntime140.dll','vcruntime140_1.dll','concrt140.dll')) {
        $runtimePath = Join-Path $env:SystemRoot "System32\$runtimeName"
        if (!(Test-Path -LiteralPath $runtimePath)) { throw "Required C++ runtime missing: $runtimeName" }
        # PyInstaller's isolated scanner imports Qt before SentencePiece. Upgrade
        # only the project's Qt build runtime, avoiding Qt's older bundled MSVC.
        $projectQtRuntime = Join-Path $PSScriptRoot ".build-tools\PyQt6\Qt6\bin\$runtimeName"
        if (Test-Path -LiteralPath (Split-Path $projectQtRuntime)) {
            $originalQtRuntime = Join-Path $PSScriptRoot ".build-tools\original-qt-runtime\$runtimeName"
            if ((Test-Path -LiteralPath $projectQtRuntime) -and !(Test-Path -LiteralPath $originalQtRuntime)) {
                New-Item -ItemType Directory -Force -Path (Split-Path $originalQtRuntime) | Out-Null
                Copy-Item -LiteralPath $projectQtRuntime -Destination $originalQtRuntime
            }
            Copy-Item -LiteralPath $runtimePath -Destination $projectQtRuntime -Force
        }
        $runtimeArgs += @('--add-binary',"$runtimePath;.")
        $runtimeArgs += @('--add-binary',"$runtimePath;PyQt6/Qt6/bin")
    }
    & $pythonBuildExe tools/build_executable.py --noconfirm --clean --onefile --windowed --name $AppName --icon assets/app.ico --version-file assets/version-info.txt --add-data 'desktop/ocr.ps1;desktop' --add-data 'ui/dist;ui/dist' --add-data 'Sarabun-Regular.ttf;.' --add-data 'PlaypenSansThai-Light.ttf;.' --add-data 'assets/app.ico;assets' --add-data 'assets/ocr;assets/ocr' --add-data 'assets/branding;assets/branding' --add-data 'assets/artwork;assets/artwork' --add-data 'assets/argos;assets/argos' --add-data "$rapidOcrPackageRoot/config.yaml;rapidocr" --add-data "$rapidOcrPackageRoot/default_models.yaml;rapidocr" --hidden-import rapidocr.main --hidden-import rapidocr.inference_engine.onnxruntime --hidden-import onnxruntime --hidden-import bidi.algorithm --collect-data sacremoses --additional-hooks-dir tools/hooks --collect-submodules winrt --exclude-module tkinter --exclude-module torch --exclude-module stanza --exclude-module easyocr --exclude-module matplotlib --exclude-module scipy --exclude-module pandas --exclude-module IPython --exclude-module transformers --exclude-module tensorflow --exclude-module sklearn --exclude-module nltk --exclude-module spacy --exclude-module huggingface_hub --exclude-module datasets --exclude-module bitsandbytes --exclude-module torchvision --exclude-module torchaudio --exclude-module numba --exclude-module llvmlite --exclude-module pyarrow --exclude-module tokenizers --exclude-module fastapi --exclude-module uvicorn --exclude-module onnxruntime.transformers @runtimeArgs main.py
    if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
} finally {
    $env:PATH = $previousBuildPath
}
