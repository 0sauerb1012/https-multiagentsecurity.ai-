from app.models import Paper
from app.services.ranking import rank_papers


def build_paper(title: str, summary: str) -> Paper:
    return Paper(
        id=title.lower().replace(" ", "-"),
        title=title,
        summary=summary,
        published="2024-01-01T00:00:00Z",
        updated="2024-01-01T00:00:00Z",
        authors=["A. Author"],
        categories=["cs.AI"],
        primary_category="cs.AI",
        paper_url="https://arxiv.org/abs/1234.5678",
        pdf_url="https://arxiv.org/pdf/1234.5678.pdf",
    )


def test_rank_papers_prioritizes_title_overlap() -> None:
    papers = [
        build_paper("Graph Neural Networks for Molecules", "Uses message passing for chemistry."),
        build_paper("Vision Transformers", "Image classification with transformers."),
    ]

    ranked = rank_papers("graph neural networks for drug discovery", papers)

    assert ranked[0].title == "Graph Neural Networks for Molecules"
    assert ranked[0].relevance_score > ranked[1].relevance_score
    assert "title matches" in ranked[0].rationale
