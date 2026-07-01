# MODULE_CONTRACT: cli.merge
# Purpose: Streamlit-free copy of the SERP/Trends per-keyword aggregation logic that lives inside
#   the Streamlit-coupled utils/pipeline.py. Provides aggregate_serp_per_keyword /
#   aggregate_trends_per_keyword / merge_enrichment, callable headlessly.
# Rationale: docs/cli-plan.md §2.2 item 3 + §10. The source helpers in utils/pipeline.py are pure
#   pandas but the module does `import streamlit` at top level, so importing ANY symbol from it
#   drags streamlit into sys.modules. To keep the CLI streamlit-free (HARD) we reproduce the logic
#   here. Drift is held to zero by test_cli_merge.py, which runs the SAME fixtures through both
#   copies and asserts equality (anti-drift parity check).
# Dependencies: pandas + stdlib only. NEVER streamlit, utils.pipeline, or config.i18n.
# Exports: normalize_keyword_for_lookup, aggregate_serp_per_keyword, aggregate_trends_per_keyword,
#   merge_enrichment.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-MERGE, docs/cli-plan.md §2.2 item 3
#   SOURCE OF TRUTH: utils/pipeline.py aggregate_serp_per_keyword (line ~2571) and
#   aggregate_trends_per_keyword (line ~2669).
# MODULE_MAP: cli/merge.py
# Public Functions: normalize_keyword_for_lookup, aggregate_serp_per_keyword,
#   aggregate_trends_per_keyword, merge_enrichment.
# Private Helpers: _aggregate_serp_group.
# Key Semantic Blocks: none.
# Critical Flows: serp_df + ads_df -> aggregate_serp_per_keyword -> ads + SERP cols; then trends_df
#   -> aggregate_trends_per_keyword -> ads + Trends cols.
# Verification: verification-plan.xml#V-18-MERGE
# CHANGE_SUMMARY: Phase B — streamlit-free copy of the two aggregate helpers + merge_enrichment
#   combiner (SERP then Trends). Behavior verified equal to utils.pipeline by test_cli_merge.py.

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

import pandas as pd


# ---------------------------------------------------------------------------
# normalize_keyword_for_lookup — verbatim copy of utils/pipeline.py:177
# (lowercase + strip quotes; case-insensitive join key)
# ---------------------------------------------------------------------------

def normalize_keyword_for_lookup(keyword: str) -> str:
    if keyword is None:
        return ""
    return str(keyword).lower().strip().strip('"').strip("'").strip()


# ---------------------------------------------------------------------------
# aggregate_serp_per_keyword — mirrors utils/pipeline.py:2571
# Aggregates SERP rows per keyword and left-joins the aggregates onto the Ads DataFrame.
# ---------------------------------------------------------------------------

def _aggregate_serp_group(group: pd.DataFrame) -> pd.Series:
    count = len(group)
    top_pos = group["Position"].min()
    if pd.isna(top_pos):
        top_pos = None

    sorted_group = group.sort_values("Position", na_position="last")
    seen: set = set()
    collected: list = []
    for _, row in sorted_group.iterrows():
        displayed = row.get("Displayed Link", "")
        if displayed and str(displayed).strip():
            domain = str(displayed).strip()
        else:
            raw_url = row.get("URL", "")
            if raw_url:
                try:
                    domain = urlparse(str(raw_url)).netloc
                    domain = domain.removeprefix("www.")
                except Exception:
                    domain = ""
            else:
                domain = ""
        if domain and domain not in seen:
            seen.add(domain)
            collected.append(domain)
            if len(collected) == 3:
                break
    top3 = ", ".join(collected)

    return pd.Series(
        {
            "SERP #results": count,
            "SERP top position": top_pos,
            "SERP top3 domains": top3,
        }
    )


def aggregate_serp_per_keyword(
    serp_df: Optional[pd.DataFrame],
    ads_df: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    """Aggregate SERP rows per keyword and left-join aggregates onto ads_df.

    Mirrors utils.pipeline.aggregate_serp_per_keyword exactly (see test_cli_merge parity check).
    """
    # Guard: ads_df None -> return None
    if ads_df is None:
        return None
    # Guard: ads_df empty or missing Keyword col -> return ads_df unchanged
    if getattr(ads_df, "empty", True) or "Keyword" not in ads_df.columns:
        return ads_df
    # Guard: serp_df None or empty -> return ads_df unchanged
    if serp_df is None or getattr(serp_df, "empty", True):
        return ads_df
    # Guard: serp_df missing Keyword col -> return ads_df unchanged
    if "Keyword" not in serp_df.columns:
        return ads_df

    # Work on copies (pure function)
    serp_copy = serp_df.copy()
    ads_copy = ads_df.copy()

    # Normalize keywords on both sides
    serp_copy["_norm_kw"] = serp_copy["Keyword"].apply(normalize_keyword_for_lookup)
    ads_copy["_norm_kw"] = ads_copy["Keyword"].apply(normalize_keyword_for_lookup)

    # Coerce Position to numeric
    serp_copy["Position"] = pd.to_numeric(serp_copy["Position"], errors="coerce")

    aggregates = (
        serp_copy.groupby("_norm_kw")[["Position", "URL", "Displayed Link"]]
        .apply(_aggregate_serp_group, include_groups=False)
        .reset_index()
    )

    # Left-join aggregates onto ads on normalized key
    result = ads_copy.merge(aggregates, on="_norm_kw", how="left")

    # Drop temp key
    result = result.drop(columns=["_norm_kw"])

    # Preserve ads_df original column order, append SERP cols at end
    base_cols = [c for c in ads_df.columns if c in result.columns]
    extra_cols = [c for c in result.columns if c not in base_cols]
    result = result[base_cols + extra_cols]

    return result


# ---------------------------------------------------------------------------
# aggregate_trends_per_keyword — mirrors utils/pipeline.py:2669
# Left-joins per-keyword Trends averages onto the Ads DataFrame.
# ---------------------------------------------------------------------------

def aggregate_trends_per_keyword(
    trends_df: Optional[pd.DataFrame],
    ads_df: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    """Left-join per-keyword Trends averages onto ads_df.

    Mirrors utils.pipeline.aggregate_trends_per_keyword exactly (see test_cli_merge parity check).
    """
    # Guard: ads_df None -> return None
    if ads_df is None:
        return None
    # Guard: ads_df empty or missing Keyword col -> return ads_df unchanged
    if getattr(ads_df, "empty", True) or "Keyword" not in ads_df.columns:
        return ads_df
    # Guard: trends_df None or empty -> return ads_df unchanged
    if trends_df is None or getattr(trends_df, "empty", True):
        return ads_df
    # Guard: trends_df missing Keyword col -> return ads_df unchanged
    if "Keyword" not in trends_df.columns:
        return ads_df

    # Work on copies (pure function)
    trends_copy = trends_df.copy()
    ads_copy = ads_df.copy()

    # Normalize keywords on both sides for case-insensitive join
    trends_copy["_norm_kw"] = trends_copy["Keyword"].apply(normalize_keyword_for_lookup)
    ads_copy["_norm_kw"] = ads_copy["Keyword"].apply(normalize_keyword_for_lookup)

    # Select only the trends columns we want to merge, renaming source -> result cols
    trends_select = trends_copy[["_norm_kw", "Average Interest", "Geo", "Timeframe"]].rename(
        columns={
            "Average Interest": "Trends Avg Interest",
            "Geo": "Trends Geo",
            "Timeframe": "Trends Timeframe",
        }
    )

    # Left-join trends onto ads on normalized key
    result = ads_copy.merge(trends_select, on="_norm_kw", how="left")

    # Drop temp key
    result = result.drop(columns=["_norm_kw"])

    # Preserve ads_df original column order, append Trends cols at end
    base_cols = [c for c in ads_df.columns if c in result.columns]
    extra_cols = [c for c in result.columns if c not in base_cols]
    result = result[base_cols + extra_cols]

    return result


# ---------------------------------------------------------------------------
# merge_enrichment — CLI-level combiner: ads -> +SERP cols -> +Trends cols
# ---------------------------------------------------------------------------

def merge_enrichment(
    ads_df: Optional[pd.DataFrame],
    serp_df: Optional[pd.DataFrame] = None,
    trends_df: Optional[pd.DataFrame] = None,
) -> Optional[pd.DataFrame]:
    """Apply SERP then Trends aggregation onto the ads DataFrame (SERP cols before Trends cols).

    Returns None only if ads_df is None. Pure: never mutates inputs.
    """
    if ads_df is None:
        return None
    result = aggregate_serp_per_keyword(serp_df, ads_df)
    result = aggregate_trends_per_keyword(trends_df, result)
    return result
