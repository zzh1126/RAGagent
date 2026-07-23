from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a desktop/mobile Streamlit runtime-status browser smoke"
    )
    parser.add_argument("--url", default="http://127.0.0.1:8502")
    parser.add_argument("--query", required=True)
    parser.add_argument(
        "--expected-decision",
        choices=("PASS", "PARTIAL_PASS", "REFUSE"),
        required=True,
    )
    parser.add_argument("--expected-fallback", choices=("true", "false"), required=True)
    parser.add_argument(
        "--expected-structured",
        choices=("success", "failed", "not called", "N/A"),
        required=True,
    )
    parser.add_argument(
        "--expected-prewarm",
        choices=("ready", "failed", "unsupported", "not_applicable"),
        required=True,
    )
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--timeout-ms", type=int, default=180_000)
    return parser.parse_args()


def extract_metric(body_text: str, label: str) -> str:
    match = re.search(rf"(?:^|\n){re.escape(label)}\s+([^\n]+)", body_text)
    if match is None:
        raise AssertionError(f"missing runtime metric: {label}")
    return match.group(1).strip()


def main() -> None:
    args = parse_args()
    output_prefix = Path(args.output_prefix)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)
        page.get_by_role("textbox", name="问题", exact=True).wait_for(
            state="visible",
            timeout=args.timeout_ms,
        )
        query_box = page.get_by_role("textbox", name="问题", exact=True)
        submit = page.get_by_role("button", name="运行问答", exact=True)
        if query_box.count() != 1 or submit.count() != 1:
            raise AssertionError("Streamlit question controls are not unique")

        query_box.fill(args.query)
        submit.click()
        status = page.locator("p.status-pass, p.status-partial, p.status-refuse")
        status.wait_for(state="visible", timeout=args.timeout_ms)
        expect(submit).to_be_enabled(timeout=args.timeout_ms)
        running = page.get_by_text("RUNNING...", exact=True)
        if running.count():
            running.wait_for(state="hidden", timeout=args.timeout_ms)
        page.wait_for_timeout(500)

        decision = status.inner_text().removeprefix("Verifier: ").strip()
        if decision != args.expected_decision:
            raise AssertionError(
                f"unexpected decision: expected {args.expected_decision}, got {decision}"
            )

        body_text = page.locator("body").inner_text()
        fallback = extract_metric(body_text, "Fallback")
        if fallback != args.expected_fallback:
            raise AssertionError(
                f"unexpected fallback: expected {args.expected_fallback}, got {fallback}"
            )
        structured = extract_metric(body_text, "Structured JSON")
        if structured != args.expected_structured:
            raise AssertionError(
                "unexpected structured-output status: "
                f"expected {args.expected_structured}, got {structured}"
            )
        if f"Prewarm: {args.expected_prewarm}" not in body_text:
            raise AssertionError(
                f"expected prewarm status is not visible: {args.expected_prewarm}"
            )
        for required_label in (
            "Generator",
            "Backend",
            "Structured JSON",
            "Routing latency",
            "Retrieval latency",
            "Packing latency",
            "LLM latency",
            "Verification latency",
            "Retry latency",
        ):
            extract_metric(body_text, required_label)
        if "Cache: disabled" not in body_text:
            raise AssertionError("answer cache status is not visible")
        if page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        ):
            raise AssertionError("desktop viewport has horizontal overflow")

        desktop_path = output_prefix.with_name(output_prefix.name + "_desktop.png")
        page.screenshot(path=str(desktop_path), full_page=True)

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(500)
        if page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        ):
            raise AssertionError("mobile viewport has horizontal overflow")
        mobile_path = output_prefix.with_name(output_prefix.name + "_mobile.png")
        page.screenshot(path=str(mobile_path), full_page=True)

        print(f"OK: decision={decision}")
        print(f"OK: generator={extract_metric(body_text, 'Generator')}")
        print(f"OK: backend={extract_metric(body_text, 'Backend')}")
        print(f"OK: fallback={fallback}")
        print(f"OK: structured={structured}")
        print(f"OK: prewarm={args.expected_prewarm}")
        print(f"OK: desktop={desktop_path}")
        print(f"OK: mobile={mobile_path}")
        browser.close()


if __name__ == "__main__":
    main()
