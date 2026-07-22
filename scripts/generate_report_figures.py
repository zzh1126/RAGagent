from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "figures"
COMPARISON_PATH = PROJECT_ROOT / "reports" / "experiments" / "pilot_comparison.json"
SEMANTIC_PATH = PROJECT_ROOT / "reports" / "experiments" / "pilot_human_metrics.json"
CONFIG_PATH = PROJECT_ROOT / "config" / "experiments.yaml"
MANIFEST_NAME = "figure_manifest.json"

METHOD_ORDER = ["vector_rag", "graph_only", "proposed", "no_verifier"]
METHOD_LABELS = {
    "vector_rag": "Vector RAG",
    "graph_only": "Graph Only",
    "proposed": "Proposed",
    "no_verifier": "No Verifier",
}
METHOD_COLORS = {
    "vector_rag": "#2F6690",
    "graph_only": "#3A7D44",
    "proposed": "#D1495B",
    "no_verifier": "#EDAE49",
}
CATEGORY_ORDER = [
    "single_hop",
    "multi_hop",
    "definition",
    "comparison",
    "principle_pros_cons",
    "metric_selection",
    "no_answer",
]
CATEGORY_LABELS = {
    "single_hop": "Single-hop",
    "multi_hop": "Multi-hop",
    "definition": "Definition",
    "comparison": "Comparison",
    "principle_pros_cons": "Pros / cons",
    "metric_selection": "Metric selection",
    "no_answer": "No-answer",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_inputs() -> tuple[dict, dict]:
    comparison = json.loads(COMPARISON_PATH.read_text(encoding="utf-8"))
    semantic = json.loads(SEMANTIC_PATH.read_text(encoding="utf-8"))
    if comparison.get("split") != "pilot" or semantic.get("split") != "pilot":
        raise ValueError("figure inputs must both describe the pilot split")
    if semantic.get("review_status") != "user_confirmed":
        raise ValueError("semantic figure requires user_confirmed status")
    methods = {row["method"] for row in comparison.get("methods", [])}
    if methods != set(METHOD_ORDER):
        raise ValueError(f"unexpected method set: {sorted(methods)}")
    return comparison, semantic


def configure_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#D9E2EC", linewidth=0.8, alpha=0.8)
    ax.set_axisbelow(True)


def save_figure(fig, output_path: Path) -> None:
    fig.savefig(
        output_path,
        dpi=180,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Software": "RAGagent report figure generator"},
    )
    plt.close(fig)


def method_rows(comparison: dict) -> dict[str, dict]:
    return {row["method"]: row for row in comparison["methods"]}


def plot_automatic_metrics(comparison: dict, output_dir: Path) -> None:
    rows = method_rows(comparison)
    metrics = [
        ("decision_accuracy", "Decision accuracy"),
        ("retrieval_recall_at_5", "Recall@5"),
        ("refusal_accuracy", "Refusal accuracy"),
        ("path_validity", "Path validity"),
    ]
    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    x = list(range(len(metrics)))
    width = 0.18
    offsets = [-1.5, -0.5, 0.5, 1.5]
    for method, offset in zip(METHOD_ORDER, offsets):
        values = [rows[method].get(key) for key, _ in metrics]
        plotted = [value if value is not None else 0 for value in values]
        bars = ax.bar(
            [item + offset * width for item in x],
            plotted,
            width=width,
            label=METHOD_LABELS[method],
            color=METHOD_COLORS[method],
        )
        for bar, value in zip(bars, values):
            if value is None:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    0.035,
                    "n/a",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    rotation=90,
                    color="#52606D",
                )
            else:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    value + 0.025,
                    f"{value:.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color="#243B53",
                )
    ax.set_ylim(0, 1.18)
    ax.set_xticks(x, [label for _, label in metrics])
    ax.set_ylabel("Score")
    ax.set_title("Pilot automatic retrieval and decision metrics", loc="left", weight="bold")
    ax.text(
        0,
        1.08,
        "All metrics are automatic; Recall@5 uses the conservative graph-derived gold subset.",
        transform=ax.transAxes,
        fontsize=9,
        color="#52606D",
    )
    ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.13))
    configure_axes(ax)
    save_figure(fig, output_dir / "pilot_automatic_metrics.png")


def plot_semantic_metrics(semantic: dict, output_dir: Path) -> None:
    rows = semantic["methods"]
    metrics = [
        ("answer_correctness", "Answer correctness"),
        ("evidence_faithfulness", "Evidence faithfulness"),
    ]
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    x = list(range(len(METHOD_ORDER)))
    width = 0.34
    for index, (key, label) in enumerate(metrics):
        values = [rows[method][key]["value"] for method in METHOD_ORDER]
        bars = ax.bar(
            [item + (index - 0.5) * width for item in x],
            values,
            width=width,
            label=label,
            color=["#5B8FF9", "#61DDAA"][index],
        )
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.025,
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=8,
                color="#243B53",
            )
    ax.set_ylim(0, 1.18)
    ax.set_xticks(x, [METHOD_LABELS[method] for method in METHOD_ORDER])
    ax.set_ylabel("Normalized score")
    ax.set_title("Pilot user-confirmed semantic review results", loc="left", weight="bold")
    ax.text(
        0,
        1.08,
        "Scores were generated with Codex assistance and confirmed by the user; not independent multi-rater annotation.",
        transform=ax.transAxes,
        fontsize=9,
        color="#9C2C2C",
    )
    ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.13))
    configure_axes(ax)
    save_figure(fig, output_dir / "pilot_semantic_confirmed.png")


def plot_latency(comparison: dict, output_dir: Path) -> None:
    rows = method_rows(comparison)
    values = [rows[method]["mean_latency_ms"] for method in METHOD_ORDER]
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    bars = ax.bar(
        [METHOD_LABELS[method] for method in METHOD_ORDER],
        values,
        color=[METHOD_COLORS[method] for method in METHOD_ORDER],
        width=0.62,
    )
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + max(values) * 0.04,
            f"{value:.3f} ms",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#243B53",
        )
    ax.set_ylabel("Mean local workflow latency (ms)")
    ax.set_title("Pilot local workflow latency", loc="left", weight="bold")
    ax.text(
        0,
        1.08,
        "Hot local offline path; not an online LLM latency measurement.",
        transform=ax.transAxes,
        fontsize=9,
        color="#52606D",
    )
    configure_axes(ax)
    save_figure(fig, output_dir / "pilot_latency.png")


def plot_category_heatmap(comparison: dict, output_dir: Path) -> None:
    category_metrics = comparison["category_metrics"]
    matrix = [
        [category_metrics[method][category]["decision_accuracy"] for category in CATEGORY_ORDER]
        for method in METHOD_ORDER
    ]
    fig, ax = plt.subplots(figsize=(11.5, 4.9))
    image = ax.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(CATEGORY_ORDER)), [CATEGORY_LABELS[item] for item in CATEGORY_ORDER], rotation=25, ha="right")
    ax.set_yticks(range(len(METHOD_ORDER)), [METHOD_LABELS[item] for item in METHOD_ORDER])
    ax.set_title("Pilot decision accuracy by question category", loc="left", weight="bold")
    ax.text(
        0,
        1.12,
        "Automatic pass/refuse decision metric; no-answer contains four questions.",
        transform=ax.transAxes,
        fontsize=9,
        color="#52606D",
    )
    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            color = "white" if value >= 0.55 else "#102A43"
            ax.text(column_index, row_index, f"{value:.2f}", ha="center", va="center", color=color, fontsize=9)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.03)
    colorbar.set_label("Decision accuracy")
    save_figure(fig, output_dir / "pilot_category_decision_accuracy.png")


def draw_box(ax, x: float, y: float, width: float, height: float, label: str, color: str) -> None:
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.2,
        edgecolor="#486581",
        facecolor=color,
    )
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height / 2, label, ha="center", va="center", fontsize=9, color="#102A43", wrap=True)


def arrow(ax, start: tuple[float, float], end: tuple[float, float], label: str | None = None, curve: float = 0.0) -> None:
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=14,
        linewidth=1.2,
        color="#627D98",
        connectionstyle=f"arc3,rad={curve}",
    )
    ax.add_patch(patch)
    if label:
        midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        ax.text(midpoint[0], midpoint[1] + 0.025, label, ha="center", va="bottom", fontsize=8, color="#52606D")


def plot_architecture(output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(14, 6.4))
    ax.set_xlim(0, 1.10)
    ax.set_ylim(0, 1)
    ax.axis("off")
    draw_box(ax, 0.02, 0.43, 0.10, 0.14, "User\nquery", "#D9EAF7")
    draw_box(ax, 0.17, 0.43, 0.13, 0.14, "Intent +\nrouter", "#D9EAD3")
    draw_box(ax, 0.37, 0.67, 0.14, 0.13, "Vector\nretriever", "#E8F1F8")
    draw_box(ax, 0.37, 0.435, 0.14, 0.13, "Graph\nretriever", "#E5F4E3")
    draw_box(ax, 0.37, 0.20, 0.14, 0.13, "Hybrid\nretriever", "#FCE8D5")
    draw_box(ax, 0.58, 0.43, 0.14, 0.14, "Evidence\nfusion", "#FFF2CC")
    draw_box(ax, 0.78, 0.43, 0.14, 0.14, "Offline rule\ngenerator", "#F4CCCC")
    draw_box(ax, 0.78, 0.12, 0.14, 0.14, "Evidence\nVerifier", "#EADCF8")
    draw_box(ax, 0.97, 0.60, 0.09, 0.12, "Pass", "#D9EAD3")
    draw_box(ax, 0.97, 0.29, 0.09, 0.12, "Refuse", "#F4CCCC")
    arrow(ax, (0.12, 0.50), (0.17, 0.50))
    arrow(ax, (0.30, 0.50), (0.37, 0.735), "route")
    arrow(ax, (0.30, 0.50), (0.37, 0.50))
    arrow(ax, (0.30, 0.50), (0.37, 0.265), "route")
    arrow(ax, (0.51, 0.735), (0.58, 0.50))
    arrow(ax, (0.51, 0.50), (0.58, 0.50))
    arrow(ax, (0.51, 0.265), (0.58, 0.50))
    arrow(ax, (0.72, 0.50), (0.78, 0.50))
    arrow(ax, (0.85, 0.43), (0.85, 0.26))
    arrow(ax, (0.92, 0.19), (0.97, 0.35), "refuse")
    arrow(ax, (0.92, 0.50), (0.97, 0.66), "pass")
    arrow(ax, (0.85, 0.12), (0.44, 0.20), "retry: expanded hybrid", curve=0.18)
    ax.text(0.5, 0.93, "Lightweight hybrid GraphRAG workflow", ha="center", va="center", fontsize=14, weight="bold", color="#102A43")
    ax.text(0.5, 0.875, "Static architecture diagram generated from the implemented LangGraph state flow", ha="center", va="center", fontsize=9, color="#52606D")
    save_figure(fig, output_dir / "architecture.png")


def figure_purposes() -> dict[str, str]:
    return {
        "architecture.png": "Implemented route, retrieval, generation, verification, retry and terminal states.",
        "pilot_automatic_metrics.png": "Automatic pilot retrieval and decision metrics.",
        "pilot_semantic_confirmed.png": "User-confirmed semantic scores; generated with Codex assistance and confirmed by the user.",
        "pilot_latency.png": "Mean local offline workflow latency for the four pilot methods.",
        "pilot_category_decision_accuracy.png": "Automatic decision accuracy by pilot question category.",
    }


def build_manifest(output_dir: Path, comparison: dict, semantic: dict) -> dict:
    source_paths = [COMPARISON_PATH, SEMANTIC_PATH, CONFIG_PATH]
    figures = {}
    for name, purpose in figure_purposes().items():
        path = output_dir / name
        with Image.open(path) as image:
            dimensions = list(image.size)
        figures[name] = {
            "sha256": sha256(path),
            "dimensions_px": dimensions,
            "purpose": purpose,
        }
    return {
        "schema_version": "1.0",
        "split": comparison["split"],
        "semantic_review_status": semantic["review_status"],
        "sources": {
            str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): sha256(path)
            for path in source_paths
        },
        "figures": figures,
    }


def generate(output_dir: Path) -> None:
    comparison, semantic = load_inputs()
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_automatic_metrics(comparison, output_dir)
    plot_semantic_metrics(semantic, output_dir)
    plot_latency(comparison, output_dir)
    plot_category_heatmap(comparison, output_dir)
    plot_architecture(output_dir)
    manifest = build_manifest(output_dir, comparison, semantic)
    (output_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"OK: generated {len(manifest['figures'])} figures in {output_dir}")


def check(output_dir: Path) -> None:
    manifest_path = output_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing figure manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    comparison, semantic = load_inputs()
    expected_sources = {
        str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): sha256(path)
        for path in (COMPARISON_PATH, SEMANTIC_PATH, CONFIG_PATH)
    }
    if manifest.get("sources") != expected_sources:
        raise ValueError("figure source hashes are stale")
    if manifest.get("semantic_review_status") != semantic["review_status"]:
        raise ValueError("figure semantic-review status is stale")
    for name in figure_purposes():
        path = output_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"missing figure: {path}")
        if manifest["figures"][name]["sha256"] != sha256(path):
            raise ValueError(f"figure hash mismatch: {name}")
    print(f"OK: figure manifest and {len(figure_purposes())} figures are current")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and validate static report figures.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--check", action="store_true", help="Validate the existing manifest and figure hashes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    try:
        if args.check:
            check(output_dir)
        else:
            generate(output_dir)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
