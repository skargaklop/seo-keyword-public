"""
Unit tests for URLValidator (improvement #17).
"""

from utils.validator import URLValidator, validate_api_keys


# Purpose: TestValidateUrl implementation
class TestValidateUrl:
    # Purpose: Test valid https url
    def test_valid_https_url(self) -> None:
        result = URLValidator.validate_url("https://example.com")
        assert result.is_valid is True

    # Purpose: Test valid http url
    def test_valid_http_url(self) -> None:
        result = URLValidator.validate_url("http://example.com")
        assert result.is_valid is True

    # Purpose: Test valid url with path
    def test_valid_url_with_path(self) -> None:
        result = URLValidator.validate_url("https://example.com/page/test")
        assert result.is_valid is True

    # Purpose: Test localhost is blocked
    def test_localhost_is_blocked(self) -> None:
        result = URLValidator.validate_url("http://localhost")
        assert result.is_valid is False

    # Purpose: Test private ip is blocked
    def test_private_ip_is_blocked(self) -> None:
        result = URLValidator.validate_url("http://10.0.0.1")
        assert result.is_valid is False

    # Purpose: Test empty url
    def test_empty_url(self) -> None:
        result = URLValidator.validate_url("")
        assert result.is_valid is False
        assert result.error == "Empty URL"

    # Purpose: Bare domain without protocol is now normalized to https://.
    def test_no_protocol_normalizes_to_https(self) -> None:
        result = URLValidator.validate_url("example.com")
        assert result.is_valid is True
        assert result.url == "https://example.com"

    # Purpose: PLAN 15-01 URL-15-01: bare domains normalize to https://.
    def test_bare_domain_normalizes_to_https(self) -> None:
        result = URLValidator.validate_url("bigbox.com.ua")
        assert result.is_valid is True
        assert result.url == "https://bigbox.com.ua"

    # Purpose: PLAN 15-01 URL-15-01: www domains normalize to https://.
    def test_bare_domain_with_www_normalizes(self) -> None:
        result = URLValidator.validate_url("www.example.com")
        assert result.is_valid is True
        assert result.url == "https://www.example.com"

    # Purpose: PLAN 15-01 URL-15-01: bare domain with path normalizes correctly.
    def test_bare_domain_with_path_normalizes(self) -> None:
        result = URLValidator.validate_url("bigbox.com.ua/catalog")
        assert result.is_valid is True
        assert result.url == "https://bigbox.com.ua/catalog"

    # Purpose: PLAN 15-01 URL-15-01: clearly invalid strings still fail.
    def test_invalid_string_still_fails(self) -> None:
        result = URLValidator.validate_url("not a url at all!!!")
        assert result.is_valid is False

    # Purpose: Test invalid format
    def test_invalid_format(self) -> None:
        result = URLValidator.validate_url("https://")
        assert result.is_valid is False

    # Purpose: Test whitespace trimmed
    def test_whitespace_trimmed(self) -> None:
        result = URLValidator.validate_url("  https://example.com  ")
        assert result.is_valid is True


# Purpose: TestValidateUrls implementation
class TestValidateUrls:
    # Purpose: Test mixed urls
    def test_mixed_urls(self) -> None:
        urls = ["https://example.com", "invalid-url", "https://test.org"]
        valid, invalid = URLValidator.validate_urls(urls)
        assert len(valid) == 2
        assert len(invalid) == 1

    # Purpose: Test deduplication
    def test_deduplication(self) -> None:
        urls = ["https://example.com", "https://example.com"]
        valid, invalid = URLValidator.validate_urls(urls)
        assert len(valid) == 1

    # Purpose: Test empty list
    def test_empty_list(self) -> None:
        valid, invalid = URLValidator.validate_urls([])
        assert valid == []
        assert invalid == []

    # Purpose: Test skips empty strings
    def test_skips_empty_strings(self) -> None:
        urls = ["", "  ", "https://example.com"]
        valid, invalid = URLValidator.validate_urls(urls)
        assert len(valid) == 1


# Purpose: TestValidateApiKeys implementation
class TestValidateApiKeys:
    # Purpose: Test returns dict
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