from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.config import load_experiment_suite


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the frozen experiment matrix")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config" / "experiments.yaml",
    )
    args = parser.parse_args()
    path = args.config if args.config.is_absolute() else PROJECT_ROOT / args.config
    suite = load_experiment_suite(path)
    frozen_result = PROJECT_ROOT / suite.protocol.frozen_holdout.result_path
    if not frozen_result.is_file():
        raise FileNotFoundError(f"frozen final result does not exist: {frozen_result}")
    print(f"OK: experiment config is valid: {path}")
    print(f"OK: config_fingerprint={suite.fingerprint()}")
    print(
        "OK: protocol="
        f"tuning:{suite.protocol.tuning_split}, "
        f"experiment:{suite.protocol.experiment_split}, "
        f"frozen:{suite.protocol.frozen_holdout.split}"
    )
    print(f"OK: frozen_result_policy=read-only ({frozen_result})")
    for name, experiment in suite.experiments.items():
        state = "enabled" if experiment.enabled else "disabled"
        print(
            f"- {name}: {state}, retrieval={experiment.retrieval_mode}, "
            f"router={experiment.router_mode}, verifier={experiment.verifier_enabled}"
        )


if __name__ == "__main__":
    main()
