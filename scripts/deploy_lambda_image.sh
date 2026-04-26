#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <aws-region> <ecr-repository-name> [image-tag|auto] [terraform-tfvars-path]"
  exit 1
fi

AWS_REGION="$1"
ECR_REPOSITORY_NAME="$2"
REQUESTED_TAG="${3:-auto}"
TFVARS_PATH="${4:-infra/terraform/phase1/terraform.tfvars}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

next_auto_tag() {
  local date_prefix existing_tags max_suffix next_suffix
  date_prefix="$(date +%F)"
  existing_tags="$(aws ecr list-images \
    --region "${AWS_REGION}" \
    --repository-name "${ECR_REPOSITORY_NAME}" \
    --query 'imageIds[].imageTag' \
    --output text 2>/dev/null || true)"
  max_suffix=0

  for tag in ${existing_tags}; do
    if [[ "${tag}" =~ ^${date_prefix}-([0-9]+)$ ]]; then
      if (( 10#${BASH_REMATCH[1]} > max_suffix )); then
        max_suffix=$((10#${BASH_REMATCH[1]}))
      fi
    fi
  done

  next_suffix="$(printf "%02d" $((max_suffix + 1)))"
  echo "${date_prefix}-${next_suffix}"
}

update_tfvars_image_tag() {
  local image_tag="$1"
  local tfvars_path="$2"

  if [[ ! -f "${tfvars_path}" ]]; then
    echo "Terraform vars file not found at ${tfvars_path}; skipping image_tag update."
    return 0
  fi

  if rg -q '^image_tag\s*=' "${tfvars_path}"; then
    sed -i.bak -E "s|^image_tag\s*=.*$|image_tag = \"${image_tag}\"|" "${tfvars_path}"
    rm -f "${tfvars_path}.bak"
  else
    printf '\nimage_tag = "%s"\n' "${image_tag}" >> "${tfvars_path}"
  fi

  echo "Updated ${tfvars_path} with image_tag = \"${image_tag}\""
}

if [[ "${REQUESTED_TAG}" == "auto" ]]; then
  IMAGE_TAG="$(next_auto_tag)"
else
  IMAGE_TAG="${REQUESTED_TAG}"
fi

IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY_NAME}:${IMAGE_TAG}"

aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

docker build -f Dockerfile.lambda -t "${IMAGE_URI}" .
docker push "${IMAGE_URI}"

update_tfvars_image_tag "${IMAGE_TAG}" "${TFVARS_PATH}"

echo "Pushed Lambda image: ${IMAGE_URI}"
echo "Image tag: ${IMAGE_TAG}"
