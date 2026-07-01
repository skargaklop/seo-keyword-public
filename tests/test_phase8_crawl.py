# Test: Phase 8 crawl workflow, safety, and math report orchestration
# LINKS: PLAN 08-03 Tasks 2-5
# MODULE_CONTRACT: tests/test_phase8_crawl
# Purpose: Verify crawl safety and math-report orchestration around sidebar-configured behavior.
# Rationale: Links crawl workflow tests to sidebar and suffix-removal verification.
# Dependencies: pytest, utils.url_safety, utils.crawler.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-011
# MODULE_MAP: tests/test_phase8_crawl.py
# Public Functions: pytest test functions.
# Private Helpers: none.
# Key Semantic Blocks: none.
# Critical Flows: validate crawl URL safety -> run crawl-related checks -> assert removed option behavior.
# Verification: verification-plan.xml#V-12-SUFFIX-REMOVAL
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-011.

import pytest

from utils.url_safety import URLSafetyError


def test_crawler_safety_blocks_localhost_private_ips_and_internal_domains() -> None:
    from utils.crawler import is_safe_url

    unsafe_urls = [
        "http://localhost",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://172.16.0.5",
        "http://192.168.1.10",
        "http://169.254.169.254",
        "http://[::1]",
        "http://service.local",
        "http://admin.internal",
    ]

    for url in unsafe_urls:
        assert is_safe_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "data:text/html,hello",
        "ftp://example.com/file.txt",
        "",
    ],
)
def test_crawler_safety_blocks_non_http_schemes(url: str) -> None:
    from utils.crawler import is_safe_url

    assert is_safe_url(url) is False


def test_crawler_safety_allows_public_http_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.crawler import is_safe_url

    monkeypatch.setattr(
        "utils.crawler.validate_safe_url_with_ips",
        lambda url: (object(), ["93.184.216.34"]),
    )

    assert is_safe_url("https://example.com/path") is True


def test_normalize_url_resolves_relative_strips_fragment_and_sorts_query() -> None:
    from utils.crawler import normalize_url

    result = normalize_url(
        "/Products?b=2&a=1#details",
        base="HTTPS://Example.COM/category/page",
    )

    assert result == "https://example.com/Products?a=1&b=2"


def test_same_domain_redirect_rules_allow_subdomains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from utils.crawler import should_follow_redirect

    monkeypatch.setattr(
        "utils.crawler.validate_safe_url_with_ips",
        lambda url: (object(), ["93.184.216.34"]),
    )

    assert should_follow_redirect(
        "https://blog.example.com/page",
        same_domain_only=True,
        current_domain="example.com",
        pinned_ip="93.184.216.34",
    )


def test_same_domain_redirect_rules_block_external_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from utils.crawler import should_follow_redirect

    monkeypatch.setattr(
        "utils.crawler.validate_safe_url_with_ips",
        lambda url: (object(), ["93.184.216.34"]),
    )

    assert not should_follow_redirect(
        "https://evil.test/page",
        same_domain_only=True,
        current_domain="example.com",
        pinned_ip="93.184.216.34",
    )


def test_redirect_to_unsafe_host_is_blocked() -> None:
    from utils.crawler import should_follow_redirect

    assert not should_follow_redirect(
        "http://127.0.0.1/admin",
        same_domain_only=False,
        current_domain="example.com",
        pinned_ip="93.184.216.34",
    )


def test_dns_rebinding_detected_when_ip_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from utils.crawler import should_follow_redirect

    monkeypatch.setattr(
        "utils.crawler.validate_safe_url_with_ips",
        lambda url: (object(), ["198.51.100.10"]),
    )

    assert not should_follow_redirect(
        "https://example.com/redirected",
        same_domain_only=True,
        current_domain="example.com",
        pinned_ip="93.184.216.34",
    )


def test_ip_pinning_returns_normalized_url_and_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from utils.crawler import pin_ip_and_validate

    monkeypatch.setattr(
        "utils.crawler.validate_safe_url_with_ips",
        lambda url: (object(), ["93.184.216.34"]),
    )

    normalized_url, pinned_ip = pin_ip_and_validate("HTTPS://Example.COM/a?b=2&a=1#x")

    assert normalized_url == "https://example.com/a?a=1&b=2"
    assert pinned_ip == "93.184.216.34"


def test_ip_pinning_rejects_internal_domain() -> None:
    from utils.crawler import pin_ip_and_validate

    with pytest.raises(URLSafetyError):
        pin_ip_and_validate("https://service.internal/path")


def _patch_public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "utils.crawler.validate_safe_url_with_ips",
        lambda url: (object(), ["93.184.216.34"]),
    )


def _patch_scraper_extract(monkeypatch: pytest.MonkeyPatch, calls: list[str]) -> None:
    from utils.scraper import ScrapedContent

    def fake_extract_text(html_content: str, url: str) -> ScrapedContent:
        calls.append(url)
        return ScrapedContent(
            url=url,
            title=f"Title for {url}",
            meta_description="Meta description",
            text=f"Body text for {url}",
            success=True,
        )

    monkeypatch.setattr("utils.crawler.WebScraper._extract_text", fake_extract_text)


def test_bounded_crawl_collects_single_page_with_webscraper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from utils.crawler import CrawlSettings, bounded_crawl

    _patch_public_dns(monkeypatch)
    calls: list[str] = []
    _patch_scraper_extract(monkeypatch, calls)

    html_by_url = {
        "https://example.com/": "<html><h1>Main Heading</h1><p>Content</p></html>",
    }

    monkeypatch.setattr(
        "utils.crawler._fetch_html_bounded",
        lambda url, current_domain, pinned_ip, settings, remaining_timeout: (
            url,
            html_by_url[url],
        ),
    )

    result = bounded_crawl(
        ["https://example.com"],
        CrawlSettings(max_pages=5, max_depth=1, timeout_seconds=120),
    )

    assert len(result.pages) == 1
    assert result.pages[0].url == "https://example.com/"
    assert result.pages[0].headings == ["Main Heading"]
    assert calls == ["https://example.com/"]


def test_bounded_crawl_follows_same_domain_links_with_depth_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from utils.crawler import CrawlSettings, bounded_crawl

    _patch_public_dns(monkeypatch)
    calls: list[str] = []
    _patch_scraper_extract(monkeypatch, calls)

    html_by_url = {
        "https://example.com/": '<a href="/about">About</a><a href="https://other.test/x">Other</a>',
        "https://example.com/about": "<h2>About</h2>",
    }

    monkeypatch.setattr(
        "utils.crawler._fetch_html_bounded",
        lambda url, current_domain, pinned_ip, settings, remaining_timeout: (
            url,
            html_by_url[url],
        ),
    )

    result = bounded_crawl(
        ["https://example.com"],
        CrawlSettings(max_pages=5, max_depth=1, same_domain_only=True),
    )

    assert [page.url for page in result.pages] == [
        "https://example.com/",
        "https://example.com/about",
    ]
    assert "https://other.test/x" not in calls


def test_bounded_crawl_respects_max_depth(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.crawler import CrawlSettings, bounded_crawl

    _patch_public_dns(monkeypatch)
    calls: list[str] = []
    _patch_scraper_extract(monkeypatch, calls)

    monkeypatch.setattr(
        "utils.crawler._fetch_html_bounded",
        lambda url, current_domain, pinned_ip, settings, remaining_timeout: (
            url,
            '<a href="/about">About</a>',
        ),
    )

    result = bounded_crawl(
        ["https://example.com"],
        CrawlSettings(max_pages=5, max_depth=0),
    )

    assert [page.url for page in result.pages] == ["https://example.com/"]


def test_bounded_crawl_normalizes_and_skips_duplicate_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from utils.crawler import CrawlSettings, bounded_crawl

    _patch_public_dns(monkeypatch)
    calls: list[str] = []
    _patch_scraper_extract(monkeypatch, calls)

    html_by_url = {
        "https://example.com/": (
            '<a href="/about?b=2&a=1#top">About A</a>'
            '<a href="/about?a=1&b=2">About B</a>'
        ),
        "https://example.com/about?a=1&b=2": "<h2>About</h2>",
    }

    monkeypatch.setattr(
        "utils.crawler._fetch_html_bounded",
        lambda url, current_domain, pinned_ip, settings, remaining_timeout: (
            url,
            html_by_url[url],
        ),
    )

    result = bounded_crawl(
        ["https://example.com"],
        CrawlSettings(max_pages=5, max_depth=1),
    )

    assert [page.url for page in result.pages] == [
        "https://example.com/",
        "https://example.com/about?a=1&b=2",
    ]


def test_bounded_crawl_stops_at_max_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils.crawler import CrawlSettings, bounded_crawl

    _patch_public_dns(monkeypatch)
    calls: list[str] = []
    _patch_scraper_extract(monkeypatch, calls)

    html_by_url = {
        "https://example.com/": '<a href="/one">One</a><a href="/two">Two</a>',
        "https://example.com/one": "<h2>One</h2>",
        "https://example.com/two": "<h2>Two</h2>",
    }

    monkeypatch.setattr(
        "utils.crawler._fetch_html_bounded",
        lambda url, current_domain, pinned_ip, settings, remaining_timeout: (
            url,
            html_by_url[url],
        ),
    )

    result = bounded_crawl(
        ["https://example.com"],
        CrawlSettings(max_pages=2, max_depth=1),
    )

    assert len(result.pages) == 2
    assert result.limit_reached is True


def test_bounded_fetch_rejects_large_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from utils.crawler import CrawlSafetyError, CrawlSettings, _fetch_html_bounded

    class _FakeResponse:
        is_redirect = False
        is_permanent_redirect = False
        headers = {"Content-Type": "text/html"}
        encoding = "utf-8"
        raw = SimpleNamespace(
            _connection=SimpleNamespace(
                sock=SimpleNamespace(getpeername=lambda: ("93.184.216.34", 443))
            )
        )

        @staticmethod
        def iter_content(chunk_size=65536):
            yield b"a" * 8
            yield b"b" * 8

        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def close() -> None:
            return None

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        @staticmethod
        def get(*args, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr("utils.crawler.requests.Session", _FakeSession)

    with pytest.raises(CrawlSafetyError):
        _fetch_html_bounded(
            "https://example.com/",
            current_domain="example.com",
            pinned_ip="93.184.216.34",
            settings=CrawlSettings(max_response_bytes=10, max_retries=0),
            remaining_timeout=10,
        )


def _enable_math_config(monkeypatch: pytest.MonkeyPatch) -> None:
    import utils.pipeline as pipeline

    for key, value in {
        "enabled": True,
        "analyze_ngrams": True,
        "analyze_tfidf": True,
        "analyze_cooccurrence": True,
        "analyze_intent": True,
        "ngram_min": 1,
        "ngram_max": 2,
        "top_terms_limit": 20,
        "min_ngram_count": 1,
        "min_document_frequency": 1,
    }.items():
        monkeypatch.setitem(pipeline.SEO_MATH_CONFIG, key, value)


def test_build_crawl_math_report_groups_pages_and_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from utils.crawler import CrawlPage, CrawlResult
    from utils.pipeline import build_crawl_math_report

    _enable_math_config(monkeypatch)
    crawl_result = CrawlResult(
        pages=[
            CrawlPage(
                url="https://example.com/",
                depth=0,
                title="SEO audit tools",
                headings=["Keyword research"],
                body_text="seo audit keyword research content",
            ),
            CrawlPage(
                url="https://example.com/about",
                depth=1,
                title="SEO audit checklist",
                headings=["SEO services"],
                body_text="seo audit keyword research services",
            ),
        ],
        visited_count=2,
    )

    report = build_crawl_math_report(crawl_result)

    assert report["info_message"] == ""
    assert len(report["pages"]) == 2
    # total_word_count spans the full analyzed corpus (title + headings + body per page):
    #   p1: "SEO audit tools"(3) + "Keyword research"(2) + body(5) = 10
    #   p2: "SEO audit checklist"(3) + "SEO services"(2) + body(5) = 10  ->  20 total
    assert report["aggregate_profile"]["total_word_count"] == 20
    assert report["aggregate_profile"]["ngrams_by_size"]
    assert report["keyword_candidates"]


def test_build_crawl_math_report_separates_page_summary_and_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from utils.crawler import CrawlPage, CrawlResult
    from utils.pipeline import build_crawl_math_report

    _enable_math_config(monkeypatch)
    crawl_result = CrawlResult(
        pages=[
            CrawlPage(
                url="https://example.com/",
                depth=0,
                title="SEO audit tools",
                meta_description="Tools for SEO audits",
                headings=["Keyword research", "SEO checklist"],
                body_text="seo audit keyword research content",
            )
        ],
        visited_count=1,
    )

    report = build_crawl_math_report(crawl_result)

    page = report["pages"][0]
    assert page["title"] == "SEO audit tools"
    assert page["url"] == "https://example.com/"
    assert page["meta_description"] == "Tools for SEO audits"
    assert page["heading_count"] == 2
    assert page["headings"] == ["Keyword research", "SEO checklist"]
    assert page["analysis_evidence"]["top_tfidf_terms"]
    assert page["analysis_evidence"]["top_ngrams"]
    assert "profile" in page


def test_render_crawl_math_report_labels_page_summary_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import nullcontext
    from types import SimpleNamespace

    import components.results as results

    calls: list[tuple[str, tuple[object, ...]]] = []

    class _Column:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _record(name: str):
        def _inner(*args, **kwargs):
            calls.append((name, args))

        return _inner

    mock_st = SimpleNamespace(
        divider=_record("divider"),
        subheader=_record("subheader"),
        info=_record("info"),
        metric=_record("metric"),
        columns=lambda count: tuple(_Column() for _ in range(count)),
        dataframe=_record("dataframe"),
        expander=lambda *args, **kwargs: nullcontext(),
        markdown=_record("markdown"),
        caption=_record("caption"),
        download_button=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        session_state={},
    )
    monkeypatch.setattr(results, "st", mock_st)
    monkeypatch.setattr(results, "render_keyword_candidate_selector", lambda *args, **kwargs: False)
    monkeypatch.setattr(results, "render_bidirectional_chain_buttons", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        results,
        "t",
        lambda key, **kwargs: {
            "crawl_report_header": "Crawl Mathematical Report",
            "crawl_pages_stat": "Pages",
            "crawl_visited_stat": "Visited",
            "crawl_errors_stat": "Errors",
            "seo_math_total_words_label": "Total Words",
            "crawl_page_details": "Report Pages",
            "crawl_page_title_label": "Title",
            "crawl_page_url_label": "URL",
            "crawl_page_meta_description_label": "Meta description",
            "crawl_page_heading_count_label": "Heading count",
            "crawl_page_headings_label": "Headings",
            "crawl_page_analysis_evidence_label": "Analysis evidence",
            "crawl_page_intent_label": "Intent",
            "crawl_page_tfidf_terms_label": "Top TF-IDF terms",
            "crawl_page_top_ngrams_label": "Top n-grams",
        }.get(key, key),
    )

    report = {
        "info_message": "",
        "crawl": SimpleNamespace(pages=[1], visited_count=1, errors=[]),
        "aggregate_profile": {},
        "pages": [
            {
                "title": "Деревна стружка",
                "url": "https://bigbox.com.ua/derevyana-struzhka/",
                "meta_description": "Декоративна стружка для коробок",
                "headings": [
                    "Деревна стружка",
                    "Декоративна стружка та наповнювач для коробок",
                    "Навіщо потрібен наповнювач у коробці",
                ],
                "analysis_evidence": {
                    "intent": "informational",
                    "top_tfidf_terms": ["стружка", "наповнювач"],
                    "top_ngrams": ["деревна стружка", "наповнювач у коробці"],
                },
            }
        ],
    }

    results.render_crawl_math_report(report=report)

    markdown_calls = [args[0] for name, args in calls if name == "markdown"]
    assert any("Title:" in call and "Деревна стружка" in call for call in markdown_calls)
    assert any("URL:" in call and "https://bigbox.com.ua/derevyana-struzhka/" in call for call in markdown_calls)
    assert any("Meta description:" in call and "Декоративна стружка для коробок" in call for call in markdown_calls)
    assert any("Heading count:" in call and "3" in call for call in markdown_calls)
    assert any("Headings:" in call for call in markdown_calls)
    assert any("Analysis evidence:" in call for call in markdown_calls)
    assert any("Intent:" in call and "informational" in call for call in markdown_calls)
    assert any("Top TF-IDF terms:" in call and "стружка" in call for call in markdown_calls)
    assert any("Top n-grams:" in call and "деревна стружка" in call for call in markdown_calls)


def test_render_crawl_math_report_uses_full_aggregate_profile_without_fixed_slices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    import components.results as results

    class _Column:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _DummyContext:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    tfidf_terms = [
        SimpleNamespace(term=f"term-{i}", tfidf=1.0 - i * 0.01, doc_frequency=i + 1)
        for i in range(20)
    ]
    ngrams = [
        SimpleNamespace(
            ngram=f"ngram-{i}",
            raw_count=i + 1,
            weighted_count=2.5 + i,
            doc_frequency=i + 2,
        )
        for i in range(20)
    ]

    calls: list[tuple[str, object]] = []
    mock_st = SimpleNamespace(
        divider=lambda *args, **kwargs: None,
        subheader=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        metric=lambda *args, **kwargs: None,
        columns=lambda count: tuple(_Column() for _ in range(count)),
        dataframe=lambda df, *args, **kwargs: calls.append(("dataframe", df.copy())),
        expander=lambda *args, **kwargs: _DummyContext(),
        markdown=lambda value, *args, **kwargs: calls.append(("markdown", value)),
        caption=lambda *args, **kwargs: None,
        session_state={},
        download_button=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        write=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(results, "st", mock_st)
    monkeypatch.setattr(results, "render_keyword_candidate_selector", lambda *args, **kwargs: False)
    monkeypatch.setattr(results, "render_bidirectional_chain_buttons", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        results,
        "t",
        lambda key, **kwargs: {
            "crawl_report_header": "Crawl Mathematical Report",
            "crawl_pages_stat": "Pages",
            "crawl_visited_stat": "Visited",
            "crawl_errors_stat": "Errors",
            "crawl_aggregate_terms": "Aggregate terms",
            "seo_math_total_words_label": "Total Words",
            "seo_math_density_pct_label": "Density %",
            "crawl_ngram_details": "N-gram details",
            "crawl_page_details": "Page details",
            "crawl_page_title_label": "Title",
            "crawl_page_url_label": "URL",
            "crawl_page_meta_description_label": "Meta description",
            "crawl_page_heading_count_label": "Heading count",
            "crawl_page_headings_label": "Headings",
            "crawl_page_analysis_evidence_label": "Analysis evidence",
            "crawl_page_intent_label": "Intent",
            "crawl_page_tfidf_terms_label": "Top TF-IDF terms",
            "crawl_page_top_ngrams_label": "Top n-grams",
            "crawl_select_keywords": "Select keywords",
            "export_math_analysis": "Export Math Analysis",
        }.get(key, key),
    )

    report = {
        "info_message": "",
        "crawl": SimpleNamespace(pages=[1], visited_count=1, errors=[]),
        "aggregate_profile": {
            "total_word_count": 40,
            "tfidf_terms": tfidf_terms,
            "ngrams_by_size": {1: ngrams},
            "related_searches": [],
            "people_also_ask": [],
        },
        "pages": [
            {
                "title": "Page title",
                "url": "https://example.com",
                "meta_description": "Description",
                "headings": ["H1", "H2"],
                "analysis_evidence": {
                    "intent": "informational",
                    "top_tfidf_terms": ["term-0", "term-1"],
                    "top_ngrams": ["ngram-0", "ngram-1"],
                },
            }
        ],
    }

    results.render_crawl_math_report(report=report)

    dataframe_calls = [value for name, value in calls if name == "dataframe"]
    assert any(getattr(df, "shape", (0, 0))[0] == 20 for df in dataframe_calls)
    assert any(
        list(getattr(df, "columns", []))
        == ["N-gram", "Count", "Total Words", "Density %", "Weighted", "DF"]
        and getattr(df, "shape", (0, 0))[0] == 20
        for df in dataframe_calls
    )


def test_run_crawl_math_report_workflow_uses_cached_crawl_and_stores_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    import utils.pipeline as pipeline
    from utils.crawler import CrawlPage, CrawlResult

    class _SessionState(dict):
        def __getattr__(self, key):
            return self.get(key)

        def __setattr__(self, key, value):
            self[key] = value

    class _Status:
        def __init__(self) -> None:
            self.messages = []

        def text(self, message):
            self.messages.append(message)

        def success(self, message):
            self.messages.append(message)

    status = _Status()
    mock_st = SimpleNamespace(
        session_state=_SessionState(),
        warning=lambda message: None,
        info=lambda message: None,
        empty=lambda: status,
    )
    monkeypatch.setattr(pipeline, "st", mock_st)
    monkeypatch.setattr(pipeline.logger, "info", lambda *args, **kwargs: None)
    _enable_math_config(monkeypatch)

    crawl_result = CrawlResult(
        pages=[
            CrawlPage(
                url="https://example.com/",
                depth=0,
                title="SEO audit",
                body_text="seo audit keyword research",
            ),
            CrawlPage(
                url="https://example.com/two",
                depth=1,
                title="SEO audit",
                body_text="seo audit keyword research",
            ),
        ],
        visited_count=2,
    )
    calls = []

    def fake_cached(seed_urls, settings_items, settings_hash):
        calls.append((seed_urls, settings_items, settings_hash))
        return crawl_result

    monkeypatch.setattr(pipeline, "_cached_bounded_crawl", fake_cached)

    report = pipeline.run_crawl_math_report_workflow(
        ["https://example.com"],
        crawler_settings={"max_pages": 3, "timeout_seconds": 120},
        run_id="crawl-test",
    )

    assert report is not None
    assert calls == [
        (
            ("https://example.com",),
            (
                ("max_depth", 3),
                ("max_pages", 3),
                ("max_response_bytes", 10485760),
                ("max_retries", 1),
                ("same_domain_only", True),
                ("timeout_seconds", 120),
            ),
            "(3, 3, True, 120, 10485760, 1)",  # settings_hash
        )
    ]
    assert mock_st.session_state.crawl_result is crawl_result
    assert mock_st.session_state.crawl_math_report is report
    assert mock_st.session_state["kw_candidates_crawl_math_handoff"]


def test_cached_bounded_crawl_is_streamlit_cached() -> None:
    from utils.pipeline import _cached_bounded_crawl

    assert hasattr(_cached_bounded_crawl, "clear")


def test_crawl_workflow_mode_registered() -> None:
    from app import WORKFLOW_MODE_CRAWL_REPORT, WORKFLOW_MODES

    assert WORKFLOW_MODE_CRAWL_REPORT == "crawl_report"
    assert WORKFLOW_MODE_CRAWL_REPORT in WORKFLOW_MODES


def test_crawl_i18n_keys_have_ru_uk_en_values() -> None:
    from config.i18n import TRANSLATIONS

    for key in [
        "crawl_mode_label",
        "crawl_seed_input_header",
        "crawl_report_header",
        "crawl_select_keywords",
        "crawl_settings_header",
        "crawl_enabled",
        "crawl_disabled_warning",
        "crawl_page_title_label",
        "crawl_page_url_label",
        "crawl_page_meta_description_label",
        "crawl_page_heading_count_label",
        "crawl_page_headings_label",
        "crawl_page_analysis_evidence_label",
        "crawl_page_intent_label",
        "crawl_page_tfidf_terms_label",
        "crawl_page_top_ngrams_label",
    ]:
        assert key in TRANSLATIONS
        for lang in ("ru", "uk", "en"):
            assert TRANSLATIONS[key].get(lang)


def test_crawler_config_is_top_level_and_valid() -> None:
    from config.settings import CRAWLER_CONFIG, config

    assert "crawler" in config
    assert "crawler" not in config.get("seo_math", {})
    assert isinstance(CRAWLER_CONFIG["enabled"], bool)
    assert CRAWLER_CONFIG["max_pages"] >= 1
    assert CRAWLER_CONFIG["max_depth"] >= 0
    assert isinstance(CRAWLER_CONFIG["same_domain_only"], bool)
    assert CRAWLER_CONFIG["timeout_seconds"] > 0
    assert CRAWLER_CONFIG["max_response_bytes"] > 0


def test_sidebar_persists_crawler_namespace_top_level() -> None:
    from components.sidebar import _build_sidebar_config_updates

    values = {
        "keyword_prompt": "",
        "seo_prompt": "",
        "api_timeout": 10,
        "api_delay": 2,
        "api_retry_count": 4,
        "api_retry_delay": 4,
        "cleanup_max_age": 30,
        "app_log_level": "INFO",
        "console_logging_enabled": True,
        "console_log_level": "INFO",
        "api_logging_enabled": True,
        "api_log_level": "ERROR",
        "api_retention_days": 30,
        "error_log_level": "ERROR",
        "history_retention_days": 30,
        "log_test_runs": False,
        "provider": "Omniroute",
        "model_name": "Kiro GLM rotate",
        "max_keywords": 50,
        "upload_max_file_size_mb": 5,
        "upload_max_rows": 1000,
        "ui_lang": "en",
        "location_id": "2840",
        "language_id": "1000",
        "currency_code": "USD",
        "serp_provider": "searchapi_io",
        "serp_num_results": 10,
        "serp_gl": "ua",
        "serp_hl": "uk",
        "serp_device": "",
        "serp_search_type": "web",
        "serp_time_period": "any",
        "serp_safe_search": "off",
        "serp_google_domain": "google.com",
        "serp_city": "",
        "serp_uule": "",
        "seo_math_enabled": True,
        "seo_math_analyze_ngrams": True,
        "seo_math_analyze_tfidf": True,
        "seo_math_analyze_cooccurrence": True,
        "seo_math_analyze_intent": True,
        "seo_math_analyze_generation_quality": True,
        "seo_math_suffix_stripping": False,
        "seo_math_ngram_min": 1,
        "seo_math_ngram_max": 3,
        "seo_math_top_terms": 30,
        "seo_math_min_count": 2,
        "seo_math_min_df": 2,
        "seo_math_use_related": True,
        "seo_math_use_paa": True,
        "crawler_enabled": True,
        "crawler_max_pages": 12,
        "crawler_max_depth": 2,
        "crawler_same_domain_only": True,
        "crawler_timeout_seconds": 120,
        "crawler_max_response_bytes": 10485760,
        "crawler_max_retries": 1,
    }

    updated = _build_sidebar_config_updates({}, values)

    assert updated["crawler"] == {
        "enabled": True,
        "max_pages": 12,
        "max_depth": 2,
        "same_domain_only": True,
        "timeout_seconds": 120,
        "max_response_bytes": 10485760,
        "max_retries": 1,
    }
    assert "crawler" not in updated["seo_math"]


def _serp_fixture_df():
    import pandas as pd

    return pd.DataFrame(
        {
            "Keyword": ["seo tools", "seo tools"],
            "Position": [1, 2],
            "Title": ["SEO tools audit", "Keyword research software"],
            "URL": ["https://one.test", "https://two.test"],
            "Snippet": [
                "SEO tools for keyword research and content audit",
                "SEO audit software for keyword research",
            ],
            "Displayed Link": ["one.test", "two.test"],
            "Rich Snippet": ["", ""],
            "Provider": ["test", "test"],
        }
    )


def test_reverse_math_report_treats_ads_metrics_as_enrichment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pandas as pd

    from utils.pipeline import build_reverse_math_report

    _enable_math_config(monkeypatch)
    ads_df = pd.DataFrame(
        {
            "Keyword": ["seo tools", "content gap"],
            "Avg Monthly Searches": [999999, 500],
            "Competition": ["HIGH", "LOW"],
            "Competition Index": [98, 12],
            "Low CPC": [1.23, 0.4],
            "High CPC": [5.67, 0.9],
            "CPC Currency": ["USD", "USD"],
        }
    )

    report = build_reverse_math_report(_serp_fixture_df(), [], ads_df)

    assert report["ads_as_enrichment"] is True
    assert report["ads_metrics_used_as_text"] is False
    assert report["ads_enrichment"][0]["Avg Monthly Searches"] == 999999
    assert "999999" not in report["text_evidence_terms"]
    assert "seo tools" in report["overlap_keywords"]
    assert "content gap" in report["ads_only_keywords"]


def test_reverse_math_report_overlap_respects_lemmatization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # When strip_suffixes is enabled, SERP text terms are lemmatized (e.g. "SEO tools"
    # -> bigram "seo tool", singular) but the Ads keyword stays as the user-typed
    # "seo tools" (plural). The reverse-math report must still recognize these as the
    # SAME keyword — the user's directive is "ALL the math must respect lemmatisation".
    # So an Ads keyword that differs from a SERP term only by inflection must be reported
    # in overlap_keywords (using the original Ads surface form), not in ads_only_keywords.
    import pandas as pd

    from utils.pipeline import SEO_MATH_CONFIG, build_reverse_math_report

    monkeypatch.setitem(SEO_MATH_CONFIG, "strip_suffixes", True)

    ads_df = pd.DataFrame(
        {
            "Keyword": ["seo tools", "content gap"],
            "Avg Monthly Searches": [999999, 500],
            "Competition": ["HIGH", "LOW"],
        }
    )

    report = build_reverse_math_report(_serp_fixture_df(), [], ads_df)

    # "seo tools" overlaps SERP text (lemmatized to "seo tool"); report the original form.
    assert "seo tools" in report["overlap_keywords"], (
        f"ENABLED should match inflected Ads keyword to lemmatized SERP term; "
        f"overlap_keywords={report['overlap_keywords']}"
    )
    # "content gap" is not in the SERP fixture text, so it remains ads-only.
    assert "content gap" in report["ads_only_keywords"]


def test_reverse_math_report_overlap_strict_uses_raw_matching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # When strip_suffixes is explicitly OFF, overlap uses raw lowercased matching — an
    # Ads keyword "seo tools" matches the SERP bigram "seo tools" verbatim, and a
    # deliberately singular Ads form "seo tool" must NOT match (it would only match under
    # lemmatization). Locks the user's "disable it and get raw analysis" guarantee.
    import pandas as pd

    from utils.pipeline import SEO_MATH_CONFIG, build_reverse_math_report

    monkeypatch.setitem(SEO_MATH_CONFIG, "strip_suffixes", False)

    ads_df = pd.DataFrame(
        {
            "Keyword": ["seo tools", "seo tool"],
            "Avg Monthly Searches": [1000, 500],
        }
    )

    report = build_reverse_math_report(_serp_fixture_df(), [], ads_df)

    # "seo tools" matches verbatim; singular "seo tool" does NOT (raw mode).
    assert "seo tools" in report["overlap_keywords"]
    assert "seo tool" in report["ads_only_keywords"]


def test_reverse_math_report_ads_only_does_not_create_text_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pandas as pd

    from utils.pipeline import build_reverse_math_report

    _enable_math_config(monkeypatch)
    ads_df = pd.DataFrame(
        {
            "Keyword": ["seo tools"],
            "Avg Monthly Searches": [1000],
            "Competition": ["MEDIUM"],
        }
    )

    report = build_reverse_math_report(ads_df=ads_df)

    assert report["ads_enrichment"] == [
        {
            "Keyword": "seo tools",
            "Avg Monthly Searches": 1000,
            "Competition": "MEDIUM",
        }
    ]
    assert report["text_evidence_terms"] == []
    assert report["info_message"].startswith("Ads keyword metrics available")


def test_reverse_math_report_empty_inputs_show_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from utils.pipeline import build_reverse_math_report

    _enable_math_config(monkeypatch)

    report = build_reverse_math_report()

    assert report["info_message"] == "No SERP or Ads data available for mathematical report."
    assert report["ads_enrichment"] == []
    assert report["text_evidence_terms"] == []
# GRACE: Purpose: Test crawler safety blocks localhost private ips and internal domains
# GRACE: Purpose: Test crawler safety blocks non http schemes
# GRACE: Purpose: Test crawler safety allows public http url
# GRACE: Purpose: Test normalize url resolves relative strips fragment and sorts query
# GRACE: Purpose: Test same domain redirect rules allow subdomains
# GRACE: Purpose: Test same domain redirect rules block external domain
# GRACE: Purpose: Test redirect to unsafe host is blocked
# GRACE: Purpose: Test dns rebinding detected when ip changes
# GRACE: Purpose: Test ip pinning returns normalized url and ip
# GRACE: Purpose: Test ip pinning rejects internal domain
# GRACE: Purpose:  patch public dns implementation
# GRACE: Purpose:  patch scraper extract implementation
    # GRACE: Purpose: fake extract text implementation
# GRACE: Purpose: Test bounded crawl collects single page with webscraper
# GRACE: Purpose: Test bounded crawl follows same domain links with depth limit
# GRACE: Purpose: Test bounded crawl respects max depth
# GRACE: Purpose: Test bounded crawl normalizes and skips duplicate urls
# GRACE: Purpose: Test bounded crawl stops at max pages
# GRACE: Purpose: Test bounded fetch rejects large response
    # GRACE: Purpose:  FakeResponse implementation
        # GRACE: Purpose: iter content implementation Purpose: iter content implementation
        # GRACE: Purpose: raise for status implementation Purpose: raise for status implementation
        # GRACE: Purpose: close implementation Purpose: close implementation
    # GRACE: Purpose:  FakeSession implementation
        # GRACE: Purpose:   enter   implementation
        # GRACE: Purpose:   exit   implementation
        # GRACE: Purpose: get implementation Purpose: get implementation
# GRACE: Purpose:  enable math config implementation
# GRACE: Purpose: Test build crawl math report groups pages and aggregate
# GRACE: Purpose: Test build crawl math report separates page summary and evidence
# GRACE: Purpose: Test render crawl math report labels page summary fields
    # GRACE: Purpose:  Column implementation
        # GRACE: Purpose:   enter   implementation
        # GRACE: Purpose:   exit   implementation
    # GRACE: Purpose:  record implementation
        # GRACE: Purpose:  inner implementation
# GRACE: Purpose: Test render crawl math report uses full aggregate profile without fixed slices
    # GRACE: Purpose:  Column implementation
        # GRACE: Purpose:   enter   implementation
        # GRACE: Purpose:   exit   implementation
    # GRACE: Purpose:  DummyContext implementation
        # GRACE: Purpose:   enter   implementation
        # GRACE: Purpose:   exit   implementation
# GRACE: Purpose: Test run crawl math report workflow uses cached crawl and stores candidates
    # GRACE: Purpose:  SessionState implementation
        # GRACE: Purpose:   getattr   implementation
        # GRACE: Purpose:   setattr   implementation
    # GRACE: Purpose:  Status implementation
        # GRACE: Purpose:   init   implementation
        # GRACE: Purpose: text implementation
        # GRACE: Purpose: success implementation
    # GRACE: Purpose: fake cached implementation
# GRACE: Purpose: Test cached bounded crawl is streamlit cached
# GRACE: Purpose: Test crawl workflow mode registered
# GRACE: Purpose: Test crawl i18n keys have ru uk en values
# GRACE: Purpose: Test crawler config is top level and valid
# GRACE: Purpose: Test sidebar persists crawler namespace top level
# GRACE: Purpose:  serp fixture df implementation
# GRACE: Purpose: Test reverse math report treats ads metrics as enrichment
# GRACE: Purpose: Test reverse math report ads only does not create text profile
# GRACE: Purpose: Test reverse math report empty inputs show info
