import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import tempfile
import time
from PyQt6.QtCore import Qt, QThread, QTimer, QRect, QRectF, pyqtSignal, QLockFile, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPen, QIcon
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QFileDialog, QTableWidgetItem, QMessageBox, QInputDialog, QLineEdit
from .auth import ChatGPTAuth
from .gemini import GeminiAuth
from .local_translation import LocalTranslator
from .storage import resource, data_dir, read_json, write_json
from .translation import Translator, recognize, installed_ocr_languages
from .languages import language_badge
from .ocr_profiles import resolve_ocr_language
from .blend import image_to_bgr, make_patch, make_patches
from .glyphs import refine_rapid_regions
from .colors import sample_text_color
from .hotkeys import GlobalHotkeys
from .paragraphs import group_dialogue
from .studio import StudioUI, STYLE
from .text_layout import paint_translation

USER32 = ctypes.WinDLL('user32', use_last_error=True)
USER32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
USER32.RegisterHotKey.restype = wintypes.BOOL
USER32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
USER32.UnregisterHotKey.restype = wintypes.BOOL

class Job(QThread):
    result = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.result.emit(self.fn())
        except Exception as exc:
            # Exception details from network/auth implementations are sanitized there.
            if isinstance(exc, (RuntimeError, ValueError)):
                self.error.emit(str(exc))
            else:
                self.error.emit('Unable to complete this action (' + type(exc).__name__ + '). Please try again.')


class Overlay(QWidget):
    cleared = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.items = []
        self.font_size = 20
        self.opacity = 90
        self.click_clear = True

    def mousePressEvent(self, event):
        if self.click_clear and event.button() == Qt.MouseButton.LeftButton:
            self.clear()
            self.cleared.emit()

    def clear(self):
        self.items = []
        self.hide()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap
        for item in self.items:
            if 'patch' in item:p.drawImage(item['patch_rect'],item['patch'])
        for item in self.items:
            if 'patch' in item:
                paint_translation(p, item, self.font_size)
                continue
            p.setFont(QFont('Sarabun', self.font_size))
            width = min(max(item['w'], 180), max(180, self.width() - 16))
            x = max(8, min(item['x'], self.width() - width - 8))
            bounds = p.boundingRect(QRectF(x + 10, 0, width - 20, 1000), flags, item['translation'])
            height = max(item['h'] + 12, bounds.height() + 16)
            y = max(8, min(item['y'] - 4, self.height() - height - 8))
            rect = QRectF(x, y, width, height)
            p.setPen(QPen(QColor(255, 255, 255, 55)))
            p.setBrush(QColor(9, 10, 11, round(self.opacity * 2.55)))
            p.drawRoundedRect(rect, 6, 6)
            p.setPen(QColor('#ffffff'))
            p.drawText(rect.adjusted(10, 6, -10, -6), flags, item['translation'])


class RegionPicker(QWidget):
    selected = pyqtSignal(QRect)
    cancelled = pyqtSignal()

    def __init__(self, screen):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setGeometry(screen.geometry())
        self.image = screen.grabWindow(0)
        self.origin = None
        self.selection = QRect()
        self._finished = False
        self.setCursor(Qt.CursorShape.CrossCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self.image)
        p.fillRect(self.rect(), QColor(0, 0, 0, 140))
        if not self.selection.isNull():
            ratio=self.image.devicePixelRatio()
            selected_image=self.image.copy(QRect(round(self.selection.x()*ratio),round(self.selection.y()*ratio),round(self.selection.width()*ratio),round(self.selection.height()*ratio)))
            p.drawPixmap(self.selection,selected_image)
            p.setPen(QPen(Qt.GlobalColor.white, 2))
            p.drawRect(self.selection)
            p.setFont(QFont('Segoe UI',11))
            size=f'{self.selection.width()} × {self.selection.height()}'
            tag=QRect(self.selection.x(),max(52,self.selection.y()-29),130,24)
            p.fillRect(tag,QColor('#111111'));p.drawText(tag,Qt.AlignmentFlag.AlignCenter,size)
        p.setPen(Qt.GlobalColor.white)
        p.setFont(QFont('Sarabun', 18))
        p.drawText(30, 45, 'Drag to select a capture area  ·  Esc to cancel')

    def mousePressEvent(self, event):
        self.origin = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.selection = QRect(self.origin, event.position().toPoint()).normalized().intersected(self.rect())
            self.update()

    def mouseReleaseEvent(self, event):
        if self.origin is not None:
            self.selection=QRect(self.origin,event.position().toPoint()).normalized().intersected(self.rect())
        if self.selection.width() > 30 and self.selection.height() > 20:
            self._finished=True
            self.selected.emit(self.selection)
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self,event):
        if not self._finished:
            self._finished=True
            self.cancelled.emit()
        event.accept()


class Window(StudioUI, QMainWindow):
    phase_changed = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.setWindowTitle('RV TRANSLATION STUDIO — 2.9.3')
        self.resize(1440, 960)
        self.setMinimumSize(980, 680)
        self.setWindowIcon(QIcon(str(resource('assets/app.ico'))))
        self.settings = read_json('settings.json', {})
        self.provider=self.settings.get('provider','openai')
        if self.provider not in ('openai','gemini','argos'):self.provider='openai'
        self.chatgpt_auth=ChatGPTAuth();self.gemini_auth=GeminiAuth()
        self.local_auth=LocalTranslator()
        self.auth={'openai':self.chatgpt_auth,'gemini':self.gemini_auth,'argos':self.local_auth}[self.provider]
        self.translator = Translator()
        self.jobs = set()
        self.busy = False
        self.auth_busy = False
        self.capture_hidden = False
        self.region_selecting = False
        self.ocr_languages=[]
        self.ocr_languages_loaded=False
        self.ocr_languages_loading=False
        saved_region = self.settings.get('region')
        self.region = QRect(*saved_region) if (isinstance(saved_region, list) and len(saved_region) == 4
                                               and all(isinstance(n, int) for n in saved_region)) else None
        self.generation = 0
        self.overlay = Overlay()
        self.overlay.cleared.connect(self.clear_overlay)
        self.history = read_json('history.json', [])[-500:]
        self.build_ui()
        self.phase_changed.connect(self.set_phase)
        self.set_motion(self.settings.get('motion', True))
        self.refresh_accounts()
        self.populate_history()
        self.hotkey_ids = []
        self.hotkey_bridge = GlobalHotkeys(self)
        self.hotkey_bridge.translate.connect(self.capture, Qt.ConnectionType.QueuedConnection)
        self.hotkey_bridge.clear.connect(self.clear_overlay, Qt.ConnectionType.QueuedConnection)
        try:
            self.hotkey_bridge.start()
            self.status('F1 works in game · Click or press F2 to clear')
        except Exception:
            for ident, key in ((4101, 0x70), (4102, 0x71)):
                if USER32.RegisterHotKey(int(self.winId()), ident, 0x4000, key):
                    self.hotkey_ids.append(ident)
            if len(self.hotkey_ids) != 2:
                self.status('F1/F2 unavailable · Close the previous app version and reopen')
        if self.is_connected:
            QTimer.singleShot(250, self.load_models)
        QTimer.singleShot(0,self.reload_ocr_languages)

    def reload_ocr_languages(self):
        if self.ocr_languages_loading or self.busy: return
        if self.settings.get('ocr_backend','native')=='rapid': self.refresh_ocr_profiles()
        self.ocr_languages_loading=True
        def done(languages):
            self.ocr_languages=languages
            self.ocr_languages_loaded=True
            self.refresh_ocr_profiles()
        def finish():
            self.ocr_languages_loading=False
            if not self.ocr_languages_loaded and self.settings.get('ocr_backend','native')!='rapid':
                self.ocr_language_note.setText('OCR languages unavailable · reload in Settings')
        self.run_job(installed_ocr_languages,done,finish)

    @property
    def is_connected(self):
        if self.provider=='argos':return self.local_auth.connected
        return self.gemini_auth.connected if self.provider=='gemini' else bool(self.auth.account and self.auth.account.get('access_token'))

    @property
    def provider_label(self):return {'gemini':'Gemini','argos':'Argos Local','openai':'ChatGPT'}[self.provider]

    @property
    def local_route_error(self):
        if self.provider!='argos':return ''
        try:self.local_auth.validate_pair(self.settings.get('source_language','en'),self.settings.get('target_language','th'))
        except RuntimeError as exc:return str(exc)
        return ''

    def switch_provider(self,provider):
        if provider not in ('openai','gemini','argos'):raise ValueError('Choose ChatGPT, Gemini or Argos Local.')
        if self.busy or self.auth_busy:return
        if provider==self.provider:return
        current=self.models.currentData()
        if current:self.settings['model_'+self.provider]=current
        if self.provider=='argos':self.local_auth.stop()
        self.clear_overlay();self.provider=provider;self.settings['provider']=provider
        self.auth={'openai':self.chatgpt_auth,'gemini':self.gemini_auth,'argos':self.local_auth}[provider]
        self.provider_selector.blockSignals(True);self.provider_selector.setCurrentIndex(self.provider_selector.findData(provider));self.provider_selector.blockSignals(False)
        self.models.clear();self.models.addItem('Connect '+self.provider_label+' to load models','')
        self.refresh_accounts();self.save_settings()
        if self.is_connected:self.load_models()
        else:self.status('Connect '+self.provider_label+' in Connection to begin')

    def translate_passages(self,texts,model,source,target,screen=False):
        if self.provider=='argos':
            self.local_auth.validate_pair(source,target)
            return self.translator.translate(texts,None,model,source=source,target=target,provider='argos',complete=self.local_auth.complete_screen if screen else self.local_auth.complete,allow_partial=screen)
        if self.provider=='gemini':
            return self.translator.translate(texts,None,model,source=source,target=target,provider='gemini',complete=self.gemini_auth.complete)
        return self.translator.translate(texts,self.auth.access_token,model,source=source,target=target)

    def switch_gemini_mode(self,mode):
        if mode not in ('api','enterprise'):raise ValueError('Choose Gemini API key or organization sign-in.')
        if self.busy or self.auth_busy:return
        self.gemini_auth.cli.stop();self.settings['gemini_auth_mode']=mode;self.save_settings();self.gemini_auth.reload()
        if hasattr(self,'gemini_mode_selector'):
            self.gemini_mode_selector.blockSignals(True);self.gemini_mode_selector.setCurrentIndex(self.gemini_mode_selector.findData(mode));self.gemini_mode_selector.blockSignals(False)
        if self.provider=='gemini':
            self.clear_overlay();self.models.clear();self.models.addItem('Connect Gemini to load models','');self.refresh_accounts()
            if self.is_connected:self.load_models()
            else:self.status('Connect an API key from Google AI Studio' if mode=='api' else 'Organization sign-in requires Code Assist Standard/Enterprise. Personal CLI access has been retired.')

    def navigate(self, index):
        if hasattr(self, 'page_animation'):
            self.page_animation.stop()
            self.pages.currentWidget().graphicsEffect().setOpacity(1.)
            self.page_animation.deleteLater()
        self.pages.setCurrentIndex(index)
        effect = self.pages.currentWidget().graphicsEffect()
        self.page_animation = QPropertyAnimation(effect, b'opacity', self)
        self.page_animation.setDuration(260 if self.settings.get('motion', True) else 0)
        self.page_animation.setStartValue(.2)
        self.page_animation.setEndValue(1.)
        self.page_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.page_animation.start()
        for i, b in enumerate(self.nav_buttons):
            b.setChecked(i == index)
        self.breadcrumb.setText('WORKSPACE  /  ' + ('STUDIO', 'LIBRARY', 'CONNECTION', 'SETTINGS')[index])

    def status(self, text):
        self.message.setText(text)
        self.message.setToolTip(text)

    def run_job(self, fn, done, finished=None):
        job = Job(fn)
        self.jobs.add(job)
        job.result.connect(done)
        job.error.connect(self.show_error)
        def cleanup():
            self.jobs.discard(job)
            if finished:
                finished()
            job.deleteLater()
        job.finished.connect(cleanup)
        job.start()

    def update_controls(self):
        self.connection.busy = self.auth_busy
        self.connection.sync()
        self.signal_canvas.set_busy(self.busy or self.auth_busy)
        if self.auth_busy:
            self.set_phase('connect')
        elif self.signal_canvas.phase == 'connect':
            self.set_phase('idle')
        self.activity.setRange(0, 0 if self.busy or self.auth_busy else 1)
        if not self.busy and not self.auth_busy:
            self.activity.setValue(0)
        ready = bool(self.is_connected and self.models.currentData() and not self.local_route_error)
        self.capture_button.setText('Translating…' if self.busy else 'Loading connection…' if self.auth_busy else
                                    'Translate screen  /  F1' if ready else 'Set up '+self.provider_label+'  ↗')
        self.capture_button.setEnabled(not self.busy and not self.auth_busy)
        self.readiness.setText(self.local_route_error or ('Ready. Return to your game and release F1.' if ready else
                               'Loading your account models…' if self.auth_busy else
                               'Connect '+self.provider_label+' and choose a model to begin.'))
        self.test_button.setEnabled(ready and not self.busy and not self.auth_busy)
        for w in (self.login_button, self.add_account, self.accounts, self.logout_button, self.refresh_button):
            w.setEnabled(not self.busy and not self.auth_busy)
        self.provider_selector.setEnabled(not self.busy and not self.auth_busy)
        self.gemini_mode_selector.setEnabled(not self.busy and not self.auth_busy)
        for w in (self.screen, self.mode, self.models, self.smart_grouping, self.hide_capture, self.match_colors, self.region_button):
            w.setEnabled(not self.busy and not self.auth_busy)
        for w in (self.source_language,self.target_language,self.swap_languages,self.ocr_language):
            w.setEnabled(not self.busy and not self.auth_busy)
        if hasattr(self,'advanced'):
            for w in (*self.advanced.values(),self.cache_toggle,self.click_clear_toggle):
                w.setEnabled(not self.busy)

    def refresh_accounts(self):
        self.accounts.blockSignals(True)
        self.accounts.clear()
        for i, a in enumerate(self.auth.credentials['accounts']):
            self.accounts.addItem(f'{i+1:02}  ·  {a["email"]}  ·  {a["client_id"][-8:]}', a['client_id'])
        index = self.accounts.findData(self.auth.credentials.get('active'))
        self.accounts.setCurrentIndex(index)
        self.accounts.blockSignals(False)
        account = self.auth.account
        connected = self.is_connected
        self.connection.setText('●  Argos Local · Offline' if self.provider=='argos' and connected else '●  '+self.provider_label+' connected' if connected else '○  Not connected')
        self.account_text.setText(account['email'] if account else 'Not connected')
        gemini_api=self.gemini_auth.mode=='api'
        self.plan_text.setText(('Gemini API · Usage and billing belong to your Google AI Studio project.' if gemini_api else 'Organization access through the official Gemini CLI · Licensed accounts only.') if self.provider=='gemini' else 'ChatGPT plan usage enabled' if connected and 'chatgpt.tokens.use.direct' in account.get('scopes', []) else 'Sign in and authorize plan usage to begin.')
        self.login_button.setText(('Replace API key' if connected else 'Connect API key') if self.provider=='gemini' and gemini_api else 'Continue with organization ↗' if self.provider=='gemini' else 'Continue with ChatGPT ↗')
        self.logout_button.setText('Disconnect Studio' if self.provider=='gemini' else 'Sign out')
        self.add_account.setVisible(self.provider=='openai')
        self.gemini_mode_selector.setVisible(self.provider=='gemini')
        self.gemini_mode_selector.setEnabled(not self.busy and not self.auth_busy)
        if self.provider=='argos':
            self.plan_text.setText(f'{len(self.local_auth.catalog["languages"])} built-in languages · CPU · No account, API key or credits')
        for widget in (self.login_button,self.logout_button,self.accounts,self.manage_usage_button):widget.setVisible(self.provider!='argos')
        self.update_controls()

    def switch_account(self):
        if not self.accounts.currentData() or self.busy or self.auth_busy:
            return
        self.auth.select(self.accounts.currentData())
        self.clear_overlay()
        self.models.clear()
        self.refresh_accounts()
        if self.is_connected:
            self.load_models()

    def login(self, checked=False, new=False):
        if self.auth_busy or self.busy:
            return
        if self.provider=='argos':self.load_models();return
        existing = None if new else self.auth.account
        api_key=None
        if self.provider=='gemini' and self.gemini_auth.mode=='api':
            api_key,accepted=QInputDialog.getText(self,'Connect Gemini API','Paste your Gemini API key from Google AI Studio.\nThe key is encrypted with Windows and never included in logs.',QLineEdit.EchoMode.Password)
            if not accepted or not api_key.strip():return
        self.auth_busy = True
        self.cancel_login.setVisible(api_key is None)
        self.update_controls()
        self.status('Verifying Gemini API key and text models…' if api_key is not None else 'Waiting for browser sign-in · Three-minute timeout')
        def done(account):
            self.refresh_accounts()
            self.status('Account verified · Loading available models')
        def finish():
            self.auth_busy = False
            self.cancel_login.hide()
            self.refresh_accounts()
            if self.is_connected:
                self.load_models()
        self.run_job((lambda:self.gemini_auth.connect_api_key(api_key)) if api_key is not None else (lambda: self.auth.sign_in(existing)), done, finish)

    def load_models(self):
        if self.auth_busy or self.busy:
            return
        self.auth_busy = True
        preferred_model = self.settings.get('model_'+self.provider,self.settings.get('model') if self.provider=='openai' else None)
        self.models.blockSignals(True)
        self.models.clear()
        self.models.addItem('Loading models…', '')
        self.update_controls()
        def done(models):
            self.models.clear()
            for slug, name in models:
                self.models.addItem(name, slug)
            preferred = self.models.findData(preferred_model)
            if preferred >= 0:
                self.models.setCurrentIndex(preferred)
            elif self.provider=='gemini' and self.gemini_auth.mode=='api':
                for i,(slug,name) in enumerate(models):
                    if 'flash' in slug and 'preview' not in slug:self.models.setCurrentIndex(i);break
            self.status('Ready · Open your game and press F1' if models else 'No models are available for this account')
        def finish():
            self.auth_busy = False
            if not self.models.currentData():
                self.models.clear()
                self.models.addItem('Models unavailable · Retry from Account', '')
            self.models.blockSignals(False)
            self.save_settings()
            self.refresh_accounts()
        self.run_job(self.auth.models, done, finish)

    def logout(self):
        if self.provider=='argos':self.status('Argos Local is built in and requires no account. Choose another provider to switch.');return
        if self.auth_busy or self.busy:
            return
        self.auth_busy = True
        self.clear_overlay()
        self.update_controls()
        def done(revoked):
            self.models.clear()
            self.models.addItem('Connect '+self.provider_label+' to load models', '')
            self.status(('API key removed from Studio. Manage or revoke the key in Google AI Studio.' if self.gemini_auth.mode=='api' else 'Disconnected from Studio. Organization credentials remain managed by Gemini CLI; use Manage Google access to revoke.') if self.provider=='gemini' else 'Signed out' if revoked else 'Signed out locally. Online revocation could not be confirmed; disconnect in ChatGPT Settings.')
        def finish():
            self.auth_busy = False
            self.refresh_accounts()
        self.run_job(self.auth.sign_out, done, finish)

    def save_settings(self):
        if not hasattr(self, 'hide_capture'):
            return
        self.settings.update(mode=self.mode.currentIndex(), font_size=self.font_slider.value(),
                             screen=self.screen.currentIndex(),
                             region=[self.region.x(), self.region.y(), self.region.width(), self.region.height()] if self.region else None,
                             opacity=self.opacity_slider.value(), hide_capture=self.hide_capture.isChecked(),
                             smart_grouping=self.smart_grouping.isChecked(),
                             match_colors=self.match_colors.isChecked() if hasattr(self,'match_colors') else self.settings.get('match_colors',True),
                             model=self.models.currentData() or self.settings.get('model'))
        if self.models.currentData():
            self.settings['model_'+self.provider]=self.models.currentData()
        write_json('settings.json',self.settings)
        self.overlay.font_size = self.font_slider.value()
        self.overlay.opacity = self.opacity_slider.value()
        self.overlay.update()
        self.refresh_capture_preview()

    def refresh_capture_preview(self):
        capture=getattr(self,'last_capture_render',None)
        if not capture:return
        image,factor,area,lines=capture
        preview=image.copy();preview.setDevicePixelRatio(1.)
        painter=QPainter(preview);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(factor,factor);painter.translate(-area.x(),-area.y())
        for line in lines:painter.drawImage(line['patch_rect'],line['patch'])
        for line in lines:paint_translation(painter,line,self.font_slider.value())
        painter.end();self.signal_canvas.set_capture(image,preview)

    def reset_region(self):
        self.region = None
        if self.mode.currentIndex() == 2:
            self.mode.setCurrentIndex(0)
        self.capture_mode_changed()

    def pick_region(self,checked=False,translate_after=False):
        if self.busy or self.auth_busy or self.region_selecting:
            return
        self.region_selecting=True
        self.picker_translate_after=translate_after
        self.picker_window_state=self.windowState()
        self.clear_overlay()
        self.status('Drag to select and translate · Esc to cancel' if translate_after else 'Drag to save a capture region · Esc to cancel')
        self.hide()
        QTimer.singleShot(250, self.show_picker)

    def show_picker(self):
        if not self.region_selecting:return
        self.picker = RegionPicker(QApplication.screens()[self.screen.currentIndex()])
        def selected(rect):
            auto_translate=self.picker_translate_after
            self.region_selecting=False
            self.region = rect
            self.mode.setCurrentIndex(2)
            self.capture_mode_changed()
            if auto_translate:
                self.capture_hidden=True
                self.status('Region selected · Translating…')
                QTimer.singleShot(0,lambda:self.capture(use_saved_region=True))
            else:
                self.setWindowState(self.picker_window_state);self.show()
                self.status(f'Region saved · {rect.width()} × {rect.height()} · F1 selects and translates a new area')
        def cancelled():
            self.region_selecting=False
            self.setWindowState(self.picker_window_state);self.show()
            self.status('Region selection cancelled · No translation sent')
        self.picker.selected.connect(selected)
        self.picker.cancelled.connect(cancelled)
        self.picker.show()
        self.picker.activateWindow()

    def clear_overlay(self):
        self.generation += 1
        self.overlay.clear()
        self.set_phase('idle')
        self.status('Overlay cleared')

    def capture(self,checked=False,use_saved_region=False):
        if self.busy or self.auth_busy or self.region_selecting:
            self.status('Processing · Wait for completion, then press F1 again')
            return
        if not self.models.currentData() or not self.auth.account:
            self.navigate(2)
            self.status('Connect '+self.provider_label+' and load a model to begin')
            return
        try:
            source,target=self.language_pair()
            if self.provider=='argos':self.local_auth.validate_pair(source,target)
            self.language_changed()
            if not self.ocr_languages_loaded and self.settings.get('ocr_backend','native')!='rapid':
                self.status('Loading local OCR languages · Retry shortly'); return
            self.capture_ocr_language=resolve_ocr_language(source,self.ocr_languages,self.settings.get('ocr_language','auto'),self.settings.get('ocr_backend','native'))
            self.settings.update(source_language=source,target_language=target)
        except (RuntimeError,ValueError) as exc:
            self.status(str(exc)); return
        if self.mode.currentIndex() == 2 and (not use_saved_region or self.region is None):
            self.pick_region(translate_after=True)
            return
        self.save_settings()
        self.busy = True
        self.capture_started = time.monotonic()
        self.set_phase('capture')
        self.generation += 1
        generation = self.generation
        self.overlay.clear()
        self.update_controls()
        self.status('Capturing screen · Recognizing and translating dialogue…')
        if self.hide_capture.isChecked():
            self.capture_hidden = True
            self.hide()
        QTimer.singleShot(self.settings.get('capture_delay',150), lambda: self.capture_now(generation))

    def capture_now(self, generation):
        try:
            screen = QApplication.screens()[self.screen.currentIndex()]
            geo = screen.geometry()
            pix = screen.grabWindow(0)
            image = pix.toImage()
            ratio = pix.devicePixelRatio()
            area = QRect(0, 0, geo.width(), geo.height())
            if self.mode.currentIndex() == 1:
                fraction = self.settings.get('subtitle_percent',40)/100
                y = round(geo.height()*(1-fraction))
                area = QRect(0,y,geo.width(),geo.height()-y)
            elif self.mode.currentIndex() == 2:
                area = self.region.intersected(area)
                if area.width() < 30 or area.height() < 20:
                    raise RuntimeError('Saved region is outside this display. Select a new capture region.')
            image = image.copy(QRect(round(area.x()*ratio), round(area.y()*ratio), round(area.width()*ratio), round(area.height()*ratio)))
            # Windows OCR supports at most 2600 px per dimension.
            scale = min(1., self.settings.get('capture_limit',2500) / max(image.width(), image.height()))
            if scale < 1:
                image = image.scaled(round(image.width()*scale), round(image.height()*scale), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            handle, name = tempfile.mkstemp(suffix='.png', prefix='ruevalley-')
            import os
            os.close(handle)
            path = Path(name)
            if not image.save(str(path)):
                path.unlink(missing_ok=True)
                raise RuntimeError('Unable to save the OCR capture')
            model = self.models.currentData()
            smart_grouping = self.smart_grouping.isChecked()
            match_colors = self.match_colors.isChecked()
            start = getattr(self,'capture_started',time.monotonic())
            options = dict(self.settings)
            def process():
                timings = {'capture':time.monotonic()-start}
                stage = time.monotonic()
                self.phase_changed.emit('recognize')
                try:
                    backend=options.get('ocr_backend','native')
                    ocr_language=self.capture_ocr_language
                    lines = recognize(path) if backend=='native' and ocr_language=='en-US' else recognize(path,backend=backend,language=ocr_language)
                finally:
                    path.unlink(missing_ok=True)
                timings['ocr'] = time.monotonic()-stage
                if not lines:
                    return [], 0, time.monotonic() - start, timings
                stage = time.monotonic()
                frame = image_to_bgr(image)
                if backend=='rapid':refine_rapid_regions(frame,lines)
                patches = {}
                def patch_for(line):
                    key = (line['x'],line['y'],line['w'],line['h'],line['text'])
                    if key not in patches:
                        patches[key] = make_patch(frame,line,options.get('inpaint_radius',3),options.get('mask_padding',1))
                    return patches[key]
                if match_colors:
                    for line in lines:
                        patch, patch_rect = patch_for(line)
                        line.update(sample_text_color(frame, line, patch, patch_rect))
                if smart_grouping:
                    lines = group_dialogue(lines,language=options.get('source_language','en'))
                lines = lines[:options.get('max_passages',100)]
                timings['prepare'] = time.monotonic()-stage
                self.phase_changed.emit('translate')
                stage = time.monotonic()
                source,target=options.get('source_language','en'),options.get('target_language','th')
                values, hits = self.translate_passages([l['text'] for l in lines],model,source,target,screen=True)
                skipped=sum(value is None for value in values)
                timings['skipped_passages']=skipped
                # Failed passages stay visible in the game; never erase/repaint
                # them or record/cache source text as a successful translation.
                pairs=[(line,value) for line,value in zip(lines,values) if value is not None]
                lines=[line for line,_ in pairs];values=[value for _,value in pairs]
                timings['translation'] = time.monotonic()-stage
                self.phase_changed.emit('blend')
                stage = time.monotonic()
                restored=make_patches(frame,lines,options.get('inpaint_radius',3),options.get('mask_padding',1))
                for line, value,(patch,patch_rect) in zip(lines, values,restored):
                    line.update(source_language=source,target_language=target)
                    factor = ratio*scale
                    line['line_height'] = line.get('line_height', line['h']) / factor
                    line['patch'] = patch
                    line['patch_rect'] = QRectF(patch_rect.x()/factor+area.x(), patch_rect.y()/factor+area.y(), patch_rect.width()/factor, patch_rect.height()/factor)
                    line.update(translation=value, x=line['x']/(ratio*scale)+area.x(), y=line['y']/(ratio*scale)+area.y(),
                                w=line['w']/(ratio*scale), h=line['h']/(ratio*scale))
                    line['text_bounds']=(0,0,geo.width(),geo.height())
                timings['blend'] = time.monotonic()-stage
                return lines, hits, time.monotonic() - start, timings
            def done(result):
                lines, hits, elapsed, timings = result
                self.last_timings = timings
                skipped=timings.pop('skipped_passages',0)
                self.performance_detail.setText('  /  '.join(f'{name.upper()} {value*1000:,.0f} ms' for name,value in timings.items()) + f'  /  TOTAL {elapsed:.2f} s')
                self.apply_advanced()
                if generation == self.generation and lines:
                    self.overlay.setGeometry(geo)
                    self.overlay.items = lines
                    self.overlay.font_size = self.font_slider.value()
                    self.overlay.opacity = self.opacity_slider.value()
                    self.overlay.show()
                    self.overlay.update()
                self.record(lines)
                if lines:
                    self.last_capture_render=(image.copy(),ratio*scale,QRect(area),lines)
                    self.refresh_capture_preview()
                    self.preview_caption.setText('LAST CAPTURE  /  '+language_badge(options.get('source_language','en'))+' → '+language_badge(options.get('target_language','th'))+'  /  LOCAL MEMORY')
                    self.session_passages += len(lines)
                    self.session_cache_hits += hits
                    self.session_count.setText(str(self.session_passages))
                    self.cache_count.setText(str(self.session_cache_hits))
                self.set_phase('complete' if lines else 'idle')
                self.stats.setText(f'{elapsed:.1f}s')
                self.metric_note.setText(f'{len(lines)} passages · cached {hits}'+(f' · {skipped} kept original' if skipped else ''))
                self.status((f'Translated {len(lines)} passages · {skipped} kept original after retry. Try a smaller region or explicit source language.' if skipped else f'Translated {len(lines)} passages · Click or press F2 to clear') if lines or skipped else 'No readable text found. Check the OCR profile or capture area.')
            self.run_job(process, done, self.finish_translation)
        except Exception as exc:
            self.finish_translation()
            self.show_error(str(exc))

    def finish_translation(self):
        self.busy = False
        # Keep the game in front; do not activate the dashboard after capture.
        if self.capture_hidden:
            self.showMinimized()
            self.capture_hidden = False
        self.update_controls()

    def test_translation(self):
        text = self.test_input.toPlainText().strip()
        if not text or self.busy or self.auth_busy:
            return
        if len(text) > 4000:
            self.status('Sample text is limited to 4,000 characters')
            return
        model = self.models.currentData()
        if not model:
            self.status('Load a model first')
            return
        try:
            source,target=self.language_pair()
            if self.provider=='argos':self.local_auth.validate_pair(source,target)
        except (ValueError,RuntimeError) as exc: self.status(str(exc)); return
        self.settings.update(source_language=source,target_language=target)
        self.busy = True
        self.set_phase('translate')
        self.update_controls()
        self.status('Translating your sample through '+self.provider_label+'…')
        def done(result):
            values, hits = result
            self.test_output.setText(values[0])
            self.copy_sample_button.setEnabled(True)
            self.set_phase('complete')
            self.record([{'text': text, 'translation': values[0],'source_language':source,'target_language':target}])
            self.status('Sample translated' + (' · From cache' if hits else ' · '+self.provider_label+' response complete'))
        self.run_job(lambda: self.translate_passages([text],model,source,target), done, self.finish_translation)

    def record(self, lines):
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        for line in lines:
            self.history.append(dict(time=now, source=line['text'], translation=line['translation'],
                                     source_language=line.get('source_language',self.settings.get('source_language','en')),
                                     target_language=line.get('target_language',self.settings.get('target_language','th'))))
        self.history = self.history[-500:]
        write_json('history.json', self.history)
        self.populate_history()
        if lines:
            self.latest.setText(lines[-1]['translation'])
            self.latest_source.setText(lines[-1]['text'])
            self.copy_latest.setEnabled(True)

    def populate_history(self):
        self.table.setRowCount(len(self.history))
        for row, item in enumerate(reversed(self.history)):
            for col, key in enumerate(('time', 'source', 'translation')):
                self.table.setItem(row, col, QTableWidgetItem(item[key]))
            self.table.setItem(row,3,QTableWidgetItem(language_badge(item.get('source_language','en'))+' → '+language_badge(item.get('target_language','th'))))
        self.table.resizeRowsToContents()
        self.filter_history()

    def export_history(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export history', 'RV-translation-history.json', 'JSON (*.json)')
        if path:
            try:
                Path(path).write_text(json.dumps(self.history, ensure_ascii=False, indent=2), encoding='utf-8')
                self.status('History exported')
            except OSError:
                self.status('Unable to write the file. Choose another folder.')

    def clear_history(self):
        if not self.history:
            self.status('There is no history to clear')
            return
        self.history_backup = list(self.history)
        self.history = []
        write_json('history.json', [])
        self.populate_history()
        self.undo_history_button.setVisible(bool(self.history_backup))
        self.copy_latest.setEnabled(False)
        self.status('History cleared · Undo is available · Translation cache retained')

    def nativeEvent(self, event_type, message):
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == 0x0312:
            if msg.wParam == 4101:
                self.capture()
            elif msg.wParam == 4102:
                self.clear_overlay()
            return True, 0
        return False, 0

    def closeEvent(self, event):
        if self.jobs:
            self.auth.cancel.set()
            self.status('Finishing the current task. Please close again once it completes.')
            event.ignore()
            return
        self.save_settings()
        self.hotkey_bridge.stop()
        for ident in self.hotkey_ids:
            USER32.UnregisterHotKey(int(self.winId()), ident)
        self.overlay.close()
        self.gemini_auth.cli.stop()
        self.local_auth.stop()
        event.accept()


def run():
    import sys
    if '--native-ui' not in sys.argv:
        from .web_dashboard import install_dashboard
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('RV TRANSLATION STUDIO')
    app.setStyle('Fusion')
    QFontDatabase.addApplicationFont(str(resource('Sarabun-Regular.ttf')))
    QFontDatabase.addApplicationFont(str(resource('PlaypenSansThai-Light.ttf')))
    app.setStyleSheet(STYLE)
    instance_lock = QLockFile(str(data_dir() / 'app.lock'))
    if not instance_lock.tryLock(0):
        QMessageBox.information(None, 'RV TRANSLATION STUDIO', 'The app is already running. Open it from the taskbar.')
        return 0
    try:
        window = Window()
        if '--native-ui' not in sys.argv:
            install_dashboard(window)
    except Exception:
        QMessageBox.critical(None, 'RV TRANSLATION STUDIO', 'Unable to open app data. Check access to %LOCALAPPDATA%/RueValleyTranslator.')
        return 1
    window.show()
    if '--smoke-test' in __import__('sys').argv:
        if hasattr(window,'web_dashboard'):
            from .web_smoke import start_smoke
            start_smoke(window,__import__('os').environ.get('RUEVALLEY_SMOKE_DIR','.'))
            return app.exec()
        def smoke():
            target = Path(__import__('os').environ.get('RUEVALLEY_SMOKE_DIR', '.'))
            target.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(target / 'ui-preview.png'))
            window.navigate(2)
            window.page_animation.stop()
            window.pages.currentWidget().graphicsEffect().setOpacity(1.)
            window.grab().save(str(target / 'account-preview.png'))
            window.navigate(3)
            window.page_animation.stop()
            window.pages.currentWidget().graphicsEffect().setOpacity(1.)
            window.grab().save(str(target / 'settings-preview.png'))
            # Exercise bundled OCR and actual WM_HOTKEY routing without OpenAI calls.
            sample = __import__('PyQt6.QtGui', fromlist=['QImage']).QImage(900, 180, __import__('PyQt6.QtGui', fromlist=['QImage']).QImage.Format.Format_RGB32)
            sample.fill(QColor('white'))
            painter = QPainter(sample)
            painter.setPen(QColor('black'))
            painter.setFont(QFont('Arial', 34))
            painter.drawText(25, 95, 'The valley remembers you.')
            painter.end()
            sample_path = target / 'ocr-test.png'
            sample.save(str(sample_path))
            from .native_ocr import recognize_native
            lines = recognize_native(sample_path.resolve())
            ocr_ok = any('valley' in line['text'].lower() for line in lines)
            window.source_language.select_language('en')
            window.target_language.select_language('ja')
            from .languages import language_catalog
            language_ok = len(language_catalog())>300 and all('JA' in badge.text() for badge in window.language_badges)
            window.navigate(0)
            window.page_animation.stop(); window.pages.currentWidget().graphicsEffect().setOpacity(1.)
            window.grab().save(str(target / 'languages-preview.png'))
            window.target_language.select_language('th')
            hotkey_routed = None
            if not window.auth.account:
                USER32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
                USER32.SendMessageW.restype = wintypes.LPARAM
                window.navigate(0)
                USER32.SendMessageW(int(window.winId()), 0x0312, 4101, 0)
                hotkey_routed = window.pages.currentIndex() == 2
            (target / 'smoke-result.json').write_text(json.dumps({'ok': ocr_ok and language_ok, 'ocr': ocr_ok, 'ocr_backend': 'native', 'languages':len(language_catalog()), 'language_controls':language_ok, 'hotkey_routing': hotkey_routed, 'pages': window.pages.count(), 'screens': window.screen.count(), 'hotkeys': len(window.hotkey_bridge.handles) or len(window.hotkey_ids)}))
            window.close()
        QTimer.singleShot(600, smoke)
    return app.exec()
