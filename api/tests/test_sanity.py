from app.models import ReviewedPaper
from app.services.sanity import SanityCheckService


def build_reviewed_paper(title: str, *, is_fit: bool, fit_score: float, has_summary: bool) -> ReviewedPaper:
    return ReviewedPaper(
        id=title.lower().replace(" ", "-"),
        title=title,
        summary="Relevant summary text.",
        published="2024-01-01T00:00:00Z",
        updated="2024-01-01T00:00:00Z",
        authors=["A. Author"],
        categories=["cs.AI"],
        primary_category="cs.AI",
        paper_url="https://arxiv.org/abs/1234.5678",
        pdf_url="https://arxiv.org/pdf/1234.5678.pdf",
        relevance_score=fit_score,
        rationale="title matches: graph, neural",
        is_fit=is_fit,
        fit_score=fit_score,
        reviewer_notes="deterministic reviewer note",
        key_points_summary=["one", "two", "three", "four", "five"] if has_summary else None,
    )


def test_sanity_check_service_passes_consistent_results() -> None:
    service = SanityCheckService()

    result = service.audit(
        topic="graph neural networks",
        query_used='all:"graph neural networks" AND cat:cs.AI',
        total_candidates=2,
        papers=[
            build_reviewed_paper("Graph Paper", is_fit=True, fit_score=4.0, has_summary=True),
            build_reviewed_paper("Less Relevant Paper", is_fit=False, fit_score=1.0, has_summary=False),
        ],
        requires_query_validation=True,
    )

    assert result.status == "passed"
    assert result.report[0].startswith("Sanity status: passed")


def test_sanity_check_service_flags_summary_mismatch() -> None:
    service = SanityCheckService()

    result = service.audit(
        topic="graph neural networks",
        query_used='all:"graph neural networks"',
        total_candidates=1,
        papers=[
            build_reviewed_paper("Graph Paper", is_fit=True, fit_score=4.0, has_summary=False),
        ],
        requires_query_validation=True,
    )

    assert result.status == "warning"
    assert any("Summary check warning" in line for line in result.report)
