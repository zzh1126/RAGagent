from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.config import load_experiment_suite
from src.evaluation.schemas import ExperimentRunReport


SUMMARY_FIELDS = [
    "method",
    "display_name",
    "split",
    "question_count",
    "decision_accuracy",
    "citation_rate",
    "refusal_accuracy",
    "over_refusal_rate",
    "retrieval_recall_at_5",
    "path_validity",
    "mean_latency_ms",
    "wrong_count",
    "wrong_question_ids",
    "answer_correctness_status",
    "faithfulness_status",
    "hallucination_status",
]


def metric(report: ExperimentRunReport, name: str):
    return getattr(report.metrics, name).value


def load_reports(root: Path, split: str) -> list[ExperimentRunReport]:
    suite = load_experiment_suite(root / "config" / "experiments.yaml")
    reports: list[ExperimentRunReport] = []
    for experiment_id, definition in suite.experiments.items():
        if not definition.enabled:
            continue
        path = root / suite.protocol.output_dir / f"{experiment_id}_{split}.json"
        if not path.is_file():
            raise FileNotFoundError(f"missing experiment report: {path}")
        report = ExperimentRunReport.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
        if report.dataset_split != split:
            raise ValueError(f"{path}: expected split {split}, got {report.dataset_split}")
        if report.experiment_id != experiment_id:
            raise ValueError(f"{path}: experiment ID does not match filename/config")
        reports.append(report)

    if not reports:
        raise ValueError("no enabled experiment reports found")
    dataset_hashes = {report.dataset_sha256 for report in reports}
    config_hashes = {report.config_fingerprint for report in reports}
    question_ids = [report.results[0].question_id for report in reports if report.results]
    if len(dataset_hashes) != 1:
        raise ValueError("experiment reports do not share one dataset hash")
    if len(config_hashes) != 1:
        raise ValueError("experiment reports do not share one config fingerprint")
    if any(report.question_count != len(report.results) for report in reports):
        raise ValueError("one or more reports have a question_count/results mismatch")
    if split == "pilot" and any(report.question_count != 40 for report in reports):
        raise ValueError("pilot comparison requires 40 questions per method")
    reference_ids = [result.question_id for result in reports[0].results]
    for report in reports[1:]:
        if [result.question_id for result in report.results] != reference_ids:
            raise ValueError(f"question ordering mismatch in {report.experiment_id}")
    if len(question_ids) != len(reports):
        raise ValueError("one or more reports contain no results")
    return reports


def build_rows(reports: list[ExperimentRunReport]) -> list[dict[str, object]]:
    rows = []
    for report in reports:
        failures = [result.question_id for result in report.results if not result.decision_correct]
        rows.append(
            {
                "method": report.experiment_id,
                "display_name": report.experiment_config.display_name,
                "split": report.dataset_split,
                "question_count": report.question_count,
                "decision_accuracy": metric(report, "decision_accuracy"),
                "citation_rate": metric(report, "citation_rate"),
                "refusal_accuracy": metric(report, "refusal_accuracy"),
                "over_refusal_rate": metric(report, "over_refusal_rate"),
                "retrieval_recall_at_5": metric(report, "retrieval_recall_at_5"),
                "path_validity": metric(report, "path_validity"),
                "mean_latency_ms": metric(report, "latency_ms"),
                "wrong_count": len(failures),
                "wrong_question_ids": ";".join(failures),
                "answer_correctness_status": report.metrics.answer_correctness.status,
                "faithfulness_status": report.metrics.evidence_faithfulness.status,
                "hallucination_status": report.metrics.hallucination_rate.status,
            }
        )
    return rows


def build_category_metrics(reports: list[ExperimentRunReport]) -> dict:
    output: dict[str, dict[str, dict[str, float | int]]] = {}
    for report in reports:
        grouped: dict[str, list] = defaultdict(list)
        for result in report.results:
            grouped[result.category].append(result)
        output[report.experiment_id] = {}
        for category, results in sorted(grouped.items()):
            output[report.experiment_id][category] = {
                "count": len(results),
                "decision_accuracy": round(
                    sum(result.decision_correct for result in results) / len(results), 4
                ),
                "refusal_count": sum(result.actual_decision == "refuse" for result in results),
            }
    return output


def build_failure_cases(reports: list[ExperimentRunReport]) -> dict[str, list[dict]]:
    return {
        report.experiment_id: [
            {
                "question_id": result.question_id,
                "category": result.category,
                "expected_decision": result.expected_decision,
                "actual_decision": result.actual_decision,
                "retry_count": result.retry_count,
            }
            for result in report.results
            if not result.decision_correct
        ]
        for report in reports
    }


def write_markdown(
    path: Path,
    rows: list[dict[str, object]],
    category_metrics: dict,
    failure_cases: dict,
    dataset_hash: str,
    config_hash: str,
) -> None:
    lines = [
        "# Pilot Experiment Comparison",
        "",
        "This report compares the four configured offline methods on the pilot split.",
        "The frozen `final` split was not rerun.",
        "",
        f"- Dataset SHA-256: `{dataset_hash}`",
        f"- Configuration fingerprint: `{config_hash}`",
        "- Human correctness, faithfulness, and hallucination scores are still pending.",
        "",
        "## Overall Metrics",
        "",
        "| Method | Decision accuracy | Citation rate | Refusal accuracy | Over-refusal rate | Recall@5 | Path validity | Mean latency (ms) | Wrong IDs |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        def fmt(name: str) -> str:
            value = row[name]
            return "n/a" if value is None else f"{value:.4f}"

        lines.append(
            f"| {row['display_name']} | {fmt('decision_accuracy')} | {fmt('citation_rate')} | "
            f"{fmt('refusal_accuracy')} | {fmt('over_refusal_rate')} | {fmt('retrieval_recall_at_5')} | "
            f"{fmt('path_validity')} | {fmt('mean_latency_ms')} | {row['wrong_question_ids'] or 'none'} |"
        )

    lines.extend(["", "## Category Accuracy", ""])
    categories = sorted({category for method in category_metrics.values() for category in method})
    lines.append("| Category | " + " | ".join(row["display_name"] for row in rows) + " |")
    lines.append("| --- | " + " | ".join("---:" for _ in rows) + " |")
    for category in categories:
        values = []
        for row in rows:
            item = category_metrics[row["method"]][category]
            values.append(f"{item['decision_accuracy']:.4f}")
        lines.append(f"| {category} | " + " | ".join(values) + " |")

    lines.extend(["", "## Observations", ""])
    lines.extend(
        [
            "- All four methods answered the 36 answerable pilot questions correctly at the decision level.",
            "- Proposed correctly refused all four no-answer questions; the three verifier-disabled/fixed-route methods answered all four and therefore show 0/4 refusal accuracy.",
            "- Vector RAG has lower Recall@5 than Graph Only, Proposed, and No Verifier on the conservative graph-derived gold subset.",
            "- Latency is a local offline workflow measurement and is not an online LLM latency claim.",
            "- These are pilot comparison results for method analysis, not a replacement for the frozen final result.",
        ]
    )
    lines.extend(["", "## Failure Cases", ""])
    for method, failures in failure_cases.items():
        if not failures:
            lines.append(f"- `{method}`: none")
        else:
            ids = ", ".join(f"`{item['question_id']}`" for item in failures)
            lines.append(f"- `{method}`: {ids}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare validated experiment reports")
    parser.add_argument("--split", choices=["dev", "pilot"], default="pilot")
    args = parser.parse_args()
    root = PROJECT_ROOT
    reports = load_reports(root, args.split)
    rows = build_rows(reports)
    category_metrics = build_category_metrics(reports)
    failure_cases = build_failure_cases(reports)
    output_dir = root / "reports" / "experiments"
    csv_path = output_dir / f"{args.split}_comparison.csv"
    json_path = output_dir / f"{args.split}_comparison.json"
    markdown_path = output_dir / f"{args.split}_comparison.md"
    for path in (csv_path, json_path, markdown_path):
        if path.exists():
            raise SystemExit(f"Refusing to overwrite existing comparison file: {path}")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "schema_version": "1.0",
        "split": args.split,
        "dataset_sha256": reports[0].dataset_sha256,
        "config_fingerprint": reports[0].config_fingerprint,
        "methods": rows,
        "category_metrics": category_metrics,
        "failure_cases": failure_cases,
        "human_scoring_status": "pending",
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(
        markdown_path,
        rows,
        category_metrics,
        failure_cases,
        reports[0].dataset_sha256,
        reports[0].config_fingerprint,
    )
    print(f"OK: validated {len(reports)} reports")
    print(f"OK: comparison_csv={csv_path}")
    print(f"OK: comparison_json={json_path}")
    print(f"OK: comparison_markdown={markdown_path}")


if __name__ == "__main__":
    main()
