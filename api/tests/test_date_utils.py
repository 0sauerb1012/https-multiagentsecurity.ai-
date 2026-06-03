from datetime import datetime, timezone

from services.date_utils import (
    format_publication_date,
    has_known_publication_date,
    normalize_publication_date,
    parse_publication_datetime,
)


def test_normalize_future_publication_date_strips_to_current_year() -> None:
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)

    assert normalize_publication_date("2026-08-27", now=now) == "2026"
    assert normalize_publication_date("2027-02-01T12:30:00Z", now=now) == "2026"


def test_normalize_keeps_non_future_publication_dates() -> None:
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)

    assert normalize_publication_date("2026-04-27", now=now) == "2026-04-27"
    assert normalize_publication_date("2024-11-15T08:00:00Z", now=now) == "2024-11-15T08:00:00Z"


def test_parse_year_only_publication_date_uses_january_first() -> None:
    parsed = parse_publication_datetime("2026")

    assert parsed == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_format_publication_date_marks_year_only_values_as_unknown() -> None:
    assert format_publication_date("2026") == "2026 (date unknown)"
    assert format_publication_date("2026-04-27") == "2026-04-27"


def test_year_only_publication_dates_are_treated_as_unknown() -> None:
    assert has_known_publication_date("2026") is False
    assert has_known_publication_date("2026-04-27") is True
