from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = PROJECT_ROOT / "src"

if __name__ == "__main__":
    sys.path.insert(0, str(SRC_DIR))
    cmd = [sys.executable, "-m", "meeting_skill.cli", "run-file", *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd, cwd=PROJECT_ROOT))
