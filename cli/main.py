# MODULE_CONTRACT: cli.main
# Purpose: argparse entry point for `seos-cli`. Builds the parser, dispatches subcommands,
#   and returns integer process exit codes. NEVER imports streamlit.
# Rationale: Phase A of docs/cli-plan.md §4/§7. This module defines the command surface only;
#   heavy logic lives in cli.pipeline (Phase B), cli.output (Phase C), cli.checkpoint (Phase C2),
#   cli.registration (Phase D).
# Dependencies: stdlib argparse only at this phase. Subcommand handlers import other cli.* modules
#   lazily inside their dispatch functions so that e.g. `--help` never pulls optional deps.
#   ALLOWED utils/ imports (enforced by test_cli_independence.py): the 7 streamlit-free modules.
#   FORBIDDEN: streamlit, utils.pipeline, config.i18n.
# Exports: build_parser(), dispatch(args), main(argv) -> int.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-MAIN, docs/cli-plan.md §4
# MODULE_MAP: cli/main.py
# Public Functions: build_parser, dispatch, main.
# Private Helpers: _add_run_parser, _cmd_version.
# Key Semantic Blocks: none yet (dispatch table is flat).
# Critical Flows: argv -> build_parser().parse_args() -> dispatch(args) -> int.
# Verification: verification-plan.xml#V-18-MAIN
# CHANGE_SUMMARY: Phase A — argparse skeleton with all subcommands from §4; dispatch returns int;
#   version handler implemented; other handlers are stubs returning exit 0 with a TODO note until
#   their phase ships. Imported with no streamlit.

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Help formatting
# ---------------------------------------------------------------------------

class _RichHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawDescriptionHelpFormatter,
):
    """Preserve multi-line examples while still showing argument defaults."""


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

CLI_VERSION = "0.1.0"


# Best-effort, dependency-light summary of configured providers.
#
# Kept defensive: if utils imports are unavailable we still return a string rather than
# crashing, so `seos-cli version` always works.
def _provider_registry_summary() -> str:
    lines: List[str] = []
    try:
        from config.settings import SERP_PROVIDER_OPTIONS  # streamlit-free

        lines.append(f"SERP providers known: {len(SERP_PROVIDER_OPTIONS)}")
    except Exception as exc:  # noqa: BLE001 — version must never crash
        lines.append(f"SERP providers: (unavailable: {exc})")
    return "\n".join(lines)


def _cmd_version(args: argparse.Namespace) -> int:
    print(f"seos-cli {CLI_VERSION}")
    summary = _provider_registry_summary()
    if summary:
        print(summary)
    return 0


# ---------------------------------------------------------------------------
# Dependency-injection hook for the run handler
# ---------------------------------------------------------------------------

# By default, `seos-cli run` calls cli.pipeline.run_enrichment. Tests inject a fake via
# _inject_run(fn) so the run handler can be exercised in an isolated subprocess without importing
# the heavy stage modules (which would perturb shared global state for streamlit-based tests).
_RUN_ENRICHMENT: Optional[callable] = None  # type: ignore[type-arg]


# Test-only hook: override the run_enrichment callable used by `_cmd_run`.
def _inject_run(fn) -> None:  # type: ignore[no-untyped-def]
    global _RUN_ENRICHMENT
    _RUN_ENRICHMENT = fn


# EN-first bilingual user-message helper: returns "<English> / <Russian>" (space-slash-space).
def _bi(en: str, ru: str) -> str:
    return f"{en} / {ru}"


# Split a comma-separated keywords string into a clean list (drops empties).
def _parse_keywords(raw: str) -> List[str]:
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]


# Parse `--steps` into a list, or None when the default (all) is requested.
def _parse_steps(raw: str) -> Optional[List[str]]:
    if not raw or raw.strip() == DEFAULT_STEPS:
        return None
    steps = [s.strip() for s in raw.split(",") if s.strip()]
    return steps or None


def _split_file_inputs(path: str) -> Tuple[List[str], List[str]]:
    keywords: List[str] = []
    urls: List[str] = []
    for line in _read_keywords_file(path):
        lowered = line.lower()
        if lowered.startswith(("http://", "https://")):
            urls.append(line)
        else:
            keywords.append(line)
    return keywords, urls


def _validate_steps(steps: Optional[List[str]]) -> Optional[str]:
    if not steps:
        return None
    invalid = [step for step in steps if step not in RUN_STEPS]
    if not invalid:
        return None
    return (
        f"unknown step(s): {', '.join(invalid)}. "
        f"Allowed steps: {', '.join(RUN_STEPS)}."
    )


# Build an EnrichmentConfig from parsed args and invoke the orchestrator.
def _cmd_run(args: argparse.Namespace) -> int:
    keywords = _parse_keywords(args.keywords)
    urls = list(args.urls or [])
    if args.from_file:
        file_keywords, file_urls = _split_file_inputs(args.from_file)
        keywords.extend(file_keywords)
        urls.extend(file_urls)

    steps = _parse_steps(args.steps)
    step_error = _validate_steps(steps)
    if step_error:
        print(_bi(f"seos-cli run: {step_error}", f"seos-cli run: {step_error}"), file=sys.stderr)
        return 2

    # Lazy import keeps `seos-cli run --help`/`version` free of the (streamlit-free but heavy)
    # utils/ stage modules; only `run` pays for them.
    from cli.pipeline import EnrichmentConfig, run_enrichment

    config = EnrichmentConfig(
        keywords=keywords,
        urls=urls,
        language=args.language or "en",
        llm_provider=args.provider or "openai",
        llm_model=args.model or "gpt-4o-mini",
        serp_provider=args.serp_provider,
        out=args.out,
        fmt=args.format,
        max_keywords=args.max_keywords,
        steps=steps,
        workdir=args.workdir,
        resume=args.resume,
        clean=args.clean,
    )

    runner = _RUN_ENRICHMENT if _RUN_ENRICHMENT is not None else run_enrichment
    try:
        result = runner(config)
    except Exception as exc:  # noqa: BLE001 — run command must return an exit code, not crash
        print(_bi(f"seos-cli run: failed: {exc}", f"seos-cli run: сбой: {exc}"), file=sys.stderr)
        return 1
    if getattr(result, "export_failed", False):
        print(_bi("seos-cli run: export failed", "seos-cli run: сбой экспорта"), file=sys.stderr)
        return 1
    return 0


# Read one keyword/URL per line from a text file (UTF-8). Missing file -> empty list.
def _read_keywords_file(path: str) -> List[str]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        print(_bi(f"seos-cli: could not read --from-file {path}: {exc}", f"seos-cli: не удалось прочитать --from-file {path}: {exc}"), file=sys.stderr)
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------

# Steps selectable via `run --steps` (docs/cli-plan.md §4)
RUN_STEPS = (
    "validate",
    "scrape",
    "llm-extract",
    "ads",
    "serp",
    "trends",
    "seo-text",
    "merge",
    "export",
)
DEFAULT_STEPS = ",".join(RUN_STEPS)
TOP_LEVEL_EPILOG = """Examples:
  seos-cli run --keywords "coffee, tea" --out reports/keywords.xlsx
  seos-cli run --from-file seeds.txt --steps ads,serp,merge,export --format csv --out report.csv
  seos-cli serp --keywords "wood wool, gift box filler" --format json --out serp.json
  seos-cli config show

Use `seos-cli <command> --help` for command-specific flags and examples.
"""
RUN_EPILOG = f"""Pipeline steps:
  {DEFAULT_STEPS}

Examples:
  seos-cli run --keywords "coffee, tea" --out report.xlsx
  seos-cli run --urls https://example.com/page --steps validate,scrape,llm-extract,ads,export
  seos-cli run --from-file seeds.txt --steps ads,serp,merge,export --workdir .seos --resume last
  seos-cli run --keywords "coffee" --format json --out report.json
"""
CONFIG_EPILOG = """Examples:
  seos-cli config show
  seos-cli config check

No secret values are printed. Provider credentials are reported only as present/missing.
"""
REGISTER_EPILOG = """Examples:
  seos-cli register --status
  seos-cli register
  seos-cli register --unregister

Windows registration writes a small user-level shim and never calls setx.
"""


def _profile_epilog(command: str, steps: List[str], example_input: str) -> str:
    fixed = ", ".join(steps)
    return f"""Fixed steps: {fixed}

This shortcut command delegates to `seos-cli run` with the fixed step list above.
All shared input/output/provider/checkpoint flags work the same as they do for `run`.

Examples:
  seos-cli {command} {example_input} --out {command}-report.xlsx
  seos-cli {command} --from-file seeds.txt --format csv --out {command}.csv
"""


def _add_shared_pipeline_args(
    p: argparse.ArgumentParser,
    *,
    include_keywords: bool = True,
    include_urls: bool = True,
    include_steps: bool = True,
) -> None:
    input_group = p.add_argument_group("Input")
    provider_group = p.add_argument_group("Providers and language")
    output_group = p.add_argument_group("Output")
    checkpoint_group = p.add_argument_group("Checkpoint and resume")

    input_group.add_argument(
        "--keywords",
        metavar="KW1,KW2",
        default="",
        help=(
            "Comma-separated seed keywords. Required for ads/serp/trends/seo-text "
            "unless keyword lines are provided through --from-file."
        ),
    )
    if include_urls:
        input_group.add_argument(
            "--urls",
            nargs="*",
            metavar="URL",
            default=[],
            help=(
                "One or more http(s) URLs to validate, scrape, and optionally use for "
                "LLM keyword extraction."
            ),
        )
    input_group.add_argument(
        "--from-file",
        metavar="PATH",
        default=None,
        help=(
            "UTF-8 text file with one keyword or URL per line. Lines starting with "
            "http:// or https:// are treated as URLs; all other lines are keywords."
        ),
    )
    if include_steps:
        input_group.add_argument(
            "--steps",
            metavar="CSV",
            default=DEFAULT_STEPS,
            help=(
                "Comma-separated subset of steps to run. "
                f"Available: {','.join(RUN_STEPS)}. Default: all applicable."
            ),
        )
    provider_group.add_argument("--language", default="en", help="Output language: en|ru|uk.")
    provider_group.add_argument(
        "--provider",
        default=None,
        help="LLM provider id for keyword extraction and SEO text generation.",
    )
    provider_group.add_argument("--model", default=None, help="LLM model id.")
    provider_group.add_argument(
        "--serp-provider",
        default=None,
        help="SERP provider id; omit to use the configured default/provider factory.",
    )
    output_group.add_argument("--out", metavar="PATH", default="report.xlsx", help="Output file path.")
    output_group.add_argument(
        "--format",
        default="xlsx",
        choices=("xlsx", "csv", "json"),
        help="Output format.",
    )
    output_group.add_argument(
        "--max-keywords",
        type=int,
        default=None,
        help="Cap the working keyword list after direct input and LLM extraction.",
    )
    # Checkpoint / resume flags (Phase C2) — accepted now, wired later.
    checkpoint_group.add_argument("--workdir", default=".seos", help="Checkpoint work directory.")
    checkpoint_group.add_argument("--resume", default=None, help="Run id to resume (or 'last').")
    checkpoint_group.add_argument(
        "--clean", action="store_true", help="Wipe the workdir before running."
    )


def _add_run_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "run",
        help="Master enrichment pipeline (chain the consequent steps).",
        description=(
            "Run the full headless enrichment pipeline or a selected subset of stages. "
            "Use this when you need precise control over stage order."
        ),
        epilog=RUN_EPILOG,
        formatter_class=_RichHelpFormatter,
    )
    _add_shared_pipeline_args(p)


def _add_profile_parser(
    subparsers: argparse._SubParsersAction,
    name: str,
    help_text: str,
    steps: List[str],
    example_input: str,
) -> None:
    p = subparsers.add_parser(
        name,
        help=help_text,
        description=help_text,
        epilog=_profile_epilog(name, steps, example_input),
        formatter_class=_RichHelpFormatter,
    )
    _add_shared_pipeline_args(p, include_steps=False)


# Construct the top-level argument parser for seos-cli.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seos-cli",
        description=(
            "Headless SEO data-enrichment CLI. "
            "Run `seos-cli <command> --help` for command-specific options."
        ),
        epilog=TOP_LEVEL_EPILOG,
        formatter_class=_RichHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"seos-cli {CLI_VERSION}")
    subparsers = parser.add_subparsers(dest="command")

    _add_run_parser(subparsers)

    _add_profile_parser(
        subparsers,
        "ads",
        "Google Ads keyword ideas/metrics only.",
        ["ads", "export"],
        '--keywords "coffee, tea"',
    )
    _add_profile_parser(
        subparsers,
        "serp",
        "SERP analysis only.",
        ["serp", "merge", "export"],
        '--keywords "wood wool, gift box filler"',
    )
    _add_profile_parser(
        subparsers,
        "trends",
        "Google Trends analysis only.",
        ["trends", "merge", "export"],
        '--keywords "coffee, tea"',
    )
    _add_profile_parser(
        subparsers,
        "seo-text",
        "Generate SEO copy from keywords.",
        ["seo-text", "export"],
        '--keywords "coffee beans"',
    )
    _add_profile_parser(
        subparsers,
        "scrape",
        "Validate and scrape URLs, then extract keywords from page content.",
        ["validate", "scrape", "llm-extract", "export"],
        "--urls https://example.com/page",
    )

    config_p = subparsers.add_parser(
        "config",
        help="Inspect resolved config / API keys.",
        description=(
            "Inspect provider credential availability without printing secret values. "
            "Use nested commands for human-readable status or CI-friendly validation."
        ),
        epilog=CONFIG_EPILOG,
        formatter_class=_RichHelpFormatter,
    )
    config_sub = config_p.add_subparsers(
        dest="config_command",
        metavar="{show,check}",
        title="config commands",
    )
    config_sub.add_parser(
        "show",
        help="Print provider availability as present/missing.",
        description="Print provider availability as present/missing. Secret values are never printed.",
        epilog="Example:\n  seos-cli config show",
        formatter_class=_RichHelpFormatter,
    )
    config_sub.add_parser(
        "check",
        help="Exit non-zero when no usable provider credentials are configured.",
        description="Return 0 when at least one provider is configured; otherwise return non-zero.",
        epilog="Example:\n  seos-cli config check",
        formatter_class=_RichHelpFormatter,
    )

    subparsers.add_parser("version", help="Print version + provider registry summary.")

    register_p = subparsers.add_parser(
        "register",
        help="Install the seos-cli command into PATH. Idempotent.",
        description=(
            "Install, inspect, or remove the user-level seos-cli shim. "
            "Registration is reversible and avoids setx PATH truncation."
        ),
        epilog=REGISTER_EPILOG,
        formatter_class=_RichHelpFormatter,
    )
    register_p.add_argument(
        "--unregister", action="store_true", help="Remove the seos-cli shim from PATH."
    )
    register_p.add_argument(
        "--status", action="store_true", help="Print shim location / PATH state, change nothing."
    )

    return parser


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _require_any_keywords(args: argparse.Namespace, command: str) -> bool:
    inline_keywords = _parse_keywords(getattr(args, "keywords", ""))
    if inline_keywords:
        return True
    from_file = getattr(args, "from_file", None)
    if from_file:
        file_keywords, _ = _split_file_inputs(from_file)
        if file_keywords:
            return True
    print(_bi(f"seos-cli {command}: at least one keyword is required.", f"seos-cli {command}: требуется хотя бы одно ключевое слово."), file=sys.stderr)
    return False


def _require_any_urls(args: argparse.Namespace, command: str) -> bool:
    inline_urls = list(getattr(args, "urls", []) or [])
    if inline_urls:
        return True
    from_file = getattr(args, "from_file", None)
    if from_file:
        _, file_urls = _split_file_inputs(from_file)
        if file_urls:
            return True
    print(_bi(f"seos-cli {command}: at least one URL is required.", f"seos-cli {command}: требуется хотя бы один URL."), file=sys.stderr)
    return False


def _run_profile(args: argparse.Namespace, steps: List[str]) -> int:
    cloned = argparse.Namespace(**vars(args))
    cloned.command = "run"
    cloned.steps = ",".join(steps)
    return _cmd_run(cloned)


def _provider_presence() -> Dict[str, bool]:
    provider_env_map: Dict[str, Tuple[str, ...]] = {
        "openai": ("OPENAI_API_KEY",),
        "anthropic": ("ANTHROPIC_API_KEY",),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "openrouter": ("OPENROUTER_API_KEY",),
        "google_ads": (
            "GOOGLE_ADS_DEVELOPER_TOKEN",
            "GOOGLE_ADS_CLIENT_ID",
            "GOOGLE_ADS_CLIENT_SECRET",
            "GOOGLE_ADS_REFRESH_TOKEN",
        ),
    }
    presence: Dict[str, bool] = {
        name: all(os.environ.get(key, "") for key in env_names)
        for name, env_names in provider_env_map.items()
    }
    try:
        from config.settings import SCRAPER_CONFIG, SERP_PROVIDER_OPTIONS, _SERP_ENV_MAP, _check_env_keys

        for display, internal in SERP_PROVIDER_OPTIONS.items():
            if internal == "browser_cloakbrowser":
                presence[f"serp:{internal}"] = bool(
                    SCRAPER_CONFIG.get("browser_enabled", False)
                )
                continue
            env_names = _SERP_ENV_MAP.get(internal, "")
            presence[f"serp:{internal}"] = _check_env_keys(env_names)
    except Exception as exc:  # noqa: BLE001
        logger = None
        try:
            from utils.logger import logger as _logger

            logger = _logger
        except Exception:  # noqa: BLE001
            logger = None
        if logger is not None:
            logger.warning(f"cli: config settings unavailable for provider summary: {exc}")
    return presence


# FUNCTION_CONTRACT: _requires_api_credentials
# Purpose: Decide whether a provider from _provider_presence() needs an API key to function.
# Input: name (str) — a key from the presence dict ("openai", "serp:browser_cloakbrowser", ...).
# Output: bool — True when the provider is API-key-backed; False for credential-free providers.
# Side Effects: lazy-imports config.settings (streamlit-free); reads the static _SERP_ENV_MAP.
# Business Rules: SERP providers whose _SERP_ENV_MAP entry is the empty string (e.g. the headless
#   browser scraper) require no credentials; all LLM providers and key-backed SERP providers do.
#   config check counts only API-key-backed providers, so a fresh install with the browser engine
#   enabled still reports "no configured API keys" and exits non-zero.
# Failure Modes: never raises — falls back to True (treat as credential-backed) if settings unloadable.
# LINKS: knowledge-graph.xml#MOD-032
def _requires_api_credentials(name: str) -> bool:
    if name.startswith("serp:"):
        try:
            from config.settings import _SERP_ENV_MAP  # streamlit-free
        except Exception:  # noqa: BLE001 — _provider_presence() already logged this; be safe
            return True
        internal = name.split(":", 1)[1]
        return bool(_SERP_ENV_MAP.get(internal, ""))
    return True


def _cmd_config(args: argparse.Namespace) -> int:
    sub = getattr(args, "config_command", None)
    presence = _provider_presence()
    if sub == "show":
        for name in sorted(presence):
            state = _bi("present", "присутствует") if presence[name] else _bi("missing", "отсутствует")
            print(f"{name}: {state}")
        return 0
    if sub == "check":
        # `check` validates API-KEY credentials; credential-free providers (browser scraper) are
        # excluded so a no-key setup still exits non-zero, matching the "no configured API keys
        # found" message this branch prints.
        configured = [
            name
            for name, present in presence.items()
            if present and _requires_api_credentials(name)
        ]
        if configured:
            print(_bi(f"configured providers: {', '.join(sorted(configured))}", f"настроенные провайдеры: {', '.join(sorted(configured))}"))
            return 0
        print(_bi("no configured API keys found", "не найдено настроенных API-ключей"), file=sys.stderr)
        return 1
    print(_bi("seos-cli config: choose 'show' or 'check'.", "seos-cli config: выберите 'show' или 'check'."), file=sys.stderr)
    return 2


# Route a parsed namespace to its handler and return an exit code.
def dispatch(args: argparse.Namespace) -> int:
    command: Optional[str] = getattr(args, "command", None)
    if command is None:
        build_parser().print_help()
        return 0

    if command == "version":
        return _cmd_version(args)
    if command == "run":
        return _cmd_run(args)
    if command == "ads":
        if not _require_any_keywords(args, "ads"):
            return 2
        return _run_profile(args, ["ads", "export"])
    if command == "serp":
        if not _require_any_keywords(args, "serp"):
            return 2
        return _run_profile(args, ["serp", "merge", "export"])
    if command == "trends":
        if not _require_any_keywords(args, "trends"):
            return 2
        return _run_profile(args, ["trends", "merge", "export"])
    if command == "seo-text":
        if not _require_any_keywords(args, "seo-text"):
            return 2
        return _run_profile(args, ["seo-text", "export"])
    if command == "scrape":
        if not _require_any_urls(args, "scrape"):
            return 2
        return _run_profile(args, ["validate", "scrape", "llm-extract", "export"])
    if command == "config":
        return _cmd_config(args)
    if command == "register":
        return _cmd_register(args)
    print(_bi(f"seos-cli: unknown command {command!r}", f"seos-cli: неизвестная команда {command!r}"), file=sys.stderr)
    return 2


# Install/uninstall/status the seos-cli command into PATH (Phase D).
def _cmd_register(args: argparse.Namespace) -> int:
    from cli import registration as reg

    shim_dir = _default_shim_dir()
    if getattr(args, "status", False):
        info = reg.status(shim_dir)
        print(_bi(f"shim path:    {info['shim_path']}", f"путь к shim:  {info['shim_path']}"))
        print(_bi(f"shim exists:  {info['shim_exists']}", f"shim существует: {info['shim_exists']}"))
        print(_bi(f"on PATH:      {info['on_path']}", f"в PATH:       {info['on_path']}"))
        print(_bi(f"interpreter:  {info['interpreter']}", f"интерпретатор: {info['interpreter']}"))
        print(_bi(f"PATH length:  {info['path_length']} chars", f"длина PATH:   {info['path_length']} симв."))
        return 0
    if getattr(args, "unregister", False):
        return reg.unregister(shim_dir)
    return reg.register(shim_dir)


# Where the seos-cli shim lives by default (stable, user-writable).
def _default_shim_dir() -> str:
    if sys.platform.startswith("win"):
        # A per-user bin dir; created on register. Avoids needing admin.
        return str(Path.home() / ".seos-cli" / "bin")
    return str(Path.home() / ".local" / "bin")


# Entry point. Returns a process exit code (int).
#
# argparse raises SystemExit for --help/--version and for parse errors (e.g. an
# unknown subcommand). We convert those into plain int codes so callers (tests,
# `python -m cli.main`) always get an integer and never see an uncaught SystemExit.
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        return dispatch(args)
    except SystemExit as exc:  # argparse --help / --version / invalid choice
        code = exc.code
        return code if isinstance(code, int) else (0 if code is None else 1)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
