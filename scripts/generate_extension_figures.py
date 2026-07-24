from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = (
    PROJECT_ROOT / "reports" / "extension_v2" / "combined_metrics_user_confirmed.json"
)
REVIEWS_PATH = (
    PROJECT_ROOT
    / "reports"
    / "extension_v2"
    / "blind_review_unblinded_user_confirmed.csv"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "figures" / "extension_v2"
MANIFEST_NAME = "figure_manifest.json"

METHOD_ORDER = [
    "rule_baseline",
    "llm_strict_v2",
    "llm_no_verifier_v2",
    "llm_partial_pass_v2",
]
METHOD_LABELS = {
    "rule_baseline": "Rule Baseline",
    "llm_strict_v2": "LLM Strict v2",
    "llm_no_verifier_v2": "LLM No Verifier v2",
    "llm_partial_pass_v2": "LLM Partial-pass v2",
}
METHOD_COLORS = {
    "rule_baseline": "#2F6690",
    "llm_strict_v2": "#7B8794",
    "llm_no_verifier_v2": "#D1495B",
    "llm_partial_pass_v2": "#3A7D44",
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


def _metric_value(method: dict, section: str, name: str) -> float:
    metric = method[section][name]
    if metric.get("status", "computed") != "computed" or metric.get("value") is None:
        raise ValueError(f"metric is not computed: {section}.{name}")
    return float(metric["value"])


def _optional_int(row: dict[str, str], field: str) -> int | None:
    raw = row[field].strip()
    return None if raw == "" else int(raw)


def _assert_close(actual: float, expected: float, label: str) -> None:
    if abs(actual - expected) > 5e-5:
        raise ValueError(f"{label} mismatch: CSV={actual:.6f}, metrics={expected:.6f}")


def _validate_method_aggregates(metrics: dict, rows: list[dict[str, str]]) -> None:
    for method_id in METHOD_ORDER:
        method_rows = [row for row in rows if row["method_id"] == method_id]
        human = metrics["methods"][method_id]["human"]

        correctness = [int(row["answer_correctness"]) for row in method_rows]
        _assert_close(
            sum(correctness) / (2 * len(correctness)),
            float(human["answer_correctness"]["value"]),
            f"{method_id} answer_correctness",
        )

        faithfulness = [
            score
            for row in method_rows
            if (score := _optional_int(row, "evidence_faithfulness")) is not None
        ]
        _assert_close(
            sum(faithfulness) / (2 * len(faithfulness)),
            float(human["evidence_faithfulness"]["value"]),
            f"{method_id} evidence_faithfulness",
        )

        hallucinations = [
            score
            for row in method_rows
            if (score := _optional_int(row, "hallucination")) is not None
        ]
        _assert_close(
            sum(hallucinations) / len(hallucinations),
            float(human["hallucination_rate"]["value"]),
            f"{method_id} hallucination_rate",
        )

        answerable_rows = [
            row for row in method_rows if row["expected_behavior"] == "answer"
        ]
        over_refusals = [int(row["over_refusal"]) for row in answerable_rows]
        _assert_close(
            sum(over_refusals) / len(over_refusals),
            float(human["over_refusal_rate"]["value"]),
            f"{method_id} over_refusal_rate",
        )

        readability = [
            score
            for row in method_rows
            if (score := _optional_int(row, "readability")) is not None
        ]
        _assert_close(
            sum(readability) / len(readability),
            float(human["readability"]["value"]),
            f"{method_id} readability",
        )


def load_inputs() -> tuple[dict, list[dict[str, str]]]:
    if not METRICS_PATH.is_file() or not REVIEWS_PATH.is_file():
        raise FileNotFoundError("user-confirmed extension inputs are missing")

    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    if metrics.get("artifact") != "extension_combined_metrics_user_confirmed":
        raise ValueError("unexpected extension metrics artifact")
    if metrics.get("review_status") != "user_confirmed":
        raise ValueError("extension metrics are not user_confirmed")
    if metrics.get("method_order") != METHOD_ORDER:
        raise ValueError("extension method order differs from the frozen comparison")
    if set(metrics.get("methods", {})) != set(METHOD_ORDER):
        raise ValueError("extension metrics do not contain the four frozen methods")

    with REVIEWS_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required_fields = {
        "review_item_id",
        "question_id",
        "category",
        "expected_behavior",
        "method_id",
        "answer_correctness",
        "evidence_faithfulness",
        "hallucination",
        "over_refusal",
        "readability",
        "review_notes",
        "review_status",
    }
    if not rows or not required_fields.issubset(rows[0]):
        raise ValueError("confirmed review CSV has an unexpected schema")
    if len(rows) != 92 or len({row["review_item_id"] for row in rows}) != 92:
        raise ValueError("confirmed review CSV must contain 92 unique rows")
    if any(row["review_status"] != "user_confirmed" for row in rows):
        raise ValueError("all extension review rows must be user_confirmed")

    by_question: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["method_id"] not in METHOD_ORDER:
            raise ValueError(f"unexpected review method: {row['method_id']}")
        if row["category"] not in CATEGORY_ORDER:
            raise ValueError(f"unexpected review category: {row['category']}")
        if row["expected_behavior"] not in {"answer", "refuse"}:
            raise ValueError("unexpected expected_behavior in confirmed review")
        if int(row["answer_correctness"]) not in {0, 1, 2}:
            raise ValueError("answer_correctness must be 0, 1 or 2")
        by_question[row["question_id"]].append(row)

    if len(by_question) != 23:
        raise ValueError("confirmed extension review must contain 23 questions")
    for question_id, question_rows in by_question.items():
        if len(question_rows) != 4 or {row["method_id"] for row in question_rows} != set(
            METHOD_ORDER
        ):
            raise ValueError(f"question does not contain all four methods: {question_id}")
        if len({row["category"] for row in question_rows}) != 1:
            raise ValueError(f"category differs across methods: {question_id}")
        if len({row["expected_behavior"] for row in question_rows}) != 1:
            raise ValueError(f"expected behavior differs across methods: {question_id}")

    _validate_method_aggregates(metrics, rows)
    return metrics, rows


def category_question_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    question_categories = {
        row["question_id"]: row["category"]
        for row in rows
        if row["method_id"] == METHOD_ORDER[0]
    }
    return {
        category: sum(value == category for value in question_categories.values())
        for category in CATEGORY_ORDER
    }


def category_correctness(rows: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for method_id in METHOD_ORDER:
        method_rows = [row for row in rows if row["method_id"] == method_id]
        result[method_id] = {}
        for category in CATEGORY_ORDER:
            scores = [
                int(row["answer_correctness"])
                for row in method_rows
                if row["category"] == category
            ]
            if not scores:
                raise ValueError(f"missing category rows: {method_id}.{category}")
            result[method_id][category] = sum(scores) / (2 * len(scores))
    return result


def configure_axes(ax, *, x_grid: bool = False) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(
        axis="both" if x_grid else "y",
        color="#D9E2EC",
        linewidth=0.8,
        alpha=0.8,
    )
    ax.set_axisbelow(True)


def save_figure(fig, output_path: Path) -> None:
    fig.savefig(
        output_path,
        dpi=180,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Software": "RAGagent extension figure generator"},
    )
    plt.close(fig)


def plot_quality(metrics: dict, output_dir: Path) -> None:
    metric_specs = [
        ("answer_correctness", "Correctness", "#2F6690"),
        ("evidence_faithfulness", "Faithfulness", "#3A7D44"),
    ]
    fig, ax = plt.subplots(figsize=(10.6, 5.9))
    x = list(range(len(METHOD_ORDER)))
    width = 0.34
    for metric_index, (metric_name, label, color) in enumerate(metric_specs):
        values = [
            float(metrics["methods"][method]["human"][metric_name]["value"])
            for method in METHOD_ORDER
        ]
        denominators = [
            int(metrics["methods"][method]["human"][metric_name]["denominator"])
            for method in METHOD_ORDER
        ]
        bars = ax.bar(
            [position + (metric_index - 0.5) * width for position in x],
            values,
            width=width,
            label=label,
            color=color,
        )
        for bar, value, denominator in zip(bars, values, denominators):
            sample_count = denominator // 2
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.025,
                f"{value:.2f}\nn={sample_count}",
                ha="center",
                va="bottom",
                fontsize=8,
                color="#243B53",
            )
    ax.set_ylim(0, 1.20)
    ax.set_xticks(x, [METHOD_LABELS[method] for method in METHOD_ORDER])
    ax.set_ylabel("Normalized user-confirmed score")
    ax.set_title("Extension answer quality by method", loc="left", weight="bold")
    ax.text(
        0,
        1.08,
        "Correctness covers all 23 questions; Faithfulness excludes refusals, so its n varies.",
        transform=ax.transAxes,
        fontsize=9,
        color="#52606D",
    )
    ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.14))
    configure_axes(ax)
    save_figure(fig, output_dir / "extension_answer_quality.png")


def plot_safety_tradeoff(metrics: dict, output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.3, 6.0))
    label_offsets = {
        "rule_baseline": (12, 15),
        "llm_strict_v2": (-122, 15),
        "llm_no_verifier_v2": (12, -8),
        "llm_partial_pass_v2": (12, 15),
    }
    for method_id in METHOD_ORDER:
        human = metrics["methods"][method_id]["human"]
        over_refusal = human["over_refusal_rate"]
        hallucination = human["hallucination_rate"]
        x_value = float(over_refusal["value"])
        y_value = float(hallucination["value"])
        ax.scatter(
            x_value,
            y_value,
            s=125,
            color=METHOD_COLORS[method_id],
            edgecolor="white",
            linewidth=1.2,
            zorder=3,
        )
        detail = (
            f"{METHOD_LABELS[method_id]}\n"
            f"O {over_refusal['numerator']}/{over_refusal['denominator']}; "
            f"H {hallucination['numerator']}/{hallucination['denominator']}"
        )
        ax.annotate(
            detail,
            (x_value, y_value),
            xytext=label_offsets[method_id],
            textcoords="offset points",
            fontsize=8.5,
            color="#243B53",
            va="center",
        )
    ax.set_xlim(-0.06, 0.98)
    ax.set_ylim(-0.035, 0.36)
    ax.set_xlabel("Over-refusal rate on 19 answerable questions")
    ax.set_ylabel("Observed hallucination rate on substantive answers")
    ax.set_title("Extension safety and coverage trade-off", loc="left", weight="bold")
    ax.text(
        0,
        1.06,
        "Lower-left is preferable; hallucination denominators vary because refusals are excluded.",
        transform=ax.transAxes,
        fontsize=9,
        color="#52606D",
    )
    configure_axes(ax, x_grid=True)
    save_figure(fig, output_dir / "extension_safety_tradeoff.png")


def plot_latency(metrics: dict, output_dir: Path) -> None:
    values = [
        _metric_value(metrics["methods"][method], "automatic", "mean_end_to_end_latency_ms")
        for method in METHOD_ORDER
    ]
    fig, ax = plt.subplots(figsize=(9.6, 5.7))
    bars = ax.bar(
        [METHOD_LABELS[method] for method in METHOD_ORDER],
        values,
        color=[METHOD_COLORS[method] for method in METHOD_ORDER],
        width=0.62,
    )
    ax.set_yscale("log")
    ax.set_ylim(1, max(values) * 2.1)
    for bar, value in zip(bars, values):
        display = f"{value:.2f} ms" if value < 1000 else f"{value / 1000:.2f} s"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value * 1.18,
            display,
            ha="center",
            va="bottom",
            fontsize=8.5,
            color="#243B53",
        )
    ax.set_ylabel("Mean end-to-end latency (ms, log scale)")
    ax.set_title("Extension end-to-end latency", loc="left", weight="bold")
    ax.text(
        0,
        1.08,
        "Single-machine local run; the logarithmic axis keeps the rule and LLM paths visible.",
        transform=ax.transAxes,
        fontsize=9,
        color="#52606D",
    )
    configure_axes(ax)
    save_figure(fig, output_dir / "extension_latency_log.png")


def plot_category_heatmap(rows: list[dict[str, str]], output_dir: Path) -> None:
    scores = category_correctness(rows)
    counts = category_question_counts(rows)
    matrix = [
        [scores[method][category] for category in CATEGORY_ORDER]
        for method in METHOD_ORDER
    ]
    fig, ax = plt.subplots(figsize=(12.2, 5.1))
    image = ax.imshow(matrix, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    x_labels = [
        f"{CATEGORY_LABELS[category]}\n(n={counts[category]})"
        for category in CATEGORY_ORDER
    ]
    ax.set_xticks(range(len(CATEGORY_ORDER)), x_labels)
    ax.set_yticks(range(len(METHOD_ORDER)), [METHOD_LABELS[method] for method in METHOD_ORDER])
    ax.set_title("Extension correctness by question category", loc="left", weight="bold")
    ax.text(
        0,
        1.11,
        "Cell values are mean user-confirmed 0/1/2 correctness scores normalized to 0-1.",
        transform=ax.transAxes,
        fontsize=9,
        color="#52606D",
    )
    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            text_color = "white" if value < 0.22 or value > 0.78 else "#102A43"
            ax.text(
                column_index,
                row_index,
                f"{value:.2f}",
                ha="center",
                va="center",
                color=text_color,
                fontsize=9,
            )
    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.03)
    colorbar.set_label("Normalized correctness")
    save_figure(fig, output_dir / "extension_category_correctness.png")


def figure_purposes() -> dict[str, str]:
    return {
        "extension_answer_quality.png": (
            "User-confirmed answer correctness and evidence faithfulness with effective sample sizes."
        ),
        "extension_safety_tradeoff.png": (
            "Observed hallucination versus over-refusal, with method-specific denominators."
        ),
        "extension_latency_log.png": (
            "Mean end-to-end latency on a log scale for the rule and three LLM methods."
        ),
        "extension_category_correctness.png": (
            "User-confirmed normalized correctness by method and question category."
        ),
    }


def source_hashes() -> dict[str, str]:
    return {
        str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): sha256(path)
        for path in (METRICS_PATH, REVIEWS_PATH)
    }


def build_manifest(
    output_dir: Path, metrics: dict, rows: list[dict[str, str]]
) -> dict:
    figures = {}
    for name, purpose in figure_purposes().items():
        path = output_dir / name
        with Image.open(path) as rendered:
            dimensions = list(rendered.size)
        figures[name] = {
            "sha256": sha256(path),
            "dimensions_px": dimensions,
            "purpose": purpose,
        }
    return {
        "schema_version": "1.0",
        "artifact": "extension_user_confirmed_figures",
        "release_id": metrics["release_id"],
        "review_status": metrics["review_status"],
        "question_count": len({row["question_id"] for row in rows}),
        "review_row_count": len(rows),
        "method_order": METHOD_ORDER,
        "category_question_counts": category_question_counts(rows),
        "category_correctness": category_correctness(rows),
        "sources": source_hashes(),
        "generator": {
            "path": "scripts/generate_extension_figures.py",
            "sha256": sha256(Path(__file__)),
        },
        "figures": figures,
        "limitations": [
            "The extension contains 23 questions, including four no-answer questions.",
            "Scores are Codex-assisted and user-confirmed, not independent double annotation.",
            "Faithfulness and hallucination exclude refusals, so method denominators differ.",
            "Comparisons are descriptive and do not establish statistical significance.",
        ],
    }


def generate(output_dir: Path) -> None:
    metrics, rows = load_inputs()
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_quality(metrics, output_dir)
    plot_safety_tradeoff(metrics, output_dir)
    plot_latency(metrics, output_dir)
    plot_category_heatmap(rows, output_dir)
    manifest = build_manifest(output_dir, metrics, rows)
    (output_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"OK: generated {len(manifest['figures'])} extension figures in {output_dir}")


def check(output_dir: Path) -> None:
    metrics, rows = load_inputs()
    manifest_path = output_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing extension figure manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    expected_fields = {
        "artifact": "extension_user_confirmed_figures",
        "release_id": metrics["release_id"],
        "review_status": "user_confirmed",
        "question_count": 23,
        "review_row_count": 92,
        "method_order": METHOD_ORDER,
        "category_question_counts": category_question_counts(rows),
        "category_correctness": category_correctness(rows),
        "sources": source_hashes(),
    }
    for field, expected in expected_fields.items():
        if manifest.get(field) != expected:
            raise ValueError(f"extension figure manifest field is stale: {field}")
    if manifest.get("generator", {}).get("sha256") != sha256(Path(__file__)):
        raise ValueError("extension figure generator hash is stale")
    if set(manifest.get("figures", {})) != set(figure_purposes()):
        raise ValueError("extension figure manifest has an unexpected figure set")

    for name in figure_purposes():
        path = output_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"missing extension figure: {path}")
        figure_record = manifest["figures"][name]
        if figure_record.get("sha256") != sha256(path):
            raise ValueError(f"extension figure hash mismatch: {name}")
        with Image.open(path) as rendered:
            if figure_record.get("dimensions_px") != list(rendered.size):
                raise ValueError(f"extension figure dimensions mismatch: {name}")
    print(f"OK: extension figure manifest and {len(figure_purposes())} figures are current")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or validate figures from user-confirmed extension results."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--check", action="store_true", help="Validate existing figures and hashes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    try:
        if args.check:
            check(output_dir)
        else:
            generate(output_dir)
    except (FileNotFoundError, ValueError, OSError, KeyError, ZeroDivisionError) as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
