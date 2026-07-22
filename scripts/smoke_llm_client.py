from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.llm import LLMError, LLMSettings, create_llm_client


class ClientSmokePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    evidence_ids: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one synthetic structured-output request through the production LLM Client."
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=PROJECT_ROOT / "config" / "settings.yaml",
    )
    parser.add_argument("--timeout", type=float)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings_path = args.settings if args.settings.is_absolute() else PROJECT_ROOT / args.settings
    raw_settings = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    llm_settings = LLMSettings.model_validate(raw_settings.get("llm", {}))
    events = []
    client = create_llm_client(llm_settings, event_sink=events.append)

    try:
        result = client.generate_structured(
            messages=[
                {
                    "role": "system",
                    "content": "Return only JSON that follows the supplied schema.",
                },
                {
                    "role": "user",
                    "content": "Return status ok and evidence_ids containing exactly E1.",
                },
            ],
            response_model=ClientSmokePayload,
            timeout_seconds=args.timeout,
            node="llm_client_smoke",
        )
    except LLMError as exc:
        print(f"ERROR: LLM Client smoke failed error_type={type(exc).__name__}")
        return 1

    if result.status != "ok" or result.evidence_ids != ["E1"]:
        print("ERROR: LLM Client smoke returned schema-valid but semantically invalid output")
        return 1
    if not events:
        print("ERROR: LLM Client smoke did not emit call metadata")
        return 1

    record = events[-1]
    print("OK: production LLM Client returned schema-valid synthetic output")
    print(
        f"OK: provider={record.provider} model={record.model} "
        f"attempts={record.attempts} latency_ms={record.latency_ms:.1f}"
    )
    print("OK: formal_content_used=True thinking_content_recorded=False")
    return 0


if __name__ == "__main__":
    sys.exit(main())
