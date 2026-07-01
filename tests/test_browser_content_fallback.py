# MODULE_CONTRACT: tests/test_browser_content_fallback
# Purpose: TDD coverage for the url_llm browser fallback — WebScraper.scrape_urls_with_browser_fallback
#   orchestrator + BrowserScraper.scrape_content cloakbrowser delegate, settings keys, and i18n completeness
#   for the content-fallback UI labels. The fallback re-tries URLs that the requests-based scraper failed on
#   (captcha / Cloudflare turnstile / 403) via cloakbrowser, mirroring how trends/SERP already fall back.
# Dependencies: pytest, unittest.mock, utils.browser_scraper, utils.scraper, config.i18n, config.settings
# CHANGE_SUMMARY: RED phase — failing tests written before implementation

from unittest.mock import MagicMock, patch

import pytest

from config.i18n import TRANSLATIONS
from utils.browser_scraper import (
    BrowserScrapeResult,
    BrowserScraper,
    BrowserScraperConfig,
    DependencyStatus,
)
from utils.scraper import ScrapedContent, WebScraper


# ---------------------------------------------------------------------------
# BrowserScraper.scrape_content — public cloakbrowser delegate for arbitrary URLs
# ---------------------------------------------------------------------------


class TestScrapeContentAvailability:
    # Purpose: scrape_content is unavailable when no browser engine is installed.
    def test_scrape_content_unavailable_returns_failure(self) -> None:
        scraper = BrowserScraper()
        with patch.object(BrowserScraper, "is_available", return_value=False):
            result = scraper.scrape_content("https://example.com", {})
        assert result.success is False
        assert any("No browser engine available" in error for error in result.errors)


class TestScrapeContentDelegation:
    # Purpose: scrape_content delegates to _execute_cloakbrowser_content and returns its result.
    def test_scrape_content_delegates_to_cloakbrowser_executor(self) -> None:
        scraper = BrowserScraper(config=BrowserScraperConfig(rate_limit_delay=0))
        sentinel = BrowserScrapeResult(source="cloakbrowser", success=True, raw_html="<html/>")
        with patch.object(BrowserScraper, "is_available", return_value=True):
            with patch.object(scraper, "_execute_cloakbrowser_content", return_value=sentinel) as mock_exec:
                result = scraper.scrape_content("https://example.com", {"headless": True})
        assert result is sentinel
        mock_exec.assert_called_once()
        passed_url, passed_params = mock_exec.call_args.args
        assert passed_url == "https://example.com"
        assert passed_params["headless"] is True


# ---------------------------------------------------------------------------
# BrowserScraper._execute_cloakbrowser_content — cloakbrowser launch + extraction
# ---------------------------------------------------------------------------


class TestExecuteCloakbrowserContent:
    # Purpose: returns a missing-dependency failure when cloakbrowser cannot be imported.
    def test_execute_returns_failure_when_cloakbrowser_missing(self) -> None:
        scraper = BrowserScraper(config=BrowserScraperConfig(rate_limit_delay=0))
        # Force the inner `from cloakbrowser import launch` to raise ImportError.
        with patch.dict("sys.modules", {"cloakbrowser": None}):
            result = scraper._execute_cloakbrowser_content("https://example.com", {})
        assert result.success is False
        assert any("cloakbrowser" in error.lower() for error in result.errors)

    # Purpose: navigates the URL, detects no block, extracts via trafilatura, returns success.
    def test_execute_extracts_content_from_navigated_page(self) -> None:
        scraper = BrowserScraper(config=BrowserScraperConfig(rate_limit_delay=0, headless=True))
        mock_browser, mock_ctx, mock_page = MagicMock(), MagicMock(), MagicMock()
        mock_launch = MagicMock(return_value=mock_browser)
        mock_browser.new_context.return_value = mock_ctx
        mock_ctx.new_page.return_value = mock_page
        mock_page.content.return_value = "<html><body>Hello world article body text</body></html>"
        # No captcha / no turnstile present on the page.
        mock_page.query_selector.return_value = None
        mock_page.title.return_value = "Example Article"

        with patch("builtins.__import__", side_effect=_import_cloakbrowser_factory(mock_launch)):
            with patch.object(scraper, "_detect_captcha", return_value=False):
                with patch.object(scraper, "_detect_content_block", return_value=False):
                    with patch.object(
                        scraper,
                        "_parse_with_trafilatura",
                        return_value={"title": "Example Article", "text": "Hello world article body text"},
                    ):
                        result = scraper._execute_cloakbrowser_content("https://example.com", {"headless": True})

        mock_launch.assert_called_once()
        assert mock_launch.call_args.kwargs.get("headless") is True
        mock_page.goto.assert_called_once()
        assert result.success is True
        assert result.source == "cloakbrowser"
        assert result.parsed_content["text"] == "Hello world article body text"
        mock_browser.close.assert_called()

    # Purpose: when Cloudflare turnstile / challenge is detected, returns a blocked failure.
    def test_execute_returns_blocked_when_turnstile_detected(self) -> None:
        scraper = BrowserScraper(config=BrowserScraperConfig(rate_limit_delay=0))
        mock_browser, mock_ctx, mock_page = MagicMock(), MagicMock(), MagicMock()
        mock_launch = MagicMock(return_value=mock_browser)
        mock_browser.new_context.return_value = mock_ctx
        mock_ctx.new_page.return_value = mock_page
        mock_page.content.return_value = "<html>Just a moment...</html>"

        with patch("builtins.__import__", side_effect=_import_cloakbrowser_factory(mock_launch)):
            with patch.object(scraper, "_detect_captcha", return_value=False):
                with patch.object(scraper, "_detect_content_block", return_value=True):
                    result = scraper._execute_cloakbrowser_content("https://example.com", {})

        assert result.success is False
        assert any("block" in error.lower() or "captcha" in error.lower() or "turnstile" in error.lower()
                   for error in result.errors)
        mock_browser.close.assert_called()


def _import_cloakbrowser_factory(mock_launch: MagicMock):
    """Build a __import__ side effect that returns a fake cloakbrowser module exposing launch()."""
    fake_module = MagicMock()
    fake_module.launch = mock_launch

    def _import(name, *args, **kwargs):
        if name == "cloakbrowser":
            return fake_module
        # Defer everything else to the real import machinery.
        import importlib
        return importlib.import_module(name, *args[1:] if len(args) > 1 else None)

    return _import


# ---------------------------------------------------------------------------
# WebScraper.scrape_urls_with_browser_fallback — orchestrator
# ---------------------------------------------------------------------------


def _ok(url: str) -> ScrapedContent:
    return ScrapedContent(url=url, title="t", text="content", success=True)


def _failed(url: str, err: str = "403 Forbidden") -> ScrapedContent:
    return ScrapedContent(url=url, success=False, error=err)


class TestScrapeUrlsWithBrowserFallback:
    # Purpose: when all URLs succeed via the requests path, no browser fallback is invoked.
    def test_no_fallback_when_all_requests_succeed(self) -> None:
        urls = ["https://a.example", "https://b.example"]
        with patch.object(WebScraper, "scrape_urls", return_value=[_ok(urls[0]), _ok(urls[1])]):
            with patch("utils.browser_scraper.create_browser_scraper") as mock_factory:
                results = WebScraper.scrape_urls_with_browser_fallback(urls)
        assert all(r.success for r in results)
        mock_factory.assert_not_called()

    # Purpose: failed URLs are retried via the browser scraper when the toggle is on + deps available.
    def test_failed_urls_retried_via_browser(self) -> None:
        urls = ["https://a.example", "https://b.example"]
        # First URL failed requests-scrape (captcha); second succeeded.
        requests_results = [_failed(urls[0], "403 Forbidden"), _ok(urls[1])]

        browser_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            parsed_content={"title": "A", "text": "recovered body"},
            raw_html="<html/>",
        )
        mock_browser_scraper = MagicMock()
        mock_browser_scraper.scrape_content.return_value = browser_result

        with patch.object(WebScraper, "scrape_urls", return_value=requests_results):
            with patch("utils.browser_scraper.create_browser_scraper", return_value=mock_browser_scraper):
                with patch("utils.scraper.SCRAPER_CONFIG", {"content_browser_fallback_enabled": True}):
                    results = WebScraper.scrape_urls_with_browser_fallback(urls)

        # The failed URL was retried and recovered.
        recovered = [r for r in results if r.url == urls[0]]
        assert len(recovered) == 1
        assert recovered[0].success is True
        assert "recovered body" in recovered[0].text
        mock_browser_scraper.scrape_content.assert_called_once()
        assert mock_browser_scraper.scrape_content.call_args.args[0] == urls[0]

    # Purpose: when the toggle is disabled, failed URLs stay failed — no browser call.
    def test_disabled_toggle_skips_browser(self) -> None:
        urls = ["https://a.example"]
        with patch.object(WebScraper, "scrape_urls", return_value=[_failed(urls[0])]):
            with patch("utils.browser_scraper.create_browser_scraper") as mock_factory:
                with patch("utils.scraper.SCRAPER_CONFIG", {"content_browser_fallback_enabled": False}):
                    results = WebScraper.scrape_urls_with_browser_fallback(urls)
        assert results[0].success is False
        mock_factory.assert_not_called()

    # Purpose: when cloakbrowser deps are unavailable (create_browser_scraper returns None),
    # failed URLs stay failed — graceful degradation, no crash.
    def test_unavailable_browser_keeps_original_failure(self) -> None:
        urls = ["https://a.example"]
        with patch.object(WebScraper, "scrape_urls", return_value=[_failed(urls[0])]):
            with patch("utils.browser_scraper.create_browser_scraper", return_value=None):
                with patch("utils.scraper.SCRAPER_CONFIG", {"content_browser_fallback_enabled": True}):
                    results = WebScraper.scrape_urls_with_browser_fallback(urls)
        assert results[0].success is False
        assert results[0].url == urls[0]

    # Purpose: a browser retry that also fails leaves the original failure in place.
    def test_browser_retry_failure_keeps_original(self) -> None:
        urls = ["https://a.example"]
        browser_fail = BrowserScrapeResult(
            source="cloakbrowser", success=False, errors=["captcha"]
        )
        mock_browser_scraper = MagicMock()
        mock_browser_scraper.scrape_content.return_value = browser_fail
        with patch.object(WebScraper, "scrape_urls", return_value=[_failed(urls[0])]):
            with patch("utils.browser_scraper.create_browser_scraper", return_value=mock_browser_scraper):
                with patch("utils.scraper.SCRAPER_CONFIG", {"content_browser_fallback_enabled": True}):
                    results = WebScraper.scrape_urls_with_browser_fallback(urls)
        assert results[0].success is False
        assert results[0].url == urls[0]

    # Purpose: a requests-scrape that "succeeded" but landed on a Cloudflare / captcha
    # interstitial page must STILL be retried via the browser fallback. This is the
    # integration gap that makes the feature actually fire for the real failure mode
    # (challenge pages carry a <title>, so _extract_text marks them success=True).
    def test_blocked_success_row_still_retried_via_browser(self) -> None:
        urls = ["https://a.example"]
        # success=True but the content is a Cloudflare "Just a moment..." interstitial.
        requests_results = [
            ScrapedContent(
                url=urls[0],
                title="Just a moment...",
                text="Just a moment... Checking your browser before accessing the site.",
                success=True,
            )
        ]
        browser_result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            parsed_content={"title": "Real", "text": "real recovered body content"},
            raw_html="<html/>",
        )
        mock_browser_scraper = MagicMock()
        mock_browser_scraper.scrape_content.return_value = browser_result
        with patch.object(WebScraper, "scrape_urls", return_value=requests_results):
            with patch("utils.browser_scraper.create_browser_scraper", return_value=mock_browser_scraper):
                with patch("utils.scraper.SCRAPER_CONFIG", {"content_browser_fallback_enabled": True}):
                    results = WebScraper.scrape_urls_with_browser_fallback(urls)
        # Browser fallback fired despite the requests path reporting success.
        mock_browser_scraper.scrape_content.assert_called_once()
        assert mock_browser_scraper.scrape_content.call_args.args[0] == urls[0]
        assert results[0].success is True
        assert "real recovered body content" in results[0].text

    # Purpose: a genuine success (real content) must NOT be retried even though it shares
    # the success=True flag with blocked pages — _is_block_content must be selective.
    def test_real_success_row_not_retried(self) -> None:
        urls = ["https://a.example"]
        requests_results = [
            ScrapedContent(
                url=urls[0],
                title="How to bake sourdough bread",
                text="A detailed guide on baking sourdough bread at home with a starter.",
                success=True,
            )
        ]
        with patch.object(WebScraper, "scrape_urls", return_value=requests_results):
            with patch("utils.browser_scraper.create_browser_scraper") as mock_factory:
                with patch("utils.scraper.SCRAPER_CONFIG", {"content_browser_fallback_enabled": True}):
                    results = WebScraper.scrape_urls_with_browser_fallback(urls)
        mock_factory.assert_not_called()
        assert results[0].success is True

    # Purpose: when the browser ALSO lands on a block page (e.g. Akamai "Access Denied"),
    # the final result must be a FAILURE — never feed challenge/thin text to the LLM as content.
    # Covers the bestbuy.com case seen in live testing.
    def test_browser_lands_on_block_becomes_final_failure(self) -> None:
        urls = ["https://a.example"]
        # requests path: hard-failed 403.
        requests_results = [_failed(urls[0], "403 Forbidden")]
        # browser recovered — but to an Akamai "Access Denied" interstitial.
        browser_blocked = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            parsed_content={
                "title": "Access Denied",
                "text": "Access Denied Reference #18.350c4017 errors.edgesuite.net",
            },
            raw_html="<html/>",
        )
        mock_browser_scraper = MagicMock()
        mock_browser_scraper.scrape_content.return_value = browser_blocked
        with patch.object(WebScraper, "scrape_urls", return_value=requests_results):
            with patch("utils.browser_scraper.create_browser_scraper", return_value=mock_browser_scraper):
                with patch("utils.scraper.SCRAPER_CONFIG", {"content_browser_fallback_enabled": True}):
                    results = WebScraper.scrape_urls_with_browser_fallback(urls)
        # The browser fired (we asked it to), but its block-page output is rejected.
        assert results[0].success is False
        assert results[0].url == urls[0]
        # The error must explain it was a block, not a bare 403.
        assert results[0].error is not None
        assert any(t in results[0].error.lower() for t in ("block", "captcha", "denied", "challenge"))

    # Purpose: when the original row was a success-but-blocked requests page AND the browser
    # ALSO lands on a block, the final row is a forced failure — NOT the original block page.
    def test_browser_block_replaces_blocked_original_with_failure(self) -> None:
        urls = ["https://a.example"]
        requests_results = [
            ScrapedContent(
                url=urls[0],
                title="Just a moment...",
                text="Checking your browser before accessing the site.",
                success=True,
            )
        ]
        browser_blocked = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            parsed_content={"title": "Just a moment...", "text": "Checking your browser"},
            raw_html="<html/>",
        )
        mock_browser_scraper = MagicMock()
        mock_browser_scraper.scrape_content.return_value = browser_blocked
        with patch.object(WebScraper, "scrape_urls", return_value=requests_results):
            with patch("utils.browser_scraper.create_browser_scraper", return_value=mock_browser_scraper):
                with patch("utils.scraper.SCRAPER_CONFIG", {"content_browser_fallback_enabled": True}):
                    results = WebScraper.scrape_urls_with_browser_fallback(urls)
        assert results[0].success is False
        # Critical: the original block text is NOT returned (would be LLM food).
        assert "just a moment" not in (results[0].text or "").lower()

    # Purpose: regression guard — when the browser recovers REAL content, it still wins
    # (the block-detection must not over-trigger and discard good recoveries).
    def test_browser_real_recovery_wins_over_blocked_original(self) -> None:
        urls = ["https://a.example"]
        requests_results = [
            ScrapedContent(
                url=urls[0],
                title="Just a moment...",
                text="Checking your browser",
                success=True,
            )
        ]
        browser_ok = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            parsed_content={"title": "Real Article", "text": "real recovered body content here"},
            raw_html="<html/>",
        )
        mock_browser_scraper = MagicMock()
        mock_browser_scraper.scrape_content.return_value = browser_ok
        with patch.object(WebScraper, "scrape_urls", return_value=requests_results):
            with patch("utils.browser_scraper.create_browser_scraper", return_value=mock_browser_scraper):
                with patch("utils.scraper.SCRAPER_CONFIG", {"content_browser_fallback_enabled": True}):
                    results = WebScraper.scrape_urls_with_browser_fallback(urls)
        assert results[0].success is True
        assert "real recovered body content here" in results[0].text

    # Purpose: regression (task #4) — when the browser recovers real content, the
    # recovery must be PERSISTED to the scraping cache so the next rerun hits the good
    # result instead of re-scraping (and re-failing) the original path.
    def test_recovery_persists_to_cache(self) -> None:
        from utils import scraper as scraper_module
        from utils.cache import ScrapingCache

        fresh_cache = ScrapingCache(ttl_seconds=3600)
        urls = ["https://a.example"]
        requests_results = [
            ScrapedContent(url=urls[0], title="Just a moment...", text="Checking your browser", success=True),
        ]
        browser_ok = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            parsed_content={"title": "Real Article", "text": "real recovered body content here"},
            raw_html="<html/>",
        )
        mock_browser_scraper = MagicMock()
        mock_browser_scraper.scrape_content.return_value = browser_ok
        with patch.object(WebScraper, "scrape_urls", return_value=requests_results):
            with patch("utils.browser_scraper.create_browser_scraper", return_value=mock_browser_scraper):
                with patch("utils.scraper.SCRAPER_CONFIG", {"content_browser_fallback_enabled": True}):
                    with patch.object(scraper_module, "scraping_cache", fresh_cache):
                        results = WebScraper.scrape_urls_with_browser_fallback(urls)
        assert results[0].success is True
        # The recovered content must be in the cache, keyed by URL.
        cached = fresh_cache.get(urls[0])
        assert cached is not None
        assert getattr(cached, "success", False) is True
        assert "real recovered body content here" in getattr(cached, "text", "")

    # Purpose: regression (task #4) — when the browser ALSO lands on a block (forced
    # failure), the stale cached block page must be INVALIDATED so a later rerun does not
    # return the old block content as if it were valid.
    def test_forced_failure_invalidates_stale_cache(self) -> None:
        from utils import scraper as scraper_module
        from utils.cache import ScrapingCache

        fresh_cache = ScrapingCache(ttl_seconds=3600)
        urls = ["https://a.example"]
        # Simulate a stale block page already cached from a prior run.
        stale_block = ScrapedContent(
            url=urls[0], title="Just a moment...", text="Checking your browser", success=True,
        )
        fresh_cache.set(urls[0], stale_block)
        assert fresh_cache.get(urls[0]) is not None  # precondition

        requests_results = [stale_block]
        browser_blocked = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            parsed_content={"title": "Just a moment...", "text": "Checking your browser"},
            raw_html="<html/>",
        )
        mock_browser_scraper = MagicMock()
        mock_browser_scraper.scrape_content.return_value = browser_blocked
        with patch.object(WebScraper, "scrape_urls", return_value=requests_results):
            with patch("utils.browser_scraper.create_browser_scraper", return_value=mock_browser_scraper):
                with patch("utils.scraper.SCRAPER_CONFIG", {"content_browser_fallback_enabled": True}):
                    with patch.object(scraper_module, "scraping_cache", fresh_cache):
                        results = WebScraper.scrape_urls_with_browser_fallback(urls)
        assert results[0].success is False
        # The stale block page must no longer be served from cache.
        assert fresh_cache.get(urls[0]) is None


# ---------------------------------------------------------------------------
# WebScraper._is_block_content — detect a success=True row that is actually a block page
# ---------------------------------------------------------------------------


class TestIsBlockContent:
    # Purpose: a success=True row whose title/body carries Cloudflare/captcha markers
    # is flagged as a block page (needs browser retry).
    @pytest.mark.parametrize("title,text", [
        ("Just a moment...", "Checking your browser"),
        ("Attention Required! | Cloudflare", "enable JavaScript and cookies"),
        ("Are you a robot?", "captcha to verify you are human"),
    ])
    def test_block_marked_when_challenge_markers_present(self, title: str, text: str) -> None:
        row = ScrapedContent(url="https://x.example", title=title, text=text, success=True)
        assert WebScraper._is_block_content(row) is True

    # Purpose: genuine article content is NOT flagged as a block page.
    def test_not_block_for_real_content(self) -> None:
        row = ScrapedContent(
            url="https://x.example",
            title="Best hiking trails 2025",
            text="Here are the top hiking trails with detailed descriptions.",
            success=True,
        )
        assert WebScraper._is_block_content(row) is False

    # Purpose: a hard-failed row (success=False) is not "block content" — it's a plain
    # failure handled by the existing not-success branch, so _is_block_content returns False.
    def test_hard_failure_not_block(self) -> None:
        row = ScrapedContent(url="https://x.example", success=False, error="403 Forbidden")
        assert WebScraper._is_block_content(row) is False

    # Purpose: the shared detector now also covers the Akamai "Access Denied" interstitial
    # seen in live testing (bestbuy.com), so a browser-landed block is caught.
    def test_akamai_access_denied_detected(self) -> None:
        from utils.browser_scraper import _detect_content_block
        assert _detect_content_block("Access Denied Reference #18.350c4017.1782837754.558f768e") is True
        assert _detect_content_block("https://errors.edgesuite.net/18.350c4017.1782837754.558f768e") is True


# ---------------------------------------------------------------------------
# Settings + i18n completeness gate
# ---------------------------------------------------------------------------


class TestSettingsAndI18n:
    # Purpose: settings.yaml exposes the two new content-fallback keys with the spec'd defaults
    # (enabled default-on; headless default-on) — and they are bool.
    def test_settings_yaml_has_content_fallback_keys(self) -> None:
        from config.settings import SCRAPER_CONFIG
        assert "content_browser_fallback_enabled" in SCRAPER_CONFIG
        assert "content_browser_fallback_headless" in SCRAPER_CONFIG
        assert isinstance(SCRAPER_CONFIG["content_browser_fallback_enabled"], bool)
        assert isinstance(SCRAPER_CONFIG["content_browser_fallback_headless"], bool)
        assert SCRAPER_CONFIG["content_browser_fallback_enabled"] is True
        assert SCRAPER_CONFIG["content_browser_fallback_headless"] is True

    # Purpose: i18n completeness — every new label exists in ru/uk/en.
    @pytest.mark.parametrize("key", [
        "scraper_content_browser_fallback_enabled",
        "scraper_content_browser_fallback_enabled_help",
        "scraper_content_browser_fallback_headless",
    ])
    def test_i18n_keys_present_all_locales(self, key: str) -> None:
        assert key in TRANSLATIONS, f"missing i18n key: {key}"
        entry = TRANSLATIONS[key]
        for locale in ("ru", "uk", "en"):
            assert locale in entry, f"{key} missing locale {locale}"
            assert entry[locale].strip(), f"{key}.{locale} is empty"
