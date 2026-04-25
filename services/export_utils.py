"""Lightweight export helpers for the website routes."""

from __future__ import annotations

import re

from api.app.models import ReviewedPaper


def slugify_filename(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "papers"


def build_ris(papers: list[ReviewedPaper]) -> str:
    blocks: list[str] = []
    for paper in papers:
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
        ]
        if paper.doi:
            lines.append(f"DO  - {paper.doi}")
        if paper.venue:
            lines.append(f"JO  - {paper.venue}")
        if paper.pdf_url:
            lines.append(f"L1  - {paper.pdf_url}")
        if paper.key_points_summary:
            lines.extend(f"N1  - Key point: {point}" for point in paper.key_points_summary)
        lines.append("ER  - ")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"
