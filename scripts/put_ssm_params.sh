#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <aws-region> <parameter-name> <value> [parameter-name value ...]"
  echo "Example: $0 us-east-1 /multiagentsecurity/dev/DATABASE_URL 'postgresql://...'"
  exit 1
fi

AWS_REGION="$1"
shift

if (( $# % 2 != 0 )); then
  echo "Parameter names and values must be supplied in pairs."
  exit 1
fi

while (( $# > 0 )); do
  PARAM_NAME="$1"
  PARAM_VALUE="$2"
  shift 2

  aws ssm put-parameter \
    --region "${AWS_REGION}" \
    --name "${PARAM_NAME}" \
    --type SecureString \
    --overwrite \
    --value "${PARAM_VALUE}" >/dev/null

  echo "Stored ${PARAM_NAME}"
done
