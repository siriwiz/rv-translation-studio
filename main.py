"""RV TRANSLATION STUDIO 2.10.0 desktop entry point."""
import sys
from pathlib import Path
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).parent / '.build-tools'))
from desktop.window import run
if __name__ == '__main__':
    sys.exit(run())
