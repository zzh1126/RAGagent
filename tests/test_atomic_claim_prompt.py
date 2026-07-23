from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from scripts.probe_atomic_claim_prompt import (
    SCENARIOS,
    prompt_sha256,
    summarize_results,
    validate_atomic_draft,
    wire_schema_sha256,
)
from scripts.validate_atomic_claim_prompt import find_forbidden_raw_keys
from src.agent.generators.llm_generator import (
    ANSWER_PROMPT_VERSION,
    LLMAnswerDraft,
    MAX_LLM_CLAIMS,
    SYSTEM_PROMPT,
)


def random_forest_draft() -> LLMAnswerDraft:
    return LLMAnswerDraft.model_validate(
        {
            "answer": "随机森林属于集成学习，平均预测可以降低方差。",
            "claims": [
                {
                    "claim": "随机森林属于集成学习。",
                    "evidence_ids": ["E1"],
                    "graph_path_ids": ["P1"],
                    "relation_id": "R1",
                    "supporting_quotes": [
                        {
                            "evidence_id": "E1",
                            "quote": (
                                "Random forests are ensemble methods based on randomized "
                                "decision trees."
                            ),
                        }
                    ],
                },
                {
                    "claim": "随机森林的平均预测可以降低方差。",
                    "evidence_ids": ["E2"],
                    "graph_path_ids": [],
                    "relation_id": "",
                    "supporting_quotes": [
                        {
                            "evidence_id": "E2",
                            "quote": "Averaging reduces variance.",
                        }
                    ],
                },
            ],
            "graph_paths": ["P1"],
            "unsupported_claims": [],
            "confidence": 0.9,
        }
    )


def test_prompt_v2_exposes_atomic_claim_contract() -> None:
    assert ANSWER_PROMPT_VERSION == "v2"
    assert MAX_LLM_CLAIMS == 4
    assert "1 到 4 条 Claims" in SYSTEM_PROMPT
    assert "只能表达一个可独立判断真假的专业事实" in SYSTEM_PROMPT
    assert "连续逐字复制" in SYSTEM_PROMPT
    assert "禁止把 P/R ID 填入 evidence_ids" in SYSTEM_PROMPT


def test_frozen_prompt_contract_matches_runtime_hashes() -> None:
    contract = yaml.safe_load(
        Path("config/atomic_claim_prompt_v2.yaml").read_text(encoding="utf-8")
    )

    assert contract["implementation"]["system_prompt_sha256"] == prompt_sha256()
    assert contract["implementation"]["wire_schema_sha256"] == wire_schema_sha256()


def test_wire_schema_rejects_fifth_claim() -> None:
    payload = random_forest_draft().model_dump(mode="json")
    payload["claims"] = [payload["claims"][0]] * 5

    with pytest.raises(ValidationError, match="at most 4 items"):
        LLMAnswerDraft.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_ids", []),
        ("supporting_quotes", []),
    ],
)
def test_wire_schema_requires_evidence_and_quote(field: str, value: list) -> None:
    payload = random_forest_draft().model_dump(mode="json")
    payload["claims"][0][field] = value

    with pytest.raises(ValidationError):
        LLMAnswerDraft.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_ids", ["P1"]),
        ("graph_path_ids", ["E1"]),
        ("relation_id", "P1"),
    ],
)
def test_wire_schema_enforces_e_p_r_id_namespaces(field: str, value) -> None:
    payload = random_forest_draft().model_dump(mode="json")
    payload["claims"][0][field] = value

    with pytest.raises(ValidationError):
        LLMAnswerDraft.model_validate(payload)


def test_wire_schema_rejects_unknown_fields() -> None:
    payload = random_forest_draft().model_dump(mode="json")
    payload["claims"][0]["invented_field"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        LLMAnswerDraft.model_validate(payload)


def test_atomic_probe_accepts_separate_supported_facts() -> None:
    assert validate_atomic_draft(random_forest_draft(), SCENARIOS[0]) == []


def test_atomic_probe_rejects_compound_claim() -> None:
    draft = LLMAnswerDraft.model_validate(
        {
            "answer": "随机森林属于集成学习并通过平均降低方差。",
            "claims": [
                {
                    "claim": "随机森林属于集成学习，并且随机森林的平均预测降低方差。",
                    "evidence_ids": ["E1", "E2"],
                    "graph_path_ids": ["P1"],
                    "relation_id": "R1",
                    "supporting_quotes": [
                        {
                            "evidence_id": "E1",
                            "quote": (
                                "Random forests are ensemble methods based on randomized "
                                "decision trees."
                            ),
                        },
                        {
                            "evidence_id": "E2",
                            "quote": "Averaging reduces variance.",
                        },
                    ],
                }
            ],
            "graph_paths": ["P1"],
            "unsupported_claims": [],
            "confidence": 0.8,
        }
    )

    errors = validate_atomic_draft(draft, SCENARIOS[0])

    assert "claim_1:fact_match_count_2" in errors
    assert "fact_rf_family:count_0" in errors
    assert "fact_rf_variance:count_0" in errors


def test_atomic_probe_requires_case_preserving_verbatim_quote() -> None:
    draft = random_forest_draft()
    draft.claims[0].supporting_quotes[0].quote = (
        "random forests are ensemble methods based on randomized decision trees."
    )

    assert "claim_1:quote_not_verbatim" in validate_atomic_draft(
        draft,
        SCENARIOS[0],
    )


def test_atomic_probe_accepts_supported_fact_and_explicit_gap() -> None:
    draft = LLMAnswerDraft.model_validate(
        {
            "answer": "KMeans 最小化簇内距离平方和。",
            "claims": [
                {
                    "claim": "KMeans 最小化簇内距离平方和。",
                    "evidence_ids": ["E1"],
                    "graph_path_ids": [],
                    "relation_id": "",
                    "supporting_quotes": [
                        {
                            "evidence_id": "E1",
                            "quote": (
                                "KMeans minimizes the within-cluster sum of squared distances."
                            ),
                        }
                    ],
                }
            ],
            "graph_paths": [],
            "unsupported_claims": ["当前证据没有给出默认最大迭代次数。"],
            "confidence": 0.7,
        }
    )

    assert validate_atomic_draft(draft, SCENARIOS[3]) == []


def test_probe_summary_requires_nineteen_of_twenty_successes() -> None:
    results = []
    for index in range(20):
        results.append(
            {
                "scenario": SCENARIOS[index % len(SCENARIOS)].name,
                "success": index < 19,
                "schema_valid": True,
                "error_type": None,
                "latency_ms": 100.0,
            }
        )

    summary = summarize_results(results, minimum_successes=19)

    assert summary["semantic_successes"] == 19
    assert summary["gate_passed"] is True


def test_probe_report_raw_content_guard_is_recursive() -> None:
    report = {
        "results": [
            {
                "run_index": 1,
                "nested": {"content": "must not be persisted"},
            }
        ]
    }

    assert find_forbidden_raw_keys(report) == ["root.results[0].nested.content"]
