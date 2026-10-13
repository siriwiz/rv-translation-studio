"""Small, local Qt animations. No web view or network assets."""
from PyQt6.QtCore import QVariantAnimation, QEasingCurve, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QPushButton


class MotionButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.hover = 0.
        self.motion = QVariantAnimation(self)
        self.motion.setDuration(180)
        self.motion.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.motion.valueChanged.connect(self._frame)

    def _frame(self, value):
        self.hover = float(value)
        self.update()

    def _to(self, value):
        self.motion.stop()
        self.motion.setStartValue(self.hover)
        self.motion.setEndValue(value)
        self.motion.start()

    def enterEvent(self, event):
        self._to(1.)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._to(0.)
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.hover and self.isEnabled():
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setBrush(QColor(255, 255, 255, round(18*self.hover)))
            p.setPen(QPen(QColor(255, 255, 255, round(80*self.hover)), 1))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)

