"""Local SQLite persistence for the research hub."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from api.app.config import settings
from api.app.models import ReviewedPaper, SourceRecord

from .research_hub import HeatmapRow, LibraryCategoryGroup, PaperCard


@dataclass(frozen=True)
class IngestionRun:
    run_id: int
    status: str
    started_at: str
    completed_at: str | None = None
    fetched_count: int = 0
    merged_count: int = 0
    relevant_count: int = 0
    notes: str | None = None


class DatabaseService:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path or settings.database_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    fetched_count INTEGER NOT NULL DEFAULT 0,
                    merged_count INTEGER NOT NULL DEFAULT 0,
                    relevant_count INTEGER NOT NULL DEFAULT 0,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS papers (
                    canonical_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    published TEXT NOT NULL,
                    updated TEXT NOT NULL,
                    authors_json TEXT NOT NULL,
                    categories_json TEXT NOT NULL,
                    hub_categories_json TEXT NOT NULL,
                    primary_category TEXT,
                    doi TEXT,
                    arxiv_id TEXT,
                    venue TEXT,
                    source_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    merged_from_sources_json TEXT NOT NULL,
                    source_records_json TEXT NOT NULL,
                    paper_url TEXT NOT NULL,
                    pdf_url TEXT,
                    relevance_score REAL NOT NULL,
                    rationale TEXT NOT NULL,
                    is_fit INTEGER NOT NULL,
                    fit_score REAL NOT NULL,
                    reviewer_notes TEXT NOT NULL,
                    classification_confidence REAL,
                    classification_notes TEXT,
                    key_points_summary_json TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    run_id INTEGER,
                    FOREIGN KEY (run_id) REFERENCES ingestion_runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published DESC);
                CREATE INDEX IF NOT EXISTS idx_runs_started_at ON ingestion_runs(started_at DESC);
                """
            )

    def start_run(self, *, notes: str | None = None) -> IngestionRun:
        self.initialize()
        started_at = self._now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ingestion_runs (status, started_at, notes)
                VALUES (?, ?, ?)
                """,
                ("running", started_at, notes),
            )
            run_id = int(cursor.lastrowid)
        return IngestionRun(run_id=run_id, status="running", started_at=started_at, notes=notes)

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        fetched_count: int,
        merged_count: int,
        relevant_count: int,
        notes: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE ingestion_runs
                SET status = ?, completed_at = ?, fetched_count = ?, merged_count = ?, relevant_count = ?, notes = ?
                WHERE run_id = ?
                """,
                (status, self._now(), fetched_count, merged_count, relevant_count, notes, run_id),
            )

    def save_cards(self, cards: list[PaperCard], *, run_id: int | None = None) -> None:
        self.initialize()
        ingested_at = self._now()
        with self._connect() as connection:
            for card in cards:
                paper = card.paper
                connection.execute(
                    """
                    INSERT INTO papers (
                        canonical_id, title, summary, published, updated, authors_json, categories_json,
                        hub_categories_json, primary_category, doi, arxiv_id, venue, source_name, source_type,
                        merged_from_sources_json, source_records_json, paper_url, pdf_url, relevance_score,
                        rationale, is_fit, fit_score, reviewer_notes, classification_confidence,
                        classification_notes, key_points_summary_json, ingested_at, run_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(canonical_id) DO UPDATE SET
                        title = excluded.title,
                        summary = excluded.summary,
                        published = excluded.published,
                        updated = excluded.updated,
                        authors_json = excluded.authors_json,
                        categories_json = excluded.categories_json,
                        hub_categories_json = excluded.hub_categories_json,
                        primary_category = excluded.primary_category,
                        doi = excluded.doi,
                        arxiv_id = excluded.arxiv_id,
                        venue = excluded.venue,
                        source_name = excluded.source_name,
                        source_type = excluded.source_type,
                        merged_from_sources_json = excluded.merged_from_sources_json,
                        source_records_json = excluded.source_records_json,
                        paper_url = excluded.paper_url,
                        pdf_url = excluded.pdf_url,
                        relevance_score = excluded.relevance_score,
                        rationale = excluded.rationale,
                        is_fit = excluded.is_fit,
                        fit_score = excluded.fit_score,
                        reviewer_notes = excluded.reviewer_notes,
                        classification_confidence = excluded.classification_confidence,
                        classification_notes = excluded.classification_notes,
                        key_points_summary_json = excluded.key_points_summary_json,
                        ingested_at = excluded.ingested_at,
                        run_id = excluded.run_id
                    """,
                    (
                        paper.canonical_id or paper.id,
                        paper.title,
                        paper.summary,
                        paper.published,
                        paper.updated,
                        self._dump_json(paper.authors),
                        self._dump_json(paper.categories),
                        self._dump_json(paper.hub_categories),
                        paper.primary_category,
                        paper.doi,
                        paper.arxiv_id,
                        paper.venue,
                        paper.source_name,
                        paper.source_type,
                        self._dump_json(paper.merged_from_sources),
                        self._dump_json([record.model_dump() for record in paper.source_records]),
                        paper.paper_url,
                        paper.pdf_url,
                        paper.relevance_score,
                        paper.rationale,
                        1 if paper.is_fit else 0,
                        paper.fit_score,
                        paper.reviewer_notes,
                        paper.classification_confidence,
                        paper.classification_notes,
                        self._dump_json(card.bullets),
                        ingested_at,
                        run_id,
                    ),
                )

    def has_persisted_papers(self) -> bool:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM papers WHERE is_fit = 1").fetchone()
        return bool(row and row["count"])

    def load_cards(self, *, limit: int) -> list[PaperCard]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM papers
                WHERE is_fit = 1
                ORDER BY published DESC, fit_score DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_card(row) for row in rows]

    def load_area_cards(self, *, area_slug: str, limit: int) -> tuple[str, list[PaperCard]]:
        cards = self.load_cards(limit=5000)
        for group in self.load_library_groups(limit=5000):
            if group.slug == area_slug:
                matching = [card for card in cards if group.category in card.paper.hub_categories][:limit]
                return group.category, matching
        raise ValueError("Unknown research area.")

    def load_library_groups(self, *, limit: int) -> list[LibraryCategoryGroup]:
        cards = self.load_cards(limit=limit)
        grouped: dict[str, list[PaperCard]] = {}
        for card in cards:
            for category in card.paper.hub_categories:
                grouped.setdefault(category, []).append(card)

        groups: list[LibraryCategoryGroup] = []
        for category, group_cards in grouped.items():
            groups.append(
                LibraryCategoryGroup(
                    slug=self.slugify_category(category),
                    category=category,
                    count=len(group_cards),
                    cards=group_cards[:3],
                )
            )
        groups.sort(key=lambda group: (-group.count, group.category))
        return groups

    def load_heatmap_rows(self, *, limit: int | None = None) -> tuple[list[HeatmapRow], list[str], list[str]]:
        cards = self.load_cards(limit=limit or 5000)
        counts: dict[str, int] = {}
        for card in cards:
            for category in card.paper.hub_categories:
                counts[category] = counts.get(category, 0) + 1

        if not counts:
            return [], [], []

        max_value = max(counts.values()) or 1
        rows: list[HeatmapRow] = []
        for category, count in counts.items():
            intensity = count / max_value if max_value else 0.0
            if count >= max(3, round(max_value * 0.6)):
                status = "High concentration"
            elif count <= 1:
                status = "Gap / underexplored"
            else:
                status = "Emerging / moderate"
            rows.append(
                HeatmapRow(
                    slug=self.slugify_category(category),
                    category=category,
                    count=count,
                    intensity=intensity,
                    status=status,
                )
            )

        rows.sort(key=lambda row: (-row.count, row.category))
        concentration_labels = [row.category for row in rows if row.status == "High concentration"]
        gap_labels = [row.category for row in rows if row.status == "Gap / underexplored"]
        return rows, gap_labels[:3], concentration_labels[:3]

    def latest_run(self) -> IngestionRun | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT run_id, status, started_at, completed_at, fetched_count, merged_count, relevant_count, notes
                FROM ingestion_runs
                ORDER BY started_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return IngestionRun(
            run_id=row["run_id"],
            status=row["status"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            fetched_count=row["fetched_count"],
            merged_count=row["merged_count"],
            relevant_count=row["relevant_count"],
            notes=row["notes"],
        )

    def _row_to_card(self, row: sqlite3.Row) -> PaperCard:
        paper = ReviewedPaper(
            id=row["canonical_id"],
            canonical_id=row["canonical_id"],
            title=row["title"],
            summary=row["summary"],
            published=row["published"],
            updated=row["updated"],
            authors=self._load_json(row["authors_json"]),
            categories=self._load_json(row["categories_json"]),
            hub_categories=self._load_json(row["hub_categories_json"]),
            primary_category=row["primary_category"],
            doi=row["doi"],
            arxiv_id=row["arxiv_id"],
            venue=row["venue"],
            source_name=row["source_name"],
            source_type=row["source_type"],
            merged_from_sources=self._load_json(row["merged_from_sources_json"]),
            source_records=[
                SourceRecord.model_validate(item) for item in self._load_json(row["source_records_json"])
            ],
            paper_url=row["paper_url"],
            pdf_url=row["pdf_url"],
            relevance_score=row["relevance_score"],
            rationale=row["rationale"],
            is_fit=bool(row["is_fit"]),
            fit_score=row["fit_score"],
            reviewer_notes=row["reviewer_notes"],
            classification_confidence=row["classification_confidence"],
            classification_notes=row["classification_notes"],
            key_points_summary=self._load_json(row["key_points_summary_json"]),
        )
        return PaperCard(paper=paper, bullets=self._load_json(row["key_points_summary_json"]))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _dump_json(value: object) -> str:
        return json.dumps(value, ensure_ascii=True)

    @staticmethod
    def _load_json(value: str) -> list:
        return json.loads(value or "[]")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def slugify_category(category: str) -> str:
        return (
            category.strip()
            .lower()
            .replace("&", "and")
            .replace("/", "-")
            .replace(" ", "-")
        )
