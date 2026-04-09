#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

echo "Starting Conference Matching Platform on ${HOST}:${PORT}"
exec .venv/bin/python server.py --host "$HOST" --port "$PORT"
