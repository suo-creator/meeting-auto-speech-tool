#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
[ -f config/.env ] || cp config/.env.example config/.env
export PYTHONPATH="$PWD/src"
python -m meeting_skill.cli --help
