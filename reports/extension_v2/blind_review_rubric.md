# Extension 匿名盲评量表

## 评审边界

本量表用于 `blind_review_codex_preliminary.csv` 与用户后续确认。评审者只看题目、匿名答案和该题显示的官方证据，不读取 `blind_method_key.json`，不根据 A/B/C/D 标签猜测方法身份，也不把自动 `pass`、`partial_pass` 或 `refuse` 当作人工结论。

当前文件中的分数是：

```text
reviewer = Codex-assisted preliminary review
review_status = preliminary_pending_user_confirmation
```

它们是辅助初评，不是独立人工标注。用户应逐行确认或修改后，才允许解盲和汇总。

## 评分字段

### Answer Correctness

| 分数 | 含义 |
| ---: | --- |
| 2 | 完整回答问题的核心要求；对于知识库外、属性不存在或错误前提问题，明确而恰当地拒答或纠正 |
| 1 | 有部分正确事实或部分纠正，但遗漏关键方面、回答不完整或只覆盖问题的一部分 |
| 0 | 事实错误、答非所问、把无证据问题当成已知事实，或对可回答问题无依据拒答 |

### Evidence Faithfulness

只对实质性答案评分；拒答按合同留空。

| 分数 | 含义 |
| ---: | --- |
| 2 | 主要专业陈述都能由该答案展示的官方证据支持，引用与陈述基本对应 |
| 1 | 只有部分陈述被支持，存在引用错位、证据不足、过度推断或主次内容混杂 |
| 0 | 核心陈述没有展示证据支持，或与展示证据冲突 |

### Hallucination

只对实质性答案填写：

- `1`：答案包含展示证据不支持的专业事实性陈述；
- `0`：没有发现这类陈述。

无证据但只输出拒答句不算 hallucination；这类情况通过 Correctness 和 Over-refusal 记录。

### Over-refusal

- `1`：题目本可由展示证据回答，但答案以证据不足为由拒答或没有提供可用回答；
- `0`：没有发生该情况。

无答案题、知识库外问题和不存在属性问题不因为拒答而记为 over-refusal。

### Readability

只对正确或部分正确的实质性答案填写：

| 分数 | 含义 |
| ---: | --- |
| 1 | 几乎无法理解，结构严重混乱 |
| 2 | 可勉强理解，但表达断裂或噪声很多 |
| 3 | 基本清楚，但有明显冗余、重复或组织问题 |
| 4 | 清楚、直接，只有少量冗余或格式问题 |
| 5 | 简洁、连贯、术语准确，适合直接交付给用户 |

拒答、完全错误答案和没有可评价实质内容的答案留空。

## 审核操作

1. 打开 `blind_review_codex_preliminary.md` 阅读每题 A/B/C/D 答案与初评分；原始证据正文以 `blind_review_codex_preliminary.csv` 的 `retrieved_evidence_json` 为准。
2. 如不同意初评，直接修改 `blind_review_codex_preliminary_scores.csv` 对应行的分数或 `review_notes`；不要修改 `review_item_id`、`question_id` 或 `answer_label`。
3. 修改后运行：

```bash
python scripts/build_extension_blind_preliminary.py --overwrite
python scripts/validate_extension_blind_preliminary.py
```

4. 在用户确认全部行之前，不运行 method key 解盲，也不生成按方法的人工指标。

最终确认脚本将在用户审核完成后单独执行，并保留初评文件和用户修改记录。
