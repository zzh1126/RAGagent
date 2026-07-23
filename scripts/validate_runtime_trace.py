from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.workflow import build_default_workflow


def validate_latency_components(response) -> None:
    latency = response.latency_trace
    values = (
        latency.routing_latency_ms,
        latency.retrieval_latency_ms,
        latency.evidence_packing_latency_ms,
        latency.llm_generation_latency_ms,
        latency.verification_latency_ms,
        latency.retry_latency_ms,
    )
    if any(value < 0.0 for value in values):
        raise AssertionError("runtime trace contains a negative stage latency")
    if latency.end_to_end_latency_ms < max(values, default=0.0):
        raise AssertionError("end-to-end latency does not cover every stage")
    if response.cache_status != "disabled":
        raise AssertionError("formal workflow must keep answer caching disabled")


def main() -> None:
    workflow = build_default_workflow(PROJECT_ROOT, generator_backend="offline_rule")
    pass_response = workflow.invoke("随机森林为什么更稳定")
    retry_response = workflow.invoke("随机森林的学习率是多少")

    validate_latency_components(pass_response)
    validate_latency_components(retry_response)

    if pass_response.verification.decision != "pass":
        raise AssertionError("expected the known supported trace case to pass")
    if pass_response.route_trace is None:
        raise AssertionError("route trace is missing")
    if len(pass_response.retrieval_trace) != 1:
        raise AssertionError("non-retry case must contain one retrieval call")
    if len(pass_response.verification_trace) != 1:
        raise AssertionError("non-retry case must contain one verification call")

    if retry_response.verification.decision != "refuse":
        raise AssertionError("expected the unsupported attribute case to refuse")
    if retry_response.retry_count != 1:
        raise AssertionError("retry case must execute exactly one retry")
    if len(retry_response.retrieval_trace) != 2:
        raise AssertionError("retry case must preserve both retrieval calls")
    if len(retry_response.generation_trace) != 2:
        raise AssertionError("retry case must preserve both generation calls")
    if len(retry_response.verification_trace) != 2:
        raise AssertionError("retry case must preserve both verification calls")
    if retry_response.verification_trace[0].decision != "retry":
        raise AssertionError("first verification decision must be retry")
    if retry_response.verification_trace[1].decision != "refuse":
        raise AssertionError("second verification decision must be refuse")
    if not retry_response.retrieval_trace[1].is_retry:
        raise AssertionError("supplemental retrieval must be marked as retry")
    if retry_response.latency_trace.retry_latency_ms < 0.0:
        raise AssertionError("retry branch latency must be non-negative")
    if retry_response.latency_trace.llm_generation_latency_ms != 0.0:
        raise AssertionError("offline rule validation must not report LLM latency")

    warmup = workflow.prewarm()
    if warmup.status != "not_applicable":
        raise AssertionError("offline rule workflow must not prewarm an LLM")

    print("OK: Stage 8.4 runtime trace contract is valid")
    print(
        "OK: pass_calls="
        f"{len(pass_response.retrieval_trace)}/"
        f"{len(pass_response.generation_trace)}/"
        f"{len(pass_response.verification_trace)}"
    )
    print(
        "OK: retry_calls="
        f"{len(retry_response.retrieval_trace)}/"
        f"{len(retry_response.generation_trace)}/"
        f"{len(retry_response.verification_trace)} "
        f"retry_latency_ms={retry_response.latency_trace.retry_latency_ms:.3f}"
    )
    print(
        "OK: latency_fields="
        "routing,retrieval,evidence_packing,llm_generation,verification,retry,end_to_end"
    )


if __name__ == "__main__":
    main()
