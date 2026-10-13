"""Packaged-browser smoke check; uses isolated data and never calls OpenAI."""
import json
from pathlib import Path
from PyQt6.QtCore import QTimer,Qt
from PyQt6.QtGui import QImage,QColor,QPainter,QFont
from .languages import language_catalog
from .native_ocr import recognize_native


def start_smoke(window,target):
    target=Path(target);target.mkdir(parents=True,exist_ok=True)
    view=window.web_dashboard
    result={'ok':False,'web_loaded':False}
    attempts=0

    def finish():
        result['javascript_errors']=view.dashboard_page.errors
        result['ok']=all(result.get(key) for key in ('web_loaded','daisyui_theme','ocr','rapid_ocr','rapid_multilingual','language_controls','brand_assets','two_providers','text_scale','thai_wrapping','argos_offline','argos_auto_detect','argos_complete_paragraph','argos_bilingual','argos_fullscreen_safe','english_original_font')) and not result['javascript_errors']
        (target/'smoke-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        window.close()

    def local_checks():
        try:
            image=QImage(900,180,QImage.Format.Format_RGB32);image.fill(QColor('white'))
            painter=QPainter(image);painter.setPen(QColor('black'));painter.setFont(QFont('Arial',34))
            painter.drawText(25,95,'The valley remembers you.');painter.end()
            path=target/'ocr-test.png';image.save(str(path))
            result.update(ocr=any('valley' in item['text'].lower() for item in recognize_native(path.resolve())),
                          ocr_backend='native',languages=len(language_catalog()),pages=window.pages.count(),
                          screens=window.screen.count(),hotkeys=len(window.hotkey_bridge.handles) or len(window.hotkey_ids))
            from .translation import recognize
            from unittest.mock import patch
            import socket
            with patch.object(socket.socket,'connect',side_effect=RuntimeError('OCR must stay offline')):
                result['rapid_ocr']=any('valley' in item['text'].lower() for item in recognize(path,'rapid','rapid:en'))
                multilingual={}
                for code,text,font,expected in [('th','หุบเขาจดจำคุณได้','Sarabun','หุบเขา'),('ch','この谷はあなたを覚えている。','Yu Gothic','この谷'),('arabic','الوادي يتذكرك','Segoe UI','الوادي')]:
                    image.fill(QColor('white'));painter=QPainter(image);painter.setPen(QColor('black'));painter.setFont(QFont(font,34))
                    painter.drawText(25,95,text);painter.end();path=target/f'rapid-{code}.png';image.save(str(path))
                    multilingual[code]=any(expected in line['text'] for line in recognize(path,'rapid','rapid:'+code))
                result['rapid_multilingual']=all(multilingual.values());result['rapid_samples']=multilingual
                from .text_layout import translation_layout,display_text,paint_translation
                item=dict(x=30,y=40,w=400,h=60,line_height=28,translation='ฉันยังจดจำค่ำคืนที่คุณกลับมายังหุบเขาแห่งนี้ได้',target_language='th',text_bounds=(0,0,900,180))
                sizes=[translation_layout(item,v)[3] for v in (12,20,36)]
                result['text_scale']=sizes[0]<sizes[1]<sizes[2];result['scale_font_pixels']=sizes
                result['thai_wrapping']='\u200b' in display_text(item['translation'],'th')
                from .local_translation import LocalTranslator
                local=LocalTranslator()
                try:
                    local_samples={}
                    for source,destination,text in [('en','th','The valley remembers you.'),('ja','th','この谷はあなたを覚えています。'),('es','en','El valle te recuerda.')]:
                        output=local.complete(None,'argos-balanced-v1',[text],source=source,target=destination)
                        local_samples[source+'-'+destination]=bool(output and output[0])
                    result['argos_offline']=all(local_samples.values());result['argos_samples']=local_samples
                    result['argos_languages']=len(local.catalog['languages']);result['argos_model_sessions']=len(local.sessions)
                    samples={'en':'The valley remembers you.','th':'หุบเขายังจำคุณได้','zh':'这个山谷还记得你。','ja':'この谷はあなたを覚えています。',
                             'ko':'이 계곡은 당신을 기억합니다.','fr':'La vallée se souvient de vous.','de':'Das Tal erinnert sich an dich.',
                             'es':'El valle te recuerda.','vi':'Thung lũng vẫn nhớ bạn.','ru':'Долина помнит тебя.'}
                    result['argos_detected_languages']={code:local.detector.detect(text) for code,text in samples.items()}
                    auto_texts=[samples[code] for code in ('en','fr','ja','th')]+['123…']
                    auto=local.complete(None,'argos-balanced-v1',auto_texts,source='auto',target='th')
                    result['argos_auto_detect']=all(code==detected for code,detected in result['argos_detected_languages'].items()) and len(auto)==5 and auto[3:]==auto_texts[3:] and all(any('\u0e00'<=c<='\u0e7f' for c in text) for text in auto[:3])
                    paragraph="You hungry?What can we get you? We've got those left overs from that Thai Me To The Moon place, the slice of cake from I Like Big Bundts. or the pizza from Pie On Life. Which will it be?"
                    result['argos_paragraph_samples']={mode:local.complete(None,mode,[paragraph],source='auto',target='th')[0] for mode in ('argos-fast-v1','argos-balanced-v1','argos-quality-v1')}
                    result['argos_complete_paragraph']=all(all(word in translated for word in ('หิว','เค้ก','พิซซ่า','ไหนดี')) for translated in result['argos_paragraph_samples'].values())
                    bilingual=local.complete(None,'argos-balanced-v1',['こんにちは。Hello, welcome back.','こんにちは Hello, welcome back.'],source='auto',target='th')
                    result['argos_bilingual']=all('สวัสดี' in value and 'ต้อนรับ' in value for value in bilingual)
                    symbols=local.complete(None,'argos-quality-v1',['Continue.\n_\nBack.'],source='auto',target='th')
                    partial=local.complete_screen(None,'argos-quality-v1',['Hello, welcome back.','X','こんにちは。'],source='auto',target='th')
                    result['argos_fullscreen_safe']='_' in symbols[0] and bool(partial[0]) and partial[1] is None and bool(partial[2])
                    from .languages import overlay_font
                    result['english_original_font']=overlay_font('en')==overlay_font('th')=='Playpen Sans Thai' and QFont(overlay_font('en')).exactMatch()
                finally:local.stop()
                for value in (12,20,36):
                    rendered=QImage(900,180,QImage.Format.Format_RGB32);rendered.fill(QColor('#202d2b'));p=QPainter(rendered);paint_translation(p,item,value);p.end();rendered.save(str(target/f'scale-{value}.png'))
            window.set_advanced_values({'ocr_backend':'rapid'});window.navigate(3);view.bridge.sync(True)
            QTimer.singleShot(100,lambda:window.grab().save(str(target/'rapid-ocr-settings.png')))
            window.target_language.select_language('ja')
            result['language_controls']=all('JA' in badge.text() for badge in window.language_badges)
            window.navigate(0);view.bridge.sync(True)
            def capture():
                window.grab().save(str(target/'languages-preview.png'));window.target_language.select_language('th')
                if not window.auth.account:
                    from .window import USER32,wintypes
                    USER32.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
                    USER32.SendMessageW.restype=wintypes.LPARAM
                    window.navigate(0);USER32.SendMessageW(int(window.winId()),0x0312,4101,0)
                    result['hotkey_routing']=window.pages.currentIndex()==2
                finish()
            QTimer.singleShot(200,capture)
        except Exception as exc:
            result['error']=type(exc).__name__+': '+str(exc);finish()

    screens=[(0,'ui-preview.png'),(1,'library-preview.png'),(2,'account-preview.png'),(3,'settings-preview.png')]
    def capture_page(index=0):
        if index>=len(screens): local_checks();return
        page,name=screens[index];window.navigate(page);view.bridge.sync(True)
        def take():
            window.grab().save(str(target/name));capture_page(index+1)
        QTimer.singleShot(200,take)

    def ready(value):
        nonlocal attempts
        if value:
            result['web_loaded']=True
            view.page().runJavaScript("getComputedStyle(document.documentElement).getPropertyValue('--radius-box').trim()==='.65rem'",theme)
        else:
            attempts+=1
            if attempts>50: result['error']='Dashboard did not initialize';finish()
            else:QTimer.singleShot(200,poll)
    def theme(value):
        result['daisyui_theme']=bool(value)
        view.page().runJavaScript("({brand:[...document.querySelectorAll('.brand-mark,.scene-art')].every(n=>n.tagName==='IMG'&&n.complete&&n.naturalWidth>1000),providers:[...document.getElementById('provider').options].map(n=>n.value).join(',')})",brand)
    def brand(value):
        result['brand_assets']=bool(value and value.get('brand'))
        result['two_providers']=bool(value and value.get('providers')=='openai,argos')
        capture_page()
    def poll():view.page().runJavaScript("document.documentElement.dataset.ready==='true'",ready)
    QTimer.singleShot(300,poll)
