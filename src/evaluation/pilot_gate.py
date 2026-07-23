from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.evaluation.extension_release import prompt_contract, sha256_file


PILOT_GATE_CONTRACT_PATH = Path("config/pilot_freeze_gate_v2.yaml")
PILOT_REPORT_PATH = Path("reports/evaluation_llm_agent_v2_pilot_stage8_6.json")
PILOT_STATE_PATH = Path(
    "reports/evaluation_llm_agent_v2_pilot_stage8_6_state.json"
)
PILOT_GATE_DECISION_PATH = Path(
    "reports/evaluation_llm_agent_v2_pilot_stage8_6_gate.json"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_gate_contract(root: Path) -> dict[str, Any]:
    value = yaml.safe_load(
        (root / PILOT_GATE_CONTRACT_PATH).read_text(encoding="utf-8")
    )
    if not isinstance(value, dict):
        raise ValueError("pilot freeze gate contract must contain a YAML mapping")
    return value


def validate_gate_contract(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        contract = load_gate_contract(root)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [f"unable to read pilot freeze gate contract: {exc}"]

    if contract.get("artifact") != "llm_agent_v2_pilot_freeze_gate":
        errors.append("invalid pilot freeze gate artifact")
    if contract.get("status") != "frozen_before_stage8_6_pilot":
        errors.append("pilot freeze gate is not frozen before execution")

    dataset = contract.get("dataset")
    if not isinstance(dataset, dict):
        errors.append("pilot gate dataset must be a mapping")
        dataset = {}
    dataset_path = Path(str(dataset.get("path", "")))
    if dataset_path != Path("data/evaluation/pilot_questions.jsonl"):
        errors.append("pilot gate dataset path mismatch")
    elif not (root / dataset_path).is_file():
        errors.append("pilot gate dataset does not exist")
    elif dataset.get("sha256") != sha256_file(root / dataset_path):
        errors.append("pilot gate dataset hash mismatch")
    if dataset.get("question_count") != 40:
        errors.append("pilot gate question count must be 40")
    if dataset.get("answerable_count") != 36:
        errors.append("pilot gate answerable count must be 36")
    if dataset.get("no_answer_count") != 4:
        errors.append("pilot gate no-answer count must be 4")

    candidate = contract.get("candidate")
    if not isinstance(candidate, dict):
        errors.append("pilot gate candidate must be a mapping")
        candidate = {}
    if candidate.get("settings_sha256") != sha256_file(
        root / "config/settings.yaml"
    ):
        errors.append("pilot gate settings hash mismatch")
    current_prompt = prompt_contract()
    if candidate.get("prompt_version") != current_prompt["version"]:
        errors.append("pilot gate prompt version mismatch")
    if candidate.get("system_prompt_sha256") != current_prompt[
        "system_prompt_sha256"
    ]:
        errors.append("pilot gate system prompt hash mismatch")
    if candidate.get("wire_schema_sha256") != current_prompt[
        "wire_schema_sha256"
    ]:
        errors.append("pilot gate wire schema hash mismatch")

    governance = contract.get("governance")
    if not isinstance(governance, dict):
        errors.append("pilot gate governance must be a mapping")
        governance = {}
    expected_paths = {
        "canonical_output": PILOT_REPORT_PATH.as_posix(),
        "execution_state": PILOT_STATE_PATH.as_posix(),
        "decision_output": PILOT_GATE_DECISION_PATH.as_posix(),
    }
    for field, expected in expected_paths.items():
        if governance.get(field) != expected:
            errors.append(f"pilot gate governance {field} mismatch")
    if governance.get("maximum_runs") != 1:
        errors.append("pilot gate must permit exactly one run")
    if governance.get("overwrite_outputs") is not False:
        errors.append("pilot gate must forbid output overwrite")
    if governance.get("rerun_after_failure") is not False:
        errors.append("pilot gate must forbid reruns after failure")
    if governance.get("go_requires_all_checks") is not True:
        errors.append("pilot gate must require every check to pass")
    return errors


def _check(
    check_id: str,
    actual: Any,
    target: Any,
    operator: str,
) -> dict[str, Any]:
    if operator == "eq":
        passed = actual == target
    elif operator == "gte":
        passed = isinstance(actual, (int, float)) and actual >= target
    elif operator == "lte":
        passed = isinstance(actual, (int, float)) and actual <= target
    else:
        raise ValueError(f"unsupported pilot gate operator: {operator}")
    return {
        "check_id": check_id,
        "operator": operator,
        "target": target,
        "actual": actual,
        "passed": passed,
    }


def evaluate_pilot_report(
    root: Path,
    report: dict[str, Any],
    state: dict[str, Any],
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    contract_errors = validate_gate_contract(root)
    if contract_errors:
        raise ValueError("; ".join(contract_errors))
    contract = load_gate_contract(root)
    dataset = contract["dataset"]
    candidate = contract["candidate"]
    thresholds = contract["thresholds"]
    generator = report.get("generator", {})
    report_prompt = report.get("prompt_contract", {})

    checks = [
        _check("state_status", state.get("status"), "completed_once", "eq"),
        _check("question_count", report.get("question_count"), dataset["question_count"], "eq"),
        _check("answerable_count", report.get("answerable_count"), dataset["answerable_count"], "eq"),
        _check("no_answer_count", report.get("no_answer_count"), dataset["no_answer_count"], "eq"),
        _check("dataset_sha256", report.get("dataset_sha256"), dataset["sha256"], "eq"),
        _check(
            "settings_sha256",
            report.get("settings_sha256"),
            candidate["settings_sha256"],
            "eq",
        ),
        _check(
            "implementation_commit",
            report.get("implementation_commit"),
            state.get("implementation_commit"),
            "eq",
        ),
        _check(
            "generator_backend",
            generator.get("requested_backend"),
            candidate["generator_backend"],
            "eq",
        ),
        _check("provider", generator.get("provider"), candidate["provider"], "eq"),
        _check("model", generator.get("model"), candidate["model"], "eq"),
        _check(
            "prompt_version",
            generator.get("prompt_version"),
            candidate["prompt_version"],
            "eq",
        ),
        _check(
            "system_prompt_sha256",
            report_prompt.get("system_prompt_sha256"),
            candidate["system_prompt_sha256"],
            "eq",
        ),
        _check(
            "wire_schema_sha256",
            report_prompt.get("wire_schema_sha256"),
            candidate["wire_schema_sha256"],
            "eq",
        ),
        _check(
            "evidence_packer_version",
            generator.get("evidence_packer_version"),
            candidate["evidence_packer_version"],
            "eq",
        ),
        _check(
            "decision_accuracy",
            report.get("decision_accuracy"),
            thresholds["minimum_decision_accuracy"],
            "gte",
        ),
        _check(
            "structured_output_success_rate",
            report.get("structured_output_success_rate"),
            thresholds["minimum_structured_output_success_rate"],
            "gte",
        ),
        _check(
            "fallback_rate",
            report.get("fallback_rate"),
            thresholds["maximum_fallback_rate"],
            "lte",
        ),
        _check(
            "refusal_accuracy",
            report.get("refusal_accuracy"),
            thresholds["minimum_refusal_accuracy"],
            "gte",
        ),
        _check(
            "over_refusal_rate",
            report.get("over_refusal_rate"),
            thresholds["maximum_over_refusal_rate"],
            "lte",
        ),
        _check(
            "retry_rate",
            report.get("retry_rate"),
            thresholds["maximum_retry_rate"],
            "lte",
        ),
        _check(
            "unsupported_claim_leakage_count",
            report.get("unsupported_claim_leakage_count"),
            thresholds["maximum_unsupported_claim_leakage_count"],
            "lte",
        ),
    ]
    passed = all(item["passed"] for item in checks)
    return {
        "schema_version": "1.0",
        "artifact": "llm_agent_v2_pilot_freeze_gate_decision",
        "protocol_version": "v2",
        "status": "go" if passed else "no_go",
        "evaluated_at": evaluated_at or utc_now(),
        "pilot_consumed": True,
        "rerun_authorized": False,
        "per_question_tuning_authorized": False,
        "contract_path": PILOT_GATE_CONTRACT_PATH.as_posix(),
        "contract_sha256": sha256_file(root / PILOT_GATE_CONTRACT_PATH),
        "report_path": PILOT_REPORT_PATH.as_posix(),
        "report_sha256": sha256_file(root / PILOT_REPORT_PATH),
        "state_path": PILOT_STATE_PATH.as_posix(),
        "state_sha256": sha256_file(root / PILOT_STATE_PATH),
        "implementation_commit": report.get("implementation_commit"),
        "checks": checks,
        "failed_check_ids": [
            item["check_id"] for item in checks if not item["passed"]
        ],
        "interpretation": (
            "engineering_freeze_gate_not_independent_quality_evidence"
        ),
    }
