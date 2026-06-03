# arXiv Agent API

Small FastAPI service for:

- searching arXiv directly
- building arXiv queries from a research topic
- running a four-agent LangGraph workflow over candidate papers
- analyzing uploaded PDFs or Zotero RDF exports
- importing personal Zotero libraries through the Zotero API
- exporting reviewed results as RIS or Excel
- optionally backing search, review, and summarization with OpenAI models

## Endpoints

`GET /health`

`GET /papers/search`

Example:

```bash
curl "http://localhost:8000/papers/search?q=cat:cs.AI+AND+all:%22graph+neural+networks%22&max_results=5"
```

`POST /papers/discover`

Example:

```bash
curl -X POST "http://localhost:8000/papers/discover" \
  -H "content-type: application/json" \
  -d '{
    "topic": "graph neural networks for drug discovery",
    "categories": ["cs.LG", "q-bio.QM"],
    "include_terms": ["molecular property prediction"],
    "exclude_terms": ["survey"],
    "max_results": 5,
    "min_fit_score": 2.0,
    "include_rejected": true
  }'
```

This endpoint:

1. `search_agent` turns the topic into an arXiv query and fetches candidate papers
2. `review_agent` scores each candidate against the topic and decides whether it fits
3. `summary_agent` reads accepted papers and produces 5 to 10 bullet points
4. `sanity_agent` validates the query, review ordering, and summary coverage
5. returns accepted papers by default, with optional rejected papers, workflow trace, and sanity report

`POST /papers/upload`

Upload PDFs or Zotero RDF exports, score them against a topic, summarize accepted papers, and return the same review structure used by `/papers/discover`.

`POST /papers/upload/organize`

Upload PDFs or Zotero RDF exports, skip topic scoring, summarize every reference, and prepare the full set for export.

`POST /papers/zotero`

Fetch items from a Zotero personal library using a username and API key, then review and summarize them against a topic.

`POST /papers/zotero/jobs`

Create an asynchronous Zotero import job for longer library reads.

`GET /papers/zotero/jobs/{job_id}`

Poll job status, progress, and final results for an asynchronous Zotero import.

`POST /exports/ris`

Export selected reviewed papers as an RIS bibliography file.

`POST /exports/xlsx`

Export selected reviewed papers as an Excel workbook.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for Swagger UI.
Open `http://localhost:8000/` for the web app search bar.

## Environment

Copy `.env.example` to `.env` and set:

- `OPENAI_API_KEY` for your API key
- `OPENAI_MODEL` for a shared default model
- `OPENAI_SEARCH_MODEL` if you want a different model for the search agent
- `OPENAI_REVIEW_MODEL` if you want a different model for the reviewer agent
- `OPENAI_SUMMARY_MODEL` if you want a different model for the summary agent
- `PAPER_TEXT_CHUNK_CHARS` to control summarization chunk size
- `PAPER_TEXT_MAX_CHARS` to limit extracted PDF text length

## LangGraph design

- Graph orchestration lives in `app/services/graph.py`
- arXiv retrieval lives in `app/services/arxiv.py`
- fit scoring and reviewer notes live in `app/services/ranking.py`
- uploaded-file ingestion lives in `app/services/upload_discovery.py`
- Zotero API ingestion lives in `app/services/zotero_api.py`
- sanity auditing lives in `app/services/sanity.py`

The arXiv workflow currently has four stages:

- the search agent builds a structured arXiv query from topic and constraints
- the reviewer agent accepts or rejects papers using lexical relevance scoring
- the summary agent reads extracted paper text and produces 5 to 10 bullets
- the sanity agent checks that query construction, ranking order, and summaries are internally consistent

When `OPENAI_API_KEY` is set, the agents upgrade to LangChain-backed OpenAI calls:

- the search agent uses `ChatOpenAI` to plan a tighter arXiv query
- the reviewer agent uses `ChatOpenAI` to score and justify paper fit
- the summary agent reads extracted PDF text and produces 5 to 10 bullet points
- the sanity agent remains deterministic and audits the full workflow output
- if an OpenAI call fails, the workflow falls back to the deterministic path for that step

The summary agent pulls the arXiv PDF, extracts text, chunks long papers, summarizes each chunk, and then consolidates that into the final bullets.

The upload and Zotero flows reuse the same review, summary, and sanity patterns after they extract candidate paper text.

If you want a stronger reviewer, the clean extension point is `app/services/ranking.py`. You can replace that with:

- embedding similarity
- an LLM-based reranker
- a workflow that expands a seed paper into citation-neighbor searches
