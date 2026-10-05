"""Build the Windows executable using a project-local build environment."""
from pathlib import Path
import subprocess
import sys


def main():
    home = Path(__file__).resolve().parent
    if sys.platform != "win32":
        raise RuntimeError("Build the Windows executable on Windows.")
    work = home / "installer-build"
    output = home / "installer-dist"
    work.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--onefile", "--windowed", "--noupx",
                    "--name", "AgentToolkitSetup", "--distpath", str(output), "--workpath", str(work),
                    "--specpath", str(work), "--paths", str(home), "--hidden-import", "providers",
                    str(home / "installer.py")], check=True)
    print(output / "AgentToolkitSetup.exe")


if __name__ == "__main__":
    main()
