from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


NOISE_SELECTORS = [
    "script",
    "style",
    "nav",
    "footer",
    "header",
    ".sidebar",
    ".sphinxsidebar",
    ".related",
    ".breadcrumb",
    ".search",
    ".admonition.note .highlight",
    "div.highlight",
    "pre",
    "table.docutils",
]


@dataclass
class Section:
    source_id: str
    page_title: str
    heading_path: list[str]
    url: str
    text: str
    content_hash: str
    retrieved_at: str


@dataclass
class Chunk:
    chunk_id: str
    source_id: str
    page_title: str
    heading_path: list[str]
    url: str
    display_text: str
    embedding_text: str
    language: str
    retrieved_at: str
    content_hash: str


def write_jsonl(path: Path, rows: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            if not isinstance(row, dict):
                row = asdict(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_space(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:48] or "section"


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", text)
    return [normalize_space(part) for part in parts if normalize_space(part)]


def rough_token_count(text: str) -> int:
    return max(1, int(len(text.split()) * 1.25))


def extract_sections(source: dict, html: str, retrieved_at: str | None = None) -> list[Section]:
    retrieved_at = retrieved_at or datetime.now(timezone.utc).isoformat()
    soup = BeautifulSoup(html, "lxml")
    for selector in NOISE_SELECTORS:
        for node in soup.select(selector):
            node.decompose()

    main = (
        soup.select_one("main")
        or soup.select_one("div.body")
        or soup.select_one("article")
        or soup.body
    )
    if main is None:
        return []

    page_title = source.get("title") or source.get("name") or source["id"]
    h1 = main.find("h1")
    if h1:
        page_title = normalize_space(h1.get_text(" "))

    sections: list[Section] = []
    current_headings: list[str] = [page_title]
    current_anchor = source["url"]
    buffer: list[str] = []

    def flush() -> None:
        text = normalize_space(" ".join(buffer))
        if len(text) < 120:
            return
        sections.append(
            Section(
                source_id=source["id"],
                page_title=page_title,
                heading_path=current_headings.copy(),
                url=current_anchor,
                text=text,
                content_hash=content_hash(text),
                retrieved_at=retrieved_at,
            )
        )

    for node in main.descendants:
        if not isinstance(node, Tag):
            continue
        if node.name in {"h1", "h2", "h3"}:
            flush()
            buffer = []
            level = int(node.name[1])
            heading = normalize_space(node.get_text(" "))
            if not heading:
                continue
            if level == 1:
                current_headings = [heading]
            elif level == 2:
                current_headings = [page_title, heading]
            else:
                current_headings = current_headings[:2] + [heading]
            anchor = node.get("id") or node.find_parent(id=True)
            if isinstance(anchor, Tag):
                anchor = anchor.get("id")
            current_anchor = source["url"] + (f"#{anchor}" if anchor else "")
        elif node.name in {"p", "li"}:
            text = normalize_space(node.get_text(" "))
            if text and not _looks_like_noise(text):
                buffer.append(text)
    flush()
    return sections


def build_chunks(sections: list[Section], target_tokens: int = 580, max_tokens: int = 950) -> list[Chunk]:
    chunks: list[Chunk] = []
    per_source_counts: dict[str, int] = {}

    for section in sections:
        sentences = split_sentences(section.text)
        if not sentences:
            continue
        current: list[str] = []

        def emit() -> None:
            text = normalize_space(" ".join(current))
            if len(text) < 80:
                return
            per_source_counts[section.source_id] = per_source_counts.get(section.source_id, 0) + 1
            heading_slug = slugify(section.heading_path[-1])
            chunk_id = f"SKL-{section.source_id}-{heading_slug.upper()}-{per_source_counts[section.source_id]:03d}"
            heading_text = " > ".join(section.heading_path)
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    source_id=section.source_id,
                    page_title=section.page_title,
                    heading_path=section.heading_path,
                    url=section.url,
                    display_text=text,
                    embedding_text=f"{heading_text}\n{text}",
                    language="en",
                    retrieved_at=section.retrieved_at,
                    content_hash=content_hash(text),
                )
            )

        for sentence in sentences:
            next_text = normalize_space(" ".join([*current, sentence]))
            if current and rough_token_count(next_text) > max_tokens:
                emit()
                current = current[-2:] if rough_token_count(" ".join(current[-2:])) <= 60 else []
            current.append(sentence)
            if rough_token_count(" ".join(current)) >= target_tokens:
                emit()
                current = current[-2:] if rough_token_count(" ".join(current[-2:])) <= 60 else []
        emit()

    seen: set[str] = set()
    unique_chunks: list[Chunk] = []
    for chunk in chunks:
        if chunk.content_hash in seen:
            continue
        seen.add(chunk.content_hash)
        unique_chunks.append(chunk)
    return unique_chunks


def _looks_like_noise(text: str) -> bool:
    lower = text.lower()
    if len(text) < 25:
        return True
    noise_phrases = [
        "gallery examples",
        "download",
        "previous",
        "next",
        "show source",
        "edit this page",
        "© copyright",
        "navigation",
    ]
    return any(phrase in lower for phrase in noise_phrases)
