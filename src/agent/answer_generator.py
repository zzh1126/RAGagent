from __future__ import annotations

from src.schemas import AnswerClaim, AnswerPayload, GraphTriple, RetrievalResult


RELATION_LABELS = {
    "BELONGS_TO": "属于",
    "SOLVES": "可用于解决",
    "USES": "使用",
    "REQUIRES": "需要",
    "EVALUATED_BY": "可用来评估",
    "DIFFERS_FROM": "与之存在差异",
    "HAS_ADVANTAGE": "的优势与之相关",
    "HAS_LIMITATION": "的局限与之相关",
    "MITIGATES": "有助于缓解",
}


class GroundedAnswerGenerator:
    """Create deterministic, citation-bearing answers without an online LLM."""

    def __init__(self, graph_repo=None):
        self.graph_repo = graph_repo

    def generate(self, query: str, retrieval: RetrievalResult) -> AnswerPayload:
        evidence_by_chunk = {item.chunk_id: item for item in retrieval.text_evidence}
        claims: list[AnswerClaim] = []

        for path in retrieval.graph_paths:
            for triple in path.triples:
                evidence_ids = self._evidence_ids(triple.evidence_chunk_ids, evidence_by_chunk)
                if not evidence_ids:
                    continue
                claims.append(
                    AnswerClaim(
                        claim=self._triple_sentence(triple),
                        evidence_ids=evidence_ids,
                        graph_path_ids=[path.path_id],
                        relation_id=triple.relation_id,
                    )
                )

        if retrieval.intent == "comparison":
            self._append_comparison_context(retrieval, evidence_by_chunk, claims)

        if retrieval.intent == "definition" or not claims:
            self._append_entity_definition_claim(retrieval, evidence_by_chunk, claims)

        if not claims and retrieval.text_evidence:
            item = retrieval.text_evidence[0]
            excerpt = self._excerpt(item.display_text)
            claims.append(
                AnswerClaim(
                    claim=f"官方文档相关原文指出：{excerpt}",
                    evidence_ids=[item.evidence_id],
                )
            )

        if not claims:
            return AnswerPayload(
                answer="当前六页 scikit-learn 官方文档中没有检索到足以支持该问题的证据。",
                claims=[],
                graph_paths=[],
                confidence=0.0,
            )

        lines = [claim.claim + " " + self._citation_text(claim.evidence_ids) for claim in claims]
        references = self._references(retrieval)
        answer = "\n".join(f"- {line}" for line in lines)
        if any(marker in query for marker in ("一定", "必然", "always", "guaranteed")):
            answer = "注意：当前证据只支持下列具体关系，不足以证明该比较在所有数据集上都成立。\n" + answer
        if references:
            answer += "\n\n官方证据：\n" + "\n".join(references)

        confidence = min(1.0, 0.55 + 0.08 * len(claims) + 0.05 * len(retrieval.text_evidence))
        return AnswerPayload(
            answer=answer,
            claims=claims,
            graph_paths=[path.path_id for path in retrieval.graph_paths],
            confidence=confidence,
            generator_backend="offline_rule",
        )

    @staticmethod
    def refusal_answer() -> str:
        return "现有六页 scikit-learn 官方文档证据不足，无法对该问题作出可靠回答。"

    def _append_entity_definition_claim(
        self,
        retrieval: RetrievalResult,
        evidence_by_chunk: dict,
        claims: list[AnswerClaim],
    ) -> None:
        if not retrieval.entities or self.graph_repo is None:
            return
        entity = retrieval.entities[0]
        metadata = self.graph_repo.find_entity(entity.entity_id)
        description = (metadata or {}).get("description_zh", "").strip()
        if not description:
            return
        evidence_ids = [item.evidence_id for item in retrieval.text_evidence[:2]]
        if not evidence_ids:
            return
        claims.append(
            AnswerClaim(
                claim=f"{entity.name_zh}：{description}。",
                evidence_ids=evidence_ids,
            )
        )

    @staticmethod
    def _triple_sentence(triple: GraphTriple) -> str:
        relation = triple.relation
        if relation == "HAS_ADVANTAGE" and triple.target_name == "方差":
            return f"{triple.source_name}有助于降低方差，因此通常比单一估计器更稳定。"
        if relation == "HAS_ADVANTAGE" and triple.target_name == "噪声数据":
            return f"{triple.source_name}对噪声数据具有一定鲁棒性。"
        if relation == "HAS_ADVANTAGE" and triple.target_name == "可解释性":
            return f"{triple.source_name}具有可解释性方面的优势。"
        if relation == "HAS_LIMITATION":
            if triple.target_name == "类别不平衡问题":
                return f"{triple.source_name}在类别不平衡场景下存在局限。"
            return f"{triple.source_name}的一个已标注局限与“{triple.target_name}”有关。"
        if relation == "HAS_ADVANTAGE" and triple.target_name == "类别不平衡问题":
            return f"{triple.source_name}适合用于类别不平衡场景的评估。"
        if relation == "MITIGATES":
            return f"{triple.source_name}有助于缓解“{triple.target_name}”。"
        if relation == "DIFFERS_FROM":
            return f"{triple.source_name}与{triple.target_name}在方法机制上存在差异。"
        label = RELATION_LABELS.get(relation, relation)
        return f"{triple.source_name}{label}{triple.target_name}。"

    def _append_comparison_context(
        self,
        retrieval: RetrievalResult,
        evidence_by_chunk: dict,
        claims: list[AnswerClaim],
    ) -> None:
        seen = {claim.claim for claim in claims}
        for entity in retrieval.entities[:2]:
            if self.graph_repo is None:
                continue
            metadata = self.graph_repo.find_entity(entity.entity_id) or {}
            description = metadata.get("description_zh", "").strip()
            if not description:
                continue
            evidence_ids = [item.evidence_id for item in retrieval.text_evidence if entity.name_en.lower() in item.display_text.lower()][:2]
            if not evidence_ids:
                evidence_ids = [item.evidence_id for item in retrieval.text_evidence[:1]]
            claim_text = f"{entity.name_zh}的定义特征是：{description}。"
            if claim_text not in seen and evidence_ids:
                claims.append(AnswerClaim(claim=claim_text, evidence_ids=evidence_ids))
                seen.add(claim_text)

    @staticmethod
    def _evidence_ids(chunk_ids: list[str], evidence_by_chunk: dict) -> list[str]:
        return list(dict.fromkeys(evidence_by_chunk[chunk_id].evidence_id for chunk_id in chunk_ids if chunk_id in evidence_by_chunk))

    @staticmethod
    def _citation_text(evidence_ids: list[str]) -> str:
        return "".join(f"[{evidence_id}]" for evidence_id in evidence_ids)

    @staticmethod
    def _excerpt(text: str, max_chars: int = 260) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= max_chars:
            return normalized
        return normalized[: max_chars - 3].rstrip() + "..."

    @staticmethod
    def _references(retrieval: RetrievalResult) -> list[str]:
        return [
            f"[{item.evidence_id}] {item.page_title} | {' > '.join(item.heading_path)} | {item.url}"
            for item in retrieval.text_evidence[:5]
        ]
