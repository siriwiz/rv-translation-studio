"""Desktop package and shared Windows native-runtime bootstrap."""
import ctypes
import os
from pathlib import Path
import sys

# Qt wheels carry an older MSVC runtime. Load the app's current shared runtime
# before Qt so ONNX Runtime and Qt use the same compatible C++ library.
if sys.platform == 'win32':
    _runtime_root = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(os.environ['SystemRoot']) / 'System32'
    _cpp_runtime = ctypes.WinDLL(str(_runtime_root / 'msvcp140.dll'))
