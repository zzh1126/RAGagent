from __future__ import annotations

from src.retrieval.query_rewrite import rewrite_query_to_english
from src.schemas import AnswerClaim, AnswerPayload, RetrievalResult, VerifyResult


CLAIM_GROUNDING_TERMS = {
    "随机森林": ("random forest",),
    "逻辑回归": ("logistic regression",),
    "决策树": ("decision tree",),
    "装袋法": ("bagging",),
    "集成学习": ("ensemble",),
    "自助采样": ("bootstrap", "with replacement"),
    "有放回": ("with replacement", "bootstrap"),
    "随机子集": ("random subset",),
    "基模型": ("base estimator", "base learner"),
    "基学习器": ("base estimator", "base learner"),
    "聚合": ("aggregate", "aggregation", "combine"),
    "平均": ("average", "averaging"),
    "投票": ("voting", "vote"),
    "方差": ("variance",),
    "偏差": ("bias",),
    "权重": ("weight", "weighted"),
    "加权": ("weight", "weighted"),
    "迭代": ("iteration", "iterative"),
    "错误样本": ("misclassified", "incorrectly classified", "error example"),
    "特征缩放": ("feature scaling", "scaled"),
    "缩放特征": ("feature scaling", "scaled", "scale your data"),
    "正则化": ("regularization",),
    "过拟合": ("overfitting", "over-fit"),
    "类别不平衡": ("class imbalance", "imbalanced"),
    "精确率": ("precision",),
    "召回率": ("recall",),
    "平衡准确率": ("balanced accuracy",),
    "f1": ("f1", "f-measure", "f measure"),
}


class EvidenceVerifier:
    def __init__(
        self,
        pass_threshold: float = 0.80,
        retry_threshold: float = 0.55,
        max_retries: int = 1,
        min_vector_score: float = 0.08,
    ):
        self.pass_threshold = pass_threshold
        self.retry_threshold = retry_threshold
        self.max_retries = max_retries
        self.min_vector_score = min_vector_score

    def verify(
        self,
        query: str,
        answer: AnswerPayload,
        retrieval: RetrievalResult,
        graph_repo=None,
        retry_count: int = 0,
    ) -> VerifyResult:
        evidence_by_id = {item.evidence_id: item for item in retrieval.text_evidence}
        valid_paths = self._valid_path_count(retrieval, graph_repo)
        path_total = len(retrieval.graph_paths)
        retrieval_path_validity = valid_paths / path_total if path_total else 1.0
        available_path_ids = {path.path_id for path in retrieval.graph_paths}
        answer_path_ids = list(
            dict.fromkeys(
                [*answer.graph_paths]
                + [path_id for claim in answer.claims for path_id in claim.graph_path_ids]
            )
        )
        valid_answer_path_count = sum(path_id in available_path_ids for path_id in answer_path_ids)
        answer_path_validity = (
            valid_answer_path_count / len(answer_path_ids) if answer_path_ids else 1.0
        )
        path_validity = min(retrieval_path_validity, answer_path_validity)

        unsupported: list[str] = list(answer.unsupported_claims)
        unknown_path_ids = sorted(set(answer_path_ids) - available_path_ids)
        if unknown_path_ids:
            unsupported.append(
                "回答引用了不存在的 graph_path_id: " + ", ".join(unknown_path_ids)
            )
        valid_reference_count = 0
        reference_count = 0
        supported_claim_count = 0
        for claim in answer.claims:
            claim_text = claim.claim.strip()
            claim_errors: list[str] = []
            refs = [str(ref) for ref in claim.evidence_ids]
            reference_count += len(refs)
            valid_refs = [ref for ref in refs if ref in evidence_by_id]
            valid_reference_count += len(valid_refs)
            has_relevant_evidence = self._has_relevant_evidence(valid_refs, evidence_by_id, claim, retrieval)
            if not valid_refs or not has_relevant_evidence:
                claim_errors.append(claim_text or "未命名 claim")
            if answer.generator_backend == "ollama":
                if not claim.supporting_quotes:
                    claim_errors.append(f"Claim 缺少可核验原文: {claim_text}")
                for quote in claim.supporting_quotes:
                    if quote.evidence_id not in refs:
                        claim_errors.append(
                            f"Claim 原文未绑定到 evidence_ids: {quote.evidence_id}"
                        )
                        continue
                    evidence_item = evidence_by_id.get(quote.evidence_id)
                    if evidence_item is None:
                        continue
                    normalized_quote = self._normalize_text(quote.quote)
                    normalized_evidence = self._normalize_text(evidence_item.display_text)
                    if normalized_quote not in normalized_evidence:
                        claim_errors.append(
                            f"Claim 原文不属于引用证据: {quote.evidence_id}"
                        )
                missing_terms = self._missing_grounding_terms(claim)
                if missing_terms:
                    claim_errors.append(
                        "Claim 关键术语未被原文覆盖: " + ", ".join(missing_terms)
                    )
            if claim_errors:
                unsupported.extend(claim_errors)
            else:
                supported_claim_count += 1

        claim_total = len(answer.claims)
        claim_coverage = supported_claim_count / claim_total if claim_total else 0.0
        citation_validity = valid_reference_count / reference_count if reference_count else 0.0
        retrieval_sufficiency = self._retrieval_sufficiency(retrieval, path_validity)
        if not self._query_alignment(query, retrieval, graph_repo):
            claim_coverage = 0.0
            unsupported.append("检索证据未覆盖问题中的关键限定条件")
        unsupported = list(dict.fromkeys(item for item in unsupported if item))
        evidence_score = round(
            0.30 * claim_coverage
            + 0.25 * citation_validity
            + 0.20 * path_validity
            + 0.25 * retrieval_sufficiency,
            4,
        )

        if not retrieval.text_evidence or not answer.claims:
            decision = "refuse"
        elif (
            evidence_score >= self.pass_threshold
            and claim_coverage >= 0.80
            and citation_validity >= 0.80
            and path_validity >= 0.80
            and not unsupported
        ):
            decision = "pass"
        elif (
            retry_count < self.max_retries
            and (
                evidence_score >= self.retry_threshold
                or bool(unsupported)
                or retrieval_sufficiency < 0.5
            )
        ):
            decision = "retry"
        else:
            decision = "refuse"

        return VerifyResult(
            decision=decision,
            evidence_score=evidence_score,
            claim_coverage=round(claim_coverage, 4),
            citation_validity=round(citation_validity, 4),
            path_validity=round(path_validity, 4),
            retrieval_sufficiency=round(retrieval_sufficiency, 4),
            unsupported_claims=unsupported,
        )

    def _valid_path_count(self, retrieval: RetrievalResult, graph_repo) -> int:
        if not retrieval.graph_paths:
            return 0
        if graph_repo is None:
            return 0
        return sum(
            1
            for path in retrieval.graph_paths
            if graph_repo.validate_path([triple.model_dump() for triple in path.triples])
        )

    def _has_relevant_evidence(
        self,
        refs: list[str],
        evidence_by_id: dict,
        claim: AnswerClaim,
        retrieval: RetrievalResult,
    ) -> bool:
        if not refs:
            return False
        if claim.relation_id and retrieval.graph_paths:
            return any(
                claim.relation_id == triple.relation_id
                for path in retrieval.graph_paths
                for triple in path.triples
            )
        return any(evidence_by_id[ref].score >= self.min_vector_score for ref in refs)

    def _retrieval_sufficiency(self, retrieval: RetrievalResult, path_validity: float) -> float:
        if not retrieval.text_evidence:
            return 0.0
        if retrieval.graph_paths:
            return round(0.75 + 0.25 * path_validity, 4)
        max_score = max(item.score for item in retrieval.text_evidence)
        if max_score >= 0.25:
            return 1.0
        if max_score >= self.min_vector_score:
            return 0.82
        return 0.35

    def _query_alignment(self, query: str, retrieval: RetrievalResult, graph_repo=None) -> bool:
        evidence_text = " ".join(
            [
                item.display_text
                + " "
                + " ".join(item.heading_path)
                for item in retrieval.text_evidence
            ]
        ).lower()
        if not evidence_text:
            return False

        lowered = query.lower()
        if not self._premise_supported(lowered, retrieval, graph_repo):
            return False
        attribute_aliases = {
            "学习率": ("learning rate", "learning_rate"),
            "缺失值": ("missing value", "missing values"),
            "特征缩放": ("feature scaling", "scaling"),
            "正则化": ("regularization",),
            "参数": ("parameter", "n_estimators", "max_features", "max_depth"),
            "过拟合": ("overfitting", "over-fit"),
            "指标": ("metric", "score", "accuracy", "recall", "f1", "auc"),
            "类别不平衡": ("imbalanced", "class imbalance", "balanced accuracy"),
        }
        graph_relations = {
            triple.relation
            for path in retrieval.graph_paths
            for triple in path.triples
        }
        graph_attribute_support = {
            "特征缩放": {"REQUIRES", "USES"},
            "正则化": {"USES", "MITIGATES"},
            "过拟合": {"HAS_LIMITATION", "MITIGATES"},
            "指标": {"EVALUATED_BY", "HAS_ADVANTAGE", "HAS_LIMITATION"},
            "类别不平衡": {"HAS_ADVANTAGE", "HAS_LIMITATION"},
        }
        for marker, aliases in attribute_aliases.items():
            if marker in lowered and graph_attribute_support.get(marker, set()) & graph_relations:
                continue
            if marker in lowered and not any(alias in evidence_text for alias in aliases):
                return False
            if marker in lowered and marker in {"学习率", "缺失值", "特征缩放", "正则化", "参数"}:
                entity_terms = self._entity_terms(retrieval)
                if entity_terms and not any(
                    any(alias in item_text for alias in aliases)
                    and any(term in section_text for term in entity_terms)
                    for item_text, section_text in self._evidence_items(retrieval)
                ):
                    return False

        if "稳定" in lowered:
            graph_relations = {
                triple.relation
                for path in retrieval.graph_paths
                for triple in path.triples
            }
            if not ({"HAS_ADVANTAGE", "MITIGATES"} & graph_relations) and not any(
                term in evidence_text for term in ("variance", "robust", "generalizability")
            ):
                return False

        if any(marker in lowered for marker in ("区别", "不同", "比较", "对比", "相比")):
            if not retrieval.entities or len(retrieval.entities) < 2:
                return False

        if not retrieval.entities and not retrieval.graph_paths:
            query_terms = [term for term in rewrite_query_to_english(query).lower().split() if len(term) > 2]
            return max((item.score for item in retrieval.text_evidence), default=0.0) >= 0.15 and any(
                term in evidence_text for term in query_terms
            )

        return bool(retrieval.entities or retrieval.graph_paths)

    @staticmethod
    def _premise_supported(query: str, retrieval: RetrievalResult, graph_repo) -> bool:
        if graph_repo is None or not any(marker in query for marker in ("吗", "是否", "是不是")):
            return True
        algorithms = [entity for entity in retrieval.entities if entity.type == "Algorithm"]
        if not algorithms:
            return True

        target_ids = {
            entity.entity_id
            for entity in retrieval.entities
            if entity.entity_id != algorithms[0].entity_id
            and entity.type in {"Task", "MethodFamily", "Technique", "Concept", "Metric"}
        }
        keyword_targets = {
            "监督分类": "TASK_CLASS",
            "分类算法": "TASK_CLASS",
            "回归算法": "TASK_REG",
            "无监督": "TASK_CLUSTER",
            "聚类算法": "TASK_CLUSTER",
            "线性模型": "FAM_LINEAR",
            "核方法": "FAM_KERNEL",
            "集成学习": "FAM_ENSEMBLE",
        }
        target_ids.update(target_id for marker, target_id in keyword_targets.items() if marker in query)
        if not target_ids:
            return True

        algorithm_id = algorithms[0].entity_id
        neighbors = graph_repo.get_neighbors(algorithm_id)
        return any(
            row["source_id"] == algorithm_id and row["target_id"] in target_ids
            for row in neighbors
        )

    @staticmethod
    def _evidence_items(retrieval: RetrievalResult) -> list[tuple[str, str]]:
        return [
            (
                (item.display_text + " " + " ".join(item.heading_path)).lower(),
                " ".join(item.heading_path[1:]).lower(),
            )
            for item in retrieval.text_evidence
        ]

    @staticmethod
    def _entity_terms(retrieval: RetrievalResult) -> list[str]:
        terms: list[str] = []
        for entity in retrieval.entities:
            english = entity.name_en.lower()
            terms.extend([english, english.replace(" ", ""), entity.name_zh.lower()])
        for path in retrieval.graph_paths:
            for triple in path.triples:
                terms.extend([triple.source_name.lower(), triple.target_name.lower()])
        return [term for term in terms if term]

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(value.split()).casefold()

    @classmethod
    def _missing_grounding_terms(cls, claim: AnswerClaim) -> list[str]:
        claim_text = cls._normalize_text(claim.claim)
        quoted_text = " ".join(
            cls._normalize_text(quote.quote) for quote in claim.supporting_quotes
        )
        return [
            marker
            for marker, aliases in CLAIM_GROUNDING_TERMS.items()
            if marker.casefold() in claim_text
            and not any(alias.casefold() in quoted_text for alias in aliases)
        ]
