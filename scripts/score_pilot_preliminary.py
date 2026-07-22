from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.config import load_experiment_suite
from src.evaluation.schemas import ExperimentRunReport


REVIEWER = "Codex-assisted preliminary review"
REVIEW_STATUS = "preliminary_pending_user_confirmation"

BASE_FIELDS = [
    "question_id",
    "method",
    "question",
    "category",
    "expected_decision",
    "actual_decision",
    "correctness_score",
    "faithfulness_score",
    "hallucination",
    "over_refusal",
    "notes",
    "reviewer",
]

ALIASES = {
    "集成学习": ("集成学习", "集成方法"),
    "过拟合风险": ("过拟合风险", "过拟合"),
    "聚类方法": ("聚类方法", "聚类算法"),
    "支持向量": ("支持向量", "支持向量机"),
}

CASE_ORDER = [
    "F-NA-01",
    "F-NA-02",
    "F-NA-03",
    "F-NA-04",
    "F-SH-04",
    "F-MH-01",
    "F-MH-03",
    "F-DF-05",
    "F-MS-02",
]

CASE_ANALYSIS = {
    "F-NA-01": {
        "stage": "verification/finalization",
        "cause": "答案生成器已输出无证据拒答句，但关闭 Verifier 后状态仍被标记为 pass，决策标签与文本语义不一致。",
        "improvement": "为 AnswerPayload 增加显式 refusal_intent，并让实验统计同时报告内容级拒答与验证器决策。",
    },
    "F-NA-02": {
        "stage": "entity linking/text retrieval/verification",
        "cause": "XGBoost 只在参考文献片段中出现，稀疏检索返回了相关名称但没有缺失值处理证据；Verifier 能识别限定条件未覆盖。",
        "improvement": "增加实体范围门控和属性级证据检查，区分正文主题实体与参考文献提及。",
    },
    "F-NA-03": {
        "stage": "query alignment/verification",
        "cause": "随机森林实体存在，但知识库没有学习率属性；无验证流程仍返回随机森林定义或普通关系。",
        "improvement": "增加属性白名单与不存在属性检测，在生成前验证实体和询问属性是否共同得到证据支持。",
    },
    "F-NA-04": {
        "stage": "premise validation/verification",
        "cause": "检索能找到 KMeans 的聚类关系，但无验证流程只陈述聚类事实，没有明确否定监督分类这一错误前提。",
        "improvement": "对“是否属于/是否解决”问题增加图谱前提校验，并生成明确的否定与纠正答案。",
    },
    "F-SH-04": {
        "stage": "entity linking/graph retrieval",
        "cause": "关系查询没有锁定 Ridge--USES--正则化，而是扩展到多个线性模型的 SOLVES--回归关系。",
        "improvement": "使用问题中的算法实体和 USES 关系类型联合约束邻居检索，避免泛化到同族算法。",
    },
    "F-MH-01": {
        "stage": "multi-hop retrieval/fusion",
        "cause": "系统优先返回随机森林直属的集成学习关系，没有完成随机森林--USES--决策树--BELONGS_TO--树模型路径。",
        "improvement": "多跳题按显式中间实体拆分目标，并合并每个目标的最短路径；报告中同时说明随机森林直属方法族的本体歧义。",
    },
    "F-MH-03": {
        "stage": "multi-hop retrieval/fusion",
        "cause": "仅返回支持向量分类需要特征缩放，未继续连接特征缩放与高维问题。",
        "improvement": "要求多跳检索覆盖全部已链接目标实体，并在缺少任一目标路径时降低完整性分数。",
    },
    "F-DF-05": {
        "stage": "entity linking/generation",
        "cause": "定义题把通用分类任务排在支持向量分类算法之前，生成了分类定义而非 SVC 定义。",
        "improvement": "定义题优先选择问题中精确命中的 Algorithm 实体，再以任务实体作为补充上下文。",
    },
    "F-MS-02": {
        "stage": "routing/graph retrieval",
        "cause": "指标选择题返回了可解决回归的算法列表，没有沿回归任务的 EVALUATED_BY 入边找到均方误差和 R2。",
        "improvement": "指标选择路由固定优先查询 Task--EVALUATED_BY--Metric，并支持从任务节点聚合多个指标。",
    },
}


def contains_keyword(answer: str, keyword: str) -> bool:
    lowered = answer.lower()
    candidates = ALIASES.get(keyword, (keyword,))
    return any(candidate.lower() in lowered for candidate in candidates)


def keyword_coverage(answer: str, expected_keywords: list[str]) -> tuple[int, int]:
    hits = sum(contains_keyword(answer, keyword) for keyword in expected_keywords)
    return hits, len(expected_keywords)


def is_refusal_text(answer: str) -> bool:
    markers = ("证据不足", "没有检索到足以支持", "无法对该问题作出可靠回答")
    return any(marker in answer for marker in markers)


def score_correctness(item: dict, result, coverage: tuple[int, int]) -> tuple[int, str]:
    expected = item["expected_behavior"]
    answer = result.answer
    if expected == "refuse":
        if is_refusal_text(answer):
            return 2, "文本明确拒答，内容层面正确；需与 actual_decision 分开记录。"
        if item["question_id"] == "F-NA-04" and "聚类" in answer:
            return 1, "回答给出 KMeans 属于聚类的纠正性信息，但未明确否定监督分类前提。"
        return 0, "未拒答且未直接处理知识库外、属性缺失或错误前提问题。"

    hits, total = coverage
    if result.actual_decision == "refuse":
        return 0, "可回答问题被拒答，属于过度拒答。"
    if total == 0:
        return 1, "题目缺少关键词标注，保留人工判断。"
    if hits == total:
        return 2, f"覆盖 gold 关键点 {hits}/{total}。"
    if hits > 0:
        return 1, f"仅覆盖部分 gold 关键点 {hits}/{total}。"
    return 0, "未覆盖 gold 关键点，回答与问题目标不匹配。"


def score_faithfulness(item: dict, result) -> tuple[int, str]:
    has_evidence = result.citation_present
    if result.actual_decision == "refuse":
        if is_refusal_text(result.answer):
            return 2, "拒答文本没有引入新的专业事实。"
        return 1, "拒答方向保守，但文本依据需要人工复核。"
    if not has_evidence:
        return 0, "回答没有绑定文本证据。"
    if item["expected_behavior"] == "refuse":
        return 1, "引用存在但回答没有满足无答案/错误前提的拒答要求，证据与问题目标不完全匹配。"
    if result.graph_path_ids or result.citation_validity >= 0.8:
        return 2, "关键陈述绑定图路径或有效引用。"
    return 1, "有引用，但缺少足够结构证据，需人工核对引用与结论的一致性。"


def score_row(item: dict, report: ExperimentRunReport, result) -> dict[str, str]:
    hits, total = keyword_coverage(result.answer, item["expected_keywords"])
    correctness, correctness_note = score_correctness(item, result, (hits, total))
    faithfulness, faithfulness_note = score_faithfulness(item, result)
    hallucination = int(
        not result.citation_present
        and not is_refusal_text(result.answer)
        and result.actual_decision == "pass"
    )
    over_refusal = int(
        item["expected_behavior"] == "answer" and result.actual_decision == "refuse"
    )
    notes = (
        f"keyword_coverage={hits}/{total}; evidence_score={result.evidence_score:.4f}; "
        f"citation_present={result.citation_present}. "
        f"Correctness: {correctness_note} Faithfulness: {faithfulness_note}"
    )
    return {
        "question_id": result.question_id,
        "method": report.experiment_id,
        "question": result.question,
        "category": result.category,
        "expected_decision": result.expected_decision,
        "actual_decision": result.actual_decision,
        "correctness_score": str(correctness),
        "faithfulness_score": str(faithfulness),
        "hallucination": str(hallucination),
        "over_refusal": str(over_refusal),
        "notes": notes,
        "reviewer": REVIEWER,
        "review_status": REVIEW_STATUS,
    }


def metric(numerator: float, denominator: float) -> dict:
    if denominator <= 0:
        return {"value": None, "numerator": numerator, "denominator": denominator}
    return {
        "value": round(numerator / denominator, 4),
        "numerator": numerator,
        "denominator": denominator,
    }


def build_metrics(rows: list[dict[str, str]]) -> dict:
    total = len(rows)
    answerable = [row for row in rows if row["expected_decision"] == "pass"]
    return {
        "answer_correctness": metric(
            sum(int(row["correctness_score"]) for row in rows),
            2 * total,
        ),
        "evidence_faithfulness": metric(
            sum(int(row["faithfulness_score"]) for row in rows),
            2 * total,
        ),
        "hallucination_rate": metric(
            sum(int(row["hallucination"]) for row in rows),
            total,
        ),
        "over_refusal_rate": metric(
            sum(int(row["over_refusal"]) for row in rows),
            len(answerable),
        ),
        "scoring_status": REVIEW_STATUS,
        "reviewer": REVIEWER,
    }


def build_error_analysis(rows_by_method: dict[str, list[dict[str, str]]], questions: dict[str, dict]) -> str:
    lines = [
        "# Pilot Error Analysis Draft",
        "",
        "This is an agent-assisted preliminary draft. It is not a claim of independent human annotation.",
        "The final report should retain the raw answers and have a reviewer confirm or revise each score.",
        "",
        "| Case | Question ID | Category | Methods / observed issue | Stage and root cause | Proposed improvement |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for index, question_id in enumerate(CASE_ORDER, start=1):
        item = questions.get(question_id, {})
        observations = []
        for method, rows in rows_by_method.items():
            row = next((row for row in rows if row["question_id"] == question_id), None)
            if row is None:
                continue
            score = row["correctness_score"]
            if score != "2" or question_id.startswith("F-NA"):
                observations.append(f"{method}: correctness={score}, decision={row['actual_decision']}")
        if not observations:
            continue
        analysis = CASE_ANALYSIS[question_id]
        lines.append(
            f"| E{index:02d} | `{question_id}` | {item.get('category', '')} | "
            f"{'<br>'.join(observations)} | **{analysis['stage']}**<br>{analysis['cause']} | "
            f"{analysis['improvement']} |"
        )
    lines.extend(
        [
            "",
            "## Required Follow-up",
            "",
            "1. Confirm correctness and faithfulness scores against the full answer and cited source chunks.",
            "2. Treat irrelevant but supported text as an answer-relevance failure unless it also introduces unsupported professional facts.",
            "3. Keep these improvements as future-work analysis; do not change or rerun the frozen final result.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Score pilot reports with an auditable preliminary rubric")
    parser.add_argument("--split", choices=["dev", "pilot"], default="pilot")
    args = parser.parse_args()
    root = PROJECT_ROOT
    suite = load_experiment_suite(root / "config" / "experiments.yaml")
    questions = {
        item["question_id"]: item
        for line in (root / "data" / "evaluation" / f"{args.split}_questions.jsonl").read_text(
            encoding="utf-8-sig"
        ).splitlines()
        if line.strip()
        for item in [json.loads(line)]
    }
    all_rows: list[dict[str, str]] = []
    rows_by_method: dict[str, list[dict[str, str]]] = {}
    metric_summary: dict[str, dict] = {}
    for experiment_id, definition in suite.experiments.items():
        if not definition.enabled:
            continue
        path = root / suite.protocol.output_dir / f"{experiment_id}_{args.split}.json"
        report = ExperimentRunReport.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
        rows = [score_row(questions[result.question_id], report, result) for result in report.results]
        rows_by_method[experiment_id] = rows
        all_rows.extend(rows)
        metric_summary[experiment_id] = build_metrics(rows)

    output_csv = root / "reports" / f"human_scoring_{args.split}_preliminary.csv"
    output_json = root / "reports" / "experiments" / f"{args.split}_human_metrics.json"
    output_md = root / "reports" / "experiments" / f"{args.split}_error_analysis_draft.md"
    outputs = (output_csv, output_json, output_md)
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise SystemExit("Refusing to overwrite preliminary scoring outputs: " + ", ".join(existing))

    fields = BASE_FIELDS + ["review_status"]
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_rows)

    output_json.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "split": args.split,
                "reviewer": REVIEWER,
                "review_status": REVIEW_STATUS,
                "methods": metric_summary,
                "notes": [
                    "Scores are an agent-assisted preliminary semantic review.",
                    "A human reviewer must confirm or revise them before final reporting.",
                    "The frozen final split was not used.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output_md.write_text(build_error_analysis(rows_by_method, questions), encoding="utf-8")
    print(f"OK: preliminary scoring rows={len(all_rows)}")
    print(f"OK: scoring_csv={output_csv}")
    print(f"OK: metrics_json={output_json}")
    print(f"OK: error_analysis_draft={output_md}")


if __name__ == "__main__":
    main()
