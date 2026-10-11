#!/usr/bin/env bash
# Thin wrapper around verify_competition_data.py. It only checks; it never downloads.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; fi
exec "$PY" scripts/verify_competition_data.py "$@"
