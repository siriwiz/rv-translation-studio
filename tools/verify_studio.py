"""Functional desktop acceptance checks with isolated data and no OpenAI calls."""
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'.build-tools')]
target=root/'artifacts'/'studio-acceptance'
target.mkdir(parents=True,exist_ok=True)
os.environ['RUEVALLEY_DATA_DIR']=str(target/'test-data')
from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from desktop.window import Window, STYLE
from desktop.storage import read_json

app=QApplication([])
app.setStyle('Fusion'); app.setStyleSheet(STYLE)
for font in ('Sarabun-Regular.ttf','PlaypenSansThai-Light.ttf'):
    QFontDatabase.addApplicationFont(str(root/font))
window=Window(); window.show()
checks={}

def wait_for_jobs():
    deadline=time.monotonic()+5
    while window.jobs and time.monotonic()<deadline:
        QTest.qWait(30)
    assert not window.jobs,'Fixture job did not finish'

def check(name,value):
    checks[name]=bool(value)
    assert value,name

try:
    QTest.qWait(350)
    window.original_tab.click()
    check('original_tab',not window.signal_canvas.translated and window.original_tab.isChecked())
    window.translated_tab.click()
    check('translated_tab',window.signal_canvas.translated and not window.original_tab.isChecked())
    prior=window.smart_grouping.isChecked()
    QTest.mouseClick(window.smart_grouping,Qt.MouseButton.LeftButton)
    check('switch_mouse_hit',window.smart_grouping.isChecked()!=prior)
    window.smart_grouping.setChecked(True)
    window.match_colors.setChecked(False)
    check('color_toggle_saved',not read_json('settings.json',{})['match_colors'])
    window.match_colors.setChecked(True)
    window.font_slider.setValue(28)
    check('scale_saved',window.overlay.font_size==28 and read_json('settings.json',{})['font_size']==28)
    window.font_slider.setValue(20)
    window.auth.credentials={'active':'fixture','accounts':[dict(client_id='fixture',email='fixture@example.invalid',
        access_token='fake',expires_at=9999999999,scopes=['chatgpt.tokens.use.direct'])]}
    window.auth.models=lambda:[('fixture-1','Fixture One'),('fixture-2','Fixture Two')]
    window.settings['model']='fixture-2'
    window.load_models(); wait_for_jobs()
    check('reload_preserves_model',window.models.currentData()=='fixture-2')
    window.translator.translate=lambda texts,token,model,**languages:(['หุบเขาแห่งนี้ยังจดจำคุณได้' for _ in texts],0)
    window.test_input.setPlainText('The valley remembers you.')
    window.test_button.click(); wait_for_jobs()
    check('sample_job',window.test_output.text()=='หุบเขาแห่งนี้ยังจดจำคุณได้' and window.copy_sample_button.isEnabled())
    window.copy_sample_button.click()
    check('copy_sample',app.clipboard().text()==window.test_output.text())
    window.clear_sample()
    check('clear_sample',not window.test_input.toPlainText() and not window.copy_sample_button.isEnabled())
    check('language_catalog',window.target_language.count()>300 and window.source_language.findData('ja')>=0 and window.target_language.findData('ar')>=0)
    window.source_language.select_language('en'); window.target_language.select_language('ja')
    check('language_saved',read_json('settings.json',{})['target_language']=='ja')
    check('language_badges',all('JA' in badge.text() for badge in window.language_badges) and 'JA' in window.footer_mode.text())
    window.swap_language_pair()
    check('language_swap',window.language_pair()==('ja','en'))
    if not any(tag.startswith('ja') for tag,name in window.ocr_languages):
        window.capture()
        check('missing_ocr_blocks_capture',not window.busy and 'OCR is not installed' in window.message.text())
    window.source_language.select_language('auto'); window.target_language.setEditText('Klingon')
    window.language_changed()
    check('custom_language',window.language_pair()==('auto','custom:Klingon') and window.settings['target_language']=='custom:Klingon')
    window.swap_language_pair()
    check('auto_swap_guard',window.language_pair()==('auto','custom:Klingon'))
    window.source_language.select_language('en'); window.target_language.select_language('th')
    prior_generation=window.generation
    window.language_changed()
    check('language_focus_preserves_capture',window.generation==prior_generation)
    window.history=[]
    window.record([dict(text='The valley remembers you.',translation='หุบเขาแห่งนี้ยังจดจำคุณได้'),
                   dict(text='We should return before the storm.',translation='เราควรกลับไปก่อนพายุจะมา'),
                   dict(text='Do you remember the old station?',translation='คุณจำสถานีเก่าได้ไหม')])
    window.copy_latest.click()
    check('copy_latest',app.clipboard().text()=='คุณจำสถานีเก่าได้ไหม')
    window.navigate(1); QTest.qWait(300)
    window.history_search.setText('storm')
    check('history_search',sum(not window.table.isRowHidden(i) for i in range(3))==1)
    window.table.selectRow(1); window.copy_history_button.click()
    check('copy_history',app.clipboard().text()=='เราควรกลับไปก่อนพายุจะมา')
    window.history_search.setText('ไม่มีคำนี้')
    check('empty_search',window.history_empty.isVisible() and not window.table.isVisible())
    window.history_search.clear()
    export=target/'export.json'
    with patch('desktop.window.QFileDialog.getSaveFileName',return_value=(str(export),'JSON')):
        window.export_history()
    check('export_history',len(json.loads(export.read_text(encoding='utf-8')))==3)
    window.clear_history(); check('clear_history',not window.history and window.undo_history_button.isVisible())
    window.undo_history_button.click(); check('undo_clear',len(window.history)==3)
    window.table.selectRow(0)
    window.grab().save(str(target/'library-populated.png'))
    for width,height in ((1440,960),(1280,800),(1100,720)):
        window.resize(width,height)
        for index,name in enumerate(('studio','library','connection','settings')):
            window.navigate(index); QTest.qWait(300)
            scroll=window.pages.currentWidget()
            check(f'{name}_{width}_no_horizontal_overflow',scroll.widget().minimumSizeHint().width()<=scroll.viewport().width())
            scroll.verticalScrollBar().setValue(0)
            window.grab().save(str(target/f'{name}-{width}x{height}.png'))
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
            QTest.qWait(30)
            if index==0:
                center=window.clear_button.mapTo(scroll.viewport(),window.clear_button.rect().center())
                check(f'clear_button_{width}_reachable',scroll.viewport().rect().contains(center))
                window.grab().save(str(target/f'studio-bottom-{width}x{height}.png'))
    window.navigate(3)
    check('settings_page',window.pages.count()==4 and 'RV TRANSLATION STUDIO' in window.windowTitle())
    window.fast_preset()
    check('fast_preset_persisted',read_json('settings.json',{})['capture_delay']==120 and window.settings['capture_limit']==1920)
    window.advanced['subtitle_percent'].setValue(35)
    window.mode.setCurrentIndex(1)
    check('subtitle_setting_applied','35%' in window.region_info.text())
    window.cache_toggle.setChecked(False)
    check('cache_setting_applied',not window.translator.cache_enabled)
    window.click_clear_toggle.setChecked(False)
    check('overlay_setting_applied',not window.overlay.click_clear)
    window.advanced['request_timeout'].setValue(60)
    check('timeout_applied',window.translator.timeout==60)
    window.reset_advanced()
    check('advanced_reset',window.settings['capture_limit']==2500 and window.overlay.click_clear and window.translator.cache_enabled)
    window.connection.setText('ChatGPT connected')
    QTest.qWait(300)
    connection_frame=window.connection.grab().toImage()
    QTest.qWait(220)
    check('connection_heartbeat',connection_frame!=window.connection.grab().toImage())
    window.motion_toggle.setChecked(False)
    check('reduce_motion',not window.signal_canvas.timer.isActive())
    check('reduce_connection_motion',not window.connection.timer.isActive())
    window.navigate(0)
    check('reduced_page_transition',window.page_animation.duration()==0)
    window.motion_toggle.setChecked(True)
    window.region=QRect(70,80,600,250); window.mode.setCurrentIndex(2); window.save_settings()
    check('region_saved',read_json('settings.json',{})['region']==[70,80,600,250])
    window.auth.models=lambda: (_ for _ in ()).throw(RuntimeError('Fixture model failure'))
    window.load_models(); wait_for_jobs()
    check('error_recovery',not window.auth_busy and window.signal_canvas.phase=='error' and window.login_button.isEnabled())
    QTimer.singleShot(150,lambda:app.activeModalWidget().accept())
    window.show_help(); check('help_dialog',app.activeModalWidget() is None)
    checks['ok']=all(checks.values())
finally:
    (target/'result.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    window.close()
print(json.dumps(checks))
sys.exit(0 if checks.get('ok') else 1)
