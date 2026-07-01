# MODULE_CONTRACT: tests/test_cli_output
# Purpose: TDD RED->GREEN for cli.output — DataFrame -> file writers (xlsx/csv/json) that round-trip
#   parse, plus the SEO-text sidecar path and the never-raises contract of write_report.
# Rationale: docs/cli-plan.md §3 step 9 + §7 Phase C. Export logic must live outside the orchestrator,
#   and the report must be machine-readable (the merge feature's output gap from session ac6169dd).
# Dependencies: cli.output, pandas, openpyxl. Deliberately NOT streamlit (ExcelExporter is clean).
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-OUTPUT, docs/cli-plan.md §3 step 9
# MODULE_MAP: tests/test_cli_output.py
# Public Functions: pytest test functions.
# Private Helpers: _fixture_df.
# Key Semantic Blocks: none.
# Critical Flows: DataFrame -> write_dataframe(fmt) -> read back -> equal contents.
# Verification: verification-plan.xml#V-18-OUTPUT
# CHANGE_SUMMARY: Phase C RED — round-trip xlsx/csv/json, sidecar path naming, write_report
#   never-raises + writes sidecar, unsupported-format raises.

import json
from pathlib import Path

import pandas as pd
import pytest


def _fixture_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Keyword": ["coffee", "Tea", "купить кофе"],
            "Volume": [100, 200, 300],
            "Competition": [0.1, 0.2, 0.3],
        }
    )


# ---------------------------------------------------------------------------
# Round-trip: write -> read back -> equal contents
# ---------------------------------------------------------------------------

def test_write_dataframe_xlsx_round_trips(tmp_path: Path) -> None:
    from cli.output import write_dataframe

    out = tmp_path / "report.xlsx"
    written = write_dataframe(_fixture_df(), str(out), "xlsx")
    assert written == str(out)
    back = pd.read_excel(out)
    pd.testing.assert_frame_equal(back, _fixture_df(), check_dtype=False)


def test_write_dataframe_csv_round_trips(tmp_path: Path) -> None:
    from cli.output import write_dataframe

    out = tmp_path / "report.csv"
    written = write_dataframe(_fixture_df(), str(out), "csv")
    assert written == str(out)
    back = pd.read_csv(out)
    pd.testing.assert_frame_equal(back, _fixture_df(), check_dtype=False)


def test_write_dataframe_json_round_trips(tmp_path: Path) -> None:
    from cli.output import write_dataframe

    out = tmp_path / "report.json"
    written = write_dataframe(_fixture_df(), str(out), "json")
    assert written == str(out)
    back = pd.DataFrame(json.loads(out.read_text(encoding="utf-8")))
    pd.testing.assert_frame_equal(back, _fixture_df(), check_dtype=False)


# ---------------------------------------------------------------------------
# write_report: never raises + sidecar
# ---------------------------------------------------------------------------

def test_write_report_creates_parent_dir_and_returns_path(tmp_path: Path) -> None:
    from cli.output import write_report

    out = tmp_path / "nested" / "deep" / "report.xlsx"
    written = write_report(_fixture_df(), str(out), "xlsx")
    assert written == str(out)
    assert out.exists()


def test_write_report_writes_seo_text_sidecar(tmp_path: Path) -> None:
    from cli.output import seo_text_sidecar_path, write_report

    out = tmp_path / "report.xlsx"
    write_report(_fixture_df(), str(out), "xlsx", seo_text="Generated SEO copy here")
    side = Path(seo_text_sidecar_path(str(out)))
    assert side.exists()
    assert side.read_text(encoding="utf-8") == "Generated SEO copy here"


# write_report must log + return None, never raise (exit-code contract).
def test_write_report_never_raises_on_unsupported_format(tmp_path: Path) -> None:
    from cli.output import write_report

    out = tmp_path / "report.xyz"
    written = write_report(_fixture_df(), str(out), "totally-unknown-fmt")
    assert written is None


# The low-level writer DOES raise so the orchestrator can decide (write_report swallows).
def test_write_dataframe_raises_on_unsupported_format(tmp_path: Path) -> None:
    from cli.output import write_dataframe

    with pytest.raises(ValueError):
        write_dataframe(_fixture_df(), str(tmp_path / "report.xyz"), "totally-unknown-fmt")


def test_seo_text_sidecar_path_is_stem_plus_seo_txt() -> None:
    from cli.output import seo_text_sidecar_path

    assert seo_text_sidecar_path("report.xlsx") == "report.seo.txt"
    # Path normalization is platform-dependent (fwd vs back slashes); assert by parts.
    side = seo_text_sidecar_path("/tmp/deep/out.json")
    assert side.endswith("out.seo.txt")
    assert "deep" in side
    assert not side.endswith(".json")
