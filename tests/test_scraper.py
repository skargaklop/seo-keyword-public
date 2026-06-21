# Test coverage for modules: MOD-001,MOD-005
"""
Unit tests for scraper metadata extraction.
"""

import asyncio
import ssl
from types import SimpleNamespace

import pytest
import requests

from utils.scraper import ScrapedContent, WebScraper


# Purpose: TestWebScraperMetadata implementation
class TestWebScraperMetadata:
    # Purpose: Test extracts meta title description and keywords
    def test_extracts_meta_title_description_and_keywords(self) -> None:
        html = """
        <html>
          <head>
            <title>Test Product Page</title>
            <meta name=\"description\" content=\"Best product for testing SEO extraction.\" />
            <meta name=\"keywords\" content=\"seo, keyword research; ad campaigns\" />
          </head>
          <body>
            <main>
              This page contains enough body content to pass the minimum extraction threshold.
              It describes product features, pricing details, and common use cases for marketers.
            </main>
          </body>
        </html>
        """

        result = WebScraper._extract_text(html, "https://example.com/product")

        assert result.success is True
        assert result.title == "Test Product Page"
        assert result.meta_description == "Best product for testing SEO extraction."
        assert result.meta_keywords == ["seo", "keyword research", "ad campaigns"]
        assert "Meta title: Test Product Page" in result.text
        assert "Meta description: Best product for testing SEO extraction." in result.text
        assert "Meta keywords: seo, keyword research, ad campaigns" in result.text

    # Purpose: Test uses metadata fallback when body text is short
    def test_uses_metadata_fallback_when_body_text_is_short(self) -> None:
        html = """
        <html>
          <head>
            <title>Fallback Title</title>
            <meta name=\"description\" content=\"Description from meta tag for fallback mode.\" />
            <meta name=\"keywords\" content=\"fallback, metadata\" />
          </head>
          <body>short</body>
        </html>
        """

        result = WebScraper._extract_text(html, "https://example.com/fallback")

        assert result.success is True
        assert result.title == "Fallback Title"
        assert result.meta_description == "Description from meta tag for fallback mode."
        assert result.meta_keywords == ["fallback", "metadata"]
        assert "Meta title: Fallback Title" in result.text
        assert "Meta keywords: fallback, metadata" in result.text

    # Purpose: Test fails when text and metadata are missing
    def test_fails_when_text_and_metadata_are_missing(self) -> None:
        html = "<html><head></head><body>tiny</body></html>"

        result = WebScraper._extract_text(html, "https://example.com/empty")

        assert result.success is False
        assert result.error == "Insufficient text extracted"

    # Purpose: Test rejects redirect to private ip
    def test_rejects_redirect_to_private_ip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Purpose:  RedirectResponse implementation
        class _RedirectResponse:
            is_redirect = True
            is_permanent_redirect = False
            headers = {"Location": "http://10.0.0.1/private"}
            status_code = 302

            # Purpose: raise for status implementation
            def raise_for_status(self) -> None:
                return None

            # Purpose: close implementation
            def close(self) -> None:
                return None

        # Purpose:  FakeSession implementation
        class _FakeSession:
            # Purpose:   enter   implementation
            def __enter__(self):
                return self

            # Purpose:   exit   implementation
            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            # Purpose: get implementation
            # Purpose: get implementation
            @staticmethod
            def get(*args, **kwargs):
                return _RedirectResponse()

        monkeypatch.setattr("utils.scraper.trafilatura.fetch_url", lambda url: None)
        monkeypatch.setattr("utils.scraper.requests.Session", lambda: _FakeSession())

        with pytest.raises(ValueError):
            WebScraper._fetch_url("https://example.com")

    # Purpose: Test fetch url retries without ssl verification on certificate error
    def test_fetch_url_retries_without_ssl_verification_on_certificate_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "utils.url_safety.resolve_hostname_ips",
            lambda hostname: ["93.184.216.34"],
        )

        calls = []

        # Purpose:  SuccessfulResponse implementation
        class _SuccessfulResponse:
            is_redirect = False
            is_permanent_redirect = False
            headers = {}
            text = "<html><body>ok</body></html>"

            # Purpose:   init   implementation
            def __init__(self) -> None:
                sock = SimpleNamespace(getpeername=lambda: ("93.184.216.34", 443))
                self.raw = SimpleNamespace(_connection=SimpleNamespace(sock=sock))

            # Purpose: raise for status implementation
            def raise_for_status(self) -> None:
                return None

            # Purpose: close implementation
            def close(self) -> None:
                return None

        # Purpose:  FakeSession implementation
        class _FakeSession:
            # Purpose:   enter   implementation
            def __enter__(self):
                return self

            # Purpose:   exit   implementation
            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            # Purpose: get implementation
            # Purpose: get implementation
            @staticmethod
            def get(*args, **kwargs):
                calls.append(
                    {
                        "verify": kwargs.get("verify", True),
                        "stream": kwargs.get("stream", False),
                    }
                )
                if len(calls) == 1:
                    raise requests.exceptions.SSLError(
                        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
                    )
                return _SuccessfulResponse()

        monkeypatch.setattr("utils.scraper.requests.Session", lambda: _FakeSession())

        html = WebScraper._fetch_url.__wrapped__("https://example.com")

        assert html == "<html><body>ok</body></html>"
        assert calls == [
            {"verify": True, "stream": True},
            {"verify": False, "stream": True},
        ]

    # Purpose: Test async scraper falls back to sync on certificate error
    def test_async_scraper_falls_back_to_sync_on_certificate_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Purpose:  raise ssl implementation
        async def _raise_ssl(*args, **kwargs):
            raise ssl.SSLCertVerificationError(
                1, "certificate verify failed: unable to get local issuer certificate"
            )

        monkeypatch.setattr("utils.scraper.WebScraper._fetch_url_async", _raise_ssl)
        monkeypatch.setattr(
            "utils.scraper.WebScraper.scrape_url",
            lambda url: ScrapedContent(url=url, text="sync fallback", success=True),
        )

        result = asyncio.run(
            WebScraper._scrape_url_async("https://example.com", session=None)
        )

        assert result.success is True
        assert result.text == "sync fallback"