# Ingestion Service

This service provides the ingestion and enrichment scaffold for `multiagentsecurity.ai`.

## Design Goals

- Lambda-friendly Python entrypoint
- Source adapters isolated by upstream system
- Explicit normalization, dedupe, and tagging steps
- Small surface area with clear TODOs for real implementation

## Current Status

Implemented:

- Importable package structure under `src/`
- `handler.py` Lambda entrypoint
- Placeholder adapters for arXiv, Crossref, and RSS
- Common article dataclass
- Pipeline stages for normalization, dedupe, and taxonomy tagging

Not implemented yet:

- Live API integrations and retry logic
- Persistent database writes
- Rate limiting, metrics, and alerting
- Full test coverage

## Commands

- `pip install -r requirements.txt`
- `pytest`
- `python -m compileall src`
