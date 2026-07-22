from __future__ import annotations

import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.config import AgentLLMSettings, LLMSettings


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def main() -> None:
    config_dir = PROJECT_ROOT / "config"
    sources_path = config_dir / "sources.yaml"
    ontology_path = config_dir / "ontology.yaml"
    settings_path = config_dir / "settings.yaml"

    for path in (sources_path, ontology_path, settings_path):
        if not path.exists():
            fail(f"missing config file: {path}")

    sources = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
    ontology = yaml.safe_load(ontology_path.read_text(encoding="utf-8"))
    settings = yaml.safe_load(settings_path.read_text(encoding="utf-8"))

    source_rows = sources.get("sources", [])
    if len(source_rows) != 6:
        fail(f"expected 6 sources, found {len(source_rows)}")

    source_ids = [row.get("id") for row in source_rows]
    if len(source_ids) != len(set(source_ids)):
        fail("source ids must be unique")

    for row in source_rows:
        if not str(row.get("url", "")).startswith("https://scikit-learn.org/stable/modules/"):
            fail(f"source is outside whitelist: {row}")

    required_node_types = {
        "Algorithm",
        "Concept",
        "Task",
        "Metric",
        "MethodFamily",
        "Technique",
        "Problem",
    }
    if set(ontology.get("node_types", [])) != required_node_types:
        fail("ontology node_types do not match the frozen schema")

    required_paths = ["sources", "ontology", "entities", "relations", "chunks", "chroma"]
    missing_paths = [key for key in required_paths if key not in settings.get("paths", {})]
    if missing_paths:
        fail(f"settings.paths missing keys: {missing_paths}")

    try:
        llm_settings = LLMSettings.model_validate(settings.get("llm", {}))
        agent_settings = AgentLLMSettings.model_validate(settings.get("agent", {}))
    except ValidationError as exc:
        fail(f"invalid LLM or Agent settings: {exc}")

    print("OK: config files are valid")
    print(f"OK: sources={len(source_rows)} node_types={len(required_node_types)}")
    print(
        f"OK: llm={llm_settings.provider}/{llm_settings.model} "
        f"planner={agent_settings.planner_backend} "
        f"generator={agent_settings.generator_backend}"
    )


if __name__ == "__main__":
    sys.exit(main())
