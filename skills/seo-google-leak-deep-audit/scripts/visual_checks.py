#!/usr/bin/env python3
"""Optional Playwright-powered visual checks for mobile/UI penalties."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_urls(crawl_jsonl: Path, max_pages: int) -> list[str]:
    urls: list[str] = []
    if not crawl_jsonl.exists():
        return urls
    for line in crawl_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("status", 0) and int(row["status"]) >= 400:
            continue
        url = row.get("url")
        if isinstance(url, str) and url:
            urls.append(url)
        if len(urls) >= max_pages:
            break
    return urls


def _evaluate_with_playwright(urls: list[str]) -> list[dict[str, Any]]:
    from playwright.sync_api import sync_playwright  # type: ignore

    results: list[dict[str, Any]] = []
    script = """
    () => {
      const viewportArea = window.innerWidth * window.innerHeight;
      const nodes = Array.from(document.querySelectorAll('*'));
      let intrusive = 0;
      let fullscreenIntrusive = 0;
      let popupKeywordCount = 0;
      const popupRe = /(popup|modal|interstitial|subscribe|newsletter)/i;
      for (const node of nodes) {
        const style = window.getComputedStyle(node);
        if (!style) continue;
        if (style.display === 'none' || style.visibility === 'hidden') continue;
        const attrs = `${node.id || ''} ${(node.className || '').toString()} ${(node.getAttribute('role') || '')}`;
        if (popupRe.test(attrs)) popupKeywordCount += 1;
        if (style.position !== 'fixed' && style.position !== 'sticky') continue;
        const rect = node.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) continue;
        const area = rect.width * rect.height;
        const ratio = area / viewportArea;
        if (ratio >= 0.12) intrusive += 1;
        if (ratio >= 0.4) fullscreenIntrusive += 1;
      }
      const hasHorizontalScroll =
        document.documentElement.scrollWidth > window.innerWidth + 4;
      const scriptEntries = performance.getEntriesByType('resource')
        .filter(r => (r.initiatorType || '').toLowerCase() === 'script').length;
      const hasDelayedPopupHint =
        popupKeywordCount > 0 && intrusive === 0 &&
        nodes.some(node => {
          const attrs = `${node.id || ''} ${(node.className || '').toString()}`;
          if (!popupRe.test(attrs)) return false;
          const style = window.getComputedStyle(node);
          if (!style) return false;
          return style.display === 'none' || style.opacity === '0';
        });
      return {
        intrusiveOverlays: intrusive,
        fullscreenIntrusive,
        popupKeywordCount,
        hasDelayedPopupHint,
        hasHorizontalScroll,
        scriptEntries
      };
    }
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="seo-google-leak-deep-audit-visual/1.0",
            is_mobile=True,
            device_scale_factor=2,
        )
        page = context.new_page()
        for url in urls:
            result: dict[str, Any] = {"url": url, "error": None}
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                data = page.evaluate(script)
                intrusive = int(data.get("intrusiveOverlays", 0))
                scripts = int(data.get("scriptEntries", 0))
                result.update(
                    {
                        "overlay_detected": intrusive > 0,
                        "intrusive_overlay_count": intrusive,
                        "fullscreen_intrusive_count": int(
                            data.get("fullscreenIntrusive", 0)
                        ),
                        "popup_keyword_count": int(data.get("popupKeywordCount", 0)),
                        "delayed_popup_hint": bool(data.get("hasDelayedPopupHint", False)),
                        "violates_mobile_interstitial_policy_proxy": bool(
                            int(data.get("fullscreenIntrusive", 0)) > 0
                            or (
                                intrusive > 0
                                and int(data.get("popupKeywordCount", 0)) > 0
                            )
                            or bool(data.get("hasDelayedPopupHint", False))
                        ),
                        "horizontal_scroll": bool(data.get("hasHorizontalScroll", False)),
                        "heavy_js": scripts > 25,
                        "script_entries": scripts,
                    }
                )
            except Exception as exc:
                result["error"] = str(exc)
                result.update(
                    {
                        "overlay_detected": False,
                        "intrusive_overlay_count": 0,
                        "fullscreen_intrusive_count": 0,
                        "popup_keyword_count": 0,
                        "delayed_popup_hint": False,
                        "violates_mobile_interstitial_policy_proxy": False,
                        "horizontal_scroll": False,
                        "heavy_js": False,
                        "script_entries": 0,
                    }
                )
            results.append(result)
        context.close()
        browser.close()
    return results


def run_visual_checks(
    urls: list[str],
    use_playwright: str = "auto",
) -> dict[str, Any]:
    """Run mobile visual checks with optional Playwright fallback."""
    mode = use_playwright.strip().lower()
    if mode not in {"auto", "true", "false"}:
        raise ValueError("--use-playwright must be auto|true|false")
    if mode == "false":
        return {"enabled": False, "mode": "disabled", "reason": "user_disabled", "results": []}

    try:
        results = _evaluate_with_playwright(urls)
    except ModuleNotFoundError:
        if mode == "true":
            raise
        return {
            "enabled": False,
            "mode": "auto",
            "reason": "playwright_not_installed",
            "results": [],
        }
    except Exception as exc:  # pragma: no cover - environment-specific
        if mode == "true":
            raise
        return {
            "enabled": False,
            "mode": "auto",
            "reason": f"playwright_error: {exc}",
            "results": [],
        }

    risk_count = sum(
        1
        for item in results
        if item.get("overlay_detected")
        or item.get("horizontal_scroll")
        or item.get("heavy_js")
        or item.get("violates_mobile_interstitial_policy_proxy")
    )
    return {
        "enabled": True,
        "mode": mode,
        "reason": "",
        "results": results,
        "summary": {
            "checked_urls": len(results),
            "risk_urls": risk_count,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run optional visual checks for leak-audit.")
    parser.add_argument("--crawl-jsonl", type=Path, default=Path("cache/crawl.jsonl"))
    parser.add_argument("--max-pages", type=int, default=12)
    parser.add_argument("--use-playwright", default="auto")
    parser.add_argument("--output", type=Path, default=Path("cache/visual.json"))
    args = parser.parse_args()

    urls = _load_urls(args.crawl_jsonl, max_pages=args.max_pages)
    payload = run_visual_checks(urls, use_playwright=args.use_playwright)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Checked URLs: {len(urls)}")
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
