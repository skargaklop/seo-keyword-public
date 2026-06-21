"""
Unit tests for KeywordProcessor (improvement #17).
"""

from utils.keyword_processor import KeywordProcessor


# Purpose: TestCleanKeyword implementation
class TestCleanKeyword:
    # Purpose: Test basic cleaning
    def test_basic_cleaning(self) -> None:
        assert KeywordProcessor.clean_keyword("  Купить Кофе  ") == "купить кофе"

    # Purpose: Test removes special chars
    def test_removes_special_chars(self) -> None:
        result = KeywordProcessor.clean_keyword("купить!!! кофе@#$")
        assert result == "купить кофе"

    # Purpose: Test preserves hyphens
    def test_preserves_hyphens(self) -> None:
        result = KeywordProcessor.clean_keyword("кофе-машина")
        assert result == "кофе-машина"

    # Purpose: Test empty string
    def test_empty_string(self) -> None:
        assert KeywordProcessor.clean_keyword("") == ""

    # Purpose: Test multiple spaces
    def test_multiple_spaces(self) -> None:
        result = KeywordProcessor.clean_keyword("купить    кофе    машину")
        assert result == "купить кофе машину"


# Purpose: TestIsValidKeyword implementation
class TestIsValidKeyword:
    # Purpose: Test valid cyrillic keyword
    def test_valid_cyrillic_keyword(self) -> None:
        assert KeywordProcessor.is_valid_keyword("купить кофе") is True

    # Purpose: Test short keyword rejected
    def test_short_keyword_rejected(self) -> None:
        assert KeywordProcessor.is_valid_keyword("ко") is False

    # Purpose: Test latin only rejected
    def test_latin_only_rejected(self) -> None:
        assert KeywordProcessor.is_valid_keyword("buy coffee") is False

    # Purpose: Test mixed cyrillic latin accepted
    # Contains cyrillic, so should pass.
    def test_mixed_cyrillic_latin_accepted(self) -> None:
        assert KeywordProcessor.is_valid_keyword("купить iPhone") is True

    # Purpose: Test empty string
    def test_empty_string(self) -> None:
        assert KeywordProcessor.is_valid_keyword("") is False


# Purpose: TestProcessKeywords implementation
class TestProcessKeywords:
    # Purpose: Test basic processing
    def test_basic_processing(self) -> None:
        raw = ["Купить Кофе", "купить кофе", "Чай Зеленый"]
        result = KeywordProcessor.process_keywords(raw)
        assert len(result) == 2  # Deduplication
        assert "купить кофе" in result
        assert "чай зеленый" in result

    # Purpose: Test filters invalid
    def test_filters_invalid(self) -> None:
        raw = ["ab", "buy coffee", "купить кофе"]
        result = KeywordProcessor.process_keywords(raw)
        assert result == ["купить кофе"]

    # Purpose: Test empty list
    def test_empty_list(self) -> None:
        assert KeywordProcessor.process_keywords([]) == []


# Purpose: TestDeduplicateAcrossSources implementation
class TestDeduplicateAcrossSources:
    # Purpose: Test basic deduplication
    def test_basic_deduplication(self) -> None:
        source_keywords = {
            "url1": ["купить кофе", "чай зеленый"],
            "url2": ["купить кофе", "молоко"],
        }
        result = KeywordProcessor.deduplicate_across_sources(source_keywords)
        assert result["url1"] == ["купить кофе", "чай зеленый"]
        assert result["url2"] == ["молоко"]  # "купить кофе" removed

    # Purpose: Test no overlap
    def test_no_overlap(self) -> None:
        source_keywords = {
            "url1": ["кофе"],
            "url2": ["чай"],
        }
        result = KeywordProcessor.deduplicate_across_sources(source_keywords)
        assert result["url1"] == ["кофе"]
        assert result["url2"] == ["чай"]

    # Purpose: Test empty sources
    def test_empty_sources(self) -> None:
        result = KeywordProcessor.deduplicate_across_sources({})
        assert result == {}
