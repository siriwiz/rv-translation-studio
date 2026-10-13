"""Compile and bundle daisyUI locally; the executable needs no Node or CDN."""
import shutil
import subprocess
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'.build-tools'))
from PyQt6.QtCore import QFile,QIODevice
import PyQt6.QtWebChannel

subprocess.run(['npm.cmd','run','check'],cwd=root/'ui',check=True)
subprocess.run(['npm.cmd','run','build'],cwd=root/'ui',check=True)
target=root/'ui/dist';target.mkdir(parents=True,exist_ok=True)
for file in ('index.html','app.js','controls.js'): shutil.copyfile(root/'ui/src'/file,target/file)
shutil.copyfile(root/'Sarabun-Regular.ttf',target/'Sarabun-Regular.ttf')
shutil.copyfile(root/'PlaypenSansThai-Light.ttf',target/'PlaypenSansThai-Light.ttf')
script=QFile(':/qtwebchannel/qwebchannel.js')
if not script.open(QIODevice.OpenModeFlag.ReadOnly): raise RuntimeError('Qt WebChannel client is unavailable')
(target/'qwebchannel.js').write_bytes(bytes(script.readAll()))
print('Offline UI ready:',target)
