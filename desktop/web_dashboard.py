"""Offline daisyUI dashboard connected to the existing native application."""
import json
from pathlib import Path
from PyQt6.QtCore import QObject, QTimer, QUrl, QBuffer, QIODevice, pyqtSignal, pyqtSlot, Qt, QCoreApplication
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
from PyQt6.QtWidgets import QApplication, QComboBox, QSpinBox
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineUrlRequestInterceptor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from .storage import resource
from .languages import language_catalog, language_badge,language_name
from .ocr_profiles import resolve_ocr_language, profiles_for


class LocalAssets(QWebEngineUrlRequestInterceptor):
    def __init__(self,root,parent):
        super().__init__(parent); self.root=root.resolve()

    def interceptRequest(self,info):
        url=info.requestUrl()
        if url.scheme() in ('qrc','data','about'): return
        if url.isLocalFile() and Path(url.toLocalFile()).resolve().is_relative_to(self.root): return
        info.block(True)


class DashboardPage(QWebEnginePage):
    def __init__(self,profile,parent,root):
        super().__init__(profile,parent); self.root=root.resolve(); self.errors=[]

    def acceptNavigationRequest(self,url,kind,main):
        return url.isLocalFile() and Path(url.toLocalFile()).resolve().is_relative_to(self.root)

    def javaScriptConsoleMessage(self,level,message,line,source):
        if level==QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.errors.append(f'{Path(source).name}:{line}: {message}')


class StudioBridge(QObject):
    stateChanged=pyqtSignal(str)

    def __init__(self,window):
        super().__init__(window); self.window=window; self.previous=''; self.preview_keys=None; self.previews=('', '')

    def combo(self,widget,index=False):
        return [dict(label=widget.itemText(i),value=i if index else widget.itemData(i)) for i in range(widget.count())]

    def preview(self):
        canvas=self.window.signal_canvas
        images=(canvas.before,canvas.after)
        keys=tuple(image.cacheKey() if image is not None else None for image in images)
        if keys!=self.preview_keys:
            result=[]
            for image in images:
                if image is None: result.append(''); continue
                scaled=image.scaled(1400,800,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
                data=QBuffer();data.open(QIODevice.OpenModeFlag.WriteOnly);scaled.save(data,'PNG')
                result.append('data:image/png;base64,'+bytes(data.data().toBase64()).decode('ascii'))
            self.previews=tuple(result);self.preview_keys=keys
        return self.previews

    def snapshot(self):
        w=self.window
        settings=dict(w.settings)
        settings.update(font_size=w.font_slider.value(),mode=w.mode.currentIndex(),screen=w.screen.currentIndex(),
                        smart_grouping=w.smart_grouping.isChecked(),hide_capture=w.hide_capture.isChecked(),
                        match_colors=w.match_colors.isChecked(),motion=w.motion_toggle.isChecked(),
                        cache_enabled=w.cache_toggle.isChecked(),click_clear=w.click_clear_toggle.isChecked())
        for key,control in w.advanced.items(): settings[key]=control.value() if isinstance(control,QSpinBox) else control.currentData()
        source,target=w.settings.get('source_language','en'),w.settings.get('target_language','th')
        account=w.auth.account
        connected=w.is_connected
        before,after=self.preview()
        history=[dict(item,pair=language_badge(item.get('source_language','en'))+' → '+language_badge(item.get('target_language','th'))) for item in reversed(w.history)]
        try:
            active_ocr=resolve_ocr_language(source,w.ocr_languages,settings.get('ocr_language','auto'),settings.get('ocr_backend','native'))
            ocr_ready=settings.get('ocr_backend')=='rapid' or w.ocr_languages_loaded
            ocr_name=dict(profiles_for(settings.get('ocr_backend','native'),w.ocr_languages)).get(active_ocr,active_ocr)
        except RuntimeError: ocr_ready=False;ocr_name='Supported OCR profile needed'
        return dict(page=w.pages.currentIndex(),busy=w.busy,auth_busy=w.auth_busy,phase=w.signal_canvas.phase,provider=w.provider,provider_label=w.provider_label,
                    local_languages=list(w.local_auth.catalog['languages'].values()),local_route_error=w.local_route_error,
                    local_language_choices=[dict(code='zh-Hans' if code=='zh' else code,name=language_name('zh-Hans' if code=='zh' else code)) for code in w.local_auth.catalog['languages']],
                    settings=settings,source=source,target=target,pair=language_badge(source)+' → '+language_badge(target),
                    connected=connected,ready=bool(connected and w.models.currentData() and not w.local_route_error),ocr_ready=ocr_ready,
                    ocr_note=w.ocr_language_note.text(),ocr_active=ocr_name,ocr_languages=[dict(label=name,value=tag) for tag,name in profiles_for(settings.get('ocr_backend','native'),w.ocr_languages)],
                    screens=self.combo(w.screen,True),models=self.combo(w.models),model=w.models.currentData(),
                    accounts=[dict(label=a['email'],value=i) for i,a in enumerate(w.auth.credentials['accounts'])],
                    account_index=w.accounts.currentIndex(),account_name=w.account_text.text(),account_plan=w.plan_text.text(),
                    login_pending=not w.cancel_login.isHidden(),capture_enabled=w.capture_button.isEnabled(),
                    sample_enabled=w.test_button.isEnabled(),sample_copy=w.copy_sample_button.isEnabled(),
                    sample_input=w.test_input.toPlainText(),sample_output=w.test_output.text(),
                    latest_source=w.history[-1]['source'] if w.history else '',latest_translation=w.history[-1]['translation'] if w.history else '',
                    history=history,has_history=bool(w.history),undo_history=bool(getattr(w,'history_backup',None)),
                    region=w.region_info.text(),readiness=w.readiness.text(),message=w.message.text(),
                    metric_time=w.stats.text(),metric_note=w.metric_note.text(),session_passages=w.session_passages,session_cache=w.session_cache_hits,
                    cache_size=w.cache_size.text(),timings=getattr(w,'last_timings',{}),performance_detail=w.performance_detail.text(),
                    preview_before=before,preview_after=after,preview_caption=w.preview_caption.text())

    @pyqtSlot(result=str)
    def bootstrap(self):
        return json.dumps(dict(languages=[dict(code=code,name=name) for code,name in language_catalog()],state=self.snapshot()),ensure_ascii=False)

    def sync(self,force=False):
        payload=json.dumps(self.snapshot(),ensure_ascii=False)
        if force or payload!=self.previous:
            self.previous=payload;self.stateChanged.emit(payload)

    def languages(self,payload):
        w=self.window
        w.source_language.setEditText(str(payload['source'])[:80]);w.target_language.setEditText(str(payload['target'])[:80])
        w.language_changed()
        w.language_pair()  # Validate before an action can use it.

    @pyqtSlot(str)
    def dispatch(self,payload):
        w=self.window
        try:
            data=json.loads(payload); action=data.get('action')
            if w.busy and action not in ('navigate','clear_overlay','copy_latest','copy_sample','copy_history','preview','sample_input'):
                w.status('Wait for the current translation to finish.'); return
            if action=='navigate': w.navigate(max(0,min(3,int(data['index']))))
            elif action=='languages': self.languages(data)
            elif action=='swap': w.swap_language_pair()
            elif action=='capture':
                self.languages(data);w.capture()
            elif action=='sample':
                w.test_input.setPlainText(str(data.get('text',''))[:4000]);w.test_translation()
            elif action=='sample_input': w.test_input.setPlainText(str(data.get('text',''))[:4000])
            elif action=='preview': w.set_preview(bool(data['translated']))
            elif action=='copy_history':
                entries=list(reversed(w.history));rows=sorted({int(i) for i in data.get('rows',[]) if isinstance(i,int) and 0<=i<len(entries)})
                if rows:
                    QApplication.clipboard().setText('\n\n'.join(entries[i]['translation'] for i in rows));w.status(f'Copied {len(rows)} translation(s)')
            elif action=='setting': self.setting(data['key'],data['value'])
            else:
                callbacks={'clear_overlay':w.clear_overlay,'copy_latest':w.copy_latest_translation,'copy_sample':w.copy_sample,
                           'clear_sample':w.clear_sample,'export_history':w.export_history,'clear_history':w.clear_history,
                           'undo_history':w.undo_clear_history,'login':w.login,'add_account':lambda:w.login(new=True),
                           'cancel_login':w.auth.cancel.set,'reload_models':w.load_models,'manage_usage':w.manage_usage,'create_gemini_key':w.create_gemini_key,
                           'logout':w.logout,'pick_region':w.pick_region,'reload_languages':w.reload_ocr_languages,
                           'language_packs':w.open_language_settings,'fast_preset':w.fast_preset,'clear_cache':w.clear_translation_cache,
                           'reset_advanced':w.reset_advanced,'reset_scale':lambda:w.font_slider.setValue(20)}
                if action not in callbacks: raise ValueError('Unknown desktop action.')
                callbacks[action]()
        except (ValueError,KeyError,TypeError) as exc:
            w.status('Unable to apply this control. Check the entered value.');w.set_phase('error')
        except RuntimeError as exc: w.show_error(str(exc))
        finally: self.sync()

    def setting(self,key,value):
        w=self.window
        toggles={'smart_grouping':w.smart_grouping,'hide_capture':w.hide_capture,'match_colors':w.match_colors,
                 'motion':w.motion_toggle,'cache_enabled':w.cache_toggle,'click_clear':w.click_clear_toggle}
        if key in toggles:
            if not isinstance(value,bool): raise ValueError('Expected a switch value')
            toggles[key].setChecked(value)
        elif key=='provider':w.switch_provider(str(value))
        elif key=='gemini_auth_mode':w.switch_gemini_mode(str(value))
        elif key=='gemini_project':
            import re
            project=str(value).strip()
            if project and not re.fullmatch(r'[a-z][a-z0-9-]{4,62}',project):raise ValueError('Enter a Google Cloud project ID.')
            w.settings[key]=project;w.gemini_auth.cli.stop();w.save_settings()
        elif key=='font_size': w.font_slider.setValue(int(value))
        elif key in ('screen','mode','account'):
            control={'screen':w.screen,'mode':w.mode,'account':w.accounts}[key]
            index=int(value)
            if not 0<=index<control.count(): raise ValueError('Invalid selection')
            control.setCurrentIndex(index)
        elif key in ('model','ocr_language'):
            control=w.models if key=='model' else w.ocr_language
            index=control.findData(value)
            if index<0: raise ValueError('Unavailable selection')
            control.setCurrentIndex(index)
        elif key in w.advanced:
            control=w.advanced[key]
            if isinstance(control,QSpinBox): control.setValue(int(value))
            else:
                index=control.findData(int(value) if key=='capture_limit' else value)
                if index<0: raise ValueError('Unavailable selection')
                control.setCurrentIndex(index)
        else: raise ValueError('Unknown setting')


class WebDashboard(QWebEngineView):
    def __init__(self,window):
        super().__init__(window)
        root=resource('ui/dist')
        self.profile=QWebEngineProfile(self)
        self.interceptor=LocalAssets(root,self.profile);self.profile.setUrlRequestInterceptor(self.interceptor)
        self.dashboard_page=DashboardPage(self.profile,self,root);self.setPage(self.dashboard_page)
        self.profile.setParent(self.dashboard_page)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,False)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,False)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled,False)
        self.channel=QWebChannel(self.page());self.bridge=StudioBridge(window)
        self.channel.registerObject('studio',self.bridge);self.page().setWebChannel(self.channel)
        self.timer=QTimer(self);self.timer.setInterval(200);self.timer.timeout.connect(self.bridge.sync)
        self.loaded=False
        self.loadFinished.connect(self.finished)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.load(QUrl.fromLocalFile(str(root/'index.html')))

    def finished(self,ok):
        self.loaded=ok
        if ok: self.bridge.sync(True)
        else: self.bridge.window.status('Unable to load the dashboard. Start with --native-ui to use the compatibility interface.')

    def showEvent(self,event):
        super().showEvent(event);self.timer.start();self.bridge.sync(True)
        self.page().runJavaScript("document.documentElement?.classList.remove('window-hidden')")

    def hideEvent(self,event):
        self.timer.stop();self.page().runJavaScript("document.documentElement?.classList.add('window-hidden')");super().hideEvent(event)


def install_dashboard(window):
    previous=window.takeCentralWidget();previous.setParent(window);previous.hide()
    window.native_dashboard=previous
    window.web_dashboard=WebDashboard(window);window.setCentralWidget(window.web_dashboard)
