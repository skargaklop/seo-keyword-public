# MODULE_CONTRACT: cli.output
# Purpose: DataFrame -> file writers (xlsx/csv/json) for seos-cli, written directly via pandas +
#   openpyxl so an arbitrary user --out path is honored. Also writes an optional SEO-text sidecar.
# Rationale: docs/cli-plan.md §3 step 9 + §7 Phase C. Keeps export logic out of the orchestrator.
#   (Not utils.excel_exporter.ExcelExporter — that sandboxes to outputs/; the CLI must write anywhere.)
# Dependencies: pandas, openpyxl, utils.logger (all streamlit-free). NEVER streamlit/utils.pipeline/config.i18n.
# Exports: write_report, write_dataframe.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-OUTPUT, docs/cli-plan.md §3 step 9
# MODULE_MAP: cli/output.py
# Public Functions: write_report, write_dataframe, seo_text_sidecar_path.
# Private Helpers: none.
# Key Semantic Blocks: none.
# Critical Flows: DataFrame -> format -> file on disk (round-trip parseable).
# Verification: verification-plan.xml#V-18-OUTPUT
# CHANGE_SUMMARY: Phase B (minimal, to unblock pipeline) + Phase C (TDD GREEN). xlsx/csv/json
#   written DIRECTLY via pandas + openpyxl (NOT ExcelExporter, which sandboxes to outputs/ and so
#   can't honor an arbitrary user --out path — the Phase C RED round-trip test caught this).
#   SEO text written to a .txt sidecar when provided. write_report never raises (exit-code contract).

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from utils.logger import logger


# Path of the SEO-text sidecar (same stem as the report, .txt extension).
def seo_text_sidecar_path(out_path: str) -> str:
    stem = Path(out_path).with_suffix("")
    return str(stem) + ".seo.txt"


# Write a single DataFrame to disk in the requested format. Returns out_path.
#
# Raises on failure so callers can decide (the orchestrator logs + continues).
#
# NOTE: this writes directly via pandas + openpyxl, NOT via utils.excel_exporter.ExcelExporter,
# because ExcelExporter sandboxes all exports to the app's outputs/ directory (its
# _validate_export_path rejects arbitrary paths). The CLI must honor an arbitrary user `--out`
# path, so we write there directly.
def write_dataframe(df: pd.DataFrame, out_path: str, fmt: str) -> str:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt_l = (fmt or "xlsx").lower()

    if fmt_l == "xlsx":
        df.to_excel(path, index=False, engine="openpyxl")
    elif fmt_l == "csv":
        df.to_csv(path, index=False, encoding="utf-8")
    elif fmt_l == "json":
        records = df.to_dict(orient="records")
        path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    else:
        raise ValueError(f"unsupported format: {fmt!r}")

    return str(path)


def write_report(
    df: pd.DataFrame,
    out_path: str,
    fmt: str = "xlsx",
    seo_text: Optional[str] = None,
) -> Optional[str]:
    """Write the report DataFrame (and optional SEO-text sidecar). Returns the written path or None.

    Never raises: logs and returns None on failure so the pipeline keeps its exit-code contract.
    """
    try:
        written = write_dataframe(df, out_path, fmt)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"cli: failed to write report to {out_path} ({fmt}): {exc}")
        return None

    if seo_text:
        try:
            Path(seo_text_sidecar_path(out_path)).write_text(seo_text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"cli: failed to write SEO-text sidecar: {exc}")

    return written
