# Cost-Optimized MVP AWS Deployment Plan

This document replaces the earlier App Runner + RDS + ECS plan with a lower-cost MVP shape that preserves the current FastAPI app, Postgres compatibility, and scheduled ingestion model.

## Objectives

- remove always-on compute for the web tier
- remove fixed RDS cost from the MVP path
- preserve `seed`, `incremental`, and `reconcile` ingestion modes
- keep a clean migration path back to AWS-native managed services later
- target roughly `$10-$30/month` where traffic and AI usage remain modest

## MVP Architecture

- `Web API`: AWS Lambda running FastAPI through `Mangum`
- `HTTP ingress`: API Gateway HTTP API
- `Database`: external serverless Postgres such as `Neon` or `Supabase`
- `Ingestion`: AWS Lambda
- `Scheduler`: EventBridge Scheduler
- `Config and secrets`: direct Lambda environment variables for local/dev, or SSM Parameter Store for production
- `Logs`: CloudWatch Logs with `7` day retention
- `Container registry`: Amazon ECR for a shared Lambda container image

## Why this is cheaper

### App Runner replacement

App Runner charges for provisioned memory even when traffic is low. Lambda does not. For an MVP research site with low or bursty traffic, Lambda + HTTP API removes the fixed always-on web tier cost.

### RDS replacement

Single-AZ RDS PostgreSQL is one of the biggest fixed costs in the previous plan. Neon or Supabase gives you Postgres compatibility without the baseline RDS instance charge.

### ECS replacement

Daily and weekly jobs are predictable, infrequent, and bounded. Lambda handles those schedules more cheaply than an ECS/Fargate task for this stage.

## Runtime Split

### Local development

- web:
  - `uvicorn main:app --host 0.0.0.0 --port 8000`
- ingestion:
  - `python -m services.ingest --mode incremental --target-limit 250 --per-topic-limit 40 --overlap-days 3`

### AWS MVP

- API Lambda handler:
  - `lambda_handlers.api.handler`
- ingestion Lambda handler:
  - `lambda_handlers.ingest.handler`

Both are built from the same Lambda image defined in [Dockerfile.lambda](/home/ben/Desktop/website/Dockerfile.lambda).

## Database Strategy

For the MVP, use serverless Postgres:

- `Preferred`: Neon
- `Also viable`: Supabase

Requirements:

- standard `postgresql://...` connection string
- SSL enabled by the provider
- connection pooling if the provider offers it

The application remains Postgres-compatible through `DATABASE_URL`, so moving back to RDS later is a configuration and infrastructure change, not an application rewrite.

## Secrets Strategy

### Local

Use `.env` with placeholder-based examples from [.env.example](/home/ben/Desktop/website/.env.example) or [.env.postgres.example](/home/ben/Desktop/website/.env.postgres.example).

### AWS MVP

Prefer SSM Parameter Store SecureString values:

- `DATABASE_URL_PARAM`
- `OPENAI_API_KEY_PARAM`
- optional source parameter names

Direct environment variables are still supported, but Parameter Store is the safer default for production.

The Lambda handlers load SSM-backed values at cold start through [lambda_handlers/runtime_env.py](/home/ben/Desktop/website/lambda_handlers/runtime_env.py).

## Scheduling Plan

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

### One-time seed

- run locally against the production Postgres URL
- or invoke the ingestion Lambda manually with `mode=seed`

## Logging

Use CloudWatch Logs only:

- API Lambda log group retention: `7` days
- ingestion Lambda log group retention: `7` days
- keep `LOG_LEVEL=INFO` for production
- avoid verbose debug logging unless diagnosing a live issue

## Estimated Monthly Cost Range

These are rough ranges and depend on traffic, execution time, and AI usage. They are intentionally directional rather than exact quotes.

| Component | Previous AWS-native plan | Cost-optimized MVP |
| --- | ---: | ---: |
| Web compute | App Runner: roughly `$20-$40+` baseline | Lambda + HTTP API: often `<$1-$5` at low traffic |
| Database | RDS PostgreSQL Single-AZ: roughly `$15-$30+` baseline | Neon/Supabase free tier to roughly `$0-$10+` |
| Scheduled jobs | ECS Fargate scheduled tasks: roughly `$5-$20+` | Lambda scheduled jobs: often `<$1-$3` |
| Secrets/config | Secrets Manager: several dollars if used broadly | SSM Parameter Store: often `$0-$1` for MVP usage |
| Logs | CloudWatch Logs: variable | CloudWatch Logs with short retention: low single digits |
| Total platform | roughly `$40-$90+` before AI spend | roughly `$10-$30` before AI spend |

AI inference cost remains the wildcard in both architectures. The savings here are about the platform baseline.

## Migration Path Later

When traffic or ingestion volume grows, migrate selectively:

### Move database back to AWS

- swap Neon/Supabase `DATABASE_URL` for RDS or Aurora Postgres
- keep the current Postgres-compatible database layer

### Move ingestion back to ECS

- keep `services.ingest` as the shared entrypoint
- move long-running or memory-heavy ingestion jobs to ECS/Fargate only if Lambda limits become restrictive

### Move web tier back to containers

- keep `main.py` unchanged
- continue to support the existing local `uvicorn` entrypoint
- deploy the same app to ECS or a future container service if sustained traffic makes Lambda less efficient

## Repo Alignment

The repo now supports this MVP shape with:

- [lambda_handlers/api.py](/home/ben/Desktop/website/lambda_handlers/api.py)
- [lambda_handlers/ingest.py](/home/ben/Desktop/website/lambda_handlers/ingest.py)
- [lambda_handlers/runtime_env.py](/home/ben/Desktop/website/lambda_handlers/runtime_env.py)
- [Dockerfile.lambda](/home/ben/Desktop/website/Dockerfile.lambda)
- [infra/terraform/phase1](/home/ben/Desktop/website/infra/terraform/phase1)

This keeps the local developer workflow intact while removing the high fixed-cost services from the MVP path.
