"""Tests for Trends-Ads merge: pipeline aggregation, build/store, render guard, state key, and i18n.

Mirrors tests/test_serp_workflow.py SERP-Ads merge tests.
"""

from unittest.mock import MagicMock

import pandas as pd

from app import EXACT_STATE_KEYS
from config.i18n import TRANSLATIONS


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

RESULT_COLUMNS = [
    "Keyword", "Source URL", "Avg Monthly Searches",
    "Competition", "Competition Index", "Low CPC",
    "High CPC", "CPC Currency", "Months With Data",
]


def _ads_df_two_keywords() -> pd.DataFrame:
    return pd.DataFrame([
        {"Keyword": "nike", "Source URL": "", "Avg Monthly Searches": 1000,
         "Competition": "LOW", "Competition Index": 10, "Low CPC": 0.5,
         "High CPC": 1.5, "CPC Currency": "USD", "Months With Data": 12},
        {"Keyword": "potato", "Source URL": "", "Avg Monthly Searches": 500,
         "Competition": "MEDIUM", "Competition Index": 30, "Low CPC": 0.3,
         "High CPC": 0.8, "CPC Currency": "USD", "Months With Data": 6},
    ])


def _trends_averages_two_keywords() -> pd.DataFrame:
    return pd.DataFrame([
        {"Keyword": "nike", "Average Interest": 88, "Geo": "UA",
         "Timeframe": "12m", "Provider": "google"},
        {"Keyword": "potato", "Average Interest": 44, "Geo": "UA",
         "Timeframe": "12m", "Provider": "google"},
    ])


# ---------------------------------------------------------------------------
# Pipeline function tests: aggregate_trends_per_keyword
# ---------------------------------------------------------------------------

# --- Trends-Ads merge (TDD) ---


# Purpose: aggregate_trends_per_keyword collapses trends averages rows into one per keyword and appends trends cols.
def test_aggregate_trends_per_keyword_collapses_n_rows_into_one():
    from utils.pipeline import aggregate_trends_per_keyword

    trends_df = _trends_averages_two_keywords()
    ads_df = _ads_df_two_keywords()

    result = aggregate_trends_per_keyword(trends_df, ads_df)

    assert len(result) == 2
    # Ads cols preserved with original order
    for i, col in enumerate(RESULT_COLUMNS):
        assert result.columns[i] == col, f"Expected col {i} = {col}, got {result.columns[i]}"
    # Trends cols at end
    assert list(result.columns[-3:]) == ["Trends Avg Interest", "Trends Geo", "Trends Timeframe"]

    nike_row = result[result["Keyword"] == "nike"].iloc[0]
    assert nike_row["Trends Avg Interest"] == 88
    assert nike_row["Trends Geo"] == "UA"
    assert nike_row["Trends Timeframe"] == "12m"

    potato_row = result[result["Keyword"] == "potato"].iloc[0]
    assert potato_row["Trends Avg Interest"] == 44
    assert potato_row["Trends Geo"] == "UA"
    assert potato_row["Trends Timeframe"] == "12m"


# Purpose: aggregate_trends_per_keyword performs case-insensitive join via normalization.
def test_aggregate_trends_per_keyword_case_insensitive_join():
    from utils.pipeline import aggregate_trends_per_keyword

    ads_df = pd.DataFrame([
        {"Keyword": "Nike", "Source URL": "", "Avg Monthly Searches": 1000,
         "Competition": "LOW", "Competition Index": 10, "Low CPC": 0.5,
         "High CPC": 1.5, "CPC Currency": "USD", "Months With Data": 12},
    ])
    trends_df = pd.DataFrame([
        {"Keyword": "nike", "Average Interest": 88, "Geo": "UA",
         "Timeframe": "12m", "Provider": "google"},
    ])

    result = aggregate_trends_per_keyword(trends_df, ads_df)

    assert len(result) == 1
    assert result.iloc[0]["Trends Avg Interest"] == 88
    assert result.iloc[0]["Trends Geo"] == "UA"
    assert result.iloc[0]["Trends Timeframe"] == "12m"


# Purpose: aggregate_trends_per_keyword left join leaves trends cols blank when keyword has no trends match.
def test_aggregate_trends_per_keyword_left_join_blank_when_no_match():
    from utils.pipeline import aggregate_trends_per_keyword

    ads_df = pd.DataFrame([
        {"Keyword": "nike", "Source URL": "", "Avg Monthly Searches": 1000,
         "Competition": "LOW", "Competition Index": 10, "Low CPC": 0.5,
         "High CPC": 1.5, "CPC Currency": "USD", "Months With Data": 12},
        {"Keyword": "shoes", "Source URL": "", "Avg Monthly Searches": 200,
         "Competition": "HIGH", "Competition Index": 80, "Low CPC": 1.0,
         "High CPC": 3.0, "CPC Currency": "USD", "Months With Data": 3},
    ])
    trends_df = pd.DataFrame([
        {"Keyword": "nike", "Average Interest": 88, "Geo": "UA",
         "Timeframe": "12m", "Provider": "google"},
    ])

    result = aggregate_trends_per_keyword(trends_df, ads_df)

    assert len(result) == 2
    shoes_row = result[result["Keyword"] == "shoes"].iloc[0]
    assert pd.isna(shoes_row["Trends Avg Interest"]), \
        f"Expected NaN Trends Avg Interest, got {shoes_row['Trends Avg Interest']}"
    assert pd.isna(shoes_row["Trends Geo"]), \
        f"Expected NaN Trends Geo, got {shoes_row['Trends Geo']}"
    assert pd.isna(shoes_row["Trends Timeframe"]), \
        f"Expected NaN Trends Timeframe, got {shoes_row['Trends Timeframe']}"
    # Verify nike row still works
    nike_row = result[result["Keyword"] == "nike"].iloc[0]
    assert nike_row["Trends Avg Interest"] == 88


# Purpose: aggregate_trends_per_keyword guards return ads_df unchanged for None/empty/missing-key inputs.
def test_aggregate_trends_per_keyword_guards_return_ads_unchanged():
    from utils.pipeline import aggregate_trends_per_keyword

    valid_ads = _ads_df_two_keywords()
    valid_trends = _trends_averages_two_keywords()
    empty_trends = pd.DataFrame()

    # (a) trends_df is None -> return ads_df unchanged
    result_a = aggregate_trends_per_keyword(None, valid_ads)
    assert result_a is valid_ads or result_a.equals(valid_ads)

    # (b) ads_df is None -> return None
    result_b = aggregate_trends_per_keyword(valid_trends, None)
    assert result_b is None

    # (c) trends_df is empty -> return ads_df unchanged
    result_c = aggregate_trends_per_keyword(empty_trends, valid_ads)
    assert result_c is valid_ads or result_c.equals(valid_ads)

    # (d) ads_df missing Keyword col -> return ads_df unchanged
    bad_ads = pd.DataFrame([{"NotKeyword": 1}])
    result_d = aggregate_trends_per_keyword(valid_trends, bad_ads)
    assert result_d is bad_ads or result_d.equals(bad_ads)

    # (e) trends_df missing Keyword col -> return ads_df unchanged
    bad_trends = pd.DataFrame([{"NotKeyword": 1, "Average Interest": 5}])
    result_e = aggregate_trends_per_keyword(bad_trends, valid_ads)
    assert result_e is valid_ads or result_e.equals(valid_ads)


# ---------------------------------------------------------------------------
# Build/store tests: build_and_store_merged_ads_trends
# ---------------------------------------------------------------------------

# Purpose: build_and_store_merged_ads_trends creates merged_ads_trends_data when both inputs present.
def test_build_and_store_merged_ads_trends_creates_key(monkeypatch):
    from components.results import build_and_store_merged_ads_trends

    mock_st = MagicMock()
    ads_df = _ads_df_two_keywords()
    trends_averages = _trends_averages_two_keywords()
    trends_interest = pd.DataFrame([
        {"Date": "2024-01", "nike": 80, "potato": 40},
    ])
    trends_related = pd.DataFrame([
        {"Related Query": "nike shoes", "Value": 100, "Type": "rising",
         "Rank Type": "top", "Source Keywords": "nike"},
    ])
    mock_st.session_state.processed_data = ads_df
    mock_st.session_state.google_trends_tables = {
        "averages": trends_averages,
        "interest": trends_interest,
        "related": trends_related,
    }
    monkeypatch.setattr("components.results.st", mock_st)

    result = build_and_store_merged_ads_trends()

    assert result is not None
    assert mock_st.session_state.merged_ads_trends_data is not None
    merged = mock_st.session_state.merged_ads_trends_data
    for col in ["Trends Avg Interest", "Trends Geo", "Trends Timeframe"]:
        assert col in merged.columns, f"Missing Trends col: {col}"


# Purpose: build_and_store_merged_ads_trends returns None when google_trends_tables is missing.
def test_build_and_store_merged_ads_trends_noop_when_missing(monkeypatch):
    from components.results import build_and_store_merged_ads_trends

    mock_st = MagicMock()
    mock_st.session_state.processed_data = _ads_df_two_keywords()
    # No google_trends_tables set
    monkeypatch.setattr("components.results.st", mock_st)

    result = build_and_store_merged_ads_trends()

    assert result is None
    val = getattr(mock_st.session_state, "merged_ads_trends_data", None)
    assert val is None


# Purpose: build_and_store_merged_ads_trends returns None when averages table is absent or empty.
def test_build_and_store_merged_ads_trends_noop_when_averages_empty_or_absent(monkeypatch):
    from components.results import build_and_store_merged_ads_trends

    ads_df = _ads_df_two_keywords()

    # Case 1: google_trends_tables has no "averages" key
    mock_st_1 = MagicMock()
    mock_st_1.session_state.processed_data = ads_df
    mock_st_1.session_state.google_trends_tables = {"interest": pd.DataFrame()}
    monkeypatch.setattr("components.results.st", mock_st_1)
    result_1 = build_and_store_merged_ads_trends()
    assert result_1 is None

    # Case 2: google_trends_tables has empty "averages"
    mock_st_2 = MagicMock()
    mock_st_2.session_state.processed_data = ads_df
    mock_st_2.session_state.google_trends_tables = {"averages": pd.DataFrame()}
    monkeypatch.setattr("components.results.st", mock_st_2)
    result_2 = build_and_store_merged_ads_trends()
    assert result_2 is None

    # Case 3: google_trends_tables is empty dict
    mock_st_3 = MagicMock()
    mock_st_3.session_state.processed_data = ads_df
    mock_st_3.session_state.google_trends_tables = {}
    monkeypatch.setattr("components.results.st", mock_st_3)
    result_3 = build_and_store_merged_ads_trends()
    assert result_3 is None


# ---------------------------------------------------------------------------
# Render guard test
# ---------------------------------------------------------------------------

# Purpose: render_merged_ads_trends_results no-ops when merged data is empty/None.
def test_render_merged_ads_trends_results_noop_when_empty(monkeypatch):
    from components.results import render_merged_ads_trends_results

    mock_st = MagicMock()
    mock_st.session_state.merged_ads_trends_data = None
    monkeypatch.setattr("components.results.st", mock_st)

    # Should not raise
    render_merged_ads_trends_results()

    # Also test empty DataFrame
    mock_st_2 = MagicMock()
    mock_st_2.session_state.merged_ads_trends_data = pd.DataFrame()
    monkeypatch.setattr("components.results.st", mock_st_2)
    render_merged_ads_trends_results()


# ---------------------------------------------------------------------------
# State key + i18n keys
# ---------------------------------------------------------------------------

# Purpose: merged_ads_trends_data is declared in app.EXACT_STATE_KEYS.
def test_merged_ads_trends_state_key_in_defaults():
    assert "merged_ads_trends_data" in EXACT_STATE_KEYS, \
        "merged_ads_trends_data missing from EXACT_STATE_KEYS"


# Purpose: merged_ads_trends and trends_results_after_ads i18n keys exist in TRANSLATIONS.
def test_merged_ads_trends_i18n_keys_present():
    expected_keys = [
        "merged_ads_trends_header",
        "merged_ads_trends_desc",
        "trends_results_after_ads_header",
        "trends_results_after_ads_desc",
    ]
    for key in expected_keys:
        assert key in TRANSLATIONS, f"Missing key in TRANSLATIONS: {key}"
        entry = TRANSLATIONS[key]
        assert "ru" in entry, f"Missing 'ru' for key {key}"
        assert "uk" in entry, f"Missing 'uk' for key {key}"
        assert "en" in entry, f"Missing 'en' for key {key}"
