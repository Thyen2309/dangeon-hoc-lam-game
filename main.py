from pathlib import Path
import runpy
import sys


PROJECT_DIR = Path(__file__).resolve().parent / "project"

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

runpy.run_path(str(PROJECT_DIR / "main.py"), run_name="__main__")
