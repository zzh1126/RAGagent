from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.workflow import build_default_workflow
from src.schemas import FinalResponse


st.set_page_config(
    page_title="scikit-learn 知识问答 Agent",
    page_icon="SK",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #17202a;
        --muted: #667085;
        --line: #d9dee7;
        --paper: #ffffff;
        --accent: #1864ab;
        --success: #18794e;
        --partial: #a15c00;
        --danger: #b42318;
    }
    .stApp { background: #f5f7fa; color: var(--ink); }
    [data-testid="stSidebar"] { background: #eef2f6; border-right: 1px solid var(--line); }
    [data-testid="stHeader"] { background: transparent; }
    .block-container { max-width: 1220px; padding-top: 2rem; padding-bottom: 4rem; }
    h1, h2, h3 { letter-spacing: 0 !important; color: var(--ink); }
    h1 { font-size: 2rem !important; }
    .agent-kicker { color: var(--accent); font-weight: 700; font-size: .82rem; text-transform: uppercase; }
    .agent-subtitle { color: var(--muted); margin: .2rem 0 1.5rem; }
    .status-pass { color: var(--success); font-weight: 700; }
    .status-partial { color: var(--partial); font-weight: 700; }
    .status-refuse { color: var(--danger); font-weight: 700; }
    div[data-testid="stForm"] { background: var(--paper); border: 1px solid var(--line); border-radius: 6px; padding: 1rem; }
    div[data-testid="stMetric"] { background: var(--paper); border: 1px solid var(--line); border-radius: 6px; padding: .75rem 1rem; }
    div[data-testid="stExpander"] { background: var(--paper); border-color: var(--line); border-radius: 6px; }
    .stButton > button, .stDownloadButton > button { border-radius: 5px; }
    button[kind="primary"], button[kind="primaryFormSubmit"], [data-testid="baseButton-primaryFormSubmit"] { background: var(--accent) !important; border-color: var(--accent) !important; }
    button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover, [data-testid="baseButton-primaryFormSubmit"]:hover { background: #0f4c81 !important; border-color: #0f4c81 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def get_workflow():
    workflow = build_default_workflow(PROJECT_ROOT)
    workflow.prewarm()
    return workflow


@st.cache_data(show_spinner=False)
def load_demo_questions() -> list[dict]:
    path = PROJECT_ROOT / "data" / "evaluation" / "demo_questions.jsonl"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def path_rows(response: FinalResponse) -> list[dict]:
    rows: list[dict] = []
    for path in response.retrieval.graph_paths:
        for triple in path.triples:
            rows.append(
                {
                    "路径": path.path_id,
                    "源实体": triple.source_name,
                    "关系": triple.relation,
                    "目标实体": triple.target_name,
                    "关系 ID": triple.relation_id,
                }
            )
    return rows


def render_evidence(response: FinalResponse) -> None:
    if not response.retrieval.text_evidence:
        st.info("本次没有返回文本证据。")
        return
    for item in response.retrieval.text_evidence:
        heading = " > ".join(item.heading_path)
        st.markdown(f"**[{item.evidence_id}] {heading}**")
        st.caption(f"{item.chunk_id} · {item.source_id} · score {item.score:.4f}")
        st.write(item.display_text)
        st.markdown(f"[打开 scikit-learn 官方文档]({item.url})")
        st.divider()


def render_runtime_status(response: FinalResponse, warmup_status) -> None:
    llm_calls = [
        call
        for call in response.generation_trace
        if call.requested_backend == "ollama"
    ]
    runtime_call = (
        llm_calls[0]
        if llm_calls
        else (response.generation_trace[0] if response.generation_trace else None)
    )
    requested_backend = runtime_call.requested_backend if runtime_call else "-"
    actual_backend = response.answer_payload.generator_backend
    fallback_used = any(call.fallback_used for call in response.generation_trace)
    fallback_reason = next(
        (call.fallback_reason for call in response.generation_trace if call.fallback_reason),
        None,
    )
    attempted_llm_calls = [call for call in llm_calls if call.attempts > 0]
    structured_success = bool(
        attempted_llm_calls
        and all(call.structured_output_success for call in attempted_llm_calls)
    )
    if structured_success:
        structured_label = "success"
    elif attempted_llm_calls:
        structured_label = "failed"
    elif llm_calls:
        structured_label = "not called"
    else:
        structured_label = "N/A"
    model_label = runtime_call.model if runtime_call and runtime_call.model else "Offline rule"

    first_row = st.columns(2)
    first_row[0].metric("Generator", model_label)
    first_row[1].metric("Backend", f"{requested_backend} → {actual_backend}")
    second_row = st.columns(2)
    second_row[0].metric("Fallback", str(fallback_used).lower())
    second_row[1].metric("Structured JSON", structured_label)
    if fallback_reason:
        st.caption(f"Fallback reason: {fallback_reason}")

    warmup_parts = [f"Prewarm: {warmup_status.status}"]
    if warmup_status.latency_ms:
        warmup_parts.append(f"{warmup_status.latency_ms:.1f} ms")
    if warmup_status.error_type:
        warmup_parts.append(warmup_status.error_type)
    warmup_parts.append(f"Cache: {response.cache_status}")
    st.caption(" · ".join(warmup_parts))

    latency = response.latency_trace
    latency_rows = (
        (
            ("Routing latency", latency.routing_latency_ms),
            ("Retrieval latency", latency.retrieval_latency_ms),
        ),
        (
            ("Packing latency", latency.evidence_packing_latency_ms),
            ("LLM latency", latency.llm_generation_latency_ms),
        ),
        (
            ("Verification latency", latency.verification_latency_ms),
            ("Retry latency", latency.retry_latency_ms),
        ),
    )
    for row in latency_rows:
        columns = st.columns(2)
        for column, (label, value) in zip(columns, row, strict=True):
            column.metric(label, f"{value:.1f} ms")


def render_trace(response: FinalResponse, warmup_status) -> None:
    if response.route_trace is not None:
        st.markdown("**Routing**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "intent": response.route_trace.intent,
                        "mode": response.route_trace.mode,
                        "reason": response.route_trace.reason,
                        "latency_ms": response.route_trace.latency_ms,
                    }
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )

    if response.retrieval_trace:
        st.markdown("**Retrieval calls**")
        st.dataframe(
            pd.DataFrame([call.model_dump() for call in response.retrieval_trace]),
            hide_index=True,
            use_container_width=True,
        )

    if response.generation_trace:
        st.markdown("**Generation calls**")
        st.dataframe(
            pd.DataFrame([call.model_dump() for call in response.generation_trace]),
            hide_index=True,
            use_container_width=True,
        )

    if response.verification_trace:
        st.markdown("**Verification calls**")
        st.dataframe(
            pd.DataFrame([call.model_dump() for call in response.verification_trace]),
            hide_index=True,
            use_container_width=True,
        )

    st.markdown("**Latency summary**")
    st.json(response.latency_trace.model_dump())
    st.markdown("**Startup prewarm**")
    st.json(warmup_status.model_dump())


def render_response(response: FinalResponse, engine_name: str, warmup_status) -> None:
    intent_labels = {
        "relation": "关系",
        "definition": "定义",
        "explanation": "解释",
        "comparison": "对比",
        "recommendation": "推荐",
        "multi_hop": "多跳",
        "general": "综合",
    }
    verification = response.verification
    decision_class = {
        "pass": "status-pass",
        "partial_pass": "status-partial",
        "refuse": "status-refuse",
        "retry": "status-partial",
    }[verification.decision]
    st.markdown(
        f'<p class="{decision_class}">Verifier: {verification.decision.upper()}</p>',
        unsafe_allow_html=True,
    )
    metric_columns = st.columns(2)
    metric_columns[0].metric("检索模式", response.retrieval.mode.upper())
    metric_columns[1].metric("问题类型", intent_labels.get(response.retrieval.intent, response.retrieval.intent))
    metric_columns = st.columns(2)
    metric_columns[0].metric("证据分数", f"{verification.evidence_score:.2f}")
    metric_columns[1].metric("Claim 覆盖率", f"{verification.claim_coverage:.2f}")
    metric_columns = st.columns(2)
    metric_columns[0].metric("重试次数", response.retry_count)
    metric_columns[1].metric(
        "端到端耗时",
        f"{response.latency_trace.end_to_end_latency_ms:.1f} ms",
    )

    st.markdown("### 运行状态")
    render_runtime_status(response, warmup_status)

    answer_tab, graph_tab, evidence_tab, verify_tab, trace_tab = st.tabs(
        ["回答", "图路径", "官方证据", "验证详情", "运行轨迹"]
    )
    with answer_tab:
        answer_text = response.answer.split("\n\n官方证据：", 1)[0]
        st.markdown(answer_text)
        if response.retrieval.text_evidence:
            st.caption("引用详情见“官方证据”页签。")
    with graph_tab:
        rows = path_rows(response)
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.info("本次检索未使用图路径。")
    with evidence_tab:
        render_evidence(response)
    with verify_tab:
        details = verification.model_dump()
        details["engine"] = engine_name
        details["linked_entities"] = [entity.model_dump() for entity in response.retrieval.entities]
        st.json(details)
    with trace_tab:
        render_trace(response, warmup_status)

    payload = json.dumps(response.model_dump(), ensure_ascii=False, indent=2)
    st.download_button(
        "下载本次响应 JSON",
        data=payload,
        file_name="qa_response.json",
        mime="application/json",
        use_container_width=False,
    )


workflow = get_workflow()
demo_questions = load_demo_questions()

with st.sidebar:
    st.title("知识问答 Agent")
    st.caption("scikit-learn 官方文档 · 六页冻结知识范围")
    st.divider()
    st.metric("工作流引擎", workflow.engine_name)
    st.metric("图后端", workflow.graph_repo.__class__.__name__.replace("GraphRepository", ""))
    st.metric("Generator", workflow.generator_model or "Offline rule")
    st.metric("预热状态", workflow.warmup_status.status)
    st.metric("正式测试题", 40)
    st.divider()
    demo_labels = [item["question"] for item in demo_questions]
    selected_demo = st.selectbox(
        "演示问题",
        options=[""] + demo_labels,
        format_func=lambda value: "选择预设问题" if not value else value,
    )

st.markdown('<div class="agent-kicker">Knowledge-Graph-Enhanced RAG</div>', unsafe_allow_html=True)
st.title("scikit-learn 知识问答 Agent")
st.markdown(
    '<p class="agent-subtitle">基于预定义知识图谱与官方文档证据的混合检索问答</p>',
    unsafe_allow_html=True,
)

with st.form("qa_form", clear_on_submit=False):
    query = st.text_area(
        "问题",
        value=selected_demo,
        height=96,
        placeholder="输入关于线性模型、SVM、决策树、集成学习、聚类或评估指标的问题",
    )
    submitted = st.form_submit_button("运行问答", type="primary", use_container_width=True)

if submitted:
    normalized_query = query.strip()
    if not normalized_query:
        st.warning("请输入问题。")
    else:
        with st.spinner("正在检索并校验证据..."):
            st.session_state["last_response"] = workflow.invoke(normalized_query)

if "last_response" in st.session_state:
    st.divider()
    render_response(
        st.session_state["last_response"],
        workflow.engine_name,
        workflow.warmup_status,
    )
