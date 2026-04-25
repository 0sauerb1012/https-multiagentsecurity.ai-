"""CLI entrypoint for local batch ingestion into SQLite."""

from __future__ import annotations

import argparse
import asyncio

from .research_hub import ResearchHubService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-ingest and persist multi-agent security papers locally.")
    parser.add_argument(
        "--target-limit",
        type=int,
        default=1000,
        help="Maximum number of relevant canonical papers to classify and store.",
    )
    parser.add_argument(
        "--per-topic-limit",
        type=int,
        default=60,
        help="Candidate papers to request per topic per source before merge/dedupe.",
    )
    parser.add_argument(
        "--years-back",
        type=int,
        default=5,
        help="Only keep papers published within the last N years.",
    )
    return parser.parse_args()


async def _main() -> None:
    args = parse_args()
    service = ResearchHubService()
    result = await service.ingest_and_store(
        target_limit=args.target_limit,
        per_topic_limit=args.per_topic_limit,
        years_back=args.years_back,
    )
    print("Batch ingestion completed.")
    for key, value in result.items():
        print(f"{key}: {value}")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
