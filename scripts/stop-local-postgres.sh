#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${LOCAL_POSTGRES_CONTAINER_NAME:-researchhub-postgres}"

if ! docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
  echo "Local Postgres container '${CONTAINER_NAME}' does not exist."
  exit 0
fi

if docker ps --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
  docker stop "${CONTAINER_NAME}" >/dev/null
  echo "Stopped local Postgres container '${CONTAINER_NAME}'."
  exit 0
fi

echo "Local Postgres container '${CONTAINER_NAME}' is already stopped."
