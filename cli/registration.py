# MODULE_CONTRACT: cli.registration
# Purpose: Install the `seos-cli` command into PATH so it's callable from anywhere — idempotently
#   and reversibly, WITHOUT ever calling setx (which silently truncates User PATH > 1024 chars).
# Rationale: docs/cli-plan.md §6 + §7 Phase D. setx corrupts an already-long PATH, so Windows
#   registration goes through winreg (Python stdlib) which has no 1024-char limit and no admin
#   requirement. Registration writes long PATH values through that safe setter instead of
#   forcing the user to clean PATH first.
# Design:
#   - register(shim_dir, interpreter, set_path=None, current_path=None) writes a shim file
#     (seos-cli.bat on Windows, seos-cli with shebang on POSIX) into shim_dir and appends shim_dir
#     to PATH via `set_path`. Idempotent: skips if already present.
#   - `set_path` is a DI hook (defaults to _windows_set_user_path / _posix_set_path) so tests inject
#     an in-memory setter and never touch real PATH state.
#   - unregister() reverses both: removes the shim file and the PATH entry.
#   - NEVER calls setx. Setter failures return non-zero without corrupting PATH.
# Dependencies: stdlib only (os/pathlib/sys/subprocess/winreg). NEVER streamlit/utils.pipeline/config.i18n.
# Exports: register, unregister, status.
# LINKS: knowledge-graph.xml#MOD-032, verification-plan.xml#V-18-REGISTRATION, docs/cli-plan.md §6
# MODULE_MAP: cli/registration.py
# Public Functions: register, unregister, status.
# Private Helpers: _windows_set_user_path, _posix_set_user_path, _current_user_path, _path_entries,
#   _join_path, _write_windows_shim, _write_posix_shim, _shim_name.
# Key Semantic Blocks: none.
# Critical Flows: register -> shim file + PATH entry (idempotent) -> unregister reverses both.
# Verification: verification-plan.xml#V-18-REGISTRATION
# CHANGE_SUMMARY: Phase D GREEN — platform-aware register/unregister with DI `set_path` hook;
#   winreg-based Windows PATH setter (no setx, no 1024 truncation); long PATH values are allowed;
#   idempotent; fully reversible.

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional

from utils.logger import logger

# Windows User PATH is stored in the registry under HKCU\Environment\Path. There is no hard
# 1024-character limit there (unlike setx), and this module never invokes setx, so long existing
# PATH values are allowed.

IsWindows = sys.platform.startswith("win")


# ---------------------------------------------------------------------------
# PATH entry helpers
# ---------------------------------------------------------------------------

# Split a PATH string into entries (os.pathsep-aware).
def _path_entries(path_value: str) -> List[str]:
    if not path_value:
        return []
    return [p for p in path_value.split(os.pathsep) if p]


def _join_path(entries: List[str]) -> str:
    return os.pathsep.join(entries)


def _shim_name() -> str:
    return "seos-cli.bat" if IsWindows else "seos-cli"


def _entry_on_path(shim_dir: str, path_value: str) -> bool:
    target = os.path.normcase(os.path.normpath(shim_dir.strip().strip('"')))
    for entry in _path_entries(path_value):
        candidate = os.path.normcase(os.path.normpath(entry.strip().strip('"')))
        if candidate == target:
            return True
    return False


# Best-effort read of the current User PATH (Windows registry / POSIX env).
def _current_user_path() -> str:
    if IsWindows:
        return _read_windows_user_path()
    return os.environ.get("PATH", "")


# ---------------------------------------------------------------------------
# Shim file writers
# ---------------------------------------------------------------------------

# Write a seos-cli.bat that delegates to `python -m cli.main %*`.
def _write_windows_shim(shim_path: Path, interpreter: str) -> None:
    project_root = str(Path(__file__).resolve().parent.parent)
    # bat-launcher-generator style: PYTHONUTF8 + chcp 65001 for reliable Cyrillic.
    content = (
        "@echo off\n"
        "chcp 65001 > nul\n"
        'set "PYTHONUTF8=1"\n'
        f'set "PYTHONPATH={project_root}"\n'
        f'"{interpreter}" -m cli.main %*\n'
    )
    shim_path.write_text(content, encoding="utf-8")


# Write a seos-cli shell shim with a shebang.
def _write_posix_shim(shim_path: Path, interpreter: str) -> None:
    project_root = str(Path(__file__).resolve().parent.parent)
    content = (
        "#!/usr/bin/env bash\n"
        f'export PYTHONPATH="{project_root}:$PYTHONPATH"\n'
        f'export PYTHONUTF8=1\n'
        f'exec "{interpreter}" -m cli.main "$@"\n'
    )
    shim_path.write_text(content, encoding="utf-8")
    # chmod +x
    try:
        shim_path.chmod(0o755)
    except OSError as exc:  # noqa: BLE001
        logger.warning(f"cli: could not chmod shim {shim_path}: {exc}")


# ---------------------------------------------------------------------------
# PATH setters (Windows uses winreg — NEVER setx)
# ---------------------------------------------------------------------------

# Read the User PATH value from HKCU\\Environment via winreg (stdlib).
def _read_windows_user_path() -> str:
    try:
        import winreg  # type: ignore[import-not-found]

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ
        ) as key:
            value, _ = winreg.QueryValueEx(key, "Path")
            return str(value)
    except Exception as exc:  # noqa: BLE001 — fall back to env if registry read fails
        logger.warning(f"cli: could not read User PATH from registry, using env: {exc}")
        return os.environ.get("PATH", "")


# Set the User PATH via winreg (NOT setx — no 1024-char truncation, no admin required).
def _windows_set_user_path(new_path: str) -> None:
    import winreg  # type: ignore[import-not-found]

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
    ) as key:
        # REG_EXPAND_SZ so %VAR% in the value expands at runtime.
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
    # Broadcast so other processes pick up the change without a reboot.
    _broadcast_path_change()
    # Also reflect in this process's env.
    os.environ["PATH"] = new_path + os.pathsep + os.environ.get("PATH", "")


# Broadcast WM_SETTINGCHANGE so Explorer/terminals notice the PATH update.
def _broadcast_path_change() -> None:
    try:
        import ctypes

        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        ctypes.windll.user32.SendMessageTimeoutW(  # type: ignore[attr-defined]
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", 0x0002, 1000, None
        )
    except Exception as exc:  # noqa: BLE001 — broadcast is best-effort
        logger.warning(f"cli: could not broadcast PATH change: {exc}")


# Return the platform-appropriate PATH setter (DI default).
def _default_set_path() -> Callable[[str], None]:
    if IsWindows:
        return _windows_set_user_path
    return _posix_set_user_path


# POSIX: append to PATH in the user's shell rc (best-effort) + reflect in this process.
def _posix_set_user_path(new_path: str) -> None:
    # Updating shell rc files is invasive and shell-specific; for the CLI we reflect in the current
    # process env and log guidance. The caller can persist shell rc themselves if desired.
    os.environ["PATH"] = new_path + os.pathsep + os.environ.get("PATH", "")
    logger.info("cli: PATH updated for this process; add to shell rc to persist.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _resolve_set_path(set_path: Optional[Callable[[str], None]]) -> Callable[[str], None]:
    return set_path if set_path is not None else _default_set_path()


def register(
    shim_dir: str,
    interpreter: Optional[str] = None,
    set_path: Optional[Callable[[str], None]] = None,
    current_path: Optional[str] = None,
) -> int:
    """Install the seos-cli shim into shim_dir and add shim_dir to PATH. Idempotent.

    Returns 0 on success and non-zero if PATH persistence fails. Never calls setx.
    """
    interpreter = interpreter or sys.executable
    shim_dir_path = Path(shim_dir)
    shim_dir_path.mkdir(parents=True, exist_ok=True)
    shim_path = shim_dir_path / _shim_name()

    # Write (refresh) the shim.
    if IsWindows:
        _write_windows_shim(shim_path, interpreter)
    else:
        _write_posix_shim(shim_path, interpreter)

    path_value = current_path if current_path is not None else _current_user_path()

    if _entry_on_path(str(shim_dir_path), path_value):
        logger.info(f"cli: shim dir already on PATH; shim refreshed at {shim_path}")
        return 0

    entries = _path_entries(path_value) + [str(shim_dir_path)]
    new_path = _join_path(entries)
    setter = _resolve_set_path(set_path)
    try:
        setter(new_path)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"cli: failed to set PATH: {exc}")
        return 1
    logger.info(f"cli: added {shim_dir_path} to PATH")
    return 0


def unregister(
    shim_dir: str,
    set_path: Optional[Callable[[str], None]] = None,
    current_path: Optional[str] = None,
) -> int:
    """Remove the seos-cli shim and its PATH entry. Returns 0 on success."""
    shim_dir_path = Path(shim_dir)
    shim_path = shim_dir_path / _shim_name()

    path_value = current_path if current_path is not None else _current_user_path()
    normalized_dir = os.path.normcase(os.path.normpath(str(shim_dir_path)))

    # Remove the PATH entry.
    if _entry_on_path(str(shim_dir_path), path_value):
        entries = [
            p for p in _path_entries(path_value)
            if os.path.normcase(os.path.normpath(p.strip().strip('"'))) != normalized_dir
        ]
        setter = _resolve_set_path(set_path)
        try:
            setter(_join_path(entries))
            logger.info(f"cli: removed {shim_dir_path} from PATH")
        except Exception as exc:  # noqa: BLE001
            logger.error(f"cli: failed to update PATH on unregister: {exc}")
            return 1

    # Remove the shim file.
    if shim_path.exists():
        try:
            shim_path.unlink()
            logger.info(f"cli: removed shim {shim_path}")
        except OSError as exc:  # noqa: BLE001
            logger.warning(f"cli: could not remove shim {shim_path}: {exc}")
            return 1

    return 0


def status(
    shim_dir: str,
    current_path: Optional[str] = None,
) -> dict:
    """Report shim location + PATH state without changing anything."""
    shim_path = Path(shim_dir) / _shim_name()
    path_value = current_path if current_path is not None else _current_user_path()
    return {
        "shim_path": str(shim_path),
        "shim_exists": shim_path.exists(),
        "on_path": _entry_on_path(str(shim_dir), path_value),
        "interpreter": sys.executable,
        "path_length": len(path_value),
    }
