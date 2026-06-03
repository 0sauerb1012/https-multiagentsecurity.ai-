import asyncio

from app.models import ReviewedPaper
from app.services.zotero_api import ZoteroDiscoveryService


def build_paper(title: str, *, paper_id: str, fit_score: float) -> ReviewedPaper:
    return ReviewedPaper(
        id=paper_id,
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
        rationale="title matches",
        is_fit=fit_score >= 2.0,
        fit_score=fit_score,
        reviewer_notes="reviewer notes",
        key_points_summary=["one", "two", "three", "four", "five"] if fit_score >= 2.0 else None,
    )


def test_prune_library_items_deletes_duplicates_and_low_scores(monkeypatch) -> None:
    service = ZoteroDiscoveryService()
    deleted_chunks: list[list[str]] = []

    async def fake_delete_items(*, api_key: str, user_id: str, item_keys: list[str], library_version: str) -> None:
        assert api_key == "secret"
        assert user_id == "12345"
        assert library_version == "99"
        deleted_chunks.append(item_keys)

    monkeypatch.setattr(service, "_delete_items", fake_delete_items)

    result = asyncio.run(
        service.prune_library_items(
            api_key="secret",
            papers=[
                build_paper("Duplicate Title", paper_id="zotero-keep-1", fit_score=4.0),
                build_paper("Duplicate Title", paper_id="zotero-drop-2", fit_score=1.0),
                build_paper("Unique Low Score", paper_id="zotero-drop-3", fit_score=0.5),
            ],
            user_id="12345",
            library_version="99",
            min_fit_score=2.0,
            delete_below_score=True,
            delete_duplicates=True,
        )
    )

    assert result.deleted_items == 2
    assert result.deleted_low_score == 2
    assert result.deleted_duplicates == 1
    assert deleted_chunks == [["drop-2", "drop-3"]]
