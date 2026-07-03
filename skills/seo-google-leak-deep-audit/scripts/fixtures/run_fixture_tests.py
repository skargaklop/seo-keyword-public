#!/usr/bin/env python3
"""Deterministic fixture checks for leak audit analysis."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_SCRIPTS = SCRIPT_DIR.parent
if str(PARENT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PARENT_SCRIPTS))

from analyze_leak_checks import (  # noqa: E402
    _detect_navboost_risk,
    analyze_site,
    normalize_url,
)
import crawl_site as crawl_site_module  # noqa: E402
from extract_signals import extract_signals  # noqa: E402
from fetch_domain_rdap import (  # noqa: E402
    extract_domain_profile_from_rdap,
    load_domain_rdap,
)
from import_ga4_scroll_csv import load_ga4_scroll_csv  # noqa: E402
from import_ga4_traffic_csv import load_ga4_traffic_csv  # noqa: E402
from import_gsc_timeseries_csv import load_gsc_timeseries_csv  # noqa: E402


def _build_row(html_path: Path, url: str, depth: int) -> dict[str, Any]:
    html = html_path.read_text(encoding="utf-8")
    row = extract_signals(html, url)
    row["status"] = 200
    row["depth"] = depth
    row["content_type"] = "text/html"
    row["fetch_error"] = None
    return row


class _FakeResponse:
    def __init__(
        self,
        url: str,
        html: str,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.url = url
        self.text = html
        self.content = html.encode("utf-8")
        self.status_code = status_code
        self.headers = {"content-type": content_type}


class _FakeSession:
    def __init__(self, response_map: dict[str, _FakeResponse]) -> None:
        self._response_map = response_map
        self.headers: dict[str, str] = {}

    def get(
        self,
        url: str,
        timeout: int = 15,
        allow_redirects: bool = True,
        verify: bool = True,
    ) -> _FakeResponse:
        _ = timeout, allow_redirects, verify
        if url not in self._response_map:
            raise RuntimeError(f"Missing fake response for URL: {url}")
        return self._response_map[url]


class _RetrySession:
    def __init__(self, failures_before_success: int, payload: dict[str, Any]) -> None:
        self.failures_before_success = failures_before_success
        self.payload = payload
        self.calls = 0

    def get(
        self,
        url: str,
        timeout: int = 15,
        headers: dict[str, str] | None = None,
    ) -> Any:
        _ = url, timeout, headers
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise crawl_site_module.requests.exceptions.ReadTimeout("retry me")

        class _Response:
            def raise_for_status(self) -> None:
                return None

            def json(self_inner) -> dict[str, Any]:
                return self.payload

        return _Response()


def _run_crawl_with_fake_session(
    response_map: dict[str, _FakeResponse], **crawl_kwargs: Any
) -> list[dict[str, Any]]:
    original_session_cls = crawl_site_module.requests.Session
    crawl_site_module.requests.Session = lambda: _FakeSession(response_map)  # type: ignore[assignment]
    try:
        return crawl_site_module.crawl_site(**crawl_kwargs)
    finally:
        crawl_site_module.requests.Session = original_session_cls


def test_pagination_crawling() -> None:
    """Pagination URLs must be crawled as separate pages."""
    response_map = {
        "https://fixture.local/blog": _FakeResponse(
            "https://fixture.local/blog",
            "<html><head><title>Blog</title></head><body>"
            "<a href='/blog?page=2'>Next</a></body></html>",
        ),
        "https://fixture.local/blog?page=2": _FakeResponse(
            "https://fixture.local/blog?page=2",
            "<html><head><title>Blog p2</title></head><body>"
            "<a href='/blog?page=3'>Next</a></body></html>",
        ),
        "https://fixture.local/blog?page=3": _FakeResponse(
            "https://fixture.local/blog?page=3",
            "<html><head><title>Blog p3</title></head><body>No next</body></html>",
        ),
    }

    rows = _run_crawl_with_fake_session(
        response_map,
        site_url="https://fixture.local/blog",
        max_pages=10,
        delay_ms=0,
        respect_robots=False,
    )
    crawled_urls = {row.get("url", "") for row in rows}

    assert "https://fixture.local/blog?page=2" in crawled_urls, (
        f"Expected pagination page 2 in crawl set, got: {sorted(crawled_urls)}"
    )
    assert "https://fixture.local/blog?page=3" in crawled_urls, (
        f"Expected pagination page 3 in crawl set, got: {sorted(crawled_urls)}"
    )

    print("Pagination crawling checks passed.")


def test_sitemap_and_html_sitemap_seeds() -> None:
    """Crawler should accept XML sitemap and HTML site map as seed sources."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        local_sitemap = tmp_path / "sitemap-local.xml"
        html_sitemap = tmp_path / "site-map.html"

        local_sitemap.write_text(
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
            "<url><loc>https://fixture.local/from-local-sitemap</loc></url>"
            "</urlset>",
            encoding="utf-8",
        )
        html_sitemap.write_text(
            "<html><body><a href='https://fixture.local/from-html-map'>Map link</a></body></html>",
            encoding="utf-8",
        )

        response_map = {
            "https://fixture.local/": _FakeResponse(
                "https://fixture.local/",
                "<html><head><title>Home</title></head><body>Home</body></html>",
            ),
            "https://fixture.local/sitemap-remote.xml": _FakeResponse(
                "https://fixture.local/sitemap-remote.xml",
                "<?xml version='1.0' encoding='UTF-8'?>"
                "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
                "<url><loc>https://fixture.local/from-remote-sitemap</loc></url>"
                "</urlset>",
                content_type="application/xml; charset=utf-8",
            ),
            "https://fixture.local/from-local-sitemap": _FakeResponse(
                "https://fixture.local/from-local-sitemap",
                "<html><head><title>Local Seed</title></head><body>local</body></html>",
            ),
            "https://fixture.local/from-remote-sitemap": _FakeResponse(
                "https://fixture.local/from-remote-sitemap",
                "<html><head><title>Remote Seed</title></head><body>remote</body></html>",
            ),
            "https://fixture.local/from-html-map": _FakeResponse(
                "https://fixture.local/from-html-map",
                "<html><head><title>Map Seed</title></head><body>map</body></html>",
            ),
        }

        rows = _run_crawl_with_fake_session(
            response_map,
            site_url="https://fixture.local/",
            max_pages=10,
            delay_ms=0,
            respect_robots=False,
            sitemap_sources=[
                str(local_sitemap),
                "https://fixture.local/sitemap-remote.xml",
            ],
            sitemap_page_sources=[str(html_sitemap)],
        )

    crawled_urls = {row.get("url", "") for row in rows}
    expected_urls = {
        "https://fixture.local/from-local-sitemap",
        "https://fixture.local/from-remote-sitemap",
        "https://fixture.local/from-html-map",
    }
    missing = expected_urls - crawled_urls
    assert not missing, f"Expected sitemap seed URLs to be crawled, missing: {missing}"

    print("Sitemap seed crawling checks passed.")


def test_sitemap_index_and_image_entries() -> None:
    """Sitemap index should be traversed; image entries should be ignored."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        index_sitemap = tmp_path / "index.xml"
        local_child_sitemap = tmp_path / "child-local.xml"

        local_child_sitemap.write_text(
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9' "
            "xmlns:image='http://www.google.com/schemas/sitemap-image/1.1'>"
            "<url>"
            "<loc>https://fixture.local/from-local-child</loc>"
            "<image:image><image:loc>https://fixture.local/media/image-by-id</image:loc></image:image>"
            "</url>"
            "</urlset>",
            encoding="utf-8",
        )
        index_sitemap.write_text(
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<sitemapindex xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
            "<sitemap><loc>child-local.xml</loc></sitemap>"
            "<sitemap><loc>https://fixture.local/child-remote.xml</loc></sitemap>"
            "</sitemapindex>",
            encoding="utf-8",
        )

        response_map = {
            "https://fixture.local/": _FakeResponse(
                "https://fixture.local/",
                "<html><head><title>Home</title></head><body>Home</body></html>",
            ),
            "https://fixture.local/child-remote.xml": _FakeResponse(
                "https://fixture.local/child-remote.xml",
                "<?xml version='1.0' encoding='UTF-8'?>"
                "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
                "<url><loc>https://fixture.local/from-remote-child</loc></url>"
                "</urlset>",
                content_type="application/xml; charset=utf-8",
            ),
            "https://fixture.local/from-local-child": _FakeResponse(
                "https://fixture.local/from-local-child",
                "<html><head><title>Local Child</title></head><body>ok</body></html>",
            ),
            "https://fixture.local/from-remote-child": _FakeResponse(
                "https://fixture.local/from-remote-child",
                "<html><head><title>Remote Child</title></head><body>ok</body></html>",
            ),
            "https://fixture.local/media/image-by-id": _FakeResponse(
                "https://fixture.local/media/image-by-id",
                "binary-image-placeholder",
                content_type="image/jpeg",
            ),
        }

        rows = _run_crawl_with_fake_session(
            response_map,
            site_url="https://fixture.local/",
            max_pages=10,
            delay_ms=0,
            respect_robots=False,
            sitemap_sources=[str(index_sitemap)],
            sitemap_page_sources=[],
        )

    crawled_urls = {row.get("url", "") for row in rows}
    assert "https://fixture.local/from-local-child" in crawled_urls, (
        f"Expected URL from local child sitemap. Got: {sorted(crawled_urls)}"
    )
    assert "https://fixture.local/from-remote-child" in crawled_urls, (
        f"Expected URL from remote child sitemap. Got: {sorted(crawled_urls)}"
    )
    assert "https://fixture.local/media/image-by-id" not in crawled_urls, (
        "Image sitemap URL should not be enqueued as crawl target."
    )

    print("Sitemap index and image entry checks passed.")


def test_sitemap_query_alias_redirect_dedupes() -> None:
    """Sitemap query aliases should be crawled and deduped into canonical URL records."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sitemap_path = tmp_path / "sitemap.xml"
        sitemap_path.write_text(
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
            "<url><loc>https://fixture.local/category-slug</loc></url>"
            "<url><loc>https://fixture.local/index.html?cat_id=123</loc></url>"
            "</urlset>",
            encoding="utf-8",
        )

        response_map = {
            "https://fixture.local/": _FakeResponse(
                "https://fixture.local/",
                "<html><head><title>Home</title></head><body>Home</body></html>",
            ),
            "https://fixture.local/category-slug": _FakeResponse(
                "https://fixture.local/category-slug",
                "<html><head><title>Category</title></head><body>Category</body></html>",
            ),
            # Simulate a redirect from query URL to the canonical slug URL.
            "https://fixture.local/index.html?cat_id=123": _FakeResponse(
                "https://fixture.local/category-slug",
                "<html><head><title>Category</title></head><body>Category</body></html>",
            ),
        }

        rows = _run_crawl_with_fake_session(
            response_map,
            site_url="https://fixture.local/",
            max_pages=10,
            delay_ms=0,
            concurrency=1,
            respect_robots=False,
            sitemap_sources=[str(sitemap_path)],
            sitemap_page_sources=[],
        )

    canonical_rows = [
        row
        for row in rows
        if row.get("url", "") == "https://fixture.local/category-slug"
    ]
    assert len(canonical_rows) == 1, (
        f"Expected a single canonical record, got {len(canonical_rows)}: {canonical_rows}"
    )
    canonical = canonical_rows[0]
    aliases = canonical.get("aliases", []) or []
    assert "https://fixture.local/index.html?cat_id=123" in aliases, (
        f"Expected query alias in aliases, got: {aliases}"
    )
    alias_sources = canonical.get("alias_sources", {}) or {}
    assert alias_sources.get("https://fixture.local/index.html?cat_id=123") == "sitemap", (
        f"Expected alias source=sitemap, got: {alias_sources}"
    )

    print("Sitemap query alias dedupe checks passed.")


def test_original_checks(
    rows: list[dict[str, Any]], visual_data: dict[str, Any]
) -> None:
    """Run original fixture checks (excluding noindex pages by default)."""
    analysis = analyze_site(rows, external_data={}, visual_data=visual_data)
    checks_by_id = {item["id"]: item for item in analysis["checks"]}

    assert checks_by_id["check_04_ui_penalty_smearing"]["evidence_urls"], (
        "Expected UI smearing check to trigger."
    )
    assert checks_by_id["check_09_lexical_cannibalization"]["evidence_urls"], (
        "Expected duplicate check to trigger."
    )
    assert checks_by_id["check_05_broken_author_entity_graph"]["evidence_urls"], (
        "Expected missing author check to trigger."
    )

    print("Original fixture checks passed.")
    print(
        json.dumps(
            {key: checks_by_id[key]["severity"] for key in checks_by_id},
            ensure_ascii=False,
            indent=2,
        )
    )


def test_noindex_detection(fixture_dir: Path) -> None:
    """Test that is_noindex flag is correctly extracted."""
    noindex_row = _build_row(
        fixture_dir / "noindex-page.html", "https://fixture.local/draft", 1
    )
    assert noindex_row["is_noindex"] is True, (
        f"Expected is_noindex=True, got {noindex_row['is_noindex']}"
    )
    assert "noindex" in noindex_row["robots"].lower(), (
        f"Expected 'noindex' in robots content, got '{noindex_row['robots']}'"
    )

    normal_row = _build_row(
        fixture_dir / "sticky-overlay.html", "https://fixture.local/overlay", 1
    )
    assert normal_row.get("is_noindex", False) is False, (
        f"Expected is_noindex=False for normal page, got {normal_row.get('is_noindex')}"
    )

    print("Noindex detection checks passed.")


def test_noindex_exclusion(rows_with_noindex: list[dict[str, Any]]) -> None:
    """Test that noindex pages are excluded from analysis by default and included with flag."""
    # Default: exclude noindex
    analysis_exclude = analyze_site(rows_with_noindex, include_noindex=False)
    noindex_report = analysis_exclude.get("noindex_pages", [])
    assert len(noindex_report) >= 1, (
        "Expected at least 1 noindex page in noindex_pages report."
    )
    noindex_urls = {item["url"] for item in noindex_report}
    assert any("draft" in url for url in noindex_urls), (
        f"Expected draft URL in noindex report, got {noindex_urls}"
    )

    pages_analyzed_exclude = analysis_exclude["summary"]["pages_analyzed"]
    noindex_count = analysis_exclude["summary"]["noindex_page_count"]
    assert noindex_count >= 1, f"Expected noindex_page_count >= 1, got {noindex_count}"

    # Include noindex
    analysis_include = analyze_site(rows_with_noindex, include_noindex=True)
    pages_analyzed_include = analysis_include["summary"]["pages_analyzed"]
    assert pages_analyzed_include > pages_analyzed_exclude, (
        f"Expected more pages when including noindex: {pages_analyzed_include} vs {pages_analyzed_exclude}"
    )

    # Noindex report should be present regardless of the flag
    noindex_report_include = analysis_include.get("noindex_pages", [])
    assert len(noindex_report_include) >= 1, (
        "Expected noindex_pages even when include_noindex=True."
    )

    print("Noindex exclusion/inclusion checks passed.")


def test_metric_coverage_has_pdf_metrics() -> None:
    analysis = analyze_site([])
    coverage = analysis.get("metric_coverage", {})
    assert "contentEffort" in coverage, "Expected PDF metric in coverage table."
    assert "siteAuthority" in coverage, "Expected PDF metric in coverage table."
    print("Metric coverage fixture check passed.")


def test_internal_pagerank_proxy_present() -> None:
    rows = [_build_row(SCRIPT_DIR / "city-service-a.html", "https://fixture.local/a", 1)]
    analysis = analyze_site(rows)
    assert "internalPageRank_proxy" in analysis.get("proxy_metrics", {})
    print("Internal PageRank proxy check passed.")


def test_nsr_proxy_present() -> None:
    rows = [_build_row(SCRIPT_DIR / "missing-author.html", "https://fixture.local/x", 1)]
    analysis = analyze_site(rows)
    assert "NSR_proxy" in analysis.get("proxy_metrics", {})
    print("NSR proxy check passed.")


def test_gsc_timeseries_import() -> None:
    payload = load_gsc_timeseries_csv(
        SCRIPT_DIR / "gsc_timeseries_sample.csv",
        site_origin="https://fixture.local",
    )
    by_url_date = payload.get("by_url_date", {})
    assert "https://fixture.local/services/city-a" in by_url_date
    assert "2026-02-01" in by_url_date["https://fixture.local/services/city-a"]
    print("GSC timeseries import check passed.")


def test_ga4_extra_imports() -> None:
    traffic = load_ga4_traffic_csv(
        SCRIPT_DIR / "ga4_traffic_sample.csv", site_origin="https://fixture.local"
    )
    scroll = load_ga4_scroll_csv(
        SCRIPT_DIR / "ga4_scroll_sample.csv", site_origin="https://fixture.local"
    )
    assert "https://fixture.local/services/city-a" in traffic.get("by_url", {})
    assert "https://fixture.local/services/city-a" in scroll.get("by_url", {})
    print("GA4 extra import checks passed.")


def test_rdap_domain_profile_parsing() -> None:
    payload = {
        "ldhName": "example.com.ua",
        "events": [
            {
                "eventAction": "registration",
                "eventDate": "2024-06-17T14:29:35+03:00",
                "eventActor": "ua.thehost",
            },
            {
                "eventAction": "last changed",
                "eventDate": "2026-03-04T20:13:33+02:00",
            },
            {
                "eventAction": "expiration",
                "eventDate": "2027-06-17T14:29:35+03:00",
            },
        ],
    }
    profile = extract_domain_profile_from_rdap(
        payload,
        now="2026-03-13T00:00:00+00:00",
    )
    assert profile is not None, "Expected RDAP payload to produce domain profile."
    assert profile.get("domain") == "example.com.ua"
    assert profile.get("registration_date") == "2024-06-17T14:29:35+03:00"
    assert profile.get("domain_age_days", 0) > 600
    assert 1.7 <= float(profile.get("domain_age_years", 0)) <= 1.8
    print("RDAP domain profile parsing checks passed.")


def test_host_age_metric_from_rdap() -> None:
    rows = [_build_row(SCRIPT_DIR / "city-service-a.html", "https://fixture.local/a", 1)]
    analysis = analyze_site(
        rows,
        external_data={
            "rdap_whois": {
                "domain": "fixture.local",
                "registration_date": "2020-01-15T00:00:00+00:00",
                "domain_age_days": 1885,
                "domain_age_years": 5.161,
                "source": "rdap",
            }
        },
    )
    coverage = analysis.get("metric_coverage", {}).get("hostAge", {})
    assert coverage.get("status") == "implemented", (
        f"Expected hostAge implemented, got: {coverage}"
    )
    assert coverage.get("proxy_value") == 5.161, (
        f"Expected hostAge proxy value from RDAP, got: {coverage.get('proxy_value')}"
    )
    assert analysis.get("data_sources", {}).get("rdap_whois") is True
    print("RDAP hostAge metric checks passed.")


def test_rdap_retries_three_attempts() -> None:
    delays: list[float] = []
    session = _RetrySession(
        failures_before_success=2,
        payload={
            "ldhName": "example.com",
            "events": [
                {
                    "eventAction": "registration",
                    "eventDate": "2020-01-15T00:00:00+00:00",
                }
            ],
        },
    )
    profile = load_domain_rdap(
        "https://example.com/some-page",
        session=session,
        timeout=1,
        max_attempts=3,
        retry_min_delay=5.0,
        retry_max_delay=10.0,
        sleep_fn=delays.append,
        delay_fn=lambda: 7.5,
    )
    assert profile.get("domain") == "example.com"
    assert session.calls == 3, f"Expected 3 RDAP attempts, got {session.calls}"
    assert delays == [7.5, 7.5], f"Expected retry delays between failed attempts, got {delays}"
    print("RDAP retry checks passed.")


def test_title_rewrite_risk_proxy() -> None:
    rows = [
        _build_row(
            SCRIPT_DIR / "title-rewrite-risk.html",
            "https://fixture.local/rewrite-risk",
            1,
        ),
        _build_row(
            SCRIPT_DIR / "city-service-a.html",
            "https://fixture.local/services/city-a",
            2,
        ),
    ]
    analysis = analyze_site(rows)
    assert "titleRewriteRisk_proxy" in analysis.get("proxy_metrics", {})
    evidence_urls = analysis.get("title_rewrite_risk_pages", [])
    assert "https://fixture.local/rewrite-risk" in evidence_urls
    print("Title rewrite-risk checks passed.")


def test_ugc_and_interstitial_proxies() -> None:
    rows = [
        _build_row(
            SCRIPT_DIR / "ugc-discussion.html",
            "https://fixture.local/community/thread-a",
            2,
        ),
        _build_row(
            SCRIPT_DIR / "mobile-interstitial.html",
            "https://fixture.local/mobile-offer",
            1,
        ),
    ]
    visual_data = {
        "enabled": True,
        "results": [
            {
                "url": "https://fixture.local/mobile-offer",
                "overlay_detected": True,
                "horizontal_scroll": False,
                "heavy_js": False,
                "violates_mobile_interstitial_policy_proxy": True,
            }
        ],
    }
    analysis = analyze_site(rows, visual_data=visual_data)
    assert "ugcDiscussionEffortScore_proxy" in analysis.get("proxy_metrics", {})
    check_4 = {item["id"]: item for item in analysis.get("checks", [])}.get(
        "check_04_ui_penalty_smearing", {}
    )
    assert "https://fixture.local/mobile-offer" in check_4.get("evidence_urls", [])
    print("UGC and interstitial checks passed.")


def test_navboost_does_not_flag_without_ga4_engagement() -> None:
    url = normalize_url("https://fixture.local/no-ga4")
    pages = [
        {
            "url": url,
            "clickbait_title": False,
            "answer_first": {"has_direct_answer": True},
        }
    ]
    risks = _detect_navboost_risk(
        pages,
        gsc_by_url={url: {"impressions": 150, "ctr": 1.4}},
        ga4_by_url={},
    )
    assert not risks, (
        "Expected no high_ctr_low_engagement flag when GA4 engagement data is missing."
    )
    print("NavBoost no-GA4 guard checks passed.")


def test_navboost_flags_zero_coec() -> None:
    url = normalize_url("https://fixture.local/low-coec")
    pages = [
        {
            "url": url,
            "clickbait_title": False,
            "answer_first": {"has_direct_answer": True},
        }
    ]
    risks = _detect_navboost_risk(
        pages,
        gsc_by_url={url: {"impressions": 150, "ctr": 0.0}},
        ga4_by_url={},
        coec_by_url={url: 0.0},
    )
    assert risks, "Expected low-COEC page to be flagged."
    assert "coec_below_expected" in risks[0].get("reasons", []), (
        f"Expected coec_below_expected reason, got: {risks[0].get('reasons', [])}"
    )
    print("NavBoost zero-COEC checks passed.")


def main() -> None:
    fixture_dir = SCRIPT_DIR
    rows = [
        _build_row(
            fixture_dir / "sticky-overlay.html", "https://fixture.local/overlay", 1
        ),
        _build_row(
            fixture_dir / "city-service-a.html",
            "https://fixture.local/services/city-a",
            2,
        ),
        _build_row(
            fixture_dir / "city-service-b.html",
            "https://fixture.local/services/city-b",
            2,
        ),
        _build_row(
            fixture_dir / "missing-author.html",
            "https://fixture.local/guides/enterprise-playbook",
            2,
        ),
    ]

    visual_data = {
        "enabled": True,
        "results": [
            {
                "url": "https://fixture.local/overlay",
                "overlay_detected": True,
                "horizontal_scroll": False,
                "heavy_js": False,
            }
        ],
    }

    # Test 1: Original checks
    test_original_checks(rows, visual_data)

    # Test 2: Noindex detection
    test_noindex_detection(fixture_dir)

    # Test 3: Noindex exclusion/inclusion
    noindex_row = _build_row(
        fixture_dir / "noindex-page.html", "https://fixture.local/draft", 1
    )
    rows_with_noindex = rows + [noindex_row]
    test_noindex_exclusion(rows_with_noindex)

    # Test 4: Pagination support
    test_pagination_crawling()

    # Test 5: Sitemap seeds support
    test_sitemap_and_html_sitemap_seeds()

    # Test 6: Sitemap index + image entries
    test_sitemap_index_and_image_entries()

    # Test 7: Sitemap query alias + redirect dedupe
    test_sitemap_query_alias_redirect_dedupes()

    # Test 8: Metric coverage matrix
    test_metric_coverage_has_pdf_metrics()

    # Test 9: Internal PageRank proxy
    test_internal_pagerank_proxy_present()

    # Test 10: NSR proxy
    test_nsr_proxy_present()

    # Test 11: GSC timeseries parser
    test_gsc_timeseries_import()

    # Test 12: GA4 traffic + scroll parsers
    test_ga4_extra_imports()

    # Test 13: RDAP domain profile parser
    test_rdap_domain_profile_parsing()

    # Test 14: hostAge metric from RDAP
    test_host_age_metric_from_rdap()

    # Test 15: RDAP retry behavior
    test_rdap_retries_three_attempts()

    # Test 16: Title rewrite-risk signals
    test_title_rewrite_risk_proxy()

    # Test 17: UGC + interstitial policy signals
    test_ugc_and_interstitial_proxies()

    # Test 18: NavBoost should not infer low engagement without GA4 data
    test_navboost_does_not_flag_without_ga4_engagement()

    # Test 19: COEC==0 should still trigger demotion risk
    test_navboost_flags_zero_coec()

    print("\nAll fixture tests passed!")


if __name__ == "__main__":
    main()
