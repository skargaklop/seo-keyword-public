# TDD tests asserting _execute_cloakbrowser_trends matches the validated
#          beta_trends_parsing.py baseline EXACTLY. The validated script
#          (tmp/beta_trends_parsing.py, results in tmp/google_trends_test_results.md)
#          proved that MINIMAL cloakbrowser config works reliably, while
#          stealth_args/humanize/headless trigger IMMEDIATE 429.
# Reference: tmp/beta_trends_parsing.py, tmp/google_trends_test_results.md, Phase 16

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch


from utils.browser_scraper import BrowserScraper, BrowserScraperConfig

# --- Cloakbrowser mocking that works whether or not the package is installed ---
# The real cloakbrowser package is optional (see utils/browser_scraper.py import guard).
# patch("cloakbrowser.launch") requires the package to be importable, which fails on a
# clean install. Inject a fake module into sys.modules instead so both installed and
# uninstalled environments run the same code path.
def _patch_cloakbrowser_launch(launch_mock):
    """Return a context manager exposing a fake ``cloakbrowser.launch``.

    ``launch_mock`` is whatever the source's ``from cloakbrowser import launch``
    should resolve to (a MagicMock, or a real callable). The returned object is a
    context manager to be used in a ``with`` statement.
    """
    fake_module = MagicMock()
    fake_module.launch = launch_mock
    return patch.dict("sys.modules", {"cloakbrowser": fake_module})


# --- Beta baseline reference (from tmp/beta_trends_parsing.py main() + launch) ---
# The validated working launch kwargs are MINIMAL:
#     launch_kwargs = {"headless": args.headless, "locale": ..., "timezone": ...}
# stealth_args / geoip / humanize are all OFF by default and opt-in only.
# Context kwargs are equally minimal: accept_downloads, locale, timezone_id, storage_state.

BETA_LAUNCH_KEYS: set = {"headless", "locale", "timezone"}
BETA_CONTEXT_KEYS: set = {"accept_downloads", "locale", "timezone_id"}


# GRACE: function _run_execute declaration.
def _run_execute(params: Dict[str, Any], keywords: List[str]) -> tuple:
    scraper = BrowserScraper(BrowserScraperConfig.from_settings())

    captured: Dict[str, dict] = {"launch": {}, "context": {}}

    # Build a fake browser/context/page that drives the CSV path to success.
    fake_page = MagicMock()
    # chart loads -> wait_for_trends_chart returns True
    fake_page.get_by_text.return_value.first.wait_for.return_value = None
    # detect_block -> body inner_text with no markers
    fake_page.locator.return_value.inner_text.return_value = "Interest over time"
    # expect_download yields a download whose saved CSV is valid
    fake_download = MagicMock()
    # _download_trends_csv saves to a temp file and reads it; supply a valid CSV
    csv_text = (
        "Категорія: Усі категорії\n"
        "Регіон: Україна\n"
        "День,keyword planner: (Україна)\n"
        "2025-01-01 – 2025-01-07,45\n"
        "2025-01-08 – 2025-01-14,52\n"
    )

    # GRACE: function fake_expect_download declaration.
    def fake_expect_download(*a, **kw):
        def save_as(path, _csv=csv_text):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_csv)
        fake_download.save_as.side_effect = save_as
        return fake_download

    fake_page.expect_download = MagicMock()
    fake_page.expect_download.return_value.__enter__ = MagicMock(return_value=fake_download)
    fake_page.expect_download.return_value.__exit__ = MagicMock(return_value=False)

    # _download_trends_csv iterates selectors -> locator.count() > 0 -> nth(i).click
    fake_locator = MagicMock()
    fake_locator.count.return_value = 1
    fake_item = MagicMock()
    fake_item.is_visible.return_value = True
    fake_item.click.return_value = None
    fake_locator.nth.return_value = fake_item
    fake_page.locator.return_value = fake_locator

    # _maybe_accept_trends_cookies -> get_by_text(...).count() returns 0
    fake_cookie_btn = MagicMock()
    fake_cookie_btn.count.return_value = 0
    fake_page.get_by_text.return_value = fake_cookie_btn

    fake_context = MagicMock()
    fake_context.new_page.return_value = fake_page
    fake_context.storage_state = MagicMock()

    # GRACE: function fake_launch declaration.
    def fake_launch(**kwargs):
        captured["launch"] = dict(kwargs)
        fake_browser = MagicMock()
        def new_context(**ckwargs):
            captured["context"] = dict(ckwargs)
            return fake_context
        fake_browser.new_context.side_effect = new_context
        return fake_browser

    with _patch_cloakbrowser_launch(fake_launch), \
         patch.object(BrowserScraper, "_apply_rate_limit"):
        result = scraper._execute_cloakbrowser_trends(keywords, params)

    return result, captured["launch"], captured["context"]



class TestTrendsLaunchMatchesBetaBaseline:

    # GRACE: function test_launch_has_no_stealth_args declaration.
    def test_launch_has_no_stealth_args(self):
        _, launch_kwargs, _ = _run_execute(
            {"geo": "UA", "hl": "uk", "timeframe": "today 12-m"},
            ["keyword planner"],
        )
        assert not launch_kwargs.get("stealth_args", False), (
            "stealth_args is enabled — beta Test 4a proved this causes immediate 429. "
            "It must be absent or False to match the validated baseline."
        )

    # GRACE: function test_launch_has_no_humanize declaration.
    def test_launch_has_no_humanize(self):
        _, launch_kwargs, _ = _run_execute(
            {"geo": "UA", "hl": "uk", "timeframe": "today 12-m"},
            ["keyword planner"],
        )
        assert not launch_kwargs.get("humanize", False), (
            "humanize is force-enabled but the validated beta keeps it OFF by default. "
            "Remove it to match the baseline."
        )

    # GRACE: function test_launch_has_no_custom_args declaration.
    def test_launch_has_no_custom_args(self):
        _, launch_kwargs, _ = _run_execute(
            {"geo": "UA", "hl": "uk", "timeframe": "today 12-m"},
            ["keyword planner"],
        )
        assert "args" not in launch_kwargs, (
            f"Custom browser args present in launch kwargs: {launch_kwargs.get('args')}. "
            "The validated beta baseline passes NO custom args."
        )

    # GRACE: function test_launch_has_no_geoip declaration.
    def test_launch_has_no_geoip(self):
        _, launch_kwargs, _ = _run_execute(
            {"geo": "UA", "hl": "uk", "timeframe": "today 12-m"},
            ["keyword planner"],
        )
        assert not launch_kwargs.get("geoip", False), (
            "geoip is enabled — the validated beta keeps it OFF."
        )

    # GRACE: function test_launch_is_minimal_headless_locale_timezone declaration.
    def test_launch_is_minimal_headless_locale_timezone(self):
        _, launch_kwargs, _ = _run_execute(
            {"geo": "UA", "hl": "uk", "timeframe": "today 12-m", "locale": "uk-UA",
             "timezone": "Europe/Kyiv"},
            ["keyword planner"],
        )
        # Allow the baseline keys; forbid everything that adds fingerprint surface.
        forbidden = launch_kwargs.keys() - BETA_LAUNCH_KEYS
        assert not forbidden, (
            f"Unexpected launch kwargs beyond baseline {BETA_LAUNCH_KEYS}: {forbidden}"
        )



class TestTrendsContextMatchesBetaBaseline:

    # GRACE: function test_context_has_no_custom_user_agent declaration.
    def test_context_has_no_custom_user_agent(self):
        _, _, context_kwargs = _run_execute(
            {"geo": "UA", "hl": "uk", "timeframe": "today 12-m"},
            ["keyword planner"],
        )
        assert "user_agent" not in context_kwargs, (
            "Custom user_agent set on context — the validated beta does NOT set one. "
            "Removing it reduces automation fingerprint."
        )

    # GRACE: function test_context_has_no_custom_viewport declaration.
    def test_context_has_no_custom_viewport(self):
        _, _, context_kwargs = _run_execute(
            {"geo": "UA", "hl": "uk", "timeframe": "today 12-m"},
            ["keyword planner"],
        )
        assert "viewport" not in context_kwargs, (
            "Custom viewport set on context — the validated beta does NOT set one."
        )

    # GRACE: function test_context_has_no_extra_http_headers declaration.
    def test_context_has_no_extra_http_headers(self):
        _, _, context_kwargs = _run_execute(
            {"geo": "UA", "hl": "uk", "timeframe": "today 12-m"},
            ["keyword planner"],
        )
        assert "extra_http_headers" not in context_kwargs, (
            "extra_http_headers set on context — the validated beta does NOT set these."
        )

    # GRACE: function test_context_has_accept_downloads declaration.
    def test_context_has_accept_downloads(self):
        _, _, context_kwargs = _run_execute(
            {"geo": "UA", "hl": "uk", "timeframe": "today 12-m"},
            ["keyword planner"],
        )
        assert context_kwargs.get("accept_downloads") is True



class TestTrendsWarmupUsesManualStartWait:

    # GRACE: function test_manual_start_wait_triggers_warmup_navigation declaration.
    def test_manual_start_wait_triggers_warmup_navigation(self):
        scraper = BrowserScraper(BrowserScraperConfig.from_settings())

        navigations: List[str] = []

        fake_page = MagicMock()
        fake_page.get_by_text.return_value.first.wait_for.return_value = None
        fake_page.locator.return_value.inner_text.return_value = "Interest over time"
        # record every goto URL
        fake_page.goto.side_effect = lambda url, **kw: navigations.append(url) or None

        fake_context = MagicMock()
        fake_context.new_page.return_value = fake_page
        fake_context.storage_state = MagicMock()

        fake_browser = MagicMock()
        fake_browser.new_context.return_value = fake_context

        with _patch_cloakbrowser_launch(MagicMock(return_value=fake_browser)), \
             patch.object(BrowserScraper, "_apply_rate_limit"), \
             patch.object(BrowserScraper, "_download_trends_csv",
                          return_value="День,kw: (UA)\n2025-01-01,50\n"):
            scraper._execute_cloakbrowser_trends(
                ["keyword planner"],
                {"geo": "UA", "hl": "uk", "timeframe": "today 12-m",
                 "manual_start_wait": 30},
            )

        # The FIRST navigation must be the Trends home page (warmup), not the explore URL.
        assert navigations, "No page.goto calls were made at all"
        assert "https://trends.google.com/trends/" in navigations[0], (
            f"With manual_start_wait=30, warmup must navigate to the Trends home page first. "
            f"First navigation was: {navigations[0]}"
        )

    # GRACE: function test_zero_manual_start_wait_skips_warmup declaration.
    def test_zero_manual_start_wait_skips_warmup(self):
        scraper = BrowserScraper(BrowserScraperConfig.from_settings())

        navigations: List[str] = []
        fake_page = MagicMock()
        fake_page.get_by_text.return_value.first.wait_for.return_value = None
        fake_page.locator.return_value.inner_text.return_value = "Interest over time"
        fake_page.goto.side_effect = lambda url, **kw: navigations.append(url) or None

        fake_context = MagicMock()
        fake_context.new_page.return_value = fake_page
        fake_context.storage_state = MagicMock()
        fake_browser = MagicMock()
        fake_browser.new_context.return_value = fake_context

        with _patch_cloakbrowser_launch(MagicMock(return_value=fake_browser)), \
             patch.object(BrowserScraper, "_apply_rate_limit"), \
             patch.object(BrowserScraper, "_download_trends_csv",
                          return_value="День,kw: (UA)\n2025-01-01,50\n"):
            scraper._execute_cloakbrowser_trends(
                ["keyword planner"],
                {"geo": "UA", "hl": "uk", "timeframe": "today 12-m",
                 "manual_start_wait": 0},
            )

        if navigations:
            assert "/trends/explore" in navigations[0] or "q=" in navigations[0], (
                f"With manual_start_wait=0 the first nav should be the explore URL, got: {navigations[0]}"
            )



class TestTrendsHeadlessDefault:

    # GRACE: function test_trends_runs_non_headless_by_default declaration.
    def test_trends_runs_non_headless_by_default(self):
        _, launch_kwargs, _ = _run_execute(
            {"geo": "UA", "hl": "uk", "timeframe": "today 12-m"},
            ["keyword planner"],
        )
        assert launch_kwargs.get("headless") is False, (
            f"Trends launched headless={launch_kwargs.get('headless')} by default. "
            "The validated beta baseline runs NON-headless (--headless is opt-in and "
            "was never successfully tested)."
        )
        # GRACE: download.save_as writes csv_text to the requested path
        # GRACE: new_context kwargs captured here
# GRACE: MARK: Launch configuration must match validated beta baseline
# GRACE: MARK: Context configuration must match validated beta baseline
# GRACE: MARK: Warmup must use manual_start_wait (validated beta step)
# GRACE: MARK: Headless default for Trends must be non-headless (validated default)
