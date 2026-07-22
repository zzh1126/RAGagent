from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
METHODS = {"vector_rag", "graph_only", "proposed", "no_verifier"}
STATUS = "user_confirmed"
REVIEWER = "User-confirmed review of Codex-assisted scoring"
PRELIMINARY_STATUS = "preliminary_pending_user_confirmation"
KEY_FIELDS = ("method", "question_id")
SCORE_FIELDS = ("correctness_score", "faithfulness_score", "hallucination", "over_refusal")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def metric(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 4)


def main() -> None:
    blank_path = PROJECT_ROOT / "reports" / "human_scoring.csv"
    preliminary_path = PROJECT_ROOT / "reports" / "human_scoring_pilot_preliminary.csv"
    scored_path = PROJECT_ROOT / "reports" / "human_scoring_pilot_confirmed.csv"
    metrics_path = PROJECT_ROOT / "reports" / "experiments" / "pilot_human_metrics.json"
    preliminary_metrics_path = PROJECT_ROOT / "reports" / "experiments" / "pilot_human_metrics_preliminary.json"
    error_path = PROJECT_ROOT / "reports" / "experiments" / "pilot_error_analysis.md"
    blank_rows = read_csv(blank_path)
    preliminary_rows = read_csv(preliminary_path)
    scored_rows = read_csv(scored_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    preliminary_metrics = json.loads(preliminary_metrics_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    if len(blank_rows) != 160 or len(preliminary_rows) != 160 or len(scored_rows) != 160:
        errors.append(
            "expected 160 blank/preliminary/confirmed rows, got "
            f"{len(blank_rows)}/{len(preliminary_rows)}/{len(scored_rows)}"
        )
    if any(row["correctness_score"] or row["faithfulness_score"] for row in blank_rows):
        errors.append("the human scoring template must keep score fields blank")
    method_counts = Counter(row["method"] for row in scored_rows)
    if set(method_counts) != METHODS or any(count != 40 for count in method_counts.values()):
        errors.append(f"invalid method distribution: {dict(method_counts)}")
    keys = {(row["method"], row["question_id"]) for row in scored_rows}
    if len(keys) != len(scored_rows):
        errors.append("duplicate method/question scoring rows")

    if len(preliminary_rows) == len(scored_rows):
        for index, (preliminary, confirmed) in enumerate(zip(preliminary_rows, scored_rows)):
            for field in [*KEY_FIELDS, "question", *SCORE_FIELDS]:
                if preliminary.get(field) != confirmed.get(field):
                    errors.append(f"confirmed score changed at row {index + 1}: {field}")
            if preliminary.get("review_status") != PRELIMINARY_STATUS:
                errors.append(f"invalid archived preliminary status at row {index + 1}")

    for row in scored_rows:
        if row["correctness_score"] not in {"0", "1", "2"}:
            errors.append(f"invalid correctness score: {row['method']} {row['question_id']}")
        if row["faithfulness_score"] not in {"0", "1", "2"}:
            errors.append(f"invalid faithfulness score: {row['method']} {row['question_id']}")
        if row["hallucination"] not in {"0", "1"} or row["over_refusal"] not in {"0", "1"}:
            errors.append(f"invalid binary score: {row['method']} {row['question_id']}")
        if row["review_status"] != STATUS:
            errors.append(f"invalid review status: {row['method']} {row['question_id']}")
        if row["reviewer"] != REVIEWER:
            errors.append(f"invalid reviewer: {row['method']} {row['question_id']}")

    for method in METHODS:
        rows = [row for row in scored_rows if row["method"] == method]
        expected = metrics["methods"][method]
        recomputed = {
            "answer_correctness": metric(sum(int(row["correctness_score"]) for row in rows), 80),
            "evidence_faithfulness": metric(sum(int(row["faithfulness_score"]) for row in rows), 80),
            "hallucination_rate": metric(sum(int(row["hallucination"]) for row in rows), 40),
            "over_refusal_rate": metric(
                sum(int(row["over_refusal"]) for row in rows),
                sum(row["expected_decision"] == "pass" for row in rows),
            ),
        }
        for name, value in recomputed.items():
            if expected[name]["value"] != value:
                errors.append(f"metric mismatch for {method} {name}: {value} != {expected[name]['value']}")

    case_count = sum(
        line.startswith("| E") for line in error_path.read_text(encoding="utf-8").splitlines()
    )
    if case_count < 8:
        errors.append(f"error analysis requires at least 8 cases, got {case_count}")
    if metrics.get("review_status") != STATUS:
        errors.append("metrics JSON must have user_confirmed review status")
    if preliminary_metrics.get("review_status") != PRELIMINARY_STATUS:
        errors.append("preliminary metrics archive must retain its historical status")
    for method in METHODS:
        if metrics["methods"][method].get("scoring_status") != STATUS:
            errors.append(f"confirmed metrics status mismatch: {method}")
        for metric_name in ("answer_correctness", "evidence_faithfulness", "hallucination_rate", "over_refusal_rate"):
            confirmed_value = metrics["methods"][method][metric_name]["value"]
            preliminary_value = preliminary_metrics["methods"][method][metric_name]["value"]
            if confirmed_value != preliminary_value:
                errors.append(f"confirmed metric changed: {method} {metric_name}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("OK: user-confirmed scoring artifacts are internally consistent")
    print(f"OK: rows={len(scored_rows)} methods={dict(method_counts)} error_cases={case_count}")
    print(f"OK: review_status={STATUS}")


if __name__ == "__main__":
    main()
