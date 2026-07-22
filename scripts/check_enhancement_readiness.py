from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


OLLAMA_URL = "http://127.0.0.1:11434"
KNOWN_LLM_ENV_NAMES = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DASHSCOPE_API_KEY",
    "DEEPSEEK_API_KEY",
    "AZURE_OPENAI_API_KEY",
)
TEXT_MODEL_MARKERS = (
    "sentence-transformers",
    "text2vec",
    "bge",
    "e5",
    "gte",
    "m3e",
    "multilingual",
)


def http_json(url: str, payload: dict | None = None, timeout: int = 10) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ollama_inventory() -> dict:
    executable = shutil.which("ollama")
    version = None
    if executable:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        version_text = (completed.stdout or completed.stderr).strip()
        version = version_text.rsplit(" ", 1)[-1] if version_text else None

    try:
        tags = http_json(f"{OLLAMA_URL}/api/tags")
        models = [
            {"name": item.get("name", ""), "size_bytes": item.get("size")}
            for item in tags.get("models", [])
        ]
        reachable = True
        error = None
    except (OSError, URLError, ValueError) as exc:
        models = []
        reachable = False
        error = f"{type(exc).__name__}: {exc}"

    return {
        "executable_present": executable is not None,
        "version": version,
        "endpoint": OLLAMA_URL,
        "reachable": reachable,
        "models": models,
        "error": error,
    }


def dense_model_inventory() -> dict:
    cache_root = Path.home() / ".cache" / "huggingface" / "hub"
    cached_names = []
    if cache_root.is_dir():
        cached_names = sorted(path.name for path in cache_root.glob("models--*") if path.is_dir())
    text_models = [
        name for name in cached_names if any(marker in name.lower() for marker in TEXT_MODEL_MARKERS)
    ]
    return {
        "sentence_transformers_installed": importlib.util.find_spec("sentence_transformers") is not None,
        "cached_text_models": text_models,
        "other_cached_model_count": len(cached_names) - len(text_models),
    }


def probe_ollama(model: str, timeout: int) -> dict:
    schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["ok"]},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["status", "evidence_ids"],
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Return status ok and evidence_ids E1. Follow the schema exactly.",
            }
        ],
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"temperature": 0, "num_predict": 128},
    }

    started = time.perf_counter()
    try:
        result = http_json(f"{OLLAMA_URL}/api/chat", payload=payload, timeout=timeout)
    except (OSError, URLError, ValueError) as exc:
        return {
            "attempted": True,
            "model": model,
            "schema_success": False,
            "error": f"{type(exc).__name__}: {exc}",
            "wall_ms": round((time.perf_counter() - started) * 1000, 1),
        }

    message = result.get("message") or {}
    content = str(message.get("content") or "")
    thinking = str(message.get("thinking") or "")
    parsed = None
    if content:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = None
    evidence_ids = parsed.get("evidence_ids", []) if isinstance(parsed, dict) else []
    schema_success = bool(
        isinstance(parsed, dict)
        and parsed.get("status") == "ok"
        and isinstance(evidence_ids, list)
        and "E1" in evidence_ids
    )
    thinking_json = False
    if thinking:
        try:
            thinking_json = isinstance(json.loads(thinking), dict)
        except json.JSONDecodeError:
            thinking_json = False

    return {
        "attempted": True,
        "model": model,
        "answer_field": "message.content",
        "content_length": len(content),
        "thinking_length": len(thinking),
        "thinking_contains_json": thinking_json,
        "json_parse_success": parsed is not None,
        "schema_success": schema_success,
        "done_reason": result.get("done_reason"),
        "output_tokens": result.get("eval_count"),
        "total_ms": round((result.get("total_duration") or 0) / 1_000_000, 1),
        "load_ms": round((result.get("load_duration") or 0) / 1_000_000, 1),
        "wall_ms": round((time.perf_counter() - started) * 1000, 1),
        "error": None,
    }


def build_report(probe: bool, model: str | None, timeout: int) -> dict:
    ollama = ollama_inventory()
    dense = dense_model_inventory()
    configured_env_names = [name for name in KNOWN_LLM_ENV_NAMES if os.getenv(name)]
    clients = {
        name: importlib.util.find_spec(name) is not None
        for name in ("openai", "anthropic", "ollama")
    }

    probe_result = None
    if probe:
        selected_model = model or next(
            (item["name"] for item in ollama["models"] if item.get("name")),
            None,
        )
        if selected_model and ollama["reachable"]:
            probe_result = probe_ollama(selected_model, timeout)
        else:
            probe_result = {
                "attempted": False,
                "schema_success": False,
                "error": "Ollama endpoint or installed model is unavailable",
            }

    if probe_result is not None:
        decision = "conditional_go_enhancement_a" if probe_result["schema_success"] else "no_go"
    elif ollama["reachable"] and ollama["models"]:
        decision = "probe_required"
    else:
        decision = "no_go"

    reasons = []
    if probe_result and not probe_result["schema_success"]:
        reasons.append("structured output did not reach the official answer field")
    if not dense["cached_text_models"]:
        reasons.append("no cached text embedding model is available for enhancement B")

    return {
        "schema_version": "1.0",
        "llm_environment_variable_names": configured_env_names,
        "python_clients": clients,
        "ollama": ollama,
        "dense_retrieval": dense,
        "structured_output_probe": probe_result,
        "decision": decision,
        "reasons": reasons,
        "secrets_printed": False,
    }


def print_summary(report: dict) -> None:
    ollama = report["ollama"]
    dense = report["dense_retrieval"]
    probe = report["structured_output_probe"]
    print(f"ollama_reachable={ollama['reachable']} version={ollama['version']}")
    print(f"ollama_models={[item['name'] for item in ollama['models']]}")
    print(f"configured_llm_env_names={report['llm_environment_variable_names']}")
    print(f"python_clients={report['python_clients']}")
    print(
        "dense_readiness="
        f"library:{dense['sentence_transformers_installed']} "
        f"cached_text_models:{dense['cached_text_models']}"
    )
    if probe is not None:
        print(
            "structured_probe="
            f"schema_success:{probe['schema_success']} "
            f"content_length:{probe.get('content_length')} "
            f"thinking_length:{probe.get('thinking_length')} "
            f"thinking_contains_json:{probe.get('thinking_contains_json')} "
            f"wall_ms:{probe.get('wall_ms')} "
            f"total_ms:{probe.get('total_ms')} "
            f"load_ms:{probe.get('load_ms')}"
        )
    print(f"decision={report['decision']}")
    for reason in report["reasons"]:
        print(f"reason={reason}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit technical-enhancement prerequisites without exposing secrets.")
    parser.add_argument("--probe-ollama", action="store_true", help="Run one real local JSON-Schema probe")
    parser.add_argument("--model", help="Ollama model name; defaults to the first installed model")
    parser.add_argument("--timeout", type=int, default=120, help="Probe timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Print the audit as JSON")
    parser.add_argument("--require-ready", action="store_true", help="Exit nonzero unless enhancement A is ready")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.probe_ollama, args.model, args.timeout)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_summary(report)
    if args.require_ready and report["decision"] != "conditional_go_enhancement_a":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
