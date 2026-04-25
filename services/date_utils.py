"""Utilities for normalizing publication dates across sources."""

from __future__ import annotations

from datetime import datetime, timezone
import re


def clamp_future_year(value: str) -> str:
    """Prevent source data from producing impossible future publication years.

    If the year prefix is later than the current UTC year, rewrite only the year
    portion to the current year and preserve the remaining date/time suffix.
    """

    if not value:
        return value

    match = re.match(r"^(\d{4})(.*)$", value.strip())
    if not match:
        return value

    year = int(match.group(1))
    suffix = match.group(2)
    current_year = datetime.now(timezone.utc).year
    if year <= current_year:
        return value
    return f"{current_year}{suffix}"
