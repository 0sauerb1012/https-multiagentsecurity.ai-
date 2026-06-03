from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re

import httpx
from pypdf import PdfReader

from ..config import settings
from ..models import Paper


@dataclass(frozen=True)
class ExtractedPaperContent:
    title: str
    summary: str
    text: str
    authors: list[str]


class PaperContentService:
    async def fetch_text(self, paper: Paper) -> str:
        if not paper.pdf_url:
            raise ValueError("Paper does not have a PDF URL")

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(paper.pdf_url)
            response.raise_for_status()

        reader = PdfReader(BytesIO(response.content))
        pages: list[str] = []
        current_length = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            cleaned = " ".join(text.split())
            if not cleaned:
                continue
            remaining = settings.paper_text_max_chars - current_length
            if remaining <= 0:
                break
            clipped = cleaned[:remaining]
            pages.append(clipped)
            current_length += len(clipped)

        combined = "\n".join(pages).strip()
        if not combined:
            raise ValueError("No extractable PDF text was found")
        return combined

    def extract_uploaded_paper(self, file_bytes: bytes, *, filename: str) -> ExtractedPaperContent:
        reader = PdfReader(BytesIO(file_bytes))
        text = self._extract_text_from_reader(reader)
        metadata = reader.metadata or {}
        title = self._resolve_title(metadata.title if metadata else None, filename, text)
        authors = self._resolve_authors(metadata.author if metadata else None)
        summary = self._build_summary_preview(text)
        return ExtractedPaperContent(title=title, summary=summary, text=text, authors=authors)

    def _extract_text_from_reader(self, reader: PdfReader) -> str:
        pages: list[str] = []
        current_length = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            cleaned = " ".join(text.split())
            if not cleaned:
                continue
            remaining = settings.paper_text_max_chars - current_length
            if remaining <= 0:
                break
            clipped = cleaned[:remaining]
            pages.append(clipped)
            current_length += len(clipped)

        combined = "\n".join(pages).strip()
        if not combined:
            raise ValueError("No extractable PDF text was found")
        return combined

    def _resolve_title(self, metadata_title: str | None, filename: str, text: str) -> str:
        title = (metadata_title or "").strip()
        if title and title.lower() not in {"untitled", "microsoft word -"}:
            return title

        for line in text.splitlines():
            candidate = " ".join(line.split()).strip()
            if len(candidate) >= 12:
                return candidate[:240]

        return Path(filename).stem.replace("_", " ").replace("-", " ").strip() or "Uploaded PDF"

    def _resolve_authors(self, metadata_author: str | None) -> list[str]:
        author_text = (metadata_author or "").strip()
        if not author_text:
            return []
        return [author.strip() for author in re.split(r"[;,]", author_text) if author.strip()]

    def _build_summary_preview(self, text: str) -> str:
        sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
        if sentences:
            return " ".join(sentences[:4])[:4000]
        return text[:4000]
