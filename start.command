#!/bin/zsh
set -e
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  echo "Run ./setup.command first."
  exit 1
fi
if [[ ! -f backend/static/frontend/index.html ]]; then
  if [[ ! -f frontend/dist/index.html ]]; then (cd frontend && npm run build); fi
  mkdir -p backend/static/frontend
  cp -R frontend/dist/. backend/static/frontend/
fi
echo "Eco-Sentinel: http://127.0.0.1:${PORT:-5050}"
echo "Login: demo / demo123 (or register your own account)"
echo "Keep this terminal open. Press Ctrl+C to stop."
cd backend
exec ../.venv/bin/python app.py
