# Multi-Agent Security Research Hub

This is the first Python-based iteration of a research hub for tracking recent multi-agent security papers from arXiv, OpenAlex, Crossref, Semantic Scholar, and DBLP.

## What it does

- reuses the existing Python arXiv integration from `api/`
- adds OpenAlex as a second scholarly source
- adds Crossref as a third metadata source
- adds Semantic Scholar as a fourth scholarly source
- adds DBLP as a computer-science bibliography source
- pulls the newest papers first from a fixed multi-agent security query set
- clusters overlapping works across sources into canonical merged records before review
- supports local SQLite-backed batch ingestion for larger corpus testing before deployment
- renders a lightweight server-side web UI with FastAPI + Jinja templates
- shows title, authors, published date, merged provenance, categories, source link, and bullet summaries
- includes a simple concentration/gap heat map based on merged category coverage across sources
- uses OpenAI for summaries when `OPENAI_API_KEY` is set
- falls back to a local extractive summary when no API key is available
- removes topic choice in the UI so the app behaves like a dedicated field tracker

## Project structure

```text
.
├── api/                 Reused Python arXiv and summarization helpers
├── routes/              FastAPI web routes
├── services/            Topic selection, orchestration, merging, categorization, summarization, ingestion, and persistence
├── static/              CSS for the local UI
├── templates/           Server-rendered HTML templates
├── docs/                Deployment and architecture notes
├── infra/terraform/     Phase 1 AWS Terraform scaffold
├── .env.example         Local environment template
├── Dockerfile           Shared web/worker container image
├── main.py              Local app entrypoint
└── requirements.txt     Python dependencies
```

## Setup

1. Create a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy the environment template:

   ```bash
   cp .env.example .env
   ```

4. Optionally set `OPENAI_API_KEY` in `.env` if you want model-generated summaries/classification.
5. Optionally set `OPENALEX_API_KEY` and `OPENALEX_EMAIL` in `.env` if you want identified OpenAlex requests.
6. Optionally set `CROSSREF_EMAIL` in `.env` so Crossref requests use a polite contact header.
7. Optionally set `SEMANTIC_SCHOLAR_API_KEY` in `.env` for authenticated Semantic Scholar requests.
8. Optionally set `DATABASE_PATH` if you do not want the default local SQLite file at `data/research_hub.db`.
9. For future production deployment, `DATABASE_BACKEND`, `DATABASE_URL`, `HOST`, and `PORT` are now supported as environment variables.

## Local Postgres smoke test

Use this before the first AWS deploy so the app is proven against `DATABASE_URL` instead of only SQLite.

1. Install dependencies:

   ```bash
   .venv/bin/pip install -r requirements.txt
   ```

2. Copy the Postgres env template:

   ```bash
   cp .env.postgres.example .env
   ```

3. Start local Postgres:

   ```bash
   ./scripts/start-local-postgres.sh
   ```

4. Run the database smoke test:

   ```bash
   .venv/bin/python3 scripts/smoke_test_postgres.py
   ```

5. Stop the container when you are done:

   ```bash
   ./scripts/stop-local-postgres.sh
   ```

The smoke test validates schema initialization, ingestion run writes, and source sync state reads/writes against PostgreSQL.

## Batch ingestion and local DB testing

To test a larger corpus locally before AWS, run the ingestion pipeline separately from the web app:

```bash
python3 -m services.ingest --mode seed --target-limit 1000 --per-topic-limit 60
```

What this does:

- fetches candidate records from all configured scholarly sources
- merges duplicates into canonical papers
- filters/classifies them for multi-agent security relevance
- generates/stores bullet summaries
- persists the results into local SQLite

Additional ingestion modes:

- `incremental`
  - daily sync against per-source watermarks plus a small overlap window
- `reconcile`
  - wider lookback pass to catch delayed indexing

After ingestion, the web app will prefer the stored corpus for:

- `Research Feed`
- `Research Library`
- `Research Gaps`

## Run locally

```bash
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## Container run

Build the shared image:

```bash
docker build -t multiagentsecurity-ai:local .
```

Run the web app:

```bash
docker run --rm -p 8000:8000 --env-file .env multiagentsecurity-ai:local
```

Run the ingestion worker:

```bash
docker run --rm --env-file .env multiagentsecurity-ai:local \
  python -m services.ingest --mode incremental --target-limit 250 --per-topic-limit 40 --overlap-days 3
```

## Cost-Optimized MVP Architecture

The low-cost AWS MVP now uses:

- AWS Lambda + API Gateway HTTP API for the FastAPI web app
- Neon or Supabase for PostgreSQL-compatible persistence
- a shared Lambda image for both the API and ingestion handlers
- EventBridge Scheduler for daily `incremental` and weekly `reconcile`
- SSM Parameter Store or Lambda environment variables for secrets/config
- CloudWatch Logs with short retention

Core runtime entrypoints stay the same locally:

- `uvicorn main:app --host 0.0.0.0 --port 8000`
- `python -m services.ingest --mode incremental --target-limit 250 --per-topic-limit 40 --overlap-days 3`

Additional Lambda entrypoints now exist:

- API handler: `lambda_handlers.api.handler`
- ingestion handler: `lambda_handlers.ingest.handler`

### MVP deployment flow

1. provision a serverless Postgres database in Neon or Supabase
2. store `DATABASE_URL` and `OPENAI_API_KEY` as either:
   - Lambda env vars
   - or SSM Parameter Store SecureString values
3. build and push the Lambda image:

   ```bash
   docker build -f Dockerfile.lambda -t multiagentsecurity-ai-lambda:latest .
   ```

4. deploy [infra/terraform/phase1](/home/ben/Desktop/website/infra/terraform/phase1)
5. validate the HTTP API and scheduled jobs

### Estimated monthly platform cost

| Architecture | Estimated range |
| --- | ---: |
| Current AWS-native plan | `$40-$90+` before AI spend |
| Cost-optimized MVP | `$10-$30` before AI spend |
| Future scalable architecture | `$50+` depending on RDS, ECS, and traffic |

### Migration notes

- move back to `RDS` later by swapping `DATABASE_URL`
- move ingestion back to `ECS` if Lambda timeout or memory becomes constraining
- move web compute back to `ECS` or another container service if traffic becomes sustained enough to justify always-on compute

## AWS Phase 1

The current Terraform in `infra/terraform/phase1` is now the cost-optimized MVP stack:

- ECR
- API Lambda
- API Gateway HTTP API
- ingestion Lambda
- EventBridge Scheduler
- CloudWatch log groups
- optional SSM Parameter Store-backed secrets

See:

- [docs/phase1-aws-deployment.md](/home/ben/Desktop/website/docs/phase1-aws-deployment.md)
- [infra/terraform/phase1/README.md](/home/ben/Desktop/website/infra/terraform/phase1/README.md)

## Notes

- The app does not yet use authentication.
- If a local SQLite corpus exists, the feed/library/gaps pages will read from stored records instead of fetching live on every request.
- Topic retrieval, summarization, and presentation are separated so future work can add:
  - more academic APIs
  - daily scheduled refresh and caching
  - stronger relevance ranking
  - richer research gap detection
  - Postgres/RDS as a drop-in replacement for SQLite
  - a future return to ECS or another container runtime if Lambda is outgrown
