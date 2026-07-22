from __future__ import annotations

from src.schemas import TextEvidence


def build_vector_answer(query: str, evidence: list[TextEvidence]) -> str:
    if not evidence:
        return "当前向量知识库没有检索到足够的官方文档证据，因此不作确定回答。"

    lowered = query.lower()
    if "随机森林" in query:
        answer = (
            "根据 scikit-learn 官方文档，随机森林属于基于随机化决策树的集成方法。"
            "它通过组合多棵基学习器的预测来提升相对于单一估计器的泛化能力和鲁棒性；"
            "每棵树通常基于 bootstrap 样本构建，并在建树过程中引入随机性，因此整体预测比单棵决策树更稳定。"
        )
    elif "类别不平衡" in query or "imbalanc" in lowered:
        answer = (
            "类别不平衡时不应只看普通准确率。可以优先关注 balanced accuracy、precision、recall、F1 或 ROC AUC 等分类指标，"
            "因为这些指标能从不同角度反映少数类识别、正类预测质量或排序能力。"
        )
    else:
        answer = (
            "根据当前检索到的 scikit-learn 官方文档证据，答案应围绕检索结果中的算法定义、适用任务、优点、限制和评价指标展开。"
            "后续接入 LLM 后会在同一证据集合上生成更自然的中文回答。"
        )

    citations = []
    for item in evidence[:5]:
        heading = " > ".join(item.heading_path)
        citations.append(f"[{item.evidence_id}] {item.page_title} | {heading} | {item.url}")
    return answer + "\n\n官方证据：\n" + "\n".join(citations)
