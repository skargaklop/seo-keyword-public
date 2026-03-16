"""
Unit tests for URLValidator (improvement #17).
"""

from utils.validator import URLValidator, validate_api_keys


class TestValidateUrl:
    def test_valid_https_url(self) -> None:
        result = URLValidator.validate_url("https://example.com")
        assert result.is_valid is True

    def test_valid_http_url(self) -> None:
        result = URLValidator.validate_url("http://example.com")
        assert result.is_valid is True

    def test_valid_url_with_path(self) -> None:
        result = URLValidator.validate_url("https://example.com/page/test")
        assert result.is_valid is True

    def test_localhost_is_blocked(self) -> None:
        result = URLValidator.validate_url("http://localhost")
        assert result.is_valid is False

    def test_private_ip_is_blocked(self) -> None:
        result = URLValidator.validate_url("http://10.0.0.1")
        assert result.is_valid is False

    def test_empty_url(self) -> None:
        result = URLValidator.validate_url("")
        assert result.is_valid is False
        assert result.error == "Empty URL"

    def test_no_protocol(self) -> None:
        result = URLValidator.validate_url("example.com")
        assert result.is_valid is False

    def test_invalid_format(self) -> None:
        result = URLValidator.validate_url("https://")
        assert result.is_valid is False

    def test_whitespace_trimmed(self) -> None:
        result = URLValidator.validate_url("  https://example.com  ")
        assert result.is_valid is True


class TestValidateUrls:
    def test_mixed_urls(self) -> None:
        urls = ["https://example.com", "invalid-url", "https://test.org"]
        valid, invalid = URLValidator.validate_urls(urls)
        assert len(valid) == 2
        assert len(invalid) == 1

    def test_deduplication(self) -> None:
        urls = ["https://example.com", "https://example.com"]
        valid, invalid = URLValidator.validate_urls(urls)
        assert len(valid) == 1

    def test_empty_list(self) -> None:
        valid, invalid = URLValidator.validate_urls([])
        assert valid == []
        assert invalid == []

    def test_skips_empty_strings(self) -> None:
        urls = ["", "  ", "https://example.com"]
        valid, invalid = URLValidator.validate_urls(urls)
        assert len(valid) == 1


class TestValidateApiKeys:
    def test_returns_dict(self) -> None:
        result = validate_api_keys()
        assert isinstance(result, dict)
        assert "OpenAI" in result
        assert "Google (Gemini)" in result
        assert "xAI (Grok)" in result
        assert "Groq" in result
        assert "DeepSeek" in result
        assert "MiniMax" in result
        assert "Moonshot" in result
