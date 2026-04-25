"""CLI entrypoint for local and production batch ingestion."""

from __future__ import annotations

import argparse
import asyncio

from .research_hub import ResearchHubService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-ingest and persist multi-agent security papers locally.")
    parser.add_argument(
        "--mode",
        choices=("seed", "incremental", "reconcile"),
        default="incremental",
        help="Run a one-time seed import, a daily incremental sync, or a wider reconcile pass.",
    )
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
    parser.add_argument(
        "--overlap-days",
        type=int,
        default=3,
        help="Incremental overlap window to catch late-indexed records.",
    )
    parser.add_argument(
        "--reconcile-lookback-days",
        type=int,
        default=30,
        help="Wider lookback window used during reconcile runs.",
    )
    return parser.parse_args()


async def _main() -> None:
    args = parse_args()
    service = ResearchHubService()
    result = await service.ingest_and_store(
        mode=args.mode,
        target_limit=args.target_limit,
        per_topic_limit=args.per_topic_limit,
        years_back=args.years_back,
        overlap_days=args.overlap_days,
        reconcile_lookback_days=args.reconcile_lookback_days,
    )
    print(f"{args.mode.capitalize()} ingestion completed.")
    for key, value in result.items():
        print(f"{key}: {value}")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
