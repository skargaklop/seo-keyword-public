# MODULE_CONTRACT: cli.__main__
# Purpose: Enable `python -m cli` (and the seos-cli shim's `python -m cli.main`) to run the CLI.
# Rationale: docs/cli-plan.md §7 Phase E. The seos-cli.bat / POSIX shim delegate to `python -m cli.main`;
# this __main__.py makes `python -m cli` an equivalent entry so both invocation forms work.
# Dependencies: cli.main.
# Exports: none (side-effecting entry point).
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-MAIN, docs/cli-plan.md §7 Phase E
# MODULE_MAP: cli/__main__.py
# Public Functions: none.
# Private Helpers: none.
# Key Semantic Blocks: none.
# Critical Flows: `python -m cli` -> cli.main.main(sys.argv[1:]) -> SystemExit(code).
# Verification: verification-plan.xml#V-18-MAIN
# CHANGE_SUMMARY: Phase E — one-line entry point delegating to cli.main.main with the int exit code.

import sys

from cli.main import main

if __name__ == "__main__":  # pragma: no cover — exercised via `python -m cli`
    raise SystemExit(main(sys.argv[1:]))
