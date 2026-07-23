from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TypedDict

import yaml

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from src.agent.answer_generator import GroundedAnswerGenerator
from src.agent.generators.base import AnswerGenerator
from src.agent.generators.factory import create_answer_generator
from src.graph.networkx_repository import NetworkXGraphRepository
from src.llm.base import LLMClient
from src.llm.config import AgentLLMSettings, LLMSettings
from src.llm.factory import create_llm_client
from src.retrieval.graph_retriever import GraphRetriever
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.intent_router import IntentRouter, RouteDecision
from src.retrieval.vector_retriever import TfidfVectorRetriever
from src.schemas import (
    AnswerPayload,
    EvidencePackingTrace,
    FinalResponse,
    GenerationCall,
    RetrievalResult,
    VerifyResult,
)
from src.verification.evidence_verifier import EvidenceVerifier

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    END = None
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


class AgentState(TypedDict, total=False):
    query: str
    route: RouteDecision
    retrieval: RetrievalResult
    answer_payload: AnswerPayload
    generation_trace: list[GenerationCall]
    evidence_packing_trace: list[EvidencePackingTrace]
    verification: VerifyResult
    retry_count: int
    started_at: float
    final_response: FinalResponse


class QAWorkflow:
    def __init__(
        self,
        retriever: HybridRetriever,
        graph_repo,
        router: IntentRouter | None = None,
        answer_generator: AnswerGenerator | None = None,
        verifier: EvidenceVerifier | None = None,
        top_k: int = 8,
    ):
        self.retriever = retriever
        self.graph_repo = graph_repo
        self.router = router or IntentRouter()
        self.answer_generator = answer_generator or GroundedAnswerGenerator(graph_repo)
        self.verifier = verifier or EvidenceVerifier()
        self.top_k = top_k
        self.engine_name = "langgraph" if LANGGRAPH_AVAILABLE else "local-state-machine"
        self._compiled = self._build_langgraph() if LANGGRAPH_AVAILABLE else None

    def invoke(self, query: str) -> FinalResponse:
        initial: AgentState = {"query": query, "retry_count": 0, "started_at": time.perf_counter()}
        if self._compiled is not None:
            state = self._compiled.invoke(initial)
        else:
            state = self._invoke_local(initial)
        return state["final_response"]

    def _build_langgraph(self):
        builder = StateGraph(AgentState)
        builder.add_node("route", self._route_node)
        builder.add_node("retrieve", self._retrieve_node)
        builder.add_node("answer", self._answer_node)
        builder.add_node("verify", self._verify_node)
        builder.add_node("retry", self._retry_node)
        builder.add_node("finalize", self._finalize_node)
        builder.set_entry_point("route")
        builder.add_edge("route", "retrieve")
        builder.add_edge("retrieve", "answer")
        builder.add_edge("answer", "verify")
        builder.add_conditional_edges(
            "verify",
            self._next_after_verify,
            {"retry": "retry", "pass": "finalize", "refuse": "finalize"},
        )
        builder.add_edge("retry", "answer")
        builder.add_edge("finalize", END)
        return builder.compile()

    def _route_node(self, state: AgentState) -> dict:
        return {"route": self.router.route(state["query"])}

    def _retrieve_node(self, state: AgentState) -> dict:
        route = state["route"]
        return {"retrieval": self._retrieve(state["query"], route, state.get("retry_count", 0))}

    def _answer_node(self, state: AgentState) -> dict:
        payload = self.answer_generator.generate(state["query"], state["retrieval"])
        requested_backend = (
            "ollama"
            if payload.generator_backend == "ollama" or payload.fallback_used
            else "offline_rule"
        )
        call = GenerationCall(
            requested_backend=requested_backend,
            actual_backend=payload.generator_backend,
            fallback_used=payload.fallback_used,
            fallback_reason=payload.fallback_reason,
            attempts=payload.generation_attempts,
            latency_ms=payload.generation_latency_ms,
            structured_output_success=bool(
                requested_backend == "ollama"
                and payload.generator_backend == "ollama"
                and not payload.fallback_used
                and payload.generation_attempts > 0
            ),
        )
        result = {
            "answer_payload": payload,
            "generation_trace": [*state.get("generation_trace", []), call],
        }
        if payload.evidence_packing is not None:
            result["evidence_packing_trace"] = [
                *state.get("evidence_packing_trace", []),
                payload.evidence_packing,
            ]
        return result

    def _verify_node(self, state: AgentState) -> dict:
        return {
            "verification": self.verifier.verify(
                state["query"],
                state["answer_payload"],
                state["retrieval"],
                graph_repo=self.graph_repo,
                retry_count=state.get("retry_count", 0),
            )
        }

    def _retry_node(self, state: AgentState) -> dict:
        retry_count = state.get("retry_count", 0) + 1
        route = state["route"]
        retry_route = RouteDecision(route.intent, "hybrid", "verification requested broader retrieval")
        return {
            "retry_count": retry_count,
            "retrieval": self._retrieve(state["query"], retry_route, retry_count),
        }

    def _next_after_verify(self, state: AgentState) -> str:
        decision = state["verification"].decision
        if decision == "retry" and state.get("retry_count", 0) < self.verifier.max_retries:
            return "retry"
        return decision

    def _finalize_node(self, state: AgentState) -> dict:
        verification = state["verification"]
        answer = state["answer_payload"].answer
        if verification.decision == "refuse":
            answer = self.answer_generator.refusal_answer()
        latency_ms = int((time.perf_counter() - state["started_at"]) * 1000)
        return {
            "final_response": FinalResponse(
                query=state["query"],
                answer=answer,
                answer_payload=state["answer_payload"],
                retrieval=state["retrieval"],
                verification=verification,
                generation_trace=state.get("generation_trace", []),
                evidence_packing_trace=state.get("evidence_packing_trace", []),
                latency_ms=latency_ms,
                retry_count=state.get("retry_count", 0),
            )
        }

    def _invoke_local(self, state: AgentState) -> AgentState:
        state.update(self._route_node(state))
        state.update(self._retrieve_node(state))
        while True:
            state.update(self._answer_node(state))
            state.update(self._verify_node(state))
            if self._next_after_verify(state) != "retry":
                state.update(self._finalize_node(state))
                return state
            state.update(self._retry_node(state))

    def _retrieve(self, query: str, route: RouteDecision, retry_count: int) -> RetrievalResult:
        multiplier = 2 if retry_count else 1
        return self.retriever.retrieve(query, route.intent, route.mode, top_k=self.top_k * multiplier)


def build_default_workflow(
    project_root: Path | None = None,
    *,
    router: IntentRouter | None = None,
    verifier=None,
    answer_generator: AnswerGenerator | None = None,
    llm_client: LLMClient | None = None,
    generator_backend: str | None = None,
) -> QAWorkflow:
    root = project_root or Path(__file__).resolve().parents[2]
    settings = yaml.safe_load((root / "config" / "settings.yaml").read_text(encoding="utf-8"))
    entities_path = root / settings["paths"]["entities"]
    relations_path = root / settings["paths"]["relations"]
    chunks_path = root / settings["paths"]["chunks"]
    index_dir = root / settings["paths"]["chroma"]

    if load_dotenv:
        load_dotenv(root / ".env")
    agent_values = dict(settings.get("agent", {}))
    backend_override = generator_backend or os.environ.get("AGENT_GENERATOR_BACKEND")
    if backend_override:
        agent_values["generator_backend"] = backend_override
    agent_settings = AgentLLMSettings.model_validate(agent_values)
    backend = os.environ.get("GRAPH_BACKEND", settings["project"].get("graph_backend", "networkx")).lower()
    if backend == "networkx":
        graph_repo = NetworkXGraphRepository(entities_path, relations_path, approved_only=True)
    elif backend == "neo4j":
        from src.graph.neo4j_repository import Neo4jGraphRepository

        required = ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise RuntimeError(f"Neo4j backend missing environment variables: {', '.join(missing)}")
        graph_repo = Neo4jGraphRepository(
            os.environ["NEO4J_URI"],
            os.environ["NEO4J_USER"],
            os.environ["NEO4J_PASSWORD"],
        )
    else:
        raise RuntimeError(f"Unsupported GRAPH_BACKEND: {backend}")
    graph_retriever = GraphRetriever(graph_repo, entities_path, chunks_path)
    vector_retriever = TfidfVectorRetriever(index_dir)
    hybrid_retriever = HybridRetriever(
        vector_retriever,
        graph_retriever,
        default_top_k=int(settings["retrieval"].get("final_top_k", 8)),
    )
    verification = settings.get("verification", {})
    default_verifier = EvidenceVerifier(
        pass_threshold=float(verification.get("pass_threshold", 0.80)),
        retry_threshold=float(verification.get("retry_threshold", 0.55)),
        max_retries=int(verification.get("max_retries", 1)),
        min_vector_score=float(verification.get("min_vector_score", 0.08)),
    )
    if verifier is None:
        verifier = default_verifier
    if answer_generator is None:
        if agent_settings.generator_backend == "llm" and llm_client is None:
            llm_settings = LLMSettings.model_validate(settings.get("llm", {}))
            llm_client = create_llm_client(llm_settings)
        answer_generator = create_answer_generator(
            agent_settings,
            graph_repo=graph_repo,
            llm_client=llm_client,
        )
    return QAWorkflow(
        hybrid_retriever,
        graph_repo,
        router=router,
        answer_generator=answer_generator,
        verifier=verifier,
        top_k=int(settings["retrieval"].get("final_top_k", 8)),
    )
