# Phase 1 AWS Deployment Plan

This document now reflects the current AWS shape for the project:

- `Web app`: ECS Fargate running the FastAPI app from `uvicorn main:app`
- `HTTP ingress`: Application Load Balancer
- `Database`: external serverless Postgres such as `Neon` or `Supabase`
- `Ingestion`: AWS Lambda
- `Scheduler`: EventBridge Scheduler
- `Config and secrets`: SSM Parameter Store or direct runtime environment variables
- `Logs`: CloudWatch Logs with `7` day retention
- `Container registries`: separate ECR repositories for the web image and the ingestion Lambda image

## Objectives

- avoid the Lambda cold-start problems seen with the old web tier
- keep the web deployment simple and inexpensive
- preserve `seed`, `incremental`, and `reconcile` ingestion modes
- keep a clean path to HTTPS, private networking, or higher availability later
- keep the deployment operationally small for an early-stage research site

## Architecture

### Web tier

- ALB in two public subnets
- ECS Fargate service with one task by default
- task launched with a public IP
- no NAT gateway
- web container built from [Dockerfile](/home/ben/Desktop/website/Dockerfile)

### Ingestion tier

- ingestion Lambda handler:
  - `lambda_handlers.ingest.handler`
- image built from [Dockerfile.lambda](/home/ben/Desktop/website/Dockerfile.lambda)
- EventBridge daily incremental schedule
- EventBridge weekly reconcile schedule

### Database

- external Postgres via `DATABASE_URL`
- `Preferred`: Neon
- `Also viable`: Supabase

## Why this shape

### Why ECS for the web app

The repo notes and CloudWatch history showed the server-rendered FastAPI app was a poor runtime fit for Lambda cold starts. ECS avoids the Mangum/Lambda adapter path and gives predictable startup behavior.

### Why public subnets and no NAT

The main cost driver in the earlier private-subnet Fargate design was the NAT gateway, not the app task itself. Running the web task in public subnets with security-group-restricted ingress keeps the architecture much cheaper while remaining acceptable for this low-traffic project stage.

### Why Lambda for ingestion

The ingestion workload is scheduled and bounded, which is still a good fit for Lambda. Keeping it on Lambda avoids unnecessary refactoring and preserves the cheap scheduler-driven batch model.

## Runtime split

### Local development

- web:
  - `uvicorn main:app --host 0.0.0.0 --port 8000`
- ingestion:
  - `python -m services.ingest --mode incremental --target-limit 250 --per-topic-limit 40 --overlap-days 3`

### AWS

- web:
  - ECS Fargate task running the default command from [Dockerfile](/home/ben/Desktop/website/Dockerfile)
- ingestion:
  - `lambda_handlers.ingest.handler`

## Secrets strategy

### Local

Use `.env` with placeholders from [.env.example](/home/ben/Desktop/website/.env.example) or [.env.postgres.example](/home/ben/Desktop/website/.env.postgres.example).

### AWS

Prefer SSM Parameter Store SecureString values:

- `DATABASE_URL`
- `OPENAI_API_KEY`
- optional source API values

Behavior differs by runtime:

- ECS web task:
  - Terraform injects SSM-backed values as ECS task secrets
- ingestion Lambda:
  - [lambda_handlers/runtime_env.py](/home/ben/Desktop/website/lambda_handlers/runtime_env.py) hydrates values from `*_PARAM` env vars at runtime

## Networking

Current cost-optimized networking shape:

- one VPC
- two public subnets
- internet gateway
- internet-facing ALB
- ECS web task with a public IP
- no NAT gateway

This is intentionally not the highest-availability or highest-isolation design. It is the lowest-cost containerized web shape currently chosen for the repo.

## Scheduling plan

### Daily incremental

- cadence: once per day
- default cron: `cron(0 11 * * ? *)`
- target: ingestion Lambda
- payload:
  - `mode=incremental`
  - `target_limit=250`
  - `per_topic_limit=40`
  - `overlap_days=3`

### Weekly reconcile

- cadence: once per week
- default cron: `cron(0 12 ? * SUN *)`
- target: ingestion Lambda
- payload:
  - `mode=reconcile`
  - `target_limit=500`
  - `per_topic_limit=60`
  - `reconcile_lookback_days=30`

## Logging

Use CloudWatch Logs:

- ECS web log group retention: `7` days
- ingestion Lambda log group retention: `7` days
- keep `LOG_LEVEL=INFO` for production

## Rough platform cost posture

This design is materially cheaper than private-subnet Fargate with NAT, but more expensive than the old Lambda web MVP.

Main fixed cost drivers now are:

- ALB
- public IPv4 charges
- always-on single Fargate task

NAT is intentionally absent to keep baseline cost lower.

## Migration path later

When usage grows, migrate selectively:

### Improve web resilience

- raise ECS desired count above `1`
- add HTTPS with ACM and Route53
- move tasks to private subnets if stronger network isolation becomes worth the extra cost

### Move database back to AWS

- swap Neon/Supabase `DATABASE_URL` for RDS or Aurora Postgres
- keep the current Postgres-compatible database layer

### Move ingestion later if needed

- keep `services.ingest` as the shared entrypoint
- only move ingestion off Lambda if execution duration or memory limits become restrictive

## Repo alignment

The repo now supports this architecture through:

- [infra/terraform/phase1](/home/ben/Desktop/website/infra/terraform/phase1)
- [Dockerfile](/home/ben/Desktop/website/Dockerfile)
- [Dockerfile.lambda](/home/ben/Desktop/website/Dockerfile.lambda)
- [scripts/deploy_web_image.sh](/home/ben/Desktop/website/scripts/deploy_web_image.sh)
- [scripts/deploy_lambda_image.sh](/home/ben/Desktop/website/scripts/deploy_lambda_image.sh)
- [lambda_handlers/ingest.py](/home/ben/Desktop/website/lambda_handlers/ingest.py)

The custom domain can be repointed later to the ALB once the new stack is verified.
