"""Tests for the refresh-token helper used by the Google Ads bootstrap flow."""

from types import SimpleNamespace

import builtins
import pytest

import generate_refresh_token


# MODULE_CONTRACT: tests/test_refresh_token
# Purpose: Verify the refresh-token helper preserves secret masking and .env updates.
# Rationale: Links the refresh-token tests to the GRACE module under test.
# Dependencies: builtins, pytest, generate_refresh_token.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-028
# MODULE_MAP: tests/test_refresh_token.py
# Public Functions: pytest test functions.
# Private Helpers: _FakeFlow.
# Key Semantic Blocks: none.
# Critical Flows: inject fake OAuth flow -> run helper main -> assert token masking and env write behavior.
# Verification: verification-plan.xml#V-12-REFRESH-TOKEN-TESTS
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-028.


# Purpose:  FakeFlow implementation
class _FakeFlow:
    # Purpose: from client config implementation
    @staticmethod
    def from_client_config(config, scopes):
        return _FakeFlow()

    # Purpose: run local server implementation
    @staticmethod
    def run_local_server(port: int, prompt: str, access_type: str):
        return SimpleNamespace(refresh_token="refresh-token-secret-123456")


# Purpose: TestRefreshTokenScript implementation
class TestRefreshTokenScript:
    # Purpose: Test masks token when writing to env
    def test_masks_token_when_writing_to_env(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        captured = {}
        monkeypatch.setenv("GOOGLE_ADS_CLIENT_ID", "client-id")
        monkeypatch.setenv("GOOGLE_ADS_CLIENT_SECRET", "client-secret")
        monkeypatch.setattr(generate_refresh_token, "InstalledAppFlow", _FakeFlow)
        monkeypatch.setattr(builtins, "input", lambda prompt="": "y")
        monkeypatch.setattr(
            generate_refresh_token,
            "_update_env_file",
            lambda env_path, refresh_token: captured.update(
                {"env_path": env_path, "refresh_token": refresh_token}
            ),
        )

        generate_refresh_token.main()

        output = capsys.readouterr().out
        assert "refresh-token-secret-123456" not in output
        assert captured["refresh_token"] == "refresh-token-secret-123456"

    # Purpose: Test prints token only when user declines env write
    def test_prints_token_only_when_user_declines_env_write(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("GOOGLE_ADS_CLIENT_ID", "client-id")
        monkeypatch.setenv("GOOGLE_ADS_CLIENT_SECRET", "client-secret")
        monkeypatch.setattr(generate_refresh_token, "InstalledAppFlow", _FakeFlow)
        monkeypatch.setattr(builtins, "input", lambda prompt="": "n")

        generate_refresh_token.main()

        output = capsys.readouterr().out
        assert "refresh-token-secret-123456" in output
        assert "GOOGLE_ADS_REFRESH_TOKEN=refresh-token-secret-123456" in output
