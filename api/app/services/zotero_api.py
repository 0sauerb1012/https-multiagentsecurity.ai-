from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable
import uuid
import re

import httpx

from app.models import AgentSearchResponse, Paper, ReviewedPaper
from app.services.paper_content import ExtractedPaperContent
from app.services.upload_discovery import UploadDiscoveryRequest, UploadDiscoveryService


ZOTERO_API_BASE = "https://api.zotero.org"


@dataclass(frozen=True)
class ZoteroDiscoveryRequest:
    topic: str
    username: str
    api_key: str
    min_fit_score: float
    include_rejected: bool
    max_items: int = 100
    delete_below_score: bool = False
    delete_duplicates: bool = False


@dataclass(frozen=True)
class ZoteroSaveResult:
    saved_items: int
    failed_items: int
    message: str


@dataclass(frozen=True)
class ZoteroPruneResult:
    deleted_items: int
    deleted_low_score: int
    deleted_duplicates: int
    message: str


class ZoteroDiscoveryService:
    def __init__(self) -> None:
        self.upload_service = UploadDiscoveryService()

    async def run(
        self,
        request: ZoteroDiscoveryRequest,
        progress_callback: Callable[[int, str], Awaitable[None] | None] | None = None,
    ) -> AgentSearchResponse:
        await self._report_progress(progress_callback, 5, "Resolving Zotero user ID from API key")
        user_id = await self._resolve_user_id(request.api_key)
        await self._report_progress(progress_callback, 12, f"Resolved Zotero library for {request.username or user_id}")
        extracted, library_version = await self._fetch_library_entries(request, user_id, progress_callback)
        await self._report_progress(progress_callback, 72, "Reviewing Zotero library items")
        include_all_reviewed = request.include_rejected or request.delete_below_score or request.delete_duplicates
        result = await self.upload_service.run_on_extracted(
            UploadDiscoveryRequest(
                topic=request.topic,
                min_fit_score=request.min_fit_score,
                include_rejected=include_all_reviewed,
                score_against_topic=True,
            ),
            extracted,
            query_used=f"zotero_user_{request.username or user_id}",
            source_description=f"Zotero personal library {request.username or user_id}",
            progress_callback=progress_callback,
        )
        if request.delete_below_score or request.delete_duplicates:
            await self._report_progress(progress_callback, 94, "Pruning Zotero items based on score and duplicate checks")
            prune_result = await self.prune_library_items(
                api_key=request.api_key,
                papers=result.papers,
                user_id=user_id,
                library_version=library_version,
                min_fit_score=request.min_fit_score,
                delete_below_score=request.delete_below_score,
                delete_duplicates=request.delete_duplicates,
            )
            result.zotero_deleted_items = prune_result.deleted_items
            result.workflow_steps.append(f"zotero_prune: {prune_result.message}")
        if not request.include_rejected:
            result.papers = [paper for paper in result.papers if paper.is_fit]
        return result

    async def prune_library_items(
        self,
        *,
        api_key: str,
        papers: list[ReviewedPaper],
        user_id: str,
        library_version: str,
        min_fit_score: float,
        delete_below_score: bool,
        delete_duplicates: bool,
    ) -> ZoteroPruneResult:
        delete_keys: set[str] = set()
        low_score_keys: set[str] = set()
        duplicate_keys: set[str] = set()

        if delete_below_score:
            for paper in papers:
                if paper.fit_score < min_fit_score:
                    key = self._paper_key(paper)
                    if key:
                        low_score_keys.add(key)

        if delete_duplicates:
            papers_by_title: dict[str, list[ReviewedPaper]] = {}
            for paper in papers:
                normalized = self._normalize_title(paper.title)
                if not normalized:
                    continue
                papers_by_title.setdefault(normalized, []).append(paper)

            for group in papers_by_title.values():
                if len(group) < 2:
                    continue
                ranked_group = sorted(
                    group,
                    key=lambda paper: (paper.fit_score, paper.relevance_score, paper.updated, paper.id),
                    reverse=True,
                )
                for duplicate in ranked_group[1:]:
                    key = self._paper_key(duplicate)
                    if key:
                        duplicate_keys.add(key)

        delete_keys.update(low_score_keys)
        delete_keys.update(duplicate_keys)

        if not delete_keys:
            return ZoteroPruneResult(
                deleted_items=0,
                deleted_low_score=0,
                deleted_duplicates=0,
                message="No Zotero items met the selected prune rules.",
            )

        await self._delete_items(
            api_key=api_key,
            user_id=user_id,
            item_keys=sorted(delete_keys),
            library_version=library_version,
        )

        return ZoteroPruneResult(
            deleted_items=len(delete_keys),
            deleted_low_score=len(low_score_keys),
            deleted_duplicates=len(duplicate_keys),
            message=(
                f"Deleted {len(delete_keys)} item(s) from Zotero "
                f"({len(low_score_keys)} below score, {len(duplicate_keys)} duplicate title matches)."
            ),
        )

    async def save_search_results(
        self,
        *,
        api_key: str,
        papers: list[ReviewedPaper],
        username: str | None = None,
        topic: str | None = None,
    ) -> ZoteroSaveResult:
        accepted_papers = [paper for paper in papers if paper.is_fit]
        if not accepted_papers:
            return ZoteroSaveResult(saved_items=0, failed_items=0, message="No accepted papers were eligible for Zotero save.")

        user_id = await self._resolve_user_id(api_key)
        headers = {
            "Zotero-API-Version": "3",
            "Zotero-API-Key": api_key,
            "Zotero-Write-Token": uuid.uuid4().hex,
        }
        payload = [self._paper_to_zotero_item(paper, topic=topic) for paper in accepted_papers]

        async with httpx.AsyncClient(base_url=ZOTERO_API_BASE, headers=headers, timeout=30.0) as client:
            response = await client.post(f"/users/{user_id}/items", json=payload)
            response.raise_for_status()
            result = response.json()

        successful = result.get("successful", {}) if isinstance(result, dict) else {}
        failed = result.get("failed", {}) if isinstance(result, dict) else {}
        saved_items = len(successful)
        failed_items = len(failed)
        library_label = username or user_id
        message = f"Saved {saved_items} accepted paper(s) to Zotero library {library_label}."
        if failed_items:
            message = f"Saved {saved_items} accepted paper(s) to Zotero library {library_label}; {failed_items} item(s) failed."
        return ZoteroSaveResult(saved_items=saved_items, failed_items=failed_items, message=message)

    async def _resolve_user_id(self, api_key: str) -> str:
        headers = {
            "Zotero-API-Version": "3",
        }
        async with httpx.AsyncClient(base_url=ZOTERO_API_BASE, headers=headers, timeout=20.0) as client:
            response = await client.get(f"/keys/{api_key}")
            response.raise_for_status()
            payload = response.json()

        user_id = str(payload.get("userID") or "").strip()
        if not user_id:
            raise ValueError("Could not resolve a Zotero user ID from the provided API key.")
        return user_id

    def _paper_to_zotero_item(self, paper: ReviewedPaper, *, topic: str | None) -> dict:
        tags = [{"tag": category} for category in paper.categories[:8]]
        tags.append({"tag": "arxiv-agent-api"})
        if topic:
            tags.append({"tag": f"topic:{topic[:120]}"})

        item: dict = {
            "itemType": "journalArticle",
            "title": paper.title,
            "creators": [self._author_to_creator(author) for author in paper.authors],
            "abstractNote": paper.summary,
            "url": paper.paper_url or paper.pdf_url or "",
            "date": paper.published[:10] if paper.published else "",
            "tags": tags,
            "extra": (
                f"arXiv URL: {paper.paper_url or 'n/a'}\n"
                f"PDF URL: {paper.pdf_url or 'n/a'}\n"
                f"Fit score: {paper.fit_score:.3f}\n"
                f"Relevance score: {paper.relevance_score:.3f}\n"
                f"Reviewer notes: {paper.reviewer_notes}"
            ),
        }
        return item

    @staticmethod
    def _author_to_creator(author: str) -> dict:
        parts = [part for part in author.split() if part]
        if len(parts) >= 2:
            return {
                "creatorType": "author",
                "firstName": " ".join(parts[:-1]),
                "lastName": parts[-1],
            }
        return {
            "creatorType": "author",
            "name": author,
        }

    async def _fetch_library_entries(
        self,
        request: ZoteroDiscoveryRequest,
        user_id: str,
        progress_callback: Callable[[int, str], Awaitable[None] | None] | None = None,
    ) -> tuple[list[tuple[Paper, ExtractedPaperContent]], str]:
        headers = {
            "Zotero-API-Version": "3",
            "Zotero-API-Key": request.api_key,
        }
        entries: list[tuple[Paper, ExtractedPaperContent]] = []
        start = 0
        library_version = "0"

        async with httpx.AsyncClient(base_url=ZOTERO_API_BASE, headers=headers, timeout=30.0) as client:
            while len(entries) < request.max_items:
                limit = min(100, request.max_items - len(entries))
                response = await client.get(
                    f"/users/{user_id}/items/top",
                    params={"format": "json", "limit": limit, "start": start},
                )
                response.raise_for_status()
                library_version = response.headers.get("Last-Modified-Version", library_version)
                items = response.json()
                if not items:
                    break

                for item in items:
                    parsed = await self._parse_item(client, user_id, item)
                    if parsed is not None:
                        entries.append(parsed)
                        progress = 12 + int((len(entries) / max(request.max_items, 1)) * 53)
                        await self._report_progress(
                            progress_callback,
                            progress,
                            f"Fetched {len(entries)} of up to {request.max_items} Zotero items",
                        )
                    if len(entries) >= request.max_items:
                        break

                if len(items) < limit:
                    break
                start += limit

        return entries, library_version

    async def _report_progress(
        self,
        callback: Callable[[int, str], Awaitable[None] | None] | None,
        progress: int,
        message: str,
    ) -> None:
        if callback is None:
            return
        result = callback(progress, message)
        if result is not None:
            await result

    async def _parse_item(
        self,
        client: httpx.AsyncClient,
        user_id: str,
        item: dict,
    ) -> tuple[Paper, ExtractedPaperContent] | None:
        data = item.get("data", {})
        title = (data.get("title") or "").strip()
        item_type = (data.get("itemType") or "").strip()
        if not title or item_type in {"attachment", "note", "annotation"}:
            return None

        key = data.get("key") or title
        authors = self._extract_authors(data.get("creators", []))
        summary = " ".join((data.get("abstractNote") or "").split())
        categories = [tag.get("tag", "").strip() for tag in data.get("tags", []) if tag.get("tag")]
        paper_url = (
            item.get("links", {}).get("alternate", {}).get("href")
            or (data.get("url") or "").strip()
        )
        published = (data.get("date") or "").strip()
        full_text = await self._fetch_best_full_text(client, user_id, key)
        text = full_text or self._build_entry_text(title, summary, authors, categories, published, item_type)

        paper = Paper(
            id=f"zotero-{key}",
            title=title,
            summary=summary or f"Imported from Zotero personal library item {key}.",
            published=published,
            updated=(data.get("dateModified") or "").strip(),
            authors=authors,
            categories=categories or [f"zotero:{item_type or 'item'}"],
            primary_category=f"zotero:{item_type or 'item'}",
            paper_url=paper_url,
            pdf_url=None,
        )
        extracted = ExtractedPaperContent(
            title=paper.title,
            summary=paper.summary,
            text=text,
            authors=paper.authors,
        )
        return paper, extracted

    async def _fetch_best_full_text(self, client: httpx.AsyncClient, user_id: str, parent_key: str) -> str:
        children_response = await client.get(f"/users/{user_id}/items/{parent_key}/children", params={"format": "json"})
        children_response.raise_for_status()
        children = children_response.json()

        attachment_key = None
        for child in children:
            data = child.get("data", {})
            if data.get("itemType") != "attachment":
                continue
            content_type = (data.get("contentType") or "").lower()
            if "pdf" in content_type:
                attachment_key = data.get("key")
                break

        if not attachment_key:
            return ""

        fulltext_response = await client.get(f"/users/{user_id}/items/{attachment_key}/fulltext")
        if fulltext_response.status_code == 404:
            return ""
        fulltext_response.raise_for_status()
        payload = fulltext_response.json()
        return " ".join((payload.get("content") or "").split())

    async def _delete_items(
        self,
        *,
        api_key: str,
        user_id: str,
        item_keys: list[str],
        library_version: str,
    ) -> None:
        headers = {
            "Zotero-API-Version": "3",
            "Zotero-API-Key": api_key,
            "If-Unmodified-Since-Version": library_version,
        }
        async with httpx.AsyncClient(base_url=ZOTERO_API_BASE, headers=headers, timeout=30.0) as client:
            for index in range(0, len(item_keys), 50):
                chunk = item_keys[index : index + 50]
                response = await client.delete("/users/{}/items".format(user_id), params={"itemKey": ",".join(chunk)})
                response.raise_for_status()

    @staticmethod
    def _extract_authors(creators: list[dict]) -> list[str]:
        authors: list[str] = []
        for creator in creators:
            if creator.get("creatorType") not in {"author", "editor"}:
                continue
            first = (creator.get("firstName") or "").strip()
            last = (creator.get("lastName") or "").strip()
            literal = (creator.get("name") or "").strip()
            name = " ".join(part for part in [first, last] if part) or literal
            if name:
                authors.append(name)
        return authors

    @staticmethod
    def _build_entry_text(
        title: str,
        summary: str,
        authors: list[str],
        categories: list[str],
        published: str,
        item_type: str,
    ) -> str:
        parts = [f"Title: {title}", f"Type: {item_type or 'unknown'}"]
        if authors:
            parts.append(f"Authors: {', '.join(authors)}")
        if published:
            parts.append(f"Published: {published}")
        if categories:
            parts.append(f"Tags: {', '.join(categories)}")
        if summary:
            parts.append(f"Abstract: {summary}")
        return "\n".join(parts)

    @staticmethod
    def _paper_key(paper: ReviewedPaper) -> str:
        if paper.id.startswith("zotero-"):
            return paper.id.removeprefix("zotero-")
        return ""

    @staticmethod
    def _normalize_title(title: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", title.lower())
