# Neon Setup Notes

Use this as the preferred external Postgres provider for the MVP deployment.

## Why Neon fits this repo

- Postgres-compatible `DATABASE_URL`
- lower fixed cost than RDS for MVP
- easy branch-based dev workflow later if needed
- pooled connection strings are available, which is useful for Lambda workloads

## Recommended Neon setup

1. Create a Neon project in the AWS region closest to the Lambda deployment.
2. Create or confirm a database named `researchhub`.
3. Create a dedicated app role rather than using the default owner role for day-to-day app access.
4. Retrieve the connection string.
5. Prefer the pooled connection string if Neon exposes both pooled and direct URLs.

## Connection string guidance

Expected format:

```text
postgresql://username:password@hostname/researchhub?sslmode=require
```

Recommended:

- keep `sslmode=require`
- use the pooled URL for Lambda if available
- keep the raw URL out of committed files

## Where to put it

### Local development

Use:

- [.env.postgres.example](/home/ben/Desktop/website/.env.postgres.example)
- local `.env`

### AWS deployment

Preferred:

- store the value in SSM Parameter Store as a SecureString

Recommended parameter name:

```text
/multiagentsecurity/dev/DATABASE_URL
```

Then point Terraform at that parameter name through:

- `database_url_param_name`

## Quick verification before AWS

Before deployment, verify the URL locally:

```bash
cp .env.postgres.example .env
```

Replace the placeholder connection string, then:

```bash
bash scripts/start-local-postgres.sh
.venv/bin/python3 scripts/smoke_test_postgres.py
```

The smoke test itself uses local Docker Postgres, but the point is to confirm the app's Postgres code path is already working before you switch the connection string to Neon.

## Expected production usage pattern

- API Lambda reads from Neon
- ingestion Lambda writes to Neon
- EventBridge invokes ingestion on schedule

## When to stop using Neon for this app

Move to RDS or Aurora later if:

- you need tighter AWS-native networking controls
- you want AWS-native backups and database ops ownership
- the external provider pricing or connection model stops fitting the workload

For the MVP, Neon is the simpler and cheaper fit.
