from __future__ import annotations

import json
from pathlib import Path

from probe_llm_structured import summarize_results


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "reports" / "llm_probe_qwen3_4b.json"
EXPECTED_SCENARIOS = ["simple_status", "query_plan", "nested_answer"]


def main() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []
    contract = report.get("probe_contract") or {}
    results = report.get("results") or []
    summary = report.get("summary") or {}

    if report.get("model") != "qwen3:4b":
        errors.append(f"unexpected model: {report.get('model')}")
    if contract.get("runs_per_schema") != 20:
        errors.append("formal probe must use 20 runs per schema")
    if contract.get("scenario_names") != EXPECTED_SCENARIOS:
        errors.append(f"unexpected scenarios: {contract.get('scenario_names')}")
    if contract.get("think") is not False or contract.get("stream") is not False:
        errors.append("formal probe must use think=false and stream=false")
    if contract.get("thinking_content_recorded") is not False:
        errors.append("thinking content must not be recorded")
    if len(results) != 60:
        errors.append(f"expected 60 result rows, got {len(results)}")
    if any("thinking" in row for row in results):
        errors.append("raw thinking content is present in a result row")

    if results and summary:
        recomputed = summarize_results(
            results,
            scenario_names=EXPECTED_SCENARIOS,
            minimum_success_rate=float(summary["minimum_success_rate"]),
            target_gate=str(summary["target_gate"]),
        )
        if recomputed != summary:
            errors.append("stored summary does not match recomputed result rows")

    expected_gates = {
        "structured_output_gate_passed": True,
        "generator_gate_passed": True,
        "planner_gate_passed": False,
        "full_agent_gate_passed": False,
        "target_gate": "generator",
        "gate_passed": True,
    }
    for field, expected in expected_gates.items():
        if summary.get(field) != expected:
            errors.append(f"unexpected {field}: {summary.get(field)} != {expected}")

    expected_semantic_successes = {
        "simple_status": 20,
        "query_plan": 1,
        "nested_answer": 20,
    }
    for scenario, expected in expected_semantic_successes.items():
        actual = (summary.get("per_scenario") or {}).get(scenario, {}).get("semantic_successes")
        if actual != expected:
            errors.append(f"unexpected semantic successes for {scenario}: {actual} != {expected}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print("OK: qwen3:4b formal structured-output probe is internally consistent")
    print("OK: schema=60/60 simple=20/20 nested_answer=20/20 planner=1/20")
    print("OK: decision=generator_go planner_no_go")


if __name__ == "__main__":
    main()
