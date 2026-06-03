from __future__ import annotations

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET

from app.models import Paper


NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "bib": "http://purl.org/net/biblio#",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "link": "http://purl.org/rss/1.0/modules/link/",
    "z": "http://www.zotero.org/namespaces/export#",
    "prism": "http://prismstandard.org/namespaces/1.2/basic/",
}

IGNORED_TYPES = {"Attachment", "Collection"}


@dataclass(frozen=True)
class ParsedZoteroEntry:
    paper: Paper
    text: str


def parse_zotero_rdf(file_bytes: bytes, *, filename: str) -> list[ParsedZoteroEntry]:
    root = ET.fromstring(file_bytes)
    entries: list[ParsedZoteroEntry] = []
    counter = 0

    for child in root:
        local_name = _local_name(child.tag)
        if local_name in IGNORED_TYPES:
            continue

        title = _first_text(child, "dc:title", "dcterms:title")
        if not title:
            continue

        counter += 1
        authors = _extract_authors(child)
        summary = _first_text(child, "dcterms:abstract", "dc:description", "dc:abstract")
        published = _first_text(child, "dc:date", "dcterms:date", "prism:publicationDate")
        categories = _collect_texts(child, "dc:subject")
        paper_url = _extract_link(child)
        text = _build_entry_text(title=title, summary=summary, authors=authors, categories=categories, published=published)

        identifier = _slugify(_about_id(child) or title or f"{filename}-{counter}")
        paper = Paper(
            id=f"rdf-{counter}-{identifier}",
            title=title,
            summary=summary or f"Imported from Zotero RDF: {title}",
            published=published or "",
            updated=published or "",
            authors=authors,
            categories=categories or ["zotero-rdf"],
            primary_category=(categories[0] if categories else "zotero-rdf"),
            paper_url=paper_url,
            pdf_url=None,
        )
        entries.append(ParsedZoteroEntry(paper=paper, text=text))

    return entries


def _first_text(element: ET.Element, *paths: str) -> str:
    for path in paths:
        value = element.findtext(path, default="", namespaces=NS).strip()
        if value:
            return " ".join(value.split())
    return ""


def _collect_texts(element: ET.Element, path: str) -> list[str]:
    values: list[str] = []
    for node in element.findall(path, NS):
        text = " ".join((node.text or "").split())
        if text:
            values.append(text)
    return values


def _extract_authors(element: ET.Element) -> list[str]:
    authors: list[str] = []
    for creator in element.findall("dc:creator", NS):
        person = creator.find("foaf:Person", NS)
        if person is None:
            literal = " ".join((creator.text or "").split())
            if literal:
                authors.append(literal)
            continue

        given = person.findtext("foaf:givenName", default="", namespaces=NS).strip()
        surname = person.findtext("foaf:surname", default="", namespaces=NS).strip()
        name = " ".join(part for part in [given, surname] if part)
        if not name:
            name = " ".join((person.findtext("foaf:name", default="", namespaces=NS) or "").split())
        if name:
            authors.append(name)
    return authors


def _extract_link(element: ET.Element) -> str:
    for node in element.findall("link:link", NS):
        href = node.attrib.get(f"{{{NS['rdf']}}}resource", "").strip()
        if href:
            return href
    for node in element.findall("dc:identifier", NS):
        text = " ".join((node.text or "").split())
        if text.startswith("http://") or text.startswith("https://"):
            return text
    return ""


def _build_entry_text(
    *,
    title: str,
    summary: str,
    authors: list[str],
    categories: list[str],
    published: str,
) -> str:
    parts = [f"Title: {title}"]
    if authors:
        parts.append(f"Authors: {', '.join(authors)}")
    if published:
        parts.append(f"Published: {published}")
    if categories:
        parts.append(f"Keywords: {', '.join(categories)}")
    if summary:
        parts.append(f"Abstract: {summary}")
    return "\n".join(parts)


def _about_id(element: ET.Element) -> str:
    return element.attrib.get(f"{{{NS['rdf']}}}about", "").rsplit("#", maxsplit=1)[-1]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "entry"
