# Next Session Plan - Possible Fargate Pivot for Web Tier

This note captures the current state after the first AWS MVP deployment attempt and the likely next architectural decision.

## Current status

The low-cost MVP stack was deployed with:

- API Gateway HTTP API
- API Lambda
- ingestion Lambda
- EventBridge schedules
- Neon as the external Postgres database
- SSM Parameter Store for `DATABASE_URL` and `OPENAI_API_KEY`

Infrastructure deployment succeeded and the public endpoint exists.

## What was learned

### 1. Lambda image deployment now works

The repo now supports:

- versioned Lambda image pushes
- automatic image tag incrementing in [scripts/deploy_lambda_image.sh](/home/ben/Desktop/website/scripts/deploy_lambda_image.sh)
- updating local `terraform.tfvars` with the new tag

### 2. Several runtime bugs were fixed

Already fixed in code:

- Postgres boolean comparison bug in [services/database.py](/home/ben/Desktop/website/services/database.py)
- `_load_topic_papers()` web snapshot call signature bug in [services/research_hub.py](/home/ben/Desktop/website/services/research_hub.py)

### 3. The bigger issue is Lambda runtime fit for the web app

CloudWatch logs showed:

```text
INIT_REPORT Init Duration: 10000.08 ms Phase: init Status: timeout
```

Interpretation:

- API Lambda cold-start initialization is too heavy
- startup/import path is likely too expensive for the current Lambda web model

Most likely contributors:

- runtime env hydration during import
- FastAPI app import and initialization during cold start
- heavier-than-ideal module graph for a Lambda-hosted server-rendered site

## Important conclusion

The web application may not be a good long-term fit for Lambda, even though the ingestion jobs still are.

The likely better architecture for the next iteration is:

- web app on ECS Fargate
- ingestion jobs remain on Lambda initially
- EventBridge continues scheduling ingestion
- Neon remains the database for now

This would preserve:

- lower DB cost than RDS
- cheap scheduled ingestion
- more predictable web performance

while avoiding:

- Lambda cold-start sensitivity for the web tier
- Mangum/Lambda adapter complexity for a server-rendered FastAPI app

## Proposed next-session architecture

### Web tier

Move from:

- API Gateway HTTP API -> Lambda -> Mangum -> FastAPI

To:

- public ingress -> ECS Fargate service -> `uvicorn main:app`

Ingress options to decide next time:

- ALB in front of ECS
- or a simpler AWS-managed public path if available and cost-appropriate

### Ingestion tier

Keep as-is for now:

- EventBridge Scheduler
- ingestion Lambda
- `seed`, `incremental`, and `reconcile` modes

Only move ingestion off Lambda later if:

- runtime duration
- memory usage
- or reliability

make Lambda a poor fit there too.

### Database

Keep:

- Neon via `DATABASE_URL`

Do not reintroduce RDS yet unless there is a clear operational reason.

## Repo state at the time of this note

Relevant deployment/runtime files already exist:

- [Dockerfile](/home/ben/Desktop/website/Dockerfile)
- [Dockerfile.lambda](/home/ben/Desktop/website/Dockerfile.lambda)
- [lambda_handlers/api.py](/home/ben/Desktop/website/lambda_handlers/api.py)
- [lambda_handlers/ingest.py](/home/ben/Desktop/website/lambda_handlers/ingest.py)
- [infra/terraform/phase1](/home/ben/Desktop/website/infra/terraform/phase1)
- [scripts/deploy_lambda_image.sh](/home/ben/Desktop/website/scripts/deploy_lambda_image.sh)
- [scripts/put_ssm_params.sh](/home/ben/Desktop/website/scripts/put_ssm_params.sh)

This means the next session does not need to start from zero. It needs to decide whether to:

1. keep tuning Lambda for the web tier
2. or pivot the web tier to Fargate

## Recommended next-session decision

Start by deciding this explicitly:

- if minimum monthly cost is still the top priority, try one more Lambda optimization pass
- if user-facing performance and simpler runtime behavior now matter more, move the web tier to Fargate

Current recommendation based on observed behavior:

- pivot the web tier to Fargate
- keep ingestion on Lambda for now

## If Lambda is attempted one more time before pivoting

The next Lambda-specific mitigations would be:

1. lazy-initialize the API handler in [lambda_handlers/api.py](/home/ben/Desktop/website/lambda_handlers/api.py)
2. reduce import-time work further
3. increase API Lambda memory from `1024` to `1536` or `2048`
4. retest cold starts

But this should be treated as a bounded experiment, not an open-ended tuning loop.

## If the Fargate pivot is chosen

Next session should do the following:

1. redesign the web deployment from Lambda to ECS Fargate
2. decide ingress:
   - ALB most likely
3. keep Neon
4. keep ingestion Lambda initially
5. update Terraform accordingly
6. reuse [Dockerfile](/home/ben/Desktop/website/Dockerfile) for the web tier
7. stop using `Mangum`/API Lambda for the public site

## Main question to resume with

At the start of the next session, resume with:

`Should the web tier stay on Lambda, or should it move to ECS Fargate while keeping Lambda for ingestion?`
