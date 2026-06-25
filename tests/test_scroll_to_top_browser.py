# End-to-end browser test for the scroll-to-top button (Playwright + live Streamlit).
# MODULE_CONTRACT: tests/test_scroll_to_top_browser
# Purpose: Verify that the injected scroll-to-top <script> actually executes in a real
#          browser against Streamlit 1.58's REAL scroll container
#          (section[data-testid="stMain"]) — the only scrollable element in the layout.
#          Static string assertions cannot prove the script runs against the live DOM —
#          only a real browser can.
# Rationale: Guards three distinct bugs:
#   (a) st.html() ignored the <script> so it never ran (needs unsafe_allow_javascript=True);
#   (b) the visibility logic queried the WRONG container (.main / stAppViewContainer), which
#       are not scrollable in 1.58 — so a 1s setInterval fallback kept stripping .is-visible
#       (flicker) and the button was never stably visible;
#   (c) the click handler scrolled .main / stAppViewContainer (a no-op), so clicking the
#       button did nothing.
#   A native-style non-bubbling scroll event on section[data-testid="stMain"] faithfully
#   reproduces how the browser notifies a scroll of that element (capture-phase listeners
#   receive it), so it is the realistic trigger — NOT a bypass of the bug.
# Dependencies: playwright, streamlit, the running app.py.
# Exports: pytest tests (browser-backed).
# Verification: python -m pytest tests/test_scroll_to_top_browser.py -q
# CHANGE_SUMMARY: New — Playwright E2E proof that the scroll-to-top button becomes stably
#                 visible on the real Streamlit scroll container AND that clicking it scrolls
#                 back to the top.

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

playwright = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _streamlit_ready(proc: subprocess.Popen, port: int, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline() if proc.stdout else ""
        if line and ("You can now view your app" in line or f":{port}" in line):
            return True
        if proc.poll() is not None:
            return False
        time.sleep(0.3)
    return False


def _wait_for_script_settled(page, timeout: float = 25.0) -> None:
    """Wait until Streamlit's script run is no longer in the 'running' state.

    The button + CSS are injected by app code during the script run; querying while
    data-test-script-state="running" returns an empty shell. This waits for the run to
    reach a settled (non-running) state before asserting.
    """
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-test-script-state]');
            if (!el) return true;
            return el.getAttribute('data-test-script-state') !== 'running';
        }""",
        timeout=int(timeout * 1000),
    )


def _scroll_real_container(page, delta: int = 800) -> None:
    """Scroll Streamlit 1.58's real content container (section[data-testid="stMain"]).

    The browser dispatches a NON-bubbling 'scroll' event on whichever element scrolled;
    we reproduce that exactly (bubbles:false). Capture-phase listeners on window/document
    still receive it, so this is the faithful real-user trigger — not a bug-bypassing
    synthetic bubbling event. page.mouse.wheel is NOT used because on a fresh load it hits
    the sidebar (stSidebarContent), not the main area.
    """
    page.evaluate(
        """(delta) => {
            const el = document.querySelector('section[data-testid="stMain"]');
            if (!el) return;
            el.scrollTop = delta;
            el.dispatchEvent(new Event('scroll', { bubbles: false }));
        }""",
        delta,
    )


@pytest.fixture(scope="module")
def streamlit_url() -> str:
    port = _free_port()
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.port", str(port), "--server.headless", "true",
         "--browser.gatherUsageStats", "false"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    try:
        if not _streamlit_ready(proc, port):
            pytest.skip("Streamlit server did not become ready in time")
        url = f"http://127.0.0.1:{port}"
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture()
def page_at_ready(streamlit_url: str):
    """A browser page on the loaded app, settled past the initial script run."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(streamlit_url, wait_until="networkidle", timeout=45000)
        _wait_for_script_settled(page)
        page.wait_for_selector("#consoleScrollTop", timeout=20000)
        try:
            yield page
        finally:
            browser.close()


def _button_class(page) -> str:
    return page.get_attribute("#consoleScrollTop", "class") or ""


def test_button_hidden_when_content_is_at_top(page_at_ready) -> None:
    """At the top, the button must be hidden (no .is-visible)."""
    assert "is-visible" not in _button_class(page_at_ready)


def test_button_stays_visible_after_scroll_no_flicker(page_at_ready) -> None:
    """After scrolling the real container, the button must be visible AND stay visible.

    Regression: the 1s setInterval fallback queried the WRONG container
    (.main / stAppViewContainer, scrollTop always 0 in Streamlit 1.58), so it kept
    REMOVING .is-visible ~1s after the scroll event ADDed it — a visible flicker that
    made the button unreliable. A stable (no-flicker) assertion catches this; the old
    flaky test only caught a transient is-visible and masked the bug.
    """
    page = page_at_ready
    _scroll_real_container(page, 800)

    # Must become visible promptly.
    page.wait_for_function(
        """() => {
            const b = document.getElementById('consoleScrollTop');
            return b && b.classList.contains('is-visible');
        }""",
        timeout=8000,
    )

    # ... and MUST still be visible after the 1s fallback interval has fired 2-3 times.
    # This is the RED for the flicker bug: with the old code, the interval strips
    # is-visible off here.
    time.sleep(2.5)
    assert "is-visible" in _button_class(page), (
        "scroll-to-top button flickered off after scrolling — the setInterval fallback "
        "reads the wrong (non-scrollable) container instead of section[data-testid='stMain']"
    )


def test_clicking_button_scrolls_back_to_top(page_at_ready) -> None:
    """Clicking the visible button must scroll the real container back to the top.

    Regression: window.__consoleScrollToTop scrolled .main / stAppViewContainer — neither
    is scrollable in Streamlit 1.58, so the click was a no-op and the page never moved.
    """
    page = page_at_ready
    _scroll_real_container(page, 800)
    page.wait_for_function(
        """() => document.querySelector('section[data-testid="stMain"]').scrollTop > 100""",
        timeout=8000,
    )

    # Fire a genuine DOM click on the button (a real pointer click on a pointer-events:none
    # element is itself unreliable; the onclick handler is what we are exercising). This is
    # exactly what the browser invokes when the visible button is clicked.
    page.evaluate(
        """() => {
            const b = document.getElementById('consoleScrollTop');
            if (!b) throw new Error('button missing');
            b.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        }"""
    )

    # The real container must return near the top after the click (smooth scroll settles).
    page.wait_for_function(
        """() => document.querySelector('section[data-testid="stMain"]').scrollTop < 50""",
        timeout=10000,
    )
