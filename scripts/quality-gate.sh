#!/bin/bash
set -e
echo "=== Quality Gate ==="
echo "[1/4] Running ruff check..."
ruff check .
echo "[2/4] Running unit tests with coverage..."
python -m pytest tests/unit/ -v --cov=odap --cov-fail-under=80 --tb=short
echo "[3/4] Running frontend lint..."
cd frontend && npm run lint && cd ..
echo "[4/4] Running frontend typecheck..."
cd frontend && npx tsc --noEmit && cd ..
echo "=== Quality Gate PASSED ==="
