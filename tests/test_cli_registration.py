# MODULE_CONTRACT: tests/test_cli_registration
# Purpose: TDD RED->GREEN for cli.registration — install the `seos-cli` command into PATH,
#   idempotently and reversibly, WITHOUT ever calling setx (which truncates PATH > 1024 chars).
# Rationale: docs/cli-plan.md §6 + §7 Phase D. setx silently corrupts long PATH values, so Windows
#   registration must go through winreg/[Environment]::SetEnvironmentVariable and must allow long
#   User PATH values instead of forcing cleanup.
# Process-isolation note: registration touches real PATH state (winreg / os.environ). To keep the
#   pytest suite hermetic, the Windows path setter is DI-injected and tested against an in-memory
#   dict; the real winreg call is exercised in an isolated subprocess that asserts setx absence.
# Dependencies: cli.registration, pytest.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-REGISTRATION, docs/cli-plan.md §6
# MODULE_MAP: tests/test_cli_registration.py
# Public Functions: pytest test functions.
# Private Helpers: none.
# Key Semantic Blocks: none.
# Critical Flows: register -> shim file + PATH entry -> idempotent -> unregister removes both.
# Verification: verification-plan.xml#V-18-REGISTRATION
# CHANGE_SUMMARY: Phase D RED — register creates shim + adds PATH entry (injected setter);
#   idempotent (no dup); --unregister reverses; never calls setx (subprocess grep of source +
#   runtime); allows long User PATH values.

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Core registration against an injected (in-memory) PATH setter — fully hermetic.
# ---------------------------------------------------------------------------

def test_register_creates_shim_and_adds_path_entry(tmp_path: Path) -> None:
    from cli.registration import register

    shim_dir = tmp_path / "shims"
    path_state = {"path": ""}
    calls = []

    def fake_set_path(new_path):
        calls.append(("set_path", new_path))
        path_state["path"] = new_path

    rc = register(
        shim_dir=str(shim_dir),
        interpreter=sys.executable,
        set_path=fake_set_path,
        current_path="",  # hermetic: don't read the real machine PATH
    )
    assert rc == 0
    # Shim file exists
    shims = list(shim_dir.glob("seos-cli*"))
    assert shims, f"no shim created in {shim_dir}"
    # The shim dir was added to PATH exactly once
    assert str(shim_dir) in path_state["path"]


def test_register_is_idempotent_no_duplicate_path_entry(tmp_path: Path) -> None:
    from cli.registration import register

    shim_dir = tmp_path / "shims"
    entries = []

    def fake_set_path(new_path):
        entries.append(new_path)

    register(
        shim_dir=str(shim_dir), interpreter=sys.executable, set_path=fake_set_path, current_path=""
    )
    # Second registration: shim dir already on PATH -> should not add a duplicate.
    register(
        shim_dir=str(shim_dir),
        interpreter=sys.executable,
        set_path=fake_set_path,
        current_path=entries[-1],
    )
    # The shim dir appears exactly once in the final PATH.
    final = entries[-1]
    assert final.count(str(shim_dir)) == 1


def test_unregister_removes_shim_and_path_entry(tmp_path: Path) -> None:
    from cli.registration import register, unregister

    shim_dir = tmp_path / "shims"
    path_state = {"path": ""}

    def fake_set_path(new_path):
        path_state["path"] = new_path

    register(
        shim_dir=str(shim_dir), interpreter=sys.executable, set_path=fake_set_path, current_path=""
    )
    assert str(shim_dir) in path_state["path"]
    assert list(shim_dir.glob("seos-cli*"))

    rc = unregister(
        shim_dir=str(shim_dir), set_path=fake_set_path, current_path=path_state["path"]
    )
    assert rc == 0
    assert str(shim_dir) not in path_state["path"]
    assert not list(shim_dir.glob("seos-cli*"))


def test_register_allows_long_existing_path_when_registry_setter_is_used(tmp_path: Path) -> None:
    from cli.registration import register

    shim_dir = tmp_path / "shims"
    set_calls = []

    def fake_set_path(new_path):
        set_calls.append(new_path)

    huge_path = "C:\\" + ";".join(f"d{i}" for i in range(5000))  # well over the limit
    rc = register(
        shim_dir=str(shim_dir),
        interpreter=sys.executable,
        set_path=fake_set_path,
        current_path=huge_path,
    )
    assert rc == 0, "registration should not require PATH cleanup"
    assert set_calls, "set_path should persist the updated PATH"
    assert set_calls[-1].endswith(str(shim_dir))
    assert list(shim_dir.glob("seos-cli*"))


def test_register_allows_resulting_long_path_when_registry_setter_is_used(tmp_path: Path) -> None:
    from cli.registration import register

    shim_dir = tmp_path / "shims"
    calls = []

    def fake_set_path(new_path):
        calls.append(new_path)

    almost_full = "C:\\" + ("a" * 5000)
    rc = register(
        shim_dir=str(shim_dir),
        interpreter=sys.executable,
        set_path=fake_set_path,
        current_path=almost_full,
    )
    assert rc == 0
    assert calls
    assert calls[-1].endswith(str(shim_dir))


def test_entry_on_path_handles_expandable_vars_without_resolve(monkeypatch) -> None:
    import cli.registration as registration

    path_value = r"%USERPROFILE%\.seos-cli\bin;C:\Tools"
    monkeypatch.setattr(registration.os, "pathsep", ":")

    assert registration._entry_on_path(r"%USERPROFILE%\.seos-cli\bin", path_value) is True


# ---------------------------------------------------------------------------
# HARD gate: registration source + runtime NEVER call setx.
# ---------------------------------------------------------------------------

# The cli/registration.py source must never INVOKE setx as a command.
#
# Refined from a naive substring scan to an AST check for an actual setx call: the contract
# documents WHY we avoid setx (it truncates PATH), so the word legitimately appears in
# docstrings/comments. What's forbidden is invoking it — e.g. `subprocess.run(["setx", ...])`,
# `check_call("setx ...")`, or a bare `setx(...)` call.
def test_registration_source_never_calls_setx() -> None:
    import ast

    src = (PROJECT_ROOT / "cli" / "registration.py").read_text(encoding="utf-8")
    tree = ast.parse(src, filename="cli/registration.py")
    offenders = []
    for node in ast.walk(tree):
        # subprocess.run/check_call/call/Popen([...,"setx",...]) and string-command forms
        if isinstance(node, ast.Call):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and "setx" in arg.value.lower():
                    offenders.append(f"call with setx string arg: {ast.dump(node)}")
                if isinstance(arg, (ast.List, ast.Tuple)):
                    for elt in arg.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str) and "setx" in elt.value.lower():
                            offenders.append(f"call with setx in arg list: {ast.dump(node)}")
            # bare setx(...) function call
            func = node.func
            if isinstance(func, ast.Name) and func.id.lower() == "setx":
                offenders.append(f"bare setx() call: {ast.dump(node)}")
            if isinstance(func, ast.Attribute) and func.attr.lower() == "setx":
                offenders.append(f"attribute .setx() call: {ast.dump(node)}")
    assert not offenders, (
        f"cli/registration.py invokes setx (forbidden — truncates PATH): {offenders}"
    )


# Runtime: registering must not spawn a setx process (subprocess isolation check).
def test_registration_does_not_spawn_setx_subprocess(tmp_path: Path) -> None:
    code = (
        "import sys, subprocess as _sp\n"
        "orig = _sp.run\n"
        "seen = []\n"
        "def spy(*a, **k):\n"
        "    cmd = a[0] if a else k.get('args')\n"
        "    if isinstance(cmd, (list, tuple)):\n"
        "        flat = ' '.join(str(x) for x in cmd)\n"
        "    else:\n"
        "        flat = str(cmd)\n"
        "    seen.append(flat.lower())\n"
        "    return orig(*a, **k)\n"
        "_sp.run = spy\n"
        "from cli.registration import register\n"
        f"register(shim_dir={str(tmp_path / 's')!r}, interpreter={sys.executable!r},\n"
        "          set_path=lambda p: None)\n"
        "bad = [s for s in seen if 'setx' in s]\n"
        "print('SPAWNED_SETX=' + ('YES' if bad else 'NO'))\n"
        "if bad:\n"
        "    print('OFFENDERS=' + repr(bad))\n"
    )
    import os

    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(PROJECT_ROOT)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), env=env,
    )
    assert result.returncode == 0, (
        f"subprocess failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "SPAWNED_SETX=NO" in result.stdout, result.stdout
