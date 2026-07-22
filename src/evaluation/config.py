from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


ExperimentRetrievalMode = Literal["none", "vector", "graph", "hybrid", "adaptive"]
ExperimentRouterMode = Literal[
    "none", "fixed_vector", "fixed_graph", "fixed_hybrid", "adaptive"
]
AnswerGeneratorMode = Literal["offline_rule", "llm"]

REQUIRED_ENABLED_EXPERIMENTS = {"vector_rag", "graph_only", "proposed", "no_verifier"}
REQUIRED_EXPERIMENTS = REQUIRED_ENABLED_EXPERIMENTS | {"direct_llm", "no_router"}


class FrozenHoldoutPolicy(BaseModel):
    split: Literal["final"] = "final"
    result_path: str = "reports/evaluation_final.json"
    policy: Literal["reuse_v1_result_only"] = "reuse_v1_result_only"


class ExperimentProtocol(BaseModel):
    tuning_split: Literal["dev", "pilot"] = "dev"
    experiment_split: Literal["dev", "pilot"] = "pilot"
    output_dir: str = "reports/experiments"
    answer_generator: Literal["offline_rule"] = "offline_rule"
    retrieval_recall_k: Literal[5] = 5
    frozen_holdout: FrozenHoldoutPolicy = Field(default_factory=FrozenHoldoutPolicy)

    @model_validator(mode="after")
    def validate_split_policy(self) -> "ExperimentProtocol":
        if self.tuning_split == "final" or self.experiment_split == "final":
            raise ValueError("final split is read-only and cannot be used for tuning or experiments")
        return self


class ExperimentDefinition(BaseModel):
    id: str
    display_name: str
    enabled: bool
    retrieval_mode: ExperimentRetrievalMode
    router_mode: ExperimentRouterMode
    verifier_enabled: bool
    answer_generator: AnswerGeneratorMode
    requires_network: bool = False
    purpose: str


class ExperimentSuite(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    protocol: ExperimentProtocol
    experiments: dict[str, ExperimentDefinition]

    @model_validator(mode="after")
    def validate_matrix(self) -> "ExperimentSuite":
        configured = set(self.experiments)
        missing = REQUIRED_EXPERIMENTS - configured
        if missing:
            raise ValueError(f"missing required experiment definitions: {sorted(missing)}")

        for key, experiment in self.experiments.items():
            if key != experiment.id:
                raise ValueError(f"experiment key/id mismatch: {key} != {experiment.id}")

        expected = {
            "vector_rag": ("vector", "fixed_vector", False),
            "graph_only": ("graph", "fixed_graph", False),
            "proposed": ("adaptive", "adaptive", True),
            "no_verifier": ("adaptive", "adaptive", False),
        }
        for name, (retrieval_mode, router_mode, verifier_enabled) in expected.items():
            experiment = self.experiments[name]
            if not experiment.enabled:
                raise ValueError(f"required experiment must be enabled: {name}")
            if (
                experiment.retrieval_mode != retrieval_mode
                or experiment.router_mode != router_mode
                or experiment.verifier_enabled != verifier_enabled
            ):
                raise ValueError(f"invalid ablation contract for {name}")
            if experiment.answer_generator != "offline_rule":
                raise ValueError(f"required offline experiment cannot use {experiment.answer_generator}: {name}")

        direct_llm = self.experiments["direct_llm"]
        if direct_llm.enabled:
            raise ValueError("direct_llm must remain disabled until a stable real LLM is available")
        if direct_llm.answer_generator != "llm" or direct_llm.retrieval_mode != "none":
            raise ValueError("direct_llm must be an explicitly disabled knowledge-free LLM configuration")

        if self.experiments["no_router"].enabled:
            raise ValueError("no_router is optional and must remain disabled in the first experiment batch")
        return self

    def fingerprint(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def load_experiment_suite(path: Path) -> ExperimentSuite:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"experiment config must be a mapping: {path}")
    return ExperimentSuite.model_validate(raw)
