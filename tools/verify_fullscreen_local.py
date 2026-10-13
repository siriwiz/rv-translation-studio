"""Actual fullscreen F1, bilingual OCR, partial capture and unchanged failed text."""
import ctypes,json,os,sys,time,socket
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'.build-tools')]
target=root/'artifacts/fullscreen-local';target.mkdir(parents=True,exist_ok=True)
import tempfile
os.environ['RUEVALLEY_DATA_DIR']=tempfile.mkdtemp(prefix='test-data-',dir=target)
import desktop
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtGui import QPainter,QFont,QFontDatabase,QColor
from PyQt6.QtWidgets import QApplication,QWidget
from desktop.window import Window,STYLE
from desktop.web_dashboard import install_dashboard
from desktop.text_layout import translation_layout

app=QApplication(['RV-fullscreen-local']);app.setStyleSheet(STYLE)
QFontDatabase.addApplicationFont(str(root/'PlaypenSansThai-Light.ttf'))
window=Window();install_dashboard(window)
import desktop.window as window_module,shutil
real_recognize=window_module.recognize
def recognize(path,**kwargs):
    shutil.copyfile(path,target/'captured.png');return real_recognize(path,**kwargs)
window_module.recognize=recognize
window.set_advanced_values({'ocr_backend':'rapid','ocr_language':'auto'})
window.source_language.select_language('auto');window.target_language.select_language('th')
window.switch_provider('argos');window.mode.setCurrentIndex(0)
routes=[];real_session=window.local_auth._session
def session(model):
    routes.append(model['source']+'-'+model['target']);return real_session(model)
window.local_auth._session=session

class Fixture(QWidget):
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#202d2b'));p.setPen(QColor('#e7bc66'))
        p.setFont(QFont('Arial',22))
        for x,y,text in [(60,75,'Settings'),(450,75,'Loading... 42%'),(950,75,'FPS: 60'),(60,155,'X'),
                         (100,300,'Hello, welcome back.'),(100,350,'The valley remembers you.'),
                         (950,220,'Continue.'),(950,270,'Back.'),(950,320,'Cancel.')]:p.drawText(x,y,text)
        p.setFont(QFont('Yu Gothic',24));p.drawText(100,450,'こんにちは。');p.drawText(100,510,'この谷はあなたを覚えています。')

fixture=Fixture();fixture.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint)
fixture.setGeometry(app.primaryScreen().geometry())
result={'ok':False};started=time.monotonic()
def begin():
    if window.auth_busy or not window.models.currentData():QTimer.singleShot(100,begin);return
    window.models.setCurrentIndex(window.models.findData('argos-quality-v1'))
    window.showMinimized();fixture.show();fixture.raise_();fixture.activateWindow()
    QTimer.singleShot(600,press)
def press():
    fixture.grab().save(str(target/'before.png'))
    ctypes.windll.user32.keybd_event(0x70,ctypes.windll.user32.MapVirtualKeyW(0x70,0),0,0)
    QTimer.singleShot(140,lambda:ctypes.windll.user32.keybd_event(0x70,ctypes.windll.user32.MapVirtualKeyW(0x70,0),2,0))
    QTimer.singleShot(350,poll)
def poll():
    if not window.busy and window.overlay.items:
        try:
            texts=[line['translation'] for line in window.overlay.items]
            result.update(fullscreen_capture=not window.region_selecting and window.mode.currentIndex()==0,
                routes=sorted(set(routes)),translations=texts,english_and_japanese_routes=all(code in routes for code in ('en-th','ja-en')),
                valid_passages_translated=len(texts)>=6,unknown_not_painted=all(line['text'].strip()!='X' for line in window.overlay.items),
                unknown_not_in_history=all(item['source'].strip()!='X' for item in window.history),
                skipped_count_visible='kept original' in window.metric_note.text(),
                unknown_not_cached=not any('"X"' in key for key in window.translator.cache),
                thai_font=translation_layout(window.overlay.items[0],20)[0].font().family()=='Playpen Sans Thai')
            result['fixture_actually_captured']=any('valley' in line['text'] for line in window.overlay.items) and any('谷' in line['text'] for line in window.overlay.items)
            english=dict(window.overlay.items[0],translation='Welcome back.',target_language='en')
            result['english_same_font']=translation_layout(english,20)[0].font().family()=='Playpen Sans Thai'
            result['status']=window.message.text()
            # The ambiguous X lives in this untouched region. No restored patch
            # may cross it; the screenshot remains the original game content.
            from PyQt6.QtCore import QRectF
            zone=QRectF(30,110,100,65)
            result['unknown_background_untouched']=all(not line['patch_rect'].intersects(zone) for line in window.overlay.items)
            app.primaryScreen().grabWindow(0).save(str(target/'after.png'))
            result['ok']=all(value for key,value in result.items() if isinstance(value,bool) and key!='ok')
        finally:finish()
    elif time.monotonic()-started>40:
        result['error']=window.message.text();finish()
    else:QTimer.singleShot(100,poll)
def finish():
    (target/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    fixture.close();window.close();app.quit()
QTimer.singleShot(100,begin)
with patch.object(socket.socket,'connect',side_effect=AssertionError('Fullscreen local attempted network')):app.exec()
print(json.dumps(result,ensure_ascii=True));sys.exit(0 if result['ok'] else 1)
