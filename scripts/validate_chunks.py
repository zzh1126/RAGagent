from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    sections_path = PROJECT_ROOT / "data" / "processed" / "sections.jsonl"
    chunks_path = PROJECT_ROOT / "data" / "processed" / "chunks.jsonl"
    if not sections_path.exists():
        fail("sections.jsonl does not exist")
    if not chunks_path.exists():
        fail("chunks.jsonl does not exist")

    sections = read_jsonl(sections_path)
    chunks = read_jsonl(chunks_path)
    if not sections:
        fail("no sections generated")
    if not 120 <= len(chunks) <= 180:
        fail(f"expected 120-180 chunks, found {len(chunks)}")

    required = {
        "chunk_id",
        "source_id",
        "page_title",
        "heading_path",
        "url",
        "display_text",
        "embedding_text",
        "language",
        "retrieved_at",
        "content_hash",
    }
    ids = set()
    source_counts: Counter[str] = Counter()
    noisy = []
    for chunk in chunks:
        missing = required - set(chunk)
        if missing:
            fail(f"chunk missing fields {missing}: {chunk.get('chunk_id')}")
        if chunk["chunk_id"] in ids:
            fail(f"duplicate chunk_id: {chunk['chunk_id']}")
        ids.add(chunk["chunk_id"])
        if not chunk["url"].startswith("https://scikit-learn.org/stable/modules/"):
            fail(f"chunk url outside whitelist: {chunk['chunk_id']}")
        if not chunk["heading_path"]:
            fail(f"chunk heading_path empty: {chunk['chunk_id']}")
        text = chunk["display_text"].lower()
        if any(term in text for term in ["show source", "edit this page", "gallery examples"]):
            noisy.append(chunk["chunk_id"])
        source_counts[chunk["source_id"]] += 1
    if noisy:
        fail(f"possible noisy chunks: {noisy[:10]}")

    print("OK: chunks are valid")
    print(f"OK: sections={len(sections)} chunks={len(chunks)}")
    print("OK: source distribution=" + ", ".join(f"{k}:{v}" for k, v in sorted(source_counts.items())))


if __name__ == "__main__":
    sys.exit(main())
