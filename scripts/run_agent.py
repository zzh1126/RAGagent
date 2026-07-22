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
    print(f"RETRY_COUNT: {response.retry_count}")
    print("ANSWER:")
    print(response.answer)
    print("EVIDENCE_CHUNKS:")
    for item in response.retrieval.text_evidence:
        print(f"  {item.evidence_id} {item.chunk_id} score={item.score:.4f} {item.url}")


if __name__ == "__main__":
    main()
