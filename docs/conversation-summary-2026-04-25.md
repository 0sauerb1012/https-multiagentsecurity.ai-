# Conversation Summary - 2026-04-25

This note captures the current state of the `multiagentsecurity.ai` architecture and repo changes so work can resume later without replaying the full conversation.

## Current direction

The deployment plan was re-architected away from the more expensive AWS-native baseline:

- old direction:
  - App Runner
  - RDS PostgreSQL
  - ECS Fargate scheduled ingestion
  - EventBridge Scheduler
  - Secrets Manager
- new MVP direction:
  - Lambda + API Gateway HTTP API for FastAPI
  - external Postgres via `DATABASE_URL` such as Neon or Supabase
  - Lambda for ingestion jobs
  - EventBridge Scheduler invoking Lambda directly
  - SSM Parameter Store or env vars for runtime secrets/config
  - CloudWatch Logs with short retention

Target platform cost discussed:

- roughly `$10-$30/month` before AI spend for the MVP path

## Application decisions

- Keep local dev unchanged:
  - `uvicorn main:app --host 0.0.0.0 --port 8000`
  - `python -m services.ingest --mode incremental --target-limit 250 --per-topic-limit 40 --overlap-days 3`
- Keep ingestion modes:
  - `seed`
  - `incremental`
  - `reconcile`
- Preserve Postgres compatibility through `DATABASE_URL`
- Avoid RDS for MVP
- Avoid always-on web compute for MVP
- Keep a clean migration path back to RDS, ECS, or container-based web hosting later

## Repo changes already made

### Lambda support

Added:

- [lambda_handlers/api.py](/home/ben/Desktop/website/lambda_handlers/api.py)
- [lambda_handlers/ingest.py](/home/ben/Desktop/website/lambda_handlers/ingest.py)
- [lambda_handlers/runtime_env.py](/home/ben/Desktop/website/lambda_handlers/runtime_env.py)

Purpose:

- `lambda_handlers.api.handler`
  - wraps the FastAPI app with `Mangum`
- `lambda_handlers.ingest.handler`
  - runs scheduled ingestion with event-driven `mode`, limits, and overlap/lookback settings
- `runtime_env.py`
  - loads secrets/config from SSM Parameter Store when `*_PARAM` env vars are set

### Containerization

Added:

- [Dockerfile.lambda](/home/ben/Desktop/website/Dockerfile.lambda)

Existing:

- [Dockerfile](/home/ben/Desktop/website/Dockerfile)

Intent:

- keep local/container workflows intact
- support a shared Lambda image in ECR

### Dependencies

Updated:

- [requirements.txt](/home/ben/Desktop/website/requirements.txt)

Added packages:

- `mangum`
- `boto3`

### Environment templates

Updated:

- [.env.example](/home/ben/Desktop/website/.env.example)

Added support for:

- `DATABASE_URL_PARAM`
- `OPENAI_API_KEY_PARAM`
- `OPENALEX_API_KEY_PARAM`
- `OPENALEX_EMAIL_PARAM`
- `CROSSREF_EMAIL_PARAM`
- `SEMANTIC_SCHOLAR_API_KEY_PARAM`
- `LOG_LEVEL`

Existing local Postgres helper:

- [.env.postgres.example](/home/ben/Desktop/website/.env.postgres.example)

### Terraform

Replaced the old scaffold in:

- [infra/terraform/phase1/main.tf](/home/ben/Desktop/website/infra/terraform/phase1/main.tf)
- [infra/terraform/phase1/variables.tf](/home/ben/Desktop/website/infra/terraform/phase1/variables.tf)
- [infra/terraform/phase1/outputs.tf](/home/ben/Desktop/website/infra/terraform/phase1/outputs.tf)
- [infra/terraform/phase1/terraform.tfvars.example](/home/ben/Desktop/website/infra/terraform/phase1/terraform.tfvars.example)
- [infra/terraform/phase1/README.md](/home/ben/Desktop/website/infra/terraform/phase1/README.md)

Current Terraform now defines:

- ECR repository
- API Lambda
- ingestion Lambda
- API Gateway HTTP API
- EventBridge daily incremental schedule
- EventBridge weekly reconcile schedule
- IAM roles/policies
- CloudWatch log groups with short retention

Current Terraform intentionally does not define:

- App Runner
- RDS
- ECS/Fargate
- VPC resources

### Documentation

Updated:

- [README.md](/home/ben/Desktop/website/README.md)
- [docs/phase1-aws-deployment.md](/home/ben/Desktop/website/docs/phase1-aws-deployment.md)

The repo now documents the cost-optimized MVP architecture instead of the old App Runner/RDS/Fargate model.

## Local Postgres validation already completed

To prove the new Postgres path before AWS, a local validation workflow was added:

- [scripts/start-local-postgres.sh](/home/ben/Desktop/website/scripts/start-local-postgres.sh)
- [scripts/stop-local-postgres.sh](/home/ben/Desktop/website/scripts/stop-local-postgres.sh)
- [scripts/smoke_test_postgres.py](/home/ben/Desktop/website/scripts/smoke_test_postgres.py)

This was run successfully against a Dockerized local Postgres instance.

Observed successful output:

```text
Postgres smoke test passed.
Latest run id: 1
Latest run mode: incremental
Sync watermark source: arxiv
Sync watermark published_at: 2026-04-24T00:00:00+00:00
```

## Verification already run

These checks were run successfully:

- `python3 -m py_compile main.py services/ingest.py services/database.py services/research_hub.py lambda_handlers/api.py lambda_handlers/ingest.py lambda_handlers/runtime_env.py`
- `terraform fmt -recursive infra/terraform/phase1`
- `.venv/bin/pip install -r requirements.txt`
- local Postgres smoke test via `scripts/smoke_test_postgres.py`

## Important status note

The repo is now aligned to the low-cost MVP architecture, but deployment has not yet been proven in AWS.

Not yet done:

- `terraform init`
- `terraform validate`
- `terraform plan`
- first ECR push for the Lambda image
- first deployed Lambda/API Gateway test in AWS
- first live connection test against Neon or Supabase

## Recommended next steps

When work resumes, the next highest-value tasks are:

1. choose the external Postgres provider:
   - Neon preferred
   - Supabase acceptable
2. create production/dev `DATABASE_URL`
3. decide whether production secrets will use:
   - SSM Parameter Store
   - or direct Lambda environment variables
4. run:
   - `terraform init`
   - `terraform validate`
   - `terraform plan`
5. build and push the Lambda image from [Dockerfile.lambda](/home/ben/Desktop/website/Dockerfile.lambda)
6. do the first dev deployment
7. test:
   - API Lambda through API Gateway
   - daily incremental ingestion Lambda
   - weekly reconcile Lambda

## Cost model discussed

Rough directional estimates from the conversation:

- previous AWS-native plan:
  - roughly `$40-$90+` before AI spend
- new cost-optimized MVP:
  - roughly `$10-$30` before AI spend
- future scalable architecture:
  - likely `$50+` depending on RDS, ECS, and traffic

## Additional site/content context

There were also earlier website content updates in this broader thread:

- About page cleaned up and made personal to Benjamin Sauers
- blog boilerplate removed
- one real blog post imported
- About nav dropdown removed
- Industry Intel hidden for now

Those UI/content changes are separate from the deployment refactor but already exist in the repo.
