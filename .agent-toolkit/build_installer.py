"""Build the Windows executable using a project-local build environment."""
from pathlib import Path
import hashlib
import subprocess
import sys


def main():
    home = Path(__file__).resolve().parent
    if sys.platform != "win32":
        raise RuntimeError("Build the Windows executable on Windows.")
    work = home / "installer-build"
    output = home.parent
    work.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--onefile", "--windowed", "--noupx",
                    "--name", "AgentToolkitSetup", "--distpath", str(output), "--workpath", str(work),
                    "--specpath", str(work), "--paths", str(home), "--hidden-import", "providers",
                    str(home / "installer.py")], check=True)
    executable = output / "AgentToolkitSetup.exe"
    checksum = hashlib.sha256(executable.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(checksum + "  AgentToolkitSetup.exe\n", encoding="utf-8")
    print(executable)


if __name__ == "__main__":
    main()
