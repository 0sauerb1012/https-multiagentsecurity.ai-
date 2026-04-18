#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL must be set" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for migration in "$ROOT_DIR"/database/migrations/*.sql; do
  echo "Applying $migration"
  psql "$DATABASE_URL" -f "$migration"
done
