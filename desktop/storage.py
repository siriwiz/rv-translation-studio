"""Per-user settings and Windows DPAPI-protected OAuth credentials."""
import ctypes
import json
import os
from pathlib import Path
import sys
from ctypes import wintypes


def resource(name):
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / name


def data_dir():
    root = Path(os.environ.get('RUEVALLEY_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'RueValleyTranslator')
    root.mkdir(parents=True, exist_ok=True)
    return root


def read_json(name, default):
    try:
        return json.loads((data_dir() / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def write_json(name, value):
    atomic_write(data_dir() / name, json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8'))


def atomic_write(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_bytes(data)
    os.replace(temp, path)


class Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    buf = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel.LocalFree(target.pbData)


def save_credentials(value):
    atomic_write(data_dir() / 'accounts.dat', protect(json.dumps(value).encode()))


def load_credentials():
    path = data_dir() / 'accounts.dat'
    if not path.exists():
        return {'accounts': [], 'active': None}
    return json.loads(protect(path.read_bytes(), decrypt=True).decode())
