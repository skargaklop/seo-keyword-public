import config.settings as settings


def test_settings_exports_history_and_uploads_configs() -> None:
    assert settings.HISTORY_CONFIG == settings.config.get("history", {})
    assert settings.UPLOADS_CONFIG == settings.config.get("uploads", {})
