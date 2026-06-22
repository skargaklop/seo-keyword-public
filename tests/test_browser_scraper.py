# Test coverage for module: MOD-016
"""
Unit tests for browser scraper module (OPT-IN feature).

Tests verify graceful handling when dependencies are not installed and
correct behavior when dependencies are present. Tests are skipped
gracefully when optional dependencies are missing.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Optional local capture (tmp/tsk.html) is not checked into the repo. Tests that
# depend on it skip gracefully when the fixture is absent.
_TSK_HTML_PATH = Path("tmp/tsk.html")
_TSK_HTML_AVAILABLE = _TSK_HTML_PATH.exists()

from utils.browser_scraper import (
    BrowserScraper,
    BrowserScraperConfig,
    BrowserScrapeResult,
    DependencyStatus,
    _check_dependency,
    _detect_serp_block,
    build_optional_dependency_install_command,
    create_browser_scraper,
    get_problem_dependencies,
)


class TestDependencyChecking:

    def test_check_dependencies_returns_status(self) -> None:
        deps = BrowserScraper.check_dependencies()
        assert isinstance(deps, dict)
        assert all(isinstance(status, DependencyStatus) for status in deps.values())
        assert "trafilatura" in deps

    def test_check_dependencies_caches_results(self) -> None:
        deps1 = BrowserScraper.check_dependencies()
        deps2 = BrowserScraper.check_dependencies()
        assert deps1 is deps2

    # GRACE: function test_check_dependency_function declaration.
    # Test with a known installed package.
    def test_check_dependency_function(self) -> None:
        status = _check_dependency("sys")
        assert status == DependencyStatus.AVAILABLE

    def test_check_dependency_validates_required_api(self) -> None:
        assert _check_dependency("sys", ("path",)) == DependencyStatus.AVAILABLE
        assert _check_dependency("sys", ("missing_browser_api",)) == DependencyStatus.UNUSABLE

    def test_check_dependencies_include_parsers(self) -> None:
        deps = BrowserScraper.check_dependencies()
        for package_name in ("cloakbrowser", "trafilatura"):
            assert package_name in deps

    def test_dependency_install_command_scope(self) -> None:
        project_command = build_optional_dependency_install_command("project")
        global_command = build_optional_dependency_install_command("global")
        assert project_command.startswith("python -m pip install --upgrade")
        assert "--user" not in project_command
        assert global_command.startswith("python -m pip install --user --upgrade")
        for package_name in ("cloakbrowser", "trafilatura"):
            assert package_name in project_command
            assert package_name in global_command

    def test_get_problem_dependencies_filters_available(self) -> None:
        result = get_problem_dependencies({
            "cloakbrowser": DependencyStatus.UNUSABLE,
            "trafilatura": DependencyStatus.AVAILABLE,
        })
        assert result == {
            "cloakbrowser": DependencyStatus.UNUSABLE,
        }

    def test_is_available_when_no_engines_installed(self, monkeypatch) -> None:
        with patch.object(BrowserScraper, 'check_dependencies', return_value={
            "cloakbrowser": DependencyStatus.MISSING,
            "trafilatura": DependencyStatus.AVAILABLE,
        }):
            assert BrowserScraper.is_available() is False

    def test_is_available_when_cloakbrowser_installed(self, monkeypatch) -> None:
        with patch.object(BrowserScraper, 'check_dependencies', return_value={
            "cloakbrowser": DependencyStatus.AVAILABLE,
            "trafilatura": DependencyStatus.AVAILABLE,
        }):
            assert BrowserScraper.is_available() is True

    def test_is_available_requires_a_parser(self, monkeypatch) -> None:
        with patch.object(BrowserScraper, 'check_dependencies', return_value={
            "cloakbrowser": DependencyStatus.AVAILABLE,
            "trafilatura": DependencyStatus.MISSING,
        }):
            assert BrowserScraper.is_available() is False

    def test_dependency_install_message_includes_project_and_global_commands(self) -> None:
        with patch.object(BrowserScraper, 'check_dependencies', return_value={
            "cloakbrowser": DependencyStatus.MISSING,
            "trafilatura": DependencyStatus.MISSING,
        }):
            message = BrowserScraper.dependency_install_message()

        assert message is not None
        assert "python -m pip install cloakbrowser playwright trafilatura" in message
        assert "python -m pip install --user --upgrade cloakbrowser playwright trafilatura" in message


class TestBrowserScraperConfig:

    def test_default_config(self) -> None:
        config = BrowserScraperConfig()
        assert config.engine == "cloakbrowser"
        assert config.parser == "trafilatura"
        assert config.headless is True
        assert config.timeout_seconds == 30
        assert config.retry_on_failure == 3
        assert config.rate_limit_delay == 3.0

    def test_config_from_settings_dict(self) -> None:
        settings = {
            "engine": "cloakbrowser",
            "parser": "trafilatura",
            "headless": False,
            "timeout_seconds": 60,
            "retry_on_failure": 5,
            "rate_limit_delay": 5.0,
        }
        config = BrowserScraperConfig.from_settings(settings)
        assert config.engine == "cloakbrowser"
        assert config.parser == "trafilatura"
        assert config.headless is False
        assert config.timeout_seconds == 60
        assert config.retry_on_failure == 5
        assert config.rate_limit_delay == 5.0

    def test_config_with_proxy(self) -> None:
        config = BrowserScraperConfig(proxy="http://proxy.example.com:8080")
        assert config.proxy == "http://proxy.example.com:8080"

    def test_config_with_custom_viewport(self) -> None:
        config = BrowserScraperConfig(viewport={"width": 1280, "height": 720})
        assert config.viewport == {"width": 1280, "height": 720}


class TestBrowserScrapeResult:

    def test_default_result(self) -> None:
        result = BrowserScrapeResult(source="none")
        assert result.source == "none"
        assert result.raw_html is None
        assert result.parsed_content == {}
        assert result.extracted_data is None
        assert result.metadata == {}
        assert result.errors == []
        assert result.cache_key == ""
        assert result.success is True

    def test_result_with_data(self) -> None:
        result = BrowserScrapeResult(
            source="cloakbrowser",
            raw_html="<html>test</html>",
            parsed_content={"title": "Test"},
            cache_key="abc123",
        )
        assert result.source == "cloakbrowser"
        assert result.raw_html == "<html>test</html>"
        assert result.parsed_content == {"title": "Test"}
        assert result.cache_key == "abc123"

    def test_result_with_errors(self) -> None:
        result = BrowserScrapeResult(
            source="cloakbrowser",
            success=False,
            errors=["CAPTCHA detected", "Timeout"],
        )
        assert result.success is False
        assert result.errors == ["CAPTCHA detected", "Timeout"]


class TestCacheKeyGeneration:

    def test_build_cache_key_simple(self) -> None:
        scraper = BrowserScraper()
        key = scraper._build_cache_key("trends", {"geo": "UA", "timeframe": "today 12-m"})
        assert isinstance(key, str)
        assert len(key) == 32  # SHA256 truncated to 32 chars

    def test_build_cache_key_with_keywords(self) -> None:
        scraper = BrowserScraper()
        key1 = scraper._build_cache_key("trends", {"keywords": ["keyword1", "keyword2"]})
        key2 = scraper._build_cache_key("trends", {"keywords": ["keyword1", "keyword2"]})
        key3 = scraper._build_cache_key("trends", {"keywords": ["keyword3"]})
        assert key1 == key2
        assert key1 != key3

    def test_build_cache_key_different_kinds(self) -> None:
        scraper = BrowserScraper()
        key1 = scraper._build_cache_key("trends", {"geo": "UA"})
        key2 = scraper._build_cache_key("serp", {"geo": "UA"})
        assert key1 != key2


@pytest.mark.skipif(
    _check_dependency("trafilatura", ("extract", "extract_metadata")) != DependencyStatus.AVAILABLE,
    reason="trafilatura not installed or unusable",
)
class TestTrafilaturaParser:

    def test_parse_with_trafilatura_basic_html(self) -> None:
        scraper = BrowserScraper()
        html = """
        <html>
            <head>
                <title>Test Page</title>
                <meta name="description" content="Test description" />
            </head>
            <body>
                <p>This is test content for parsing.</p>
            </body>
        </html>
        """
        result = scraper._parse_with_trafilatura(html, "https://example.com")
        assert isinstance(result, dict)
        assert "text" in result

    def test_parse_with_trafilatura_empty_html(self) -> None:
        scraper = BrowserScraper()
        result = scraper._parse_with_trafilatura("", "https://example.com")
        assert isinstance(result, dict)

    def test_parse_with_trafilatura_missing_dependency(self, monkeypatch) -> None:
        scraper = BrowserScraper()
        monkeypatch.setattr("utils.browser_scraper.trafilatura", None)
        BrowserScraper._dependency_cache = {}
        with patch.object(scraper, 'check_dependencies', return_value={
            "cloakbrowser": DependencyStatus.AVAILABLE,
            "trafilatura": DependencyStatus.MISSING,
        }):
            result = scraper._parse_with_trafilatura("<html></html>", "https://example.com")

        assert result == {}


class TestMissingParserHandling:

    def test_parse_with_trafilatura_missing_returns_empty_dict(self) -> None:
        scraper = BrowserScraper()
        with patch.object(scraper, 'check_dependencies', return_value={
            "cloakbrowser": DependencyStatus.MISSING,
            "trafilatura": DependencyStatus.MISSING,
        }):
            result = scraper._parse_with_trafilatura("<html></html>", "https://example.com")
        assert result == {}


class TestRateLimiting:

    def test_rate_limit_first_call(self) -> None:
        scraper = BrowserScraper(config=BrowserScraperConfig(rate_limit_delay=1.0))
        start = time.monotonic()
        scraper._apply_rate_limit()
        elapsed = time.monotonic() - start
        assert elapsed < 0.5  # Should be nearly instant on first call

    def test_rate_limit_subsequent_calls(self) -> None:
        scraper = BrowserScraper(config=BrowserScraperConfig(rate_limit_delay=0.5))
        scraper._rate_limit_last = time.monotonic()
        start = time.monotonic()
        scraper._apply_rate_limit()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.4  # Should delay (with small tolerance)

    def test_rate_limit_uses_monotonic_clock(self) -> None:
        scraper = BrowserScraper(config=BrowserScraperConfig(rate_limit_delay=0.5))
        with patch("utils.browser_scraper.time.monotonic", side_effect=[10.0, 10.5]):
            with patch("utils.browser_scraper.time.sleep") as sleep_mock:
                scraper._apply_rate_limit()

        sleep_mock.assert_not_called()
        assert scraper._rate_limit_last == 10.5


class TestGoogleTrendsScraping:

    def test_scrape_trends_no_engines_available(self) -> None:
        scraper = BrowserScraper()
        with patch.object(BrowserScraper, 'is_available', return_value=False):
            result = scraper.scrape_google_trends(["keyword"], {"geo": "UA"})
            assert result.success is False
            assert any("No browser engine available" in error for error in result.errors)

    def test_scrape_trends_cloakbrowser_not_installed(self) -> None:
        scraper = BrowserScraper()
        with patch.object(BrowserScraper, 'is_available', return_value=True):
            with patch('utils.browser_scraper._check_dependency', return_value=DependencyStatus.MISSING):
                result = scraper.scrape_google_trends(["keyword"], {"geo": "UA"})
                # Should fail with import error
                assert result.success is False

    def test_scrape_trends_with_mocked_cloakbrowser(self) -> None:
        scraper = BrowserScraper(config=BrowserScraperConfig(rate_limit_delay=0))
        mock_browser_class = MagicMock()
        mock_browser_instance = MagicMock()
        mock_page = MagicMock()

        mock_browser_instance.__enter__ = MagicMock(return_value=mock_browser_instance)
        mock_browser_instance.__exit__ = MagicMock(return_value=False)
        mock_browser_instance.new_page.return_value = mock_page
        mock_browser_class.return_value = mock_browser_instance

        with patch.object(BrowserScraper, 'is_available', return_value=True):
            with patch('utils.browser_scraper._check_dependency', return_value=DependencyStatus.AVAILABLE):
                with patch.object(scraper, '_wait_for_dynamic_content'):
                    with patch.object(scraper, '_detect_captcha', return_value=False):
                        with patch.object(scraper, '_maybe_accept_trends_cookies', return_value=False):
                            with patch.object(scraper, '_wait_for_trends_chart', return_value=True):
                                with patch.object(scraper, '_download_trends_csv', return_value="Day,keyword\n2025-06-01,45\n"):
                                    with patch.object(scraper, '_extract_trends_widget_data', return_value={"html": "<html>test</html>"}):
                                        with patch.dict('sys.modules', {'cloakbrowser': MagicMock(Browser=mock_browser_class)}):
                                            result = scraper.scrape_google_trends(["keyword"], {"geo": "UA"})
                                        assert result.source == "cloakbrowser"
                                        assert result.success is True

    # GRACE: function test_extract_trends_widget_data_preserves_html_payload declaration.
    @pytest.mark.skipif(
        not _TSK_HTML_AVAILABLE,
        reason="Optional local fixture tmp/tsk.html not present",
    )
    def test_extract_trends_widget_data_preserves_html_payload(self) -> None:
        scraper = BrowserScraper()
        html = _TSK_HTML_PATH.read_text(encoding="utf-8", errors="replace")

        data = scraper._extract_trends_widget_data(html)

        assert "html" in data
        assert "timeline" not in data


class TestSERPScraping:

    def test_scrape_serp_no_engines_available(self) -> None:
        scraper = BrowserScraper()
        with patch.object(BrowserScraper, 'is_available', return_value=False):
            result = scraper.scrape_serp("test query", {"gl": "ua"})
            assert result.success is False
            assert any("No browser engine available" in error for error in result.errors)

    def test_scrape_serp_with_mocked_cloakbrowser(self) -> None:
        scraper = BrowserScraper(config=BrowserScraperConfig(rate_limit_delay=0))
        mock_browser_class = MagicMock()
        mock_browser_instance = MagicMock()
        mock_page = MagicMock()

        mock_browser_instance.__enter__ = MagicMock(return_value=mock_browser_instance)
        mock_browser_instance.__exit__ = MagicMock(return_value=False)
        mock_browser_instance.new_page.return_value = mock_page
        mock_browser_class.return_value = mock_browser_instance

        with patch.object(BrowserScraper, 'is_available', return_value=True):
            with patch('utils.browser_scraper._check_dependency', return_value=DependencyStatus.AVAILABLE):
                with patch.object(scraper, '_wait_for_dynamic_content'):
                    with patch.object(scraper, '_detect_captcha', return_value=False):
                        with patch.object(scraper, '_extract_serp_data', return_value={"organic": []}):
                            with patch.dict('sys.modules', {'cloakbrowser': MagicMock(Browser=mock_browser_class)}):
                                result = scraper.scrape_serp("test query", {"gl": "ua"})
                            assert result.source == "cloakbrowser"
                            assert result.success is False


class TestCAPTCHADetection:

    def test_detect_captcha_with_recaptcha_div(self) -> None:
        scraper = BrowserScraper()
        mock_page = MagicMock()
        mock_element = MagicMock()
        mock_element.is_visible.return_value = True
        mock_page.query_selector.return_value = mock_element

        result = scraper._detect_captcha(mock_page)
        assert result is True

    def test_detect_captcha_with_page_title(self) -> None:
        scraper = BrowserScraper()
        mock_page = MagicMock()
        mock_page.query_selector.return_value = None
        mock_page.title.return_value = "Prove you are human - unusual traffic"

        result = scraper._detect_captcha(mock_page)
        assert result is True

    def test_detect_captcha_no_captcha(self) -> None:
        scraper = BrowserScraper()
        mock_page = MagicMock()
        mock_page.query_selector.return_value = None
        mock_page.title.return_value = "Google Search"

        result = scraper._detect_captcha(mock_page)
        assert result is False


class TestSERPBlockDetection:

    def test_detect_serp_block_with_google_429_text(self) -> None:
        body_text = "Our systems have detected unusual traffic from your computer network. Error 429"

        assert _detect_serp_block(body_text) is True

    def test_detect_serp_block_ignores_normal_results_page(self) -> None:
        body_text = "Google Search Result stats Example Domain People also ask"

        assert _detect_serp_block(body_text) is False


class TestCreateBrowserScraper:

    def test_create_browser_scraper_with_disabled_setting(self, monkeypatch) -> None:
        mock_settings = {"scraper": {"browser_enabled": False}}
        with patch('utils.browser_scraper.load_config', return_value=mock_settings):
            scraper = create_browser_scraper()
            assert scraper is None

    def test_create_browser_scraper_no_engines_installed(self, monkeypatch) -> None:
        mock_settings = {"scraper": {"browser_enabled": True}}
        with patch('utils.browser_scraper.load_config', return_value=mock_settings):
            with patch.object(BrowserScraper, 'is_available', return_value=False):
                scraper = create_browser_scraper()
                assert scraper is None

    def test_create_browser_scraper_success(self, monkeypatch) -> None:
        mock_settings = {"scraper": {"browser_enabled": True}}
        with patch('utils.browser_scraper.load_config', return_value=mock_settings):
            with patch.object(BrowserScraper, 'is_available', return_value=True):
                scraper = create_browser_scraper()
                assert isinstance(scraper, BrowserScraper)

    def test_create_browser_scraper_with_custom_config(self) -> None:
        config = BrowserScraperConfig(engine="cloakbrowser")
        mock_settings = {"scraper": {"browser_enabled": True}}
        with patch('utils.browser_scraper.load_config', return_value=mock_settings):
            with patch.object(BrowserScraper, 'is_available', return_value=True):
                scraper = create_browser_scraper(config)
                assert scraper.config.engine == "cloakbrowser"


# GRACE: class TestSkipOnMissingDependencies declaration.
# Covers behavior when cloakbrowser is unavailable or unusable.
class TestSkipOnMissingDependencies:
    @pytest.mark.skipif(
        _check_dependency("cloakbrowser", ("Browser",)) != DependencyStatus.AVAILABLE,
        reason="cloakbrowser not installed or unusable"
    )
    def test_real_cloakbrowser_dependency_available(self) -> None:
        try:
            import cloakbrowser
            assert cloakbrowser is not None
        except ImportError:
            pytest.skip("cloakbrowser check failed during import")


class TestUrlEncoding:

    def test_encode_params_basic(self) -> None:
        scraper = BrowserScraper()
        params = {"q": "test query", "gl": "ua"}
        encoded = scraper._encode_params(params)
        assert "q=test+query" in encoded or "q=test%20query" in encoded
        assert "gl=ua" in encoded

    def test_encode_params_empty(self) -> None:
        scraper = BrowserScraper()
        encoded = scraper._encode_params({})
        assert encoded == ""

    def test_encode_params_unicode(self) -> None:
        scraper = BrowserScraper()
        params = {"q": "тест", "hl": "uk"}
        encoded = scraper._encode_params(params)
        assert "hl=uk" in encoded
# GRACE: Purpose: Tests for dependency detection functionality
    # GRACE: Purpose: Test that dependency checking returns valid status
    # GRACE: Purpose: Test that dependency check results are cached
    # GRACE: Purpose: Test individual dependency check function
    # GRACE: Purpose: Installed packages without the expected API are marked unusable
    # GRACE: Purpose: Browser dependency checks include both engines and parser tools
    # GRACE: Purpose: Install command offers project and global user Python variants
    # GRACE: Purpose: Only non-available dependencies should trigger the install prompt
    # GRACE: Purpose: Test is_available returns False when no engines installed
    # GRACE: Purpose: Test is_available returns True when cloakbrowser installed
    # GRACE: Purpose: Test is_available returns False when parser dependencies are missing
    # GRACE: Purpose: Test install guidance includes both project and global commands
# GRACE: Purpose: Tests for browser scraper configuration
    # GRACE: Purpose: Test default configuration values
    # GRACE: Purpose: Test creating config from settings dict
    # GRACE: Purpose: Test config with proxy setting
    # GRACE: Purpose: Test config with custom viewport
# GRACE: Purpose: Tests for browser scrape result dataclass
    # GRACE: Purpose: Test default result values
    # GRACE: Purpose: Test result with populated data
    # GRACE: Purpose: Test result with error list
# GRACE: Purpose: Tests for cache key generation
    # GRACE: Purpose: Test cache key generation with simple params
    # GRACE: Purpose: Test cache key generation includes keywords
    # GRACE: Purpose: Test cache key differs by kind
# GRACE: Purpose: Tests for trafilatura parser
    # GRACE: Purpose: Test parsing basic HTML with trafilatura
    # GRACE: Purpose: Test parsing empty HTML
    # GRACE: Purpose: Test parsing returns an empty dict when trafilatura is unavailable
# GRACE: Purpose: Tests for graceful behavior when no HTML parser is usable
    # GRACE: Purpose: Test parse with trafilatura missing returns empty dict
# GRACE: Purpose: Tests for rate limiting functionality
    # GRACE: Purpose: Test first call has no delay
    # GRACE: Purpose: Test rate limit delay on subsequent calls
    # GRACE: Purpose: Rate limit state should be measured with a monotonic clock
# GRACE: Purpose: Tests for Google Trends scraping
    # GRACE: Purpose: Test trends scraping fails gracefully when no engines available
    # GRACE: Purpose: Test trends scraping handles missing cloakbrowser
    # GRACE: Purpose: Test trends scraping with mocked cloakbrowser
# GRACE: Purpose: Tests for SERP scraping
    # GRACE: Purpose: Test SERP scraping fails gracefully when no engines available
    # GRACE: Purpose: Test SERP scraping with mocked cloakbrowser
# GRACE: Purpose: Tests for CAPTCHA detection
    # GRACE: Purpose: Test CAPTCHA detection with recaptcha div
    # GRACE: Purpose: Test CAPTCHA detection via page title
    # GRACE: Purpose: Test CAPTCHA detection returns False when no CAPTCHA
# GRACE: Purpose: Tests for factory function
    # GRACE: Purpose: Test factory returns None when browser scraping disabled
    # GRACE: Purpose: Test factory returns None when no engines installed
    # GRACE: Purpose: Test factory returns scraper when available and enabled
    # GRACE: Purpose: Test factory with custom config
# GRACE: Purpose: Tests that skip gracefully when dependencies are missing
    # GRACE: Purpose: This test only runs when cloakbrowser is installed
# GRACE: Purpose: Tests for URL parameter encoding
    # GRACE: Purpose: Test basic URL parameter encoding
    # GRACE: Purpose: Test encoding empty parameters
    # GRACE: Purpose: Test encoding with Unicode characters
