#!/usr/bin/env bash
set -euo pipefail

echo "Bootstrapping multiagentsecurity-ai development environment"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required for apps/web" >&2
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for services/ingestion" >&2
fi

echo "TODO: install shared toolchain dependencies, create .env files, and validate local services."
