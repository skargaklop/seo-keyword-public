"""Tests for SERP workflow: pipeline function, rendering, routing, and i18n."""

from unittest.mock import MagicMock, patch

import pandas as pd

from app import (
    EXACT_STATE_KEYS,
    WORKFLOW_MODE_CRAWL_REPORT,
    WORKFLOW_MODE_SERP_ANALYSIS,
    WORKFLOW_MODE_TRENDS,
    WORKFLOW_MODES,
)
from config.i18n import TRANSLATIONS
from utils.pipeline import (
    SERP_CHAIN_MAX_KEYWORDS,
    SERP_RESULT_COLUMNS,
    SESSION_KEY_SERP_MATCH_INDEX,
    build_serp_match_index,
    enrich_ads_dataframe_with_serp_context,
)
from utils.serp_client import (
    SERPOrganicResult,
    SERPPeopleAlsoAsk,
    SERPSearchResult,
)


# ---------------------------------------------------------------------------
# Pipeline function tests
# ---------------------------------------------------------------------------


# Purpose: Pipeline returns None and does not crash when SERP client is None.
@patch("utils.pipeline.create_serp_client", return_value=None)
def test_serp_workflow_returns_none_when_no_api_key(_mock_create, monkeypatch):
    mock_st = MagicMock()
    monkeypatch.setattr("utils.pipeline.st", mock_st)

    from utils.pipeline import run_serp_analysis_workflow

    result = run_serp_analysis_workflow(keywords=["test keyword"])
    assert result is None


# Purpose: Pipeline returns None when given an empty keyword list.
@patch("utils.pipeline.create_serp_client", return_value=None)
def test_serp_workflow_returns_none_on_empty_keywords(_mock_create, monkeypatch):
    mock_st = MagicMock()
    monkeypatch.setattr("utils.pipeline.st", mock_st)

    from utils.pipeline import run_serp_analysis_workflow

    result = run_serp_analysis_workflow(keywords=[])
    assert result is None


# Purpose: Pipeline flattens SERPSearchResult organic items into a DataFrame with SERP_RESULT_COLUMNS.
@patch("utils.pipeline.create_serp_client")
def test_serp_workflow_builds_dataframe_from_results(mock_create, monkeypatch):
    organic_items = [
        SERPOrganicResult(position=1, title="Title 1", url="https://one.test", snippet="First"),
        SERPOrganicResult(position=2, title="Title 2", url="https://two.test", snippet="Second"),
    ]
    search_result = SERPSearchResult(
        keyword="seo",
        organic=organic_items,
        related_searches=["related 1"],
        people_also_ask=[SERPPeopleAlsoAsk(question="What is SEO?", snippet="Answer")],
        provider="serper_dev",
        success=True,
    )
    mock_client = MagicMock()
    mock_client.search_batch.return_value = [search_result]
    mock_create.return_value = mock_client

    mock_st = MagicMock()
    monkeypatch.setattr("utils.pipeline.st", mock_st)

    from utils.pipeline import run_serp_analysis_workflow

    result = run_serp_analysis_workflow(keywords=["seo"])

    assert result is not None
    assert list(result.columns) == SERP_RESULT_COLUMNS
    assert len(result) == 2
    assert result.iloc[0]["Keyword"] == "seo"
    assert result.iloc[0]["Position"] == 1
    assert result.iloc[1]["Title"] == "Title 2"


# Purpose: Pipeline stores related_searches and people_also_ask in session state.
@patch("utils.pipeline.create_serp_client")
def test_serp_workflow_stores_related_data(mock_create, monkeypatch):
    search_result = SERPSearchResult(
        keyword="seo",
        organic=[SERPOrganicResult(1, "T", "https://t.test", "S")],
        related_searches=["related query 1", "related query 2"],
        people_also_ask=[SERPPeopleAlsoAsk(question="Q?", snippet="A")],
        provider="serper_dev",
        success=True,
    )
    mock_client = MagicMock()
    mock_client.search_batch.return_value = [search_result]
    mock_create.return_value = mock_client

    mock_st = MagicMock()
    monkeypatch.setattr("utils.pipeline.st", mock_st)

    from utils.pipeline import run_serp_analysis_workflow

    run_serp_analysis_workflow(keywords=["seo"])

    related_data = mock_st.session_state.serp_related_data
    assert related_data is not None
    assert len(related_data) == 3  # 2 related_searches + 1 people_also_ask

    related_searches = [r for r in related_data if r["Type"] == "related_search"]
    people_also_ask = [r for r in related_data if r["Type"] == "people_also_ask"]

    assert len(related_searches) == 2
    assert related_searches[0]["Related Query"] == "related query 1"
    assert len(people_also_ask) == 1
    assert people_also_ask[0]["Related Query"] == "Q?"


# Purpose: SERP rank evidence must not cross-match another selected source URL.
def test_source_aware_match_index_uses_only_row_source_url(monkeypatch):
    mock_st = MagicMock()
    mock_st.session_state = {
        "active_source_urls": [
            "https://source-a.test/page",
            "https://source-b.test/page",
        ],
    }
    monkeypatch.setattr("utils.pipeline.st", mock_st)

    serp_df = pd.DataFrame(
        [
            {
                "Keyword": "box filler",
                "Position": 3,
                "URL": "https://source-b.test/page",
                "source_context_key": ("box filler", "https://source-a.test/page"),
            },
        ]
    )

    match_index = build_serp_match_index(serp_df)

    assert match_index == {}


# Purpose: Non-matches should not populate Page URL in SERP or rank columns.
def test_ads_serp_enrichment_ignores_none_match_evidence(monkeypatch):
    mock_st = MagicMock()
    mock_st.session_state = {
        SESSION_KEY_SERP_MATCH_INDEX: {
            ("box filler", "https://source-a.test/page"): {
                "match_type": "none",
                "matched_serp_url": "https://unrelated.test/page",
                "serp_rank": 1,
            },
        },
    }
    monkeypatch.setattr("utils.pipeline.st", mock_st)

    ads_df = pd.DataFrame(
        [
            {
                "Keyword": "Box Filler",
                "Source URL": "https://source-a.test/page",
            },
        ]
    )

    enriched = enrich_ads_dataframe_with_serp_context(ads_df)

    assert enriched.loc[0, "Page URL in SERP"] == ""
    assert pd.isna(enriched.loc[0, "SERP Rank"])


# ---------------------------------------------------------------------------
# Rendering function tests
# ---------------------------------------------------------------------------


# Purpose: render_serp_results does not raise when given valid SERP data and mode.
def test_render_serp_results_shows_dataframe(monkeypatch):
    mock_st = MagicMock()
    mock_st.session_state.processed_data = pd.DataFrame(
        {
            "Keyword": ["seo"],
            "Position": [1],
            "Title": ["Title"],
            "URL": ["https://test.com"],
            "Snippet": ["Snippet"],
            "Provider": ["serper_dev"],
        }
    )
    mock_st.session_state.workflow_mode = "serp_analysis"
    mock_st.session_state.serp_results_saved = False
    mock_st.columns.return_value.__enter__ = MagicMock(
        side_effect=[MagicMock(), MagicMock()]
    )
    mock_st.columns.return_value.__exit__ = MagicMock(return_value=False)

    monkeypatch.setattr("components.results.st", mock_st)

    from components.results import render_serp_results

    render_serp_results(auto_save_excel=False)
    # Function completed without raising
    assert True


# Purpose: render_serp_related_searches does not raise with sample related data.
def test_render_serp_related_searches_shows_expanders(monkeypatch):
    mock_st = MagicMock()
    session_state = {
        "serp_related_data": [
            {"Keyword": "seo", "Related Query": "related 1", "Type": "related_search"},
            {"Keyword": "seo", "Related Query": "What is SEO?", "Type": "people_also_ask"},
        ],
    }
    mock_st.session_state = session_state
    mock_st.expander.return_value.__enter__ = MagicMock()
    mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)
    mock_col1 = MagicMock()
    mock_col2 = MagicMock()
    mock_col1.__enter__ = MagicMock(return_value=mock_col1)
    mock_col1.__exit__ = MagicMock(return_value=False)
    mock_col2.__enter__ = MagicMock(return_value=mock_col2)
    mock_col2.__exit__ = MagicMock(return_value=False)
    mock_st.columns.return_value = [mock_col1, mock_col2]

    monkeypatch.setattr("components.results.st", mock_st)

    from components.results import render_serp_related_searches

    render_serp_related_searches()
    # Function completed without raising
    assert True


# ---------------------------------------------------------------------------
# Routing test
# ---------------------------------------------------------------------------


# Purpose: WORKFLOW_MODE_SERP_ANALYSIS is in WORKFLOW_MODES and equals 'serp_analysis'.
def test_serp_mode_in_workflow_modes():
    assert WORKFLOW_MODE_SERP_ANALYSIS == "serp_analysis"
    assert WORKFLOW_MODE_SERP_ANALYSIS in WORKFLOW_MODES
    assert WORKFLOW_MODE_CRAWL_REPORT == "crawl_report"
    assert WORKFLOW_MODE_CRAWL_REPORT in WORKFLOW_MODES
    assert WORKFLOW_MODE_TRENDS == "google_trends"
    assert WORKFLOW_MODE_TRENDS in WORKFLOW_MODES
    assert len(WORKFLOW_MODES) == 7


# ---------------------------------------------------------------------------
# i18n test
# ---------------------------------------------------------------------------


# Purpose: All 18+ serp_* keys exist in TRANSLATIONS with ru/uk/en values.
def test_serp_i18n_keys_present():
    serp_keys = [k for k in TRANSLATIONS if k.startswith("serp_")]
    assert len(serp_keys) >= 18, f"Expected >= 18 serp_ keys, found {len(serp_keys)}"

    for key in serp_keys:
        entry = TRANSLATIONS[key]
        assert "ru" in entry, f"Missing 'ru' for key {key}"
        assert "uk" in entry, f"Missing 'uk' for key {key}"
        assert "en" in entry, f"Missing 'en' for key {key}"


# ---------------------------------------------------------------------------
# Phase 3: SERP chain to Ads pipeline tests
# ---------------------------------------------------------------------------


# Purpose: run_serp_chain_to_ads_workflow returns None when given empty queries.
def test_serp_chain_returns_none_on_empty_queries(monkeypatch):
    mock_st = MagicMock()
    monkeypatch.setattr("utils.pipeline.st", mock_st)

    from utils.pipeline import run_serp_chain_to_ads_workflow

    result = run_serp_chain_to_ads_workflow(
        selected_queries=[],
        location_id="1234",
        language_id="1001",
        currency_code="USD",
    )
    assert result is None


# Purpose: run_serp_chain_to_ads_workflow returns DataFrame and stores in serp_chained_ads_data.
@patch("utils.pipeline.GoogleAdsHandler")
def test_serp_chain_builds_ads_dataframe(mock_ads_cls, monkeypatch):
    mock_df = pd.DataFrame({
        "Keyword": ["seo tools"],
        "Source URL": ["keyword-seed://manual-input"],
        "Avg Monthly Searches": [1000],
        "Competition": ["LOW"],
        "Competition Index": [10],
        "Low CPC": [0.5],
        "High CPC": [2.0],
        "CPC Currency": ["USD"],
        "Months With Data": ["12"],
    })
    mock_handler = MagicMock()
    mock_handler.get_keyword_ideas.return_value = mock_df
    mock_ads_cls.return_value = mock_handler

    mock_st = MagicMock()
    monkeypatch.setattr("utils.pipeline.st", mock_st)

    from utils.pipeline import run_serp_chain_to_ads_workflow

    result = run_serp_chain_to_ads_workflow(
        selected_queries=["seo tools"],
        location_id="1234",
        language_id="1001",
        currency_code="USD",
    )
    assert result is not None
    assert "Keyword" in result.columns
    assert mock_st.session_state.serp_chained_ads_data is not None


# Purpose: run_serp_chain_to_ads_workflow truncates to SERP_CHAIN_MAX_KEYWORDS.
@patch("utils.pipeline.GoogleAdsHandler")
def test_serp_chain_limits_to_max_keywords(mock_ads_cls, monkeypatch):
    mock_df = pd.DataFrame({
        "Keyword": ["kw" + str(i) for i in range(20)],
        "Source URL": ["keyword-seed://manual-input"] * 20,
        "Avg Monthly Searches": [100] * 20,
        "Competition": ["LOW"] * 20,
        "Competition Index": [10] * 20,
        "Low CPC": [0.5] * 20,
        "High CPC": [2.0] * 20,
        "CPC Currency": ["USD"] * 20,
        "Months With Data": ["12"] * 20,
    })
    mock_handler = MagicMock()
    mock_handler.get_keyword_ideas.return_value = mock_df
    mock_ads_cls.return_value = mock_handler

    mock_st = MagicMock()
    monkeypatch.setattr("utils.pipeline.st", mock_st)

    from utils.pipeline import run_serp_chain_to_ads_workflow

    queries = [f"query {i}" for i in range(30)]
    result = run_serp_chain_to_ads_workflow(
        selected_queries=queries,
        location_id="1234",
        language_id="1001",
        currency_code="USD",
    )
    assert result is not None
    mock_handler.get_keyword_ideas.assert_called_once()
    called_args = mock_handler.get_keyword_ideas.call_args
    assert len(called_args[0][0]) == SERP_CHAIN_MAX_KEYWORDS


# ---------------------------------------------------------------------------
# Phase 3: Chained Ads rendering tests
# ---------------------------------------------------------------------------


# Purpose: render_serp_chained_ads_results does not raise with valid Ads data and serp_analysis mode.
def test_render_serp_chained_ads_results_shows_dataframe(monkeypatch):
    mock_st = MagicMock()
    mock_st.session_state.workflow_mode = "serp_analysis"
    mock_st.session_state.serp_chained_ads_data = pd.DataFrame({
        "Keyword": ["seo tools"],
        "Source URL": ["keyword-seed://manual-input"],
        "Avg Monthly Searches": [1000],
        "Competition": ["LOW"],
        "Competition Index": [10],
        "Low CPC": [0.5],
        "High CPC": [2.0],
        "CPC Currency": ["USD"],
        "Months With Data": ["12"],
    })
    mock_st.columns.return_value.__enter__ = MagicMock(
        side_effect=[MagicMock(), MagicMock()]
    )
    mock_st.columns.return_value.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr("components.results.st", mock_st)

    from components.results import render_serp_chained_ads_results

    render_serp_chained_ads_results(auto_save_excel=False)
    assert True


# Purpose: render_serp_chained_ads_results returns early when workflow_mode is not serp_analysis.
def test_render_serp_chained_ads_results_skips_wrong_mode(monkeypatch):
    mock_st = MagicMock()
    mock_st.session_state.workflow_mode = "url_llm"
    mock_st.session_state.serp_chained_ads_data = pd.DataFrame({"Keyword": ["test"]})
    monkeypatch.setattr("components.results.st", mock_st)

    from components.results import render_serp_chained_ads_results

    render_serp_chained_ads_results(auto_save_excel=False)
    assert True


# ---------------------------------------------------------------------------
# Phase 3: Session state tests
# ---------------------------------------------------------------------------


# Purpose: serp_chained_ads_data and serp_chain_ads_saved are in EXACT_STATE_KEYS.
def test_serp_chain_state_keys_in_defaults():
    assert "serp_chained_ads_data" in EXACT_STATE_KEYS
    assert "serp_chain_ads_saved" in EXACT_STATE_KEYS


# ---------------------------------------------------------------------------
# Phase 3: Extended i18n test
# ---------------------------------------------------------------------------


# Purpose: All serp_chain_* and serp_export_* keys exist in TRANSLATIONS with ru/uk/en values.
def test_serp_chain_i18n_keys_present():
    expected_keys = [
        "serp_export_related",
        "serp_export_related_csv",
        "serp_chain_header",
        "serp_chain_select_all",
        "serp_chain_button",
        "serp_chain_no_queries",
        "serp_chain_querying",
        "serp_chain_complete",
        "serp_chain_results_header",
        "serp_chain_limit_notice",
        "serp_chain_empty",
    ]
    for key in expected_keys:
        assert key in TRANSLATIONS, f"Missing key in TRANSLATIONS: {key}"
        entry = TRANSLATIONS[key]
        assert "ru" in entry, f"Missing 'ru' for key {key}"
        assert "uk" in entry, f"Missing 'uk' for key {key}"
        assert "en" in entry, f"Missing 'en' for key {key}"

# GRACE module link: MOD-006

# GRACE module link: MOD-007

# --- SERP-Ads merge (TDD) ---

RESULT_COLUMNS = [
    "Keyword", "Source URL", "Avg Monthly Searches",
    "Competition", "Competition Index", "Low CPC",
    "High CPC", "CPC Currency", "Months With Data",
]


# Purpose: aggregate_serp_per_keyword collapses N SERP rows per keyword into one row with aggregates.
def test_aggregate_serp_per_keyword_collapses_n_rows_into_one():
    from utils.pipeline import aggregate_serp_per_keyword

    serp_df = pd.DataFrame([
        {"Keyword": "nike", "Position": 1, "Title": "Nike1", "URL": "https://nike.com/a",
         "Snippet": "s1", "Displayed Link": "nike.com", "Rich Snippet": None, "Provider": "g"},
        {"Keyword": "nike", "Position": 3, "Title": "Nike2", "URL": "https://nike.com/b",
         "Snippet": "s2", "Displayed Link": "nike.com", "Rich Snippet": None, "Provider": "g"},
        {"Keyword": "nike", "Position": 5, "Title": "Nike3", "URL": "https://nike.com/c",
         "Snippet": "s3", "Displayed Link": "nike.com", "Rich Snippet": None, "Provider": "g"},
        {"Keyword": "potato", "Position": 2, "Title": "P1", "URL": "https://potato.com/a",
         "Snippet": "s4", "Displayed Link": "potato.com", "Rich Snippet": None, "Provider": "g"},
        {"Keyword": "potato", "Position": 4, "Title": "P2", "URL": "https://potato.com/b",
         "Snippet": "s5", "Displayed Link": "potato.com", "Rich Snippet": None, "Provider": "g"},
    ])
    ads_df = pd.DataFrame([
        {"Keyword": "nike", "Source URL": "", "Avg Monthly Searches": 1000,
         "Competition": "LOW", "Competition Index": 10, "Low CPC": 0.5,
         "High CPC": 1.5, "CPC Currency": "USD", "Months With Data": 12},
        {"Keyword": "potato", "Source URL": "", "Avg Monthly Searches": 500,
         "Competition": "MEDIUM", "Competition Index": 30, "Low CPC": 0.3,
         "High CPC": 0.8, "CPC Currency": "USD", "Months With Data": 6},
    ])

    result = aggregate_serp_per_keyword(serp_df, ads_df)

    assert len(result) == 2
    # Ads cols preserved with original order
    for i, col in enumerate(RESULT_COLUMNS):
        assert result.columns[i] == col, f"Expected col {i} = {col}, got {result.columns[i]}"
    # SERP cols at end
    assert list(result.columns[-3:]) == ["SERP #results", "SERP top position", "SERP top3 domains"]

    nike_row = result[result["Keyword"] == "nike"].iloc[0]
    assert nike_row["SERP #results"] == 3
    assert nike_row["SERP top position"] == 1
    assert nike_row["SERP top3 domains"] == "nike.com"

    potato_row = result[result["Keyword"] == "potato"].iloc[0]
    assert potato_row["SERP #results"] == 2
    assert potato_row["SERP top position"] == 2


# Purpose: aggregate_serp_per_keyword performs case-insensitive join via normalization.
def test_aggregate_serp_per_keyword_case_insensitive_join():
    from utils.pipeline import aggregate_serp_per_keyword

    ads_df = pd.DataFrame([
        {"Keyword": "Nike", "Source URL": "", "Avg Monthly Searches": 1000,
         "Competition": "LOW", "Competition Index": 10, "Low CPC": 0.5,
         "High CPC": 1.5, "CPC Currency": "USD", "Months With Data": 12},
    ])
    serp_df = pd.DataFrame([
        {"Keyword": "nike", "Position": 2, "Title": "N", "URL": "https://nike.com",
         "Snippet": "s", "Displayed Link": "nike.com", "Rich Snippet": None, "Provider": "g"},
    ])

    result = aggregate_serp_per_keyword(serp_df, ads_df)

    assert len(result) == 1
    assert result.iloc[0]["SERP #results"] == 1
    assert result.iloc[0]["SERP top position"] == 2


# Purpose: aggregate_serp_per_keyword left join leaves SERP cols empty when keyword has no SERP match.
def test_aggregate_serp_per_keyword_left_join_blank_when_no_match():
    from utils.pipeline import aggregate_serp_per_keyword

    ads_df = pd.DataFrame([
        {"Keyword": "nike", "Source URL": "", "Avg Monthly Searches": 1000,
         "Competition": "LOW", "Competition Index": 10, "Low CPC": 0.5,
         "High CPC": 1.5, "CPC Currency": "USD", "Months With Data": 12},
        {"Keyword": "shoes", "Source URL": "", "Avg Monthly Searches": 200,
         "Competition": "HIGH", "Competition Index": 80, "Low CPC": 1.0,
         "High CPC": 3.0, "CPC Currency": "USD", "Months With Data": 3},
    ])
    serp_df = pd.DataFrame([
        {"Keyword": "nike", "Position": 1, "Title": "N", "URL": "https://nike.com",
         "Snippet": "s", "Displayed Link": "nike.com", "Rich Snippet": None, "Provider": "g"},
    ])

    result = aggregate_serp_per_keyword(serp_df, ads_df)

    assert len(result) == 2
    shoes_row = result[result["Keyword"] == "shoes"].iloc[0]
    # SERP #results may be 0 or NaN — assert it's empty-ish
    assert shoes_row["SERP #results"] == 0 or pd.isna(shoes_row["SERP #results"]), \
        f"Expected empty SERP #results, got {shoes_row['SERP #results']}"
    assert pd.isna(shoes_row["SERP top position"]) or shoes_row["SERP top position"] is None, \
        f"Expected None/NaN SERP top position, got {shoes_row['SERP top position']}"
    assert shoes_row["SERP top3 domains"] == "" or pd.isna(shoes_row["SERP top3 domains"]), \
        f"Expected empty SERP top3 domains, got {shoes_row['SERP top3 domains']}"
    # Verify nike row still works
    nike_row = result[result["Keyword"] == "nike"].iloc[0]
    assert nike_row["SERP #results"] == 1


# Purpose: aggregate_serp_per_keyword guards return ads_df unchanged for None/empty/missing-key inputs.
def test_aggregate_serp_per_keyword_guards_return_ads_unchanged():
    from utils.pipeline import aggregate_serp_per_keyword

    valid_ads = pd.DataFrame([{"Keyword": "test", "Source URL": ""}])
    valid_serp = pd.DataFrame([{"Keyword": "test", "Position": 1, "Title": "T",
                                 "URL": "https://t.com", "Snippet": "s",
                                 "Displayed Link": "t.com", "Rich Snippet": None,
                                 "Provider": "g"}])
    empty_serp = pd.DataFrame()

    # (a) serp_df is None -> return ads_df unchanged
    result_a = aggregate_serp_per_keyword(None, valid_ads)
    assert result_a is valid_ads or result_a.equals(valid_ads)

    # (b) ads_df is None -> return None
    result_b = aggregate_serp_per_keyword(valid_serp, None)
    assert result_b is None

    # (c) serp_df is empty -> return ads_df unchanged
    result_c = aggregate_serp_per_keyword(empty_serp, valid_ads)
    assert result_c is valid_ads or result_c.equals(valid_ads)

    # (d) ads_df missing Keyword col -> return ads_df unchanged
    bad_ads = pd.DataFrame([{"NotKeyword": 1}])
    result_d = aggregate_serp_per_keyword(valid_serp, bad_ads)
    assert result_d is bad_ads or result_d.equals(bad_ads)


# Purpose: aggregate_serp_per_keyword collects top 3 distinct domains by rank, deduplicating and capping at 3.
def test_aggregate_serp_per_keyword_top3_domains_distinct_dedup_capped():
    from utils.pipeline import aggregate_serp_per_keyword

    ads_df = pd.DataFrame([
        {"Keyword": "multi", "Source URL": "", "Avg Monthly Searches": 1000,
         "Competition": "LOW", "Competition Index": 10, "Low CPC": 0.5,
         "High CPC": 1.5, "CPC Currency": "USD", "Months With Data": 12},
    ])
    serp_df = pd.DataFrame([
        {"Keyword": "multi", "Position": 1, "Title": "A1", "URL": "https://a.com/1",
         "Snippet": "s1", "Displayed Link": "a.com", "Rich Snippet": None, "Provider": "g"},
        {"Keyword": "multi", "Position": 2, "Title": "B1", "URL": "https://b.com/1",
         "Snippet": "s2", "Displayed Link": "b.com", "Rich Snippet": None, "Provider": "g"},
        {"Keyword": "multi", "Position": 3, "Title": "C1", "URL": "https://c.com/1",
         "Snippet": "s3", "Displayed Link": "c.com", "Rich Snippet": None, "Provider": "g"},
        {"Keyword": "multi", "Position": 4, "Title": "D1", "URL": "https://d.com/1",
         "Snippet": "s4", "Displayed Link": "d.com", "Rich Snippet": None, "Provider": "g"},
        {"Keyword": "multi", "Position": 5, "Title": "A2", "URL": "https://a.com/2",
         "Snippet": "s5", "Displayed Link": "a.com", "Rich Snippet": None, "Provider": "g"},
    ])

    result = aggregate_serp_per_keyword(serp_df, ads_df)

    assert len(result) == 1
    multi_row = result[result["Keyword"] == "multi"].iloc[0]
    assert multi_row["SERP top3 domains"] == "a.com, b.com, c.com"
    assert multi_row["SERP #results"] == 5
    assert multi_row["SERP top position"] == 1


# Purpose: aggregate_serp_per_keyword returns as many distinct domains as available when fewer than 3 exist (no padding, no trailing separator).
def test_aggregate_serp_per_keyword_top3_domains_fewer_than_three():
    from utils.pipeline import aggregate_serp_per_keyword

    ads_df = pd.DataFrame([
        {"Keyword": "few", "Source URL": "", "Avg Monthly Searches": 1000,
         "Competition": "LOW", "Competition Index": 10, "Low CPC": 0.5,
         "High CPC": 1.5, "CPC Currency": "USD", "Months With Data": 12},
    ])
    serp_df = pd.DataFrame([
        {"Keyword": "few", "Position": 1, "Title": "X1", "URL": "https://x.com/1",
         "Snippet": "s1", "Displayed Link": "x.com", "Rich Snippet": None, "Provider": "g"},
        {"Keyword": "few", "Position": 2, "Title": "Y1", "URL": "https://y.com/1",
         "Snippet": "s2", "Displayed Link": "y.com", "Rich Snippet": None, "Provider": "g"},
    ])

    result = aggregate_serp_per_keyword(serp_df, ads_df)

    assert len(result) == 1
    few_row = result[result["Keyword"] == "few"].iloc[0]
    assert few_row["SERP top3 domains"] == "x.com, y.com"
    assert few_row["SERP #results"] == 2
    assert few_row["SERP top position"] == 1


# Purpose: build_and_store_merged_ads_serp creates merged_ads_serp_data when both inputs present.
def test_build_and_store_merged_ads_serp_creates_key(monkeypatch):
    from components.results import build_and_store_merged_ads_serp

    mock_st = MagicMock()
    ads_df = pd.DataFrame([
        {"Keyword": "nike", "Source URL": "", "Avg Monthly Searches": 1000,
         "Competition": "LOW", "Competition Index": 10, "Low CPC": 0.5,
         "High CPC": 1.5, "CPC Currency": "USD", "Months With Data": 12},
    ])
    serp_df = pd.DataFrame([
        {"Keyword": "nike", "Position": 1, "Title": "N", "URL": "https://nike.com",
         "Snippet": "s", "Displayed Link": "nike.com", "Rich Snippet": None, "Provider": "g"},
    ])
    mock_st.session_state.processed_data = ads_df
    mock_st.session_state.chained_serp_results = serp_df
    monkeypatch.setattr("components.results.st", mock_st)

    result = build_and_store_merged_ads_serp()

    assert result is not None
    assert mock_st.session_state.merged_ads_serp_data is not None
    merged = mock_st.session_state.merged_ads_serp_data
    for col in ["SERP #results", "SERP top position", "SERP top3 domains"]:
        assert col in merged.columns, f"Missing SERP col: {col}"


# Purpose: build_and_store_merged_ads_serp returns None when chained_serp_results is missing.
def test_build_and_store_merged_ads_serp_noop_when_missing(monkeypatch):
    from components.results import build_and_store_merged_ads_serp

    mock_st = MagicMock()
    mock_st.session_state.processed_data = pd.DataFrame([{"Keyword": "nike"}])
    # No chained_serp_results set
    monkeypatch.setattr("components.results.st", mock_st)

    result = build_and_store_merged_ads_serp()

    assert result is None
    # merged_ads_serp_data should not have been set
    val = getattr(mock_st.session_state, "merged_ads_serp_data", None)
    assert val is None


# Purpose: render_merged_ads_serp_results no-ops when merged data is empty/None.
def test_render_merged_ads_serp_results_noop_when_empty(monkeypatch):
    from components.results import render_merged_ads_serp_results

    mock_st = MagicMock()
    mock_st.session_state.merged_ads_serp_data = None
    monkeypatch.setattr("components.results.st", mock_st)

    # Should not raise
    render_merged_ads_serp_results()

    # Also test empty DataFrame
    mock_st2 = MagicMock()
    mock_st2.session_state.merged_ads_serp_data = pd.DataFrame()
    monkeypatch.setattr("components.results.st", mock_st2)
    render_merged_ads_serp_results()


# Purpose: merged_ads_serp_data is declared in app.EXACT_STATE_KEYS.
def test_merged_ads_serp_state_key_in_defaults():
    assert "merged_ads_serp_data" in EXACT_STATE_KEYS, \
        "merged_ads_serp_data missing from EXACT_STATE_KEYS"


# Purpose: merged_ads_serp_header and merged_ads_serp_desc i18n keys exist in TRANSLATIONS.
def test_merged_ads_serp_i18n_keys_present():
    expected_keys = [
        "merged_ads_serp_header",
        "merged_ads_serp_desc",
    ]
    for key in expected_keys:
        assert key in TRANSLATIONS, f"Missing key in TRANSLATIONS: {key}"
        entry = TRANSLATIONS[key]
        assert "ru" in entry, f"Missing 'ru' for key {key}"
        assert "uk" in entry, f"Missing 'uk' for key {key}"
        assert "en" in entry, f"Missing 'en' for key {key}"
