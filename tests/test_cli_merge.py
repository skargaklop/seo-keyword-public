# MODULE_CONTRACT: tests/test_cli_merge
# Purpose: TDD coverage for cli.merge — the streamlit-free copy of the SERP/Trends aggregation
#   logic (docs/cli-plan.md §2.2 item 3, §3 step 8). The ANTI-DRIFT PARITY CHECK runs the SAME
#   fixtures through utils.pipeline.aggregate_* and cli.merge.aggregate_* and asserts equal output,
#   so the copy can never silently diverge from the source.
# Rationale: the true fix (shared utils/aggregation.py) is deferred (§9) because it would modify
#   utils/pipeline.py, violating the no-modify HARD constraint. The parity test holds drift to zero.
# Process-isolation note: the parity comparison imports utils.pipeline (which imports streamlit).
#   To avoid perturbing the rest of the pytest suite's streamlit state (ordering-dependent failures),
#   the utils.pipeline reference runs in an ISOLATED SUBPROCESS. cli.merge itself is tested in-process.
# Dependencies: cli.merge (in-process), utils.pipeline (subprocess only). pandas, pytest.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-MERGE, docs/cli-plan.md §2.2 item 3
# MODULE_MAP: tests/test_cli_merge.py
# Public Functions: pytest test functions + fixture builders.
# Private Helpers: _serp_rows, _ads_df, _trends_rows, _run_in_subprocess.
# Key Semantic Blocks: none.
# Critical Flows: build fixture DataFrames -> run cli.merge (in-proc) and utils.pipeline
#   (subprocess) -> assert equal columns+values.
# Verification: verification-plan.xml#V-18-MERGE
# CHANGE_SUMMARY: Phase B RED->GREEN — parity tests for aggregate_serp_per_keyword /
#   aggregate_trends_per_keyword clones; guard/None-input behavior; column-order preservation;
#   purity. utils.pipeline reference isolated to a subprocess to keep the suite order-independent.

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, List

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Subprocess helper — run a snippet in a clean interpreter (no shared global state)
# ---------------------------------------------------------------------------

# Execute `code` in a fresh python -c subprocess with the project root on sys.path.
#
# The snippet must print a single JSON line (its return value). Returns the parsed value.
def _run_in_subprocess(code: str) -> Any:
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(PROJECT_ROOT)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"subprocess failed (rc={result.returncode}):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    out = result.stdout.strip().splitlines()
    if not out:
        return None
    return json.loads(out[-1])


# ---------------------------------------------------------------------------
# Fixture builders (mirror the real SERP/Ads/Trends DataFrame schemas)
# ---------------------------------------------------------------------------

def _serp_rows(rows: List[dict]) -> pd.DataFrame:
    cols = ["Keyword", "Position", "Title", "URL", "Snippet", "Displayed Link", "Rich Snippet", "Provider"]
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]


def _ads_df(keywords: List[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Keyword": keywords,
            "Avg. Monthly Searches": [100 * (i + 1) for i in range(len(keywords))],
            "Competition": [0.1 * (i + 1) for i in range(len(keywords))],
        }
    )


def _trends_rows(rows: List[dict]) -> pd.DataFrame:
    cols = ["Keyword", "Average Interest", "Geo", "Timeframe", "Provider"]
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]


# ---------------------------------------------------------------------------
# cli.merge behavior (in-process — no streamlit involved)
# ---------------------------------------------------------------------------

@pytest.fixture
def serp_ads_pair():
    serp = _serp_rows(
        [
            {"Keyword": "купить кофе", "Position": 1, "URL": "https://a.com/x", "Displayed Link": "a.com"},
            {"Keyword": "купить кофе", "Position": 4, "URL": "https://b.com/y", "Displayed Link": "b.com"},
            {"Keyword": "купить кофе", "Position": 2, "URL": "https://c.com/z", "Displayed Link": "c.com"},
            {"Keyword": "Tea", "Position": 10, "URL": "https://d.com", "Displayed Link": "d.com"},
            {"Keyword": "noads", "Position": 3, "URL": "https://e.com", "Displayed Link": "e.com"},
        ]
    )
    ads = _ads_df(["Купить Кофе", "Tea", "milk"])  # note case + whitespace differences
    return serp, ads


# cli.merge.aggregate_serp_per_keyword appends the 3 SERP cols with correct values.
def test_serp_aggregation_cli_columns_and_values(serp_ads_pair):
    from cli.merge import aggregate_serp_per_keyword

    serp, ads = serp_ads_pair
    out = aggregate_serp_per_keyword(serp, ads)
    assert out is not None
    assert {"SERP #results", "SERP top position", "SERP top3 domains"} <= set(out.columns)
    # 3 ads rows preserved
    assert len(out) == 3
    # "Купить Кофе" normalized-matches the 3 "купить кофе" SERP rows
    coffee_row = out[out["Keyword"] == "Купить Кофе"].iloc[0]
    assert coffee_row["SERP #results"] == 3
    assert coffee_row["SERP top position"] == 1
    # best-rank-first: a.com(1), c.com(2), b.com(4)
    assert coffee_row["SERP top3 domains"] == "a.com, c.com, b.com"


# Pure-function guarantee: the copy must not mutate its inputs.
def test_serp_aggregation_is_pure_does_not_mutate_inputs(serp_ads_pair):
    from cli.merge import aggregate_serp_per_keyword

    serp, ads = serp_ads_pair
    serp_before = serp.copy(deep=True)
    ads_before = ads.copy(deep=True)
    aggregate_serp_per_keyword(serp, ads)
    pd.testing.assert_frame_equal(serp, serp_before)
    pd.testing.assert_frame_equal(ads, ads_before)


# cli.merge.aggregate_trends_per_keyword appends the 3 Trends cols.
def test_trends_aggregation_cli_columns_and_values():
    from cli.merge import aggregate_trends_per_keyword

    trends = _trends_rows(
        [
            {"Keyword": "Tea", "Average Interest": 55.0, "Geo": "", "Timeframe": "today 12-m"},
            {"Keyword": "coffee", "Average Interest": 72.5, "Geo": "", "Timeframe": "today 12-m"},
        ]
    )
    ads = _ads_df(["Tea", "Coffee", "milk"])
    out = aggregate_trends_per_keyword(trends, ads)
    assert out is not None
    assert {"Trends Avg Interest", "Trends Geo", "Trends Timeframe"} <= set(out.columns)
    tea = out[out["Keyword"] == "Tea"].iloc[0]
    assert tea["Trends Avg Interest"] == 55.0


# High-level merge: SERP cols then Trends cols appended onto ads, in that order.
def test_merge_combined_left_joins_serp_then_trends_onto_ads(serp_ads_pair):
    from cli.merge import merge_enrichment

    serp, ads = serp_ads_pair
    trends = _trends_rows(
        [{"Keyword": "Tea", "Average Interest": 55.0, "Geo": "", "Timeframe": "today 12-m"}]
    )
    merged = merge_enrichment(ads, serp_df=serp, trends_df=trends)
    assert merged is not None
    cols = list(merged.columns)
    assert cols.index("SERP #results") < cols.index("Trends Avg Interest")


@pytest.mark.parametrize(
    "serp,ads,expect_none",
    [
        (None, _ads_df(["x"]), False),  # serp None -> ads unchanged (not None)
        (_serp_rows([]), _ads_df(["x"]), False),
        (_serp_rows([{"Keyword": "x", "Position": 1}]), None, True),  # ads None -> None
        (_serp_rows([{"Keyword": "x", "Position": 1}]), pd.DataFrame({"Foo": [1]}), False),
    ],
)
# Guard behavior: bad inputs return ads unchanged (or None only when ads is None).
def test_serp_aggregation_guards(serp, ads, expect_none):
    from cli.merge import aggregate_serp_per_keyword

    out = aggregate_serp_per_keyword(serp, ads)
    if expect_none:
        assert out is None
    else:
        assert out is not None


# ---------------------------------------------------------------------------
# Anti-drift PARITY vs utils.pipeline — run in an isolated subprocess
# (utils.pipeline imports streamlit; isolating keeps the pytest suite order-independent)
# ---------------------------------------------------------------------------

# Run both aggregators on a shared fixture in a clean interpreter; return both as JSON.
def _parity_serp_subprocess() -> dict:
    code = r'''
import json
import pandas as pd
from cli.merge import aggregate_serp_per_keyword as cli_agg
from utils.pipeline import aggregate_serp_per_keyword as ref_agg

serp = pd.DataFrame([
    {"Keyword":"coffee","Position":1,"URL":"https://a.com/x","Displayed Link":"a.com","Title":"","Snippet":"","Rich Snippet":None,"Provider":"p"},
    {"Keyword":"coffee","Position":4,"URL":"https://b.com/y","Displayed Link":"b.com","Title":"","Snippet":"","Rich Snippet":None,"Provider":"p"},
    {"Keyword":"coffee","Position":2,"URL":"https://c.com/z","Displayed Link":"c.com","Title":"","Snippet":"","Rich Snippet":None,"Provider":"p"},
    {"Keyword":"Tea","Position":10,"URL":"https://d.com","Displayed Link":"d.com","Title":"","Snippet":"","Rich Snippet":None,"Provider":"p"},
])
ads = pd.DataFrame({"Keyword":["Coffee","Tea"],"Volume":[100,200]})
exp = ref_agg(serp, ads)
act = cli_agg(serp, ads)
print(json.dumps({
    "exp_cols": list(exp.columns),
    "act_cols": list(act.columns),
    "exp_records": exp.to_dict(orient="records"),
    "act_records": act.to_dict(orient="records"),
}))
'''
    return _run_in_subprocess(code)


# Anti-drift: cli.merge.aggregate_serp_per_keyword == utils.pipeline version (subprocess).
def test_serp_aggregation_parity_matches_utils_pipeline():
    data = _parity_serp_subprocess()
    assert data["act_cols"] == data["exp_cols"], (
        f"column mismatch: cli={data['act_cols']} ref={data['exp_cols']}"
    )
    # Compare values via pandas round-trip
    exp = pd.DataFrame(data["exp_records"])
    act = pd.DataFrame(data["act_records"])
    pd.testing.assert_frame_equal(
        act.reset_index(drop=True), exp.reset_index(drop=True), check_dtype=False
    )


def _parity_trends_subprocess() -> dict:
    code = r'''
import json
import pandas as pd
from cli.merge import aggregate_trends_per_keyword as cli_agg
from utils.pipeline import aggregate_trends_per_keyword as ref_agg

trends = pd.DataFrame([
    {"Keyword":"Tea","Average Interest":55.0,"Geo":"","Timeframe":"today 12-m","Provider":"p"},
    {"Keyword":"coffee","Average Interest":72.5,"Geo":"","Timeframe":"today 12-m","Provider":"p"},
])
ads = pd.DataFrame({"Keyword":["Tea","Coffee"],"Volume":[100,200]})
exp = ref_agg(trends, ads)
act = cli_agg(trends, ads)
print(json.dumps({
    "exp_cols": list(exp.columns),
    "act_cols": list(act.columns),
    "exp_records": exp.to_dict(orient="records"),
    "act_records": act.to_dict(orient="records"),
}))
'''
    return _run_in_subprocess(code)


# Anti-drift: cli.merge.aggregate_trends_per_keyword == utils.pipeline version (subprocess).
def test_trends_aggregation_parity_matches_utils_pipeline():
    data = _parity_trends_subprocess()
    assert data["act_cols"] == data["exp_cols"]
    exp = pd.DataFrame(data["exp_records"])
    act = pd.DataFrame(data["act_records"])
    pd.testing.assert_frame_equal(
        act.reset_index(drop=True), exp.reset_index(drop=True), check_dtype=False
    )
