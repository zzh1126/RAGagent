# 报告图表素材

这些 PNG 由 `scripts/generate_report_figures.py` 从已保存的 pilot 实验 JSON 生成，不会重新运行问答工作流。

| 文件 | 内容 | 解释边界 |
| --- | --- | --- |
| `architecture.png` | LangGraph 状态流和检索分支 | 根据当前实现绘制的静态架构图 |
| `pilot_automatic_metrics.png` | 自动决策、Recall@5、拒答和路径指标 | Recall@5 仅适用于保守 gold Chunk 子集 |
| `pilot_semantic_confirmed.png` | Answer Correctness、Evidence Faithfulness | 用户确认后的语义复核；不是独立双人标注 |
| `pilot_latency.png` | 四种 pilot 配置本地耗时 | 离线热路径，不是在线 LLM 延迟 |
| `pilot_category_decision_accuracy.png` | 各题型自动决策准确率 | No-answer 类别只有 4 题 |

`figure_manifest.json` 保存输入文件 SHA-256 和每个 PNG 的 SHA-256。生成或检查命令：

```bash
python scripts/generate_report_figures.py
python scripts/generate_report_figures.py --check
```

语义图表显示用户确认状态。评分初稿由 Codex 辅助生成，随后由用户确认；图表不将其外推为独立双人标注。
