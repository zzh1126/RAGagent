from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = PROJECT_ROOT / "reports" / "extension_v2" / "blind_review.csv"
SCORES_PATH = PROJECT_ROOT / "reports" / "extension_v2" / "blind_review_codex_preliminary_scores.csv"
OUTPUT_PATH = PROJECT_ROOT / "reports" / "extension_v2" / "blind_review_codex_preliminary.csv"
SUMMARY_PATH = PROJECT_ROOT / "reports" / "extension_v2" / "blind_review_codex_preliminary.md"
MANIFEST_PATH = PROJECT_ROOT / "reports" / "extension_v2" / "blind_review_codex_preliminary_manifest.json"
RECEIPT_PATH = PROJECT_ROOT / "reports" / "extension_v2" / "execution_receipt.json"

REVIEWER = "Codex-assisted preliminary review"
REVIEW_STATUS = "preliminary_pending_user_confirmation"
TEXT_HASH_SUFFIXES = {".csv", ".json", ".jsonl", ".md", ".py", ".yaml", ".yml"}
SCORE_FIELDS = (
    "answer_correctness",
    "evidence_faithfulness",
    "hallucination",
    "over_refusal",
    "readability",
)
SCORE_MAP_FIELDS = ("review_item_id", *SCORE_FIELDS, "review_notes")


def sha256_file(path: Path) -> str:
    if path.suffix.lower() in TEXT_HASH_SUFFIXES:
        payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        return hashlib.sha256(payload).hexdigest()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_scores(source: list[dict[str, str]], scores: list[dict[str, str]]) -> None:
    if len(source) != 92:
        raise ValueError(f"expected 92 blind rows, got {len(source)}")
    if [row["review_item_id"] for row in scores] != [
        row["review_item_id"] for row in source
    ]:
        raise ValueError("preliminary score order or IDs differ from the blind source")
    if set(scores[0]) != set(SCORE_MAP_FIELDS):
        raise ValueError("preliminary score columns do not match the scoring contract")
    for row in source:
        if "method_id" in row or any(key.startswith("expected") for key in row):
            raise ValueError("blind source exposes a forbidden identity or expected field")
    for row in scores:
        for field, allowed in {
            "answer_correctness": {"0", "1", "2"},
            "evidence_faithfulness": {"", "0", "1", "2"},
            "hallucination": {"", "0", "1"},
            "over_refusal": {"0", "1"},
            "readability": {"", "1", "2", "3", "4", "5"},
        }.items():
            if row[field] not in allowed:
                raise ValueError(f"invalid {field} for {row['review_item_id']}")
        if not row["review_notes"].strip():
            raise ValueError(f"missing review note for {row['review_item_id']}")


def build_output(
    source: list[dict[str, str]], scores: list[dict[str, str]]
) -> list[dict[str, str]]:
    by_id = {row["review_item_id"]: row for row in scores}
    output: list[dict[str, str]] = []
    for source_row in source:
        row = dict(source_row)
        score = by_id[source_row["review_item_id"]]
        for field in SCORE_FIELDS:
            row[field] = score[field]
        row["review_notes"] = score["review_notes"]
        row["reviewer"] = REVIEWER
        row["review_status"] = REVIEW_STATUS
        output.append(row)
    return output


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_markdown(rows: list[dict[str, str]]) -> str:
    groups: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
    for row in rows:
        groups.setdefault(row["question_id"], []).append(row)
    lines = [
        "# Stage 8.7 Extension 匿名盲评：Codex 初评",
        "",
        "这是 Codex 辅助初评，不是独立人工标注。用户确认或修改前，不得解盲、汇总为最终人工指标或写入正式结论。",
        "",
        "评分字段：Correctness 0-2；Faithfulness 0-2；Hallucination 0-1；Over-refusal 0-1；Readability 1-5。拒答的 Faithfulness 和 Readability 按合同留空。",
        "",
        "原始答案和证据仍以 `blind_review.csv` 为准；本文件只展示匿名答案与初评分数。",
        "",
    ]
    for question_id, question_rows in groups.items():
        lines.append(f"## {question_id}: {question_rows[0]['question']}")
        lines.append("")
        lines.extend(
            [
                "| Label | Answer | Correctness | Faithfulness | Hallucination | Over-refusal | Readability | Note |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for row in question_rows:
            answer = " ".join(row["answer"].split()).replace("|", "\\|")
            note = row["review_notes"].replace("|", "\\|")
            values = [
                row["answer_correctness"],
                row["evidence_faithfulness"] or "n/a",
                row["hallucination"] or "n/a",
                row["over_refusal"],
                row["readability"] or "n/a",
            ]
            lines.append(
                f"| {row['answer_label']} | {answer} | {values[0]} | {values[1]} | {values[2]} | {values[3]} | {values[4]} | {note} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    overwrite = "--overwrite" in sys.argv[1:]
    if not SOURCE_PATH.is_file() or not SCORES_PATH.is_file():
        raise SystemExit("blind source or preliminary score map is missing")
    if not overwrite and any(path.exists() for path in (OUTPUT_PATH, SUMMARY_PATH, MANIFEST_PATH)):
        raise SystemExit("refusing to overwrite existing preliminary review artifacts")

    source = read_csv(SOURCE_PATH)
    scores = read_csv(SCORES_PATH)
    validate_scores(source, scores)
    output = build_output(source, scores)
    write_csv(OUTPUT_PATH, output)
    SUMMARY_PATH.write_text(build_markdown(output), encoding="utf-8")

    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "artifact": "extension_blind_preliminary_review",
        "protocol_version": "v2",
        "release_id": receipt["release_id"],
        "reviewer": REVIEWER,
        "review_status": REVIEW_STATUS,
        "source_blind_review_sha256": sha256_file(SOURCE_PATH),
        "score_map_sha256": sha256_file(SCORES_PATH),
        "output_sha256": sha256_file(OUTPUT_PATH),
        "question_count": 23,
        "row_count": len(output),
        "method_identity_read": False,
        "expected_answer_fields_read": False,
        "notes": [
            "Scores are Codex-assisted preliminary judgments.",
            "A user must confirm or revise every row before unblinding.",
            "The immutable blind source and method key are not modified.",
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"OK: preliminary rows={len(output)}")
    print(f"OK: output={OUTPUT_PATH}")
    print(f"OK: summary={SUMMARY_PATH}")
    print(f"OK: manifest={MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
