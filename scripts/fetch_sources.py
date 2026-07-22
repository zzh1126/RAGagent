from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sources_path = PROJECT_ROOT / "config" / "sources.yaml"
    out_dir = PROJECT_ROOT / "data" / "raw" / "html"
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = yaml.safe_load(sources_path.read_text(encoding="utf-8"))["sources"]
    manifest = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": "sklearn-ml-qa-agent-research-practice/0.1",
    })

    for source in sources:
        html_path = out_dir / f"{source['id']}_{source['name']}.html"
        meta_path = out_dir / f"{source['id']}_{source['name']}.json"
        if html_path.exists() and html_path.stat().st_size > 1000:
            status = "cached"
            retrieved_at = json.loads(meta_path.read_text(encoding="utf-8")).get("retrieved_at") if meta_path.exists() else None
        else:
            response = session.get(source["url"], timeout=30)
            response.raise_for_status()
            html_path.write_text(response.text, encoding="utf-8", newline="\n")
            retrieved_at = datetime.now(timezone.utc).isoformat()
            meta_path.write_text(
                json.dumps(
                    {
                        "source_id": source["id"],
                        "name": source["name"],
                        "url": source["url"],
                        "retrieved_at": retrieved_at,
                        "status_code": response.status_code,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            status = "fetched"
            time.sleep(1)

        manifest.append({
            "source_id": source["id"],
            "name": source["name"],
            "url": source["url"],
            "html_path": str(html_path.relative_to(PROJECT_ROOT)),
            "status": status,
            "retrieved_at": retrieved_at,
        })
        print(f"OK: {source['id']} {source['name']} {status}")

    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: wrote {out_dir / 'manifest.json'}")


if __name__ == "__main__":
    sys.exit(main())
