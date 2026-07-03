#!/usr/bin/env python3
"""Main orchestration script for seo-google-leak-deep-audit audit."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from analyze_leak_checks import analyze_site
from crawl_site import crawl_site, parse_bool, write_jsonl
from fetch_domain_rdap import load_domain_rdap
from import_ga4_csv import load_ga4_csv
from import_ga4_scroll_csv import load_ga4_scroll_csv
from import_ga4_traffic_csv import load_ga4_traffic_csv
from import_gsc_csv import load_gsc_csv
from import_gsc_timeseries_csv import load_gsc_timeseries_csv
from visual_checks import run_visual_checks


def _read_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def _site_origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _format_proxy_metrics(metrics: dict[str, Any]) -> str:
    lines = ["| Metric | Value |", "|---|---|"]
    for key, value in metrics.items():
        lines.append(f"| `{key}` | `{value}` |")
    return "\n".join(lines)


def _format_data_sources(data_sources: dict[str, Any]) -> str:
    if not data_sources:
        return "No data sources detected."
    lines = ["| Source | Used |", "|---|---|"]
    for key, value in sorted(data_sources.items()):
        lines.append(f"| `{key}` | `{'yes' if value else 'no'}` |")
    return "\n".join(lines)


def _format_metric_coverage(coverage: dict[str, Any]) -> str:
    if not coverage:
        return "Metric coverage is unavailable."
    lines = [
        "| Metric | Status | Proxy | Data | Confidence | Used In |",
        "|---|---|---|---|---|---|",
    ]
    for metric_name, payload in coverage.items():
        status = payload.get("status", "unknown")
        proxy_formula = str(payload.get("proxy_formula", "")).replace("|", "/")
        data = ", ".join(payload.get("data", []))
        confidence = payload.get("confidence", "")
        used_in = ", ".join(payload.get("used_in", []))
        lines.append(
            f"| `{metric_name}` | `{status}` | {proxy_formula} | `{data}` | `{confidence}` | `{used_in}` |"
        )
    return "\n".join(lines)


def _format_url_aliases_section(url_aliases: dict[str, Any]) -> str:
    if not url_aliases:
        return "URL alias detection unavailable."
    total = int(url_aliases.get("total_aliases", 0) or 0)
    canonical_urls = int(url_aliases.get("canonical_pages_with_aliases", 0) or 0)
    sitemap_aliases = int(url_aliases.get("sitemap_aliases", 0) or 0)
    top_rows = url_aliases.get("top", []) if isinstance(url_aliases.get("top"), list) else []

    if total <= 0:
        return "No URL aliases detected."

    lines: list[str] = []
    lines.append(f"- Total aliases detected: `{total}` across `{canonical_urls}` canonical URL(s).")
    if sitemap_aliases:
        lines.append(f"- Aliases discovered from sitemap seeds: `{sitemap_aliases}`.")
    if top_rows:
        lines.append("")
        lines.append("| Canonical URL | Aliases | From sitemap | Examples |")
        lines.append("|---|---:|---:|---|")
        for row in top_rows[:10]:
            examples = ", ".join(row.get("examples", []))
            lines.append(
                f"| {row.get('canonical_url', '')} | {row.get('alias_count', 0)} | {row.get('sitemap_alias_count', 0)} | {examples} |"
            )
    lines.append("")
    lines.append(
        "Interpretation: these URLs resolve/canonicalize to the same page (e.g., `index.html?cat_id=...` → clean slug). Prefer canonical URLs in sitemaps and internal links."
    )
    return "\n".join(lines).strip()


def _format_authority_panel(authority_graph: dict[str, Any]) -> str:
    if not authority_graph:
        return "No authority graph data available."
    pagerank_rows = authority_graph.get("top_internal_pagerank_pages", [])
    money_rows = authority_graph.get("money_page_prominence", [])
    anchor_stats = authority_graph.get("anchor_stats", {})

    lines: list[str] = []
    lines.append(
        f"- Anchor stats: `{json.dumps(anchor_stats, ensure_ascii=False)}`"
    )
    if pagerank_rows:
        lines.append("")
        lines.append("Top pages by internal PageRank:")
        lines.append("| URL | Score |")
        lines.append("|---|---:|")
        for row in pagerank_rows[:10]:
            lines.append(f"| {row.get('url', '')} | {row.get('score', 0)} |")
    if money_rows:
        lines.append("")
        lines.append("Top money pages by prominence:")
        lines.append("| URL | Prominence | Inlinks |")
        lines.append("|---|---:|---:|")
        for row in money_rows[:10]:
            lines.append(
                f"| {row.get('url', '')} | {row.get('prominence', 0)} | {row.get('inlinks', 0)} |"
            )
    return "\n".join(lines).strip()


def _format_checks_section(checks: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for check in checks:
        lines.append(f"### {check['id']} - {check['title']}")
        lines.append(f"- Stage: `{check['stage']}`")
        lines.append(f"- Severity: `{check['severity']}`")
        lines.append(f"- Confidence: `{check['confidence']}`")
        lines.append(
            f"- Proxy metric: `{json.dumps(check.get('proxy_metric', {}), ensure_ascii=False)}`"
        )
        evidence = check.get("evidence_urls", [])
        if evidence:
            lines.append("- Evidence URLs:")
            for url in evidence[:10]:
                lines.append(f"  - {url}")
        else:
            lines.append("- Evidence URLs: none")
        lines.append("- Fix steps:")
        for step in check.get("fix_steps", []):
            lines.append(f"  - {step}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_noindex_section(
    noindex_pages: list[dict[str, Any]], include_noindex: bool
) -> str:
    if not noindex_pages:
        return "No noindex pages detected."
    mode = (
        "included in analysis"
        if include_noindex
        else "excluded from analysis (use `--include-noindex true` to include)"
    )
    lines = [f"Found **{len(noindex_pages)}** noindex page(s), {mode}.\n"]
    lines.append("| URL | Title | Robots | Words |")
    lines.append("|---|---|---|---:|")
    for item in noindex_pages[:30]:
        lines.append(
            f"| {item.get('url', '')} | {item.get('title', '')[:60]} | `{item.get('robots', '')}` | {item.get('word_count', 0)} |"
        )
    return "\n".join(lines)


def _format_navboost_section(
    navboost_risk_pages: list[dict[str, Any]], navboost_panel: dict[str, Any]
) -> str:
    if not navboost_risk_pages:
        if not navboost_panel:
            return "No NavBoost-risk pages detected from available signals."
        lines = [
            f"- COEC site median: `{navboost_panel.get('coec_site_median', 0)}`",
            f"- Scroll depth proxy: `{navboost_panel.get('scroll_depth_proxy', 0)}`",
            f"- Direct visits proxy: `{navboost_panel.get('direct_url_visits_proxy', 0)}`",
        ]
        return "\n".join(lines)

    lines = [
        f"- COEC site median: `{navboost_panel.get('coec_site_median', 0)}`",
        f"- Scroll depth proxy: `{navboost_panel.get('scroll_depth_proxy', 0)}`",
        f"- Direct visits proxy: `{navboost_panel.get('direct_url_visits_proxy', 0)}`",
        "",
        "| URL | Score | Reasons |",
        "|---|---:|---|",
    ]
    for item in navboost_risk_pages[:20]:
        reasons = ", ".join(item.get("reasons", []))
        lines.append(f"| {item.get('url', '')} | {item.get('score', 0)} | {reasons} |")
    serp_demotion_pages = navboost_panel.get("serp_demotion_pages", [])
    if serp_demotion_pages:
        lines.append("")
        lines.append("Low-COEC / SERP demotion candidates:")
        lines.append("| URL | COEC | Impressions | Position Volatility |")
        lines.append("|---|---:|---:|---:|")
        for row in serp_demotion_pages[:15]:
            lines.append(
                f"| {row.get('url', '')} | {row.get('coec', 0)} | {row.get('impressions', 0)} | {row.get('position_volatility', 0)} |"
            )
    return "\n".join(lines)


def _format_growth_section(growth_actions: list[dict[str, Any]]) -> str:
    if not growth_actions:
        return "No strategic actions generated (no medium/high issues found)."
    lines: list[str] = []
    for action in growth_actions:
        lines.append(f"### {action['id']} - {action['title']}")
        lines.append(f"- Priority: `{action['priority']}` ({action['priority_score']})")
        lines.append(f"- Linked checks: {', '.join(action['linked_checks'])}")
        lines.append("- Tasks:")
        for task in action.get("tasks", []):
            lines.append(f"  - {task}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_pipeline_summary(checks: list[dict[str, Any]]) -> str:
    stage_map = {
        "Mustang": {"issues": 0, "total": 0},
        "Twiddlers": {"issues": 0, "total": 0},
        "NavBoost": {"issues": 0, "total": 0},
    }
    for check in checks:
        stage = check.get("stage", "Mustang")
        if stage not in stage_map:
            stage_map[stage] = {"issues": 0, "total": 0}
        stage_map[stage]["total"] += 1
        if check.get("evidence_urls") and check.get("severity") in {
            "Critical",
            "High",
            "Medium",
        }:
            stage_map[stage]["issues"] += 1
    lines = ["| Stage | Checks | With Issues |", "|---|---:|---:|"]
    for stage, counters in stage_map.items():
        lines.append(f"| {stage} | {counters['total']} | {counters['issues']} |")
    return "\n".join(lines)


def _split_plan_buckets(growth_actions: list[dict[str, Any]]) -> tuple[str, str, str]:
    if not growth_actions:
        fallback = "- Keep monitoring and rerun audit after meaningful content updates."
        return fallback, fallback, fallback

    day30: list[str] = []
    day60: list[str] = []
    day90: list[str] = []
    for action in growth_actions:
        line = f"- [{action['priority']}] {action['title']}: {action['tasks'][0]}"
        if action["priority"] == "Critical":
            day30.append(line)
        elif action["priority"] == "High":
            day60.append(line)
        else:
            day90.append(line)
    if not day30:
        day30.append("- Fix the top two highest-priority action groups first.")
    if not day60:
        day60.append(
            "- Expand execution to medium-priority architecture/content tasks."
        )
    if not day90:
        day90.append("- Stabilize, monitor, and iterate based on KPI deltas.")
    return "\n".join(day30), "\n".join(day60), "\n".join(day90)


def _format_missing_data_recommendations(metric_coverage: dict[str, Any]) -> str:
    missing_metrics = [
        (metric_name, payload)
        for metric_name, payload in metric_coverage.items()
        if payload.get("status") == "missing-data"
    ]
    if not missing_metrics:
        return "- All tracked proxy metrics have sufficient input data."

    lines: list[str] = []
    for metric_name, payload in missing_metrics[:15]:
        required = payload.get("data_required") or payload.get("data") or []
        required_text = ", ".join(required)
        lines.append(f"- `{metric_name}`: add `{required_text}`")
    return "\n".join(lines)


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    cache_dir = Path(args.cache_dir)
    out_dir = Path(args.out_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Crawl
    crawl_rows = crawl_site(
        site_url=args.site_url,
        max_pages=args.max_pages,
        concurrency=args.concurrency,
        delay_ms=args.delay_ms,
        respect_robots=parse_bool(args.respect_robots),
        sitemap_sources=args.sitemap,
        sitemap_page_sources=args.sitemap_page,
    )
    crawl_path = cache_dir / "crawl.jsonl"
    write_jsonl(crawl_rows, crawl_path)

    # 2) Optional visual checks
    visual_payload = {"enabled": False, "mode": "disabled", "results": []}
    if args.use_playwright in {"auto", "true"}:
        sample_urls = [
            row.get("url", "")
            for row in crawl_rows
            if row.get("status", 0) and int(row["status"]) < 400
        ][:12]
        visual_payload = run_visual_checks(
            sample_urls, use_playwright=args.use_playwright
        )
    _save_json(cache_dir / "visual.json", visual_payload)

    # 3) Optional external imports
    site_origin = _site_origin(args.site_url)
    external_payload: dict[str, Any] = {}
    if args.gsc_pages:
        external_payload["gsc"] = load_gsc_csv(
            Path(args.gsc_pages), site_origin=site_origin
        )
    if args.gsc_queries:
        external_payload["gsc_queries"] = load_gsc_csv(
            Path(args.gsc_queries), site_origin=site_origin
        )
    if args.ga4:
        external_payload["ga4"] = load_ga4_csv(Path(args.ga4), site_origin=site_origin)
    if args.gsc_timeseries:
        external_payload["gsc_timeseries"] = load_gsc_timeseries_csv(
            Path(args.gsc_timeseries), site_origin=site_origin
        )
    if args.ga4_traffic:
        external_payload["ga4_traffic"] = load_ga4_traffic_csv(
            Path(args.ga4_traffic), site_origin=site_origin
        )
    if args.ga4_scroll:
        external_payload["ga4_scroll"] = load_ga4_scroll_csv(
            Path(args.ga4_scroll), site_origin=site_origin
        )
    try:
        rdap_profile = load_domain_rdap(args.site_url)
    except Exception as exc:
        rdap_profile = {"source": "rdap", "error": str(exc)}
    if rdap_profile:
        external_payload["rdap_whois"] = rdap_profile
    _save_json(cache_dir / "external.json", external_payload)

    # 4) Analyze checks
    include_noindex = parse_bool(args.include_noindex)
    analysis = analyze_site(
        crawl_rows,
        external_data=external_payload,
        visual_data=visual_payload,
        include_noindex=include_noindex,
    )
    _save_json(cache_dir / "analysis.json", analysis)

    # 5) Render reports
    script_dir = Path(__file__).resolve().parent
    root_dir = script_dir.parent
    report_template = _read_template(root_dir / "templates" / "report.md")
    action_template = _read_template(root_dir / "templates" / "action-plan.md")

    checks = analysis.get("checks", [])
    growth_actions = analysis.get("growth_actions", [])
    summary = analysis.get("summary", {})
    generated_at = datetime.now(timezone.utc).isoformat()

    report_text = _render_template(
        report_template,
        {
            "site_url": args.site_url,
            "generated_at": generated_at,
            "pages_crawled": str(summary.get("pages_crawled", 0)),
            "checks_with_issues": str(summary.get("checks_with_issues", 0)),
            "pipeline_summary": _format_pipeline_summary(checks),
            "data_sources_section": _format_data_sources(
                analysis.get("data_sources", {})
            ),
            "url_aliases_section": _format_url_aliases_section(
                analysis.get("url_aliases", {})
            ),
            "proxy_metrics": _format_proxy_metrics(analysis.get("proxy_metrics", {})),
            "metric_coverage_section": _format_metric_coverage(
                analysis.get("metric_coverage", {})
            ),
            "authority_graph_section": _format_authority_panel(
                analysis.get("authority_graph", {})
            ),
            "noindex_section": _format_noindex_section(
                analysis.get("noindex_pages", []), include_noindex
            ),
            "checks_section": _format_checks_section(checks),
            "navboost_section": _format_navboost_section(
                analysis.get("navboost_risk_pages", []),
                analysis.get("navboost_panel", {}),
            ),
            "growth_section": _format_growth_section(growth_actions),
        },
    )

    plan_30, plan_60, plan_90 = _split_plan_buckets(growth_actions)
    action_text = _render_template(
        action_template,
        {
            "site_url": args.site_url,
            "generated_at": generated_at,
            "actions_section": _format_growth_section(growth_actions),
            "plan_30": plan_30,
            "plan_60": plan_60,
            "plan_90": plan_90,
            "missing_data_section": _format_missing_data_recommendations(
                analysis.get("metric_coverage", {})
            ),
        },
    )

    (out_dir / "LEAK-AUDIT-REPORT.md").write_text(report_text, encoding="utf-8")
    (out_dir / "LEAK-ACTION-PLAN.md").write_text(action_text, encoding="utf-8")

    return {
        "crawl_path": str(crawl_path),
        "analysis_path": str(cache_dir / "analysis.json"),
        "report_path": str(out_dir / "LEAK-AUDIT-REPORT.md"),
        "action_plan_path": str(out_dir / "LEAK-ACTION-PLAN.md"),
        "summary": summary,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run leak-inspired SEO audit.")
    parser.add_argument("site_url")
    parser.add_argument("--max-pages", type=int, default=300)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Max concurrent in-flight page fetches (respects --delay-ms between request starts).",
    )
    parser.add_argument("--delay-ms", type=int, default=200)
    parser.add_argument("--respect-robots", default="true")
    parser.add_argument(
        "--sitemap",
        action="append",
        default=[],
        help="XML sitemap source (URL or local file path). Repeat flag for multiple sources.",
    )
    parser.add_argument(
        "--sitemap-page",
        action="append",
        default=[],
        help="HTML sitemap page source (URL or local file path). Repeat flag for multiple sources.",
    )
    parser.add_argument("--gsc-pages")
    parser.add_argument("--gsc-queries")
    parser.add_argument("--ga4")
    parser.add_argument("--gsc-timeseries")
    parser.add_argument("--ga4-traffic")
    parser.add_argument("--ga4-scroll")
    parser.add_argument(
        "--use-playwright", default="auto", choices=["auto", "true", "false"]
    )
    parser.add_argument(
        "--include-noindex",
        default="false",
        help="Include noindex pages in the 12-check analysis (default: false).",
    )
    parser.add_argument("--out-dir", default="reports")
    parser.add_argument("--cache-dir", default="cache")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = run_audit(args)
    print("Audit completed.")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
