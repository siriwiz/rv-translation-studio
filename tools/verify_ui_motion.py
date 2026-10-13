"""Render English pages and verify real animation frames without an account."""
import json
import os
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / '.build-tools')]
target = root / 'artifacts' / 'ui-v2.2'
target.mkdir(parents=True, exist_ok=True)
os.environ['RUEVALLEY_DATA_DIR'] = str(target / 'motion-test-data')
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication
from desktop.window import Window, STYLE

app = QApplication([])
app.setStyle('Fusion')
QFontDatabase.addApplicationFont(str(root / 'Sarabun-Regular.ttf'))
QFontDatabase.addApplicationFont(str(root / 'PlaypenSansThai-Light.ttf'))
app.setStyleSheet(STYLE)
window = Window()
window.show()
result = {}
frames = []

def first():
    window.grab().save(str(target / 'ui-preview.png'))
    frames.append(window.signal_canvas.grab().toImage())
    window.capture_button.setEnabled(True)
    window.capture_button._to(1.)

def hover():
    result['hover_interpolates'] = 0 < window.capture_button.hover < 1

def second():
    frames.append(window.signal_canvas.grab().toImage())
    result['scan_animation_changes_pixels'] = frames[0] != frames[1]
    window.capture_button._to(0.)
    window.navigate(2)

def fade():
    result['page_fade_interpolates'] = .2 < window.pages.currentWidget().graphicsEffect().opacity() < 1

def account():
    window.grab().save(str(target / 'account-preview.png'))
    result['page_fade_completes'] = window.pages.currentWidget().graphicsEffect().opacity() == 1.
    window.navigate(1)

def history():
    window.grab().save(str(target / 'history-preview.png'))
    result['ok'] = all(result.values())
    (target / 'motion-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    window.close()
    app.quit()

QTimer.singleShot(450, first)
QTimer.singleShot(520, hover)
QTimer.singleShot(850, second)
QTimer.singleShot(930, fade)
QTimer.singleShot(1250, account)
QTimer.singleShot(1600, history)
app.exec()
sys.exit(0 if result.get('ok') else 1)
