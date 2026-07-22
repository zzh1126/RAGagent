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
from typing import Callable, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3:4b"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StatusPayload(StrictModel):
    status: Literal["ok"]
    evidence_ids: list[str]


class QueryPlanPayload(StrictModel):
    intent: Literal[
        "definition",
        "relation",
        "multi_hop",
        "comparison",
        "explanation",
        "recommendation",
        "ambiguous",
        "out_of_scope",
    ]
    entities: list[str] = Field(default_factory=list)
    retrieval_mode: Literal["vector", "graph", "hybrid"]
    query_en: str
    required_aspects: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class ProbeClaim(StrictModel):
    claim: str = Field(min_length=1)
    text_evidence_ids: list[str] = Field(default_factory=list)
    graph_path_ids: list[str] = Field(default_factory=list)


class AnswerPayloadProbe(StrictModel):
    answer: str = Field(min_length=1)
    claims: list[ProbeClaim] = Field(min_length=1)
    unsupported_claims: list[str] = Field(default_factory=list)


SemanticValidator = Callable[[BaseModel], list[str]]


@dataclass(frozen=True)
class ProbeScenario:
    name: str
    response_model: type[BaseModel]
    system_prompt: str
    user_prompt: str
    validate_semantics: SemanticValidator


def validate_status(payload: BaseModel) -> list[str]:
    value = StatusPayload.model_validate(payload)
    errors: list[str] = []
    if value.evidence_ids != ["E1"]:
        errors.append("evidence_ids must equal ['E1']")
    return errors


def validate_query_plan(payload: BaseModel) -> list[str]:
    value = QueryPlanPayload.model_validate(payload)
    errors: list[str] = []
    if value.intent != "relation":
        errors.append("intent must be relation")
    if value.retrieval_mode != "graph":
        errors.append("retrieval_mode must be graph")
    normalized_entities = " ".join(value.entities).lower()
    if "随机森林" not in normalized_entities and "random forest" not in normalized_entities:
        errors.append("entities must include random forest")
    if "random forest" not in value.query_en.lower():
        errors.append("query_en must mention random forest")
    if not value.required_aspects:
        errors.append("required_aspects must not be empty")
    return errors


def validate_answer(payload: BaseModel) -> list[str]:
    value = AnswerPayloadProbe.model_validate(payload)
    errors: list[str] = []
    text_ids = {
        evidence_id
        for claim in value.claims
        for evidence_id in claim.text_evidence_ids
    }
    path_ids = {
        path_id
        for claim in value.claims
        for path_id in claim.graph_path_ids
    }
    if not text_ids.issubset({"E1"}):
        errors.append(f"unknown text evidence IDs: {sorted(text_ids - {'E1'})}")
    if not path_ids.issubset({"P1"}):
        errors.append(f"unknown graph path IDs: {sorted(path_ids - {'P1'})}")
    if "E1" not in text_ids:
        errors.append("at least one claim must cite E1")
    if "P1" not in path_ids:
        errors.append("at least one claim must cite P1")
    if value.unsupported_claims:
        errors.append("unsupported_claims must be empty for the supplied evidence")
    if "随机森林" not in value.answer or "集成" not in value.answer:
        errors.append("answer must state that random forest is an ensemble method")
    return errors


SCENARIOS = (
    ProbeScenario(
        name="simple_status",
        response_model=StatusPayload,
        system_prompt="Return only JSON that follows the supplied schema.",
        user_prompt="Return status ok and evidence_ids containing exactly E1.",
        validate_semantics=validate_status,
    ),
    ProbeScenario(
        name="query_plan",
        response_model=QueryPlanPayload,
        system_prompt=(
            "You plan retrieval for a scikit-learn question. Do not answer the question. "
            "Return only a retrieval plan that follows the supplied schema."
        ),
        user_prompt=(
            "Plan retrieval for: 随机森林属于什么模型族？ "
            "Use relation intent, graph retrieval, the question entity, a short English "
            "query, and at least one required answer aspect."
        ),
        validate_semantics=validate_query_plan,
    ),
    ProbeScenario(
        name="nested_answer",
        response_model=AnswerPayloadProbe,
        system_prompt=(
            "Answer only from the supplied evidence. Return Chinese text and structured "
            "claims. Never invent evidence IDs or graph path IDs. Return only JSON."
        ),
        user_prompt=(
            "QUESTION: 随机森林属于什么模型族？\n"
            "TEXT_EVIDENCE:\n"
            "[E1] Random forests are ensemble methods based on randomized decision trees.\n"
            "GRAPH_PATHS:\n"
            "[P1] 随机森林 -BELONGS_TO-> 集成学习\n"
            "Answer in Chinese. Every claim must cite the applicable E1 and P1 IDs. "
            "The evidence fully supports the answer, so unsupported_claims must be empty."
        ),
        validate_semantics=validate_answer,
    ),
)


def execute_probe(
    session: requests.Session,
    *,
    base_url: str,
    model: str,
    scenario: ProbeScenario,
    run_index: int,
    timeout_seconds: int,
    keep_alive: str,
    num_predict: int,
) -> dict:
    request_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": scenario.system_prompt},
            {"role": "user", "content": scenario.user_prompt},
        ],
        "think": False,
        "stream": False,
        "format": scenario.response_model.model_json_schema(),
        "keep_alive": keep_alive,
        "options": {
            "temperature": 0,
            "seed": 42,
            "num_predict": num_predict,
        },
    }
    started = time.perf_counter()
    content = ""
    thinking = ""
    parsed_output = None
    schema_valid = False
    semantic_errors: list[str] = []
    error_type = None
    error_message = None
    response_data: dict = {}

    try:
        response = session.post(
            f"{base_url.rstrip('/')}/api/chat",
            json=request_payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        response_data = response.json()
        message = response_data.get("message") or {}
        content = str(message.get("content") or "").strip()
        thinking = str(message.get("thinking") or "")
        if not content:
            error_type = "empty_content"
            error_message = "message.content is empty"
        else:
            try:
                parsed = scenario.response_model.model_validate_json(content)
                parsed_output = parsed.model_dump(mode="json")
                schema_valid = True
                semantic_errors = scenario.validate_semantics(parsed)
            except ValidationError as exc:
                error_type = "schema_validation"
                error_message = str(exc)
    except requests.Timeout as exc:
        error_type = "timeout"
        error_message = str(exc)
    except requests.RequestException as exc:
        error_type = "request_error"
        error_message = str(exc)
    except (ValueError, TypeError) as exc:
        error_type = "response_error"
        error_message = str(exc)

    if schema_valid and semantic_errors:
        error_type = "semantic_validation"
        error_message = "; ".join(semantic_errors)

    success = bool(
        content
        and not thinking
        and schema_valid
        and not semantic_errors
        and error_type is None
    )
    return {
        "run_index": run_index,
        "scenario": scenario.name,
        "success": success,
        "content_nonempty": bool(content),
        "thinking_empty": not bool(thinking),
        "content_length": len(content),
        "thinking_length": len(thinking),
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest() if content else None,
        "schema_valid": schema_valid,
        "semantic_valid": schema_valid and not semantic_errors,
        "semantic_errors": semantic_errors,
        "parsed_output": parsed_output,
        "done_reason": response_data.get("done_reason"),
        "prompt_tokens": response_data.get("prompt_eval_count"),
        "completion_tokens": response_data.get("eval_count"),
        "load_ms": round((response_data.get("load_duration") or 0) / 1_000_000, 1),
        "total_ms": round((response_data.get("total_duration") or 0) / 1_000_000, 1),
        "wall_ms": round((time.perf_counter() - started) * 1000, 1),
        "error_type": error_type,
        "error_message": error_message,
    }


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return round(ordered[index], 1)


def summarize_results(
    results: list[dict],
    *,
    scenario_names: list[str],
    minimum_success_rate: float,
    target_gate: str,
) -> dict:
    per_scenario = {}
    for scenario_name in scenario_names:
        rows = [row for row in results if row["scenario"] == scenario_name]
        schema_successes = sum(
            bool(row["content_nonempty"] and row["thinking_empty"] and row["schema_valid"])
            for row in rows
        )
        semantic_successes = sum(bool(row["success"]) for row in rows)
        per_scenario[scenario_name] = {
            "runs": len(rows),
            "schema_successes": schema_successes,
            "schema_success_rate": round(schema_successes / len(rows), 4) if rows else 0.0,
            "semantic_successes": semantic_successes,
            "semantic_success_rate": round(semantic_successes / len(rows), 4) if rows else 0.0,
        }

    warm_rows = results[1:]
    warm_latencies = [float(row["wall_ms"]) for row in warm_rows]
    empty_content_count = sum(not row["content_nonempty"] for row in results)
    thinking_nonempty_count = sum(not row["thinking_empty"] for row in results)
    structured_output_gate_passed = bool(
        all(
            row["runs"] > 0 and row["schema_success_rate"] >= minimum_success_rate
            for row in per_scenario.values()
        )
        and empty_content_count == 0
        and thinking_nonempty_count == 0
    )
    generator_gate_passed = bool(
        structured_output_gate_passed
        and per_scenario["simple_status"]["semantic_success_rate"] >= minimum_success_rate
        and per_scenario["nested_answer"]["semantic_success_rate"] >= minimum_success_rate
    )
    planner_gate_passed = bool(
        structured_output_gate_passed
        and per_scenario["query_plan"]["semantic_success_rate"] >= minimum_success_rate
    )
    full_agent_gate_passed = generator_gate_passed and planner_gate_passed
    gates = {
        "structured": structured_output_gate_passed,
        "generator": generator_gate_passed,
        "planner": planner_gate_passed,
        "full_agent": full_agent_gate_passed,
    }
    if target_gate not in gates:
        raise ValueError(f"unsupported target gate: {target_gate}")
    return {
        "total_runs": len(results),
        "total_schema_successes": sum(
            bool(row["content_nonempty"] and row["thinking_empty"] and row["schema_valid"])
            for row in results
        ),
        "total_semantic_successes": sum(bool(row["success"]) for row in results),
        "per_scenario": per_scenario,
        "empty_content_count": empty_content_count,
        "thinking_nonempty_count": thinking_nonempty_count,
        "cold_start_wall_ms": results[0]["wall_ms"] if results else None,
        "warm_latency_mean_ms": round(statistics.mean(warm_latencies), 1) if warm_latencies else None,
        "warm_latency_p95_ms": percentile(warm_latencies, 0.95),
        "minimum_success_rate": minimum_success_rate,
        "structured_output_gate_passed": structured_output_gate_passed,
        "generator_gate_passed": generator_gate_passed,
        "planner_gate_passed": planner_gate_passed,
        "full_agent_gate_passed": full_agent_gate_passed,
        "target_gate": target_gate,
        "gate_passed": gates[target_gate],
    }


def unload_model(
    session: requests.Session,
    *,
    base_url: str,
    model: str,
    timeout_seconds: int,
) -> None:
    response = session.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={"model": model, "keep_alive": 0},
        timeout=timeout_seconds,
    )
    response.raise_for_status()


def model_info(session: requests.Session, *, base_url: str, model: str, timeout_seconds: int) -> dict:
    response = session.post(
        f"{base_url.rstrip('/')}/api/show",
        json={"model": model},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    return {
        "details": data.get("details"),
        "capabilities": data.get("capabilities"),
        "parameters": data.get("parameters"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe Ollama structured output with simple, planner, and nested answer schemas."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--runs-per-schema", type=int, default=20)
    parser.add_argument("--minimum-success-rate", type=float, default=0.95)
    parser.add_argument(
        "--target-gate",
        choices=("structured", "generator", "planner", "full_agent"),
        default="generator",
        help="Select which capability gate controls the process exit code.",
    )
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--keep-alive", default="30m")
    parser.add_argument("--num-predict", type=int, default=512)
    parser.add_argument(
        "--unload-before-run",
        action="store_true",
        help="Unload the model before the first request so the first latency is a cold start.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "reports" / "llm_probe_qwen3_4b.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.runs_per_schema < 1:
        raise SystemExit("--runs-per-schema must be positive")
    if not 0 < args.minimum_success_rate <= 1:
        raise SystemExit("--minimum-success-rate must be in (0, 1]")

    session = requests.Session()
    if args.unload_before_run:
        unload_model(
            session,
            base_url=args.base_url,
            model=args.model,
            timeout_seconds=args.timeout,
        )
        time.sleep(0.5)

    info = model_info(
        session,
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout,
    )
    results: list[dict] = []
    total_runs = args.runs_per_schema * len(SCENARIOS)
    for round_index in range(args.runs_per_schema):
        for scenario in SCENARIOS:
            run_index = len(results) + 1
            result = execute_probe(
                session,
                base_url=args.base_url,
                model=args.model,
                scenario=scenario,
                run_index=run_index,
                timeout_seconds=args.timeout,
                keep_alive=args.keep_alive,
                num_predict=args.num_predict,
            )
            results.append(result)
            print(
                f"[{run_index:02d}/{total_runs}] {scenario.name} "
                f"success={result['success']} wall_ms={result['wall_ms']} "
                f"error={result['error_type']}"
            )

    summary = summarize_results(
        results,
        scenario_names=[scenario.name for scenario in SCENARIOS],
        minimum_success_rate=args.minimum_success_rate,
        target_gate=args.target_gate,
    )
    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": args.base_url,
        "model": args.model,
        "model_info": info,
        "probe_contract": {
            "think": False,
            "stream": False,
            "temperature": 0,
            "seed": 42,
            "num_predict": args.num_predict,
            "keep_alive": args.keep_alive,
            "runs_per_schema": args.runs_per_schema,
            "scenario_names": [scenario.name for scenario in SCENARIOS],
            "target_gate": args.target_gate,
            "thinking_content_recorded": False,
        },
        "summary": summary,
        "results": results,
    }
    output_path = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report={output_path}")
    print(
        "gates="
        f"structured:{summary['structured_output_gate_passed']} "
        f"generator:{summary['generator_gate_passed']} "
        f"planner:{summary['planner_gate_passed']} "
        f"full_agent:{summary['full_agent_gate_passed']}"
    )
    print(f"target_gate={summary['target_gate']} gate_passed={summary['gate_passed']}")
    return 0 if summary["gate_passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
