from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.workflow import build_default_workflow


def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or "随机森林为什么更稳定"
    workflow = build_default_workflow(PROJECT_ROOT)
    response = workflow.invoke(query)
    verification = response.verification
    print(f"ENGINE: {workflow.engine_name}")
    print(f"QUERY: {response.query}")
    print(f"INTENT: {response.retrieval.intent}")
    print(f"MODE: {response.retrieval.mode}")
    print(f"DECISION: {verification.decision}")
    print(f"EVIDENCE_SCORE: {verification.evidence_score:.4f}")
    print(f"CLAIM_COVERAGE: {verification.claim_coverage:.4f}")
    print(f"CITATION_VALIDITY: {verification.citation_validity:.4f}")
    print(f"PATH_VALIDITY: {verification.path_validity:.4f}")
    print(f"RETRIEVAL_SUFFICIENCY: {verification.retrieval_sufficiency:.4f}")
    print(f"RETRY_COUNT: {response.retry_count}")
    print(f"GENERATOR_BACKEND: {response.answer_payload.generator_backend}")
    print(f"GENERATOR_FALLBACK: {response.answer_payload.fallback_used}")
    if response.answer_payload.fallback_reason:
        print(f"GENERATOR_FALLBACK_REASON: {response.answer_payload.fallback_reason}")
    print(f"GENERATION_ATTEMPTS: {response.answer_payload.generation_attempts}")
    print(f"GENERATION_LATENCY_MS: {response.answer_payload.generation_latency_ms:.1f}")
    print(f"GENERATION_CALLS: {len(response.generation_trace)}")
    for index, call in enumerate(response.generation_trace, start=1):
        print(
            f"  GENERATION_CALL_{index}: requested={call.requested_backend} "
            f"actual={call.actual_backend} fallback={call.fallback_used} "
            f"attempts={call.attempts} latency_ms={call.latency_ms:.1f}"
        )
    print(f"EVIDENCE_PACKING_CALLS: {len(response.evidence_packing_trace)}")
    for index, packing in enumerate(response.evidence_packing_trace, start=1):
        print(
            f"  EVIDENCE_PACK_{index}: selected={packing.selected_evidence_ids} "
            f"paths={packing.selected_graph_path_ids} "
            f"latency_ms={packing.evidence_packing_latency_ms:.3f}"
        )
        if packing.coverage_gaps:
            print(f"    coverage_gaps={packing.coverage_gaps}")
    print(f"GENERATOR_ANSWER: {response.answer_payload.answer}")
    print("GENERATOR_CLAIMS:")
    for claim in response.answer_payload.claims:
        print(
            f"  claim={claim.claim} evidence_ids={claim.evidence_ids} "
            f"graph_path_ids={claim.graph_path_ids} relation_id={claim.relation_id or '-'}"
        )
        for quote in claim.supporting_quotes:
            print(f"    quote[{quote.evidence_id}]={quote.quote}")
    if response.answer_payload.unsupported_claims:
        print("GENERATOR_UNSUPPORTED:")
        for item in response.answer_payload.unsupported_claims:
            print(f"  {item}")
    if verification.unsupported_claims:
        print("VERIFIER_UNSUPPORTED:")
        for item in verification.unsupported_claims:
            print(f"  {item}")
    print("ANSWER:")
    print(response.answer)
    print("EVIDENCE_CHUNKS:")
    for item in response.retrieval.text_evidence:
        print(f"  {item.evidence_id} {item.chunk_id} score={item.score:.4f} {item.url}")


if __name__ == "__main__":
    main()
