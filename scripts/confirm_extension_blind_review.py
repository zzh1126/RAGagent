from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_extension_blind_preliminary as preliminary
import validate_extension_blind_preliminary as preliminary_validator


RELEASE_ID = "extension-qwen3-4b-v2-e207cb91"
CONFIRMED_REVIEWER = "User-confirmed review of Codex-assisted scoring"
CONFIRMED_STATUS = "user_confirmed"
KEY_PATH = PROJECT_ROOT / "reports" / "extension_v2" / "blind_method_key.json"
DATASET_PATH = PROJECT_ROOT / "data" / "evaluation" / "extension_questions.jsonl"
AUTO_METRICS_PATH = PROJECT_ROOT / "reports" / "extension_v2" / "combined_metrics.json"
CONFIRMED_CSV_PATH = PROJECT_ROOT / "reports" / "extension_v2" / "blind_review_user_confirmed.csv"
UNBLINDED_CSV_PATH = (
    PROJECT_ROOT / "reports" / "extension_v2" / "blind_review_unblinded_user_confirmed.csv"
)
HUMAN_METRICS_PATH = PROJECT_ROOT / "reports" / "extension_v2" / "human_metrics_user_confirmed.json"
COMBINED_METRICS_PATH = (
    PROJECT_ROOT / "reports" / "extension_v2" / "combined_metrics_user_confirmed.json"
)
SUMMARY_PATH = PROJECT_ROOT / "reports" / "extension_v2" / "metrics_user_confirmed.md"
CONFIRMATION_MANIFEST_PATH = (
    PROJECT_ROOT / "reports" / "extension_v2" / "blind_review_user_confirmation_manifest.json"
)
OUTPUT_PATHS = (
    CONFIRMED_CSV_PATH,
    UNBLINDED_CSV_PATH,
    HUMAN_METRICS_PATH,
    COMBINED_METRICS_PATH,
    SUMMARY_PATH,
    CONFIRMATION_MANIFEST_PATH,
)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return value


def read_questions(path: Path = DATASET_PATH) -> dict[str, dict[str, Any]]:
    return {
        item["question_id"]: item
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
        for item in [json.loads(line)]
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def metric(numerator: float, denominator: float, *, note: str = "") -> dict[str, Any]:
    return {
        "value": None if denominator == 0 else round(numerator / denominator, 4),
        "numerator": numerator,
        "denominator": denominator,
        "note": note,
    }


def validate_key(
    key: dict[str, Any], source_rows: list[dict[str, str]], method_order: list[str]
) -> list[dict[str, str]]:
    if key.get("artifact") != "extension_blind_method_key":
        raise ValueError("invalid blind method key artifact")
    if key.get("release_id") != RELEASE_ID:
        raise ValueError("blind method key release ID mismatch")
    rows = key.get("rows")
    if not isinstance(rows, list) or len(rows) != 92:
        raise ValueError("blind method key must contain 92 rows")
    if [row.get("review_item_id") for row in rows] != [
        row["review_item_id"] for row in source_rows
    ]:
        raise ValueError("blind method key order differs from confirmed blind rows")
    if {row.get("method_id") for row in rows} != set(method_order):
        raise ValueError("blind method key method set mismatch")
    counts = Counter(row["method_id"] for row in rows)
    if counts != Counter({method_id: 23 for method_id in method_order}):
        raise ValueError("blind method key must map 23 rows to every method")
    return rows


def build_confirmed_rows(preliminary_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in preliminary_rows:
        row = dict(item)
        row["reviewer"] = CONFIRMED_REVIEWER
        row["review_status"] = CONFIRMED_STATUS
        rows.append(row)
    return rows


def build_unblinded_rows(
    confirmed_rows: list[dict[str, str]],
    key_rows: list[dict[str, str]],
    questions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    key_by_id = {row["review_item_id"]: row for row in key_rows}
    rows: list[dict[str, Any]] = []
    for item in confirmed_rows:
        key = key_by_id[item["review_item_id"]]
        question = questions[item["question_id"]]
        rows.append(
            {
                "review_item_id": item["review_item_id"],
                "question_id": item["question_id"],
                "category": question["category"],
                "expected_behavior": question["expected_behavior"],
                "answer_label": item["answer_label"],
                "method_id": key["method_id"],
                "answer_correctness": item["answer_correctness"],
                "evidence_faithfulness": item["evidence_faithfulness"],
                "hallucination": item["hallucination"],
                "over_refusal": item["over_refusal"],
                "readability": item["readability"],
                "review_notes": item["review_notes"],
                "reviewer": CONFIRMED_REVIEWER,
                "review_status": CONFIRMED_STATUS,
            }
        )
    return rows


def distribution(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row[field]) for row in rows if str(row[field]) != "").items()))


def summarize_method(rows: list[dict[str, Any]]) -> dict[str, Any]:
    correctness_points = sum(int(row["answer_correctness"]) for row in rows)
    faithfulness_rows = [row for row in rows if row["evidence_faithfulness"] != ""]
    hallucination_rows = [row for row in rows if row["hallucination"] != ""]
    readability_rows = [row for row in rows if row["readability"] != ""]
    answerable_rows = [row for row in rows if row["expected_behavior"] == "answer"]
    return {
        "question_count": len(rows),
        "answer_correctness": metric(
            correctness_points,
            2 * len(rows),
            note="normalized 0-1 from user-confirmed 0/1/2 scores over all questions",
        ),
        "evidence_faithfulness": metric(
            sum(int(row["evidence_faithfulness"]) for row in faithfulness_rows),
            2 * len(faithfulness_rows),
            note="normalized 0-1 over substantive answers; refusals are not applicable",
        ),
        "hallucination_rate": metric(
            sum(int(row["hallucination"]) for row in hallucination_rows),
            len(hallucination_rows),
            note="unsupported professional factual claims over substantive answers",
        ),
        "over_refusal_rate": metric(
            sum(int(row["over_refusal"]) for row in answerable_rows),
            len(answerable_rows),
            note="user-confirmed over-refusal over 19 answerable questions",
        ),
        "readability": metric(
            sum(int(row["readability"]) for row in readability_rows),
            len(readability_rows),
            note="mean raw 1-5 score over correct or partially correct substantive answers",
        ),
        "scored_row_counts": {
            "correctness": len(rows),
            "faithfulness": len(faithfulness_rows),
            "hallucination": len(hallucination_rows),
            "over_refusal": len(answerable_rows),
            "readability": len(readability_rows),
        },
        "score_distributions": {
            field: distribution(rows, field)
            for field in preliminary.SCORE_FIELDS
        },
        "reviewer": CONFIRMED_REVIEWER,
        "review_status": CONFIRMED_STATUS,
    }


def build_human_metrics(
    unblinded_rows: list[dict[str, Any]], method_order: list[str]
) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "artifact": "extension_human_metrics",
        "protocol_version": "v2",
        "release_id": RELEASE_ID,
        "reviewer": CONFIRMED_REVIEWER,
        "review_status": CONFIRMED_STATUS,
        "independent_double_annotation": False,
        "method_order": method_order,
        "methods": {
            method_id: summarize_method(
                [row for row in unblinded_rows if row["method_id"] == method_id]
            )
            for method_id in method_order
        },
        "claim_scope": "descriptive_only_due_to_small_sample_and_single_confirmed_review",
    }


def build_combined_metrics(
    automatic: dict[str, Any], human: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "artifact": "extension_combined_metrics_user_confirmed",
        "protocol_version": "v2",
        "release_id": RELEASE_ID,
        "review_status": CONFIRMED_STATUS,
        "reviewer": CONFIRMED_REVIEWER,
        "automatic_metrics_source": {
            "path": "reports/extension_v2/combined_metrics.json",
            "sha256": preliminary.sha256_file(AUTO_METRICS_PATH),
        },
        "human_metrics_source": {
            "path": "reports/extension_v2/human_metrics_user_confirmed.json",
        },
        "method_order": automatic["method_order"],
        "methods": {
            method_id: {
                "automatic": automatic["metrics"][method_id],
                "human": human["methods"][method_id],
            }
            for method_id in automatic["method_order"]
        },
        "limitations": [
            "The extension contains 23 questions and only four no-answer cases.",
            "Scores are Codex-assisted and user-confirmed rather than independent double annotation.",
            "All method comparisons are descriptive and do not establish statistical significance.",
            "The extension was executed once and was not rerun after scoring.",
        ],
    }


def fmt_metric(item: dict[str, Any], *, digits: int = 4) -> str:
    value = item.get("value")
    return "n/a" if value is None else f"{value:.{digits}f}"


def build_markdown(combined: dict[str, Any]) -> str:
    lines = [
        "# Extension 自动与用户确认指标",
        "",
        "92 行匿名评分由 Codex 辅助初评并经用户逐行审核确认。解盲只在确认后进行；该流程不是独立双人标注，23 题结果只作描述性比较。",
        "",
        "| Method | Auto Decision | Correctness | Faithfulness | Hallucination | Over-refusal | Readability | Mean E2E |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method_id in combined["method_order"]:
        method = combined["methods"][method_id]
        auto = method["automatic"]
        human = method["human"]
        lines.append(
            f"| {method_id} | {fmt_metric(auto['decision_accuracy'])} | "
            f"{fmt_metric(human['answer_correctness'])} | "
            f"{fmt_metric(human['evidence_faithfulness'])} | "
            f"{fmt_metric(human['hallucination_rate'])} | "
            f"{fmt_metric(human['over_refusal_rate'])} | "
            f"{fmt_metric(human['readability'], digits=2)} | "
            f"{fmt_metric(auto['mean_end_to_end_latency_ms'], digits=2)} ms |"
        )
    lines.extend(
        [
            "",
            "指标口径：Correctness 与 Faithfulness 归一化到 0-1；Hallucination 和 Over-refusal 为比例；Readability 是 1-5 原始均值。拒答不进入 Faithfulness 和 Readability 分母。",
            "",
            "正式解释必须同时保留自动决策、人工答案质量、延迟、样本规模和单一确认流程限制，不能只选取单个优势指标。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def score_signature(rows: list[dict[str, str]]) -> list[tuple[str, ...]]:
    return [
        tuple(row[field] for field in ("review_item_id", *preliminary.SCORE_FIELDS, "review_notes"))
        for row in rows
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Confirm and unblind extension human scoring")
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--confirm-user-review", action="store_true")
    args = parser.parse_args()
    if not args.confirm_user_review:
        raise SystemExit("explicit --confirm-user-review is required")
    if args.release_id != RELEASE_ID:
        raise SystemExit("release ID does not match the completed v2 extension")
    existing = [str(path) for path in OUTPUT_PATHS if path.exists()]
    if existing:
        raise SystemExit("refusing to overwrite confirmed review outputs: " + ", ".join(existing))

    errors = preliminary_validator.validate(PROJECT_ROOT)
    if errors:
        raise SystemExit("preliminary review is invalid: " + "; ".join(errors))
    preliminary_rows = preliminary.read_csv(preliminary.OUTPUT_PATH)
    score_rows = preliminary.read_csv(preliminary.SCORES_PATH)
    if score_signature(preliminary_rows) != score_signature(score_rows):
        raise SystemExit("preliminary output and score map differ")

    automatic = read_json(AUTO_METRICS_PATH)
    method_order = list(automatic["method_order"])
    key = read_json(KEY_PATH)
    key_rows = validate_key(key, preliminary_rows, method_order)
    questions = read_questions()
    confirmed_rows = build_confirmed_rows(preliminary_rows)
    unblinded_rows = build_unblinded_rows(confirmed_rows, key_rows, questions)
    human = build_human_metrics(unblinded_rows, method_order)
    combined = build_combined_metrics(automatic, human)

    write_csv(CONFIRMED_CSV_PATH, confirmed_rows)
    write_csv(UNBLINDED_CSV_PATH, unblinded_rows)
    HUMAN_METRICS_PATH.write_text(
        json.dumps(human, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    COMBINED_METRICS_PATH.write_text(
        json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    SUMMARY_PATH.write_text(build_markdown(combined), encoding="utf-8")

    manifest = {
        "schema_version": "2.0",
        "artifact": "extension_blind_review_user_confirmation",
        "protocol_version": "v2",
        "release_id": RELEASE_ID,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "confirmation_source": "explicit_user_confirmation_after_review",
        "reviewer": CONFIRMED_REVIEWER,
        "review_status": CONFIRMED_STATUS,
        "row_count": 92,
        "scores_promoted_without_mutation": True,
        "input_hashes": {
            "immutable_blind_review": preliminary.sha256_file(preliminary.SOURCE_PATH),
            "preliminary_score_map": preliminary.sha256_file(preliminary.SCORES_PATH),
            "preliminary_output": preliminary.sha256_file(preliminary.OUTPUT_PATH),
            "blind_method_key": preliminary.sha256_file(KEY_PATH),
            "extension_dataset": preliminary.sha256_file(DATASET_PATH),
            "automatic_metrics": preliminary.sha256_file(AUTO_METRICS_PATH),
        },
        "output_hashes": {
            path.name: preliminary.sha256_file(path)
            for path in OUTPUT_PATHS
            if path != CONFIRMATION_MANIFEST_PATH
        },
        "limitations": combined["limitations"],
    }
    CONFIRMATION_MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("OK: user-confirmed blind review promoted without score mutation")
    print("OK: rows=92 methods=4 questions_per_method=23")
    print(f"OK: human_metrics={HUMAN_METRICS_PATH}")
    print(f"OK: combined_metrics={COMBINED_METRICS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
