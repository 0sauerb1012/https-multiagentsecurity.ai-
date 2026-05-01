"""Persistence service for SQLite (local) and PostgreSQL (AWS)."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from api.app.config import settings
from api.app.models import ReviewedPaper, SourceRecord

from .date_utils import clamp_future_year, has_known_publication_date, parse_publication_datetime
from .hub_types import HeatmapRow, LibraryCategoryGroup, PaperCard

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - optional dependency for local SQLite-only use
    psycopg = None
    dict_row = None


@dataclass(frozen=True)
class IngestionRun:
    run_id: int
    status: str
    started_at: str
    mode: str = "seed"
    completed_at: str | None = None
    fetched_count: int = 0
    merged_count: int = 0
    relevant_count: int = 0
    notes: str | None = None


@dataclass(frozen=True)
class SourceSyncState:
    source_name: str
    last_successful_run_at: str | None = None
    high_watermark_published_at: str | None = None
    high_watermark_source_id: str | None = None
    notes: str | None = None


class DatabaseService:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path or settings.database_path)
        configured_backend = settings.database_backend.strip().lower()
        self.database_url = settings.database_url
        if configured_backend == "sqlite" and self.database_url and self.database_url.startswith("postgres"):
            configured_backend = "postgres"
        self.backend = configured_backend

    def initialize(self) -> None:
        if self.backend == "postgres":
            self._initialize_postgres()
            return
        self._initialize_sqlite()

    def start_run(self, *, mode: str = "seed", notes: str | None = None) -> IngestionRun:
        self.initialize()
        started_at = self._now()
        with self._connect() as connection:
            row = connection.execute(
                self._sql(
                    """
                    INSERT INTO ingestion_runs (status, started_at, mode, notes)
                    VALUES (?, ?, ?, ?)
                    RETURNING run_id
                    """
                ),
                ("running", started_at, mode, notes),
            ).fetchone()
        return IngestionRun(
            run_id=int(self._value(row, "run_id")),
            status="running",
            started_at=started_at,
            mode=mode,
            notes=notes,
        )

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
                self._sql(
                    """
                    UPDATE ingestion_runs
                    SET status = ?, completed_at = ?, fetched_count = ?, merged_count = ?, relevant_count = ?, notes = ?
                    WHERE run_id = ?
                    """
                ),
                (status, self._now(), fetched_count, merged_count, relevant_count, notes, run_id),
            )

    def save_cards(
        self,
        cards: list[PaperCard],
        *,
        run_id: int | None = None,
        ingestion_mode: str = "seed",
    ) -> None:
        self.initialize()
        ingested_at = self._now()
        with self._connect() as connection:
            for card in cards:
                paper = card.paper
                connection.execute(
                    self._sql(
                        """
                        INSERT INTO papers (
                            canonical_id, title, summary, published, updated, authors_json, categories_json,
                            hub_categories_json, primary_category, doi, arxiv_id, venue, source_name, source_type,
                            merged_from_sources_json, source_records_json, paper_url, pdf_url, relevance_score,
                            rationale, is_fit, fit_score, reviewer_notes, classification_confidence,
                            classification_notes, key_points_summary_json, ingestion_mode, first_seen_at,
                            last_seen_at, ingested_at, run_id
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            ingestion_mode = excluded.ingestion_mode,
                            first_seen_at = COALESCE(papers.first_seen_at, excluded.first_seen_at),
                            last_seen_at = excluded.last_seen_at,
                            ingested_at = excluded.ingested_at,
                            run_id = excluded.run_id
                        """
                    ),
                    (
                        paper.canonical_id or paper.id,
                        paper.title,
                        paper.summary,
                        clamp_future_year(paper.published),
                        clamp_future_year(paper.updated),
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
                        bool(paper.is_fit) if self.backend == "postgres" else (1 if paper.is_fit else 0),
                        paper.fit_score,
                        paper.reviewer_notes,
                        paper.classification_confidence,
                        paper.classification_notes,
                        self._dump_json(card.bullets),
                        ingestion_mode,
                        ingested_at,
                        ingested_at,
                        ingested_at,
                        run_id,
                    ),
                )

    def known_canonical_ids(self, identifiers: list[str]) -> set[str]:
        self.initialize()
        clean = [identifier for identifier in identifiers if identifier]
        if not clean:
            return set()
        placeholders = ", ".join(self._placeholder() for _ in clean)
        with self._connect() as connection:
            rows = connection.execute(
                self._sql(f"SELECT canonical_id FROM papers WHERE canonical_id IN ({placeholders})"),
                tuple(clean),
            ).fetchall()
        return {self._value(row, "canonical_id") for row in rows}

    def read_source_sync_state(self, source_name: str) -> SourceSyncState | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                self._sql(
                    """
                    SELECT source_name, last_successful_run_at, high_watermark_published_at, high_watermark_source_id, notes
                    FROM source_sync_state
                    WHERE source_name = ?
                    LIMIT 1
                    """
                ),
                (source_name,),
            ).fetchone()
        if row is None:
            return None
        return SourceSyncState(
            source_name=self._value(row, "source_name"),
            last_successful_run_at=self._value(row, "last_successful_run_at"),
            high_watermark_published_at=self._value(row, "high_watermark_published_at"),
            high_watermark_source_id=self._value(row, "high_watermark_source_id"),
            notes=self._value(row, "notes"),
        )

    def write_source_sync_state(
        self,
        *,
        source_name: str,
        last_successful_run_at: str,
        high_watermark_published_at: str | None = None,
        high_watermark_source_id: str | None = None,
        notes: str | None = None,
    ) -> None:
        self.initialize()
        existing = self.read_source_sync_state(source_name)
        with self._connect() as connection:
            connection.execute(
                self._sql(
                    """
                    INSERT INTO source_sync_state (
                        source_name, last_successful_run_at, high_watermark_published_at, high_watermark_source_id, notes
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(source_name) DO UPDATE SET
                        last_successful_run_at = excluded.last_successful_run_at,
                        high_watermark_published_at = COALESCE(excluded.high_watermark_published_at, source_sync_state.high_watermark_published_at),
                        high_watermark_source_id = COALESCE(excluded.high_watermark_source_id, source_sync_state.high_watermark_source_id),
                        notes = excluded.notes
                    """
                ),
                (
                    source_name,
                    last_successful_run_at,
                    high_watermark_published_at or (existing.high_watermark_published_at if existing else None),
                    high_watermark_source_id or (existing.high_watermark_source_id if existing else None),
                    notes,
                ),
            )

    def has_persisted_papers(self) -> bool:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM papers WHERE {self._is_fit_true_clause()}"
            ).fetchone()
        return bool(row and self._value(row, "count"))

    def load_cards(self, *, limit: int | None = None) -> list[PaperCard]:
        self.initialize()
        query = """
            SELECT * FROM papers
            WHERE {is_fit_true_clause}
        """
        query = query.format(is_fit_true_clause=self._is_fit_true_clause())
        with self._connect() as connection:
            rows = connection.execute(self._sql(query)).fetchall()
        cards = [self._row_to_card(row) for row in rows]
        cards.sort(
            key=lambda card: (
                has_known_publication_date(card.paper.published),
                parse_publication_datetime(card.paper.published) or datetime.min.replace(tzinfo=timezone.utc),
                card.paper.fit_score,
            ),
            reverse=True,
        )
        if limit is not None:
            return cards[:limit]
        return cards

    def load_cards_by_source(self, *, source_filter: str, limit: int | None = None) -> list[PaperCard]:
        cards = self.load_cards()
        normalized_filter = source_filter.strip().lower()
        matching = [card for card in cards if normalized_filter in self._source_keys_for_card(card)]
        if limit is not None:
            return matching[:limit]
        return matching

    def load_available_sources(self) -> list[str]:
        cards = self.load_cards()
        sources: set[str] = set()
        for card in cards:
            sources.update(self._source_keys_for_card(card))
        return sorted(sources)

    def load_card_by_canonical_id(self, canonical_id: str) -> PaperCard | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                self._sql(
                    """
                    SELECT * FROM papers
                    WHERE canonical_id = ? AND {is_fit_true_clause}
                    LIMIT 1
                    """
                    .format(is_fit_true_clause=self._is_fit_true_clause())
                ),
                (canonical_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_card(row)

    def load_area_cards(self, *, area_slug: str, limit: int | None = None) -> tuple[str, list[PaperCard]]:
        cards = self.load_cards()
        for group in self.load_library_groups():
            if group.slug == area_slug:
                matching = [card for card in cards if group.category in card.paper.hub_categories]
                if limit is not None:
                    matching = matching[:limit]
                return group.category, matching
        raise ValueError("Unknown research area.")

    def load_library_groups(self) -> list[LibraryCategoryGroup]:
        cards = self.load_cards()
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

    def load_heatmap_rows(self) -> tuple[list[HeatmapRow], list[str], list[str]]:
        cards = self.load_cards()
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
                SELECT run_id, status, started_at, mode, completed_at, fetched_count, merged_count, relevant_count, notes
                FROM ingestion_runs
                ORDER BY started_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return IngestionRun(
            run_id=int(self._value(row, "run_id")),
            status=self._value(row, "status"),
            started_at=self._value(row, "started_at"),
            mode=self._value(row, "mode"),
            completed_at=self._value(row, "completed_at"),
            fetched_count=int(self._value(row, "fetched_count")),
            merged_count=int(self._value(row, "merged_count")),
            relevant_count=int(self._value(row, "relevant_count")),
            notes=self._value(row, "notes"),
        )

    def _row_to_card(self, row) -> PaperCard:
        paper = ReviewedPaper(
            id=self._value(row, "canonical_id"),
            canonical_id=self._value(row, "canonical_id"),
            title=self._value(row, "title"),
            summary=self._value(row, "summary"),
            published=clamp_future_year(self._value(row, "published")),
            updated=clamp_future_year(self._value(row, "updated")),
            authors=self._load_json(self._value(row, "authors_json")),
            categories=self._load_json(self._value(row, "categories_json")),
            hub_categories=self._load_json(self._value(row, "hub_categories_json")),
            primary_category=self._value(row, "primary_category"),
            doi=self._value(row, "doi"),
            arxiv_id=self._value(row, "arxiv_id"),
            venue=self._value(row, "venue"),
            source_name=self._value(row, "source_name"),
            source_type=self._value(row, "source_type"),
            merged_from_sources=self._load_json(self._value(row, "merged_from_sources_json")),
            source_records=[
                SourceRecord.model_validate(item)
                for item in self._load_json(self._value(row, "source_records_json"))
            ],
            paper_url=self._value(row, "paper_url"),
            pdf_url=self._value(row, "pdf_url"),
            relevance_score=float(self._value(row, "relevance_score")),
            rationale=self._value(row, "rationale"),
            is_fit=bool(self._value(row, "is_fit")),
            fit_score=float(self._value(row, "fit_score")),
            reviewer_notes=self._value(row, "reviewer_notes"),
            classification_confidence=self._value(row, "classification_confidence"),
            classification_notes=self._value(row, "classification_notes"),
            key_points_summary=self._load_json(self._value(row, "key_points_summary_json")),
        )
        return PaperCard(paper=paper, bullets=self._load_json(self._value(row, "key_points_summary_json")))

    def _initialize_sqlite(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(self._sqlite_schema())
            self._ensure_sqlite_column(connection, "ingestion_runs", "mode", "TEXT NOT NULL DEFAULT 'seed'")
            self._ensure_sqlite_column(connection, "papers", "ingestion_mode", "TEXT NOT NULL DEFAULT 'seed'")
            self._ensure_sqlite_column(connection, "papers", "first_seen_at", "TEXT")
            self._ensure_sqlite_column(connection, "papers", "last_seen_at", "TEXT")

    def _initialize_postgres(self) -> None:
        with self._connect() as connection:
            for statement in self._postgres_schema_statements():
                connection.execute(statement)

    @contextmanager
    def _connect(self) -> Iterator:
        if self.backend == "postgres":
            if psycopg is None or dict_row is None:
                raise RuntimeError("DATABASE_BACKEND=postgres requires psycopg to be installed.")
            if not self.database_url:
                raise RuntimeError("DATABASE_URL must be set when DATABASE_BACKEND=postgres.")
            connection = psycopg.connect(self.database_url, row_factory=dict_row)
        else:
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _sqlite_schema() -> str:
        return """
        CREATE TABLE IF NOT EXISTS ingestion_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'seed',
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
            ingestion_mode TEXT NOT NULL DEFAULT 'seed',
            first_seen_at TEXT,
            last_seen_at TEXT,
            ingested_at TEXT NOT NULL,
            run_id INTEGER,
            FOREIGN KEY (run_id) REFERENCES ingestion_runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS source_sync_state (
            source_name TEXT PRIMARY KEY,
            last_successful_run_at TEXT,
            high_watermark_published_at TEXT,
            high_watermark_source_id TEXT,
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published DESC);
        CREATE INDEX IF NOT EXISTS idx_runs_started_at ON ingestion_runs(started_at DESC);
        """

    @staticmethod
    def _postgres_schema_statements() -> list[str]:
        return [
            """
            CREATE TABLE IF NOT EXISTS ingestion_runs (
                run_id BIGSERIAL PRIMARY KEY,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                mode TEXT NOT NULL DEFAULT 'seed',
                completed_at TEXT,
                fetched_count INTEGER NOT NULL DEFAULT 0,
                merged_count INTEGER NOT NULL DEFAULT 0,
                relevant_count INTEGER NOT NULL DEFAULT 0,
                notes TEXT
            )
            """,
            """
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
                relevance_score DOUBLE PRECISION NOT NULL,
                rationale TEXT NOT NULL,
                is_fit BOOLEAN NOT NULL,
                fit_score DOUBLE PRECISION NOT NULL,
                reviewer_notes TEXT NOT NULL,
                classification_confidence DOUBLE PRECISION,
                classification_notes TEXT,
                key_points_summary_json TEXT NOT NULL,
                ingestion_mode TEXT NOT NULL DEFAULT 'seed',
                first_seen_at TEXT,
                last_seen_at TEXT,
                ingested_at TEXT NOT NULL,
                run_id BIGINT REFERENCES ingestion_runs(run_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS source_sync_state (
                source_name TEXT PRIMARY KEY,
                last_successful_run_at TEXT,
                high_watermark_published_at TEXT,
                high_watermark_source_id TEXT,
                notes TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published DESC)",
            "CREATE INDEX IF NOT EXISTS idx_runs_started_at ON ingestion_runs(started_at DESC)",
        ]

    @staticmethod
    def _ensure_sqlite_column(connection: sqlite3.Connection, table_name: str, column_name: str, column_sql: str) -> None:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {row[1] for row in rows}
        if column_name in existing:
            return
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")

    def _sql(self, query: str) -> str:
        if self.backend == "postgres":
            return query.replace("?", "%s")
        return query

    def _placeholder(self) -> str:
        return "%s" if self.backend == "postgres" else "?"

    def _is_fit_true_clause(self) -> str:
        return "is_fit = TRUE" if self.backend == "postgres" else "is_fit = 1"

    @staticmethod
    def _value(row, key: str):
        if row is None:
            return None
        return row[key]

    @staticmethod
    def _dump_json(value: object) -> str:
        return json.dumps(value, ensure_ascii=True)

    @staticmethod
    def _load_json(value: str | None) -> list:
        return json.loads(value or "[]")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def slugify_category(category: str) -> str:
        return category.strip().lower().replace("&", "and").replace("/", "-").replace(" ", "-")

    @staticmethod
    def _source_keys_for_card(card: PaperCard) -> set[str]:
        sources: set[str] = set()
        if card.paper.source_name:
            sources.add(card.paper.source_name.split("·")[0].strip().lower())
        for source in card.paper.merged_from_sources:
            if source:
                sources.add(source.strip().lower())
        return sources
