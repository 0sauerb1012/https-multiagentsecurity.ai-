# Dev Deploy Checklist

Use this checklist for the first cost-optimized MVP deployment of `multiagentsecurity.ai`.

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

image_tag = "latest"

database_url_param_name   = "/multiagentsecurity/dev/DATABASE_URL"
openai_api_key_param_name = "/multiagentsecurity/dev/OPENAI_API_KEY"
```

If you are not using SSM for dev, you can set direct values instead:

```hcl
database_url   = "postgresql://..."
openai_api_key = "sk-..."
```

That is less safe and should stay out of committed files.

## 4. Create the ECR repository

Initialize and apply Terraform once so the repository exists:

```bash
terraform -chdir=infra/terraform/phase1 init
terraform -chdir=infra/terraform/phase1 validate
terraform -chdir=infra/terraform/phase1 apply -target=aws_ecr_repository.app
```

This lets you push the Lambda image before the full stack apply.

## 5. Build and push the Lambda image

Use the helper script:

```bash
bash scripts/deploy_lambda_image.sh us-east-1 multiagentsecurity-ai-dev-lambda latest
```

Script inputs:

1. AWS region
2. ECR repository name
3. image tag

The script builds [Dockerfile.lambda](/home/ben/Desktop/website/Dockerfile.lambda), logs Docker into ECR, and pushes the image.

## 6. Apply the full Terraform stack

```bash
terraform -chdir=infra/terraform/phase1 plan
terraform -chdir=infra/terraform/phase1 apply
```

Expected created resources:

- ECR repository
- API Lambda
- ingestion Lambda
- API Gateway HTTP API
- EventBridge daily schedule
- EventBridge weekly schedule
- CloudWatch log groups
- IAM roles and policies

## 7. Smoke test the deployed API

After apply, read the API URL from Terraform output:

```bash
terraform -chdir=infra/terraform/phase1 output http_api_url
```

Then:

- open the home page
- open `/research-feed`
- confirm page rendering succeeds with the external Postgres configuration

## 8. Trigger ingestion manually once

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

## 9. Verify scheduled jobs

Check that both schedules exist:

- daily incremental
- weekly reconcile

Then confirm CloudWatch logs show successful invocation.

## 10. Recommended order for first real use

1. deploy infrastructure
2. run a small manual `seed`
3. confirm records are visible in the site
4. run a small manual `incremental`
5. leave schedules enabled

## Current known blockers removed

These were already addressed:

- Postgres runtime path exists
- Lambda handlers exist
- Terraform validates
- local Postgres smoke test passed

## Remaining unknowns

- first live Neon or Supabase connection from AWS Lambda
- first real API Gateway rendering behavior in Lambda
- first full ingest execution duration and memory profile under Lambda limits

If ingestion runs too long later, that is the signal to move only the ingestion worker back to ECS or another longer-running compute option.
