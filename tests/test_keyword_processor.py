"""
Unit tests for KeywordProcessor (improvement #17).
"""

from utils.keyword_processor import KeywordProcessor


class TestCleanKeyword:
    def test_basic_cleaning(self) -> None:
        assert KeywordProcessor.clean_keyword("  Купить Кофе  ") == "купить кофе"

    def test_removes_special_chars(self) -> None:
        result = KeywordProcessor.clean_keyword("купить!!! кофе@#$")
        assert result == "купить кофе"

    def test_preserves_hyphens(self) -> None:
        result = KeywordProcessor.clean_keyword("кофе-машина")
        assert result == "кофе-машина"

    def test_empty_string(self) -> None:
        assert KeywordProcessor.clean_keyword("") == ""

    def test_multiple_spaces(self) -> None:
        result = KeywordProcessor.clean_keyword("купить    кофе    машину")
        assert result == "купить кофе машину"


class TestIsValidKeyword:
    def test_valid_cyrillic_keyword(self) -> None:
        assert KeywordProcessor.is_valid_keyword("купить кофе") is True

    def test_short_keyword_rejected(self) -> None:
        assert KeywordProcessor.is_valid_keyword("ко") is False

    def test_latin_only_rejected(self) -> None:
        assert KeywordProcessor.is_valid_keyword("buy coffee") is False

    def test_mixed_cyrillic_latin_accepted(self) -> None:
        # Contains cyrillic, so should pass
        assert KeywordProcessor.is_valid_keyword("купить iPhone") is True

    def test_empty_string(self) -> None:
        assert KeywordProcessor.is_valid_keyword("") is False


class TestProcessKeywords:
    def test_basic_processing(self) -> None:
        raw = ["Купить Кофе", "купить кофе", "Чай Зеленый"]
        result = KeywordProcessor.process_keywords(raw)
        assert len(result) == 2  # Deduplication
        assert "купить кофе" in result
        assert "чай зеленый" in result

    def test_filters_invalid(self) -> None:
        raw = ["ab", "buy coffee", "купить кофе"]
        result = KeywordProcessor.process_keywords(raw)
        assert result == ["купить кофе"]

    def test_empty_list(self) -> None:
        assert KeywordProcessor.process_keywords([]) == []


class TestDeduplicateAcrossSources:
    def test_basic_deduplication(self) -> None:
        source_keywords = {
            "url1": ["купить кофе", "чай зеленый"],
            "url2": ["купить кофе", "молоко"],
        }
        result = KeywordProcessor.deduplicate_across_sources(source_keywords)
        assert result["url1"] == ["купить кофе", "чай зеленый"]
        assert result["url2"] == ["молоко"]  # "купить кофе" removed

    def test_no_overlap(self) -> None:
        source_keywords = {
            "url1": ["кофе"],
            "url2": ["чай"],
        }
        result = KeywordProcessor.deduplicate_across_sources(source_keywords)
        assert result["url1"] == ["кофе"]
        assert result["url2"] == ["чай"]

    def test_empty_sources(self) -> None:
        result = KeywordProcessor.deduplicate_across_sources({})
        assert result == {}
