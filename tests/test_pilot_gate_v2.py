from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.evaluation import pilot_gate


ROOT = Path(__file__).resolve().parents[1]


def synthetic_contract() -> dict:
    return {
        "dataset": {
            "question_count": 40,
            "answerable_count": 36,
            "no_answer_count": 4,
            "sha256": "dataset-hash",
        },
        "candidate": {
            "settings_sha256": "settings-hash",
            "generator_backend": "llm",
            "provider": "ollama",
            "model": "qwen3:4b",
            "prompt_version": "v2",
            "system_prompt_sha256": "prompt-hash",
            "wire_schema_sha256": "schema-hash",
            "evidence_packer_version": "intent_aware_v2",
        },
        "thresholds": {
            "minimum_decision_accuracy": 0.80,
            "minimum_structured_output_success_rate": 0.95,
            "maximum_fallback_rate": 0.05,
            "minimum_refusal_accuracy": 1.0,
            "maximum_over_refusal_rate": 0.25,
            "maximum_retry_rate": 0.70,
            "maximum_unsupported_claim_leakage_count": 0,
        },
    }


def passing_report() -> dict:
    return {
        "question_count": 40,
        "answerable_count": 36,
        "no_answer_count": 4,
        "dataset_sha256": "dataset-hash",
        "settings_sha256": "settings-hash",
        "implementation_commit": "a" * 40,
        "generator": {
            "requested_backend": "llm",
            "provider": "ollama",
            "model": "qwen3:4b",
            "prompt_version": "v2",
            "evidence_packer_version": "intent_aware_v2",
        },
        "prompt_contract": {
            "system_prompt_sha256": "prompt-hash",
            "wire_schema_sha256": "schema-hash",
        },
        "decision_accuracy": 0.90,
        "structured_output_success_rate": 1.0,
        "fallback_rate": 0.0,
        "refusal_accuracy": 1.0,
        "over_refusal_rate": 0.20,
        "retry_rate": 0.30,
        "unsupported_claim_leakage_count": 0,
    }


def test_committed_pilot_gate_contract_is_valid() -> None:
    assert pilot_gate.validate_gate_contract(ROOT) == []


def test_pilot_gate_requires_every_predeclared_check(monkeypatch) -> None:
    monkeypatch.setattr(pilot_gate, "validate_gate_contract", lambda root: [])
    monkeypatch.setattr(pilot_gate, "load_gate_contract", lambda root: synthetic_contract())
    monkeypatch.setattr(
        pilot_gate,
        "sha256_file",
        lambda path: f"hash:{Path(path).name}",
    )
    state = {
        "status": "completed_once",
        "implementation_commit": "a" * 40,
    }

    decision = pilot_gate.evaluate_pilot_report(
        ROOT,
        passing_report(),
        state,
        evaluated_at="2026-07-23T00:00:00+00:00",
    )
    assert decision["status"] == "go"
    assert decision["failed_check_ids"] == []
    assert decision["pilot_consumed"] is True
    assert decision["rerun_authorized"] is False

    failed_report = passing_report()
    failed_report["over_refusal_rate"] = 0.30
    failed = pilot_gate.evaluate_pilot_report(
        ROOT,
        failed_report,
        state,
        evaluated_at="2026-07-23T00:00:00+00:00",
    )
    assert failed["status"] == "no_go"
    assert failed["failed_check_ids"] == ["over_refusal_rate"]


def test_stage8_6_pilot_rejects_noncanonical_output_before_qa() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_evaluation.py",
            "--split",
            "pilot",
            "--output",
            "reports/not_the_stage8_6_pilot.json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode != 0
    assert "locked to the canonical output path" in completed.stdout + completed.stderr
    assert not (ROOT / "reports/not_the_stage8_6_pilot.json").exists()
