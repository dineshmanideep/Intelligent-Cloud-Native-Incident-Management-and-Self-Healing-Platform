#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/pip install -r incident_service/requirements.txt

echo "Python environment ready. Activate it with: source .venv/bin/activate"
