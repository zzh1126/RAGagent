from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.probe_atomic_claim_prompt import (
    SCENARIOS,
    prompt_sha256,
    summarize_results,
    wire_schema_sha256,
)
from src.agent.generators.llm_generator import (
    ANSWER_PROMPT_VERSION,
    LLMAnswerDraft,
    MAX_LLM_CLAIMS,
)


CONTRACT_PATH = PROJECT_ROOT / "config" / "atomic_claim_prompt_v2.yaml"
REPORT_PATH = PROJECT_ROOT / "reports" / "llm_atomic_claim_prompt_v2_probe.json"
FORBIDDEN_RAW_KEYS = {
    "answer",
    "claims",
    "content",
    "draft",
    "messages",
    "parsed_output",
    "quote",
    "raw_content",
    "raw_prompt",
    "system_prompt",
    "supporting_quotes",
    "thinking",
    "user_context",
    "user_prompt",
}


def find_forbidden_raw_keys(value, path: str = "root") -> list[str]:
    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            current = f"{path}.{key_text}"
            if key_text in FORBIDDEN_RAW_KEYS:
                errors.append(current)
            errors.extend(find_forbidden_raw_keys(item, current))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            errors.extend(find_forbidden_raw_keys(item, f"{path}[{index}]"))
    return errors


def main() -> None:
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []
    implementation = contract.get("implementation") or {}
    claim_contract = contract.get("claim_contract") or {}
    probe_contract = contract.get("formal_probe") or {}

    if contract.get("artifact") != "atomic_claim_prompt_contract":
        errors.append("invalid atomic Claim Prompt contract artifact")
    if contract.get("status") != "frozen_stage_8_2":
        errors.append("atomic Claim Prompt contract is not frozen")
    if contract.get("prompt_version") != ANSWER_PROMPT_VERSION:
        errors.append("Prompt version differs from the frozen contract")
    if ANSWER_PROMPT_VERSION != "v2":
        errors.append("current Prompt version is not v2")
    if implementation.get("maximum_claims") != MAX_LLM_CLAIMS:
        errors.append("maximum Claim count differs from runtime")
    if implementation.get("system_prompt_sha256") != prompt_sha256():
        errors.append("system Prompt SHA-256 differs from the frozen contract")
    if implementation.get("wire_schema_sha256") != wire_schema_sha256():
        errors.append("wire Schema SHA-256 differs from the frozen contract")

    schema = LLMAnswerDraft.model_json_schema()
    claims_schema = (schema.get("properties") or {}).get("claims") or {}
    if claims_schema.get("minItems") != 1 or claims_schema.get("maxItems") != 4:
        errors.append("wire Schema must constrain Claims to 1..4")
    claim_properties = (
        ((schema.get("$defs") or {}).get("LLMAnswerClaim") or {}).get("properties")
        or {}
    )
    evidence_items = (claim_properties.get("evidence_ids") or {}).get("items") or {}
    path_items = (claim_properties.get("graph_path_ids") or {}).get("items") or {}
    relation_schema = claim_properties.get("relation_id") or {}
    if evidence_items.get("pattern") != claim_contract.get("evidence_id_pattern"):
        errors.append("wire Schema evidence ID namespace differs from the contract")
    if path_items.get("pattern") != claim_contract.get("graph_path_id_pattern"):
        errors.append("wire Schema graph path ID namespace differs from the contract")
    if relation_schema.get("pattern") != claim_contract.get("relation_id_pattern"):
        errors.append("wire Schema relation ID namespace differs from the contract")

    if report.get("artifact") != "atomic_claim_prompt_probe":
        errors.append("invalid atomic Claim Prompt probe artifact")
    if report.get("model") != probe_contract.get("model"):
        errors.append("probe model differs from the frozen contract")
    if report.get("prompt_version") != ANSWER_PROMPT_VERSION:
        errors.append("probe Prompt version differs from runtime")
    if report.get("system_prompt_sha256") != prompt_sha256():
        errors.append("probe Prompt hash differs from runtime")
    if report.get("wire_schema_sha256") != wire_schema_sha256():
        errors.append("probe wire Schema hash differs from runtime")

    stored_probe_contract = report.get("probe_contract") or {}
    expected_scenarios = [scenario.name for scenario in SCENARIOS]
    if stored_probe_contract.get("scenario_names") != expected_scenarios:
        errors.append("probe scenarios differ from the runtime definitions")
    if probe_contract.get("scenarios") != expected_scenarios:
        errors.append("frozen probe scenario order differs from runtime")
    if stored_probe_contract.get("maximum_claims") != MAX_LLM_CLAIMS:
        errors.append("probe maximum Claim count differs from runtime")
    for field in (
        "raw_prompt_recorded",
        "raw_content_recorded",
        "raw_thinking_recorded",
    ):
        if stored_probe_contract.get(field) is not False:
            errors.append(f"probe must set {field}=false")
        if probe_contract.get(field) is not False:
            errors.append(f"frozen contract must set {field}=false")

    raw_key_paths = find_forbidden_raw_keys(report)
    if raw_key_paths:
        errors.append("probe report contains raw content keys: " + ", ".join(raw_key_paths))

    results = report.get("results") or []
    summary = report.get("summary") or {}
    expected_runs = int(probe_contract.get("total_runs", 0))
    minimum_successes = int(probe_contract.get("minimum_successes", 0))
    if len(results) != expected_runs:
        errors.append(f"expected {expected_runs} probe rows, got {len(results)}")
    if results:
        recomputed = summarize_results(results, minimum_successes)
        if recomputed != summary:
            errors.append("stored probe summary differs from recomputed results")
    if summary.get("semantic_successes", 0) < minimum_successes:
        errors.append("atomic Claim Prompt probe did not meet the success gate")
    if summary.get("gate_passed") is not True:
        errors.append("atomic Claim Prompt probe gate is not passed")
    scenario_counts = {
        scenario_name: sum(row.get("scenario") == scenario_name for row in results)
        for scenario_name in expected_scenarios
    }
    if scenario_counts and len(set(scenario_counts.values())) != 1:
        errors.append("formal probe scenarios are not evenly represented")
    for row in results:
        if row.get("schema_valid") and not 1 <= int(row.get("claim_count", 0)) <= 4:
            errors.append(f"run {row.get('run_index')} has an invalid Claim count")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print("OK: atomic Claim Prompt v2 contract and probe are valid")
    print(
        f"OK: prompt_sha256={prompt_sha256()} "
        f"wire_schema_sha256={wire_schema_sha256()}"
    )
    print(
        f"OK: probe={summary['semantic_successes']}/{summary['total_runs']} "
        f"scenarios={scenario_counts} raw_content_recorded=false"
    )


if __name__ == "__main__":
    main()
