from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def find_project_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "src" / "meeting_skill").exists() and (candidate / "config").exists():
            return candidate
    raise RuntimeError("Cannot locate meeting-auto-skill project root.")


ROOT = find_project_root(Path(__file__).resolve())
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

if __name__ == "__main__":
    python = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    cmd = [str(python), "-m", "meeting_skill.cli", *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd, cwd=str(ROOT), env=env))
