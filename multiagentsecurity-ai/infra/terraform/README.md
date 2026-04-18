# Terraform

This directory contains scaffold-level Terraform for AWS infrastructure supporting `multiagentsecurity.ai`.

## Current Intent

- `environments/dev` is the primary reference environment
- `staging` and `prod` mirror the shape with lighter placeholder configuration
- `modules/` contains reusable building blocks for networking, PostgreSQL, Lambda ingestion, scheduling, secrets, IAM, and optional Route 53 work

## What Is Included

- VPC networking scaffold
- RDS PostgreSQL module interface
- Lambda ingestion packaging and runtime placeholders
- EventBridge schedule placeholder
- Secrets Manager placeholder
- IAM role scaffolding
- S3 artifacts bucket
- Optional Route 53 module kept separate to avoid premature domain coupling

## What Is Not Done Yet

- Full production hardening
- Remote state bootstrapping
- Detailed security groups and subnet layouts
- Amplify provisioning
- Monitoring, alarms, and backup policy details

## Usage

Example for dev:

1. `cd infra/terraform/environments/dev`
2. Copy `backend.hcl.example` and `terraform.tfvars.example` to local equivalents
3. `terraform init -backend-config=backend.hcl`
4. `terraform plan`

Amplify for the frontend is intentionally documented rather than fully provisioned in Terraform at this stage.
