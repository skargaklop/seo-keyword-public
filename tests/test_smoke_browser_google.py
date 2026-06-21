# Unit tests for the smoke CLI's result-payload extraction. Guards the
#          attribute mismatch that made the smoke probe report timeline_count=0
#          (empty_success_forbidden) even on a genuinely successful Trends parse.
# Reference: scripts/smoke_browser_google.py, utils/browser_scraper.BrowserScrapeResult

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "smoke_browser_google", ROOT / "scripts" / "smoke_browser_google.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_result_payload = _mod._result_payload

from utils.browser_scraper import BrowserScrapeResult  # noqa: E402


class TestSmokeTrendsResultPayload:

    # GRACE: function test_successful_trends_timeline_count_is_nonzero declaration.
    def test_successful_trends_timeline_count_is_nonzero(self) -> None:
        result = BrowserScrapeResult(
            source="cloakbrowser",
            success=True,
            extracted_data={
                "timeline": [
                    {"time": "2025-06-08", "formatted_time": "2025-06-08", "value": 65},
                    {"time": "2025-06-15", "formatted_time": "2025-06-15", "value": 64},
                    {"time": "2025-06-22", "formatted_time": "2025-06-22", "value": 67},
                ],
            },
        )
        payload = _result_payload("trends", result)
        assert payload["success"] is True, (
            f"Expected success=True for a valid 3-point timeline, got payload={payload}"
        )
        assert payload["timeline_count"] == 3, (
            f"Expected timeline_count=3, got {payload['timeline_count']}. "
            "The probe is reading the wrong attribute (parsed_content vs extracted_data)."
        )
        assert payload.get("blocked_reason") != "empty_success_forbidden"
    # GRACE: class TestSmokeTrendsResultPayload declaration
