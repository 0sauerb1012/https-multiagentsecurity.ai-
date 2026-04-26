#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <aws-region> <ecr-repository-name> <image-tag>"
  exit 1
fi

AWS_REGION="$1"
ECR_REPOSITORY_NAME="$2"
IMAGE_TAG="$3"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY_NAME}:${IMAGE_TAG}"

aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

docker build -f Dockerfile.lambda -t "${IMAGE_URI}" .
docker push "${IMAGE_URI}"

echo "Pushed Lambda image: ${IMAGE_URI}"
