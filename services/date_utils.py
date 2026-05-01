"""Utilities for normalizing publication dates across sources."""

from __future__ import annotations

from datetime import datetime, timezone
import re


YEAR_ONLY_RE = re.compile(r"^\d{4}$")
YEAR_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")


def normalize_publication_date(value: str, *, now: datetime | None = None) -> str:
    """Normalize publication dates and strip impossible future precision.

    If the source date is in the future, keep only the current UTC year so the
    record can still be shown without presenting a false precise date.
    """

    if not value:
        return value

    text = value.strip()
    current = now or datetime.now(timezone.utc)
    parsed = parse_publication_datetime(text, now=current, normalize_future=False)
    if parsed is not None and parsed > current:
        return str(current.year)

    match = re.match(r"^(\d{4})(.*)$", text)
    if not match:
        return text

    year = int(match.group(1))
    current_year = current.year
    if year <= current_year:
        return text
    return str(current_year)


def clamp_future_year(value: str) -> str:
    """Backward-compatible wrapper for publication-date normalization."""

    return normalize_publication_date(value)


def parse_publication_datetime(
    value: str,
    *,
    now: datetime | None = None,
    normalize_future: bool = True,
) -> datetime | None:
    """Parse a publication date into a timezone-aware UTC datetime when possible."""

    if not value:
        return None

    text = normalize_publication_date(value, now=now) if normalize_future else value.strip()
    if not text:
        return None

    if YEAR_ONLY_RE.fullmatch(text):
        return datetime(int(text), 1, 1, tzinfo=timezone.utc)

    year_month_match = YEAR_MONTH_RE.fullmatch(text)
    if year_month_match:
        return datetime(int(year_month_match.group(1)), int(year_month_match.group(2)), 1, tzinfo=timezone.utc)

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_publication_date(value: str) -> str:
    normalized = normalize_publication_date(value)
    if not normalized:
        return "Unknown date"
    if YEAR_ONLY_RE.fullmatch(normalized):
        return f"{normalized} (date unknown)"
    return normalized[:10]


def has_known_publication_date(value: str) -> bool:
    normalized = normalize_publication_date(value)
    if not normalized:
        return False
    return not YEAR_ONLY_RE.fullmatch(normalized)
