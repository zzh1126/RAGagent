from __future__ import annotations

from dataclasses import dataclass

from src.schemas import RetrievalMode


@dataclass(frozen=True)
class RouteDecision:
    intent: str
    mode: RetrievalMode
    reason: str


class IntentRouter:
    """Deterministic first-stage router for the frozen scikit-learn scope."""

    COMPARISON_MARKERS = (
        "区别",
        "不同",
        "比较",
        "对比",
        "相比",
        "一定比",
        "还是",
        " vs ",
        "versus",
        "difference",
    )
    EXPLANATION_MARKERS = (
        "为什么",
        "为何",
        "机制",
        "原理",
        "如何工作",
        "优点",
        "优势",
        "缺点",
        "局限",
        "稳定",
        "why",
        "advantage",
    )
    RECOMMENDATION_MARKERS = (
        "用什么",
        "怎么选",
        "选择什么",
        "适合",
        "合适",
        "推荐",
        "哪个指标",
        "which metric",
    )
    DEFINITION_MARKERS = ("什么是", "是什么", "定义", "介绍", "含义", "what is")
    MULTI_HOP_MARKERS = ("关系", "关联", "通过什么", "如何影响", "共同", "路径", "relationship")
    RELATION_MARKERS = (
        "属于",
        "归属",
        "使用",
        "基于",
        "需要",
        "解决",
        "任务",
        "用于",
        "评估",
        "指标",
        "缓解",
        "belongs",
        "uses",
    )

    def route(self, query: str) -> RouteDecision:
        normalized = f" {query.strip().lower()} "
        if self._contains(normalized, self.COMPARISON_MARKERS):
            return RouteDecision("comparison", "hybrid", "comparison marker requires graph relations and text context")
        if self._contains(normalized, self.RECOMMENDATION_MARKERS):
            return RouteDecision("recommendation", "hybrid", "recommendation requires structured options and text evidence")
        if self._contains(normalized, self.EXPLANATION_MARKERS):
            return RouteDecision("explanation", "hybrid", "explanation benefits from graph facts and source passages")
        if self._contains(normalized, self.MULTI_HOP_MARKERS):
            return RouteDecision("multi_hop", "hybrid", "relationship query may require a two-hop graph path")
        if "任务" in normalized:
            return RouteDecision("relation", "graph", "task question maps to graph retrieval")
        if self._contains(normalized, self.DEFINITION_MARKERS):
            return RouteDecision("definition", "vector", "definition is primarily answered from the official text")
        if self._contains(normalized, self.RELATION_MARKERS):
            return RouteDecision("relation", "graph", "explicit relation marker maps to graph retrieval")
        return RouteDecision("general", "vector", "default to official-document retrieval")

    @staticmethod
    def _contains(query: str, markers: tuple[str, ...]) -> bool:
        return any(marker in query for marker in markers)
