from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.config import load_experiment_suite
from src.evaluation.schemas import ExperimentRunReport


FIELDS = [
    "question_id",
    "method",
    "question",
    "category",
    "expected_decision",
    "actual_decision",
    "correctness_score",
    "faithfulness_score",
    "hallucination",
    "over_refusal",
    "notes",
    "reviewer",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a blank human scoring sheet from pilot reports")
    parser.add_argument("--split", choices=["dev", "pilot"], default="pilot")
    args = parser.parse_args()
    root = PROJECT_ROOT
    suite = load_experiment_suite(root / "config" / "experiments.yaml")
    rows: list[dict[str, str]] = []
    for experiment_id, definition in suite.experiments.items():
        if not definition.enabled:
            continue
        path = root / suite.protocol.output_dir / f"{experiment_id}_{args.split}.json"
        report = ExperimentRunReport.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
        for result in report.results:
            rows.append(
                {
                    "question_id": result.question_id,
                    "method": experiment_id,
                    "question": result.question,
                    "category": result.category,
                    "expected_decision": result.expected_decision,
                    "actual_decision": result.actual_decision,
                    "correctness_score": "",
                    "faithfulness_score": "",
                    "hallucination": "",
                    "over_refusal": "",
                    "notes": "",
                    "reviewer": "",
                }
            )

    output = root / "reports" / "human_scoring.csv"
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing scoring sheet: {output}")
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"OK: created {len(rows)} blank scoring rows at {output}")


if __name__ == "__main__":
    main()
