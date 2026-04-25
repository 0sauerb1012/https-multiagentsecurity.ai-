# Phase 1 Terraform

This directory now defines the cost-optimized MVP deployment shape for `multiagentsecurity.ai`:

- ECR for a shared Lambda container image
- API Lambda for the FastAPI app
- API Gateway HTTP API
- ingestion Lambda for `seed`, `incremental`, and `reconcile`
- EventBridge Scheduler for daily and weekly runs
- CloudWatch log groups with short retention
- optional SSM Parameter Store integration for secrets

It intentionally does not create RDS, ECS, App Runner, or VPC resources.

## External database

For the MVP, use an external Postgres provider such as Neon or Supabase and supply its connection string through either:

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

Terraform creates the ECR repository, but it does not build or push the Lambda image.

Typical flow:

1. build the Lambda image with `Dockerfile.lambda`
2. authenticate Docker to ECR
3. push the tag referenced by `image_tag`
4. run `terraform apply`

Example:

```bash
docker build -f Dockerfile.lambda -t multiagentsecurity-ai-lambda:latest .
```

## SSM parameter pattern

If you prefer Parameter Store:

- create SecureString parameters such as `/multiagentsecurity/dev/DATABASE_URL`
- set the corresponding `*_param_name` Terraform variables
- the Lambda handlers will load the decrypted values at cold start

## What this stack optimizes for

- no always-on compute
- no always-on database charge from RDS
- direct EventBridge-to-Lambda scheduling
- short log retention
- clean migration path back to ECS, App Runner, or RDS later
