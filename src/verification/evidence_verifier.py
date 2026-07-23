from __future__ import annotations

import time

from src.retrieval.query_rewrite import rewrite_query_to_english
from src.schemas import (
    AnswerClaim,
    AnswerPayload,
    ClaimResult,
    RetrievalResult,
    VerifierDecisionPolicy,
    VerifyResult,
)


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
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"

    def __init__(
        self,
        pass_threshold: float = 0.80,
        retry_threshold: float = 0.55,
        max_retries: int = 1,
        min_vector_score: float = 0.08,
        decision_policy: VerifierDecisionPolicy = "partial_pass",
    ):
        if decision_policy not in {"strict", "partial_pass"}:
            raise ValueError(f"unsupported verifier decision policy: {decision_policy}")
        self.pass_threshold = pass_threshold
        self.retry_threshold = retry_threshold
        self.max_retries = max_retries
        self.min_vector_score = min_vector_score
        self.decision_policy = decision_policy

    def verify(
        self,
        query: str,
        answer: AnswerPayload,
        retrieval: RetrievalResult,
        graph_repo=None,
        retry_count: int = 0,
    ) -> VerifyResult:
        started_at = time.perf_counter()
        evidence_by_id = {item.evidence_id: item for item in retrieval.text_evidence}
        valid_path_ids = self._valid_path_ids(retrieval, graph_repo)
        path_total = len(retrieval.graph_paths)
        retrieval_path_validity = len(valid_path_ids) / path_total if path_total else 1.0
        available_path_ids = {path.path_id for path in retrieval.graph_paths}
        answer_path_ids = list(
            dict.fromkeys(
                [*answer.graph_paths]
                + [path_id for claim in answer.claims for path_id in claim.graph_path_ids]
            )
        )
        valid_answer_path_count = sum(path_id in valid_path_ids for path_id in answer_path_ids)
        answer_path_validity = (
            valid_answer_path_count / len(answer_path_ids) if answer_path_ids else 1.0
        )
        path_validity = min(retrieval_path_validity, answer_path_validity)

        unsupported: list[str] = list(answer.unsupported_claims)
        reason_codes: list[str] = []
        if answer.unsupported_claims:
            reason_codes.append("generator_reported_gap")
        unknown_path_ids = sorted(set(answer_path_ids) - available_path_ids)
        if unknown_path_ids:
            unsupported.append(
                "回答引用了不存在的 graph_path_id: " + ", ".join(unknown_path_ids)
            )
            reason_codes.append("unknown_graph_path")
        valid_reference_count = 0
        reference_count = 0
        claim_results: list[ClaimResult] = []
        for claim_index, claim in enumerate(answer.claims, start=1):
            claim_result, claim_messages, claim_reference_count, claim_valid_count = (
                self._verify_claim(
                    claim_index,
                    claim,
                    answer,
                    retrieval,
                    evidence_by_id,
                    available_path_ids,
                    valid_path_ids,
                )
            )
            claim_results.append(claim_result)
            unsupported.extend(claim_messages)
            reference_count += claim_reference_count
            valid_reference_count += claim_valid_count

        premise_supported = self._premise_supported(query.lower(), retrieval, graph_repo)
        if not premise_supported:
            reason_codes.append("premise_not_supported")
            unsupported.append("问题前提与当前知识图谱证据不一致")
            claim_results = self._invalidate_claim_results(
                claim_results,
                "premise_not_supported",
            )
        elif not self._query_alignment(query, retrieval, graph_repo):
            reason_codes.append("query_alignment_failed")
            unsupported.append("检索证据未覆盖问题中的关键限定条件")
            claim_results = self._invalidate_claim_results(
                claim_results,
                "query_alignment_failed",
            )

        claim_total = len(answer.claims)
        supported_claim_count = sum(result.supported for result in claim_results)
        claim_coverage = supported_claim_count / claim_total if claim_total else 0.0
        citation_validity = valid_reference_count / reference_count if reference_count else 0.0
        retrieval_sufficiency = self._retrieval_sufficiency(retrieval, path_validity)
        unsupported = list(dict.fromkeys(item for item in unsupported if item))
        reason_codes = list(dict.fromkeys(reason_codes))
        evidence_score = round(
            0.30 * claim_coverage
            + 0.25 * citation_validity
            + 0.20 * path_validity
            + 0.25 * retrieval_sufficiency,
            4,
        )

        decision = self._decide(
            answer=answer,
            retrieval=retrieval,
            claim_total=claim_total,
            supported_claim_count=supported_claim_count,
            evidence_score=evidence_score,
            citation_validity=citation_validity,
            path_validity=path_validity,
            retrieval_sufficiency=retrieval_sufficiency,
            unsupported=unsupported,
            reason_codes=reason_codes,
            retry_count=retry_count,
        )
        supported_claim_ids = [
            result.claim_id for result in claim_results if result.supported
        ]
        unsupported_claim_ids = [
            result.claim_id for result in claim_results if not result.supported
        ]
        if decision == "pass":
            retained_claim_ids = list(supported_claim_ids)
        elif decision == "partial_pass" and self.decision_policy == "partial_pass":
            retained_claim_ids = list(supported_claim_ids)
        else:
            retained_claim_ids = []
        retained_claim_id_set = set(retained_claim_ids)
        claim_results = [
            result.model_copy(
                update={"retained": result.claim_id in retained_claim_id_set}
            )
            for result in claim_results
        ]
        removed_claim_ids = [
            result.claim_id for result in claim_results if not result.retained
        ]
        retained_claim_indexes = [
            result.claim_index for result in claim_results if result.retained
        ]
        partial_pass_reason = None
        if decision == "partial_pass":
            partial_pass_reason = (
                "至少一个 Claim 受证据支持，但其余 Claim 或问题方面缺少足够证据"
            )

        return VerifyResult(
            decision=decision,
            decision_policy=self.decision_policy,
            evidence_score=evidence_score,
            claim_coverage=round(claim_coverage, 4),
            citation_validity=round(citation_validity, 4),
            path_validity=round(path_validity, 4),
            retrieval_sufficiency=round(retrieval_sufficiency, 4),
            unsupported_claims=unsupported,
            reason_codes=reason_codes,
            claim_results=claim_results,
            generated_claim_count=claim_total,
            supported_claim_count=supported_claim_count,
            removed_claim_count=len(removed_claim_ids),
            supported_claim_ids=supported_claim_ids,
            unsupported_claim_ids=unsupported_claim_ids,
            retained_claim_ids=retained_claim_ids,
            removed_claim_ids=removed_claim_ids,
            retained_claim_indexes=retained_claim_indexes,
            partial_pass_reason=partial_pass_reason,
            verification_latency_ms=round(
                (time.perf_counter() - started_at) * 1000,
                3,
            ),
        )

    def _verify_claim(
        self,
        claim_index: int,
        claim: AnswerClaim,
        answer: AnswerPayload,
        retrieval: RetrievalResult,
        evidence_by_id: dict,
        available_path_ids: set[str],
        valid_path_ids: set[str],
    ) -> tuple[ClaimResult, list[str], int, int]:
        claim_id = f"C{claim_index}"
        reason_codes: list[str] = []
        messages: list[str] = []

        def add_reason(code: str, message: str) -> None:
            if code not in reason_codes:
                reason_codes.append(code)
            if message and message not in messages:
                messages.append(message)

        evidence_ids = [str(item) for item in claim.evidence_ids]
        valid_evidence_ids = [
            evidence_id for evidence_id in evidence_ids if evidence_id in evidence_by_id
        ]
        unknown_evidence_ids = sorted(set(evidence_ids) - set(valid_evidence_ids))
        if not evidence_ids:
            add_reason(
                "missing_evidence_reference",
                f"{claim_id} 缺少 evidence_id",
            )
        if unknown_evidence_ids:
            add_reason(
                "unknown_evidence_id",
                f"{claim_id} 引用了不存在的 evidence_id: "
                + ", ".join(unknown_evidence_ids),
            )

        graph_path_ids = [str(item) for item in claim.graph_path_ids]
        valid_graph_path_ids = [
            path_id for path_id in graph_path_ids if path_id in valid_path_ids
        ]
        unknown_graph_path_ids = sorted(set(graph_path_ids) - available_path_ids)
        invalid_graph_path_ids = sorted(
            (set(graph_path_ids) & available_path_ids) - valid_path_ids
        )
        if unknown_graph_path_ids:
            add_reason(
                "unknown_graph_path",
                f"{claim_id} 引用了不存在的 graph_path_id: "
                + ", ".join(unknown_graph_path_ids),
            )
        if invalid_graph_path_ids:
            add_reason(
                "invalid_graph_path",
                f"{claim_id} 引用的图路径未通过校验: "
                + ", ".join(invalid_graph_path_ids),
            )
        if claim.relation_id and not self._relation_id_is_valid(claim, retrieval):
            add_reason(
                "invalid_relation_id",
                f"{claim_id} 引用了无效或未绑定路径的 relation_id: {claim.relation_id}",
            )

        if valid_evidence_ids and not self._has_relevant_evidence(
            valid_evidence_ids,
            evidence_by_id,
            claim,
            retrieval,
        ):
            add_reason(
                "evidence_not_relevant",
                f"{claim_id} 的引用证据未达到相关性要求",
            )

        if answer.generator_backend == "ollama":
            if not claim.supporting_quotes:
                add_reason(
                    "missing_supporting_quote",
                    f"{claim_id} 缺少可核验原文",
                )
            quoted_evidence_ids: set[str] = set()
            for quote in claim.supporting_quotes:
                if quote.evidence_id not in evidence_ids:
                    add_reason(
                        "quote_not_bound",
                        f"{claim_id} 的 quote 未绑定到 evidence_ids: {quote.evidence_id}",
                    )
                    continue
                quoted_evidence_ids.add(quote.evidence_id)
                evidence_item = evidence_by_id.get(quote.evidence_id)
                if evidence_item is None:
                    continue
                normalized_quote = self._normalize_verbatim_text(quote.quote)
                normalized_evidence = self._normalize_verbatim_text(
                    evidence_item.display_text
                )
                if normalized_quote not in normalized_evidence:
                    add_reason(
                        "quote_not_in_source",
                        f"{claim_id} 的 quote 不属于引用证据: {quote.evidence_id}",
                    )
            missing_quote_ids = sorted(set(evidence_ids) - quoted_evidence_ids)
            if missing_quote_ids:
                add_reason(
                    "missing_quote_for_evidence_id",
                    f"{claim_id} 的 evidence_id 缺少 quote: "
                    + ", ".join(missing_quote_ids),
                )
            missing_terms = self._missing_grounding_terms(claim)
            if missing_terms:
                add_reason(
                    "missing_grounding_term",
                    f"{claim_id} 的关键术语未被原文覆盖: "
                    + ", ".join(missing_terms),
                )

        supported = not reason_codes
        return (
            ClaimResult(
                claim_id=claim_id,
                claim_index=claim_index,
                claim=claim.claim.strip() or "未命名 Claim",
                status=self.SUPPORTED if supported else self.UNSUPPORTED,
                supported=supported,
                retained=False,
                evidence_ids=evidence_ids,
                valid_evidence_ids=valid_evidence_ids,
                graph_path_ids=graph_path_ids,
                valid_graph_path_ids=valid_graph_path_ids,
                relation_id=claim.relation_id,
                reason_codes=reason_codes,
            ),
            messages,
            len(evidence_ids),
            len(valid_evidence_ids),
        )

    def _decide(
        self,
        *,
        answer: AnswerPayload,
        retrieval: RetrievalResult,
        claim_total: int,
        supported_claim_count: int,
        evidence_score: float,
        citation_validity: float,
        path_validity: float,
        retrieval_sufficiency: float,
        unsupported: list[str],
        reason_codes: list[str],
        retry_count: int,
    ) -> str:
        if not retrieval.text_evidence or not answer.claims:
            return "refuse"

        all_supported = supported_claim_count == claim_total
        complete_pass = (
            all_supported
            and evidence_score >= self.pass_threshold
            and citation_validity >= 0.80
            and path_validity >= 0.80
            and not unsupported
        )
        if complete_pass:
            return "pass"
        if self.decision_policy == "partial_pass" and supported_claim_count > 0:
            return "partial_pass"
        if (
            retry_count < self.max_retries
            and "premise_not_supported" not in reason_codes
            and (
                evidence_score >= self.retry_threshold
                or bool(unsupported)
                or retrieval_sufficiency < 0.5
            )
        ):
            return "retry"
        return "refuse"

    @staticmethod
    def _invalidate_claim_results(
        claim_results: list[ClaimResult],
        reason_code: str,
    ) -> list[ClaimResult]:
        return [
            result.model_copy(
                update={
                    "status": EvidenceVerifier.UNSUPPORTED,
                    "supported": False,
                    "retained": False,
                    "reason_codes": list(
                        dict.fromkeys([*result.reason_codes, reason_code])
                    ),
                }
            )
            for result in claim_results
        ]

    def _valid_path_ids(self, retrieval: RetrievalResult, graph_repo) -> set[str]:
        if not retrieval.graph_paths or graph_repo is None:
            return set()
        return {
            path.path_id
            for path in retrieval.graph_paths
            if graph_repo.validate_path([triple.model_dump() for triple in path.triples])
        }

    def _valid_path_count(self, retrieval: RetrievalResult, graph_repo) -> int:
        return len(self._valid_path_ids(retrieval, graph_repo))

    def _has_relevant_evidence(
        self,
        refs: list[str],
        evidence_by_id: dict,
        claim: AnswerClaim,
        retrieval: RetrievalResult,
    ) -> bool:
        if not refs:
            return False
        if claim.relation_id:
            return self._relation_id_is_valid(claim, retrieval)
        return any(evidence_by_id[ref].score >= self.min_vector_score for ref in refs)

    @staticmethod
    def _relation_id_is_valid(
        claim: AnswerClaim,
        retrieval: RetrievalResult,
    ) -> bool:
        if not claim.relation_id or not claim.graph_path_ids:
            return False
        referenced_path_ids = set(claim.graph_path_ids)
        return any(
            claim.relation_id == triple.relation_id
            for path in retrieval.graph_paths
            if path.path_id in referenced_path_ids
            for triple in path.triples
        )

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

    @staticmethod
    def _normalize_verbatim_text(value: str) -> str:
        return " ".join(value.split())

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
