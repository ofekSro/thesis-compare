"""Launch the tkinter GUI for the blast analysis pipeline.

    python run_gui.py

Thin entry point — everything lives in the gui/ package.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gui.app import main

if __name__ == '__main__':
    main()
