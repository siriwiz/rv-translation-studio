"""Exercise the actual embedded browser and desktop bridge using isolated data."""
import os,sys,json,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'.build-tools')]
target=root/'artifacts/daisyui-acceptance';target.mkdir(parents=True,exist_ok=True)
import tempfile
os.environ['RUEVALLEY_DATA_DIR']=tempfile.mkdtemp(prefix='test-data-',dir=target)
from desktop.web_dashboard import install_dashboard
from desktop.window import Window,STYLE
from desktop.storage import read_json,write_json
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtTest import QTest
app=QApplication(['RVStudio-acceptance']);app.setStyle('Fusion');app.setStyleSheet(STYLE)
for font in ('Sarabun-Regular.ttf','PlaypenSansThai-Light.ttf'):QFontDatabase.addApplicationFont(str(root/font))
write_json('settings.json',{'provider':'retired-provider'})
window=Window();window.setMinimumSize(420,600)
window.match_colors.setChecked(True);window.motion_toggle.setChecked(True);window.font_slider.setValue(20)
window.source_language.select_language('en');window.target_language.select_language('th')
window.advanced['request_timeout'].setValue(90)
install_dashboard(window);window.show()
checks={}

def js(code):
    output=[]
    window.web_dashboard.page().runJavaScript(code,lambda value:output.append(value))
    deadline=time.monotonic()+8
    while not output and time.monotonic()<deadline:QTest.qWait(20)
    assert output,'JavaScript did not respond'
    return output[0]

def until(fn,timeout=8):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if fn():return
        QTest.qWait(40)
    raise AssertionError('Timed out waiting for dashboard state')

def check(name,value):
    checks[name]=bool(value);assert value,name

try:
    check('retired_provider_recovers_to_chatgpt',window.provider=='openai' and window.settings['provider']=='openai')
    try:
        window.switch_provider('retired-provider')
    except ValueError:
        check('unsupported_provider_rejected',True)
    else:
        check('unsupported_provider_rejected',False)
    until(lambda:js("document.documentElement.dataset.ready")=='true')
    check('embedded_bridge_ready',window.web_dashboard.loaded)
    check('real_daisyui_theme',js("getComputedStyle(document.documentElement).getPropertyValue('--radius-box').trim()")=='.65rem')
    check('language_catalog',js("document.querySelectorAll('#target-languages option').length")>300)
    window.auth.credentials={'active':'fixture','accounts':[dict(client_id='fixture',email='fixture@example.invalid',access_token='fake',expires_at=9999999999,scopes=['chatgpt.tokens.use.direct'])]}
    window.models.clear();window.models.addItem('Fixture One','fixture-1');window.models.addItem('Fixture Two','fixture-2')
    window.refresh_accounts();window.web_dashboard.bridge.sync(True);QTest.qWait(100)
    check('connection_state',js("document.getElementById('connection-label').textContent")=='ChatGPT connected')
    js("document.getElementById('target-language').value='French';document.getElementById('target-language').dispatchEvent(new Event('change',{bubbles:true}))")
    until(lambda:window.settings.get('target_language')=='fr')
    check('language_bridge_persistence',read_json('settings.json',{})['target_language']=='fr')
    js("document.getElementById('model').value='fixture-2';document.getElementById('model').dispatchEvent(new Event('change',{bubbles:true}))")
    until(lambda:window.models.currentData()=='fixture-2');check('model_bridge',True)
    check('custom_selects_all',js("document.querySelectorAll('.rv-select-native').length===document.querySelectorAll('select').length"))
    js("document.getElementById('model-trigger').click()")
    check('custom_dropdown_open',js("document.querySelector('.rv-select-popup [role=listbox]')!==null && document.getElementById('model-trigger').getAttribute('aria-expanded')==='true'"))
    js("document.querySelector('.rv-select-popup .rv-option').click()")
    until(lambda:window.models.currentData()=='fixture-1');check('custom_dropdown_choice',True)
    js("document.getElementById('model-trigger').focus()")
    QTest.keyClick(window.web_dashboard.focusProxy(),Qt.Key.Key_Down);QTest.keyClick(window.web_dashboard.focusProxy(),Qt.Key.Key_End);QTest.keyClick(window.web_dashboard.focusProxy(),Qt.Key.Key_Return)
    until(lambda:window.models.currentData()=='fixture-2');check('custom_dropdown_keyboard',True)
    js("document.querySelector('[data-setting=match_colors]').click()")
    until(lambda:not window.match_colors.isChecked());check('toggle_bridge',not read_json('settings.json',{})['match_colors'])
    js("document.getElementById('font-size').value='28';document.getElementById('font-size').dispatchEvent(new Event('change',{bubbles:true}))")
    until(lambda:window.overlay.font_size==28);check('slider_bridge',True)
    js("document.querySelector('[data-page=settings]').click();document.querySelector('[data-settings-page=performance]').click()")
    until(lambda:window.pages.currentIndex()==3);check('settings_navigation',js("document.getElementById('settings-performance').classList.contains('active')"))
    js("document.querySelector('[data-setting=request_timeout]').value='60';document.querySelector('[data-setting=request_timeout]').dispatchEvent(new Event('change',{bubbles:true}))")
    until(lambda:window.translator.timeout==60);check('advanced_bridge',True)
    js("document.querySelector('[data-page=connection]').click()")
    until(lambda:window.pages.currentIndex()==2)
    window.translator.translate=lambda texts,token,model,**languages:(['La vallée se souvient de vous.' for text in texts],0)
    js("document.getElementById('sample-input').value='The valley remembers you.';document.getElementById('translate-sample').click()")
    until(lambda:not window.jobs and window.test_output.text()=='La vallée se souvient de vous.')
    QTest.qWait(250);check('sample_translation_bridge',js("document.getElementById('sample-output').textContent")=='La vallée se souvient de vous.')
    js("document.getElementById('copy-sample').click()")
    until(lambda:app.clipboard().text()=='La vallée se souvient de vous.');check('clipboard_bridge',True)
    window.history=[]
    window.record([dict(text='The old station.',translation='La vieille gare.'),dict(text='<img src=x onerror=window.xss=true>',translation='Safe text')])
    window.web_dashboard.bridge.sync(True)
    js("document.querySelector('[data-page=library]').click()")
    QTest.qWait(150)
    check('history_text_not_html',js("document.querySelector('#history-rows img')===null && !window.xss"))
    js("document.getElementById('history-search').value='station';document.getElementById('history-search').dispatchEvent(new Event('input',{bubbles:true}))")
    check('history_search',js("document.querySelectorAll('#history-rows tr').length")==1)
    js("document.querySelector('#history-rows tr').click();document.getElementById('copy-history').click()")
    until(lambda:app.clipboard().text()=='La vieille gare.');check('history_copy_bridge',True)
    js("document.getElementById('history-search').value='';document.getElementById('history-search').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('[data-action=clear_history]').click()")
    until(lambda:not window.history);check('history_clear_bridge',True)
    QTest.qWait(250);js("document.getElementById('undo-history').click()")
    until(lambda:len(window.history)==2);check('history_undo_bridge',True)
    js("document.querySelector('[data-help]').click()")
    check('help_dialog',js("document.getElementById('help-dialog').open"))
    window.web_dashboard.setFocus();QTest.keyClick(window.web_dashboard.focusProxy() or window.web_dashboard,Qt.Key.Key_Escape);QTest.qWait(80)
    check('help_escape',not js("document.getElementById('help-dialog').open"))
    js("document.querySelector('[data-page=settings]').click();document.querySelector('[data-settings-page=interface]').click();document.querySelector('[data-setting=motion]').click()")
    until(lambda:not window.settings['motion']);QTest.qWait(220)
    check('reduced_motion_bridge',js("document.body.classList.contains('reduced-motion')"))
    window.motion_toggle.setChecked(True);window.font_slider.setValue(20);window.match_colors.setChecked(True);window.target_language.select_language('th');window.source_language.select_language('en')
    window.web_dashboard.bridge.sync(True)
    QTest.qWait(250)
    check('language_reset_after_custom_edit',window.settings.get('target_language')=='th' and js("document.getElementById('target-language').value")=='Thai')
    for width,height in [(1920,1080),(1440,960),(1280,800),(1100,720),(980,680),(850,900),(540,850)]:
        window.resize(width,height)
        js("document.querySelector('[data-page=studio]').click()")
        QTest.qWait(450)
        check(f'no_horizontal_overflow_{width}',js("document.documentElement.scrollWidth<=window.innerWidth+1"))
        check(f'studio_no_scroll_{width}',js("(()=>{const v=document.getElementById('viewport');return v.scrollHeight<=v.clientHeight+1&&getComputedStyle(v).overflowY==='hidden'})()"))
        check(f'preview_visible_{width}',js("(()=>{const r=document.getElementById('scene').getBoundingClientRect();const v=document.getElementById('viewport').getBoundingClientRect();return r.height>=70&&r.top>=v.top&&r.bottom<=v.bottom})()"))
        if width>=980:
            check(f'controls_visible_{width}',js("(()=>{const p=document.querySelector('.console').getBoundingClientRect();return [...document.querySelectorAll('.console [data-setting]')].filter(n=>!n.classList.contains('rv-select-native')).every(n=>{const r=n.getBoundingClientRect();return r.top>=p.top&&r.bottom<=p.bottom})})()"))
        else:
            js("document.getElementById('capture-setup-toggle').click()")
            check(f'compact_controls_open_{width}',js("document.getElementById('page-studio').classList.contains('capture-open')"))
            js("document.getElementById('capture-setup-toggle').click()")
        check(f'translate_visible_{width}',js("(()=>{const r=document.getElementById('translate-screen').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.right<=innerWidth})()"))
        check(f'clear_visible_{width}',js("(()=>{const r=document.querySelector('[data-action=clear_overlay]').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.right<=innerWidth})()"))
        window.grab().save(str(target/f'studio-{width}x{height}.png'))
    window.resize(980,680)
    js("document.querySelector('[data-setting=mode]').value='2';document.querySelector('[data-setting=mode]').dispatchEvent(new Event('change',{bubbles:true}))")
    until(lambda:window.mode.currentIndex()==2);QTest.qWait(250)
    check('custom_area_button_label',js("document.getElementById('translate-screen-label').textContent")== 'Select & translate')
    check('custom_area_controls_visible',js("(()=>{const p=document.querySelector('.console').getBoundingClientRect();return [...document.querySelectorAll('.console input[type=checkbox]')].every(n=>n.getBoundingClientRect().bottom<=p.bottom)})()"))
    js("document.getElementById('capture-mode-trigger').click()")
    check('custom_area_dropdown_in_viewport',js("(()=>{const r=document.querySelector('.rv-select-popup').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.right<=innerWidth})()"))
    window.grab().save(str(target/'custom-area-dropdown.png'))
    js("window.RVControls.close()")
    window.mode.setCurrentIndex(0);window.web_dashboard.bridge.sync(True)
    window.showFullScreen();QTest.qWait(400)
    check('fullscreen_no_studio_scroll',js("document.getElementById('viewport').scrollHeight<=document.getElementById('viewport').clientHeight+1"))
    window.grab().save(str(target/'studio-fullscreen.png'))
    window.showNormal();QTest.qWait(100)
    window.resize(1440,960)
    for page in ['library','connection','settings']:
        js(f"document.querySelector('[data-page={page}]').click()")
        QTest.qWait(350);window.grab().save(str(target/f'{page}.png'))
    until(lambda:not window.ocr_languages_loading)
    installed=list(window.ocr_languages)
    window.ocr_languages=[]  # RapidOCR must remain usable on a PC without Windows OCR packs.
    js("document.querySelector('[data-settings-page=capture]').click();document.querySelector('[data-setting=ocr_backend]').value='rapid';document.querySelector('[data-setting=ocr_backend]').dispatchEvent(new Event('change',{bubbles:true}))")
    until(lambda:window.settings.get('ocr_backend')=='rapid')
    window.source_language.select_language('th');window.web_dashboard.bridge.sync(True);QTest.qWait(150)
    check('rapid_engine_saved',read_json('settings.json',{})['ocr_backend']=='rapid')
    check('rapid_profiles_without_windows_packs',js("document.getElementById('ocr-profile').options.length===12 && window.rvState.ocr_ready"))
    check('rapid_profile_follows_source',js("document.getElementById('ocr-short').textContent==='Thai / English'"))
    check('rapid_hides_windows_pack_link',js("getComputedStyle(document.getElementById('ocr-windows-packs')).display==='none'"))
    js("document.getElementById('ocr-profile').value='rapid:latin';document.getElementById('ocr-profile').dispatchEvent(new Event('change',{bubbles:true}))")
    until(lambda:window.settings.get('ocr_language')=='rapid:latin')
    window.fast_preset();check('fast_preset_preserves_engine',window.settings['ocr_backend']=='rapid')
    window.ocr_languages=installed
    window.set_advanced_values({'ocr_backend':'native'});window.set_advanced_values({'ocr_backend':'rapid'})
    check('per_engine_profile_restored',window.settings['ocr_language']=='rapid:latin')
    window.web_dashboard.bridge.sync(True);QTest.qWait(200)
    js("document.querySelector('[data-setting=ocr_backend]').closest('.setting-line').querySelector('.rv-select-trigger').click()")
    check('ocr_engine_dropdown_three_choices',js("document.querySelectorAll('.rv-select-popup .rv-option').length===3"))
    QTest.qWait(180);window.grab().save(str(target/'ocr-engine-dropdown.png'));js("window.RVControls.close()");QTest.qWait(120)
    window.grab().save(str(target/'rapid-ocr-settings.png'))
    window.ocr_language.setCurrentIndex(0);window.source_language.select_language('bn');window.web_dashboard.bridge.sync(True)
    check('unsupported_rapid_language_is_explicit',not window.web_dashboard.bridge.snapshot()['ocr_ready'])
    window.source_language.select_language('en');window.set_advanced_values({'ocr_backend':'native'})
    window.chatgpt_auth.models=lambda:[('fixture-1','Fixture One'),('fixture-2','Fixture Two')]
    check('only_supported_providers',js("[...document.getElementById('provider').options].map(n=>n.value).join(',')==='openai,argos'"))
    check('generated_artwork_loaded',js("document.querySelector('.scene-art').tagName==='IMG' && document.querySelector('.scene-art').complete && document.querySelector('.scene-art').naturalWidth>1000"))
    check('generated_logo_loaded',js("document.querySelector('.brand-mark').tagName==='IMG' && document.querySelector('.brand-mark').complete && document.querySelector('.brand-mark').naturalWidth>1000"))
    check('chatgpt_account_preserved',window.chatgpt_auth.account['email']=='fixture@example.invalid')
    from desktop.translation import Translator
    window.translator.translate=Translator.translate.__get__(window.translator)
    js("document.getElementById('font-size').value='36';document.getElementById('font-size').dispatchEvent(new Event('input',{bubbles:true}))")
    until(lambda:window.overlay.font_size==36);check('live_scale_input_bridge',True)
    window.switch_provider('argos');until(lambda:not window.auth_busy and str(window.models.currentData()).startswith('argos-'))
    window.models.setCurrentIndex(window.models.findData('argos-balanced-v1'))
    window.source_language.select_language('fr');window.target_language.select_language('th');window.refresh_accounts();window.web_dashboard.bridge.sync(True);QTest.qWait(150)
    check('argos_ready_without_login',window.is_connected and window.auth.account is not None)
    check('argos_offline_label',js("document.getElementById('connection-label').textContent==='Argos Local · Offline'"))
    check('argos_hides_cloud_credentials',js("['login','sign-out','manage-usage','saved-accounts-field'].every(id=>getComputedStyle(document.getElementById(id)).display==='none')"))
    check('argos_ten_language_choices',js("window.rvState.local_language_choices.length===10"))
    js("document.querySelector('#source-language').closest('.rv-select').querySelector('button').click()")
    check('argos_auto_option_visible',js("[...document.querySelectorAll('.rv-option')].some(n=>n.textContent.includes('Auto detect'))"))
    js("[...document.querySelectorAll('.rv-option')].find(n=>n.textContent.includes('Auto detect')).click()")
    until(lambda:window.settings.get('source_language')=='auto')
    window.web_dashboard.bridge.sync(True);QTest.qWait(150)
    check('argos_auto_ready_and_persisted',js("window.rvState.ready && !document.getElementById('translate-sample').disabled") and read_json('settings.json',{})['source_language']=='auto')
    from unittest.mock import patch
    import socket
    with patch.object(socket.socket,'connect',side_effect=AssertionError('Local UI called network')):
        js("document.getElementById('sample-input').value='La vallée se souvient de vous.';document.getElementById('translate-sample').click()")
        until(lambda:not window.jobs and any('\u0e00'<=char<='\u0e7f' for char in window.test_output.text()),timeout=30)
    window.web_dashboard.bridge.sync(True);QTest.qWait(250)
    check('argos_actual_local_sample_translation',js("/[\\u0E00-\\u0E7F]/.test(document.getElementById('sample-output').textContent)"))
    check('argos_auto_source_after_translation',window.settings.get('source_language')=='auto' and window.local_auth.detector.detect('La vallée se souvient de vous.')=='fr')
    window.grab().save(str(target/'argos-local-connection.png'))
    js("document.getElementById('model').value='argos-quality-v1';document.getElementById('model').dispatchEvent(new Event('change',{bubbles:true}))")
    until(lambda:window.models.currentData()=='argos-quality-v1')
    paragraph="You hungry?What can we get you? We've got those left overs from that Thai Me To The Moon place, the slice of cake from I Like Big Bundts. or the pizza from Pie On Life. Which will it be?"
    with patch.object(socket.socket,'connect',side_effect=AssertionError('Paragraph UI called network')):
        js("document.getElementById('sample-input').value="+json.dumps(paragraph)+";document.getElementById('translate-sample').click()")
        until(lambda:not window.jobs and all(word in window.test_output.text() for word in ('หิว','เค้ก','พิซซ่า','ไหนดี')),timeout=30)
    check('argos_quality_translates_full_paragraph',True)
    window.navigate(1);window.web_dashboard.bridge.sync(True);QTest.qWait(250)
    js("document.getElementById('history-search').value='';document.getElementById('history-search').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#history-rows tr td:nth-child(3)').click()")
    check('library_selected_passage_contains_complete_translation',js("['เค้ก','พิซซ่า','ไหนดี'].every(word=>document.getElementById('detail-translation').textContent.includes(word))"))
    QTest.qWait(200)
    window.grab().save(str(target/'argos-full-paragraph-library.png'))
    window.navigate(2);window.web_dashboard.bridge.sync(True);QTest.qWait(100)
    mixed='こんにちは。Hello, welcome back.'
    with patch.object(socket.socket,'connect',side_effect=AssertionError('Mixed dialogue UI called network')):
        js("document.getElementById('sample-input').value="+json.dumps(mixed)+";document.getElementById('translate-sample').click()")
        until(lambda:not window.jobs and 'สวัสดี' in window.test_output.text() and 'ต้อนรับ' in window.test_output.text(),timeout=30)
    check('auto_mixed_japanese_english_workbench',True)
    window.target_language.select_language('en');window.web_dashboard.bridge.sync(True);QTest.qWait(100)
    with patch.object(socket.socket,'connect',side_effect=AssertionError('English font sample called network')):
        js("document.getElementById('sample-input').value="+json.dumps(mixed)+";document.getElementById('translate-sample').click()")
        until(lambda:not window.jobs and 'welcome back' in window.test_output.text().lower(),timeout=30)
    window.web_dashboard.bridge.sync(True);QTest.qWait(200)
    check('english_dialogue_uses_original_thai_font',js("getComputedStyle(document.getElementById('sample-output')).fontFamily.includes('Playpen Sans Thai') && document.fonts.check('16px \"Playpen Sans Thai\"','Welcome back')"))
    check('captured_english_uses_same_font',js("getComputedStyle(document.getElementById('detail-source')).fontFamily.includes('Playpen Sans Thai')"))
    window.grab().save(str(target/'mixed-dialogue-english-font.png'))
    window.target_language.select_language('th')
    window.source_language.select_language('ar');window.web_dashboard.bridge.sync(True);QTest.qWait(100)
    check('argos_unsupported_language_disables_sample',js("document.getElementById('translate-sample').disabled && window.rvState.local_route_error.length>0"))
    window.source_language.select_language('en');window.target_language.select_language('th')
    window.switch_provider('openai');until(lambda:not window.auth_busy)
    check('no_javascript_errors',not window.web_dashboard.dashboard_page.errors)
    checks['ok']=all(checks.values())
finally:
    (target/'result.json').write_text(json.dumps(dict(checks=checks,console_errors=window.web_dashboard.dashboard_page.errors),indent=2),encoding='utf-8')
    window.close();app.processEvents()
print(json.dumps(checks));sys.exit(0 if checks.get('ok') else 1)
