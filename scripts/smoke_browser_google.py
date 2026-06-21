# MODULE_CONTRACT: scripts/smoke_browser_google
# Purpose: CLI smoke probe for browser-backed Google SERP and Trends parsing.
# Rationale: Gives Phase 12 verification a deterministic command surface for installed browser engines.
# Dependencies: argparse, json, pathlib, sys, utils.browser_scraper.
# Exports: main.
# LINKS: knowledge-graph.xml#MOD-016, knowledge-graph.xml#MOD-031, verification-plan.xml#V-12-SMOKE-BROWSER-GOOGLE, verification-plan.xml#V-12-SMOKE-BROWSER-GOOGLE-SCRIPT
# MODULE_MAP: scripts/smoke_browser_google.py
# Public Functions: main.
# Private Helpers: _parse_keywords, _blocked_reason, _result_payload.
# Key Semantic Blocks: block_smoke_argument_parse, block_google_smoke_execution, block_google_block_reporting
# Critical Flows: parse CLI args -> execute selected BrowserScraper flow -> emit explicit JSON result.
# Verification: verification-plan.xml#V-12-SMOKE-BROWSER-GOOGLE
# CHANGE_SUMMARY: Added browser Google smoke command used by Phase 12 GRACE verification.

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.browser_scraper import BrowserScraper, BrowserScraperConfig  # noqa: E402


# FUNCTION_CONTRACT: _parse_keywords
# Purpose: Normalize comma-separated CLI keyword input.
# Input: value (str)
# Output: list[str]
# Side Effects: none.
# Business Rules: Empty tokens are discarded and at least one keyword is required.
# Failure Modes: argparse.ArgumentTypeError for empty input.
# LINKS: verification-plan.xml#V-12-SMOKE-BROWSER-GOOGLE
def _parse_keywords(value: str) -> list[str]:
    keywords = [item.strip() for item in value.split(",") if item.strip()]
    if not keywords:
        raise argparse.ArgumentTypeError("at least one keyword is required")
    return keywords


# FUNCTION_CONTRACT: _blocked_reason
# Purpose: Classify Google blocking and rate-limit errors from scraper messages.
# Input: errors (list[str])
# Output: str | None
# Side Effects: none.
# Business Rules: CAPTCHA, unusual traffic, sorry pages, and 429 are explicit blocked reasons.
# Failure Modes: none.
# LINKS: verification-plan.xml#V-12-SMOKE-BROWSER-GOOGLE
def _blocked_reason(errors: list[str]) -> str | None:
    joined = " ".join(errors).lower()
    if "429" in joined or "too many requests" in joined:
        return "google_429"
    if "captcha" in joined or "unusual traffic" in joined or "/sorry/" in joined:
        return "google_blocked"
    return None


# FUNCTION_CONTRACT: _result_payload
# Purpose: Convert BrowserScrapeResult into compact JSON-serializable smoke evidence.
# Input: mode (str), result (Any)
# Output: dict[str, Any]
# Side Effects: none.
# Business Rules: A successful empty Google parse is downgraded to empty_success_forbidden.
# Failure Modes: Missing parsed fields count as zero.
# LINKS: verification-plan.xml#V-12-SMOKE-BROWSER-GOOGLE
def _result_payload(mode: str, result: Any) -> dict[str, Any]:
    # The Trends scraper writes its parsed timeline to `extracted_data`
    # (BrowserScrapeResult.extracted_data), NOT parsed_content. SERP writes to
    # parsed_content. Probe BOTH so each mode reads the attribute the scraper
    # actually populated — otherwise a successful Trends parse reported
    # timeline_count=0 and got mislabeled empty_success_forbidden.
    parsed = result.parsed_content or {}
    extracted = getattr(result, "extracted_data", None) or {}
    errors = list(result.errors or [])
    payload: dict[str, Any] = {
        "mode": mode,
        "success": bool(result.success),
        "source": result.source,
        "errors": errors,
        "blocked_reason": _blocked_reason(errors),
    }
    if mode == "trends":
        timeline = extracted.get("timeline") or parsed.get("timeline") or []
        related = extracted.get("related_queries") or parsed.get("related_queries") or {}
        timeline_count = len(timeline)
        related_top_count = len((related or {}).get("top", []))
        payload.update({"timeline_count": timeline_count, "related_top_count": related_top_count})
        if result.success and timeline_count == 0 and related_top_count == 0:
            payload["success"] = False
            payload["blocked_reason"] = payload["blocked_reason"] or "empty_success_forbidden"
    else:
        organic_count = len(parsed.get("results") or parsed.get("organic") or [])
        paa_count = len(parsed.get("people_also_ask") or [])
        related_count = len(parsed.get("related_searches") or [])
        payload.update({"organic_count": organic_count, "paa_count": paa_count, "related_count": related_count})
        if result.success and organic_count == 0 and paa_count == 0 and related_count == 0:
            payload["success"] = False
            payload["blocked_reason"] = payload["blocked_reason"] or "empty_success_forbidden"
    return payload


# FUNCTION_CONTRACT: main
# Purpose: Run browser-backed Google smoke probes from the command line.
# Input: argv (list[str] | None)
# Output: int process status code
# Side Effects: May launch a local browser and writes JSON to stdout.
# Business Rules: Returns zero for structured scraper output, including explicit Google block reports.
# Failure Modes: Returns 2 for argument errors through argparse.
# LINKS: verification-plan.xml#V-12-SMOKE-BROWSER-GOOGLE
def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    legacy_mode = None
    if raw_args and raw_args[0] in {"search", "serp", "trends"}:
        legacy_mode = "serp" if raw_args[0] in {"search", "serp"} else "trends"
        raw_args = raw_args[1:]

    parser = argparse.ArgumentParser(description="Smoke-test browser-backed Google parsing.")
    parser.add_argument("--mode", choices=("serp", "trends", "both"), default=legacy_mode or "both")
    parser.add_argument("--engine", choices=("cloakbrowser", "playwright", "auto"), default="cloakbrowser")
    parser.add_argument("--query", default="wood shavings")
    parser.add_argument("--keywords", type=_parse_keywords, default=["wood shavings"])
    parser.add_argument("--gl", default="ua")
    parser.add_argument("--hl", default="uk")
    parser.add_argument("--geo", default="UA")
    parser.add_argument("--timeframe", default="today 12-m")
    parser.add_argument("--google-domain", default="google.com.ua")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--num-results", type=int, default=10)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(raw_args)

    scraper = BrowserScraper(
        BrowserScraperConfig(
            engine=args.engine,
            headless=not args.headed,
            timeout_seconds=args.timeout,
            rate_limit_delay=0.0,
        )
    )
    outputs: list[dict[str, Any]] = []
    if args.mode in ("serp", "both"):
        result = scraper.scrape_serp(
            args.query,
            {
                "google_domain": args.google_domain,
                "gl": args.gl,
                "hl": args.hl,
                "locale": f"{args.hl}-{args.gl.upper()}",
                "total_results_target": args.num_results,
                "pages_max": max(1, min(10, (args.num_results + 9) // 10)),
            },
        )
        outputs.append(_result_payload("serp", result))
    if args.mode in ("trends", "both"):
        result = scraper.scrape_google_trends(
            args.keywords,
            {"geo": args.geo, "timeframe": args.timeframe, "hl": args.hl, "tz": 120},
        )
        outputs.append(_result_payload("trends", result))

    print(json.dumps({"results": outputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
