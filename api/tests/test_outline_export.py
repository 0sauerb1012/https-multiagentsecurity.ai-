from zipfile import ZipFile
from io import BytesIO

from app.models import LiteratureOutlineSection, LiteratureReviewOutlineResponse
from app.services.exporters import build_outline_docx


def test_build_outline_docx_contains_word_document_parts() -> None:
    outline = LiteratureReviewOutlineResponse(
        topic="knowledge graphs",
        outline_title="Literature Review Outline: knowledge graphs",
        query_used="zotero_outline_0sauerb",
        total_candidates=5,
        accepted_papers=3,
        workflow_steps=["outline_agent used deterministic literature-review synthesis"],
        sanity_report=["Sanity status: passed."],
        sections=[
            LiteratureOutlineSection(
                title="Introduction",
                overview="Introduce the topic.",
                bullet_points=["Define the field (Smith, 2024)."],
            )
        ],
        bibliography=["Smith, J. (2024). Example paper. Zotero Library Source. https://example.org/paper"],
    )

    output = build_outline_docx(outline)
    archive = ZipFile(BytesIO(output))
    names = set(archive.namelist())

    assert "[Content_Types].xml" in names
    assert "word/document.xml" in names
    assert "word/styles.xml" in names
