#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v python >/dev/null 2>&1 || { echo "python is required"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required"; exit 1; }

cd "$ROOT_DIR/backend"
python -m pip install -e ".[dev]"

cd "$ROOT_DIR/frontend"
npm install
