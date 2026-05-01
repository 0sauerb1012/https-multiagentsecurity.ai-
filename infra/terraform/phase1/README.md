# Phase 1 Terraform

This directory now defines the current deployment shape for `multiagentsecurity.ai`:

- ECS Fargate for the public FastAPI web app
- an internet-facing Application Load Balancer
- two public subnets in a dedicated VPC
- a separate ECR repository for the web image
- ingestion Lambda for `seed`, `incremental`, and `reconcile`
- a separate ECR repository for the ingestion Lambda image
- EventBridge Scheduler for daily and weekly ingestion runs
- CloudWatch log groups with short retention
- optional SSM Parameter Store integration for secrets

It intentionally does not create RDS, API Gateway, NAT gateways, private subnets, or App Runner resources.

## External database

For this stack, use an external Postgres provider such as Neon or Supabase and supply its connection string through either:

- `database_url`
- or `database_url_param_name`

`database_url_param_name` is the preferred path because it keeps the secret out of Terraform configuration.

## Usage

1. Copy the example variables:

```bash
cp terraform.tfvars.example terraform.tfvars
```

2. Fill in:

- `database_url_param_name` or `database_url`
- `openai_api_key_param_name` or `openai_api_key`
- optional source API and contact settings

3. Initialize Terraform:

```bash
terraform init
```

4. Review the plan:

```bash
terraform plan
```

5. Apply:

```bash
terraform apply
```

## Image deployment flow

Terraform creates the ECR repositories, but it does not build or push the images.

Typical flow:

1. apply Terraform once for the ECR repositories if they do not exist yet
2. build and push the web image from [Dockerfile](/home/ben/Desktop/website/Dockerfile)
3. build and push the ingestion Lambda image from [Dockerfile.lambda](/home/ben/Desktop/website/Dockerfile.lambda)
4. run `terraform apply`

Use the helper scripts:

- [scripts/deploy_web_image.sh](/home/ben/Desktop/website/scripts/deploy_web_image.sh)
- [scripts/deploy_lambda_image.sh](/home/ben/Desktop/website/scripts/deploy_lambda_image.sh)

The web script updates `web_image_tag` in your local `terraform.tfvars`.

The Lambda script updates `lambda_image_tag` in your local `terraform.tfvars`.

## SSM parameter pattern

If you prefer Parameter Store:

- create SecureString parameters such as `/multiagentsecurity/dev/DATABASE_URL`
- set the corresponding `*_param_name` Terraform variables

Runtime behavior differs by compute type:

- ECS web task: Terraform injects SSM-backed values into the task definition as ECS secrets
- ingestion Lambda: the handler still loads SSM-backed values at runtime through [lambda_handlers/runtime_env.py](/home/ben/Desktop/website/lambda_handlers/runtime_env.py)

## What this stack optimizes for

- cheaper always-on web compute than a private-subnet Fargate design with NAT
- cleaner runtime behavior than the old Lambda-hosted web tier
- retained low-cost Lambda scheduling for ingestion
- short log retention
- clean migration path to private subnets, HTTPS, or higher availability later
