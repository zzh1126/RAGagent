from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_jsonl(path: Path) -> dict[str, dict]:
    with path.open("r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return {row["chunk_id"]: row for row in rows}


def main() -> None:
    relations = read_csv(PROJECT_ROOT / "data" / "graph" / "relations.csv")
    chunks = read_jsonl(PROJECT_ROOT / "data" / "chroma" / "chunks_snapshot.jsonl")

    approved = 0
    for relation in relations:
        if relation["review_status"] != "approved":
            fail(f"relation not approved: {relation['relation_id']}")
        approved += 1
        chunk_ids = [x for x in relation["evidence_chunk_ids"].split("|") if x]
        if not chunk_ids:
            fail(f"approved relation missing evidence chunks: {relation['relation_id']}")
        for chunk_id in chunk_ids:
            if chunk_id not in chunks:
                fail(f"missing evidence chunk id: {chunk_id} in {relation['relation_id']}")

    print(f"OK: graph evidence validated for {approved} approved relations")


if __name__ == "__main__":
    sys.exit(main())
