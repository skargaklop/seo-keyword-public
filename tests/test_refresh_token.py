from types import SimpleNamespace

import builtins
import pytest

import generate_refresh_token


class _FakeFlow:
    @staticmethod
    def from_client_config(config, scopes):
        return _FakeFlow()

    @staticmethod
    def run_local_server(port: int, prompt: str, access_type: str):
        return SimpleNamespace(refresh_token="refresh-token-secret-123456")


class TestRefreshTokenScript:
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
