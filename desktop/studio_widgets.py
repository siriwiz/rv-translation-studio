"""Painted desktop controls and a local, explicitly labelled overlay monitor."""
import math
import time
from PyQt6.QtCore import Qt, QTimer, QVariantAnimation, QEasingCurve, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen, QFont, QPainterPath, QLinearGradient, QPolygonF
from PyQt6.QtWidgets import QWidget, QCheckBox, QLabel, QPlainTextEdit, QComboBox, QCompleter
from .languages import language_catalog, language_name, resolve_language


class LanguagePicker(QComboBox):
    def __init__(self,selected,auto=False):
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMinimumWidth(0)
        self.setMaxVisibleItems(12)
        if auto: self.addItem('Auto detect','auto')
        for code,name in language_catalog(): self.addItem(f'{name} · {code}',code)
        self.select_language(selected)
        self.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.lineEdit().setPlaceholderText('Search languages or type a language name…')
        self.lineEdit().setMaxLength(80)
        self.setToolTip('Choose a language, search by name/code, or enter a custom language name. Model quality varies by language.')

    def select_language(self,code):
        previous_index=self.currentIndex()
        previous_text=self.currentText()
        index=self.findData(code)
        if index<0:
            self.addItem(language_name(code),code); index=self.count()-1
        self.setCurrentIndex(index)
        self.setEditText(self.itemText(index))
        if index==previous_index and previous_text!=self.itemText(index):
            self.currentIndexChanged.emit(index)

    def language(self):
        if self.currentIndex()>=0 and self.currentText()==self.itemText(self.currentIndex()):
            return self.currentData()
        return resolve_language(self.currentText())


class ConnectionBadge(QWidget):
    """Quiet monochrome heartbeat. Motion follows visibility and user preference."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(224, 40)
        self.connected = False
        self.motion_enabled = True
        self.busy = False
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.update)
        self.setAccessibleName('ChatGPT connection status')

    def setText(self, value):
        self.connected = 'ChatGPT connected' in value
        self.setToolTip('ChatGPT account connected' if self.connected else 'Connect your ChatGPT account')
        self.sync()

    def set_motion(self, enabled):
        self.motion_enabled = enabled
        self.sync()

    def sync(self):
        self.timer.start() if self.isVisible() and self.motion_enabled and (self.connected or self.busy) else self.timer.stop()
        self.update()

    def showEvent(self, event):
        self.sync()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor('#3c3c3c'))
        p.setBrush(QColor('#191919'))
        p.drawRoundedRect(QRectF(.5,.5,self.width()-1,self.height()-1),20,20)
        phase = (math.sin(time.monotonic()*2.8)+1)/2 if self.motion_enabled else 0
        alpha = int(26 + phase*40) if self.connected else 18
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(238,238,232,alpha))
        radius = 7 + phase*2 if self.connected else 7
        p.drawEllipse(QPointF(21,20),radius,radius)
        p.setBrush(QColor('#efefea' if self.connected else '#666666'))
        p.drawEllipse(QPointF(21,20),3,3)
        p.setPen(QColor('#ededed' if self.connected else '#999999'))
        p.setFont(QFont('Segoe UI',10))
        label = 'Connecting…' if self.busy else 'ChatGPT connected' if self.connected else 'ChatGPT disconnected'
        p.drawText(QRectF(37,0,180,40),Qt.AlignmentFlag.AlignVCenter,label)


class Switch(QCheckBox):
    def __init__(self, text=''):
        super().__init__(text)
        self.position = 0.
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(38, 22)
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(160)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.frame)
        self.toggled.connect(self.animate)
        self.setAccessibleName(text)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def frame(self, value):
        self.position = float(value)
        self.update()

    def animate(self, checked):
        self.animation.stop()
        self.animation.setStartValue(self.position)
        self.animation.setEndValue(1. if checked else 0.)
        self.animation.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        enabled = self.isEnabled()
        p.setOpacity(1. if enabled else .4)
        p.setPen(QPen(QColor('#e6e6e6' if self.isChecked() else '#505050'), 1))
        p.setBrush(QColor('#e6e6e6' if self.isChecked() else '#262626'))
        p.drawRoundedRect(QRectF(1, 2, 36, 18), 9, 9)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#111111' if self.isChecked() else '#9b9b9b'))
        p.drawEllipse(QRectF(4 + 16*self.position, 5, 12, 12))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor('white'), 1, Qt.PenStyle.DotLine))
            p.drawRoundedRect(QRectF(0, 0, 37, 21), 10, 10)


class Readout(QPlainTextEdit):
    def __init__(self, text='', height=70):
        super().__init__()
        self.setReadOnly(True)
        self.setPlainText(text)
        self.setFixedHeight(height)
        self.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        self.setObjectName('readout')

    def setText(self, text):
        self.setPlainText(text)

    def text(self):
        return self.toPlainText()


class StatusLabel(QLabel):
    def paintEvent(self, event):
        p = QPainter(self)
        p.setPen(QColor('#a8a8a8'))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width()))


class PreviewCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(330, 260)
        self.busy = False
        self.translated = True
        self.motion_enabled = True
        self.phase = 'idle'
        self.before = self.after = None
        self.text_scale = 20
        self.start = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.update)
        self.setAccessibleName('Overlay monitor: illustrative preview until a screen is captured')

    def set_capture(self, before, after):
        self.before, self.after = before.copy(), after.copy()
        self.setAccessibleName('Overlay monitor: last local screen capture')
        self.update_timer()
        self.update()

    def update_timer(self):
        if self.motion_enabled and self.isVisible() and (self.before is None or self.busy):
            self.timer.start()
        else:
            self.timer.stop()

    def set_busy(self,busy):
        self.busy=busy
        self.update_timer()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_timer()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def set_motion(self, enabled):
        self.motion_enabled = enabled
        self.update_timer()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#090909'))
        t = time.monotonic() - self.start if self.motion_enabled else 0
        image = self.after if self.translated else self.before
        if image is not None:
            size = image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            p.drawImage(QRectF((self.width()-size.width())/2, (self.height()-size.height())/2,
                              size.width(), size.height()), image)
        else:
            # Original vector scene, never presented as a live game capture.
            p.save()
            scale=max(self.width()/800,self.height()/390)
            p.translate((self.width()-800*scale)/2,(self.height()-390*scale)/2)
            p.scale(scale,scale)
            sky = QLinearGradient(0, 0, 0, 390)
            sky.setColorAt(0, QColor('#151515'))
            sky.setColorAt(1, QColor('#3b3b3b'))
            p.fillRect(0, 0, 800, 390, sky)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#707070'))
            p.drawEllipse(QRectF(560, 44, 28, 28))
            for points, color in [([(0, 180),(90,95),(180,135),(300,70),(460,155),(560,100),(700,150),(800,95),(800,390),(0,390)], '#232323'),
                                  ([(0,225),(95,175),(220,204),(350,145),(510,210),(650,165),(800,230),(800,390),(0,390)], '#303030')]:
                p.setBrush(QColor(color))
                p.drawPolygon(QPolygonF([QPointF(x, y) for x,y in points]))
            p.setBrush(QColor('#393939'))
            p.drawPolygon(QPolygonF([QPointF(390,215),QPointF(430,215),QPointF(635,390),QPointF(160,390)]))
            p.setPen(QPen(QColor('#565656'), 1))
            p.drawLine(390,215,160,390)
            p.drawLine(430,215,635,390)
            for i in range(8):
                y = 226 + i*i*2.5
                p.drawLine(QPointF(408, y), QPointF(405, y+3+i*1.4))
            for x,y,s in [(130,217,1.25),(215,210,.8),(535,220,1.1),(615,202,.7)]:
                p.setPen(QPen(QColor('#505050'), 1))
                p.setBrush(QColor('#1d1d1d'))
                p.drawRect(QRectF(x,y-40*s,64*s,40*s))
                p.setBrush(QColor('#111111'))
                p.drawPolygon(QPolygonF([QPointF(x-6*s,y-40*s),QPointF(x+32*s,y-66*s),QPointF(x+70*s,y-40*s)]))
                p.setBrush(QColor('#767676'))
                for wx in (12,42):
                    p.drawRect(QRectF(x+wx*s,y-28*s,9*s,11*s))
                p.setBrush(QColor('#101010'))
                p.drawRect(QRectF(x+27*s,y-20*s,12*s,20*s))
            for x,s in [(58,1.5),(740,1.25),(290,.6),(493,.55)]:
                y=242
                p.setPen(QPen(QColor('#111111'), 3*s))
                p.drawLine(QPointF(x,y),QPointF(x+4,y-130*s))
                for j in range(5):
                    by=y-(j*17+30)*s
                    p.drawLine(QPointF(x+2,by),QPointF(x-22*s,by-22*s))
                    p.drawLine(QPointF(x+2,by-8*s),QPointF(x+26*s,by-29*s))
            p.setPen(QPen(QColor('#656565'), .6))
            for i in range(14):
                x = (i*79+t*7) % 850-25
                y = 70+(i*47)%160
                p.drawLine(QPointF(x,y),QPointF(x+60,y))
            shade=QLinearGradient(0,240,0,390)
            shade.setColorAt(0,QColor(0,0,0,0)); shade.setColorAt(1,QColor(0,0,0,240))
            p.fillRect(0,230,800,160,shade)
            p.setPen(QPen(QColor('#b4b4b4'), 1))
            for x,sgn in [(78,1),(722,-1)]:
                p.drawLine(x,278,x+sgn*18,278); p.drawLine(x,278,x,292)
                p.drawLine(x,349,x+sgn*18,349); p.drawLine(x,349,x,335)
            from .languages import overlay_font
            target=getattr(self,'target_language','th')
            p.setFont(QFont(overlay_font(target) if self.translated else 'Georgia',
                            round(15*self.text_scale/20)))
            p.setPen(QColor('#fafafa'))
            samples={'th':'หุบเขาแห่งนี้ยังจดจำคุณได้','en':'The valley remembers you.',
                     'ja':'この谷はまだあなたを覚えている。','zh-Hans':'山谷依然记得你。','zh-Hant':'山谷依然記得你。',
                     'ko':'이 계곡은 아직 당신을 기억해요.','fr':'La vallée se souvient de vous.',
                     'de':'Das Tal erinnert sich an dich.','es':'El valle te recuerda.',
                     'ar':'الوادي لا يزال يتذكرك.','ru':'Долина помнит тебя.'}
            caption = samples.get(target,'Your translated dialogue appears here.') if self.translated else 'The valley remembers you.'
            p.drawText(QRectF(90,285,620,56), Qt.AlignmentFlag.AlignCenter, caption)
            p.setFont(QFont('Consolas', 8))
            p.setPen(QColor('#a0a0a0'))
            p.drawText(24,30,'R/V  —  OVERLAY STUDY / 001')
            p.drawText(24,370,'ILLUSTRATIVE SCENE  ·  '+getattr(self,'language_pair','EN → TH'))
            p.restore()
        # Real work is indicated by phase, never a fabricated completion percentage.
        if self.busy:
            y = (t*90) % max(1,self.height())
            p.setPen(QPen(QColor(255,255,255,120),1))
            p.drawLine(QPointF(0,y),QPointF(self.width(),y))
            p.fillRect(QRectF(12,12,175,26),QColor('#ededed'))
            p.setFont(QFont('Consolas',8))
            p.setPen(QColor('#111111'))
            p.drawText(QRectF(20,12,160,26),Qt.AlignmentFlag.AlignVCenter,self.phase.upper()+'…')


class Pipeline(QWidget):
    def __init__(self):
        super().__init__()
        self.phase = 'idle'
        self.setFixedHeight(46)

    def set_phase(self, phase):
        self.phase = phase
        self.update()

    def paintEvent(self, event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        stages=('capture','recognize','translate','blend')
        current=stages.index(self.phase) if self.phase in stages else (4 if self.phase=='complete' else -1)
        cell=self.width()/4
        for i,name in enumerate(stages):
            x=i*cell+14
            active=i<=current
            p.setPen(QPen(QColor('#d7d7d7' if active else '#424242'),1))
            p.setBrush(QColor('#eeeeee' if active else '#191919'))
            p.drawEllipse(QPointF(x,15),3,3)
            if i<3:
                p.setPen(QPen(QColor('#454545'),1))
                p.drawLine(QPointF(x+10,15),QPointF(x+cell-10,15))
            p.setFont(QFont('Consolas',8))
            p.setPen(QColor('#dedede' if active else '#777777'))
            p.drawText(QRectF(i*cell+9,25,cell-9,16),Qt.AlignmentFlag.AlignLeft,name.upper())
