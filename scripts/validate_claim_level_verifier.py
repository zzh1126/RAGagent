from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas import (
    AnswerClaim,
    AnswerPayload,
    EvidenceQuote,
    GraphPath,
    GraphTriple,
    LinkedEntity,
    RetrievalResult,
    TextEvidence,
    VerifyResult,
)
from src.verification.evidence_verifier import EvidenceVerifier


REPORT_PATH = PROJECT_ROOT / "reports" / "claim_level_partial_pass_dev02_smoke.json"
FORBIDDEN_RAW_KEYS = {
    "answer",
    "claim",
    "claims",
    "content",
    "messages",
    "prompt",
    "question",
    "quote",
    "quotes",
    "supporting_quotes",
    "thinking",
}


class ProbeGraphRepository:
    def validate_path(self, triples: list[dict]) -> bool:
        return bool(triples)

    def get_neighbors(self, entity_id: str) -> list[dict]:
        return []


def retrieval_fixture() -> RetrievalResult:
    return RetrievalResult(
        intent="explanation",
        mode="hybrid",
        entities=[
            LinkedEntity(
                entity_id="ALG_RF",
                name_en="Random Forest",
                name_zh="随机森林",
                type="Algorithm",
                matched_text="随机森林",
            )
        ],
        graph_paths=[
            GraphPath(
                path_id="P1",
                triples=[
                    GraphTriple(
                        source_id="ALG_RF",
                        source_name="随机森林",
                        relation="BELONGS_TO",
                        target_id="FAM_ENSEMBLE",
                        target_name="集成学习",
                        relation_id="R1",
                        review_status="approved",
                    )
                ],
            )
        ],
        text_evidence=[
            TextEvidence(
                evidence_id="E1",
                chunk_id="C1",
                source_id="S4",
                page_title="Ensemble methods",
                heading_path=["Random forests"],
                url="https://scikit-learn.org/stable/modules/ensemble.html",
                display_text=(
                    "Random forests are ensemble methods based on randomized decision "
                    "trees. Averaging reduces variance."
                ),
                score=0.91,
            )
        ],
    )


def supported_claim() -> AnswerClaim:
    return AnswerClaim(
        claim="随机森林属于集成学习。",
        evidence_ids=["E1"],
        graph_path_ids=["P1"],
        relation_id="R1",
        supporting_quotes=[
            EvidenceQuote(
                evidence_id="E1",
                quote=(
                    "Random forests are ensemble methods based on randomized decision "
                    "trees."
                ),
            )
        ],
    )


def unsupported_claim() -> AnswerClaim:
    return AnswerClaim(
        claim="随机森林可以直接处理缺失值。",
        evidence_ids=["E999"],
        supporting_quotes=[
            EvidenceQuote(
                evidence_id="E999",
                quote="Invented evidence for the unsupported claim.",
            )
        ],
    )


def payload(*claims: AnswerClaim) -> AnswerPayload:
    return AnswerPayload(
        answer="synthetic",
        claims=list(claims),
        graph_paths=["P1"] if any(claim.graph_path_ids for claim in claims) else [],
        confidence=0.8,
        generator_backend="ollama",
        generation_attempts=1,
    )


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def find_forbidden_raw_keys(value, path: str = "root") -> list[str]:
    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            current = f"{path}.{key}"
            if str(key) in FORBIDDEN_RAW_KEYS:
                errors.append(current)
            errors.extend(find_forbidden_raw_keys(item, current))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            errors.extend(find_forbidden_raw_keys(item, f"{path}[{index}]"))
    return errors


def main() -> None:
    schema = VerifyResult.model_json_schema()
    decision_schema = (schema.get("properties") or {}).get("decision") or {}
    expected_decisions = {"pass", "partial_pass", "retry", "refuse"}
    if set(decision_schema.get("enum") or []) != expected_decisions:
        fail("VerifyResult decision enum does not expose the four-state contract")

    retrieval = retrieval_fixture()
    graph_repo = ProbeGraphRepository()
    mixed = payload(supported_claim(), unsupported_claim())
    partial = EvidenceVerifier(
        max_retries=1,
        decision_policy="partial_pass",
    ).verify(
        "随机森林为什么更稳定",
        mixed,
        retrieval,
        graph_repo=graph_repo,
    )
    if partial.decision != "partial_pass":
        fail(f"mixed Claim payload expected partial_pass, got {partial.decision}")
    if partial.retained_claim_ids != ["C1"] or partial.removed_claim_ids != ["C2"]:
        fail("partial-pass retained/removed Claim IDs are incorrect")
    if partial.supported_claim_count != 1 or partial.removed_claim_count != 1:
        fail("partial-pass Claim counts are incorrect")

    strict_verifier = EvidenceVerifier(max_retries=1, decision_policy="strict")
    strict_first = strict_verifier.verify(
        "随机森林为什么更稳定",
        mixed,
        retrieval,
        graph_repo=graph_repo,
        retry_count=0,
    )
    strict_second = strict_verifier.verify(
        "随机森林为什么更稳定",
        mixed,
        retrieval,
        graph_repo=graph_repo,
        retry_count=1,
    )
    if strict_first.decision != "retry" or strict_second.decision != "refuse":
        fail("strict policy does not preserve retry-then-refuse behavior")
    if strict_second.retained_claim_ids:
        fail("strict refusal must not retain a supported subset")

    complete = EvidenceVerifier(max_retries=1).verify(
        "随机森林为什么更稳定",
        payload(supported_claim()),
        retrieval,
        graph_repo=graph_repo,
    )
    if complete.decision != "pass" or complete.retained_claim_ids != ["C1"]:
        fail("fully supported payload did not pass")

    if not REPORT_PATH.exists():
        fail(f"missing sanitized real smoke report: {REPORT_PATH}")
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if report.get("artifact") != "claim_level_partial_pass_dev_smoke":
        fail("invalid real smoke report artifact")
    if report.get("decision") != "partial_pass":
        fail("real DEV02 smoke did not produce partial_pass")
    if report.get("retry_count") != 0 or report.get("generation_call_count") != 1:
        fail("real DEV02 partial-pass smoke must not retry generation")
    if report.get("unsupported_claim_leakage_count") != 0:
        fail("real DEV02 smoke leaked a removed Claim")
    if not report.get("retained_claim_ids") or not report.get("removed_claim_ids"):
        fail("real DEV02 smoke must retain and remove at least one Claim")
    raw_key_paths = find_forbidden_raw_keys(report)
    if raw_key_paths:
        fail("real smoke report stores raw content keys: " + ", ".join(raw_key_paths))
    for field in (
        "raw_prompt_recorded",
        "raw_question_recorded",
        "raw_answer_recorded",
        "raw_claims_recorded",
        "raw_quotes_recorded",
        "raw_thinking_recorded",
    ):
        if report.get(field) is not False:
            fail(f"real smoke report must set {field}=false")

    print("OK: Claim-level Verifier v2 contract is valid")
    print("OK: pass=1 partial_pass=1 strict_retry=1 strict_refuse=1")
    print(
        "OK: retained_claim_ids=C1 removed_claim_ids=C2 "
        f"verification_latency_ms={partial.verification_latency_ms:.3f}"
    )
    print(
        "OK: real_dev02=partial_pass retry_count=0 generation_calls=1 "
        "unsupported_claim_leakage_count=0"
    )


if __name__ == "__main__":
    main()
