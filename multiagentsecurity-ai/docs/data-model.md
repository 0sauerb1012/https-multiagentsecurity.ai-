# Data Model

## Core Tables

The initial schema uses six main concepts:

- `sources`: upstream systems or feeds such as arXiv, Crossref, and RSS
- `articles`: normalized research or intelligence records
- `tags`: reusable taxonomy terms grouped by domain
- `article_tags`: many-to-many relationship between articles and tags
- `categories`: higher-level groupings for articles
- `article_categories`: many-to-many relationship between articles and categories

## Why Both Tags and Categories

Tags are intended for specific, reusable labels such as:

- `prompt-injection`
- `graph-orchestration`
- `observability`

Categories are intended for broader editorial buckets such as:

- Research
- Taxonomy
- Intelligence
- Case Studies

This distinction keeps the model flexible for browsing and filtering without forcing a single hierarchy.

## Source of Truth

For the current scaffold:

- JSON in `packages/taxonomy` provides shared, versioned taxonomy definitions
- SQL seed data initializes corresponding database records

Longer term, the team should decide whether taxonomy editing is code-driven, admin-driven, or hybrid.

## Article Shape

Articles are expected to include:

- Source identity and upstream URL
- Title, summary, slug, and publication date
- Optional authors metadata
- Raw payload for traceability
- Timestamps for ingestion and updates

## TODO

- Add provenance rules for conflicting source updates
- Decide whether article body content lives in the database or a separate content pipeline
- Add materialized search fields or a dedicated search subsystem when needed
