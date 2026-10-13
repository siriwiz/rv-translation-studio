"""Real multilingual CPU recognition with networking blocked, no translation API."""
import sys, json, time, socket, unicodedata
from pathlib import Path
from difflib import SequenceMatcher
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'.build-tools')]
import desktop  # Load the compatible C++ runtime before Qt.
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage,QPainter,QColor,QFont,QFontDatabase
from PyQt6.QtCore import Qt,QRect
from desktop.translation import recognize
from desktop.blend import make_patch,image_to_bgr
from desktop.colors import sample_text_color
from desktop.paragraphs import group_dialogue
app=QApplication(['RV-OCR-verification'])
QFontDatabase.addApplicationFont(str(root/'Sarabun-Regular.ttf'))
target=root/'artifacts/rapid-ocr';target.mkdir(parents=True,exist_ok=True)
samples=[
    ('en','en','The valley remembers you.','Arial'),
    ('th','th','หุบเขาแห่งนี้ยังจดจำคุณได้','Sarabun'),
    ('ja','ch','この谷はあなたを覚えている。','Yu Gothic'),
    ('zh','ch','山谷依然记得你。','Microsoft YaHei'),
    ('ko','korean','이 계곡은 당신을 기억합니다.','Malgun Gothic'),
    ('fr','latin','La vallée se souvient de vous.','Arial'),
    ('ru','cyrillic','Долина помнит тебя.','Arial'),
    ('ar','arabic','الوادي يتذكرك','Segoe UI'),
    ('hi','devanagari','यह घाटी आपको याद करती है','Nirmala UI'),
    ('el','el','Η κοιλάδα σε θυμάται.','Arial'),
    ('ta','ta','இந்த பள்ளத்தாக்கு உங்களை நினைவில் கொள்கிறது','Nirmala UI'),
    ('te','te','ఈ లోయ మిమ్మల్ని గుర్తుంచుకుంటుంది','Nirmala UI'),
]


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFC',text).casefold() if c.isalpha())


results={}
with patch.object(socket.socket,'connect',side_effect=AssertionError('OCR attempted network access')),patch.object(socket,'create_connection',side_effect=AssertionError('OCR attempted network access')):
    for code,profile,text,font in samples:
        image=QImage(1500,180,QImage.Format.Format_RGB32);image.fill(QColor('#202d2b'))
        painter=QPainter(image);painter.setPen(QColor('#e7bc66'));painter.setFont(QFont(font,30))
        painter.drawText(QRect(30,25,1440,130),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,text);painter.end()
        path=target/f'{code}.png';image.save(str(path))
        start=time.monotonic();lines=recognize(path,'rapid','rapid:'+profile);cold=time.monotonic()-start
        start=time.monotonic();recognize(path,'rapid','rapid:'+profile);warm=time.monotonic()-start
        output=' '.join(line['text'] for line in lines)
        similarity=SequenceMatcher(None,normalized(text),normalized(output)).ratio()
        result=dict(expected=text,recognized=output,similarity=round(similarity,3),first_ms=round(cold*1000),warm_ms=round(warm*1000),words=sum(len(l['words']) for l in lines),ok=similarity>=.7)
        if lines:
            frame=image_to_bgr(image);clean,rect=make_patch(frame,lines[0]);result['sampled_color']=sample_text_color(frame,lines[0],clean,rect)['text_color']
        results[code]=result
        print(code,json.dumps(result,ensure_ascii=True),flush=True)
    fixture=root/'artifacts/game-flow/captured.png'
    if fixture.exists():
        lines=recognize(fixture,'rapid','rapid:en')
        results['dialogue_join']={'ok':[l['text'] for l in group_dialogue(lines)]==['I still remember the night you came back to the valley.']}
(target/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
if not all(r['ok'] for r in results.values()):sys.exit(1)
print('All multilingual OCR checks passed with network blocked.')
