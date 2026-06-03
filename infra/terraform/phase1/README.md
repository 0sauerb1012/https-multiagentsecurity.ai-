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
- optional Amazon RDS for PostgreSQL in private subnets

It intentionally does not create NAT gateways, API Gateway, or App Runner resources.

## External database

For this stack, you can use either:

- an external Postgres provider such as Neon or Supabase
- or the optional managed RDS PostgreSQL instance in this Terraform stack

In both cases, the application still uses `DATABASE_URL` through either:

- `database_url`
- or `database_url_param_name`

`database_url_param_name` is the preferred path because it keeps the secret out of Terraform configuration.

## Managed RDS notes

If `managed_postgres_enabled = true`, Terraform creates:

- two private subnets for the database tier
- a DB subnet group
- an RDS PostgreSQL instance
- an AWS-managed master password stored in Secrets Manager
- security-group rules allowing the ECS web tasks to reach the database

If you also set `lambda_vpc_enabled = true`, Terraform attaches the ingestion Lambda to the same VPC so it can reach a private RDS instance.

Important operational constraint:

- a Lambda function attached to your VPC does not keep direct internet egress
- this ingestion job talks to external APIs, so private-subnet Lambda access usually requires a NAT gateway or a different runtime shape
- this stack does not create a NAT gateway, because the baseline design was chosen to avoid that fixed cost

Practical implication:

- `managed_postgres_enabled = true` is enough for the ECS web app to stop talking to Neon over the internet
- only enable `lambda_vpc_enabled` when you are also ready to handle Lambda egress separately, or when ingestion is moved off Lambda

## Usage

1. Copy the example variables:

```bash
cp terraform.tfvars.example terraform.tfvars
```

2. Fill in:

- `database_url_param_name` or `database_url`
- `openai_api_key_param_name` or `openai_api_key`
- optional source API and contact settings
- if using RDS: `managed_postgres_*` values

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

If you provision the managed RDS instance, update your SSM `DATABASE_URL` parameter after Terraform creates the DB endpoint. The app code is already Postgres-compatible; the cutover is a connection-string change plus data migration.

For the managed RDS path, the application no longer needs a database password in `terraform.tfvars`. Terraform lets RDS store the master password in Secrets Manager and injects or fetches that secret at runtime.

## Custom domain cutover

This stack can now manage a Route 53 hosted zone, ACM certificate validation, HTTPS on the ALB, and apex or `www` alias records for `multiagentsecurity.ai`.

Use the variables in [terraform.tfvars.example](/home/ben/Desktop/website/infra/terraform/phase1/terraform.tfvars.example):

- `enable_custom_domain = true` to enable ACM, HTTPS, and ALB alias records
- `create_public_hosted_zone = true` if AWS should create the Route 53 public hosted zone
- `hosted_zone_id` if the hosted zone already exists in Route 53
- `dns_records` to preserve non-web records currently hosted at HostGator, such as mail, SPF, DKIM, DMARC, and cPanel-related records

Typical migration flow:

1. Copy the current HostGator DNS records into `dns_records`, excluding the apex and `www` website records.
2. Set `enable_custom_domain = true`.
3. Either set `create_public_hosted_zone = true` or provide `hosted_zone_id`.
4. Run `terraform apply`.
5. If Terraform created the hosted zone, update the registrar nameservers using the `route53_name_servers` output.
6. Validate HTTPS using `custom_domain_url` after ACM finishes DNS validation.

If you are not ready to move the registrar nameservers yet, leave `enable_custom_domain = false` and continue using the ALB DNS name from the `alb_dns_name` output for smoke testing.

## What this stack optimizes for

- cheaper always-on web compute than a private-subnet Fargate design with NAT
- cleaner runtime behavior than the old Lambda-hosted web tier
- retained low-cost Lambda scheduling for ingestion
- short log retention
- clean migration path to private subnets, HTTPS, or higher availability later
