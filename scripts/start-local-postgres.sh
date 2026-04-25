#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${LOCAL_POSTGRES_CONTAINER_NAME:-researchhub-postgres}"
POSTGRES_DB="${LOCAL_POSTGRES_DB:-researchhub}"
POSTGRES_USER="${LOCAL_POSTGRES_USER:-researchhub_admin}"
POSTGRES_PASSWORD="${LOCAL_POSTGRES_PASSWORD:-researchhub_dev}"
POSTGRES_PORT="${LOCAL_POSTGRES_PORT:-5432}"
POSTGRES_IMAGE="${LOCAL_POSTGRES_IMAGE:-postgres:16}"

if docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
  if docker ps --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
    echo "Local Postgres container '${CONTAINER_NAME}' is already running."
    exit 0
  fi
  docker start "${CONTAINER_NAME}" >/dev/null
  echo "Started existing local Postgres container '${CONTAINER_NAME}'."
  exit 0
fi

docker run \
  --name "${CONTAINER_NAME}" \
  --detach \
  --restart unless-stopped \
  -e POSTGRES_DB="${POSTGRES_DB}" \
  -e POSTGRES_USER="${POSTGRES_USER}" \
  -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  -p "${POSTGRES_PORT}:5432" \
  "${POSTGRES_IMAGE}" >/dev/null

echo "Started local Postgres container '${CONTAINER_NAME}' on port ${POSTGRES_PORT}."
