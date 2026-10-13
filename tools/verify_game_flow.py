"""Exercise F1 outside the dashboard, real screen OCR and blended overlay.

Network translation is replaced with deterministic Thai text for this fixture.
"""
import sys
import os
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / '.build-tools')]
use_argos=os.environ.get('RUEVALLEY_VERIFY_TRANSLATION')=='argos'
use_paragraph=os.environ.get('RUEVALLEY_VERIFY_PARAGRAPH')=='1'
artifacts = root / 'artifacts' / (('game-flow-rapid' if os.environ.get('RUEVALLEY_VERIFY_OCR')=='rapid' else 'game-flow')+('-argos' if use_argos else '')+('-paragraph' if use_paragraph else ''))
artifacts.mkdir(parents=True, exist_ok=True)
os.environ['RUEVALLEY_DATA_DIR'] = str(artifacts / 'test-data')
import desktop  # Bootstrap the shared C++ runtime before importing Qt.
from PyQt6.QtCore import QTimer, QRect, Qt
from PyQt6.QtTest import QTest
if os.environ.get('RUEVALLEY_VERIFY_WEB')=='1':
    from desktop.web_dashboard import install_dashboard
from PyQt6.QtGui import QPainter, QColor, QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication, QWidget
from desktop.window import Window, STYLE
import desktop.window as window_module
import shutil
def debug_job(self):
    try:
        self.result.emit(self.fn())
    except Exception as exc:
        import traceback
        traceback.print_exc()
        self.error.emit(str(exc))
window_module.Job.run = debug_job
real_recognize = window_module.recognize
def capture_ocr(path,**kwargs):
    shutil.copyfile(path, artifacts / 'captured.png')
    return real_recognize(path,**kwargs)
window_module.recognize = capture_ocr
import keyboard
import ctypes

def press_key(vk):
    # Inject externally to keyboard.send(), whose replay guard skips its own hooks.
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
    ctypes.windll.user32.keybd_event(vk, scan, 0, 0)
    QTimer.singleShot(150, lambda: ctypes.windll.user32.keybd_event(vk, scan, 2, 0))

app = QApplication(['RV-game-flow'])
QFontDatabase.addApplicationFont(str(root / 'Sarabun-Regular.ttf'))
QFontDatabase.addApplicationFont(str(root / 'PlaypenSansThai-Light.ttf'))
app.setStyleSheet(STYLE)
window = Window()
window.set_advanced_values({'ocr_backend':'rapid' if os.environ.get('RUEVALLEY_VERIFY_OCR')=='rapid' else 'native'})
if os.environ.get('RUEVALLEY_VERIFY_WEB')=='1': install_dashboard(window)

class GameFixture(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#202d2b'))
        for x in range(0, self.width(), 20):
            painter.fillRect(x, 0, 7, self.height(), QColor('#253431'))
        painter.setPen(QColor('#e7bc66'))
        if use_paragraph:
            painter.setFont(QFont('Arial',19))
            for i,line in enumerate(["You hungry?What can we get you? We've",
                                     'got those left overs from that Thai Me To',
                                     'The Moon place, the slice of cake from I Like',
                                     'Big Bundts. or the pizza from Pie On Life.',
                                     'Which will it be?']):painter.drawText(65,80+i*43,line)
        else:
            painter.setFont(QFont('Arial', 24))
            painter.drawText(85, 170, 'I still remember the night')
            painter.drawText(85, 211, 'you came back to the valley.')

fixture = GameFixture()
fixture.setWindowTitle('Game fixture — F1 global hotkey test')
fixture.setGeometry(180, 220, 900, 320)
fixture.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
if use_argos:window.switch_provider('argos')
else:window.auth.credentials = {'active':'fixture', 'accounts':[dict(client_id='fixture', email='fixture@example.invalid', access_token='fixture-token', expires_at=9999999999, scopes=['chatgpt.tokens.use.direct'])]}
window.models.clear()
window.models.addItem('Argos Local' if use_argos else 'Fixture', 'argos-balanced-v1' if use_argos else 'fixture')
window.source_language.select_language('auto' if use_argos else 'en');window.target_language.select_language('th')
window.region = QRect(fixture.geometry())
window.mode.setCurrentIndex(2)
seen_passages = []
real_translate=window.translator.translate
def translate_fixture(texts, token, model,**languages):
    seen_passages.extend(texts)
    if use_argos:return real_translate(texts,token,model,**languages)
    return ['ฉันยังจดจำค่ำคืนที่คุณกลับมายังหุบเขาแห่งนี้ได้' for _ in texts], 0
window.translator.translate = translate_fixture
window.refresh_accounts()
window.showMinimized()
fixture.show()
fixture.raise_()
fixture.activateWindow()
result = {'ok':False, 'source':window.settings.get('source_language'), 'translation':'actual Argos Local inference (no API call)' if use_argos else 'deterministic fixture (no API call)'}
selected_area=False

def trigger():
    fixture.grab().save(str(artifacts / 'before.png'))
    press_key(0x70)
QTimer.singleShot(1000, trigger)

ticks = 0
def poll():
    global ticks,selected_area
    ticks += 1
    if window.region_selecting and hasattr(window,'picker') and window.picker.isVisible() and not selected_area:
        selected_area=True
        result['f1_opened_crop_selector']=True
        QTest.mousePress(window.picker,Qt.MouseButton.LeftButton,pos=fixture.geometry().topLeft())
        QTest.mouseMove(window.picker,fixture.geometry().bottomRight(),50)
        QTest.mouseRelease(window.picker,Qt.MouseButton.LeftButton,pos=fixture.geometry().bottomRight())
        result['selected_region_used']=window.region==fixture.geometry()
    if window.overlay.items and not window.busy:
        result.update(ok=True, hotkey_outside_dashboard=True, dashboard_minimized=window.isMinimized(),
                      blended_patches=all('patch' in i for i in window.overlay.items), lines=len(window.overlay.items),
                      joined_sentence=(all(word in __import__('re').sub('[^a-z]','',' '.join(seen_passages).lower()) for word in ('hungry','cake','pizza','whichwillitbe')) if use_paragraph else len(seen_passages) == 1 and 'night you came back' in seen_passages[0]))
        result['recognized_passages']=list(seen_passages)
        result['translated_text']=[item['translation'] for item in window.overlay.items]
        if use_paragraph:
            result['all_paragraph_content_translated']=all(word in ' '.join(result['translated_text']) for word in ('หิว','เค้ก','พิซซ่า','ไหนดี'))
            result['ok']=result['ok'] and result['all_paragraph_content_translated']
        result['local_preview']=window.signal_canvas.before is not None and window.signal_canvas.after is not None
        result['preview_contains_blend']=window.signal_canvas.before != window.signal_canvas.after
        from desktop.text_layout import translation_layout
        sizes=[translation_layout(window.overlay.items[0],value)[3] for value in (12,20,36)]
        result['scale_font_pixels']=sizes
        result['scale_changes_font']=sizes[0]<sizes[1]<sizes[2]
        preview_keys=[]
        for value in (12,20,36):
            window.font_slider.setValue(value);preview_keys.append(window.signal_canvas.after.cacheKey())
            window.signal_canvas.after.save(str(artifacts/f'preview-scale-{value}.png'))
        result['scale_updates_capture_preview']=len(set(preview_keys))==3
        window.font_slider.setValue(20)
        sampled=window.overlay.items[0].get('text_color',(255,255,255))
        result['sampled_rgb']=sampled
        result['matches_source_color']=sum((a-b)**2 for a,b in zip(sampled,(231,188,102)))<30**2
        window.show()
        window.navigate(0)
        QTimer.singleShot(300,lambda:window.grab().save(str(artifacts/'studio-last-capture.png')))
        screen = app.primaryScreen()
        screen.grabWindow(0).toImage().copy(fixture.geometry()).save(str(artifacts / 'after.png'))
        press_key(0x71)
        QTimer.singleShot(500, finish)
        timer.stop()
    elif ticks > 70:
        result['error'] = window.message.text()
        timer.stop()
        finish()

def finish():
    result['f2_cleared'] = not window.overlay.items
    prior_region=QRect(window.region)
    prior_passages=len(seen_passages)
    window.showMinimized();fixture.raise_();fixture.activateWindow()
    press_key(0x70)
    tries=0
    def cancel_selection():
        nonlocal tries
        tries+=1
        if window.region_selecting and window.picker.isVisible():
            result['f1_reselects_saved_region']=True
            QTest.mousePress(window.picker,Qt.MouseButton.LeftButton,pos=__import__('PyQt6.QtCore',fromlist=['QPoint']).QPoint(15,15))
            QTest.mouseRelease(window.picker,Qt.MouseButton.LeftButton,pos=__import__('PyQt6.QtCore',fromlist=['QPoint']).QPoint(25,25))
            result['tiny_region_not_translated']=window.picker.isVisible() and not window.busy
            QTest.keyClick(window.picker,Qt.Key.Key_Escape)
            result['escape_cancelled_without_api']=not window.region_selecting and not window.busy and len(seen_passages)==prior_passages and window.region==prior_region
            complete()
        elif tries<30:QTimer.singleShot(100,cancel_selection)
        else:
            result['f1_reselects_saved_region']=False;complete()
    QTimer.singleShot(100,cancel_selection)

def complete():
    (artifacts / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    fixture.close()
    window.close()
    app.quit()

timer = QTimer()
timer.timeout.connect(poll)
timer.start(200)
if use_argos:
    from unittest.mock import patch
    import socket
    with patch.object(socket.socket,'connect',side_effect=AssertionError('Game flow attempted network access')):app.exec()
else:app.exec()
print(json.dumps(result, ensure_ascii=True))
sys.exit(0 if result['ok'] and result.get('f2_cleared') and result.get('joined_sentence') and result.get('matches_source_color') and result.get('escape_cancelled_without_api') and result.get('scale_changes_font') and result.get('scale_updates_capture_preview') else 1)
