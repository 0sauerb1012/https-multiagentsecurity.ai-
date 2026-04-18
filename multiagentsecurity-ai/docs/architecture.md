# Architecture

## Intent

`multiagentsecurity.ai` is intended to become a hub for:

- Research discovery and curation
- Taxonomy-driven tagging and categorization
- Lightweight intelligence ingestion from structured and semi-structured sources
- Publication of articles, tags, and linked source metadata

## Target AWS Shape

The initial architecture is intentionally simple:

- `apps/web` deployed on AWS Amplify for frontend hosting and previews
- PostgreSQL on Amazon RDS for durable storage
- Python ingestion service packaged for AWS Lambda
- EventBridge schedule to trigger periodic ingestion runs
- Secrets Manager for database credentials and third-party API keys
- IAM roles scoped to ingestion execution and infrastructure needs
- Optional Route 53 later for subdomain or production cutover

## Data Flow

1. EventBridge invokes the ingestion Lambda on a fixed schedule.
2. The ingestion service fetches source material from adapters such as arXiv, Crossref, and RSS.
3. Source records are normalized into a common article model.
4. Placeholder dedupe and tagging stages prepare records for persistence.
5. Records are written into PostgreSQL tables for articles, sources, tags, and categories.
6. The Next.js application reads from the database through thin query modules.

## Frontend Notes

The web application is built with Next.js App Router and is currently backed by mock query functions. This keeps the UI work unblocked while the database and ingestion pipeline mature.

Planned web concerns:

- Server-rendered research and taxonomy pages
- Article detail pages by slug
- Health endpoint for deployment verification
- Future search, filters, and editorial workflows

## Backend Notes

The ingestion service is designed to stay small:

- Source adapters remain isolated by origin
- Normalization, dedupe, and tagging remain explicit pipeline steps
- Lambda packaging keeps operational cost and complexity low early on

If ingestion complexity grows, the pipeline can later move to a container or orchestrated workflow without changing the external repository shape.

## TODO

- Finalize data ownership boundaries between taxonomy JSON and database taxonomy tables
- Decide whether article rendering stays in PostgreSQL or moves to MDX/content storage
- Add observability design for ingestion metrics and failure alerts
