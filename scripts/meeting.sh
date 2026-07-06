#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
export PYTHONPATH="$PWD/src"
python -m meeting_skill.cli "$@"
