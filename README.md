# Multi-Agent Security Research Hub

This is the first local-only iteration of a Python-only research hub for tracking recent multi-agent security papers from arXiv, OpenAlex, Crossref, Semantic Scholar, and DBLP.

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
├── services/            Topic selection, orchestration, merging, categorization, summarization, ingestion, and SQLite persistence
├── static/              CSS for the local UI
├── templates/           Server-rendered HTML templates
├── .env.example         Local environment template
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

## Batch ingestion and local DB testing

To test a larger corpus locally before AWS, run the ingestion pipeline separately from the web app:

```bash
python -m services.ingest --target-limit 1000 --per-topic-limit 60
```

What this does:

- fetches candidate records from all configured scholarly sources
- merges duplicates into canonical papers
- filters/classifies them for multi-agent security relevance
- generates/stores bullet summaries
- persists the results into local SQLite

After ingestion, the web app will prefer the stored corpus for:

- `Research Feed`
- `Research Library`
- `Research Gaps`

## Run locally

```bash
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## Notes

- The app is local-only and does not use authentication or a database.
- The app is local-only and does not use authentication.
- If a local SQLite corpus exists, the feed/library/gaps pages will read from stored records instead of fetching live on every request.
- Topic retrieval, summarization, and presentation are separated so future work can add:
  - more academic APIs
  - daily scheduled refresh and caching
  - stronger relevance ranking
  - richer research gap detection
  - Postgres/RDS as a drop-in replacement for SQLite
