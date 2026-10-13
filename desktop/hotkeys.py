"""Original low-level keyboard hooks, dispatching only via Qt signals."""
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import keyboard
import ctypes
import threading
import time


class GlobalHotkeys(QObject):
    translate = pyqtSignal()
    clear = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.handles = []
        self.held = {0x70: False, 0x71: False}
        self.last_emit = {0x70: 0, 0x71: 0}
        self.lock = threading.Lock()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.poll)

    def emit_key(self, vk):
        with self.lock:
            now = time.monotonic()
            if now - self.last_emit[vk] < .3:
                return
            self.last_emit[vk] = now
        (self.translate if vk == 0x70 else self.clear).emit()

    def poll(self):
        # Some games/other hooks consume registered hotkeys. Poll physical state
        # as a fallback, independent of which window owns foreground focus.
        for vk in self.held:
            pressed = bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
            if self.held[vk] and not pressed:
                self.emit_key(vk)
            self.held[vk] = pressed

    def start(self):
        try:
            self.handles.append(keyboard.add_hotkey('f1', lambda: self.emit_key(0x70), trigger_on_release=True, suppress=True))
            self.handles.append(keyboard.add_hotkey('f2', lambda: self.emit_key(0x71), trigger_on_release=True, suppress=True))
        except Exception:
            self.stop()
        self.timer.start()

    def stop(self):
        self.timer.stop()
        for handle in self.handles:
            keyboard.remove_hotkey(handle)
        self.handles.clear()
