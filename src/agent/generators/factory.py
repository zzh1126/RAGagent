from __future__ import annotations

from src.agent.answer_generator import GroundedAnswerGenerator
from src.agent.generators.base import AnswerGenerator
from src.agent.generators.context import EvidenceContextSerializer
from src.agent.generators.fallback import FallbackAnswerGenerator
from src.agent.generators.llm_generator import LLMAnswerGenerator
from src.llm.base import LLMClient
from src.llm.config import AgentLLMSettings


def create_answer_generator(
    settings: AgentLLMSettings,
    *,
    graph_repo=None,
    llm_client: LLMClient | None = None,
) -> AnswerGenerator:
    offline = GroundedAnswerGenerator(graph_repo)
    if settings.generator_backend == "offline_rule":
        return offline
    if llm_client is None:
        raise ValueError("llm_client is required when generator_backend=llm")

    context_serializer = EvidenceContextSerializer(
        max_text_evidence=settings.max_text_evidence,
        max_graph_paths=settings.max_graph_paths,
        max_chars_per_evidence=settings.max_chars_per_evidence,
        max_context_chars=settings.max_context_chars,
    )
    primary = LLMAnswerGenerator(llm_client, context_serializer=context_serializer)
    return FallbackAnswerGenerator(primary=primary, fallback=offline)
