"""Historical pre-confirmation summarizer.

The current report uses the artifacts produced by
``scripts/confirm_pilot_scoring.py``. This script remains available to
reproduce the original preliminary summary for audit purposes.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FIELDS = [
    "method",
    "decision_accuracy",
    "answer_correctness_preliminary",
    "evidence_faithfulness_preliminary",
    "retrieval_recall_at_5",
    "path_validity",
    "refusal_accuracy",
    "hallucination_rate_preliminary",
    "over_refusal_rate",
    "mean_latency_ms",
    "review_status",
]


def main() -> None:
    auto_path = PROJECT_ROOT / "reports" / "experiments" / "pilot_comparison.json"
    human_path = PROJECT_ROOT / "reports" / "experiments" / "pilot_human_metrics.json"
    auto = json.loads(auto_path.read_text(encoding="utf-8"))
    human = json.loads(human_path.read_text(encoding="utf-8"))
    auto_by_method = {row["method"]: row for row in auto["methods"]}
    if set(auto_by_method) != set(human["methods"]):
        raise ValueError("automatic and preliminary scoring methods do not match")

    rows = []
    for method, auto_row in auto_by_method.items():
        human_row = human["methods"][method]
        rows.append(
            {
                "method": method,
                "decision_accuracy": auto_row["decision_accuracy"],
                "answer_correctness_preliminary": human_row["answer_correctness"]["value"],
                "evidence_faithfulness_preliminary": human_row["evidence_faithfulness"]["value"],
                "retrieval_recall_at_5": auto_row["retrieval_recall_at_5"],
                "path_validity": auto_row["path_validity"],
                "refusal_accuracy": auto_row["refusal_accuracy"],
                "hallucination_rate_preliminary": human_row["hallucination_rate"]["value"],
                "over_refusal_rate": human_row["over_refusal_rate"]["value"],
                "mean_latency_ms": auto_row["mean_latency_ms"],
                "review_status": human_row["scoring_status"],
            }
        )

    csv_path = PROJECT_ROOT / "reports" / "metrics_summary.csv"
    markdown_path = PROJECT_ROOT / "reports" / "metrics_summary.md"
    for path in (csv_path, markdown_path):
        if path.exists():
            raise SystemExit(f"Refusing to overwrite metrics summary: {path}")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Pilot Metrics Summary",
        "",
        "Automatic experiment metrics are combined with Codex-assisted preliminary semantic scores.",
        "The preliminary columns require user confirmation before being described as human evaluation.",
        "The frozen final split was not rerun.",
        "",
        "| Method | Decision acc. | Answer correctness* | Faithfulness* | Recall@5 | Path validity | Refusal acc. | Hallucination* | Over-refusal | Latency (ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        def fmt(name: str) -> str:
            value = row[name]
            return "n/a" if value is None else f"{value:.4f}"

        lines.append(
            f"| {row['method']} | {fmt('decision_accuracy')} | "
            f"{fmt('answer_correctness_preliminary')} | "
            f"{fmt('evidence_faithfulness_preliminary')} | "
            f"{fmt('retrieval_recall_at_5')} | {fmt('path_validity')} | "
            f"{fmt('refusal_accuracy')} | {fmt('hallucination_rate_preliminary')} | "
            f"{fmt('over_refusal_rate')} | {fmt('mean_latency_ms')} |"
        )
    lines.extend(
        [
            "",
            "`*` Codex-assisted preliminary semantic review, status: `preliminary_pending_user_confirmation`.",
            "",
            "Interpretation: Proposed has the strongest preliminary correctness and faithfulness among the four methods, while its main verified gain is 4/4 no-answer refusal. The zero preliminary hallucination rate means the observed failures were mostly irrelevant or incomplete but cited answers, not unsupported professional facts.",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: metrics_csv={csv_path}")
    print(f"OK: metrics_markdown={markdown_path}")


if __name__ == "__main__":
    main()
