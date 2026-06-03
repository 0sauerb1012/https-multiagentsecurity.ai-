from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import TYPE_CHECKING

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.database import DatabaseService

if TYPE_CHECKING:
    import psycopg


EXPECTED_HEADERS = [
    "canonical_id",
    "title",
    "summary",
    "published",
    "updated",
    "authors_json",
    "categories_json",
    "hub_categories_json",
    "primary_category",
    "doi",
    "arxiv_id",
    "venue",
    "source_name",
    "source_type",
    "merged_from_sources_json",
    "source_records_json",
    "paper_url",
    "pdf_url",
    "relevance_score",
    "rationale",
    "is_fit",
    "fit_score",
    "reviewer_notes",
    "classification_confidence",
    "classification_notes",
    "key_points_summary_json",
    "ingestion_mode",
    "first_seen_at",
    "last_seen_at",
    "ingested_at",
    "run_id",
]

JSON_COLUMNS = {
    "authors_json",
    "categories_json",
    "hub_categories_json",
    "merged_from_sources_json",
    "source_records_json",
    "key_points_summary_json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import papers from a CSV file into PostgreSQL.")
    parser.add_argument("csv_path", type=Path, help="Path to the papers CSV export.")
    parser.add_argument(
        "--database-url",
        default="",
        help="Override DATABASE_URL. Defaults to the environment variable used by the app.",
    )
    parser.add_argument(
        "--clear-papers",
        action="store_true",
        help="Delete existing rows from papers before import.",
    )
    return parser.parse_args()


def _as_nullable_text(value: str) -> str | None:
    return value if value != "" else None


def _as_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ValueError(f"Unsupported boolean value: {value!r}")


def _as_nullable_float(value: str) -> float | None:
    return float(value) if value != "" else None


def _as_nullable_int(value: str) -> int | None:
    return int(value) if value != "" else None


def _normalize_json(value: str, *, column_name: str) -> str:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {column_name}: {exc}") from exc
    return json.dumps(parsed, ensure_ascii=True)


def _normalize_row(row: dict[str, str]) -> dict[str, object]:
    for column_name in JSON_COLUMNS:
        row[column_name] = _normalize_json(row[column_name], column_name=column_name)

    return {
        "canonical_id": row["canonical_id"],
        "title": row["title"],
        "summary": row["summary"],
        "published": row["published"],
        "updated": row["updated"],
        "authors_json": row["authors_json"],
        "categories_json": row["categories_json"],
        "hub_categories_json": row["hub_categories_json"],
        "primary_category": _as_nullable_text(row["primary_category"]),
        "doi": _as_nullable_text(row["doi"]),
        "arxiv_id": _as_nullable_text(row["arxiv_id"]),
        "venue": _as_nullable_text(row["venue"]),
        "source_name": row["source_name"],
        "source_type": row["source_type"],
        "merged_from_sources_json": row["merged_from_sources_json"],
        "source_records_json": row["source_records_json"],
        "paper_url": row["paper_url"],
        "pdf_url": _as_nullable_text(row["pdf_url"]),
        "relevance_score": float(row["relevance_score"]),
        "rationale": row["rationale"],
        "is_fit": _as_bool(row["is_fit"]),
        "fit_score": float(row["fit_score"]),
        "reviewer_notes": row["reviewer_notes"],
        "classification_confidence": _as_nullable_float(row["classification_confidence"]),
        "classification_notes": _as_nullable_text(row["classification_notes"]),
        "key_points_summary_json": row["key_points_summary_json"],
        "ingestion_mode": row["ingestion_mode"] or "seed",
        "first_seen_at": _as_nullable_text(row["first_seen_at"]),
        "last_seen_at": _as_nullable_text(row["last_seen_at"]),
        "ingested_at": row["ingested_at"],
        "run_id": _as_nullable_int(row["run_id"]),
    }


def _load_rows(csv_path: Path) -> list[dict[str, object]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_HEADERS:
            raise ValueError(
                "Unexpected CSV headers.\n"
                f"Expected: {EXPECTED_HEADERS}\n"
                f"Actual:   {reader.fieldnames}"
            )
        return [_normalize_row(row) for row in reader]


def _ensure_ingestion_runs(connection, rows: list[dict[str, object]]) -> None:
    runs: dict[int, str] = {}
    for row in rows:
        run_id = row["run_id"]
        ingested_at = row["ingested_at"]
        if isinstance(run_id, int):
            previous = runs.get(run_id)
            if previous is None or ingested_at < previous:
                runs[run_id] = str(ingested_at)

    if not runs:
        return

    payload = [
        {
            "run_id": run_id,
            "status": "imported",
            "started_at": started_at,
            "completed_at": started_at,
            "mode": "csv_import",
            "notes": "Backfilled from papers.csv import",
        }
        for run_id, started_at in sorted(runs.items())
    ]

    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO ingestion_runs (
                run_id, status, started_at, mode, completed_at, fetched_count,
                merged_count, relevant_count, notes
            )
            VALUES (
                %(run_id)s, %(status)s, %(started_at)s, %(mode)s, %(completed_at)s, 0,
                0, 0, %(notes)s
            )
            ON CONFLICT (run_id) DO NOTHING
            """,
            payload,
        )


def _upsert_papers(connection, rows: list[dict[str, object]]) -> None:
    statement = """
        INSERT INTO papers (
            canonical_id, title, summary, published, updated, authors_json, categories_json,
            hub_categories_json, primary_category, doi, arxiv_id, venue, source_name, source_type,
            merged_from_sources_json, source_records_json, paper_url, pdf_url, relevance_score,
            rationale, is_fit, fit_score, reviewer_notes, classification_confidence,
            classification_notes, key_points_summary_json, ingestion_mode, first_seen_at,
            last_seen_at, ingested_at, run_id
        )
        VALUES (
            %(canonical_id)s, %(title)s, %(summary)s, %(published)s, %(updated)s, %(authors_json)s,
            %(categories_json)s, %(hub_categories_json)s, %(primary_category)s, %(doi)s, %(arxiv_id)s,
            %(venue)s, %(source_name)s, %(source_type)s, %(merged_from_sources_json)s,
            %(source_records_json)s, %(paper_url)s, %(pdf_url)s, %(relevance_score)s, %(rationale)s,
            %(is_fit)s, %(fit_score)s, %(reviewer_notes)s, %(classification_confidence)s,
            %(classification_notes)s, %(key_points_summary_json)s, %(ingestion_mode)s,
            %(first_seen_at)s, %(last_seen_at)s, %(ingested_at)s, %(run_id)s
        )
        ON CONFLICT (canonical_id) DO UPDATE SET
            title = EXCLUDED.title,
            summary = EXCLUDED.summary,
            published = EXCLUDED.published,
            updated = EXCLUDED.updated,
            authors_json = EXCLUDED.authors_json,
            categories_json = EXCLUDED.categories_json,
            hub_categories_json = EXCLUDED.hub_categories_json,
            primary_category = EXCLUDED.primary_category,
            doi = EXCLUDED.doi,
            arxiv_id = EXCLUDED.arxiv_id,
            venue = EXCLUDED.venue,
            source_name = EXCLUDED.source_name,
            source_type = EXCLUDED.source_type,
            merged_from_sources_json = EXCLUDED.merged_from_sources_json,
            source_records_json = EXCLUDED.source_records_json,
            paper_url = EXCLUDED.paper_url,
            pdf_url = EXCLUDED.pdf_url,
            relevance_score = EXCLUDED.relevance_score,
            rationale = EXCLUDED.rationale,
            is_fit = EXCLUDED.is_fit,
            fit_score = EXCLUDED.fit_score,
            reviewer_notes = EXCLUDED.reviewer_notes,
            classification_confidence = EXCLUDED.classification_confidence,
            classification_notes = EXCLUDED.classification_notes,
            key_points_summary_json = EXCLUDED.key_points_summary_json,
            ingestion_mode = EXCLUDED.ingestion_mode,
            first_seen_at = COALESCE(papers.first_seen_at, EXCLUDED.first_seen_at),
            last_seen_at = EXCLUDED.last_seen_at,
            ingested_at = EXCLUDED.ingested_at,
            run_id = EXCLUDED.run_id
    """

    with connection.cursor() as cursor:
        cursor.executemany(statement, rows)


def main() -> None:
    import psycopg

    args = parse_args()
    csv_path = args.csv_path
    if not csv_path.exists():
        raise SystemExit(f"CSV file not found: {csv_path}")

    database = DatabaseService()
    database.initialize()
    database_url = args.database_url or database.database_url
    if not database_url:
        raise SystemExit("DATABASE_URL is not set. Export it or pass --database-url.")

    rows = _load_rows(csv_path)
    imported_at = datetime.now(timezone.utc).isoformat()

    with psycopg.connect(database_url) as connection:
        if args.clear_papers:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM papers")
        _ensure_ingestion_runs(connection, rows)
        _upsert_papers(connection, rows)
        connection.commit()

    print(f"Imported {len(rows)} papers from {csv_path} at {imported_at}")


if __name__ == "__main__":
    main()
