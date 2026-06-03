from __future__ import annotations

from io import BytesIO
import re
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook

from app.models import LiteratureReviewOutlineResponse, ReviewedPaper


def slugify_filename(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "papers"


def build_apa_citation(paper: ReviewedPaper) -> str:
    authors = _format_apa_authors(paper.authors)
    year = paper.published[:4] if paper.published else "n.d."
    title = paper.title.rstrip(".")
    source = "arXiv" if "arxiv" in (paper.paper_url or "").lower() or "arxiv" in paper.id.lower() else "Zotero Library Source"
    url = paper.paper_url or paper.pdf_url or ""
    return f"{authors} ({year}). {title}. {source}.{f' {url}' if url else ''}"


def _format_apa_authors(authors: list[str]) -> str:
    if not authors:
        return "Unknown author"

    formatted = [_format_single_author(author) for author in authors]
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) <= 20:
        return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"
    return ", ".join(formatted[:19]) + ", ... " + formatted[-1]


def _format_single_author(author: str) -> str:
    parts = author.split()
    if not parts:
        return author
    last_name = parts[-1].rstrip(",")
    initials = " ".join(f"{part[0]}." for part in parts[:-1] if part)
    return f"{last_name}, {initials}".strip().replace(" ,", ",")


def build_ris(papers: list[ReviewedPaper]) -> str:
    blocks: list[str] = []
    for paper in papers:
        apa_citation = build_apa_citation(paper)
        lines = [
            "TY  - JOUR",
            f"TI  - {paper.title}",
            *(f"AU  - {author}" for author in paper.authors),
            f"PY  - {paper.published[:4]}" if paper.published else "PY  - ",
            f"DA  - {paper.published[:10]}" if paper.published else "DA  - ",
            f"AB  - {paper.summary}",
            *(f"KW  - {category}" for category in paper.categories),
            f"UR  - {paper.paper_url}",
            f"N1  - Fit score: {paper.fit_score}",
            f"N1  - Relevance score: {paper.relevance_score}",
            f"N1  - Accepted: {'yes' if paper.is_fit else 'no'}",
            f"N1  - Reviewer notes: {paper.reviewer_notes}",
            f"N1  - APA citation: {apa_citation}",
        ]
        if paper.pdf_url:
            lines.append(f"L1  - {paper.pdf_url}")
        if paper.key_points_summary:
            lines.extend(f"N1  - Key point: {point}" for point in paper.key_points_summary)
        lines.append("ER  - ")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def build_xlsx(papers: list[ReviewedPaper]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Papers"
    headers = [
        "Title",
        "Authors",
        "Published",
        "Updated",
        "Primary Category",
        "Categories",
        "APA Citation",
        "Relevance Score",
        "Fit Score",
        "Accepted",
        "Reviewer Notes",
        "Key Points",
        "Abstract URL",
        "PDF URL",
        "Summary",
    ]
    sheet.append(headers)

    for paper in papers:
        sheet.append(
            [
                paper.title,
                ", ".join(paper.authors),
                paper.published,
                paper.updated,
                paper.primary_category or "",
                ", ".join(paper.categories),
                build_apa_citation(paper),
                paper.relevance_score,
                paper.fit_score,
                "yes" if paper.is_fit else "no",
                paper.reviewer_notes,
                "\n".join(paper.key_points_summary or []),
                paper.paper_url,
                paper.pdf_url or "",
                paper.summary,
            ]
        )

    for column in sheet.columns:
        width = max(len(str(cell.value or "")) for cell in column[:30])
        sheet.column_dimensions[column[0].column_letter].width = min(max(width + 2, 14), 50)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.read()


def build_outline_docx(outline: LiteratureReviewOutlineResponse) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _rels_xml())
        archive.writestr("word/_rels/document.xml.rels", _document_rels_xml())
        archive.writestr("word/styles.xml", _styles_xml())
        archive.writestr("word/document.xml", _document_xml(outline))
    buffer.seek(0)
    return buffer.read()


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""


def _rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def _document_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>"""


def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
  </w:style>
</w:styles>"""


def _document_xml(outline: LiteratureReviewOutlineResponse) -> str:
    body: list[str] = []
    body.append(_paragraph(outline.outline_title, style="Heading1"))
    body.append(_paragraph(f"Topic: {outline.topic}"))
    body.append(_paragraph(f"Accepted papers: {outline.accepted_papers} of {outline.total_candidates}"))

    for section in outline.sections:
        body.append(_paragraph(section.title, style="Heading2"))
        body.append(_paragraph(section.overview))
        for bullet in section.bullet_points:
            body.append(_bullet_paragraph(bullet))

    body.append(_paragraph("References", style="Heading2"))
    for citation in outline.bibliography:
        body.append(_paragraph(citation))

    return (
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
        """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">"""
        f"""<w:body>{''.join(body)}<w:sectPr/></w:body></w:document>"""
    )


def _paragraph(text: str, *, style: str | None = None) -> str:
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{style_xml}<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def _bullet_paragraph(text: str) -> str:
    return (
        '<w:p>'
        '<w:r><w:t xml:space="preserve">- </w:t></w:r>'
        f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
        '</w:p>'
    )
