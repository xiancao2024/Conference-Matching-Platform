#!/usr/bin/env bash
set -euo pipefail

# Simple runner to prepare a venv, install deps, and run the precompute script.
# Usage: run on the VM inside the extracted repo directory.

PYTHON=python3
if ! command -v $PYTHON >/dev/null 2>&1; then
  echo "$PYTHON not found, aborting" >&2
  exit 1
fi

echo "Creating venv..."
$PYTHON -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

echo "Installing Python packages (sentence-transformers, faiss-cpu, numpy)..."
pip install sentence-transformers numpy faiss-cpu

echo "Running precompute script..."
python scripts/precompute_embeddings.py 2>&1 | tee precompute_run.log

echo "Done. Outputs in data/ (embeddings.npy, faiss.index, entity_ids.json if created)."
