from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.generators.llm_generator import (
    ANSWER_PROMPT_VERSION,
    LLMAnswerDraft,
    MAX_LLM_CLAIMS,
    SYSTEM_PROMPT,
)
from src.llm import LLMError, LLMSettings, OllamaClient


DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "llm_atomic_claim_prompt_v2_probe.json"


@dataclass(frozen=True)
class FactRule:
    fact_id: str
    marker_groups: tuple[tuple[str, ...], ...]
    evidence_ids: tuple[str, ...]
    graph_path_ids: tuple[str, ...] = ()
    relation_id: str = ""


@dataclass(frozen=True)
class AtomicProbeScenario:
    name: str
    user_context: str
    evidence_texts: dict[str, str]
    valid_graph_path_ids: tuple[str, ...]
    valid_relation_ids: tuple[str, ...]
    facts: tuple[FactRule, ...]
    unsupported_markers: tuple[str, ...] = ()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def prompt_sha256() -> str:
    return hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()


def wire_schema_sha256() -> str:
    return canonical_sha256(LLMAnswerDraft.model_json_schema())


def normalize_match_text(value: str) -> str:
    return " ".join(value.casefold().replace("-", " ").split())


def normalize_verbatim_text(value: str) -> str:
    return " ".join(value.split())


def matches_fact(claim: str, fact: FactRule) -> bool:
    normalized = normalize_match_text(claim)
    return all(
        any(normalize_match_text(marker) in normalized for marker in group)
        for group in fact.marker_groups
    )


def validate_atomic_draft(
    draft: LLMAnswerDraft,
    scenario: AtomicProbeScenario,
) -> list[str]:
    errors: list[str] = []
    valid_evidence_ids = set(scenario.evidence_texts)
    valid_path_ids = set(scenario.valid_graph_path_ids)
    valid_relation_ids = set(scenario.valid_relation_ids)
    fact_counts = {fact.fact_id: 0 for fact in scenario.facts}
    used_paths: list[str] = []

    for index, claim in enumerate(draft.claims, start=1):
        prefix = f"claim_{index}"
        evidence_ids = set(claim.evidence_ids)
        path_ids = set(claim.graph_path_ids)
        quote_ids = {quote.evidence_id for quote in claim.supporting_quotes}
        if not evidence_ids.issubset(valid_evidence_ids):
            errors.append(f"{prefix}:unknown_evidence_id")
        if not path_ids.issubset(valid_path_ids):
            errors.append(f"{prefix}:unknown_graph_path_id")
        if claim.relation_id and claim.relation_id not in valid_relation_ids:
            errors.append(f"{prefix}:unknown_relation_id")
        if quote_ids != evidence_ids:
            errors.append(f"{prefix}:quote_coverage_mismatch")

        for quote in claim.supporting_quotes:
            source = scenario.evidence_texts.get(quote.evidence_id)
            if source is None:
                continue
            if normalize_verbatim_text(quote.quote) not in normalize_verbatim_text(source):
                errors.append(f"{prefix}:quote_not_verbatim")

        matched = [fact for fact in scenario.facts if matches_fact(claim.claim, fact)]
        if len(matched) != 1:
            errors.append(
                f"{prefix}:fact_match_count_{len(matched)}"
            )
        else:
            fact = matched[0]
            fact_counts[fact.fact_id] += 1
            if evidence_ids != set(fact.evidence_ids):
                errors.append(f"{prefix}:wrong_evidence_for_{fact.fact_id}")
            if not path_ids.issubset(set(fact.graph_path_ids)):
                errors.append(f"{prefix}:wrong_path_for_{fact.fact_id}")
            if path_ids and claim.relation_id != fact.relation_id:
                errors.append(f"{prefix}:wrong_relation_for_{fact.fact_id}")
            if not path_ids and claim.relation_id:
                errors.append(f"{prefix}:relation_without_path")

        normalized_claim = normalize_match_text(claim.claim)
        if any(
            normalize_match_text(marker) in normalized_claim
            for marker in scenario.unsupported_markers
        ):
            errors.append(f"{prefix}:unsupported_fact_leakage")
        used_paths.extend(claim.graph_path_ids)

    for fact_id, count in fact_counts.items():
        if count != 1:
            errors.append(f"fact_{fact_id}:count_{count}")

    expected_top_paths = list(dict.fromkeys(used_paths))
    if draft.graph_paths != expected_top_paths:
        errors.append("top_level_graph_paths_mismatch")

    if scenario.unsupported_markers:
        unsupported_text = normalize_match_text(" ".join(draft.unsupported_claims))
        if not draft.unsupported_claims:
            errors.append("unsupported_claims_missing")
        elif not any(
            normalize_match_text(marker) in unsupported_text
            for marker in scenario.unsupported_markers
        ):
            errors.append("unsupported_aspect_not_identified")
    elif draft.unsupported_claims:
        errors.append("unexpected_unsupported_claims")
    return list(dict.fromkeys(errors))


SCENARIOS = (
    AtomicProbeScenario(
        name="random_forest_relation_and_effect",
        user_context="""QUESTION:
随机森林属于什么方法？平均预测有什么作用？

INTENT: explanation
RETRIEVAL_MODE: hybrid

AVAILABLE_GRAPH_PATH_IDS: P1
GRAPH_PATHS:
[P1]
随机森林 (ALG_RF) -[BELONGS_TO]-> 集成学习 (FAM_ENSEMBLE); relation_id=R1

AVAILABLE_TEXT_EVIDENCE_IDS: E1, E2
TEXT_EVIDENCE:
[E1]
text=Random forests are ensemble methods based on randomized decision trees.

[E2]
text=The forest prediction is the average of the individual tree predictions. Averaging reduces variance.""",
        evidence_texts={
            "E1": "Random forests are ensemble methods based on randomized decision trees.",
            "E2": (
                "The forest prediction is the average of the individual tree predictions. "
                "Averaging reduces variance."
            ),
        },
        valid_graph_path_ids=("P1",),
        valid_relation_ids=("R1",),
        facts=(
            FactRule(
                fact_id="rf_family",
                marker_groups=(
                    ("随机森林", "random forest"),
                    ("集成", "ensemble"),
                ),
                evidence_ids=("E1",),
                graph_path_ids=("P1",),
                relation_id="R1",
            ),
            FactRule(
                fact_id="rf_variance",
                marker_groups=(
                    ("平均", "averag"),
                    ("方差", "variance"),
                ),
                evidence_ids=("E2",),
            ),
        ),
    ),
    AtomicProbeScenario(
        name="adaboost_three_atomic_facts",
        user_context="""QUESTION:
AdaBoost 是什么方法？弱学习器如何训练，后续学习器关注什么样本？

INTENT: explanation
RETRIEVAL_MODE: vector

AVAILABLE_GRAPH_PATH_IDS: (none)
GRAPH_PATHS:
(none)

AVAILABLE_TEXT_EVIDENCE_IDS: E1, E2, E3
TEXT_EVIDENCE:
[E1]
text=AdaBoost is an ensemble method.

[E2]
text=AdaBoost fits a sequence of weak learners.

[E3]
text=Later weak learners focus more on difficult training examples.""",
        evidence_texts={
            "E1": "AdaBoost is an ensemble method.",
            "E2": "AdaBoost fits a sequence of weak learners.",
            "E3": "Later weak learners focus more on difficult training examples.",
        },
        valid_graph_path_ids=(),
        valid_relation_ids=(),
        facts=(
            FactRule(
                fact_id="ada_family",
                marker_groups=(("adaboost",), ("集成", "ensemble")),
                evidence_ids=("E1",),
            ),
            FactRule(
                fact_id="ada_sequence",
                marker_groups=(
                    (
                        "顺序",
                        "依次",
                        "序列",
                        "逐个",
                        "逐步",
                        "逐轮",
                        "连续",
                        "一个接一个",
                        "逐次",
                        "串行",
                        "先后",
                        "sequence",
                        "sequential",
                    ),
                ),
                evidence_ids=("E2",),
            ),
            FactRule(
                fact_id="ada_focus",
                marker_groups=(
                    (
                        "adaboost",
                        "后续弱学习器",
                        "后续学习器",
                        "后面的学习器",
                        "later weak learner",
                    ),
                    ("困难", "难", "错误", "误分类", "difficult"),
                    ("关注", "侧重", "focus"),
                ),
                evidence_ids=("E3",),
            ),
        ),
    ),
    AtomicProbeScenario(
        name="bagging_boosting_comparison",
        user_context="""QUESTION:
Bagging 与 Boosting 的训练方式有什么区别？

INTENT: comparison
RETRIEVAL_MODE: hybrid

AVAILABLE_GRAPH_PATH_IDS: (none)
GRAPH_PATHS:
(none)

AVAILABLE_TEXT_EVIDENCE_IDS: E1, E2
TEXT_EVIDENCE:
[E1]
text=Bagging methods train base estimators independently on random subsets of the data.

[E2]
text=Boosting methods fit weak learners sequentially.""",
        evidence_texts={
            "E1": (
                "Bagging methods train base estimators independently on random subsets "
                "of the data."
            ),
            "E2": "Boosting methods fit weak learners sequentially.",
        },
        valid_graph_path_ids=(),
        valid_relation_ids=(),
        facts=(
            FactRule(
                fact_id="bagging_independent",
                marker_groups=(
                    ("bagging", "装袋"),
                    ("独立", "并行", "independent"),
                ),
                evidence_ids=("E1",),
            ),
            FactRule(
                fact_id="boosting_sequential",
                marker_groups=(
                    ("boosting", "提升"),
                    ("顺序", "依次", "序列", "逐个", "sequential"),
                ),
                evidence_ids=("E2",),
            ),
        ),
    ),
    AtomicProbeScenario(
        name="kmeans_unsupported_parameter",
        user_context="""QUESTION:
KMeans 优化什么目标？默认最大迭代次数是多少？

INTENT: definition
RETRIEVAL_MODE: vector

AVAILABLE_GRAPH_PATH_IDS: (none)
GRAPH_PATHS:
(none)

AVAILABLE_TEXT_EVIDENCE_IDS: E1
TEXT_EVIDENCE:
[E1]
text=KMeans minimizes the within-cluster sum of squared distances.""",
        evidence_texts={
            "E1": "KMeans minimizes the within-cluster sum of squared distances.",
        },
        valid_graph_path_ids=(),
        valid_relation_ids=(),
        facts=(
            FactRule(
                fact_id="kmeans_objective",
                marker_groups=(
                    ("kmeans", "k means"),
                    ("簇内", "cluster"),
                    ("平方", "squared"),
                ),
                evidence_ids=("E1",),
            ),
        ),
        unsupported_markers=("最大迭代", "迭代次数", "max_iter", "max iter"),
    ),
)


def execute_probe(
    client: OllamaClient,
    scenario: AtomicProbeScenario,
    run_index: int,
) -> dict:
    started_at = time.perf_counter()
    draft: LLMAnswerDraft | None = None
    error_type: str | None = None
    semantic_errors: list[str] = []
    try:
        result = client.generate_structured(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": scenario.user_context},
            ],
            response_model=LLMAnswerDraft,
            node="probe_atomic_claim_prompt_v2",
        )
        draft = LLMAnswerDraft.model_validate(result)
        semantic_errors = validate_atomic_draft(draft, scenario)
    except LLMError as exc:
        error_type = type(exc).__name__

    record = client.last_call
    schema_valid = bool(record and record.success and record.schema_valid and draft is not None)
    success = bool(schema_valid and not semantic_errors and error_type is None)
    return {
        "run_index": run_index,
        "scenario": scenario.name,
        "success": success,
        "schema_valid": schema_valid,
        "semantic_valid": bool(schema_valid and not semantic_errors),
        "claim_count": len(draft.claims) if draft is not None else 0,
        "unsupported_claim_count": len(draft.unsupported_claims) if draft is not None else 0,
        "used_evidence_ids": (
            list(
                dict.fromkeys(
                    evidence_id
                    for claim in draft.claims
                    for evidence_id in claim.evidence_ids
                )
            )
            if draft is not None
            else []
        ),
        "used_graph_path_ids": (
            list(
                dict.fromkeys(
                    path_id
                    for claim in draft.claims
                    for path_id in claim.graph_path_ids
                )
            )
            if draft is not None
            else []
        ),
        "semantic_error_codes": semantic_errors,
        "error_type": error_type or (record.error_type if record else None),
        "attempts": record.attempts if record else 0,
        "latency_ms": record.latency_ms if record else round(
            (time.perf_counter() - started_at) * 1000,
            1,
        ),
        "prompt_tokens": record.prompt_tokens if record else None,
        "completion_tokens": record.completion_tokens if record else None,
        "done_reason": record.done_reason if record else None,
        "validation_issue_count": len(record.validation_issues) if record else 0,
    }


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return round(ordered[index], 1)


def summarize_results(results: list[dict], minimum_successes: int) -> dict:
    per_scenario: dict[str, dict] = {}
    for scenario in SCENARIOS:
        rows = [row for row in results if row["scenario"] == scenario.name]
        per_scenario[scenario.name] = {
            "runs": len(rows),
            "schema_successes": sum(bool(row["schema_valid"]) for row in rows),
            "semantic_successes": sum(bool(row["success"]) for row in rows),
        }
    latencies = [float(row["latency_ms"]) for row in results if row["latency_ms"] is not None]
    success_count = sum(bool(row["success"]) for row in results)
    return {
        "total_runs": len(results),
        "schema_successes": sum(bool(row["schema_valid"]) for row in results),
        "semantic_successes": success_count,
        "minimum_successes": minimum_successes,
        "gate_passed": success_count >= minimum_successes,
        "fallback_or_error_count": sum(bool(row["error_type"]) for row in results),
        "mean_latency_ms": round(statistics.mean(latencies), 1) if latencies else None,
        "p95_latency_ms": percentile(latencies, 0.95),
        "per_scenario": per_scenario,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe Prompt v2 atomic Claim structure without persisting model content."
    )
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--minimum-successes", type=int, default=19)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be positive")
    if args.minimum_successes < 1 or args.minimum_successes > args.runs:
        raise SystemExit("--minimum-successes must be between 1 and --runs")

    settings_doc = yaml.safe_load(
        (PROJECT_ROOT / "config/settings.yaml").read_text(encoding="utf-8")
    )
    settings = LLMSettings.model_validate(settings_doc.get("llm", {}))
    client = OllamaClient(settings)
    results: list[dict] = []
    for index in range(args.runs):
        scenario = SCENARIOS[index % len(SCENARIOS)]
        row = execute_probe(client, scenario, index + 1)
        results.append(row)
        print(
            f"[{index + 1:02d}/{args.runs}] {scenario.name} "
            f"success={row['success']} claims={row['claim_count']} "
            f"latency_ms={row['latency_ms']} errors={row['semantic_error_codes']}"
        )

    summary = summarize_results(results, args.minimum_successes)
    report = {
        "schema_version": "1.0",
        "artifact": "atomic_claim_prompt_probe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.model,
        "prompt_version": ANSWER_PROMPT_VERSION,
        "system_prompt_sha256": prompt_sha256(),
        "wire_schema_sha256": wire_schema_sha256(),
        "probe_contract": {
            "scenario_names": [scenario.name for scenario in SCENARIOS],
            "maximum_claims": MAX_LLM_CLAIMS,
            "raw_prompt_recorded": False,
            "raw_content_recorded": False,
            "raw_thinking_recorded": False,
            "temperature": settings.temperature,
            "seed": settings.seed,
            "think": settings.think,
            "num_predict": settings.num_predict,
        },
        "summary": summary,
        "results": results,
    }
    output_path = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"report={output_path}")
    print(
        f"gate_passed={summary['gate_passed']} "
        f"successes={summary['semantic_successes']}/{summary['total_runs']}"
    )
    return 0 if summary["gate_passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
