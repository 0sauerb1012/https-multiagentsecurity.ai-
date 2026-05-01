# Dev Deploy Checklist

Use this checklist for the current `multiagentsecurity.ai` AWS deployment:

- public web app on ECS Fargate behind an ALB
- ingestion on Lambda
- external Postgres

## 1. Create the external Postgres database

Preferred provider:

- Neon

Alternative:

- Supabase

Requirements:

- create a database named `researchhub`
- copy the pooled or direct Postgres connection string
- confirm the connection string is in standard `postgresql://...` format

Recommended:

- use the provider's connection pooling option if available
- keep SSL enabled

See:

- [docs/neon-setup.md](/home/ben/Desktop/website/docs/neon-setup.md)

## 2. Decide how secrets will be injected

Preferred for AWS:

- SSM Parameter Store SecureString

Required values:

- `DATABASE_URL`
- `OPENAI_API_KEY`

Optional values:

- `OPENALEX_API_KEY`
- `OPENALEX_EMAIL`
- `CROSSREF_EMAIL`
- `SEMANTIC_SCHOLAR_API_KEY`

Recommended parameter names:

- `/multiagentsecurity/dev/DATABASE_URL`
- `/multiagentsecurity/dev/OPENAI_API_KEY`
- `/multiagentsecurity/dev/OPENALEX_API_KEY`
- `/multiagentsecurity/dev/OPENALEX_EMAIL`
- `/multiagentsecurity/dev/CROSSREF_EMAIL`
- `/multiagentsecurity/dev/SEMANTIC_SCHOLAR_API_KEY`

You can create them with:

```bash
bash scripts/put_ssm_params.sh us-east-1 \
  /multiagentsecurity/dev/DATABASE_URL 'postgresql://...' \
  /multiagentsecurity/dev/OPENAI_API_KEY 'sk-...'
```

## 3. Prepare Terraform variables

Copy the template:

```bash
cp infra/terraform/phase1/terraform.tfvars.example infra/terraform/phase1/terraform.tfvars
```

If you want a more deployment-ready baseline, start from:

```bash
cp infra/terraform/phase1/terraform.tfvars.dev.example infra/terraform/phase1/terraform.tfvars
```

Set at minimum:

```hcl
aws_region   = "us-east-1"
project_name = "multiagentsecurity-ai"
environment  = "dev"

web_image_tag    = "2026-04-30-01"
lambda_image_tag = "2026-04-30-01"

database_url_param_name   = "/multiagentsecurity/dev/DATABASE_URL"
openai_api_key_param_name = "/multiagentsecurity/dev/OPENAI_API_KEY"
```

If you are not using SSM for dev, you can set direct values instead:

```hcl
database_url   = "postgresql://..."
openai_api_key = "sk-..."
```

That is less safe and should stay out of committed files.

## 4. Create the ECR repositories

Initialize and apply Terraform once so the repositories exist:

```bash
terraform -chdir=infra/terraform/phase1 init
terraform -chdir=infra/terraform/phase1 validate
terraform -chdir=infra/terraform/phase1 apply -target=aws_ecr_repository.web -target=aws_ecr_repository.app
```

This lets you push the web and Lambda images before the full stack apply.

## 5. Build and push the web image

Use the helper script:

```bash
bash scripts/deploy_web_image.sh us-east-1 multiagentsecurity-ai-dev-web
```

Script inputs:

1. AWS region
2. ECR repository name
3. optional image tag, defaults to an auto-incremented `YYYY-MM-DD-NN` tag
4. optional `terraform.tfvars` path, defaults to `infra/terraform/phase1/terraform.tfvars`

The script:

- builds [Dockerfile](/home/ben/Desktop/website/Dockerfile)
- logs Docker into ECR
- pushes the image
- updates `web_image_tag` in your local `terraform.tfvars` if that file exists

## 6. Build and push the ingestion Lambda image

Use the existing helper script:

```bash
bash scripts/deploy_lambda_image.sh us-east-1 multiagentsecurity-ai-dev-lambda
```

The script:

- builds [Dockerfile.lambda](/home/ben/Desktop/website/Dockerfile.lambda)
- logs Docker into ECR
- pushes the image
- updates `lambda_image_tag` in your local `terraform.tfvars` if that file exists

## 7. Apply the full Terraform stack

```bash
terraform -chdir=infra/terraform/phase1 plan
terraform -chdir=infra/terraform/phase1 apply
```

Expected created resources:

- VPC
- public ALB
- ECS cluster
- ECS task definition and service
- web and ingestion ECR repositories
- ingestion Lambda
- EventBridge daily schedule
- EventBridge weekly schedule
- CloudWatch log groups
- IAM roles and policies

## 8. Smoke test the deployed web app

After apply, read the ALB DNS or URL from Terraform output:

```bash
terraform -chdir=infra/terraform/phase1 output web_url
```

Then:

- open the home page
- open `/research-feed`
- confirm page rendering succeeds with the external Postgres configuration
- confirm CSS and JS load correctly

## 9. Trigger ingestion manually once

Invoke the ingestion Lambda manually with `seed` or `incremental` mode.

Example:

```bash
aws lambda invoke \
  --function-name multiagentsecurity-ai-dev-ingestion \
  --payload '{"mode":"incremental","target_limit":25,"per_topic_limit":10,"overlap_days":3,"years_back":5}' \
  /tmp/ingestion-response.json
cat /tmp/ingestion-response.json
```

For first corpus load, use `seed` with tighter limits before doing a large ingest.

## 10. Verify scheduled jobs

Check that both schedules exist:

- daily incremental
- weekly reconcile

Then confirm CloudWatch logs show successful invocation.

## 11. Recommended order for first real use

1. deploy infrastructure
2. push the web image
3. push the ingestion Lambda image
4. confirm the ALB-served site loads
5. run a small manual `seed`
6. confirm records are visible in the site
7. run a small manual `incremental`
8. leave schedules enabled

## Current known assumptions

- the web tier now runs as a single ECS task for cost reasons
- the web tier sits in public subnets and has no NAT gateway
- ingestion remains on Lambda
- the custom domain can be repointed later to the ALB

## Remaining unknowns

- first live ECS startup time and memory profile with `0.5 vCPU / 1 GB`
- first real ALB health check behavior against the FastAPI container
- first live Neon or Supabase connection from the ECS task
- first full ingest execution duration and memory profile under Lambda limits
