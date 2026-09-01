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
cp "$PROC_DIR/handler.py" "$PROC_DIR/line_grouping.py" "$PROC_DIR/image_processing.py" "$PROC_DIR/textract_pipeline.py" "$PROC_DIR/bedrock_extraction.py" "$LAMBDA_DIR/shared/pricing.py" "$LAMBDA_DIR/shared/dynamo.py" "$LAMBDA_DIR/shared/constants.py" "$LAMBDA_DIR/shared/line_items.py" "$PKG_DIR/"
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
cp "$API_DIR/handler.py" "$LAMBDA_DIR/shared/pricing.py" "$LAMBDA_DIR/shared/dynamo.py" "$LAMBDA_DIR/shared/constants.py" "$LAMBDA_DIR/shared/line_items.py" "$PKG_DIR/"
"$VENV/bin/pip" install -r "$API_DIR/requirements.txt" \
  --target "$PKG_DIR" \
  --platform manylinux2014_x86_64 \
  --python-version 3.12 \
  --only-binary=:all: \
  --quiet --no-cache-dir
echo "API package ready: $PKG_DIR"

echo "=== Packaging stores_refresh Lambda ==="
STORES_DIR="$LAMBDA_DIR/stores_refresh"
PKG_DIR="$STORES_DIR/package"
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR"
cp "$STORES_DIR/handler.py" "$PKG_DIR/"
echo "stores_refresh package ready: $PKG_DIR"

echo "=== Lambda packaging complete ==="
