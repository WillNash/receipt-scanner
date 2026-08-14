#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAMBDA_DIR="$PROJECT_ROOT/lambda"
VENV="$HOME/.local/venv"

if [ ! -f "$VENV/bin/pip" ]; then
  echo "ERROR: venv not found at $VENV — run scripts/install_tools.sh first" >&2
  exit 1
fi

echo "=== Packaging processor Lambda ==="
PROC_DIR="$LAMBDA_DIR/processor"
PKG_DIR="$PROC_DIR/package"
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR"
cp "$PROC_DIR/handler.py" "$PKG_DIR/"
# --platform and --only-binary guarantee Lambda-compatible manylinux binary wheels.
# Without this, pip may fall back to a source dist that won't work in the Lambda runtime.
"$VENV/bin/pip" install -r "$PROC_DIR/requirements.txt" \
  --target "$PKG_DIR" \
  --platform manylinux2014_x86_64 \
  --python-version 3.12 \
  --only-binary=:all: \
  --quiet --no-cache-dir
echo "Processor package ready: $PKG_DIR"

echo "=== Packaging api Lambda ==="
API_DIR="$LAMBDA_DIR/api"
PKG_DIR="$API_DIR/package"
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR"
cp "$API_DIR/handler.py" "$PKG_DIR/"
"$VENV/bin/pip" install -r "$API_DIR/requirements.txt" \
  --target "$PKG_DIR" \
  --platform manylinux2014_x86_64 \
  --python-version 3.12 \
  --only-binary=:all: \
  --quiet --no-cache-dir
echo "API package ready: $PKG_DIR"

echo "=== Lambda packaging complete ==="
