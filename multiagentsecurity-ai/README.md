# multiagentsecurity-ai

`multiagentsecurity-ai` is a production-oriented monorepo scaffold for `multiagentsecurity.ai`, a web and data platform for multi-agent security research, taxonomy, and intelligence.

This repository is intentionally a starting point, not a finished product. It provides:

- A Next.js frontend in `apps/web`
- A Python ingestion service in `services/ingestion`
- SQL migrations and taxonomy seeds in `database/`
- Terraform scaffolding for AWS infrastructure in `infra/terraform`
- Shared taxonomy JSON in `packages/taxonomy`
- CI workflow skeletons in `.github/workflows`
- Practical starter documentation in `docs/`

## What Exists Today

Implemented as scaffold:

- Monorepo layout with production-oriented separation of concerns
- Minimal Next.js App Router website with reusable layout and mock research/taxonomy data
- Health endpoint for uptime checks and deployment smoke tests
- Lambda-friendly Python ingestion package with source adapters and placeholder pipeline stages
- Starter PostgreSQL migrations for sources, articles, tags, and category mappings
- Terraform module and environment structure with the `dev` environment as the most complete reference
- Shell scripts for bootstrap, migration, seeding, and Lambda packaging
- CI workflow placeholders for web, ingestion, and Terraform

Still placeholder or intentionally incomplete:

- Real database connectivity and query implementations
- Live ingestion from arXiv, Crossref, and RSS feeds
- Authentication, admin workflows, and editorial tooling
- Production-grade Terraform internals for every AWS service
- Amplify provisioning in Terraform
- End-to-end tests, monitoring, and release automation

## Monorepo Structure

```text
multiagentsecurity-ai/
  apps/web                  Next.js frontend
  services/ingestion        Python ingestion and enrichment pipeline
  packages/taxonomy         Shared taxonomy definitions
  database                  SQL migrations and seeds
  infra/terraform           AWS infrastructure scaffolding
  docs                      Architecture and rollout notes
  scripts                   Developer and deployment helper scripts
  .github/workflows         CI workflows
```

## Local Development

### Frontend

1. `cd apps/web`
2. `cp .env.example .env.local`
3. `npm install`
4. `npm run dev`

The site currently uses mock data in `apps/web/lib/queries/` so the UI can evolve before the database integration is ready.

### Ingestion Service

1. `cd services/ingestion`
2. `python -m venv .venv`
3. `source .venv/bin/activate`
4. `pip install -r requirements.txt`
5. `pytest`

The ingestion code is organized for Lambda deployment but currently returns placeholder records and includes TODO markers where real integrations should be implemented.

### Database

Use the SQL files in `database/migrations` and `database/seeds` with a local PostgreSQL instance or an AWS RDS dev database.

Helper scripts:

- `./scripts/migrate-db.sh`
- `./scripts/seed-db.sh`

## Deployment Overview

The intended rollout is staged:

1. Deploy the frontend to an Amplify-generated test URL first
2. Stand up AWS dev infrastructure for ingestion and PostgreSQL
3. Optionally attach a development subdomain for broader testing
4. Cut over the production domain only after the stack is validated

See:

- `docs/architecture.md`
- `docs/deployment-plan.md`
- `docs/dns-cutover.md`
- `infra/terraform/README.md`

## Recommended Next Steps

- Replace mock web queries with database-backed query functions
- Implement scheduled ingestion source fetches and persistence
- Add local Docker Compose or Dev Container support if the team needs tighter reproducibility
- Expand Terraform module internals and remote state handling
- Introduce observability, secrets rotation, and release promotion flows
