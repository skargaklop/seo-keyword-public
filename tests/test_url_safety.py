from types import SimpleNamespace

import pytest
import requests

from utils.scraper import WebScraper
from utils.url_safety import URLSafetyError, validate_safe_url


class TestValidateSafeUrl:
    def test_allows_public_http_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "utils.url_safety.resolve_hostname_ips",
            lambda hostname: ["93.184.216.34"],
        )

        parsed = validate_safe_url("https://example.com/path")

        assert parsed.hostname == "example.com"
        assert parsed.scheme == "https"

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost",
            "http://127.0.0.1",
            "http://127.1",
            "http://10.0.0.1",
            "http://192.168.1.10",
            "http://172.16.0.5",
            "http://169.254.169.254",
            "http://[::1]",
            "ftp://example.com",
        ],
    )
    def test_blocks_known_unsafe_targets(self, url: str) -> None:
        with pytest.raises(URLSafetyError):
            validate_safe_url(url)

    def test_blocks_domains_resolving_to_private_addresses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "utils.url_safety.resolve_hostname_ips",
            lambda hostname: ["10.10.0.5"],
        )

        with pytest.raises(URLSafetyError):
            validate_safe_url("https://internal.example")

    def test_scraper_rejects_connection_when_peer_ip_differs_from_validated_dns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "utils.url_safety.resolve_hostname_ips",
            lambda hostname: ["93.184.216.34"],
        )

        class _FakeResponse:
            def __init__(self) -> None:
                sock = SimpleNamespace(getpeername=lambda: ("10.0.0.7", 443))
                self.raw = SimpleNamespace(_connection=SimpleNamespace(sock=sock))
                self.is_redirect = False
                self.is_permanent_redirect = False
                self.headers = {}
                self.text = "<html><body>ok</body></html>"

            def raise_for_status(self) -> None:
                return None

            def close(self) -> None:
                return None

        class _FakeSession:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            @staticmethod
            def get(*args, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(requests, "Session", _FakeSession)

        with pytest.raises(URLSafetyError):
            WebScraper._fetch_url.__wrapped__("https://example.com")
