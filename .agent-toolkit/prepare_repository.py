"""Copy only the reusable toolkit into an empty standalone repository directory."""
from pathlib import Path
import argparse
import os
import shutil

from sources import read_json, safe_path, save_json


def prepare(source: Path, destination: Path):
    destination = destination.absolute()
    safe_path(Path(destination.anchor), destination.relative_to(destination.anchor).as_posix())
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("The standalone repository destination must be empty.")
    destination.mkdir(parents=True, exist_ok=True)
    excluded = {"vendor", "runtime", "__pycache__", ".build-venv", "installer-build", "installer-dist"}
    private = {"tools.lock.json", "inventory.json", "INVENTORY.md", "mcp-probes.json",
               "project.json", "provider-state.json", "installation.json"}
    toolkit = source / ".agent-toolkit"
    for folder, directories, filenames in os.walk(toolkit, followlinks=False):
        directories[:] = [name for name in directories if name not in excluded]
        for filename in filenames:
            if filename in private:
                continue
            file = Path(folder) / filename
            relative = file.relative_to(source).as_posix()
            safe_path(source, relative)
            target = safe_path(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
    target = destination / ".agents/skills/agent-toolkit/SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / ".agents/skills/agent-toolkit/SKILL.md", target)
    state = read_json(toolkit / "tools.lock.json", {"tools": {}})
    portable = {"schema_version": 1, "tools": {}}
    for name, record in state["tools"].items():
        portable["tools"][name] = {key: record[key] for key in ["source", "commit"] if key in record}
        if record.get("npm"):
            portable["tools"][name]["npm"] = {key: record["npm"][key] for key in ["package", "version", "integrity"]}
    save_json(destination / ".agent-toolkit/tools.lock.json", portable)
    shutil.copy2(toolkit / "AGENTS.template.md", destination / "AGENTS.md")
    ignores = (toolkit / "gitignore.template").read_text(encoding="utf-8")
    ignores += "\n.agent-toolkit/.build-venv/\n.agent-toolkit/installer-build/\n.agent-toolkit/installer-dist/\n**/__pycache__/\n*.env\n.env\n"
    (destination / ".gitignore").write_text(ignores, encoding="utf-8")
    shutil.copy2(source / "README.md", destination / "README.md")
    for name in ["installer.py", "AgentToolkitSetup.exe", "SHA256SUMS.txt"]:
        entry = safe_path(source, name)
        if entry.is_file():
            shutil.copy2(entry, safe_path(destination, name))
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(prepare(Path(__file__).resolve().parents[1], args.destination))
