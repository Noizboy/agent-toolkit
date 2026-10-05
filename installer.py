"""Launch Agent Toolkit setup from the repository root."""
from pathlib import Path
import runpy
import sys


if __name__ == "__main__":
    toolkit = Path(__file__).resolve().parent / ".agent-toolkit"
    sys.path.insert(0, str(toolkit))
    runpy.run_path(str(toolkit / "installer.py"), run_name="__main__")
