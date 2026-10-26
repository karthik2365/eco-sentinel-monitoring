#!/bin/zsh
set -e
cd "${0:A:h}"
if [[ ! -d .venv ]]; then
  PYTHON_BIN=${PYTHON_BIN:-python3.11}
  "$PYTHON_BIN" -m venv .venv
fi
.venv/bin/python -m pip install -r backend/requirements-lock.txt
(cd frontend && npm ci && npm run build)
mkdir -p backend/static/frontend
cp -R frontend/dist/. backend/static/frontend/
echo "Setup complete. Run ./start.command"
