from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "research_report_draft.md"
BASELINE_DIR = PROJECT_ROOT / "reports" / "releases" / "v1.0-baseline"


@dataclass(frozen=True)
class TextRule:
    rule_id: str
    description: str
    pattern: str


REQUIRED_RULES = (
    TextRule("R01", "97.5% must be labelled as pass/refuse decision accuracy", r"97\.5%[^。\n]{0,40}pass/refuse 决策准确率"),
    TextRule("R02", "decision accuracy must be separated from answer correctness", r"(?:不等同于回答正确率|不是问答准确率)"),
    TextRule("R03", "user-confirmed review status must remain explicit", r"user_confirmed"),
    TextRule("R04", "confirmed scoring provenance must be disclosed", r"用户确认后的语义复核"),
    TextRule("R05", "TF-IDF representation must be disclosed", r"TF-IDF 稀疏表示"),
    TextRule("R06", "dense embedding must be explicitly disclaimed", r"不是神经稠密 Embedding"),
    TextRule("R07", "the offline generator must be disclosed", r"GroundedAnswerGenerator[^。\n]{0,40}不调用在线 LLM"),
    TextRule("R08", "the final split must be described as run once", r"final[^。\n]{0,30}(?:仅运行一次|只运行一次)"),
    TextRule("R09", "full Microsoft GraphRAG must be disclaimed", r"未实现 Microsoft GraphRAG 的完整"),
    TextRule("R10", "NetworkX must be identified as the experiment backend", r"当前(?:冻结评测和 pilot )?实验(?:均)?使用 NetworkX"),
    TextRule("R11", "Neo4j online benchmark must be disclaimed", r"不声称完成了在线 Neo4j 服务基准测试"),
    TextRule("R12", "1.48 ms must be separated from online LLM latency", r"1\.48 ms[^\n]{0,50}不是在线 LLM 延迟"),
    TextRule(
        "R13",
        "Generator wiring, Planner No-Go, and extension governance must remain explicit",
        r"当前状态：LLM Answer Generator、Verifier 与规则 fallback 已接入默认主链路，Planner No-Go；v1 extension release 已在执行前撤销，v2 合同已冻结但尚无可执行 release",
    ),
    TextRule(
        "R14",
        "the extension holdout must be described as revoked before execution",
        r"一次性 release `extension-qwen3-4b-v1-bdedf7dc` 的原文件保留 `authorized_not_executed`，但不可变撤销记录已将有效状态固定为 `revoked_before_execution`；没有 extension 输出",
    ),
    TextRule(
        "R15",
        "the current LLM workflow and offline fallback must both be disclosed",
        r"当前分支默认使用 `qwen3:4b` 的 `LLMAnswerGenerator`[\s\S]{0,500}自动回退 `GroundedAnswerGenerator`",
    ),
    TextRule(
        "R16",
        "dev results must be separated from independent enhancement evidence",
        r"候选 dev 的结构化输出成功率为 1\.0000[\s\S]{0,250}决策准确率为 0\.6000[\s\S]{0,150}(?:不能证明 LLM 增强有效|只用于开发调试)",
    ),
    TextRule(
        "R17",
        "Prompt v2 synthetic probe must remain an engineering gate",
        r"Prompt v2 合成探针成功为 20/20[\s\S]{0,500}(?:工程结构门槛|不是独立回答质量实验)",
    ),
    TextRule(
        "R18",
        "Prompt v2 strict smoke must remain separated from the Stage 8.3 fix",
        r"Claim coverage 从 0\.3333 提高到 0\.5000[\s\S]{0,220}阶段 8\.2[^。\n]{0,80}`refuse`",
    ),
    TextRule(
        "R19",
        "Stage 8.3 DEV02 smoke must remain a development mechanism check",
        r"阶段 8\.3[\s\S]{0,800}DEV02[\s\S]{0,800}`partial_pass`[\s\S]{0,500}(?:不是完整 dev/pilot 回归|只证明过滤机制)",
    ),
)


FORBIDDEN_RULES = (
    TextRule("F01", "unsupported zero-hallucination guarantee", r"系统不会产生幻觉"),
    TextRule("F02", "positive claim of complete Microsoft GraphRAG implementation", r"(?:本项目|系统)[^。\n]{0,12}完整实现(?:了)?\s*Microsoft GraphRAG"),
    TextRule("F03", "positive claim of complete Microsoft GraphRAG reproduction", r"(?:本项目|系统)[^。\n]{0,12}完整复现(?:了)?\s*Microsoft GraphRAG"),
    TextRule("F04", "97.5% incorrectly labelled as QA accuracy", r"(?:97\.5%[^。\n]{0,20}(?:问答|回答)准确率|(?:问答|回答)准确率[^。\n]{0,20}97\.5%)"),
    TextRule("F05", "citation rate incorrectly treated as faithfulness", r"(?:97\.5%[^。\n]{0,20}证据忠实度|证据忠实度[^。\n]{0,20}97\.5%)"),
    TextRule("F06", "1.48 ms incorrectly labelled as online LLM latency", r"(?:在线[^。\n]{0,20}LLM[^。\n]{0,20}1\.48\s*ms|1\.48\s*ms[^。\n]{0,20}在线[^。\n]{0,20}LLM 延迟为)"),
    TextRule("F07", "preliminary scores incorrectly labelled independent human review", r"(?:独立人工评测|正式人工评测)[^。\n]{0,30}(?:0\.8625|1\.0000)"),
    TextRule(
        "F08",
        "unverified Neo4j benchmark claim",
        r"(?:(?:已完成(?:了)?|已经完成(?:了)?|已进行(?:了)?|已经进行(?:了)?)\s*(?:在线\s*)?Neo4j\s*(?:在线\s*)?(?:服务\s*)?(?:性能|延迟|基准)[^。\n]{0,4}(?:测试|结果)|Neo4j\s*(?:在线\s*)?(?:服务\s*)?(?:性能|延迟|基准)[^。\n]{0,4}(?:测试|结果)[^。\n]{0,8}(?:已完成|已经完成|已提供|已经提供))",
    ),
    TextRule("F09", "stale preliminary scoring status in the current report", r"preliminary_pending_user_confirmation"),
    TextRule("F10", "stale preliminary semantic wording in the current report", r"(?:Codex 辅助初步语义复核|初步语义评分|初步语义复核|初步 Hallucination Rate)"),
    TextRule("F11", "stale extension holdout creation status", r"No-Go 状态下不创建 `extension_holdout`"),
    TextRule(
        "F12",
        "probe readiness incorrectly described as completed Agent integration",
        r"qwen3:4b[^。\n]{0,50}(?:已接入 Agent 主链路|已完成 enhanced 实验|已证明增强有效)",
    ),
    TextRule(
        "F13",
        "Client smoke incorrectly described as completed Generator integration",
        r"(?:统一 (?:LLM )?Client|合成 smoke)[^。\n]{0,60}(?:已接入 Agent 主链路|已完成 LLM Answer Generator|已证明增强有效)",
    ),
    TextRule(
        "F14",
        "dev tuning results incorrectly presented as LLM superiority",
        r"(?:候选 dev|dev 调试)[^。\n]{0,80}(?:证明|表明)[^。\n]{0,30}LLM[^。\n]{0,20}(?:优于|超过)规则",
    ),
    TextRule(
        "F15",
        "unsupported claim that Prompt v2 fixed over-refusal",
        r"Prompt v2[^。\n]{0,30}已(?:经)?(?:解决|消除)(?:了)?过度拒答",
    ),
    TextRule(
        "F16",
        "synthetic probe incorrectly presented as enhancement effectiveness",
        r"20/20[^。\n]{0,40}(?:证明|表明)[^。\n]{0,20}(?:增强有效|优于规则|正式准确率)",
    ),
    TextRule(
        "F17",
        "single DEV02 smoke incorrectly presented as overall effectiveness",
        r"DEV02[^。\n]{0,120}(?:证明|表明)[^。\n]{0,30}(?:总体过度拒答已解决|LLM[^。\n]{0,10}优于规则|正式准确率提升)",
    ),
    TextRule(
        "F18",
        "partial-pass incorrectly equated with a correct answer",
        r"partial_pass(?: 状态)?就是(?:人工)?正确答案",
    ),
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def expected_literals() -> dict[str, str]:
    stats = read_json(BASELINE_DIR / "data_statistics.json")
    comparison = read_json(PROJECT_ROOT / "reports" / "experiments" / "pilot_comparison.json")
    semantic = read_json(PROJECT_ROOT / "reports" / "experiments" / "pilot_human_metrics.json")
    llm_probe = read_json(PROJECT_ROOT / "reports" / "llm_probe_qwen3_4b.json")
    extension_manifest = read_json(
        PROJECT_ROOT / "data" / "evaluation" / "extension_holdout_manifest.json"
    )
    implementation_manifest = read_json(
        PROJECT_ROOT / "data" / "evaluation" / "extension_implementation_manifest.json"
    )
    extension_release = read_json(
        PROJECT_ROOT / "data" / "evaluation" / "extension_holdout_release.json"
    )
    extension_revocation = read_json(
        PROJECT_ROOT
        / "data"
        / "evaluation"
        / "extension_release_revocations"
        / "extension-qwen3-4b-v1-bdedf7dc.json"
    )
    llm_dev = read_json(PROJECT_ROOT / "reports" / "evaluation_llm_generator_dev_candidate.json")
    atomic_probe = read_json(
        PROJECT_ROOT / "reports" / "llm_atomic_claim_prompt_v2_probe.json"
    )
    partial_smoke = read_json(
        PROJECT_ROOT / "reports" / "claim_level_partial_pass_dev02_smoke.json"
    )

    kb = stats["knowledge_base"]
    graph = stats["graph"]
    final = stats["evaluation"]["final_metrics"]
    proposed_auto = next(row for row in comparison["methods"] if row["method"] == "proposed")
    proposed_semantic = semantic["methods"]["proposed"]
    llm_summary = llm_probe["summary"]

    return {
        "S01 knowledge-base scale": (
            f"系统将 {kb['section_count']} 个文档 Section 切分为 {kb['chunk_count']} 个稳定 Chunk"
        ),
        "S02 graph scale": f"{graph['entity_count']} 个实体、{graph['relation_count']} 条 approved 关系",
        "S03 final question count": f"| 问题数 | {final['question_count']} |",
        "S04 final decision accuracy": f"| 决策准确率 | {final['decision_accuracy']:.4f} |",
        "S05 final citation rate": f"| 引用率 | {final['citation_rate']:.4f} |",
        "S06 final keyword coverage": f"| 平均关键词覆盖 | {final['mean_keyword_coverage']:.4f} |",
        "S07 final entity coverage": f"| 平均实体覆盖 | {final['mean_entity_coverage']:.4f} |",
        "S08 final latency": f"| 平均本地工作流耗时 | {final['mean_latency_ms']:.2f} ms |",
        "S09 known final failure": stats["evaluation"]["known_failure_ids"][0],
        "S10 proposed pilot decision accuracy": (
            f"Proposed 的决策准确率和无答案拒答准确率分别为 "
            f"{proposed_auto['decision_accuracy']:.0%} 和 {proposed_auto['refusal_accuracy']:.0%}"
        ),
        "S11 proposed preliminary correctness": (
            f"Proposed 的回答正确性为 {proposed_semantic['answer_correctness']['value']:.4f}"
        ),
        "S12 proposed preliminary faithfulness": (
            f"证据忠实度为 {proposed_semantic['evidence_faithfulness']['value']:.4f}"
        ),
        "S13 confirmed review status": semantic["review_status"],
        "S14 qwen3 structured schema count": (
            f"结构化 Schema 成功为 {llm_summary['total_schema_successes']}/{llm_summary['total_runs']}"
        ),
        "S15 extension question count": f"{extension_manifest['question_count']} 题 `extension_holdout`",
        "S16 extension dataset hash": extension_manifest["dataset_sha256"],
        "S17 LLM dev structured success": (
            f"候选 dev 的结构化输出成功率为 {llm_dev['structured_output_success_rate']:.4f}"
        ),
        "S18 LLM dev fallback rate": f"fallback rate 为 {llm_dev['fallback_rate']:.4f}",
        "S19 LLM dev decision accuracy": (
            f"pass/refuse 决策准确率为 {llm_dev['decision_accuracy']:.4f}"
        ),
        "S20 extension release ID": f"一次性 release `{extension_release['release_id']}`",
        "S21 extension runtime bundle": implementation_manifest["runtime_bundle_sha256"],
        "S22 extension prompt hash": implementation_manifest["prompt_contract"][
            "system_prompt_sha256"
        ],
        "S23 extension trace contract hash": implementation_manifest[
            "trace_contract_sha256"
        ],
        "S24 extension effective status": (
            f"有效状态固定为 `{extension_revocation['status']}`"
        ),
        "S25 atomic Prompt probe": (
            "Prompt v2 合成探针成功为 "
            f"{atomic_probe['summary']['semantic_successes']}/"
            f"{atomic_probe['summary']['total_runs']}"
        ),
        "S26 atomic Prompt hash": (
            f"Prompt v2 SHA-256 为 `{atomic_probe['system_prompt_sha256']}`"
        ),
        "S27 atomic wire Schema hash": (
            f"wire Schema SHA-256 为 `{atomic_probe['wire_schema_sha256']}`"
        ),
        "S28 partial-pass retained and removed Claims": (
            "DEV02 脱敏 smoke 保留 "
            f"{'/'.join(partial_smoke['retained_claim_ids'])}、删除 "
            f"{'/'.join(partial_smoke['removed_claim_ids'])}"
        ),
        "S29 partial-pass warm generation latency": (
            f"warm generation latency 为 {partial_smoke['generation_latency_ms']:.1f} ms"
        ),
        "S30 partial-pass end-to-end latency": (
            f"end-to-end latency 为 {partial_smoke['end_to_end_latency_ms']} ms"
        ),
    }


def validate_report(report_path: Path) -> list[str]:
    if not report_path.is_file():
        return [f"report does not exist: {report_path}"]

    text = report_path.read_text(encoding="utf-8")
    errors: list[str] = []

    for label, literal in expected_literals().items():
        if literal not in text:
            errors.append(f"{label}: missing source-derived text: {literal!r}")

    for rule in REQUIRED_RULES:
        if not re.search(rule.pattern, text, flags=re.IGNORECASE):
            errors.append(f"{rule.rule_id}: missing required disclosure: {rule.description}")

    for rule in FORBIDDEN_RULES:
        match = re.search(rule.pattern, text, flags=re.IGNORECASE)
        if match:
            excerpt = " ".join(match.group(0).split())
            errors.append(f"{rule.rule_id}: forbidden claim ({rule.description}): {excerpt!r}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate high-risk claims in the research report.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Markdown report to validate")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    errors = validate_report(report_path)
    if errors:
        print("ERROR: research report claim validation failed")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        "OK: report claims validated "
        f"source_checks={len(expected_literals())} required_rules={len(REQUIRED_RULES)} "
        f"forbidden_rules={len(FORBIDDEN_RULES)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
