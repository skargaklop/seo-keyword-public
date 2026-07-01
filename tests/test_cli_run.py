# MODULE_CONTRACT: tests/test_cli_run
# Purpose: TDD RED->GREEN for the `seos-cli run` command — argv parsing -> EnrichmentConfig ->
#   orchestrator invocation, with the checkpoint workdir/resume/clean flags threaded through.
# Rationale: docs/cli-plan.md §4 (command surface) + §6.1 (checkpoint) + §7 Phase C2/E. The run
#   command must turn argparse flags into an EnrichmentConfig and call run_enrichment, honoring
#   --workdir/--resume/--clean. It must NOT import streamlit.
# Process-isolation note: run_enrichment transitively imports utils/ stage modules (streamlit-free),
# but exercising it in the pytest process perturbs shared global state that later streamlit-based
# tests depend on. So the run handler is exercised in an ISOLATED SUBPROCESS that injects a fake
# run_enrichment via cli.main's _inject_run hook (dependency injection, no unittest.mock).
# Dependencies: cli.main (subprocess), pandas, pytest.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-MAIN, docs/cli-plan.md §4, §6.1
# MODULE_MAP: tests/test_cli_run.py
# Public Functions: pytest test functions.
# Private Helpers: _run (subprocess harness).
# Key Semantic Blocks: none.
# Critical Flows: argv -> build EnrichmentConfig -> run_enrichment(config, checkpoint=...) -> int.
# Verification: verification-plan.xml#V-18-MAIN
# CHANGE_SUMMARY: Phase C2/E RED — run command parses keywords/steps/out/format/workdir/resume/clean
#   into EnrichmentConfig and invokes run_enrichment (DI fakes in subprocess); --clean wipes workdir.

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Run `cli.main.main(argv)` in a subprocess with a fake run_enrichment injected.
#
# Prints JSON: {exit_code, keywords, urls, steps, out, fmt, workdir, resume, clean, called, error}.
def _run(argv: list[str], inject: Dict[str, Any]) -> Dict[str, Any]:
    inject_json = json.dumps(inject)
    code = (
        "import json, sys\n"
        "import cli.main as M\n"
        f"argv = {argv!r}\n"
        f"inject = json.loads({inject_json!r})\n"
        "seen = {}\n"
        "def fake_run(config, **k):\n"
        "    seen['called'] = True\n"
        "    seen['keywords'] = list(config.keywords)\n"
        "    seen['urls'] = list(config.urls)\n"
        "    seen['steps'] = list(config.steps) if config.steps else None\n"
        "    seen['out'] = config.out\n"
        "    seen['fmt'] = config.fmt\n"
        "    seen['workdir'] = getattr(config, 'workdir', None)\n"
        "    seen['resume'] = getattr(config, 'resume', None)\n"
        "    seen['clean'] = getattr(config, 'clean', None)\n"
        "    seen['kwargs'] = {kk: str(vv) for kk, vv in k.items()}\n"
        "    return None\n"
        "M._inject_run(fake_run)\n"
        "try:\n"
        "    code = M.main(argv)\n"
        "    err = None\n"
        "except Exception as e:\n"
        "    import traceback; err = traceback.format_exc(); code = -1\n"
        "seen['exit_code'] = code\n"
        "seen['error'] = err\n"
        "print(json.dumps(seen, default=str))\n"
    )
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
            f"subprocess failed (rc={result.returncode}):\nSTDERR:\n{result.stderr}\n"
            f"STDOUT:\n{result.stdout}"
        )
    lines = [l for l in result.stdout.strip().splitlines() if l.strip().startswith("{")]
    assert lines, f"no JSON. stdout={result.stdout}\nstderr={result.stderr}"
    return json.loads(lines[-1])


def test_run_parses_keywords_into_config() -> None:
    data = _run(["run", "--keywords", "coffee, tea", "--out", "r.xlsx"], {})
    assert data["error"] is None, data["error"]
    assert data["exit_code"] == 0
    assert data["called"] is True
    assert data["keywords"] == ["coffee", "tea"]
    assert data["out"] == "r.xlsx"


def test_run_parses_steps_subset() -> None:
    data = _run(["run", "--keywords", "x", "--steps", "ads,serp"], {})
    assert data["error"] is None, data["error"]
    assert data["steps"] == ["ads", "serp"]


def test_run_parses_format_and_default_out() -> None:
    data = _run(["run", "--keywords", "x", "--format", "json"], {})
    assert data["error"] is None, data["error"]
    assert data["fmt"] == "json"


def test_run_threads_workdir_resume_clean() -> None:
    data = _run(
        ["run", "--keywords", "x", "--workdir", ".ck", "--resume", "last", "--clean"],
        {},
    )
    assert data["error"] is None, data["error"]
    assert data["workdir"] == ".ck"
    assert data["resume"] == "last"
    assert data["clean"] is True


def test_run_from_file_splits_urls_and_keywords(tmp_path: Path) -> None:
    source = tmp_path / "mixed.txt"
    source.write_text(
        "coffee beans\nhttps://example.com/page\ntea\nhttp://example.org\n",
        encoding="utf-8",
    )
    data = _run(["run", "--from-file", str(source)], {})
    assert data["error"] is None, data["error"]
    assert data["keywords"] == ["coffee beans", "tea"]
    assert data["urls"] == ["https://example.com/page", "http://example.org"]


def test_run_from_file_keeps_explicit_keywords_and_urls(tmp_path: Path) -> None:
    source = tmp_path / "mixed.txt"
    source.write_text("alpha\nhttps://example.com/from-file\n", encoding="utf-8")
    data = _run(
        [
            "run",
            "--keywords",
            "coffee",
            "--urls",
            "https://explicit.example/path",
            "--from-file",
            str(source),
        ],
        {},
    )
    assert data["error"] is None, data["error"]
    assert data["keywords"] == ["coffee", "alpha"]
    assert data["urls"] == [
        "https://explicit.example/path",
        "https://example.com/from-file",
    ]


def test_run_rejects_unknown_step_with_nonzero_exit() -> None:
    data = _run(["run", "--keywords", "x", "--steps", "ads,nope"], {})
    assert data["exit_code"] != 0
    assert data.get("called") is not True


@pytest.mark.parametrize(
    ("argv", "expected_steps", "expected_keywords", "expected_urls"),
    [
        (["ads", "--keywords", "coffee"], ["ads", "export"], ["coffee"], []),
        (["serp", "--keywords", "coffee"], ["serp", "merge", "export"], ["coffee"], []),
        (["trends", "--keywords", "coffee"], ["trends", "merge", "export"], ["coffee"], []),
        (["seo-text", "--keywords", "coffee"], ["seo-text", "export"], ["coffee"], []),
        (
            ["scrape", "--urls", "https://example.com"],
            ["validate", "scrape", "llm-extract", "export"],
            [],
            ["https://example.com"],
        ),
    ],
)
def test_practical_subcommands_dispatch_into_run_profiles(
    argv: list[str],
    expected_steps: list[str],
    expected_keywords: list[str],
    expected_urls: list[str],
) -> None:
    data = _run(argv, {})
    assert data["error"] is None, data["error"]
    assert data["exit_code"] == 0
    assert data["steps"] == expected_steps
    assert data["keywords"] == expected_keywords
    assert data["urls"] == expected_urls


def test_scrape_without_urls_is_rejected() -> None:
    data = _run(["scrape"], {})
    assert data["exit_code"] != 0
    assert data.get("called") is not True


def test_serp_requires_keywords() -> None:
    data = _run(["serp"], {})
    assert data["exit_code"] != 0
    assert data.get("called") is not True


def test_run_returns_nonzero_when_pipeline_marks_export_failed() -> None:
    inject = {"export_failed": True}
    inject_json = json.dumps(inject)
    code = (
        "import json\n"
        "import cli.main as M\n"
        "inject = json.loads(" + repr(inject_json) + ")\n"
        "def fake_run(config, **k):\n"
        "    from types import SimpleNamespace\n"
        "    return SimpleNamespace(export_failed=inject['export_failed'])\n"
        "M._inject_run(fake_run)\n"
        "rc = M.main(['run', '--keywords', 'coffee'])\n"
        "print(json.dumps({'rc': rc}))\n"
    )
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(PROJECT_ROOT)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["rc"] != 0
