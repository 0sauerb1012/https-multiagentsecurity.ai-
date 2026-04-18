#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/services/ingestion"
BUILD_DIR="$SERVICE_DIR/build"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

cp -R "$SERVICE_DIR/src/." "$BUILD_DIR/"

echo "Packaged ingestion source into $BUILD_DIR"
echo "TODO: install dependencies into the build directory and create a deployment zip."
