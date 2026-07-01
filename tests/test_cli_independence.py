# MODULE_CONTRACT: tests/test_cli_independence
# Purpose: ENFORCE the HARD Streamlit-independence guarantee (docs/cli-plan.md §2.2, §8).
# Rationale: the CLI must never import streamlit, utils.pipeline, or config.i18n — neither as
#   text in any cli/*.py, nor in the live import graph (sys.modules), nor via an AST import of the
#   two banned modules. If any of these fires, the CLI is no longer headless-runnable.
# Dependencies: stdlib ast/pathlib/sys/importlib only (deliberately NOT streamlit).
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-INDEPENDENCE, docs/cli-plan.md §2.2
# MODULE_MAP: tests/test_cli_independence.py
# Public Functions: pytest test functions.
# Private Helpers: _cli_py_files, _banned_module_aliases.
# Key Semantic Blocks: none.
# Critical Flows: scan cli/*.py text + AST imports, then import cli.main/cli.pipeline and assert
#   streamlit absent from sys.modules.
# Verification: verification-plan.xml#V-18-INDEPENDENCE
# CHANGE_SUMMARY: Phase B RED — three-way independence gate: text grep, AST banned-import scan,
#   live sys.modules check.

import ast
import importlib
import sys
from pathlib import Path
from typing import Set

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_DIR = PROJECT_ROOT / "cli"

# Modules the CLI is FORBIDDEN from importing (docs/cli-plan.md §2.1).
BANNED_MODULES = {"streamlit", "utils.pipeline", "config.i18n"}


def _cli_py_files() -> list[Path]:
    return sorted(p for p in CLI_DIR.glob("*.py") if p.name != "__pycache__")


# Extract the top-level module name(s) an Import/ImportFrom node pulls in.
#
# For `from utils.pipeline import x` we record 'utils.pipeline'; for `import streamlit as st`
# we record 'streamlit'.
def _imported_names(node: ast.AST) -> Set[str]:
    names: Set[str] = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            names.add(alias.name.split(".")[0])
            names.add(alias.name)  # also the dotted form for utils.pipeline
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module:
            names.add(module.split(".")[0])
            names.add(module)
    return names


# Find FUNCTIONAL references to streamlit: a bare Name 'streamlit'/'st' or an Attribute
# accessed off a Name 'st'/'streamlit' (e.g. st.write(...), streamlit.progress()). This catches
# real usage while allowing the word 'streamlit' to appear in docstrings/comments (where the
# GRACE contract documents WHY we avoid it).
def _functional_streamlit_refs(tree: ast.AST) -> list[str]:
    refs: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in {"streamlit", "st"}:
            refs.append(f"Name {node.id!r}")
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in {"st", "streamlit"}:
            refs.append(f"{node.value.id}.{node.attr}")
    return refs


# (§2.2 item 4a) No cli/*.py may call or reference streamlit as code (st.*, streamlit.*).
#
# Refined from a naive text grep to a functional-reference scan: the AST-import test already
# forbids `import streamlit`; this forbids any attribute/call/bare-name usage too, while letting
# the word appear in docstrings (where the contract documents the independence guarantee).
def test_no_cli_py_file_uses_streamlit_functionally() -> None:
    files = _cli_py_files()
    assert files, "no cli/*.py found — cli package missing"
    offenders: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        refs = _functional_streamlit_refs(tree)
        for r in refs:
            offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {r}")
    assert not offenders, f"cli files use streamlit functionally: {offenders}"


# (§2.2 item 4c) AST scan: no cli/*.py may import streamlit / utils.pipeline / config.i18n.
def test_no_cli_py_file_ast_imports_banned_modules() -> None:
    offenders: list[str] = []
    for path in _cli_py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            offenders.append(f"{path.relative_to(PROJECT_ROOT)}: SYNTAX ERROR {exc}")
            continue
        for node in ast.walk(tree):
            for name in _imported_names(node):
                if name in BANNED_MODULES:
                    offenders.append(
                        f"{path.relative_to(PROJECT_ROOT)} imports banned '{name}'"
                    )
    assert not offenders, f"banned imports found in cli/: {offenders}"


@pytest.mark.parametrize("module", ["cli.main", "cli.pipeline", "cli.merge"])
# (§2.2 item 4b) importing any cli.* module must NOT put streamlit in sys.modules.
#
# Run in an ISOLATED SUBPROCESS so the check starts from a truly clean interpreter where streamlit
# has never been loaded. (Doing sys.modules.pop("streamlit") in-process is destructive: it leaves
# streamlit's DeltaGeneratorSingleton half-initialized, which then breaks other tests' streamlit
# setup with 'instance already exists'. A subprocess is also a STRONGER guarantee.)
def test_importing_cli_modules_leaves_streamlit_out_of_sys_modules(module: str) -> None:
    import subprocess

    code = (
        "import sys, importlib\n"
        f"importlib.import_module({module!r})\n"
        "assert 'streamlit' not in sys.modules, 'pulled in streamlit'\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env={**__import__("os").environ, "PYTHONUTF8": "1", "PYTHONPATH": str(PROJECT_ROOT)},
    )
    assert result.returncode == 0, (
        f"subprocess import check failed for {module}:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "OK" in result.stdout
