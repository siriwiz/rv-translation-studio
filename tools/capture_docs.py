"""Capture documentation screens with isolated local data and no cloud account."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / '.build-tools')]
os.environ['RUEVALLEY_DATA_DIR'] = str(ROOT / 'artifacts/publishing/demo-data')
from desktop.storage import write_json
write_json('settings.json', dict(provider='argos', source_language='en', target_language='th',
    ocr_backend='rapid', motion=False, model_argos='argos-balanced-v1'))
from desktop.web_dashboard import install_dashboard
from desktop.window import Window, STYLE
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtTest import QTest

app = QApplication(['RVStudio-docs'])
app.setStyle('Fusion')
app.setStyleSheet(STYLE)
for font in ('Sarabun-Regular.ttf', 'PlaypenSansThai-Light.ttf'):
    QFontDatabase.addApplicationFont(str(ROOT / font))
window = Window()
install_dashboard(window)
window.resize(1440, 960)
window.show()

def js(code):
    result = []
    window.web_dashboard.page().runJavaScript(code, result.append)
    deadline = time.monotonic() + 10
    while not result and time.monotonic() < deadline:
        QTest.qWait(30)
    if not result:
        raise RuntimeError('Documentation dashboard did not respond')
    return result[0]

try:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if js("document.documentElement.dataset.ready") == 'true' and not window.jobs:
            break
        QTest.qWait(100)
    else:
        raise RuntimeError('Documentation dashboard did not become ready')
    # Public demonstration dialogue, entered explicitly; no user history is loaded.
    window.history = []
    window.record([
        dict(text='The valley remembers you.', translation='หุบเขายังจดจำคุณได้', source_language='en', target_language='th'),
        dict(text='We should return before the storm arrives.', translation='เราควรกลับไปก่อนพายุจะมา', source_language='en', target_language='th'),
        dict(text='There is still time to find another way.', translation='ยังมีเวลาที่จะหาหนทางอื่น', source_language='en', target_language='th'),
    ])
    window.motion_toggle.setChecked(False)
    window.web_dashboard.bridge.sync(True)
    target = ROOT / 'docs/assets'
    target.mkdir(parents=True, exist_ok=True)
    for page in ('studio', 'library', 'connection', 'settings'):
        js(f"document.querySelector('[data-page={page}]').click()")
        if page == 'library':
            js("document.querySelector('#history-rows tr').click()")
        QTest.qWait(600)
        window.grab().save(str(target / f'{page}.png'))
    print('Saved four documentation screenshots with illustrative sample dialogue.')
finally:
    for job in window.jobs:
        job.wait(10000)
    window.hotkey_bridge.stop()
    window.overlay.clear()
    window.close()
