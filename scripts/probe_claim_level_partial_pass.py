from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.generators.llm_generator import ANSWER_PROMPT_VERSION
from src.agent.workflow import build_default_workflow


DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "claim_level_partial_pass_dev02_smoke.json"
DEV_QUERY = "随机森林为什么更稳定"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a sanitized DEV02 Claim-level partial-pass smoke."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output_path = args.output.resolve()
    if output_path.exists():
        raise SystemExit(f"Refusing to overwrite existing smoke report: {output_path}")

    workflow = build_default_workflow(PROJECT_ROOT)
    response = workflow.invoke(DEV_QUERY)
    verification = response.verification
    removed_claims = [
        result.claim for result in verification.claim_results if not result.retained
    ]
    normalized_answer = normalize(response.answer)
    unsupported_claim_leakage_count = sum(
        bool(normalize(claim)) and normalize(claim) in normalized_answer
        for claim in removed_claims
    )
    generator = getattr(workflow.answer_generator, "primary", workflow.answer_generator)
    client = getattr(generator, "client", None)
    report = {
        "schema_version": "1.0",
        "artifact": "claim_level_partial_pass_dev_smoke",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "question_id": "DEV02",
        "question_sha256": sha256_text(DEV_QUERY),
        "development_only": True,
        "independent_quality_result": False,
        "model": getattr(client, "model", None),
        "prompt_version": ANSWER_PROMPT_VERSION,
        "verifier_policy": verification.decision_policy,
        "decision": verification.decision,
        "evidence_score": verification.evidence_score,
        "claim_coverage": verification.claim_coverage,
        "citation_validity": verification.citation_validity,
        "path_validity": verification.path_validity,
        "retrieval_sufficiency": verification.retrieval_sufficiency,
        "generated_claim_count": verification.generated_claim_count,
        "supported_claim_count": verification.supported_claim_count,
        "supported_claim_ids": verification.supported_claim_ids,
        "unsupported_claim_ids": verification.unsupported_claim_ids,
        "retained_claim_ids": verification.retained_claim_ids,
        "removed_claim_ids": verification.removed_claim_ids,
        "unsupported_claim_leakage_count": unsupported_claim_leakage_count,
        "retry_count": response.retry_count,
        "generation_call_count": len(response.generation_trace),
        "generation_attempts": sum(call.attempts for call in response.generation_trace),
        "generation_latency_ms": round(
            sum(call.latency_ms for call in response.generation_trace),
            1,
        ),
        "evidence_packing_latency_ms": round(
            sum(
                trace.evidence_packing_latency_ms
                for trace in response.evidence_packing_trace
            ),
            3,
        ),
        "verification_latency_ms": verification.verification_latency_ms,
        "end_to_end_latency_ms": response.latency_ms,
        "fallback_used": any(call.fallback_used for call in response.generation_trace),
        "raw_prompt_recorded": False,
        "raw_question_recorded": False,
        "raw_answer_recorded": False,
        "raw_claims_recorded": False,
        "raw_quotes_recorded": False,
        "raw_thinking_recorded": False,
    }

    if report["decision"] != "partial_pass":
        raise SystemExit(f"Expected partial_pass, got {report['decision']}")
    if report["supported_claim_count"] <= 0 or not report["removed_claim_ids"]:
        raise SystemExit("Smoke did not contain both retained and removed Claims")
    if report["retry_count"] != 0 or report["generation_call_count"] != 1:
        raise SystemExit("Partial-pass smoke unexpectedly retried generation")
    if report["unsupported_claim_leakage_count"] != 0:
        raise SystemExit("Removed Claim text leaked into the final answer")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OK: report={output_path}")
    print(
        f"OK: decision={report['decision']} claims="
        f"{report['supported_claim_count']}/{report['generated_claim_count']} "
        f"retry_count={report['retry_count']} generation_calls="
        f"{report['generation_call_count']}"
    )
    print(
        "OK: raw_question=false raw_answer=false raw_claims=false "
        "raw_quotes=false raw_thinking=false"
    )


if __name__ == "__main__":
    main()
