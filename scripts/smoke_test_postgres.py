from __future__ import annotations

import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("DATABASE_BACKEND", "postgres")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://researchhub_admin:researchhub_dev@localhost:5432/researchhub",
)

from services.database import DatabaseService


def main() -> int:
    database = DatabaseService()
    database.initialize()

    run = database.start_run(mode="incremental", notes="local postgres smoke test")
    database.finish_run(
        run.run_id,
        status="success",
        fetched_count=0,
        merged_count=0,
        relevant_count=0,
        notes="local postgres smoke test completed",
    )
    database.write_source_sync_state(
        source_name="arxiv",
        last_successful_run_at="2026-04-25T12:00:00+00:00",
        high_watermark_published_at="2026-04-24T00:00:00+00:00",
        high_watermark_source_id="test-arxiv-id",
        notes="local postgres smoke test",
    )

    sync_state = database.read_source_sync_state("arxiv")
    latest_run = database.latest_run()

    if sync_state is None:
        raise RuntimeError("Expected source sync state to exist after write.")
    if latest_run is None:
        raise RuntimeError("Expected latest ingestion run to exist after write.")
    if latest_run.status != "success":
        raise RuntimeError(f"Expected latest run status 'success', got '{latest_run.status}'.")

    print("Postgres smoke test passed.")
    print(f"Latest run id: {latest_run.run_id}")
    print(f"Latest run mode: {latest_run.mode}")
    print(f"Sync watermark source: {sync_state.source_name}")
    print(f"Sync watermark published_at: {sync_state.high_watermark_published_at}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
