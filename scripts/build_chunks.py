from __future__ import annotations

import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.html_processing import build_chunks, extract_sections, write_jsonl


def main() -> None:
    sources = yaml.safe_load((PROJECT_ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))["sources"]
    settings = yaml.safe_load((PROJECT_ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    html_dir = PROJECT_ROOT / "data" / "raw" / "html"
    processed_dir = PROJECT_ROOT / "data" / "processed"

    all_sections = []
    for source in sources:
        html_path = html_dir / f"{source['id']}_{source['name']}.html"
        if not html_path.exists():
            raise SystemExit(f"ERROR: missing cached html: {html_path}")
        sections = extract_sections(source, html_path.read_text(encoding="utf-8"))
        all_sections.extend(sections)
        print(f"OK: {source['id']} sections={len(sections)}")

    chunks = build_chunks(all_sections)
    chunks = cap_chunks(
        chunks,
        settings.get("chunking", {}).get("max_chunks_by_source", {}),
        settings.get("chunking", {}).get("max_chunks_total", 180),
    )
    write_jsonl(processed_dir / "sections.jsonl", all_sections)
    write_jsonl(processed_dir / "chunks.jsonl", chunks)
    print(f"OK: wrote sections={len(all_sections)} chunks={len(chunks)}")


def cap_chunks(chunks, source_caps: dict, total_cap: int):
    counts: dict[str, int] = {}
    selected = []
    for chunk in chunks:
        cap = int(source_caps.get(chunk.source_id, total_cap))
        current = counts.get(chunk.source_id, 0)
        if current >= cap:
            continue
        if len(selected) >= total_cap:
            break
        selected.append(chunk)
        counts[chunk.source_id] = current + 1
    return selected


if __name__ == "__main__":
    sys.exit(main())
