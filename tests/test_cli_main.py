# MODULE_CONTRACT: tests/test_cli_main
# Purpose: TDD RED->GREEN for cli.main argparse skeleton, dispatch, and exit codes.
# Rationale: Phase A of docs/cli-plan.md — the CLI entry surface must parse subcommands and exit cleanly.
# Dependencies: cli.main.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-MAIN
# MODULE_MAP: tests/test_cli_main.py
# Public Functions: pytest test functions.
# Private Helpers: _run_in_subprocess (clean-interpreter streamlit independence check).
# Key Semantic Blocks: none.
# Critical Flows: build_parser() -> parse known args -> dispatch -> int exit code.
# Verification: verification-plan.xml#V-18-MAIN
# CHANGE_SUMMARY: Phase A RED — assert parser parses `run` flags, unknown command errors, main() returns int,
#   and importing cli.main does not pull streamlit into sys.modules. The independence check runs in an
#   ISOLATED SUBPROCESS: the previous in-process `sys.modules.pop("streamlit")` was destructive — it
#   left streamlit's DeltaGeneratorSingleton half-initialized, breaking later streamlit-based tests with
#   "instance already exists!" (ordering-dependent failures across the suite).

import os
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Import cli.main fresh; returns the module object.
def _import_cli_main():
    import importlib

    return importlib.import_module("cli.main")


# build_parser() must parse `run --keywords a,b --out report.xlsx`.
def test_build_parser_parses_run_with_keywords_and_out() -> None:
    cli_main = _import_cli_main()
    parser = cli_main.build_parser()
    args = parser.parse_args(["run", "--keywords", "a,b", "--out", "report.xlsx"])
    assert args.command == "run"
    assert args.out == "report.xlsx"
    # keywords may be stored raw (comma string) — just assert it captured the value
    assert args.keywords == "a,b"


# All documented subcommands must be accepted by the parser.
def test_build_parser_has_all_subcommands() -> None:
    cli_main = _import_cli_main()
    parser = cli_main.build_parser()
    expected_commands = {
        "run",
        "ads",
        "serp",
        "trends",
        "seo-text",
        "scrape",
        "config",
        "version",
        "register",
    }
    for cmd in expected_commands:
        args = parser.parse_args([cmd])
        assert args.command == cmd, f"subcommand {cmd!r} not parsed"


def test_top_level_help_documents_commands_and_examples() -> None:
    cli_main = _import_cli_main()
    parser = cli_main.build_parser()
    help_text = parser.format_help()

    assert "Examples:" in help_text
    assert "seos-cli run --keywords" in help_text
    assert "seos-cli config show" in help_text
    assert "run" in help_text
    assert "config" in help_text
    assert "register" in help_text


def test_run_help_documents_pipeline_flags_and_step_values() -> None:
    cli_main = _import_cli_main()
    parser = cli_main.build_parser()
    run_parser = parser._subparsers._group_actions[0].choices["run"]
    help_text = run_parser.format_help()

    assert "Examples:" in help_text
    assert "--keywords" in help_text
    assert "--from-file" in help_text
    assert "--steps" in help_text
    assert "validate,scrape,llm-extract,ads,serp,trends,seo-text,merge,export" in help_text
    assert "--workdir" in help_text
    assert "--resume" in help_text


def test_profile_command_help_explains_fixed_pipeline_steps() -> None:
    cli_main = _import_cli_main()
    parser = cli_main.build_parser()
    choices = parser._subparsers._group_actions[0].choices

    assert "Fixed steps: serp, merge, export" in choices["serp"].format_help()
    assert "Fixed steps: trends, merge, export" in choices["trends"].format_help()
    assert "Fixed steps: validate, scrape, llm-extract, export" in choices["scrape"].format_help()


def test_nested_config_help_documents_show_and_check() -> None:
    cli_main = _import_cli_main()
    parser = cli_main.build_parser()
    config_parser = parser._subparsers._group_actions[0].choices["config"]
    help_text = config_parser.format_help()

    assert "Examples:" in help_text
    assert "show" in help_text
    assert "check" in help_text
    assert "seos-cli config show" in help_text
    assert "seos-cli config check" in help_text


# An unknown subcommand must make argparse error (SystemExit, non-zero).
def test_unknown_command_errors() -> None:
    cli_main = _import_cli_main()
    parser = cli_main.build_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["definitely-not-a-command"])
    assert excinfo.value.code != 0


# main(argv) must return an integer process exit code.
def test_main_returns_int_exit_code() -> None:
    cli_main = _import_cli_main()
    code = cli_main.main(["version"])
    assert isinstance(code, int)


# main() on an unknown command returns a non-zero exit code (does not raise).
def test_main_unknown_command_returns_nonzero() -> None:
    cli_main = _import_cli_main()
    code = cli_main.main(["definitely-not-a-command"])
    assert code != 0


def test_build_parser_parses_config_show_subcommand() -> None:
    cli_main = _import_cli_main()
    parser = cli_main.build_parser()
    args = parser.parse_args(["config", "show"])
    assert args.command == "config"
    assert args.config_command == "show"


def test_config_show_reports_provider_presence_without_secret_values() -> None:
    code = (
        "import json, io, contextlib\n"
        "import cli.main as M\n"
        "buf = io.StringIO()\n"
        "with contextlib.redirect_stdout(buf):\n"
        "    rc = M.main(['config', 'show'])\n"
        "print(json.dumps({'rc': rc, 'stdout': buf.getvalue()}))\n"
    )
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONPATH": str(PROJECT_ROOT),
        "OPENAI_API_KEY": "secret-openai-value",
        "SERPAPI_KEY": "secret-serp-value",
    }
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["rc"] == 0
    assert "openai" in data["stdout"].lower()
    assert "present" in data["stdout"].lower()
    assert "secret-openai-value" not in data["stdout"]
    assert "secret-serp-value" not in data["stdout"]


def test_config_check_returns_nonzero_when_no_api_keys_present() -> None:
    code = (
        "import json, io, contextlib\n"
        "import cli.main as M\n"
        "buf = io.StringIO()\n"
        "with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):\n"
        "    rc = M.main(['config', 'check'])\n"
        "print(json.dumps({'rc': rc, 'stdout': buf.getvalue()}))\n"
    )
    env = {
        "SEO_DISABLE_DOTENV": "1",
        "PATH": os.environ.get("PATH", ""),
        "PATHEXT": os.environ.get("PATHEXT", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "WINDIR": os.environ.get("WINDIR", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
        "USERPROFILE": os.environ.get("USERPROFILE", ""),
        "PYTHONUTF8": "1",
        "PYTHONPATH": str(PROJECT_ROOT),
        "OPENAI_API_KEY": "",
        "SERPAPI_KEY": "",
        "SERPER_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "GOOGLE_API_KEY": "",
        "GEMINI_API_KEY": "",
        "OPENROUTER_API_KEY": "",
        "BRAVE_SEARCH_API_KEY": "",
        "SEARCHAPI_IO_KEY": "",
        "ZENSERP_KEY": "",
        "SCRAPERAPI_KEY": "",
        "DATAFORSEO_LOGIN": "",
        "DATAFORSEO_PASSWORD": "",
        "SERPSTAT_TOKEN": "",
        "SEMRUSH_API_KEY": "",
        "SERPSTACK_KEY": "",
        "SCALESERP_KEY": "",
        "VALUESERP_KEY": "",
        "GOOGLE_ADS_DEVELOPER_TOKEN": "",
        "GOOGLE_ADS_CLIENT_ID": "",
        "GOOGLE_ADS_CLIENT_SECRET": "",
        "GOOGLE_ADS_REFRESH_TOKEN": "",
    }
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


# HARD independence gate (Phase A preview of Phase B): importing cli.main must
# not leave streamlit in sys.modules.
#
# Run in an ISOLATED SUBPROCESS so the check starts from a truly clean interpreter where streamlit
# has never been loaded. Doing sys.modules.pop("streamlit") in-process is destructive: it leaves
# streamlit's DeltaGeneratorSingleton half-initialized, which then breaks later tests' streamlit
# setup with 'instance already exists' (ordering-dependent failures). A subprocess is also a
# STRONGER guarantee.
def test_importing_cli_main_does_not_import_streamlit() -> None:
    code = (
        "import sys, importlib\n"
        "importlib.import_module('cli.main')\n"
        "assert 'streamlit' not in sys.modules, 'cli.main pulled in streamlit'\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(PROJECT_ROOT)},
    )
    assert result.returncode == 0, (
        f"subprocess import check failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "OK" in result.stdout
