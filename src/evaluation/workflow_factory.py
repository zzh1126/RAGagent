from __future__ import annotations

from pathlib import Path

from src.agent.workflow import build_default_workflow
from src.evaluation.config import ExperimentDefinition, ExperimentRouterMode
from src.retrieval.intent_router import IntentRouter, RouteDecision
from src.schemas import AnswerPayload, RetrievalResult, VerifyResult


class ConfiguredRouter:
    """Keep intent detection while enforcing an experiment's route policy."""

    FIXED_MODES = {
        "fixed_vector": "vector",
        "fixed_graph": "graph",
        "fixed_hybrid": "hybrid",
    }

    def __init__(self, router_mode: ExperimentRouterMode, base_router: IntentRouter | None = None):
        self.router_mode = router_mode
        self.base_router = base_router or IntentRouter()

    def route(self, query: str) -> RouteDecision:
        decision = self.base_router.route(query)
        if self.router_mode == "adaptive":
            return decision
        if self.router_mode == "none":
            raise ValueError("the Direct LLM configuration has no retrieval route")
        forced_mode = self.FIXED_MODES[self.router_mode]
        return RouteDecision(
            intent=decision.intent,
            mode=forced_mode,
            reason=f"experiment fixed route: {self.router_mode}",
        )


class NoVerifier:
    """A deliberate verifier ablation that accepts generated output without retry."""

    max_retries = 0

    def verify(
        self,
        query: str,
        answer: AnswerPayload,
        retrieval: RetrievalResult,
        graph_repo=None,
        retry_count: int = 0,
    ) -> VerifyResult:
        unsupported = list(answer.unsupported_claims)
        if not unsupported:
            unsupported = [
                claim.claim
                for claim in answer.claims
                if not claim.evidence_ids
            ]
        return VerifyResult(
            decision="pass",
            evidence_score=0.0,
            claim_coverage=0.0,
            citation_validity=0.0,
            path_validity=0.0,
            retrieval_sufficiency=0.0,
            unsupported_claims=unsupported,
        )


def build_experiment_workflow(
    project_root: Path,
    experiment: ExperimentDefinition,
):
    if not experiment.enabled:
        raise ValueError(f"experiment is disabled: {experiment.id}")
    if experiment.answer_generator != "offline_rule":
        raise ValueError(
            f"only offline_rule is available in this runner, got {experiment.answer_generator}"
        )
    if experiment.retrieval_mode == "none" or experiment.router_mode == "none":
        raise ValueError(f"experiment has no runnable retrieval route: {experiment.id}")

    router = ConfiguredRouter(experiment.router_mode)
    verifier = None if experiment.verifier_enabled else NoVerifier()
    return build_default_workflow(project_root, router=router, verifier=verifier)
