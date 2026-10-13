"""Monochrome studio shell. Application behavior remains in Window."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QApplication, QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QComboBox, QStackedWidget, QSlider, QPlainTextEdit, QTableWidget, QHeaderView,
    QAbstractItemView, QScrollArea, QGraphicsOpacityEffect, QProgressBar, QLineEdit, QDialog, QSpinBox)
from .motion import MotionButton
from .studio_widgets import Switch, PreviewCanvas, Pipeline, Readout, StatusLabel, ConnectionBadge, LanguagePicker
from .languages import language_name, language_badge, overlay_font
from .ocr_profiles import resolve_ocr_language, profiles_for
from .storage import resource
import webbrowser

STYLE = '''
QWidget { background: #101010; color: #ededed; font-family: "Segoe UI", "Sarabun"; font-size: 13px; }
QFrame#sidebar { background: #090909; border-right: 1px solid #2a2a2a; }
QFrame#topbar { background: #111111; border: 1px solid #303030; border-radius: 8px; }
QSpinBox { background: #0e0e0e; border: 1px solid #424242; border-radius: 3px; padding: 8px; min-width: 85px; }
QFrame#panel { background: #151515; border: 1px solid #333333; border-radius: 5px; }
QFrame#monitor { background: #0a0a0a; border: 1px solid #414141; border-radius: 5px; }
QFrame#paper { background: #e8e8e3; border: 0; border-radius: 4px; }
QFrame#paper QLabel { color: #151515; background: transparent; }
QFrame#paper QLabel#muted { color: #4d4d4d; }
QLabel { background: transparent; }
QLabel#muted { color: #969696; }
QLabel#eyebrow { color: #969696; font-family: "Consolas"; font-size: 11px; letter-spacing: 1px; }
QLabel#title { font-size: 34px; font-weight: 600; letter-spacing: -1px; }
QLabel#section { font-size: 19px; font-weight: 600; }
QLabel#display { font-size: 33px; font-weight: 700; letter-spacing: -1px; }
QLabel#brand { font-size: 39px; font-weight: 700; letter-spacing: -3px; }
QLabel#number { font-family: "Consolas"; font-size: 24px; color: #e5e5e5; }
QLabel#badge { background: #252525; border: 1px solid #404040; border-radius: 3px; padding: 5px 8px; font-family: "Consolas"; font-size: 10px; }
QPushButton { background: #212121; border: 1px solid #454545; border-radius: 4px; padding: 9px 13px; font-weight: 500; min-height: 18px; }
QPushButton:hover { border-color: #999999; }
QPushButton:pressed { background: #454545; }
QPushButton:focus { border: 1px solid #eeeeee; }
QPushButton:disabled { color: #626262; background: #171717; border-color: #303030; }
QPushButton#primary { background: #efefeb; color: #101010; border-color: #efefeb; font-weight: 600; }
QPushButton#primary:pressed { background: #c5c5c1; }
QPushButton#primary:disabled { background: #414141; color: #939393; border-color: #414141; }
QPushButton#nav { background: transparent; border: 1px solid transparent; text-align: left; color: #919191; padding: 13px 12px; }
QPushButton#nav:checked { background: #ecece7; color: #0e0e0e; border-color: #ecece7; }
QPushButton#quiet { background: transparent; border-color: transparent; color: #afafaf; padding: 7px 8px; }
QPushButton#quiet:hover { border-color: #555555; color: white; }
QPushButton#segment { background: #171717; color: #898989; border-color: #333333; padding: 5px 12px; font-size: 11px; }
QPushButton#segment:checked { background: #e7e7e3; color: #151515; border-color: #e7e7e3; }
QComboBox { background: #101010; border: 1px solid #424242; border-radius: 3px; padding: 8px 11px; min-height: 20px; }
QComboBox:focus, QComboBox:hover { border-color: #929292; }
QComboBox:disabled { color: #666666; border-color: #303030; }
QComboBox QAbstractItemView { background: #202020; border: 1px solid #666666; selection-background-color: #eeeeea; selection-color: #111111; padding: 6px; }
QComboBox::drop-down { border: none; width: 24px; }
QSlider::groove:horizontal { height: 3px; background: #454545; }
QSlider::sub-page:horizontal { background: #dddddd; }
QSlider::handle:horizontal { background: #efefeb; width: 11px; margin: -5px 0; border-radius: 2px; }
QPlainTextEdit, QLineEdit { background: #0e0e0e; color: #ededed; border: 1px solid #3d3d3d; border-radius: 3px; padding: 10px; selection-background-color: #eeeeea; selection-color: #111111; }
QPlainTextEdit:focus, QLineEdit:focus { border-color: #aaaaaa; }
QPlainTextEdit#readout { background: transparent; border: 0; padding: 0; }
QTableWidget { background: #121212; border: 1px solid #333333; gridline-color: #2d2d2d; selection-background-color: #333333; selection-color: white; }
QTableWidget::item { padding: 12px; border-bottom: 1px solid #292929; }
QHeaderView::section { background: #1d1d1d; color: #949494; font-family: "Consolas"; font-size: 10px; padding: 12px; border: 0; border-bottom: 1px solid #3c3c3c; }
QScrollArea { background: transparent; border: 0; }
QScrollBar:vertical { background: #141414; width: 6px; margin: 0; }
QScrollBar::handle:vertical { background: #555555; min-height: 24px; border-radius: 2px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 6px; background: #141414; }
QScrollBar::handle:horizontal { background: #555555; }
QProgressBar { background: #292929; border: 0; max-height: 2px; }
QProgressBar::chunk { background: #e9e9e5; }
QToolTip { background: #eeeeea; color: #101010; border: 0; padding: 8px; }
'''


def text(value, kind=None):
    w = QLabel(value)
    w.setWordWrap(True)
    if kind:
        w.setObjectName(kind)
    return w


def action(value, callback, kind=None):
    w = MotionButton(value)
    if kind:
        w.setObjectName(kind)
    w.setCursor(Qt.CursorShape.PointingHandCursor)
    w.clicked.connect(callback)
    return w


def panel(kind='panel', margins=20):
    w=QFrame()
    w.setObjectName(kind)
    v=QVBoxLayout(w)
    v.setContentsMargins(margins,margins,margins,margins)
    v.setSpacing(12)
    return w,v


def rule():
    w=QFrame()
    w.setFixedHeight(1)
    w.setStyleSheet('background: #333333; border: 0;')
    return w


class StudioUI:
    def build_ui(self):
        self.language_badges=[]
        root=QWidget()
        self.setCentralWidget(root)
        outer=QHBoxLayout(root)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(0)
        sidebar=QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(178)
        nav=QVBoxLayout(sidebar)
        nav.setContentsMargins(18,26,18,20)
        nav.setSpacing(8)
        brand=QLabel()
        brand.setPixmap(QPixmap(str(resource('assets/branding/rv-white-on-black.png'))).scaled(58,58,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        brand.setAccessibleName('RV Translation Studio logo')
        nav.addWidget(brand)
        nav.addWidget(text('RV TRANSLATION\nSTUDIO','eyebrow'))
        nav.addSpacing(32)
        nav.addWidget(text('WORKSPACE','eyebrow'))
        self.pages=QStackedWidget()
        self.nav_buttons=[]
        for i,name in enumerate(('01    Studio','02    Library','03    Connection','04    Settings')):
            b=action(name,lambda checked=False,index=i:self.navigate(index),'nav')
            b.setCheckable(True)
            b.setFixedHeight(46)
            nav.addWidget(b)
            self.nav_buttons.append(b)
        nav.addStretch()
        nav.addWidget(rule())
        nav.addSpacing(12)
        nav.addWidget(text('GLOBAL SHORTCUTS','eyebrow'))
        for key,caption in (('F1','Translate screen'),('F2','Clear overlay')):
            row=QHBoxLayout()
            tag=text(key,'badge'); tag.setFixedWidth(33)
            row.addWidget(tag)
            row.addWidget(text(caption,'muted'),1)
            nav.addLayout(row)
        nav.addSpacing(14)
        help_button=action('Workflow && Shortcuts',self.show_help,'quiet')
        help_button.setStyleSheet('font-size: 11px; padding: 8px 0; text-align: left;')
        nav.addWidget(help_button)
        nav.addSpacing(16)
        nav.addWidget(text('DESKTOP EDITION\nv2.6.0  /  WINDOWS','eyebrow'))
        outer.addWidget(sidebar)
        content=QVBoxLayout()
        content.setContentsMargins(26,22,26,15)
        content.setSpacing(14)
        topbar=QFrame(); topbar.setObjectName('topbar')
        top=QHBoxLayout(topbar); top.setContentsMargins(18,8,12,8)
        identity=QVBoxLayout(); identity.setSpacing(3)
        identity.addWidget(text('RV TRANSLATION STUDIO','section'))
        self.breadcrumb=text('WORKSPACE  /  STUDIO','eyebrow')
        self.breadcrumb.setWordWrap(False)
        identity.addWidget(self.breadcrumb)
        top.addLayout(identity,1)
        self.connection=ConnectionBadge()
        top.addWidget(self.connection)
        top.addSpacing(10)
        top.addWidget(action('Manage ↗',lambda:self.navigate(2),'quiet'))
        content.addWidget(topbar)
        self.activity=QProgressBar()
        self.activity.setRange(0,1); self.activity.setValue(0)
        self.activity.setTextVisible(False); self.activity.setFixedHeight(2)
        content.addWidget(self.activity)
        content.addWidget(self.pages,1)
        foot=QHBoxLayout()
        foot.addWidget(text('●','muted'))
        self.message=StatusLabel('Ready · Connect ChatGPT to begin')
        self.message.setMinimumWidth(0)
        self.message.setFixedHeight(24)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        foot.addWidget(self.message,1)
        self.footer_mode=text('EN → TH  /  LOCAL OCR','eyebrow')
        self.footer_mode.setWordWrap(False)
        foot.addWidget(self.footer_mode)
        content.addLayout(foot)
        outer.addLayout(content,1)
        self.build_translate()
        self.build_history()
        self.build_account()
        self.build_settings()
        self.language_changed()
        self.navigate(0)

    def page(self,title,subtitle,number):
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page=QWidget()
        scroll.setWidget(page)
        layout=QVBoxLayout(page)
        layout.setContentsMargins(0,0,8,0)
        layout.setSpacing(18)
        heading=QWidget()
        heading.setFixedHeight(94)
        row=QHBoxLayout(heading)
        row.setContentsMargins(0,0,0,0)
        col=QVBoxLayout(); col.setSpacing(5)
        col.addWidget(text(number,'eyebrow'))
        col.addWidget(text(title,'title'))
        col.addWidget(text(subtitle,'muted'))
        row.addLayout(col,1)
        pair=text('EN  →  TH','badge'); pair.setWordWrap(False)
        self.language_badges.append(pair)
        pair.setFixedHeight(42)
        pair.setStyleSheet('font-family: Consolas; font-size: 16px; padding: 10px 14px; border: 1px solid #454545; border-radius: 5px;')
        row.addWidget(pair,0,Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(heading)
        self.pages.addWidget(scroll)
        effect=QGraphicsOpacityEffect(scroll)
        scroll.setGraphicsEffect(effect); effect.setOpacity(1.)
        return layout

    def build_translate(self):
        layout=self.page('Stay inside the story.','Translate in place. Keep the scene, the context, and the feeling.','01  /  TRANSLATION STUDIO')
        route,r=panel(margins=14); r.setSpacing(8)
        row=QHBoxLayout(); row.setSpacing(12)
        source=QVBoxLayout(); source.setSpacing(4); source.addWidget(text('SOURCE LANGUAGE','eyebrow'))
        self.source_language=LanguagePicker(self.settings.get('source_language','en'),auto=True)
        source.addWidget(self.source_language); row.addLayout(source,1)
        self.swap_languages=action('⇄',self.swap_language_pair,'quiet')
        self.swap_languages.setFixedWidth(46); self.swap_languages.setToolTip('Swap source and target languages')
        row.addWidget(self.swap_languages)
        target=QVBoxLayout(); target.setSpacing(4); target.addWidget(text('TRANSLATE INTO','eyebrow'))
        self.target_language=LanguagePicker(self.settings.get('target_language','th'))
        target.addWidget(self.target_language); row.addLayout(target,1); r.addLayout(row)
        note=QHBoxLayout(); self.ocr_language_note=text('Loading installed OCR languages…','muted')
        note.addWidget(self.ocr_language_note,1)
        note.addWidget(action('Language packs ↗',self.open_language_settings,'quiet')); r.addLayout(note)
        layout.addWidget(route)
        for picker in (self.source_language,self.target_language):
            picker.currentIndexChanged.connect(self.language_changed)
            picker.lineEdit().editingFinished.connect(self.language_changed)
        body=QHBoxLayout(); body.setSpacing(18)
        left=QVBoxLayout(); left.setSpacing(14)
        monitor,m=panel('monitor',0)
        m.setSpacing(0)
        monitor_top=QHBoxLayout(); monitor_top.setContentsMargins(16,9,16,9)
        monitor_top.addWidget(text('OVERLAY MONITOR','eyebrow'),1)
        self.original_tab=action('Original',lambda:self.set_preview(False),'segment')
        self.translated_tab=action('Translated',lambda:self.set_preview(True),'segment')
        for b in (self.original_tab,self.translated_tab):
            b.setCheckable(True); b.setFixedHeight(28)
            monitor_top.addWidget(b)
        self.translated_tab.setChecked(True)
        m.addLayout(monitor_top)
        self.signal_canvas=PreviewCanvas()
        m.addWidget(self.signal_canvas,1)
        self.preview_caption=text('ILLUSTRATIVE PREVIEW  /  Your capture appears here','eyebrow')
        self.preview_caption.setContentsMargins(16,10,16,6)
        m.addWidget(self.preview_caption)
        self.pipeline=Pipeline(); m.addWidget(self.pipeline)
        left.addWidget(monitor,1)
        output,o=panel(margins=16)
        row=QHBoxLayout()
        row.addWidget(text('LATEST DIALOGUE','eyebrow'),1)
        self.copy_latest=action('Copy ↗',self.copy_latest_translation,'quiet')
        self.copy_latest.setEnabled(bool(self.history))
        row.addWidget(self.copy_latest)
        row.addWidget(action('Open library ↗',lambda:self.navigate(1),'quiet'))
        o.setSpacing(8)
        o.addLayout(row)
        self.latest_source=Readout('Your source dialogue will appear here.',30)
        self.latest_source.setStyleSheet('color: #999999; font-size: 12px;')
        self.latest=Readout('Ready for your next chapter.',52)
        self.latest.setStyleSheet('font-family: "Playpen Sans Thai"; font-size: 17px;')
        o.addWidget(self.latest_source); o.addWidget(rule()); o.addWidget(self.latest)
        left.addWidget(output)
        strip=QHBoxLayout(); strip.setSpacing(18)
        self.stats=text('—','number')
        self.session_count=text('0','number')
        self.cache_count=text('0','number')
        for name,value in (('LAST CAPTURE',self.stats),('SESSION PASSAGES',self.session_count),('CACHE HITS',self.cache_count)):
            col=QVBoxLayout(); col.setSpacing(2)
            col.addWidget(text(name,'eyebrow')); col.addWidget(value)
            strip.addLayout(col,1)
        left.addLayout(strip)
        self.metric_note=text('No captures in this session.','muted')
        left.addWidget(self.metric_note)
        body.addLayout(left,1)
        controls,s=panel(margins=18)
        controls.setFixedWidth(334)
        s.setSpacing(6)
        heading=QHBoxLayout()
        heading.addWidget(text('Capture setup','section'),1)
        heading.addWidget(text('02','eyebrow')); s.addLayout(heading)
        s.addWidget(rule())
        self.screen=QComboBox()
        for i,screen in enumerate(QApplication.screens()):
            self.screen.addItem(f'Display {i+1} · {screen.geometry().width()} × {screen.geometry().height()}',i)
        self.screen.setCurrentIndex(min(max(0,self.settings.get('screen',0)),self.screen.count()-1))
        self.screen.currentIndexChanged.connect(self.reset_region)
        self.mode=QComboBox(); self.mode.addItems(['Full screen','Subtitle area (bottom)','Custom region'])
        self.mode.setCurrentIndex(self.settings.get('mode',0))
        self.mode.currentIndexChanged.connect(self.capture_mode_changed)
        for name,widget in (('DISPLAY',self.screen),('CAPTURE AREA',self.mode)):
            s.addWidget(text(name,'eyebrow')); s.addWidget(widget)
        self.region_button=action('Select region on screen ↗',self.pick_region,'quiet')
        self.region_button.setFixedHeight(30)
        s.addWidget(self.region_button)
        self.region_info=text('Full display selected','muted'); s.addWidget(self.region_info)
        s.addWidget(rule())
        s.addWidget(text('TRANSLATION MODEL','eyebrow'))
        self.models=QComboBox(); self.models.addItem('Connect ChatGPT to load models','')
        self.models.setMinimumWidth(0)
        self.models.currentIndexChanged.connect(self.model_changed)
        s.addWidget(self.models)
        self.model_language_hint=text('Account models · English → Thai','muted'); s.addWidget(self.model_language_hint)
        s.addWidget(rule())
        row=QHBoxLayout()
        row.addWidget(text('TEXT SCALE','eyebrow'),1)
        self.scale_value=text('100%','eyebrow'); row.addWidget(self.scale_value)
        reset=action('Reset',lambda:self.font_slider.setValue(20),'quiet'); row.addWidget(reset)
        reset.setFixedHeight(24)
        s.addLayout(row)
        self.font_slider=QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(12,36); self.font_slider.setValue(self.settings.get('font_size',20))
        self.font_slider.valueChanged.connect(self.scale_changed)
        s.addWidget(self.font_slider)
        self.opacity_slider=QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(30,100); self.opacity_slider.setValue(self.settings.get('opacity',90))
        self.opacity_slider.hide()
        self.smart_grouping=self.toggle_row(s,'Smart dialogue','Join wrapped sentences before translation.',self.settings.get('smart_grouping',True))
        self.hide_capture=self.toggle_row(s,'Stay in game','Hide this dashboard before capturing.',self.settings.get('hide_capture',True))
        self.smart_grouping.toggled.connect(self.save_settings)
        self.hide_capture.toggled.connect(self.save_settings)
        s.addWidget(rule())
        row=QHBoxLayout()
        row.addWidget(text('BACKGROUND BLEND','eyebrow'),1)
        row.addWidget(text('ALWAYS ON','badge')); s.addLayout(row)
        self.match_colors=self.toggle_row(s,'Match source colors','Sample the original text color.',self.settings.get('match_colors',True))
        self.match_colors.setToolTip('Uses the dominant text color of each source passage. Switch off for white overlay text.')
        self.match_colors.toggled.connect(self.save_settings)
        s.addStretch()
        self.readiness=text('Connect your account to get started.','muted'); s.addWidget(self.readiness)
        self.capture_button=action('Connect ChatGPT  ↗',self.capture,'primary')
        self.capture_button.setFixedHeight(50); s.addWidget(self.capture_button)
        self.clear_button=action('Clear overlay  /  F2',self.clear_overlay)
        self.clear_button.setFixedHeight(40); s.addWidget(self.clear_button)
        body.addWidget(controls)
        layout.addLayout(body,1)
        self.session_passages=0; self.session_cache_hits=0
        self.scale_changed(self.font_slider.value())
        self.capture_mode_changed()
        if self.history:
            self.latest_source.setText(self.history[-1]['source'])
            self.latest.setText(self.history[-1]['translation'])

    def toggle_row(self,layout,title,description,checked):
        row=QHBoxLayout(); row.setSpacing(14)
        col=QVBoxLayout(); col.setSpacing(3)
        col.addWidget(text(title))
        detail=text(description,'muted'); detail.setStyleSheet('font-size: 11px;')
        col.addWidget(detail)
        switch=Switch(title); switch.setChecked(checked)
        row.addLayout(col,1); row.addWidget(switch)
        layout.addLayout(row)
        return switch

    def build_history(self):
        layout=self.page('Every line, remembered.','Find, revisit, and export the dialogue you have translated.','02  /  DIALOGUE LIBRARY')
        tools=QHBoxLayout()
        self.history_search=QLineEdit(); self.history_search.setPlaceholderText('Search dialogue in any language…')
        self.history_search.setClearButtonEnabled(True)
        self.history_search.textChanged.connect(self.filter_history)
        tools.addWidget(self.history_search,1)
        self.history_count=text('0 passages','eyebrow'); tools.addWidget(self.history_count)
        tools.addWidget(action('Export JSON ↗',self.export_history))
        layout.addLayout(tools)
        self.table=QTableWidget(0,3)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['CAPTURED','SOURCE TEXT','TRANSLATION','LANGUAGES'])
        self.table.setColumnWidth(3,116)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        for col in (1,2):
            self.table.horizontalHeader().setSectionResizeMode(col,QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide(); self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(270)
        self.table.itemSelectionChanged.connect(self.select_history)
        self.history_empty=text('NO DIALOGUE YET\nCapture your first conversation with F1.','muted')
        self.history_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_empty.setMinimumHeight(180)
        self.history_area=QStackedWidget()
        self.history_area.addWidget(self.table)
        self.history_area.addWidget(self.history_empty)
        self.history_area.setMinimumHeight(270)
        layout.addWidget(self.history_area,1)
        self.history_detail=Readout('Select a passage to read the full source and translation.',116)
        self.history_detail.setStyleSheet('border: 1px solid #333333; padding: 12px;')
        layout.addWidget(self.history_detail)
        bottom=QHBoxLayout()
        self.copy_history_button=action('Copy translation ↗',self.copy_history_translation)
        self.copy_history_button.setEnabled(False); bottom.addWidget(self.copy_history_button)
        bottom.addStretch()
        self.undo_history_button=action('Undo clear',self.undo_clear_history)
        self.undo_history_button.hide(); bottom.addWidget(self.undo_history_button)
        bottom.addWidget(action('Clear history',self.clear_history,'quiet'))
        layout.addLayout(bottom)

    def build_account(self):
        layout=self.page('Your account. Your control.','Connect through your browser. Your game remains on your desktop.','03  /  CONNECTION')
        row=QHBoxLayout(); row.setSpacing(18)
        connection,p=panel(margins=18)
        p.setSpacing(10)
        self.provider_selector=QComboBox();self.provider_selector.addItem('ChatGPT','openai');self.provider_selector.addItem('Argos Local (Offline)','argos')
        self.provider_selector.setCurrentIndex(self.provider_selector.findData(self.provider))
        self.provider_selector.currentIndexChanged.connect(lambda:self.switch_provider(self.provider_selector.currentData()))
        p.addWidget(self.provider_selector)
        p.addWidget(text('CHATGPT ACCOUNT','eyebrow'))
        self.account_text=text('Not connected','section'); p.addWidget(self.account_text)
        self.plan_text=text('Sign in and authorize plan usage to begin.','muted'); p.addWidget(self.plan_text)
        self.accounts=QComboBox(); self.accounts.setPlaceholderText('No saved accounts')
        self.accounts.currentIndexChanged.connect(self.switch_account); p.addWidget(self.accounts)
        actions=QHBoxLayout()
        self.login_button=action('Continue with ChatGPT ↗',self.login,'primary')
        self.add_account=action('Add account',lambda:self.login(new=True))
        self.cancel_login=action('Cancel',lambda:self.auth.cancel.set())
        self.cancel_login.hide()
        for widget in (self.login_button,self.add_account,self.cancel_login): actions.addWidget(widget)
        p.addLayout(actions); p.addWidget(rule())
        actions=QHBoxLayout()
        self.refresh_button=action('Reload models',self.load_models)
        self.logout_button=action('Sign out',self.logout,'quiet')
        actions.addWidget(self.refresh_button)
        self.manage_usage_button=action('Manage usage ↗',self.manage_usage,'quiet');actions.addWidget(self.manage_usage_button)
        actions.addStretch(); actions.addWidget(self.logout_button)
        p.addLayout(actions)
        p.addWidget(text('Models and plan access are supplied by your signed-in account.','muted'))
        row.addWidget(connection,3)
        privacy,v=panel('paper',22); privacy.setMinimumWidth(250)
        v.addWidget(text('ON YOUR DESKTOP','eyebrow'))
        v.addWidget(text('The scene stays.\nThe words change.','display'))
        v.addStretch()
        v.addWidget(text('01  /  Windows-encrypted credentials\n02  /  Local screenshot recognition\n03  /  Only recognized text is sent','muted'))
        row.addWidget(privacy,2); layout.addLayout(row)
        test,t=panel()
        head=QHBoxLayout(); head.addWidget(text('TRANSLATION WORKBENCH','eyebrow'),1)
        self.sample_pair=text('EN → TH','badge'); head.addWidget(self.sample_pair); t.addLayout(head)
        columns=QHBoxLayout(); columns.setSpacing(18)
        source=QVBoxLayout(); source.addWidget(text('SOURCE TEXT','eyebrow'))
        source.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.test_input=QPlainTextEdit(); self.test_input.setPlaceholderText('Enter dialogue in any language to test your connection…')
        self.test_input.setFixedHeight(120)
        source.addWidget(self.test_input)
        translated=QVBoxLayout(); translated.addWidget(text('TRANSLATED TEXT','eyebrow'))
        translated.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.test_output=Readout('Your translation will appear here.',120)
        self.test_output.setStyleSheet('border: 1px solid #3d3d3d; padding: 10px; font-family: "Playpen Sans Thai"; font-size: 16px;')
        translated.addWidget(self.test_output)
        columns.addLayout(source,1); columns.addLayout(translated,1); t.addLayout(columns)
        actions=QHBoxLayout()
        self.test_button=action('Translate sample ↗',self.test_translation,'primary')
        actions.addWidget(self.test_button)
        actions.addWidget(action('Clear sample',self.clear_sample,'quiet'))
        actions.addStretch()
        self.copy_sample_button=action('Copy result ↗',self.copy_sample,'quiet'); self.copy_sample_button.setEnabled(False)
        actions.addWidget(self.copy_sample_button); t.addLayout(actions)
        layout.addWidget(test)
        layout.addStretch()

    def build_settings(self):
        layout=self.page('Tune every capture.','A faster workflow, with the controls to make it yours. Changes save automatically.','04  /  ADVANCED SETTINGS')
        summary,s=panel('paper',20)
        row=QHBoxLayout(); row.addWidget(text('PERFORMANCE LAB','eyebrow'),1)
        row.addWidget(action('Fast capture preset',self.fast_preset,'primary')); s.addLayout(row)
        self.performance_detail=text('No capture measured yet. OCR and translation timings appear here after F1.','muted')
        s.addWidget(self.performance_detail)
        layout.addWidget(summary)
        columns=QHBoxLayout(); columns.setSpacing(18)
        capture,c=panel(); capture.setMinimumWidth(340)
        c.setSpacing(10)
        c.addWidget(text('01  /  CAPTURE & RECOGNITION','eyebrow'))
        c.addWidget(text('Read less. Respond sooner.','section'))
        c.addWidget(text('Choose Windows OCR for installed languages, or bundled RapidOCR for multilingual reading without Windows packs.','muted'))
        c.addWidget(text('LOCAL OCR LANGUAGE','eyebrow'))
        self.ocr_language=QComboBox(); self.ocr_language.addItem('Follow source language','auto')
        self.ocr_language.currentIndexChanged.connect(self.ocr_profile_changed)
        c.addWidget(self.ocr_language)
        ocr_actions=QHBoxLayout()
        ocr_actions.addWidget(action('Reload languages',self.reload_ocr_languages,'quiet'))
        ocr_actions.addWidget(action('Windows language packs ↗',self.open_language_settings,'quiet'))
        c.addLayout(ocr_actions)
        c.addWidget(text('RapidOCR includes 11 reading profiles. Follow source selects a matching model. Auto source uses English, Chinese and Japanese; choose a profile for other scripts. Windows OCR uses installed Windows packs.','muted'))
        self.advanced={}
        def choice(parent,key,label,choices,default):
            parent.addWidget(text(label,'muted'))
            control=QComboBox()
            for caption,value in choices: control.addItem(caption,value)
            index=control.findData(self.settings.get(key,default)); control.setCurrentIndex(max(0,index))
            parent.addWidget(control); self.advanced[key]=control
            control.currentIndexChanged.connect(self.save_advanced)
            return control
        def number(parent,key,label,low,high,default,suffix=''):
            row=QHBoxLayout(); row.addWidget(text(label,'muted'),1)
            control=QSpinBox(); control.setRange(low,high); control.setSuffix(suffix)
            control.setValue(self.settings.get(key,default)); row.addWidget(control)
            parent.addLayout(row); self.advanced[key]=control
            control.valueChanged.connect(self.save_advanced)
        choice(c,'ocr_backend','Recognition engine',[('Windows native · fast','native'),('RapidOCR · bundled multilingual','rapid'),('Windows via PowerShell · compatibility','legacy')],'native')
        choice(c,'capture_limit','Maximum image dimension',[('1280 px · speed',1280),('1920 px · balanced',1920),('2500 px · small text',2500)],2500)
        number(c,'capture_delay','Capture settle delay',80,1000,150,' ms')
        number(c,'subtitle_percent','Subtitle zone · bottom of display',15,70,40,' %')
        number(c,'max_passages','Maximum passages per request',1,100,100)
        c.addWidget(text('Lower image size can miss small lettering. Increase the settle delay if the app appears in captures.','muted'))
        c.addStretch(); columns.addWidget(capture,1)
        render,r=panel(); render.setMinimumWidth(340)
        r.setSpacing(10)
        r.addWidget(text('02  /  TRANSLATION & OVERLAY','eyebrow'))
        r.addWidget(text('Keep the original character.','section'))
        r.addWidget(text('Source colors and sentence grouping remain available in Studio. These controls tune the background restoration.','muted'))
        number(r,'inpaint_radius','Background repair radius',1,7,3,' px')
        number(r,'mask_padding','Text removal padding',0,5,1,' px')
        number(r,'request_timeout','Translation network timeout',30,180,90,' s')
        self.cache_toggle=self.toggle_row(r,'Reuse translations','Repeat dialogue appears from the local cache.',self.settings.get('cache_enabled',True))
        self.cache_toggle.toggled.connect(self.save_advanced)
        self.click_clear_toggle=self.toggle_row(r,'Click overlay to clear','F2 always remains available.',self.settings.get('click_clear',True))
        self.click_clear_toggle.toggled.connect(self.save_advanced)
        self.motion_toggle=self.toggle_row(r,'Interface motion','Connection heartbeat, transitions and hover effects.',self.settings.get('motion',True))
        self.motion_toggle.toggled.connect(self.set_motion)
        r.addStretch(); columns.addWidget(render,1)
        layout.addLayout(columns)
        bottom,b=panel(margins=18)
        row=QHBoxLayout(); row.addWidget(text('LOCAL STORAGE','eyebrow'),1)
        self.cache_size=text('','muted'); row.addWidget(self.cache_size)
        row.addWidget(action('Clear translation cache',self.clear_translation_cache))
        row.addWidget(action('Reset advanced settings',self.reset_advanced,'quiet'))
        b.addLayout(row)
        b.addWidget(text('Cache reset keeps your accounts and dialogue library. Fast capture uses 1920 px and a 120 ms settle delay with your selected OCR engine.','muted'))
        layout.addWidget(bottom); layout.addStretch()
        self.apply_advanced()

    def apply_advanced(self):
        self.translator.cache_enabled=self.settings.get('cache_enabled',True)
        self.translator.timeout=self.settings.get('request_timeout',90)
        self.overlay.click_clear=self.settings.get('click_clear',True)
        if hasattr(self,'cache_size'):
            self.cache_size.setText(f'{len(self.translator.cache)} cached passages')

    def language_pair(self):
        source=self.source_language.language()
        target=self.target_language.language()
        if target=='auto': raise ValueError('Choose a target language; Auto detect is for the source only.')
        return source,target

    def language_changed(self):
        if not hasattr(self,'sample_pair') or getattr(self,'_changing_languages',False): return
        try: source,target=self.language_pair()
        except ValueError as exc:
            self.status(str(exc)); return
        changed=(source,target)!=(self.settings.get('source_language','en'),self.settings.get('target_language','th'))
        self.settings.update(source_language=source,target_language=target)
        if changed and hasattr(self,'hotkey_bridge') and not self.busy:
            self.clear_overlay()
        pair=f'{language_badge(source)}  →  {language_badge(target)}'
        for badge in self.language_badges: badge.setText(pair)
        self.sample_pair.setText(pair)
        self.footer_mode.setText(pair+'  /  LOCAL OCR')
        self.model_language_hint.setText(f'Account models · {language_name(source)} → {language_name(target)}')
        self.test_input.setPlaceholderText(f'Enter {language_name(source)} dialogue…' if source!='auto' else 'Paste dialogue in any language…')
        self.signal_canvas.language_pair=pair
        self.signal_canvas.target_language=target
        self.latest.setStyleSheet(f'font-family: "{overlay_font(target)}"; font-size: 17px;')
        self.test_output.setStyleSheet(f'border: 1px solid #3d3d3d; padding: 10px; font-family: "{overlay_font(target)}"; font-size: 16px;')
        self.signal_canvas.update()
        self.refresh_ocr_note()
        self.save_settings()
        if hasattr(self,'test_button'):self.update_controls()

    def refresh_ocr_note(self):
        backend=self.settings.get('ocr_backend','native')
        if not getattr(self,'ocr_languages_loaded',False) and backend!='rapid':
            self.ocr_language_note.setText('Loading installed OCR languages…'); return
        source=self.settings.get('source_language','en')
        try:
            tag=resolve_ocr_language(source,self.ocr_languages,self.settings.get('ocr_language','auto'),backend)
            name=dict(profiles_for(backend,self.ocr_languages))[tag]
            self.ocr_language_note.setText(f'{"RapidOCR" if backend=="rapid" else "Windows OCR"}: {name}'+(' · Choose a reading profile for other scripts.' if source=='auto' else ''))
            self.ocr_language_note.setToolTip('This profile reads screenshots locally. Change the OCR profile in Settings for another script.')
        except RuntimeError as exc:
            self.ocr_language_note.setText(f'{language_name(source)} OCR unavailable here · text samples still work')
            self.ocr_language_note.setToolTip(str(exc))

    def refresh_ocr_profiles(self):
        backend=self.settings.get('ocr_backend','native')
        key='ocr_profile_rapid' if backend=='rapid' else 'ocr_profile_windows'
        preferred=self.settings.get(key,self.settings.get('ocr_language','auto'))
        self.ocr_language.blockSignals(True)
        self.ocr_language.clear(); self.ocr_language.addItem('Follow source language','auto')
        for tag,name in profiles_for(backend,getattr(self,'ocr_languages',[])):
            self.ocr_language.addItem(name if backend=='rapid' else f'{name} · {tag}',tag)
        self.ocr_language.setCurrentIndex(max(0,self.ocr_language.findData(preferred)))
        self.settings['ocr_language']=self.ocr_language.currentData()
        self.ocr_language.blockSignals(False)
        self.refresh_ocr_note(); self.save_settings()

    def swap_language_pair(self):
        if self.busy or self.auth_busy: return
        try: source,target=self.language_pair()
        except ValueError as exc: self.status(str(exc)); return
        if source=='auto':
            self.status('Choose a source language before swapping'); return
        self._changing_languages=True
        self.source_language.select_language(target); self.target_language.select_language(source)
        self._changing_languages=False
        self.language_changed()

    def ocr_profile_changed(self):
        self.settings['ocr_language']=self.ocr_language.currentData() or 'auto'
        key='ocr_profile_rapid' if self.settings.get('ocr_backend','native')=='rapid' else 'ocr_profile_windows'
        self.settings[key]=self.settings['ocr_language']
        self.refresh_ocr_note(); self.save_settings()

    def open_language_settings(self):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl('ms-settings:regionlanguage'))

    def save_advanced(self):
        previous_backend=self.settings.get('ocr_backend','native')
        for key,control in self.advanced.items():
            self.settings[key]=control.value() if isinstance(control,QSpinBox) else control.currentData()
        if previous_backend!=self.settings.get('ocr_backend','native'):
            previous_key='ocr_profile_rapid' if previous_backend=='rapid' else 'ocr_profile_windows'
            self.settings[previous_key]=self.settings.get('ocr_language','auto')
        if hasattr(self,'cache_toggle'):
            self.settings['cache_enabled']=self.cache_toggle.isChecked()
            self.settings['click_clear']=self.click_clear_toggle.isChecked()
        self.apply_advanced()
        if previous_backend!=self.settings.get('ocr_backend','native'):
            self.refresh_ocr_profiles()
        self.capture_mode_changed()

    def set_advanced_values(self,values):
        for key,value in values.items():
            if key in self.advanced:
                control=self.advanced[key]
                control.blockSignals(True)
                control.setValue(value) if isinstance(control,QSpinBox) else control.setCurrentIndex(control.findData(value))
                control.blockSignals(False)
        self.save_advanced()

    def fast_preset(self):
        if self.busy:
            self.status('Wait for the current translation before applying a preset'); return
        self.set_advanced_values(dict(capture_limit=1920,capture_delay=120))
        self.cache_toggle.setChecked(True)
        self.status('Fast capture preset applied · Select a dialogue region in Studio for best speed')

    def reset_advanced(self):
        if self.busy:
            self.status('Wait for the current translation before resetting settings'); return
        self.set_advanced_values(dict(ocr_backend='native',capture_limit=2500,capture_delay=150,subtitle_percent=40,max_passages=100,inpaint_radius=3,mask_padding=1,request_timeout=90))
        self.cache_toggle.setChecked(True); self.click_clear_toggle.setChecked(True); self.motion_toggle.setChecked(True)
        self.status('Advanced settings restored')

    def clear_translation_cache(self):
        if self.busy:
            self.status('Wait for the current translation before clearing the cache'); return
        from .storage import write_json
        self.translator.cache.clear(); write_json('translations.json',{})
        self.apply_advanced(); self.status('Translation cache cleared')

    def show_help(self):
        dialog=QDialog(self); dialog.setWindowTitle('Workflow & Shortcuts'); dialog.resize(540,420)
        layout=QVBoxLayout(dialog); layout.setContentsMargins(28,28,28,28); layout.setSpacing(18)
        layout.addWidget(text('Back to the game.','title'))
        layout.addWidget(text('01  Connect ChatGPT and select an available model.\n\n02  Choose source and target languages. Screenshot OCR needs a matching installed Windows OCR pack.\n\n03  Choose a display and dialogue region. Return to your game and release F1.\n\n04  Click the overlay or press F2 to clear it before the scene changes.','muted'))
        layout.addWidget(text('Use windowed or borderless mode if an exclusive-fullscreen game hides the overlay. The monitor shows an illustrative scene until your first capture.','muted'))
        layout.addStretch(); layout.addWidget(action('Got it',dialog.accept,'primary'))
        dialog.exec()

    def set_preview(self, translated):
        self.signal_canvas.translated=translated
        self.original_tab.setChecked(not translated)
        self.translated_tab.setChecked(translated)
        self.signal_canvas.update()

    def capture_mode_changed(self):
        if not hasattr(self,'region_info'):
            return
        mode=self.mode.currentIndex()
        self.region_info.setText('Full display selected' if mode==0 else
                                f'Bottom {self.settings.get("subtitle_percent",40)}% of the display' if mode==1 else
                                f'{self.region.width()} × {self.region.height()} · custom region' if self.region else
                                'Select a region before translating')
        self.save_settings()

    def scale_changed(self,value):
        self.scale_value.setText(f'{round(value/20*100)}%')
        self.signal_canvas.text_scale=value
        self.signal_canvas.update()
        self.save_settings()

    def model_changed(self):
        self.save_settings()
        if hasattr(self,'test_button'):
            self.update_controls()

    def set_motion(self,enabled):
        self.settings['motion']=enabled
        self.signal_canvas.set_motion(enabled)
        self.connection.set_motion(enabled)
        for switch in self.findChildren(Switch):
            switch.animation.setDuration(160 if enabled else 0)
        for widget in self.findChildren(MotionButton):
            widget.motion.setDuration(180 if enabled else 0)
        self.save_settings()

    def set_phase(self,phase):
        self.signal_canvas.phase=phase
        self.pipeline.set_phase(phase)
        self.signal_canvas.update()

    def show_error(self,message):
        self.set_phase('error')
        self.status(message)

    def copy_latest_translation(self):
        if self.history:
            QApplication.clipboard().setText(self.history[-1]['translation'])
            self.status('Latest translation copied')

    def filter_history(self):
        if not hasattr(self,'history_search'):
            return
        query=self.history_search.text().casefold().strip()
        visible=0
        for row in range(self.table.rowCount()):
            matches=not query or any(query in self.table.item(row,col).text().casefold() for col in (1,2))
            self.table.setRowHidden(row,not matches)
            visible+=int(matches)
        self.history_count.setText(f'{visible} / {self.table.rowCount()} passages')
        self.history_area.setCurrentIndex(0 if visible else 1)
        self.history_empty.setText('NO MATCHING DIALOGUE\nTry another search.' if self.history and query else
                                   'NO DIALOGUE YET\nCapture your first conversation with F1.')
        self.select_history()

    def selected_history_rows(self):
        return sorted({index.row() for index in self.table.selectedIndexes()
                       if not self.table.isRowHidden(index.row())})

    def select_history(self):
        if not hasattr(self,'copy_history_button'):
            return
        rows=self.selected_history_rows()
        self.copy_history_button.setEnabled(bool(rows))
        if rows:
            row=rows[0]
            self.history_detail.setText(self.table.item(row,1).text()+'\n\n'+self.table.item(row,2).text())
        else:
            self.history_detail.setText('Select a passage to read the full source and translation.')

    def copy_history_translation(self):
        rows=self.selected_history_rows()
        if rows:
            QApplication.clipboard().setText('\n\n'.join(self.table.item(row,2).text() for row in rows))
            self.status(f'Copied {len(rows)} translation(s)')

    def undo_clear_history(self):
        if getattr(self,'history_backup',None):
            self.history=(self.history_backup+self.history)[-500:]
            self.history_backup=None
            from .storage import write_json
            write_json('history.json',self.history)
            self.populate_history()
            self.undo_history_button.hide()
            self.copy_latest.setEnabled(True)
            self.status('History restored')

    def clear_sample(self):
        self.test_input.clear()
        self.test_output.setText('Your translation will appear here.')
        self.copy_sample_button.setEnabled(False)

    def copy_sample(self):
        if self.copy_sample_button.isEnabled():
            QApplication.clipboard().setText(self.test_output.text())
            self.status('Sample translation copied')

    def manage_usage(self):
        if self.provider=='argos':self.status('Argos Local runs offline and has no API charges.');return
        webbrowser.open('https://chatgpt.com/settings/usage')
