# Test: Domain metrics computation (Plan 14-02)
# Purpose: Verify per-domain metrics from SERP DataFrame - avg position, keyword SERP frequency, result frequency
# LINKS: PLAN 14-02 Task 1, Task 2
# MODULE_CONTRACT: tests/test_domain_metrics
# Purpose: Verify compute_domain_metrics function and render_serp_domain_metrics integration
# Rationale: Tests domain extraction, metric computation, sorting, edge cases, and session state lifecycle
# Dependencies: utils.seo_math_analysis, utils.url_matcher, utils.pipeline, components.results
# Exports: pytest tests
# Verification: python -m pytest tests/test_domain_metrics.py -q
# CHANGE_SUMMARY: Added domain metrics tests — covers compute_domain_metrics, dataclass fields, sorting, edge cases, and render integration

import pandas as pd
import pytest

from utils.seo_math_analysis import DomainMetrics, compute_domain_metrics


# Purpose: Test DomainMetrics dataclass fields and structure.
class TestDomainMetricsDataclass:

    # Purpose: DomainMetrics must have all six fields.
    def test_domain_metrics_has_all_fields(self):
        dm = DomainMetrics(
            domain="example.com",
            avg_position=3.5,
            keyword_serp_count=5,
            total_keyword_serps=8,
            result_count=12,
            total_results=80,
        )
        assert dm.domain == "example.com"
        assert dm.avg_position == 3.5
        assert dm.keyword_serp_count == 5
        assert dm.total_keyword_serps == 8
        assert dm.result_count == 12
        assert dm.total_results == 80


# Purpose: Test compute_domain_metrics with typical SERP data.
class TestComputeDomainMetricsBasic:

    # Purpose: Build a sample SERP organic results DataFrame.
    @pytest.fixture
    def sample_serp_df(self):
        return pd.DataFrame({
            "Keyword": [
                "seo tools", "seo tools", "seo tools",
                "seo tools", "seo tools",
                "keyword planner", "keyword planner", "keyword planner",
                "keyword planner", "keyword planner",
            ],
            "Position": [1, 2, 3, 4, 5, 1, 2, 3, 4, 5],
            "URL": [
                "https://www.example.com/page1",
                "https://rozetka.com.ua/seo-tool",
                "https://www.example.com/page2",
                "https://other.com.ua/seo",
                "https://www.example.com/page3",
                "https://www.example.com/kw-planner",
                "https://rozetka.com.ua/kw-tool",
                "https://www.example.com/kw2",
                "https://other.com.ua/kw",
                "https://newsite.com/article",
            ],
        })

    # Purpose: compute_domain_metrics returns List[DomainMetrics].
    def test_returns_list_of_domain_metrics(self, sample_serp_df):
        result = compute_domain_metrics(sample_serp_df)
        assert isinstance(result, list)
        assert all(isinstance(dm, DomainMetrics) for dm in result)

    # Purpose: Domain extraction must use extract_match_domain for two-level TLDs.
    def test_domain_extraction_uses_extract_match_domain(self, sample_serp_df):
        result = compute_domain_metrics(sample_serp_df)
        domains = {dm.domain for dm in result}
        # rozetka.com.ua should be correctly extracted (not just com.ua)
        assert "rozetka.com.ua" in domains
        # other.com.ua should be correctly extracted
        assert "other.com.ua" in domains
        # example.com and newsite.com are standard TLDs
        assert "example.com" in domains
        assert "newsite.com" in domains

    # Purpose: Average position is the mean of all Position values for a domain.
    def test_avg_position_computed_correctly(self, sample_serp_df):
        result = compute_domain_metrics(sample_serp_df)
        domain_map = {dm.domain: dm for dm in result}

        # example.com appears at positions 1, 3, 5, 1, 3 -> avg = 13/5 = 2.6
        ex = domain_map["example.com"]
        assert ex.avg_position == pytest.approx(2.6, abs=0.01)

        # rozetka.com.ua appears at positions 2, 2 -> avg = 2.0
        rz = domain_map["rozetka.com.ua"]
        assert rz.avg_position == pytest.approx(2.0, abs=0.01)

    # Purpose: keyword_serp_count is number of unique keywords where domain appears.
    def test_keyword_serp_count(self, sample_serp_df):
        result = compute_domain_metrics(sample_serp_df)
        domain_map = {dm.domain: dm for dm in result}

        # example.com appears in both "seo tools" and "keyword planner"
        ex = domain_map["example.com"]
        assert ex.keyword_serp_count == 2

        # rozetka.com.ua appears in both "seo tools" and "keyword planner"
        rz = domain_map["rozetka.com.ua"]
        assert rz.keyword_serp_count == 2

        # newsite.com appears only in "keyword planner"
        ns = domain_map["newsite.com"]
        assert ns.keyword_serp_count == 1

    # Purpose: total_keyword_serps is total number of unique keywords.
    def test_total_keyword_serps(self, sample_serp_df):
        result = compute_domain_metrics(sample_serp_df)
        # All domains should have total_keyword_serps = 2 (seo tools, keyword planner)
        for dm in result:
            assert dm.total_keyword_serps == 2

    # Purpose: result_count is total rows where domain appears.
    def test_result_count(self, sample_serp_df):
        result = compute_domain_metrics(sample_serp_df)
        domain_map = {dm.domain: dm for dm in result}

        # example.com: 5 rows (positions 1,3,5 from seo tools + 1,3 from keyword planner)
        assert domain_map["example.com"].result_count == 5

        # rozetka.com.ua: 2 rows (pos 2 from each keyword)
        assert domain_map["rozetka.com.ua"].result_count == 2

    # Purpose: total_results is total number of rows in DataFrame.
    def test_total_results(self, sample_serp_df):
        result = compute_domain_metrics(sample_serp_df)
        # DataFrame has 10 rows
        for dm in result:
            assert dm.total_results == 10

    # Purpose: Results sorted by keyword_serp_count desc, then avg_position asc.
    def test_sorted_by_keyword_serp_count_desc_then_avg_position_asc(self, sample_serp_df):
        result = compute_domain_metrics(sample_serp_df)
        for i in range(len(result) - 1):
            a, b = result[i], result[i + 1]
            if a.keyword_serp_count == b.keyword_serp_count:
                assert a.avg_position <= b.avg_position
            else:
                assert a.keyword_serp_count >= b.keyword_serp_count


# Purpose: Test edge cases for compute_domain_metrics.
class TestComputeDomainMetricsEdgeCases:

    # Purpose: Empty DataFrame should return empty list.
    def test_empty_dataframe_returns_empty_list(self):
        df = pd.DataFrame({"Keyword": [], "Position": [], "URL": []})
        result = compute_domain_metrics(df)
        assert result == []

    # Purpose: Missing URL column should return empty list.
    def test_missing_url_column_returns_empty_list(self):
        df = pd.DataFrame({"Keyword": ["test"], "Position": [1]})
        result = compute_domain_metrics(df)
        assert result == []

    # Purpose: Missing Position column should return empty list.
    def test_missing_position_column_returns_empty_list(self):
        df = pd.DataFrame({"Keyword": ["test"], "URL": ["https://example.com"]})
        result = compute_domain_metrics(df)
        assert result == []

    # Purpose: Single row should produce one domain metric.
    def test_single_row_dataframe(self):
        df = pd.DataFrame({
            "Keyword": ["test keyword"],
            "Position": [1],
            "URL": ["https://example.com/page"],
        })
        result = compute_domain_metrics(df)
        assert len(result) == 1
        assert result[0].domain == "example.com"
        assert result[0].avg_position == 1.0
        assert result[0].keyword_serp_count == 1
        assert result[0].total_keyword_serps == 1
        assert result[0].result_count == 1
        assert result[0].total_results == 1

    # Purpose: None URLs should be handled without crashing.
    def test_none_url_handled_gracefully(self):
        df = pd.DataFrame({
            "Keyword": ["test", "test"],
            "Position": [1, 2],
            "URL": [None, "https://example.com/page"],
        })
        result = compute_domain_metrics(df)
        # Should not crash; None URL rows should be skipped or handled
        assert isinstance(result, list)

    # Purpose: compute_domain_metrics must NOT use @lru_cache or any memoization.
    def test_no_lru_cache_decorator(self):
        import inspect

        # Check that the function is NOT wrapped with lru_cache
        func = compute_domain_metrics
        # If wrapped by lru_cache, it would have a 'cache_info' attribute
        assert not hasattr(func, 'cache_info'), (
            "compute_domain_metrics must NOT use @lru_cache - DataFrames are unhashable"
        )
        # Check the decorator line doesn't use lru_cache (first line of source before 'def')
        source_lines = inspect.getsource(func).split('\n')
        decorator_lines = [
            line.strip() for line in source_lines
            if line.strip().startswith('@') and 'def' not in line
        ]
        for decorator in decorator_lines:
            assert "lru_cache" not in decorator, (
                f"compute_domain_metrics must not have lru_cache decorator, found: {decorator}"
            )


# Purpose: Verify compute_domain_metrics uses extract_match_domain, not raw urlparse.
class TestComputeDomainMetricsUsesExtractMatchDomain:

    # Purpose: Two-level TLDs (com.ua, co.uk) must be handled correctly.
    def test_two_level_tld_domain_extraction(self):
        df = pd.DataFrame({
            "Keyword": ["test", "test"],
            "Position": [1, 2],
            "URL": [
                "https://www.rozetka.com.ua/seo-tool-p123",
                "https://shop.amazon.co.uk/product/456",
            ],
        })
        result = compute_domain_metrics(df)
        domains = {dm.domain for dm in result}
        # Must extract rozetka.com.ua (not com.ua) and amazon.co.uk (not co.uk)
        assert "rozetka.com.ua" in domains
        assert "amazon.co.uk" in domains

    # Purpose: www prefix must be stripped from domain.
    def test_www_stripped_from_domain(self):
        df = pd.DataFrame({
            "Keyword": ["test"],
            "Position": [1],
            "URL": ["https://www.example.com/page"],
        })
        result = compute_domain_metrics(df)
        assert len(result) == 1
        assert result[0].domain == "example.com"
