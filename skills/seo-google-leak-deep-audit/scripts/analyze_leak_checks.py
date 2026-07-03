#!/usr/bin/env python3
"""Analyze crawl signals and compute 12 leak-inspired SEO checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def normalize_url(value: str) -> str:
    """Normalize URL for joins and matching."""
    parsed = urlparse((value or "").strip())
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    query = parsed.query
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    if not netloc and parsed.path:
        reparsed = urlparse(f"{scheme}://{value.strip()}")
        netloc = reparsed.netloc.lower()
        path = reparsed.path or "/"
        query = reparsed.query
        if path != "/" and path.endswith("/"):
            path = path[:-1]

    normalized_query = ""
    if query:
        normalized_pairs: list[tuple[str, str]] = []
        has_pagination_key = False
        for key, value in parse_qsl(query, keep_blank_values=False):
            key_norm = str(key).strip().lower()
            value_norm = str(value).strip()
            if not key_norm or not value_norm:
                normalized_pairs = []
                break
            if key_norm in {
                "page",
                "paged",
                "p",
                "pg",
                "page_no",
                "pagenumber",
                "offset",
                "start",
                "stranica",
                "pagina",
            }:
                has_pagination_key = True
            elif key_norm not in {
                "limit",
                "per_page",
                "page_size",
                "items_per_page",
                "count",
            }:
                normalized_pairs = []
                break
            if not re.fullmatch(r"\d{1,6}", value_norm):
                normalized_pairs = []
                break
            normalized_pairs.append((key_norm, str(int(value_norm))))

        if normalized_pairs and has_pagination_key:
            normalized_pairs.sort()
            normalized_query = urlencode(normalized_pairs, doseq=True)

    return (
        urlunparse((scheme.lower(), netloc, path, "", normalized_query, ""))
        if netloc
        else path
    )


def token_set(page: dict[str, Any]) -> set[str]:
    """Build token set from top terms or tokens."""
    if page.get("top_terms"):
        return {
            str(item.get("term", "")).lower()
            for item in page["top_terms"]
            if item.get("term")
        }
    return {str(t).lower() for t in page.get("tokens", [])}


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return inter / union


def classify_severity(ratio: float, critical: float, high: float, medium: float) -> str:
    """Classify by ratio."""
    if ratio >= critical:
        return "Critical"
    if ratio >= high:
        return "High"
    if ratio >= medium:
        return "Medium"
    return "Low"


def classify_confidence(
    has_external: bool, has_visual: bool, base: str = "Medium"
) -> str:
    """Adjust confidence by data richness."""
    if has_external and has_visual:
        if base == "Low":
            return "Medium"
        return "High"
    if has_external or has_visual:
        return base
    if base == "High":
        return "Medium"
    return base


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _tokenize_text(value: str) -> list[str]:
    return [
        token.lower()
        for token in re.findall(
            r"[a-z0-9а-яёіїєґ]{2,}",
            value or "",
            flags=re.IGNORECASE,
        )
    ]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _simhash64(weighted_tokens: list[tuple[str, float]]) -> int:
    if not weighted_tokens:
        return 0
    vector = [0.0] * 64
    for token, weight in weighted_tokens:
        digest = hashlib.md5(token.encode("utf-8")).digest()
        token_hash = int.from_bytes(digest[:8], "big")
        for bit in range(64):
            if token_hash & (1 << bit):
                vector[bit] += weight
            else:
                vector[bit] -= weight
    fingerprint = 0
    for bit, value in enumerate(vector):
        if value > 0:
            fingerprint |= 1 << bit
    return fingerprint


def _internal_pagerank(
    edges: list[tuple[str, str]], iters: int = 20, damping: float = 0.85
) -> dict[str, float]:
    nodes = sorted({src for src, _ in edges} | {dst for _, dst in edges})
    if not nodes:
        return {}
    node_count = len(nodes)
    outgoing: dict[str, int] = {node: 0 for node in nodes}
    for src, _ in edges:
        outgoing[src] += 1

    rank = {node: 1.0 / node_count for node in nodes}
    for _ in range(max(1, iters)):
        next_rank = {node: (1.0 - damping) / node_count for node in nodes}
        dangling_mass = sum(rank[node] for node in nodes if outgoing[node] == 0)
        if dangling_mass:
            share = damping * dangling_mass / node_count
            for node in nodes:
                next_rank[node] += share
        for src, dst in edges:
            out_degree = outgoing.get(src, 0)
            if out_degree <= 0:
                continue
            next_rank[dst] += damping * rank[src] / out_degree
        rank = next_rank
    return rank


def _position_bucket(position: float) -> str:
    if position <= 2:
        return "1-2"
    if position <= 5:
        return "3-5"
    if position <= 10:
        return "6-10"
    if position <= 20:
        return "11-20"
    return "21+"


def _compute_coec_proxies(
    by_url_date: dict[str, dict[str, dict[str, float]]],
) -> tuple[dict[str, float], list[dict[str, Any]], float]:
    rows: list[dict[str, float | str]] = []
    for url, date_map in by_url_date.items():
        for date, values in date_map.items():
            impressions = _safe_float(values.get("impressions"))
            clicks = _safe_float(values.get("clicks"))
            position = _safe_float(values.get("position"))
            if impressions <= 0:
                continue
            rows.append(
                {
                    "url": url,
                    "date": date,
                    "clicks": clicks,
                    "impressions": impressions,
                    "position": max(1.0, position),
                }
            )

    if not rows:
        return {}, [], 0.0

    ctr_by_bucket: dict[str, dict[str, float]] = defaultdict(
        lambda: {"clicks": 0.0, "impressions": 0.0}
    )
    total_clicks = 0.0
    total_impressions = 0.0
    for row in rows:
        bucket = _position_bucket(_safe_float(row.get("position")))
        ctr_by_bucket[bucket]["clicks"] += _safe_float(row.get("clicks"))
        ctr_by_bucket[bucket]["impressions"] += _safe_float(row.get("impressions"))
        total_clicks += _safe_float(row.get("clicks"))
        total_impressions += _safe_float(row.get("impressions"))

    default_ctr = (total_clicks / total_impressions) if total_impressions > 0 else 0.0
    expected_ctr_curve: dict[str, float] = {}
    for bucket_name, values in ctr_by_bucket.items():
        impressions = values["impressions"]
        expected_ctr_curve[bucket_name] = (
            values["clicks"] / impressions if impressions > 0 else default_ctr
        )
    for bucket_name in ("1-2", "3-5", "6-10", "11-20", "21+"):
        expected_ctr_curve.setdefault(bucket_name, default_ctr)

    by_url: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "clicks": 0.0,
            "expected_clicks": 0.0,
            "impressions": 0.0,
            "positions": [],
        }
    )
    for row in rows:
        url = str(row.get("url", ""))
        bucket_name = _position_bucket(_safe_float(row.get("position")))
        expected_ctr = expected_ctr_curve.get(bucket_name, default_ctr)
        impressions = _safe_float(row.get("impressions"))
        clicks = _safe_float(row.get("clicks"))
        by_url[url]["clicks"] += clicks
        by_url[url]["impressions"] += impressions
        by_url[url]["expected_clicks"] += impressions * expected_ctr
        by_url[url]["positions"].append(_safe_float(row.get("position")))

    coec_by_url: dict[str, float] = {}
    serp_demotion_pages: list[dict[str, Any]] = []
    for url, values in by_url.items():
        expected_clicks = max(1e-9, _safe_float(values.get("expected_clicks")))
        coec_value = max(0.0, min(3.0, _safe_float(values.get("clicks")) / expected_clicks))
        coec_by_url[url] = round(coec_value, 3)
        position_values = [float(v) for v in values.get("positions", [])]
        volatility = (
            max(position_values) - min(position_values) if len(position_values) > 1 else 0.0
        )
        if coec_value < 0.75 and _safe_float(values.get("impressions")) >= 100:
            serp_demotion_pages.append(
                {
                    "url": url,
                    "coec": round(coec_value, 3),
                    "impressions": round(_safe_float(values.get("impressions")), 1),
                    "position_volatility": round(volatility, 3),
                }
            )

    serp_demotion_pages.sort(
        key=lambda item: (item.get("coec", 1.0), -item.get("impressions", 0.0))
    )
    site_coec_median = round(median(coec_by_url.values()), 3) if coec_by_url else 0.0
    return coec_by_url, serp_demotion_pages[:30], site_coec_median


METRIC_REGISTRY: dict[str, dict[str, Any]] = {
    "siteRadius": {
        "proxy_key": "siteRadius_proxy",
        "proxy_formula": "off_topic_ratio from centroid overlap dispersion",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_01_topical_dilution"],
    },
    "siteFocusScore": {
        "proxy_key": "siteFocusScore_proxy",
        "proxy_formula": "1 - off_topic_ratio",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_01_topical_dilution"],
    },
    "site2vecEmbeddingEncoded": {
        "proxy_key": "site2vecEmbeddingEncoded_proxy",
        "proxy_formula": "SimHash64 fingerprint of site-wide top-term distribution (no embedder model)",
        "data": ["crawl"],
        "confidence": "Low",
        "used_in": ["check_01_topical_dilution"],
    },
    "contentEffort": {
        "proxy_key": "contentEffort_proxy_avg",
        "proxy_formula": "length + structure + citations + media + answer-first weighted score",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_02_low_effort_originality"],
    },
    "docImages": {
        "proxy_key": "docImages_proxy",
        "proxy_formula": "blend of pages_with_images_ratio + avg_images_per_page (+ alt coverage if available)",
        "data": ["crawl"],
        "confidence": "Low",
        "used_in": ["check_02_low_effort_originality"],
    },
    "OriginalContentScore": {
        "proxy_key": "originalContentScore_proxy",
        "proxy_formula": "1 - duplicateRisk_proxy",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_02_low_effort_originality", "check_09_lexical_cannibalization"],
    },
    "goodClicks": {
        "proxy_key": "goodClicks_proxy",
        "proxy_formula": "engaged session blend from GA4 engagement and dwell time",
        "data": ["ga4_pages"],
        "confidence": "High",
        "used_in": ["check_03_intent_click_mismatch"],
    },
    "badClicks": {
        "proxy_key": "badClicks_proxy",
        "proxy_formula": "1 - goodClicks_proxy",
        "data": ["ga4_pages"],
        "confidence": "High",
        "used_in": ["check_03_intent_click_mismatch"],
    },
    "lastLongestClicks": {
        "proxy_key": "lastLongestClicks_proxy",
        "proxy_formula": "avg engagement time normalized to 180 seconds",
        "data": ["ga4_pages"],
        "confidence": "High",
        "used_in": ["check_03_intent_click_mismatch"],
    },
    "navDemotion": {
        "proxy_key": "navDemotion_proxy",
        "proxy_formula": "weighted blend of answer-first misses + UI/mobile friction + title rewrite risk (+ GA4/GSC when available)",
        "data": ["crawl"],
        "confidence": "Low",
        "used_in": ["check_03_intent_click_mismatch", "navboost_panel"],
    },
    "clutterScore": {
        "proxy_key": "clutterScore_proxy",
        "proxy_formula": "ui_risk_ratio from overlays/sticky/fixed heuristics",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_04_ui_penalty_smearing"],
    },
    "isSmearedSignal": {
        "proxy_key": "uiSmearing_proxy",
        "proxy_formula": "template-level spread of UI risks",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_04_ui_penalty_smearing"],
    },
    "authorReputationScore": {
        "proxy_key": "authorEntityCoverage_proxy",
        "proxy_formula": "author schema presence + author hub + sameAs links",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_05_broken_author_entity_graph"],
    },
    "isAuthor": {
        "proxy_key": "authorEntityCoverage_proxy",
        "proxy_formula": "share of long-form pages with author entity signals",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_05_broken_author_entity_graph"],
    },
    "sameAs": {
        "proxy_key": "sameAs_links_total_proxy",
        "proxy_formula": "aggregate sameAs links extracted from Person schema",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_05_broken_author_entity_graph"],
    },
    "anchorMismatchDemotion": {
        "proxy_key": "anchorConsistency_proxy",
        "proxy_formula": "1 - mismatch_target_ratio from anchor-target term overlap",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_08_anchor_inconsistency"],
    },
    "shingleInfo": {
        "proxy_key": "duplicateRisk_proxy",
        "proxy_formula": "near-duplicate ratio based on token jaccard pairs",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_09_lexical_cannibalization"],
    },
    "pandaDemotion": {
        "proxy_key": "duplicateRisk_proxy",
        "proxy_formula": "duplicate and low-effort content blend",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_02_low_effort_originality", "check_09_lexical_cannibalization"],
    },
    "babyPandaDemotion": {
        "proxy_key": "babyPandaDemotion_proxy",
        "proxy_formula": "0.65*duplicateRisk_proxy + 0.35*(1-contentEffort_proxy_avg) (higher=worse)",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_02_low_effort_originality", "check_09_lexical_cannibalization"],
    },
    "isSmartphoneOptimized": {
        "proxy_key": "smartphoneOptimized_proxy",
        "proxy_formula": "1 - mobileRisk_proxy",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_10_mobile_experience_failure"],
    },
    "mobileCwv": {
        "proxy_key": "mobileRisk_proxy",
        "proxy_formula": "mobile UI risk (horizontal scroll, overlays, heavy JS)",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_10_mobile_experience_failure"],
    },
    "onsiteProminence": {
        "proxy_key": "onsiteProminence_proxy",
        "proxy_formula": "internal prominence from depth and inlink distribution",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_12_conversion_hubs_isolated"],
    },
    "homepagePagerankNs": {
        "proxy_key": "internalPageRank_proxy",
        "proxy_formula": "max internal PageRank from link graph",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_12_conversion_hubs_isolated"],
    },
    "syntacticDate": {
        "proxy_key": "syntacticDate_proxy",
        "proxy_formula": "ratio of pages using freshness/date syntax markers",
        "data": ["crawl"],
        "confidence": "Low",
        "used_in": ["check_07_syntactic_semantic_date_mismatch"],
    },
    "semanticDateInfo": {
        "proxy_key": "semanticDateInfo_proxy",
        "proxy_formula": "current-year factual references ratio",
        "data": ["crawl"],
        "confidence": "Low",
        "used_in": ["check_07_syntactic_semantic_date_mismatch"],
    },
    "lastSignificantUpdate": {
        "proxy_key": "freshnessIntegrity_proxy",
        "proxy_formula": "1 - freshness_mismatch_ratio",
        "data": ["crawl"],
        "confidence": "Low",
        "used_in": ["check_07_syntactic_semantic_date_mismatch"],
    },
    "PageRank": {
        "proxy_key": "internalPageRank_proxy",
        "proxy_formula": "iterative internal link-graph PageRank max score",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["authority_graph_panel"],
    },
    "PageRankPerDocData": {
        "proxy_key": "internalPageRank_proxy",
        "proxy_formula": "document-level normalized internal PageRank",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["authority_graph_panel"],
    },
    "anchorStats": {
        "proxy_key": "anchorStats_proxy",
        "proxy_formula": "unique anchors + total internal links",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["authority_graph_panel", "check_08_anchor_inconsistency"],
    },
    "perDocData": {
        "proxy_key": "internalPageRank_proxy",
        "proxy_formula": "per-document authority estimate from graph",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["authority_graph_panel"],
    },
    "iPullRank": {
        "proxy_key": "iPullRank_proxy",
        "proxy_formula": "mean internal PageRank score",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["authority_graph_panel"],
    },
    "NSR": {
        "proxy_key": "NSR_proxy",
        "proxy_formula": "1 - weighted severity penalties / 12 checks",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["summary", "growth_actions"],
    },
    "predictedDefaultNsr": {
        "proxy_key": "predictedDefaultNsr_proxy",
        "proxy_formula": "fallback equals NSR_proxy without external authority blend",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["summary"],
    },
    "nsrDataProto": {
        "proxy_key": "NSR_proxy",
        "proxy_formula": "check-level severity and evidence aggregate",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["summary"],
    },
    "lowQuality": {
        "proxy_key": "lowQuality_proxy",
        "proxy_formula": "1 - NSR_proxy",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["summary"],
    },
    "siteAuthority": {
        "proxy_key": "siteAuthority_proxy",
        "proxy_formula": "(internalPageRank_proxy + NSR_proxy) / 2",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["summary", "growth_actions"],
    },
    "COEC": {
        "proxy_key": "COEC_proxy_site_median",
        "proxy_formula": "actual clicks / expected clicks by position CTR curve",
        "data": ["gsc_timeseries"],
        "confidence": "High",
        "used_in": ["check_03_intent_click_mismatch", "navboost_panel"],
    },
    "serpDemotion": {
        "proxy_key": "serpDemotion_proxy_count",
        "proxy_formula": "count of URLs with low COEC and sufficient impressions",
        "data": ["gsc_timeseries"],
        "confidence": "High",
        "used_in": ["navboost_panel"],
    },
    "scrollDepth": {
        "proxy_key": "scrollDepth_proxy",
        "proxy_formula": "GA4 scroll_events/users median",
        "data": ["ga4_scroll"],
        "confidence": "High",
        "used_in": ["navboost_panel", "check_03_intent_click_mismatch"],
    },
    "directUrlVisits": {
        "proxy_key": "directUrlVisits_proxy",
        "proxy_formula": "GA4 direct_sessions/sessions median",
        "data": ["ga4_traffic"],
        "confidence": "High",
        "used_in": ["navboost_panel", "check_03_intent_click_mismatch"],
    },
    "Goldmine": {
        "proxy_key": "titleRewriteRisk_proxy",
        "proxy_formula": "title mismatch, duplication, and overlap risk blend",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_03_intent_click_mismatch"],
    },
    "AlternativeTitlesAnnotator": {
        "proxy_key": "title_h1_intro_overlap_proxy",
        "proxy_formula": "title token overlap with h1 and intro",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_03_intent_click_mismatch"],
    },
    "titlematchScore": {
        "proxy_key": "titlematchScore_proxy",
        "proxy_formula": "title token overlap with h1 + intro (higher=better)",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_03_intent_click_mismatch"],
    },
    "dupTokens": {
        "proxy_key": "dupTokens_proxy",
        "proxy_formula": "ratio of pages with duplicated title token patterns",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_03_intent_click_mismatch"],
    },
    "goldmineBlockbertFactor": {
        "proxy_key": "goldmineBlockbertFactor_proxy",
        "proxy_formula": "combined title rewrite-risk factor",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["check_03_intent_click_mismatch"],
    },
    "violatesMobileInterstitialPolicy": {
        "proxy_key": "violatesMobileInterstitialPolicy_proxy",
        "proxy_formula": "ratio of pages with interstitial-policy violations",
        "data": ["crawl"],
        "confidence": "High",
        "used_in": ["check_04_ui_penalty_smearing", "check_10_mobile_experience_failure"],
    },
    "ugcDiscussionEffortScore": {
        "proxy_key": "ugcDiscussionEffortScore_proxy",
        "proxy_formula": "discussion depth and unique author participation score",
        "data": ["crawl"],
        "confidence": "Medium",
        "used_in": ["extended_ugc_check"],
    },
    "productReviewPUhqPage": {
        "proxy_key": "productReviewPUhqPage_proxy",
        "proxy_formula": "share of review pages passing high-quality thresholds",
        "data": ["crawl"],
        "confidence": "Low",
        "used_in": ["summary"],
    },
    "hostAge": {
        "proxy_key": "hostAge_proxy_years",
        "proxy_formula": "domain age in years from RDAP registration event",
        "data": ["rdap_whois"],
        "confidence": "Low",
        "used_in": [],
    },
    "unsquashedClicks": {
        "status": "unavailable",
        "proxy_formula": "raw click log signal unavailable without proprietary logs",
        "data": ["google_internal_logs"],
        "confidence": "Low",
        "used_in": [],
    },
    "chromeInTotal": {
        "status": "unavailable",
        "proxy_formula": "true Chrome telemetry totals unavailable",
        "data": ["chrome_telemetry"],
        "confidence": "Low",
        "used_in": [],
    },
    "authorObfuscatedGaiaStr": {
        "status": "unavailable",
        "proxy_formula": "obfuscated author Gaia IDs unavailable",
        "data": ["kg_internal_ids"],
        "confidence": "Low",
        "used_in": [],
    },
}


def _build_metric_coverage(
    proxy_metrics: dict[str, Any],
    data_sources: dict[str, bool],
) -> dict[str, dict[str, Any]]:
    coverage: dict[str, dict[str, Any]] = {}
    for metric_name, spec in METRIC_REGISTRY.items():
        required_data = spec.get("data", [])
        if spec.get("status") == "unavailable":
            status = "unavailable"
        elif required_data and any(not data_sources.get(key, False) for key in required_data):
            status = "missing-data"
        elif spec.get("proxy_key") and spec["proxy_key"] in proxy_metrics:
            status = "implemented"
        else:
            status = "missing-data"

        item: dict[str, Any] = {
            "status": status,
            "proxy_formula": spec.get("proxy_formula", ""),
            "data": required_data,
            "confidence": spec.get("confidence", "Medium"),
            "used_in": spec.get("used_in", []),
        }
        proxy_key = spec.get("proxy_key")
        if proxy_key:
            item["proxy_key"] = proxy_key
            if proxy_key in proxy_metrics:
                item["proxy_value"] = proxy_metrics.get(proxy_key)
        if status == "missing-data" and required_data:
            missing = [key for key in required_data if not data_sources.get(key, False)]
            if missing:
                item["data_required"] = missing
        coverage[metric_name] = item
    return coverage


def _first_path_segment(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return "/"
    return path.split("/")[0]


def _highest_severity(severities: list[str]) -> str:
    rank = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
    best = "Low"
    best_rank = 1
    for severity in severities:
        if rank.get(severity, 1) > best_rank:
            best = severity
            best_rank = rank.get(severity, 1)
    return best


def _severity_to_score(severity: str) -> int:
    return {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}.get(severity, 1)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL rows."""
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _detect_navboost_risk(
    pages: list[dict[str, Any]],
    gsc_by_url: dict[str, dict[str, float]],
    ga4_by_url: dict[str, dict[str, float]],
    coec_by_url: dict[str, float] | None = None,
    ga4_traffic_by_url: dict[str, dict[str, float]] | None = None,
    ga4_scroll_by_url: dict[str, dict[str, float]] | None = None,
    title_rewrite_risk_by_url: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    coec_by_url = coec_by_url or {}
    ga4_traffic_by_url = ga4_traffic_by_url or {}
    ga4_scroll_by_url = ga4_scroll_by_url or {}
    title_rewrite_risk_by_url = title_rewrite_risk_by_url or {}

    ctr_values = [
        v.get("ctr", 0.0)
        for v in gsc_by_url.values()
        if _safe_float(v.get("impressions")) > 0
    ]
    engagement_values = [
        v.get("engagement_rate", 0.0)
        for v in ga4_by_url.values()
        if _safe_float(v.get("views")) > 0
    ]
    scroll_values = [
        _safe_float(v.get("scroll_depth_proxy"))
        for v in ga4_scroll_by_url.values()
        if _safe_float(v.get("users")) > 0
    ]
    direct_share_values = [
        _safe_float(v.get("direct_share"))
        for v in ga4_traffic_by_url.values()
        if _safe_float(v.get("sessions")) > 0
    ]
    ctr_med = median(ctr_values) if ctr_values else 0.0
    engagement_med = median(engagement_values) if engagement_values else 0.0
    scroll_med = median(scroll_values) if scroll_values else 0.0
    direct_share_med = median(direct_share_values) if direct_share_values else 0.0

    risks: list[dict[str, Any]] = []
    for page in pages:
        url = normalize_url(page.get("url", ""))
        reasons: list[str] = []
        score = 0
        if page.get("clickbait_title") and not page.get("answer_first", {}).get(
            "has_direct_answer", False
        ):
            reasons.append("clickbait_title_without_answer_first")
            score += 2

        gsc = gsc_by_url.get(url, {})
        ga4 = ga4_by_url.get(url, {})
        ctr = _safe_float(gsc.get("ctr"))
        impressions = _safe_float(gsc.get("impressions"))
        engagement = _safe_float(ga4.get("engagement_rate"))
        avg_eng_time = _safe_float(ga4.get("avg_engagement_time"))
        has_ga4_engagement = bool(ga4) and (
            _safe_float(ga4.get("views")) > 0
            or _safe_float(ga4.get("sessions")) > 0
            or engagement > 0
            or avg_eng_time > 0
        )
        low_engagement = has_ga4_engagement and (
            (engagement_med and engagement < engagement_med * 0.8)
            or (avg_eng_time > 0 and avg_eng_time < 35)
        )
        if (
            impressions >= 100
            and ctr_med
            and ctr >= ctr_med
            and low_engagement
        ):
            reasons.append("high_ctr_low_engagement")
            score += 3

        scroll_data = ga4_scroll_by_url.get(url, {})
        scroll_depth = _safe_float(scroll_data.get("scroll_depth_proxy"))
        if (
            impressions >= 80
            and ctr_med
            and ctr >= ctr_med
            and scroll_med
            and scroll_depth < scroll_med * 0.75
        ):
            reasons.append("high_ctr_low_scroll_depth")
            score += 2

        traffic_data = ga4_traffic_by_url.get(url, {})
        direct_share = _safe_float(traffic_data.get("direct_share"))
        if (
            direct_share >= max(0.55, direct_share_med)
            and low_engagement
        ):
            reasons.append("high_direct_low_engagement")
            score += 2

        if url in coec_by_url and _safe_float(coec_by_url.get(url)) < 0.75 and impressions >= 100:
            reasons.append("coec_below_expected")
            score += 3

        title_risk = _safe_float(title_rewrite_risk_by_url.get(url))
        if title_risk >= 0.65:
            reasons.append("title_snippet_rewrite_risk")
            score += 2

        if reasons:
            risks.append({"url": url, "score": score, "reasons": reasons})

    risks.sort(key=lambda item: item["score"], reverse=True)
    return risks


def analyze_site(
    crawl_rows: list[dict[str, Any]],
    external_data: dict[str, Any] | None = None,
    visual_data: dict[str, Any] | None = None,
    include_noindex: bool = False,
) -> dict[str, Any]:
    """Compute proxy metrics, 12 checks, and 7 growth actions."""
    external_data = external_data or {}
    visual_data = visual_data or {}

    gsc_by_url = (
        external_data.get("gsc", {}).get("by_url", {})
        if isinstance(external_data.get("gsc"), dict)
        else {}
    )
    ga4_by_url = (
        external_data.get("ga4", {}).get("by_url", {})
        if isinstance(external_data.get("ga4"), dict)
        else {}
    )
    gsc_timeseries_by_url_date = (
        external_data.get("gsc_timeseries", {}).get("by_url_date", {})
        if isinstance(external_data.get("gsc_timeseries"), dict)
        else {}
    )
    ga4_traffic_by_url = (
        external_data.get("ga4_traffic", {}).get("by_url", {})
        if isinstance(external_data.get("ga4_traffic"), dict)
        else {}
    )
    ga4_scroll_by_url = (
        external_data.get("ga4_scroll", {}).get("by_url", {})
        if isinstance(external_data.get("ga4_scroll"), dict)
        else {}
    )
    rdap_profile = (
        external_data.get("rdap_whois", {})
        if isinstance(external_data.get("rdap_whois"), dict)
        else {}
    )
    has_rdap = bool(
        rdap_profile.get("registration_date")
        and rdap_profile.get("domain_age_years") is not None
    )
    has_visual = bool(visual_data.get("enabled"))
    has_external = bool(
        gsc_by_url
        or ga4_by_url
        or gsc_timeseries_by_url_date
        or ga4_traffic_by_url
        or ga4_scroll_by_url
        or has_rdap
    )
    data_sources: dict[str, bool] = {
        "crawl": bool(crawl_rows),
        "playwright": has_visual,
        "gsc_pages": bool(gsc_by_url),
        "gsc_queries": bool(
            isinstance(external_data.get("gsc_queries"), dict)
            and external_data.get("gsc_queries", {}).get("rows")
        ),
        "ga4_pages": bool(ga4_by_url),
        "gsc_timeseries": bool(gsc_timeseries_by_url_date),
        "ga4_traffic": bool(ga4_traffic_by_url),
        "ga4_scroll": bool(ga4_scroll_by_url),
        "rdap_whois": has_rdap,
    }

    all_ok_pages = [
        row
        for row in crawl_rows
        if row.get("status", 0) and int(row["status"]) < 400 and row.get("word_count")
    ]
    noindex_pages_list = [row for row in all_ok_pages if row.get("is_noindex", False)]
    if include_noindex:
        pages = all_ok_pages
    else:
        pages = [row for row in all_ok_pages if not row.get("is_noindex", False)]
    page_count = len(pages)

    noindex_report = [
        {
            "url": normalize_url(row.get("url", "")),
            "title": row.get("title", ""),
            "robots": row.get("robots", ""),
            "word_count": row.get("word_count", 0),
        }
        for row in noindex_pages_list
    ]

    url_alias_rows: list[dict[str, Any]] = []
    alias_total = 0
    alias_from_sitemap = 0
    for row in all_ok_pages:
        canonical_url = str(row.get("url") or "").strip()
        aliases = row.get("aliases") if isinstance(row.get("aliases"), list) else []
        if not canonical_url or not aliases:
            continue
        alias_total += len(aliases)
        alias_sources = (
            row.get("alias_sources") if isinstance(row.get("alias_sources"), dict) else {}
        )
        sitemap_alias_count = sum(
            1 for alias in aliases if alias_sources.get(alias) == "sitemap"
        )
        alias_from_sitemap += sitemap_alias_count
        url_alias_rows.append(
            {
                "canonical_url": canonical_url,
                "alias_count": len(aliases),
                "sitemap_alias_count": sitemap_alias_count,
                "examples": [str(alias) for alias in aliases[:3]],
            }
        )
    url_alias_rows.sort(key=lambda item: item.get("alias_count", 0), reverse=True)
    url_aliases = {
        "total_aliases": alias_total,
        "sitemap_aliases": alias_from_sitemap,
        "canonical_pages_with_aliases": len(url_alias_rows),
        "top": url_alias_rows[:15],
    }

    if page_count == 0:
        proxy_metrics: dict[str, Any] = {}
        metric_coverage = _build_metric_coverage(proxy_metrics, data_sources)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "pages_crawled": len(crawl_rows),
                "pages_analyzed": 0,
                "checks_with_issues": 0,
                "noindex_page_count": len(noindex_pages_list),
                "include_noindex_in_analysis": include_noindex,
            },
            "proxy_metrics": proxy_metrics,
            "data_sources": data_sources,
            "metric_coverage": metric_coverage,
            "checks": [],
            "growth_actions": [],
            "navboost_risk_pages": [],
            "noindex_pages": noindex_report,
            "url_aliases": url_aliases,
            "serp_demotion_pages": [],
            "title_rewrite_risk_pages": [],
        }
    visual_by_url = {
        normalize_url(item.get("url", "")): item
        for item in visual_data.get("results", [])
        if isinstance(item, dict) and item.get("url")
    }
    current_year = datetime.now().year

    checks: list[dict[str, Any]] = []

    centroid_counter: Counter[str] = Counter()
    page_terms_map: dict[str, set[str]] = {}
    inlinks: dict[str, int] = defaultdict(int)
    internal_links: list[tuple[str, str, str]] = []
    for page in pages:
        url = normalize_url(page.get("url", ""))
        terms = token_set(page)
        page_terms_map[url] = terms
        centroid_counter.update(terms)
        for link in page.get("links", {}).get("internal", []):
            target = normalize_url(link.get("url", ""))
            anchor = str(link.get("anchor_text", "")).strip()
            if target:
                inlinks[target] += 1
                internal_links.append((url, target, anchor))

    site2vec_weighted_terms = [
        (term, math.log1p(count))
        for term, count in centroid_counter.most_common(256)
        if term
    ]
    site2vec_embedding_encoded_proxy = (
        f"{_simhash64(site2vec_weighted_terms):016x}"
        if site2vec_weighted_terms
        else ""
    )

    centroid = {term for term, _ in centroid_counter.most_common(60)}
    internal_edges = [(src, dst) for src, dst, _ in internal_links]
    internal_pagerank = _internal_pagerank(internal_edges)
    anchor_counter_global: Counter[str] = Counter()
    for _, _, anchor in internal_links:
        clean_anchor = re.sub(r"\s+", " ", anchor or "").strip().lower()
        if clean_anchor:
            anchor_counter_global.update([clean_anchor])

    title_signature_counter: Counter[str] = Counter()
    title_signature_by_url: dict[str, str] = {}
    title_overlap_by_url: dict[str, float] = {}
    for page in pages:
        url = normalize_url(page.get("url", ""))
        title_tokens = set(_tokenize_text(str(page.get("title", ""))))
        signature = " ".join(sorted(title_tokens)[:10]) if title_tokens else ""
        if signature:
            title_signature_counter.update([signature])
        title_signature_by_url[url] = signature

        h1_text = " ".join(page.get("headings", {}).get("h1", [])[:1])
        intro_text = str(page.get("intro_text") or page.get("text_excerpt", ""))[:320]
        semantic_tokens = set(_tokenize_text(f"{h1_text} {intro_text}"))
        overlap = (
            len(title_tokens & semantic_tokens) / max(1, len(title_tokens))
            if title_tokens
            else 0.0
        )
        title_overlap_by_url[url] = overlap

    duplicated_title_urls = [
        url
        for url, signature in title_signature_by_url.items()
        if signature and title_signature_counter.get(signature, 0) > 1
    ]
    title_rewrite_risk_by_url: dict[str, float] = {}
    title_rewrite_risk_pages: list[str] = []
    for page in pages:
        url = normalize_url(page.get("url", ""))
        overlap = title_overlap_by_url.get(url, 0.0)
        duplicate_penalty = 1.0 if url in duplicated_title_urls else 0.0
        clickbait_penalty = 1.0 if page.get("clickbait_title") else 0.0
        no_answer_penalty = (
            0.0
            if page.get("answer_first", {}).get("has_direct_answer", False)
            else 1.0
        )
        risk = min(
            1.0,
            (0.45 * (1.0 - overlap))
            + (0.25 * duplicate_penalty)
            + (0.2 * clickbait_penalty)
            + (0.1 * no_answer_penalty),
        )
        title_rewrite_risk_by_url[url] = round(risk, 3)
        if risk >= 0.65:
            title_rewrite_risk_pages.append(url)

    coec_by_url, serp_demotion_pages, coec_site_median = _compute_coec_proxies(
        gsc_timeseries_by_url_date
    )

    ugc_scores: list[float] = []
    ugc_low_effort_urls: list[str] = []
    for page in pages:
        url = normalize_url(page.get("url", ""))
        ugc_data = (
            page.get("content_features", {}).get("ugc_discussion", {})
            if isinstance(page.get("content_features"), dict)
            else {}
        )
        comment_count = _safe_float(ugc_data.get("comment_count"))
        unique_authors = _safe_float(ugc_data.get("unique_comment_authors"))
        has_discussion = bool(ugc_data.get("has_ugc_discussion")) or comment_count > 0
        if not has_discussion:
            continue
        depth_score = min(1.0, comment_count / 20.0)
        author_score = min(1.0, unique_authors / 6.0)
        content_score = min(1.0, _safe_float(page.get("word_count")) / 800.0)
        ugc_effort = (0.5 * depth_score) + (0.35 * author_score) + (0.15 * content_score)
        ugc_scores.append(ugc_effort)
        if ugc_effort < 0.35:
            ugc_low_effort_urls.append(url)

    review_pattern = re.compile(r"(review|обзор|comparison|vs)", re.IGNORECASE)
    review_pages = 0
    high_quality_review_pages = 0
    for page in pages:
        url = normalize_url(page.get("url", ""))
        signature = f"{urlparse(url).path} {page.get('title', '')}"
        if not review_pattern.search(signature):
            continue
        review_pages += 1
        features = page.get("content_features", {})
        review_quality = (
            _safe_float(page.get("word_count")) >= 700
            and _safe_float(features.get("citation_count")) >= 2
            and (
                _safe_float(features.get("list_count"))
                + _safe_float(features.get("table_count"))
            )
            >= 1
            and bool(page.get("author", {}).get("has_person_schema"))
        )
        if review_quality:
            high_quality_review_pages += 1

    # Check 1: Topical dilution.
    off_topic_urls: list[str] = []
    topical_scores: list[float] = []
    for page in pages:
        url = normalize_url(page.get("url", ""))
        terms = page_terms_map.get(url, set())
        if not terms:
            continue
        overlap = len(terms & centroid) / max(1, len(terms))
        topical_scores.append(overlap)
        if overlap < 0.15:
            off_topic_urls.append(url)
    off_topic_ratio = len(off_topic_urls) / page_count
    checks.append(
        {
            "id": "check_01_topical_dilution",
            "title": "Topical dilution clusters",
            "stage": "Twiddlers",
            "proxy_metric": {
                "off_topic_ratio": round(off_topic_ratio, 3),
                "siteFocusScore_proxy": round(max(0.0, 1.0 - off_topic_ratio), 3),
                "mean_topical_overlap": round(
                    sum(topical_scores) / max(1, len(topical_scores)), 3
                ),
            },
            "evidence_urls": off_topic_urls[:20],
            "severity": classify_severity(
                off_topic_ratio, critical=0.45, high=0.25, medium=0.12
            ),
            "fix_steps": [
                "Prune/merge off-topic clusters and redirect thin outliers to topical hubs.",
                "Rebuild IA around 4-8 core topical pillars with clear internal hubs.",
                "Update title/h1/intro to reinforce target topical vectors.",
            ],
            "confidence": classify_confidence(has_external, has_visual, base="Medium"),
        }
    )

    # Check 2: Low effort / originality.
    low_effort: list[dict[str, Any]] = []
    effort_values: list[float] = []
    for page in pages:
        features = page.get("content_features", {})
        length_score = min(1.0, _safe_float(page.get("word_count")) / 900.0)
        structure_score = min(
            1.0,
            (
                _safe_float(features.get("list_count"))
                + _safe_float(features.get("table_count"))
            )
            / 4.0,
        )
        citations_score = min(1.0, _safe_float(features.get("citation_count")) / 6.0)
        media_score = min(1.0, _safe_float(features.get("image_count")) / 4.0)
        answer_score = (
            1.0 if page.get("answer_first", {}).get("has_direct_answer", False) else 0.0
        )
        templ_penalty = min(
            1.0, _safe_float(features.get("templated_phrase_hits")) / 3.0
        )
        effort = (
            (0.35 * length_score)
            + (0.2 * structure_score)
            + (0.2 * citations_score)
            + (0.15 * media_score)
            + (0.1 * answer_score)
        )
        effort = max(0.0, effort * (1 - 0.25 * templ_penalty))
        effort_values.append(effort)
        if effort < 0.4:
            low_effort.append(
                {
                    "url": normalize_url(page.get("url", "")),
                    "effort_score": round(effort, 3),
                }
            )
    low_effort_ratio = len(low_effort) / page_count
    checks.append(
        {
            "id": "check_02_low_effort_originality",
            "title": "Low effort / low originality",
            "stage": "Mustang",
            "proxy_metric": {
                "contentEffort_proxy_avg": round(
                    sum(effort_values) / max(1, len(effort_values)), 3
                ),
                "low_effort_ratio": round(low_effort_ratio, 3),
            },
            "evidence_urls": [item["url"] for item in low_effort[:20]],
            "severity": classify_severity(
                low_effort_ratio, critical=0.5, high=0.3, medium=0.15
            ),
            "fix_steps": [
                "Apply effort checklist: unique data points, tables/lists, expert citations, original visuals.",
                "Rewrite templated sections and add page-specific evidence blocks.",
                "Make above-fold answer explicit before long-form narrative.",
            ],
            "confidence": classify_confidence(has_external, has_visual, base="Medium"),
        }
    )

    # Check 3: Intent vs click mismatch.
    navboost_risk_pages = _detect_navboost_risk(
        pages,
        gsc_by_url=gsc_by_url,
        ga4_by_url=ga4_by_url,
        coec_by_url=coec_by_url,
        ga4_traffic_by_url=ga4_traffic_by_url,
        ga4_scroll_by_url=ga4_scroll_by_url,
        title_rewrite_risk_by_url=title_rewrite_risk_by_url,
    )
    mismatch_ratio = len(navboost_risk_pages) / page_count
    check_03_evidence = [item["url"] for item in navboost_risk_pages]
    for url in title_rewrite_risk_pages:
        if url not in check_03_evidence:
            check_03_evidence.append(url)
    checks.append(
        {
            "id": "check_03_intent_click_mismatch",
            "title": "Intent vs click patterns mismatch",
            "stage": "NavBoost",
            "proxy_metric": {
                "risk_ratio": round(mismatch_ratio, 3),
                "risk_pages": len(navboost_risk_pages),
                "coec_site_median": coec_site_median,
                "title_rewrite_risk_ratio": round(
                    len(title_rewrite_risk_pages) / max(1, page_count), 3
                ),
            },
            "evidence_urls": check_03_evidence[:20],
            "severity": classify_severity(
                mismatch_ratio, critical=0.4, high=0.22, medium=0.1
            ),
            "fix_steps": [
                "Align title promises with first-screen answers and intent-matched intros.",
                "Reduce clickbait modifiers and strengthen answer-first content blocks.",
                "Prioritize pages with high CTR + low engagement for rewrite.",
            ],
            "confidence": classify_confidence(
                has_external, has_visual, base="High" if has_external else "Medium"
            ),
        }
    )

    # Check 4: UI penalty smearing.
    ui_risk_urls: list[str] = []
    template_risk_counter: Counter[str] = Counter()
    if has_visual:
        for url, result in visual_by_url.items():
            if (
                result.get("overlay_detected")
                or result.get("horizontal_scroll")
                or result.get("violates_mobile_interstitial_policy_proxy")
            ):
                ui_risk_urls.append(url)
                template_risk_counter.update([_first_path_segment(url)])
    else:
        for page in pages:
            hints = page.get("ui_hints", {})
            score = _safe_float(hints.get("fixed_elements")) + _safe_float(
                hints.get("sticky_elements")
            )
            if (
                score >= 2
                and _safe_float(hints.get("overlay_keyword_hits")) >= 2
                or hints.get("interstitial_policy_risk")
            ):
                url = normalize_url(page.get("url", ""))
                ui_risk_urls.append(url)
                template_risk_counter.update([_first_path_segment(url)])
    ui_ratio = len(ui_risk_urls) / page_count
    checks.append(
        {
            "id": "check_04_ui_penalty_smearing",
            "title": "UI penalty smearing",
            "stage": "Twiddlers",
            "proxy_metric": {
                "ui_risk_ratio": round(ui_ratio, 3),
                "template_clusters": template_risk_counter.most_common(6),
                "playwright_enabled": has_visual,
            },
            "evidence_urls": ui_risk_urls[:20],
            "severity": classify_severity(
                ui_ratio, critical=0.5, high=0.28, medium=0.12
            ),
            "fix_steps": [
                "Remove or defer intrusive fixed/sticky overlays on mobile.",
                "Constrain promo/cookie banners to non-blocking viewport areas.",
                "Roll out template-level fixes first, then validate with mobile snapshots.",
            ],
            "confidence": "High" if has_visual else "Medium",
        }
    )

    # Check 5: Broken author graph.
    missing_author_urls: list[str] = []
    same_as_total = 0
    has_author_hub = False
    for page in pages:
        url = normalize_url(page.get("url", ""))
        author = page.get("author", {})
        if re.search(r"/author|/authors|/team", urlparse(url).path, re.IGNORECASE):
            has_author_hub = True
        same_as_total += len(author.get("same_as", []))
        if _safe_float(page.get("word_count")) >= 500 and (
            not author.get("has_person_schema") or not author.get("author_names")
        ):
            missing_author_urls.append(url)
    author_ratio = len(missing_author_urls) / page_count
    checks.append(
        {
            "id": "check_05_broken_author_entity_graph",
            "title": "Broken author entity graph",
            "stage": "Twiddlers",
            "proxy_metric": {
                "missing_author_ratio": round(author_ratio, 3),
                "site_has_author_hub": has_author_hub,
                "sameAs_links_total": same_as_total,
            },
            "evidence_urls": missing_author_urls[:20],
            "severity": classify_severity(
                author_ratio, critical=0.45, high=0.25, medium=0.12
            ),
            "fix_steps": [
                "Add Person schema with sameAs links to authoritative profiles.",
                "Create author hubs and link article bylines to canonical author pages.",
                "Standardize author entity IDs across schema blocks.",
            ],
            "confidence": classify_confidence(has_external, has_visual, base="Medium"),
        }
    )

    # Check 6: Toxic outgoing links.
    risky_outlinks: list[dict[str, Any]] = []
    risky_domain_re = re.compile(
        r"(forum|profile|comment|casino|bet|loan|adult|link|directory|spam|guestpost|promo)",
        re.IGNORECASE,
    )
    for page in pages:
        src_url = normalize_url(page.get("url", ""))
        for link in page.get("links", {}).get("external", []):
            target = link.get("url", "")
            rel = {str(rel_value).lower() for rel_value in link.get("rel", [])}
            domain = urlparse(target).netloc.lower()
            if not domain:
                continue
            dofollow = not bool(rel & {"nofollow", "sponsored", "ugc"})
            if dofollow and risky_domain_re.search(domain):
                risky_outlinks.append({"source_url": src_url, "target_url": target})
    toxic_ratio = len(risky_outlinks) / max(
        1, sum(len(page.get("links", {}).get("external", [])) for page in pages)
    )
    checks.append(
        {
            "id": "check_06_toxic_outgoing_neighborhood",
            "title": "Toxic outgoing link neighborhood",
            "stage": "Mustang",
            "proxy_metric": {
                "risky_outlinks": len(risky_outlinks),
                "toxic_outlink_ratio": round(toxic_ratio, 3),
            },
            "evidence_urls": [item["target_url"] for item in risky_outlinks[:20]],
            "severity": classify_severity(
                toxic_ratio, critical=0.25, high=0.12, medium=0.05
            ),
            "fix_steps": [
                "Audit outbound links and remove/replace low-trust destinations.",
                "Apply rel hygiene (`nofollow`, `sponsored`, `ugc`) where applicable.",
                "Monitor new outbound links in editorial QA.",
            ],
            "confidence": classify_confidence(has_external, has_visual, base="Medium"),
        }
    )

    # Check 7: Date mismatch.
    freshness_mismatch: list[str] = []
    syntactic_fresh_count = 0
    semantic_current_count = 0
    for page in pages:
        url = normalize_url(page.get("url", ""))
        title_meta = f"{page.get('title', '')} {page.get('meta_description', '')} {page.get('text_excerpt', '')}"
        syntactic_fresh = bool(
            re.search(
                r"(updated|обновлено|оновлено|last updated|update)",
                title_meta,
                re.IGNORECASE,
            )
        ) or bool(page.get("dates", {}).get("time_tags"))
        year_mentions = page.get("content_features", {}).get("year_mentions", []) or []
        has_current_facts = current_year in year_mentions
        if syntactic_fresh:
            syntactic_fresh_count += 1
        if has_current_facts:
            semantic_current_count += 1
        if (
            syntactic_fresh
            and not has_current_facts
            and _safe_float(page.get("word_count")) > 300
        ):
            freshness_mismatch.append(url)
    mismatch_fresh_ratio = len(freshness_mismatch) / page_count
    checks.append(
        {
            "id": "check_07_syntactic_semantic_date_mismatch",
            "title": "Syntactic vs semantic date mismatch",
            "stage": "Twiddlers",
            "proxy_metric": {
                "freshness_mismatch_ratio": round(mismatch_fresh_ratio, 3),
                "current_year": current_year,
            },
            "evidence_urls": freshness_mismatch[:20],
            "severity": classify_severity(
                mismatch_fresh_ratio, critical=0.4, high=0.2, medium=0.1
            ),
            "fix_steps": [
                "Replace cosmetic date updates with substantive content refreshes.",
                "Add current-year facts, benchmarks, and revision notes.",
                "Track meaningful section-level updates to trigger freshness signals.",
            ],
            "confidence": classify_confidence(has_external, has_visual, base="Low"),
        }
    )

    # Check 8: Anchor inconsistency.
    anchor_counter: Counter[str] = Counter()
    target_mismatch: Counter[str] = Counter()
    commercial_re = re.compile(
        r"(buy|price|cheap|order|service|quote|demo|trial|купить|цена|заказать|услуга)",
        re.IGNORECASE,
    )
    total_internal_links = len(internal_links)
    for _, target, anchor in internal_links:
        anchor_clean = re.sub(r"\s+", " ", anchor or "").strip().lower()
        if not anchor_clean:
            continue
        anchor_counter.update([anchor_clean])
        anchor_terms = {token for token in re.findall(r"[a-zа-я0-9]{2,}", anchor_clean)}
        target_terms = page_terms_map.get(target, set())
        overlap = len(anchor_terms & target_terms) / max(1, len(anchor_terms))
        if overlap < 0.2:
            target_mismatch.update([target])
    overused_commercial = [
        anchor
        for anchor, count in anchor_counter.items()
        if commercial_re.search(anchor)
        and count >= max(8, int(0.08 * max(1, total_internal_links)))
    ]
    anchor_mismatch_urls = [url for url, count in target_mismatch.items() if count >= 3]
    anchor_issue_ratio = len(anchor_mismatch_urls) / page_count if page_count else 0.0
    checks.append(
        {
            "id": "check_08_anchor_inconsistency",
            "title": "Anchor inconsistency / over-optimization",
            "stage": "Twiddlers",
            "proxy_metric": {
                "overused_commercial_anchors": overused_commercial[:12],
                "mismatch_target_count": len(anchor_mismatch_urls),
            },
            "evidence_urls": anchor_mismatch_urls[:20],
            "severity": classify_severity(
                anchor_issue_ratio, critical=0.4, high=0.22, medium=0.1
            ),
            "fix_steps": [
                "Diversify anchor text and avoid repeated exact-match commercial anchors.",
                "Ensure anchor context semantically matches destination page intent.",
                "Rebuild internal-link rules per template to distribute natural variants.",
            ],
            "confidence": classify_confidence(has_external, has_visual, base="Medium"),
        }
    )

    # Check 9: Lexical cannibalization.
    duplicate_pairs: list[tuple[str, str, float]] = []
    page_urls = [normalize_url(page.get("url", "")) for page in pages]
    for index, left_url in enumerate(page_urls):
        left_terms = page_terms_map.get(left_url, set())
        if len(left_terms) < 40:
            continue
        for right_index in range(index + 1, len(page_urls)):
            right_url = page_urls[right_index]
            right_terms = page_terms_map.get(right_url, set())
            if len(right_terms) < 40:
                continue
            similarity = jaccard(left_terms, right_terms)
            if similarity >= 0.82:
                duplicate_pairs.append((left_url, right_url, similarity))
    duplicate_urls = sorted({url for pair in duplicate_pairs for url in pair[:2]})
    duplicate_ratio = len(duplicate_urls) / page_count
    checks.append(
        {
            "id": "check_09_lexical_cannibalization",
            "title": "Lexical cannibalization / near-duplicates",
            "stage": "Mustang",
            "proxy_metric": {
                "duplicate_url_ratio": round(duplicate_ratio, 3),
                "duplicate_pairs": [
                    {"left": left, "right": right, "sim": round(sim, 3)}
                    for left, right, sim in duplicate_pairs[:20]
                ],
            },
            "evidence_urls": duplicate_urls[:20],
            "severity": classify_severity(
                duplicate_ratio, critical=0.45, high=0.25, medium=0.1
            ),
            "fix_steps": [
                "Consolidate duplicate clusters via merge/canonical/noindex strategy.",
                "Create unique regional/service evidence per landing page.",
                "Limit programmatic page generation without unique factual deltas.",
            ],
            "confidence": classify_confidence(has_external, has_visual, base="Medium"),
        }
    )

    # Check 10: Mobile experience failure.
    mobile_risk_urls: list[str] = []
    if has_visual:
        for url, result in visual_by_url.items():
            if (
                result.get("horizontal_scroll")
                or result.get("heavy_js")
                or result.get("overlay_detected")
                or result.get("violates_mobile_interstitial_policy_proxy")
            ):
                mobile_risk_urls.append(url)
    else:
        for page in pages:
            hints = page.get("ui_hints", {})
            has_many_overlays = (
                _safe_float(hints.get("fixed_elements"))
                + _safe_float(hints.get("sticky_elements"))
                >= 3
            )
            if (
                not page.get("viewport_present", False)
                or has_many_overlays
                or hints.get("interstitial_policy_risk")
            ):
                mobile_risk_urls.append(normalize_url(page.get("url", "")))
    mobile_ratio = len(mobile_risk_urls) / page_count
    checks.append(
        {
            "id": "check_10_mobile_experience_failure",
            "title": "Mobile experience failure",
            "stage": "NavBoost",
            "proxy_metric": {
                "mobile_risk_ratio": round(mobile_ratio, 3),
                "playwright_enabled": has_visual,
            },
            "evidence_urls": mobile_risk_urls[:20],
            "severity": classify_severity(
                mobile_ratio, critical=0.5, high=0.3, medium=0.12
            ),
            "fix_steps": [
                "Fix horizontal scroll and remove render-blocking assets above the fold.",
                "Reduce intrusive JS widgets on mobile templates.",
                "Re-test mobile layouts with a consistent viewport baseline.",
            ],
            "confidence": "High" if has_visual else "Medium",
        }
    )

    # Check 11: No passage indexing architecture.
    poor_passage_urls: list[str] = []
    for page in pages:
        features = page.get("content_features", {})
        headings_count = len(page.get("headings", {}).get("h2", [])) + len(
            page.get("headings", {}).get("h3", [])
        )
        low_extractability = (
            _safe_float(features.get("qa_blocks")) == 0
            and (
                _safe_float(features.get("list_count"))
                + _safe_float(features.get("table_count"))
            )
            < 2
        )
        if _safe_float(page.get("word_count")) >= 1000 and (
            headings_count < 3 or low_extractability
        ):
            poor_passage_urls.append(normalize_url(page.get("url", "")))
    passage_ratio = len(poor_passage_urls) / page_count
    checks.append(
        {
            "id": "check_11_no_passage_architecture",
            "title": "No Passage Indexing architecture",
            "stage": "Mustang",
            "proxy_metric": {
                "low_extractability_ratio": round(passage_ratio, 3),
            },
            "evidence_urls": poor_passage_urls[:20],
            "severity": classify_severity(
                passage_ratio, critical=0.5, high=0.3, medium=0.15
            ),
            "fix_steps": [
                "Split long walls of text into question heading -> direct answer -> evidence blocks.",
                "Increase extractable structures: lists, tables, concise factual chunks.",
                "Add schema for factual entities and Q/A sections where appropriate.",
            ],
            "confidence": classify_confidence(has_external, has_visual, base="Medium"),
        }
    )

    # Check 12: Conversion hubs isolated.
    money_re = re.compile(
        r"(pricing|price|product|service|quote|buy|shop|demo|trial|contact|заказ|купить|цена|услуг)",
        re.IGNORECASE,
    )
    isolated_money_urls: list[str] = []
    for page in pages:
        url = normalize_url(page.get("url", ""))
        signature = f"{urlparse(url).path} {page.get('title', '')}"
        if not money_re.search(signature):
            continue
        depth = int(page.get("depth", 0) or 0)
        links_in = inlinks.get(url, 0)
        if depth > 3 or links_in < 2:
            isolated_money_urls.append(url)
    total_money_pages = sum(
        1
        for page in pages
        if money_re.search(
            f"{urlparse(normalize_url(page.get('url', ''))).path} {page.get('title', '')}"
        )
    )
    isolated_ratio = len(isolated_money_urls) / max(1, total_money_pages)
    checks.append(
        {
            "id": "check_12_conversion_hubs_isolated",
            "title": "Conversion hubs isolated",
            "stage": "Twiddlers",
            "proxy_metric": {
                "isolated_money_ratio": round(isolated_ratio, 3),
                "isolated_money_count": len(isolated_money_urls),
            },
            "evidence_urls": isolated_money_urls[:20],
            "severity": classify_severity(
                isolated_ratio, critical=0.6, high=0.35, medium=0.15
            ),
            "fix_steps": [
                "Reduce click depth to money pages to <= 3 from homepage and hubs.",
                "Increase contextual inlinks from high-prominence pages.",
                "Add breadcrumb and hub/spoke linking for conversion paths.",
            ],
            "confidence": classify_confidence(has_external, has_visual, base="Medium"),
        }
    )

    interstitial_policy_urls: list[str] = []
    if has_visual:
        interstitial_policy_urls = [
            url
            for url, result in visual_by_url.items()
            if result.get("violates_mobile_interstitial_policy_proxy")
        ]
    else:
        interstitial_policy_urls = [
            normalize_url(page.get("url", ""))
            for page in pages
            if page.get("ui_hints", {}).get("interstitial_policy_risk")
        ]

    failed_checks = [
        check
        for check in checks
        if check["severity"] in {"Critical", "High", "Medium"}
        and check.get("evidence_urls")
    ]
    failed_by_id = {check["id"]: check for check in failed_checks}
    growth_catalog: dict[str, dict[str, Any]] = {
        "growth_01_navboost_pattern_engineering": {
            "title": "NavBoost pattern engineering",
            "linked_checks": [
                "check_03_intent_click_mismatch",
                "check_04_ui_penalty_smearing",
                "check_10_mobile_experience_failure",
                "check_11_no_passage_architecture",
            ],
            "tasks": [
                "Deploy answer-first above-fold blocks and reduce pogo triggers.",
                "Introduce interaction modules (TOC accordions, calculators, downloadable assets).",
            ],
        },
        "growth_02_entity_graph_syndication": {
            "title": "Entity graph syndication",
            "linked_checks": ["check_05_broken_author_entity_graph"],
            "tasks": [
                "Create/standardize author pages with Person schema and sameAs links.",
                "Backfill byline-entity linkage on all expert content templates.",
            ],
        },
        "growth_03_architectural_densification": {
            "title": "Architectural densification",
            "linked_checks": [
                "check_01_topical_dilution",
                "check_09_lexical_cannibalization",
            ],
            "tasks": [
                "Prune off-topic content and consolidate duplicate clusters.",
                "Rebuild topical hub architecture to reduce siteRadius.",
            ],
        },
        "growth_04_authority_canalization": {
            "title": "Authority canalization",
            "linked_checks": [
                "check_12_conversion_hubs_isolated",
                "check_08_anchor_inconsistency",
            ],
            "tasks": [
                "Route internal authority from hubs/homepage into priority money pages.",
                "Replace over-optimized anchors with semantically diverse contextual links.",
            ],
        },
        "growth_05_llm_content_defense": {
            "title": "LLM content defense",
            "linked_checks": [
                "check_02_low_effort_originality",
                "check_06_toxic_outgoing_neighborhood",
                "check_11_no_passage_architecture",
            ],
            "tasks": [
                "Adopt editorial QA with evidence density and original data minimums.",
                "Harden outbound link hygiene and factual reliability standards.",
            ],
        },
        "growth_06_managed_reactivation": {
            "title": "Managed reactivation",
            "linked_checks": ["check_07_syntactic_semantic_date_mismatch"],
            "tasks": [
                "Schedule cyclical updates with measurable section-level changes.",
                "Tie updates to current-year benchmarks and revised evidence.",
            ],
        },
        "growth_07_title_semantic_synchronization": {
            "title": "Title semantic synchronization",
            "linked_checks": [
                "check_03_intent_click_mismatch",
                "check_08_anchor_inconsistency",
            ],
            "tasks": [
                "Align title/h1/url/intro semantics for intent consistency.",
                "Remove title patterns that trigger rewrite or mismatch risk.",
            ],
        },
    }

    growth_actions: list[dict[str, Any]] = []
    for action_id, action in growth_catalog.items():
        linked = [
            check_id for check_id in action["linked_checks"] if check_id in failed_by_id
        ]
        if not linked:
            continue
        severities = [failed_by_id[check_id]["severity"] for check_id in linked]
        priority = _highest_severity(severities)
        score = sum(_severity_to_score(severity) for severity in severities) / max(
            1, len(severities)
        )
        growth_actions.append(
            {
                "id": action_id,
                "title": action["title"],
                "priority": priority,
                "priority_score": round(score, 2),
                "linked_checks": linked,
                "tasks": action["tasks"],
            }
        )
    growth_actions.sort(key=lambda item: (-item["priority_score"], item["title"]))

    max_internal_pr = round(max(internal_pagerank.values() or [0.0]), 6)
    mean_internal_pr = round(
        sum(internal_pagerank.values()) / max(1, len(internal_pagerank)), 6
    )
    title_overlap_avg = round(
        sum(title_overlap_by_url.values()) / max(1, len(title_overlap_by_url)), 3
    )
    dup_tokens_ratio = round(len(duplicated_title_urls) / max(1, page_count), 3)
    title_rewrite_risk_ratio = round(
        len(title_rewrite_risk_pages) / max(1, page_count), 3
    )
    goldmine_blockbert_factor = round(
        sum(title_rewrite_risk_by_url.values())
        / max(1, len(title_rewrite_risk_by_url)),
        3,
    )
    ugc_discussion_effort = round(sum(ugc_scores) / len(ugc_scores), 3) if ugc_scores else 1.0
    product_review_quality = (
        round(high_quality_review_pages / max(1, review_pages), 3) if review_pages else 0.0
    )

    images_total = 0
    pages_with_images = 0
    image_alt_coverages: list[float] = []
    for page in pages:
        features = page.get("content_features", {})
        image_count = int(_safe_float(features.get("image_count")))
        images_total += image_count
        if image_count > 0:
            pages_with_images += 1
        if "image_alt_coverage" in features:
            image_alt_coverages.append(_safe_float(features.get("image_alt_coverage")))

    pages_with_images_ratio = pages_with_images / max(1, page_count)
    avg_images_per_page = images_total / max(1, page_count)
    image_alt_coverage_avg = (
        sum(image_alt_coverages) / len(image_alt_coverages)
        if image_alt_coverages
        else 0.0
    )
    doc_images_proxy = round(
        _clamp01(
            (0.55 * pages_with_images_ratio)
            + (0.35 * min(1.0, avg_images_per_page / 3.0))
            + (0.1 * image_alt_coverage_avg)
        ),
        3,
    )
    doc_images_pages_with_images_ratio_proxy = round(pages_with_images_ratio, 3)
    doc_images_avg_images_per_page_proxy = round(avg_images_per_page, 3)
    doc_images_alt_coverage_avg_proxy = round(image_alt_coverage_avg, 3)

    answer_first_missing_ratio = 1.0 - (
        sum(
            1
            for page in pages
            if page.get("answer_first", {}).get("has_direct_answer", False)
        )
        / max(1, page_count)
    )

    engagement_values_for_proxy = [
        _safe_float(item.get("engagement_rate"))
        for item in ga4_by_url.values()
        if _safe_float(item.get("views")) > 0
    ]
    normalized_engagement = [
        value / 100.0 if value > 1.0 else value for value in engagement_values_for_proxy
    ]
    good_clicks_proxy = (
        round(median(normalized_engagement), 3) if normalized_engagement else 0.0
    )
    bad_clicks_proxy = round(max(0.0, 1.0 - good_clicks_proxy), 3)
    avg_engagement_values = [
        _safe_float(item.get("avg_engagement_time"))
        for item in ga4_by_url.values()
        if _safe_float(item.get("views")) > 0
    ]
    last_longest_clicks_proxy = (
        round(min(1.0, median(avg_engagement_values) / 180.0), 3)
        if avg_engagement_values
        else 0.0
    )

    scroll_depth_values = [
        _safe_float(item.get("scroll_depth_proxy"))
        for item in ga4_scroll_by_url.values()
        if _safe_float(item.get("users")) > 0
    ]
    direct_visit_values = [
        _safe_float(item.get("direct_share"))
        for item in ga4_traffic_by_url.values()
        if _safe_float(item.get("sessions")) > 0
    ]
    scroll_depth_proxy = round(median(scroll_depth_values), 3) if scroll_depth_values else 0.0
    direct_url_visits_proxy = (
        round(median(direct_visit_values), 3) if direct_visit_values else 0.0
    )

    max_inlinks = max(inlinks.values() or [1])
    money_page_prominence: list[dict[str, Any]] = []
    for page in pages:
        url = normalize_url(page.get("url", ""))
        signature = f"{urlparse(url).path} {page.get('title', '')}"
        if not money_re.search(signature):
            continue
        prominence = inlinks.get(url, 0) / max(1, max_inlinks)
        money_page_prominence.append(
            {"url": url, "prominence": round(prominence, 3), "inlinks": inlinks.get(url, 0)}
        )
    money_page_prominence.sort(key=lambda item: item["prominence"], reverse=True)
    onsite_prominence_proxy = round(
        sum(item["prominence"] for item in money_page_prominence)
        / max(1, len(money_page_prominence)),
        3,
    )

    severity_weights = {"Critical": 1.0, "High": 0.7, "Medium": 0.4, "Low": 0.1}
    nsr_penalty = sum(
        severity_weights.get(check["severity"], 0.1)
        for check in checks
        if check.get("evidence_urls")
    )
    nsr_proxy = round(max(0.0, 1.0 - (nsr_penalty / 12.0)), 3)
    site_authority_proxy = round((max_internal_pr + nsr_proxy) / 2.0, 3)
    low_quality_proxy = round(1.0 - nsr_proxy, 3)

    duplicate_ratio_value = _safe_float(checks[8]["proxy_metric"]["duplicate_url_ratio"])
    content_effort_avg_value = _safe_float(checks[1]["proxy_metric"]["contentEffort_proxy_avg"])
    baby_panda_demotion_proxy = round(
        _clamp01(
            (0.65 * duplicate_ratio_value)
            + (0.35 * max(0.0, 1.0 - content_effort_avg_value))
        ),
        3,
    )
    titlematch_score_proxy = round(_clamp01(title_overlap_avg), 3)

    nav_demotion_components: list[tuple[float, float]] = [
        (answer_first_missing_ratio, 0.25),
        (ui_ratio, 0.2),
        (mobile_ratio, 0.15),
        (title_rewrite_risk_ratio, 0.2),
        (mismatch_ratio, 0.2),
    ]
    if data_sources.get("ga4_pages", False):
        nav_demotion_components.append((1.0 - good_clicks_proxy, 0.15))
        nav_demotion_components.append((1.0 - last_longest_clicks_proxy, 0.1))
    if data_sources.get("gsc_timeseries", False) and coec_site_median > 0:
        nav_demotion_components.append(
            (max(0.0, 1.0 - min(1.0, coec_site_median)), 0.2)
        )

    nav_demotion_den = sum(weight for _, weight in nav_demotion_components) or 1.0
    nav_demotion_proxy = round(
        _clamp01(
            sum(value * weight for value, weight in nav_demotion_components)
            / nav_demotion_den
        ),
        3,
    )

    top_internal_pagerank_pages = sorted(
        (
            {"url": url, "score": round(score, 6)}
            for url, score in internal_pagerank.items()
        ),
        key=lambda item: item["score"],
        reverse=True,
    )[:15]

    proxy_metrics = {
        "siteRadius_proxy": checks[0]["proxy_metric"]["off_topic_ratio"],
        "siteFocusScore_proxy": checks[0]["proxy_metric"]["siteFocusScore_proxy"],
        "site2vecEmbeddingEncoded_proxy": site2vec_embedding_encoded_proxy,
        "contentEffort_proxy_avg": checks[1]["proxy_metric"]["contentEffort_proxy_avg"],
        "docImages_proxy": doc_images_proxy,
        "docImages_pages_with_images_ratio_proxy": doc_images_pages_with_images_ratio_proxy,
        "docImages_avg_images_per_page_proxy": doc_images_avg_images_per_page_proxy,
        "docImages_alt_coverage_avg_proxy": doc_images_alt_coverage_avg_proxy,
        "originalContentScore_proxy": round(
            1.0 - checks[8]["proxy_metric"]["duplicate_url_ratio"], 3
        ),
        "navboostRiskRatio_proxy": checks[2]["proxy_metric"]["risk_ratio"],
        "navDemotion_proxy": nav_demotion_proxy,
        "goodClicks_proxy": good_clicks_proxy,
        "badClicks_proxy": bad_clicks_proxy,
        "lastLongestClicks_proxy": last_longest_clicks_proxy,
        "clutterScore_proxy": checks[3]["proxy_metric"]["ui_risk_ratio"],
        "uiSmearing_proxy": round(
            len(template_risk_counter) / max(1, page_count),
            3,
        ),
        "authorEntityCoverage_proxy": round(
            1.0 - checks[4]["proxy_metric"]["missing_author_ratio"], 3
        ),
        "sameAs_links_total_proxy": same_as_total,
        "toxicityOutlinks_proxy": checks[5]["proxy_metric"]["toxic_outlink_ratio"],
        "syntacticDate_proxy": round(syntactic_fresh_count / max(1, page_count), 3),
        "semanticDateInfo_proxy": round(
            semantic_current_count / max(1, page_count), 3
        ),
        "freshnessIntegrity_proxy": round(
            1.0 - checks[6]["proxy_metric"]["freshness_mismatch_ratio"], 3
        ),
        "anchorConsistency_proxy": round(
            1.0 - min(1.0, len(checks[7]["evidence_urls"]) / max(1, page_count)), 3
        ),
        "duplicateRisk_proxy": checks[8]["proxy_metric"]["duplicate_url_ratio"],
        "babyPandaDemotion_proxy": baby_panda_demotion_proxy,
        "mobileRisk_proxy": checks[9]["proxy_metric"]["mobile_risk_ratio"],
        "smartphoneOptimized_proxy": round(
            1.0 - checks[9]["proxy_metric"]["mobile_risk_ratio"], 3
        ),
        "passageReadinessRisk_proxy": checks[10]["proxy_metric"][
            "low_extractability_ratio"
        ],
        "conversionIsolation_proxy": checks[11]["proxy_metric"]["isolated_money_ratio"],
        "onsiteProminence_proxy": onsite_prominence_proxy,
        "internalPageRank_proxy": max_internal_pr,
        "iPullRank_proxy": mean_internal_pr,
        "anchorStats_proxy": {
            "unique_anchors": len(anchor_counter_global),
            "total_internal_links": len(internal_links),
        },
        "NSR_proxy": nsr_proxy,
        "siteAuthority_proxy": site_authority_proxy,
        "predictedDefaultNsr_proxy": nsr_proxy,
        "lowQuality_proxy": low_quality_proxy,
        "COEC_proxy_site_median": coec_site_median,
        "serpDemotion_proxy_count": len(serp_demotion_pages),
        "scrollDepth_proxy": scroll_depth_proxy,
        "directUrlVisits_proxy": direct_url_visits_proxy,
        "dupTokens_proxy": dup_tokens_ratio,
        "title_h1_intro_overlap_proxy": title_overlap_avg,
        "titlematchScore_proxy": titlematch_score_proxy,
        "goldmineBlockbertFactor_proxy": goldmine_blockbert_factor,
        "titleRewriteRisk_proxy": title_rewrite_risk_ratio,
        "violatesMobileInterstitialPolicy_proxy": round(
            len(interstitial_policy_urls) / max(1, page_count), 3
        ),
        "ugcDiscussionEffortScore_proxy": ugc_discussion_effort,
        "productReviewPUhqPage_proxy": product_review_quality,
    }
    if has_rdap:
        proxy_metrics["hostAge_proxy_years"] = round(
            _safe_float(rdap_profile.get("domain_age_years")),
            3,
        )
        proxy_metrics["hostAge_proxy_days"] = int(
            _safe_float(rdap_profile.get("domain_age_days"))
        )
    metric_coverage = _build_metric_coverage(proxy_metrics, data_sources)

    summary = {
        "pages_crawled": len(crawl_rows),
        "pages_analyzed": page_count,
        "noindex_page_count": len(noindex_pages_list),
        "include_noindex_in_analysis": include_noindex,
        "checks_with_issues": len(
            [
                c
                for c in checks
                if c["evidence_urls"]
                and c["severity"] in {"Critical", "High", "Medium"}
            ]
        ),
        "critical_checks": len(
            [c for c in checks if c["severity"] == "Critical" and c["evidence_urls"]]
        ),
        "high_checks": len(
            [c for c in checks if c["severity"] == "High" and c["evidence_urls"]]
        ),
        "external_data_used": bool(has_external),
        "visual_data_used": bool(has_visual),
        "metric_coverage_implemented": len(
            [item for item in metric_coverage.values() if item.get("status") == "implemented"]
        ),
        "metric_coverage_missing_data": len(
            [item for item in metric_coverage.values() if item.get("status") == "missing-data"]
        ),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "proxy_metrics": proxy_metrics,
        "data_sources": data_sources,
        "url_aliases": url_aliases,
        "metric_coverage": metric_coverage,
        "authority_graph": {
            "top_internal_pagerank_pages": top_internal_pagerank_pages,
            "anchor_stats": proxy_metrics.get("anchorStats_proxy", {}),
            "money_page_prominence": money_page_prominence[:15],
        },
        "navboost_panel": {
            "coec_site_median": coec_site_median,
            "serp_demotion_pages": serp_demotion_pages[:20],
            "scroll_depth_proxy": scroll_depth_proxy,
            "direct_url_visits_proxy": direct_url_visits_proxy,
        },
        "checks": checks,
        "growth_actions": growth_actions,
        "navboost_risk_pages": navboost_risk_pages[:30],
        "noindex_pages": noindex_report,
        "serp_demotion_pages": serp_demotion_pages[:30],
        "title_rewrite_risk_pages": title_rewrite_risk_pages[:30],
        "ugc_low_effort_urls": ugc_low_effort_urls[:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze 12 Google-leak-inspired SEO checks."
    )
    parser.add_argument("--crawl-jsonl", type=Path, required=True)
    parser.add_argument("--external-json", type=Path)
    parser.add_argument("--visual-json", type=Path)
    parser.add_argument("--output", type=Path, default=Path("cache/analysis.json"))
    args = parser.parse_args()

    crawl_rows = load_jsonl(args.crawl_jsonl)
    external_data: dict[str, Any] = {}
    visual_data: dict[str, Any] = {}
    if args.external_json and args.external_json.exists():
        external_data = json.loads(args.external_json.read_text(encoding="utf-8"))
    if args.visual_json and args.visual_json.exists():
        visual_data = json.loads(args.visual_json.read_text(encoding="utf-8"))

    analysis = analyze_site(
        crawl_rows, external_data=external_data, visual_data=visual_data
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved: {args.output}")
    print(
        f"Checks: {len(analysis.get('checks', []))}, Issues: {analysis.get('summary', {}).get('checks_with_issues', 0)}"
    )


if __name__ == "__main__":
    main()
