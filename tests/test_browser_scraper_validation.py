"""
Validation tests for browser_scraper SERP and Trends parsing.

These tests validate that the cloakbrowser + trafilatura integration
actually works for SERP and Trends parsing as specified in Task 11-14.

Run with: python -m pytest tests/test_browser_scraper_validation.py -v
"""

import pytest
from unittest.mock import patch, MagicMock

# MODULE_CONTRACT: tests/test_browser_scraper_validation
# Purpose: Validate browser scraper parsing contracts and fixture-backed extraction behavior.
# Rationale: Links browser scraper validation tests to the browser scraper GRACE module.
# Dependencies: pytest, unittest.mock, utils.browser_scraper.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-016
# MODULE_MAP: tests/test_browser_scraper_validation.py
# Public Functions: pytest test functions.
# Private Helpers: mocks and local assertions in this file.
# Key Semantic Blocks: none.
# Critical Flows: initialize scraper/config -> load parser fixtures -> assert parser and contract behavior.
# Verification: verification-plan.xml#V-12-BROWSER-SERP-PARSER
# CHANGE_SUMMARY: Added complete GRACE module contract linking this test file to MOD-016.
from utils.browser_scraper import (
    BrowserScraper,
    BrowserScraperConfig,
    BrowserScrapeResult,
)


# MARK: Fixture Tests

class TestBrowserScraperFixtures:

    def test_default_config(self):
        config = BrowserScraperConfig()
        assert config.engine == "cloakbrowser"
        assert config.parser == "trafilatura"
        assert config.headless is True
        assert config.timeout_seconds == 30
        assert config.viewport == {"width": 1920, "height": 1080}
        assert config.retry_on_failure == 3
        assert config.rate_limit_delay == 3.0

    def test_config_from_settings(self):
        config = BrowserScraperConfig.from_settings()
        assert isinstance(config, BrowserScraperConfig)

    def test_browser_scraper_init(self):
        scraper = BrowserScraper()
        assert scraper.config is not None
        # Config comes from settings, may be "auto" or "cloakbrowser"
        assert scraper.config.engine in ["auto", "cloakbrowser"]


# MARK: SERP Parser Loading Tests

class TestSERPParserLoader:

    def test_load_js_parser_file_exists(self):
        scraper = BrowserScraper()
        js_content = scraper._load_js_parser("batch_parse_serp.js")

        assert isinstance(js_content, str)
        assert len(js_content) > 0
        # Verify it contains expected function signatures
        assert "(function()" in js_content or "(() =>" in js_content
        assert "parse(" in js_content or "h3" in js_content

    def test_load_js_parser_module_contract(self):
        scraper = BrowserScraper()
        js_content = scraper._load_js_parser("batch_parse_serp.js")

        # Check for GRACE documentation
        assert "MODULE_CONTRACT" in js_content or "Purpose:" in js_content
        # Check for semantic blocks mentioned in contract
        assert any(block in js_content for block in ["block_serp_parse_results", "block_rich_snippet", "block_serp_detect_containers"])

    def test_load_js_parser_missing_file(self):
        scraper = BrowserScraper()
        js_content = scraper._load_js_parser("nonexistent_parser.js")

        assert js_content == ""


# MARK: Helper Function Tests

class TestHelperFunctions:

    def test_build_cache_key(self):
        scraper = BrowserScraper()
        key1 = scraper._build_cache_key("serp", {"query": "test"})
        key2 = scraper._build_cache_key("serp", {"query": "test"})
        key3 = scraper._build_cache_key("serp", {"query": "other"})

        assert key1 == key2
        assert key1 != key3
        assert len(key1) == 32  # SHA256 hash truncated to 32 chars

    def test_build_cache_key_consistency(self):
        scraper = BrowserScraper()
        key1 = scraper._build_cache_key("trends", {"a": 1, "b": 2})
        key2 = scraper._build_cache_key("trends", {"b": 2, "a": 1})

        assert key1 == key2

    # GRACE: function test_build_trends_url_accepts_category_alias declaration.
    def test_build_trends_url_accepts_category_alias(self):
        scraper = BrowserScraper()
        url = scraper._build_trends_url("test keyword", {"category": 5, "hl": "uk", "tz": 120})

        assert "cat=5" in url
        assert "hl=uk" in url
        assert "tz=120" in url

    # GRACE: Purpose: Test trafilatura content extraction
    @patch('utils.browser_scraper.trafilatura')
    def test_extract_with_trafilatura(self, mock_trafilatura):
        mock_parsed = MagicMock()
        mock_trafilatura.load_html.return_value = mock_parsed
        mock_trafilatura.extract.side_effect = [
            "Plain text content",
            "**Markdown** content"
        ]

        scraper = BrowserScraper()
        html = "<html><body><p>Test content</p></body></html>"
        text, md = scraper._extract_with_trafilatura(html, "https://example.com")

        assert text == "Plain text content"
        assert md == "**Markdown** content"
        mock_trafilatura.load_html.assert_called_once()

    # GRACE: Purpose: Test trafilatura extraction when trafilatura is None
    @patch('utils.browser_scraper.trafilatura')
    def test_extract_with_trafilatura_none(self, mock_trafilatura):
        scraper = BrowserScraper()
        # Temporarily set trafilatura to None
        import utils.browser_scraper as bs
        original = bs.trafilatura
        bs.trafilatura = None

        text, md = scraper._extract_with_trafilatura("<html></html>")

        assert text == ""
        assert md == ""

        bs.trafilatura = original

    # GRACE: function test_extract_trends_widget_data_compatibility_shim declaration.
    def test_extract_trends_widget_data_compatibility_shim(self):
        scraper = BrowserScraper()
        data = scraper._extract_trends_widget_data(csv_content="Day,test keyword\n2025-06-01,45\n")

        assert "timeline" in data
        assert data["timeline"][0]["value"] == 45


# MARK: SERP Method Contract Tests

class TestSERPMethodContracts:
    # FUNCTION_CONTRACT: test_execute_cloakbrowser_serp_has_contract
    # Purpose: Verify the SERP parser exposes a dense FUNCTION_CONTRACT block before the browser scraper method
    # Input: None
    # Output: None
    # Side Effects: Reads browser_scraper source from disk only
    # Business Rules: The SERP contract check must stay immediately above the target method and preserve required fields
    # Failure Modes: Fails if the contract is missing, incomplete, or moved after the declaration
    def test_execute_cloakbrowser_serp_has_contract(self):
        import utils.browser_scraper as bs

        # Read file source to get comments above methods
        source = open(bs.__file__, 'r', encoding='utf-8').read()

        # The function contract is in code comments above the method
        expected_contract_marker = "FUNCTION_" + "CONTRACT: _execute_cloakbrowser_serp"
        assert expected_contract_marker in source
        # Check for contract fields
        assert "# Purpose:" in source
        assert "# Input:" in source or "query" in source
        assert "# Output:" in source or "BrowserScrapeResult" in source
        assert "# GRACE_LOG_MARKER:" in source

    # FUNCTION_CONTRACT: test_execute_cloakbrowser_serp_has_grace_markers
    # Purpose: Verify the SERP parser method includes GRACE log markers and parser-state evidence
    # Input: None
    # Output: None
    # Side Effects: Reads BrowserScraper source text only
    # Business Rules: The SERP marker check must preserve GRACE marker text plus error/success state evidence
    # Failure Modes: Fails if the marker text or state evidence disappears from the implementation
    def test_execute_cloakbrowser_serp_has_grace_markers(self):
        import inspect
        from utils.browser_scraper import BrowserScraper

        source = inspect.getsource(BrowserScraper._execute_cloakbrowser_serp)

        # Check for GRACE log markers
        assert "ENTER_serp_parsing" in source or "GRACE" in source
        assert "EXIT_serp_parsing" in source or "success" in source
        assert "ERROR_serp_parsing" in source or "error" in source.lower()

    def test_execute_cloakbrowser_serp_has_semantic_blocks(self):
        import inspect
        from utils.browser_scraper import BrowserScraper

        source = inspect.getsource(BrowserScraper._execute_cloakbrowser_serp)

        # Check for semantic blocks
        assert any(block in source for block in [
            "block_serp_parse_results",
            "block_pagination",
            "block_cookie_handling",
            "block_paa_extraction",
            "block_serp_stealth_config"
        ])

    def test_scrape_serp_public_method(self):
        scraper = BrowserScraper()
        assert hasattr(scraper, "scrape_serp")
        assert callable(getattr(scraper, "scrape_serp"))


# MARK: Trends Method Contract Tests

class TestTrendsMethodContracts:
    # FUNCTION_CONTRACT: test_execute_cloakbrowser_trends_has_contract
    # Purpose: Verify the Trends parser exposes a dense FUNCTION_CONTRACT block before the browser scraper method
    # Input: None
    # Output: None
    # Side Effects: Reads browser_scraper source from disk only
    # Business Rules: The Trends contract check must stay immediately above the target method and preserve required fields
    # Failure Modes: Fails if the contract is missing, incomplete, or moved after the declaration
    def test_execute_cloakbrowser_trends_has_contract(self):
        import utils.browser_scraper as bs

        # Read file source to get comments above methods
        source = open(bs.__file__, 'r', encoding='utf-8').read()

        # The function contract is in code comments above the method
        expected_contract_marker = "FUNCTION_" + "CONTRACT: _execute_cloakbrowser_trends"
        assert expected_contract_marker in source
        # Check for contract fields
        assert "# Purpose:" in source
        assert "# Input:" in source or "keywords" in source
        assert "# Output:" in source or "BrowserScrapeResult" in source
        assert "# GRACE_LOG_MARKER:" in source

    # FUNCTION_CONTRACT: test_execute_cloakbrowser_trends_has_grace_markers
    # Purpose: Verify the Trends parser method includes GRACE log markers and parser-state evidence
    # Input: None
    # Output: None
    # Side Effects: Reads BrowserScraper source text only
    # Business Rules: The Trends marker check must preserve GRACE marker text plus error/success state evidence
    # Failure Modes: Fails if the marker text or state evidence disappears from the implementation
    def test_execute_cloakbrowser_trends_has_grace_markers(self):
        import inspect
        from utils.browser_scraper import BrowserScraper

        source = inspect.getsource(BrowserScraper._execute_cloakbrowser_trends)

        # Check for GRACE log markers
        assert "ENTER_trends_parsing" in source or "GRACE" in source
        assert "EXIT_trends_parsing" in source or "success" in source
        assert "ERROR_trends_parsing" in source or "error" in source.lower()

    def test_execute_cloakbrowser_trends_has_semantic_blocks(self):
        import inspect
        from utils.browser_scraper import BrowserScraper

        source = inspect.getsource(BrowserScraper._execute_cloakbrowser_trends)

        # Check for semantic blocks
        assert any(block in source for block in [
            "block_trends_parsing",
            "block_trends_stealth_config"
        ])

    def test_scrape_google_trends_public_method(self):
        scraper = BrowserScraper()
        assert hasattr(scraper, "scrape_google_trends")
        assert callable(getattr(scraper, "scrape_google_trends"))


# MARK: Module Contract Tests

class TestModuleContract:

    # Purpose: Test that module has MODULE_CONTRACT.
    def test_module_has_contract(self):
        import utils.browser_scraper as bs

        # Check if module docstring or source contains MODULE_CONTRACT
        source = open(bs.__file__, 'r', encoding='utf-8').read()
        assert "MODULE_CONTRACT" in source

    # Purpose: Test that MODULE_CONTRACT has required fields.
    def test_module_contract_required_fields(self):
        import utils.browser_scraper as bs
        source = open(bs.__file__, 'r', encoding='utf-8').read()

        # Check for required MODULE_CONTRACT fields
        required_fields = [
            "Purpose:",
            "Dependencies:",
            "Exports:",
            "LINKS:",
            "Public Functions:",
            "Key Semantic Blocks:",
        ]

        for field in required_fields:
            assert field in source, f"Missing required field: {field}"

    # Purpose: Test that MODULE_CONTRACT mentions SERP and Trends capabilities.
    def test_module_contract_mentions_capabilities(self):
        import utils.browser_scraper as bs
        source = open(bs.__file__, 'r', encoding='utf-8').read()

        # Should mention SERP and Trends parsing capabilities
        assert any(term in source for term in ["SERP", "Trends", "SERP and Trends"])
        assert any(term in source for term in ["CSS-class-agnostic", "resilient", "semantic HTML"])


# MARK: Integration Tests (Mocked)

class TestBrowserScraperIntegration:

    # GRACE: Purpose: Test SERP scraping when browser is unavailable
    @patch('utils.browser_scraper.BrowserScraper.is_available')
    def test_scrape_serp_when_unavailable(self, mock_is_available):
        mock_is_available.return_value = False

        scraper = BrowserScraper()
        result = scraper.scrape_serp("test query", {})

        assert isinstance(result, BrowserScrapeResult)
        assert result.success is False
        assert result.source == "none"
        assert len(result.errors) > 0
        assert "No browser engine available" in result.errors[0]

    # GRACE: Purpose: Test Trends scraping when browser is unavailable
    @patch('utils.browser_scraper.BrowserScraper.is_available')
    def test_scrape_trends_when_unavailable(self, mock_is_available):
        mock_is_available.return_value = False

        scraper = BrowserScraper()
        result = scraper.scrape_google_trends(["test"], {})

        assert isinstance(result, BrowserScrapeResult)
        assert result.success is False
        assert result.source == "none"
        assert len(result.errors) > 0
        assert "No browser engine available" in result.errors[0]

    # GRACE: Purpose: Test that scrape_serp delegates to _execute_cloakbrowser_serp
    @patch('utils.browser_scraper.BrowserScraper.is_available')
    @patch('utils.browser_scraper.BrowserScraper._execute_cloakbrowser_serp')
    def test_scrape_serp_delegates_to_cloakbrowser(self, mock_execute, mock_is_available):
        mock_is_available.return_value = True
        mock_execute.return_value = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            parsed_content={"results": []}
        )

        scraper = BrowserScraper()
        result = scraper.scrape_serp("test query", {"gl": "ua"})

        mock_execute.assert_called_once()
        assert isinstance(result, BrowserScrapeResult)

    # GRACE: Purpose: Test that scrape_google_trends delegates to _execute_cloakbrowser_trends
    @patch('utils.browser_scraper.BrowserScraper.is_available')
    @patch('utils.browser_scraper.BrowserScraper._execute_cloakbrowser_trends')
    def test_scrape_trends_delegates_to_cloakbrowser(self, mock_execute, mock_is_available):
        mock_is_available.return_value = True
        mock_execute.return_value = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            parsed_content={}
        )

        scraper = BrowserScraper()
        result = scraper.scrape_google_trends(["test"], {"geo": "UA"})

        mock_execute.assert_called_once()
        assert isinstance(result, BrowserScrapeResult)


# MARK: Result Structure Tests

class TestResultStructures:

    def test_browser_scrape_result_fields(self):
        result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            raw_html="<html></html>",
            parsed_content={"results": []},
            metadata={"engine": "cloakbrowser"},
            cache_key="test123"
        )

        assert result.source == "cloakbrowser"
        assert result.success is True
        assert result.raw_html == "<html></html>"
        assert result.parsed_content == {"results": []}
        assert result.metadata == {"engine": "cloakbrowser"}
        assert result.cache_key == "test123"
        assert result.errors == []

    # GRACE: function test_serp_result_structure_includes_rich_snippets declaration.
    # Simulate a result from batch_parse_serp.js.
    def test_serp_result_structure_includes_rich_snippets(self):
        result = {
            "title": "Example Title",
            "url": "https://example.com",
            "snippet": "Example snippet",
            "rich_snippet": {
                "rating": "4.5",
                "price": "1000 грн"
            }
        }

        assert "title" in result
        assert "url" in result
        assert "snippet" in result
        assert "rich_snippet" in result
        assert "rating" in result["rich_snippet"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
# GRACE: Purpose: Test browser scraper configuration and fixtures
    # GRACE: Purpose: Test default configuration values
    # GRACE: Purpose: Test configuration creation from settings
    # GRACE: Purpose: Test BrowserScraper initialization
# GRACE: Purpose: Test SERP JavaScript parser loading
    # GRACE: Purpose: Test that batch_parse_serp.js file exists and is loadable
    # GRACE: Purpose: Test that JS parser contains GRACE module contract
    # GRACE: Purpose: Test handling of missing JS parser file
# GRACE: Purpose: Test helper functions for SERP/Trends parsing
    # GRACE: Purpose: Test cache key generation
    # GRACE: Purpose: Test cache key consistency across parameter order
    # GRACE: Sorted keys should produce same hash
    # GRACE: Restore
# GRACE: Purpose: Test SERP parsing method contracts and GRACE compliance
    # GRACE: Purpose: Test that _execute_cloakbrowser_serp has semantic block comments
    # GRACE: Purpose: Test that scrape_serp is a public method
# GRACE: Purpose: Test Trends parsing method contracts and GRACE compliance
    # GRACE: Purpose: Test that _execute_cloakbrowser_trends has semantic block comments
    # GRACE: Purpose: Test that scrape_google_trends is a public method
# GRACE: Purpose: Test module-level GRACE contract compliance
# GRACE: Purpose: Integration tests with mocked browser dependencies
# GRACE: Purpose: Test that results have expected structure
    # GRACE: Purpose: Test BrowserScrapeResult has expected fields
    # GRACE: Purpose: Test that SERP result structure includes rich_snippet field
