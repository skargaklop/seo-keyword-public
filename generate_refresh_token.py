# MODULE_CONTRACT: generate_refresh_token
# Purpose: OAuth2 refresh-token helper for Google Ads credentials and local environment updates
# Rationale: Keep the token bootstrap flow explicit for GRACE adoption and review
# Dependencies: os, sys, google_auth_oauthlib.flow, dotenv
# Exports: main, _mask_secret, _update_env_file
# LINKS: requirements.xml#UC-003, knowledge-graph.xml#MOD-028, verification-plan.xml#V-12-REFRESH-TOKEN-SYNTAX, verification-plan.xml#V-12-REFRESH-TOKEN-TESTS
# MODULE_MAP: generate_refresh_token.py
# Public Functions: main
# Private Helpers: _mask_secret, _update_env_file
# Key Semantic Blocks: block_refresh_token_bootstrap, block_env_refresh_token_persist
# Critical Flows: load credentials -> run consent flow -> persist refresh token -> update .env
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q
# CHANGE_SUMMARY: Restored top-of-file module contract metadata for refresh-token generation

import os
import sys


# EN-first bilingual user-message helper: returns "<English> / <Russian>" (space-slash-space).
def _bi(en: str, ru: str) -> str:
    return f"{en} / {ru}"


try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print(_bi("[ERROR] google-auth-oauthlib is not installed.", "[ОШИБКА] google-auth-oauthlib не установлен."))
    print(_bi("        Install with: pip install google-auth-oauthlib", "        Установите: pip install google-auth-oauthlib"))
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print(_bi("[ERROR] python-dotenv is not installed.", "[ОШИБКА] python-dotenv не установлен."))
    print(_bi("        Install with: pip install python-dotenv", "        Установите: pip install python-dotenv"))
    sys.exit(1)
# FUNCTION_CONTRACT: _mask_secret
# Purpose: Implement the  mask secret helper for this module.
# Input: secret (str), visible_tail (int = 6)
# Output: str
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _mask_secret(secret: str, visible_tail: int = 6) -> str:
    if not secret:
        return ""
    if len(secret) <= visible_tail:
        return "*" * len(secret)
    return f"{'*' * (len(secret) - visible_tail)}{secret[-visible_tail:]}"
# FUNCTION_CONTRACT: main
# Purpose: Implement the main helper for this module.
# Input: (none)
# Output: None
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def main() -> None:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(env_path)

    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("=" * 60)
        print(_bi("[ERROR] GOOGLE_ADS_CLIENT_ID is not set in .env", "[ОШИБКА] В .env не заполнены GOOGLE_ADS_CLIENT_ID"))
        print(_bi("        and/or GOOGLE_ADS_CLIENT_SECRET.", "        и/или GOOGLE_ADS_CLIENT_SECRET."))
        print()
        print(_bi("  1. Open Google Cloud Console:", "  1. Откройте Google Cloud Console:"))
        print("     https://console.cloud.google.com/apis/credentials")
        print(_bi("  2. Create or open an OAuth 2.0 Client ID", "  2. Создайте или откройте OAuth 2.0 Client ID"))
        print(_bi("  3. Copy your Client ID and Client Secret into .env", "  3. Скопируйте Client ID и Client Secret в .env"))
        print("=" * 60)
        sys.exit(1)

    SCOPES = ["https://www.googleapis.com/auth/adwords"]

    print("=" * 60)
    print(_bi("  Google Ads — Refresh Token Generation", "  Google Ads — Генерация Refresh Token"))
    print("=" * 60)
    print()
    print(_bi(f"  Client ID:     {client_id[:20]}...", f"  ID клиента:    {client_id[:20]}..."))
    print(_bi(f"  Client Secret: {client_secret[:8]}...", f"  Секрет клиента: {client_secret[:8]}..."))
    print()
    print(_bi("  A browser will open for authorization.", "  Сейчас откроется браузер для авторизации."))
    print(_bi("  Sign in to the Google account that has access", "  Войдите в Google аккаунт, который имеет доступ"))
    print(_bi("  to Google Ads (Keyword Planner).", "  к Google Ads (Планировщик ключевых слов)."))
    print()

    try:
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            },
            scopes=SCOPES,
        )

        credentials = flow.run_local_server(
            port=0,
            prompt="consent",
            access_type="offline",
        )

        refresh_token = credentials.refresh_token

        if not refresh_token:
            print(_bi("[ERROR] Refresh token not received.", "[ERROR] Refresh token не получен."))
            print(_bi("        Try revoking the app's access at", "        Попробуйте удалить доступ приложения в"))
            print("        https://myaccount.google.com/permissions")
            print(_bi("        and run the script again.", "        и запустить скрипт заново."))
            sys.exit(1)

        print()
        print("=" * 60)
        print(_bi("  ✅ Refresh Token received successfully!", "  ✅ Refresh Token получен успешно!"))
        print("=" * 60)
        print()
        print(_bi(f"  Masked token: {_mask_secret(refresh_token)}", f"  Маскированный токен: {_mask_secret(refresh_token)}"))
        print()

        answer = input(_bi("  Save token to .env automatically? (y/n): ", "  Записать token в .env автоматически? (y/n): ")).strip().lower()
        if answer in ("y", "yes", "д", "да"):
            _update_env_file(env_path, refresh_token)
            print(_bi(f"  ✅ Token saved to .env ({_mask_secret(refresh_token)})", f"  ✅ Токен сохранён в .env ({_mask_secret(refresh_token)})"))
        else:
            print(_bi("  Auto-save cancelled. Copy the token manually:", "  Автосохранение отменено. Скопируйте token вручную:"))
            print(f"  {refresh_token}")
            print(f"  GOOGLE_ADS_REFRESH_TOKEN={refresh_token}")
        print()
        print("=" * 60)

    except Exception as e:
        print(_bi(f"\n[ERROR] Authorization error: {e}", f"\n[ОШИБКА] Ошибка авторизации: {e}"))
        print()
        print(_bi("  Possible causes:", "  Возможные причины:"))
        print(_bi("  - Invalid Client ID / Client Secret", "  - Неверные Client ID / Client Secret"))
        print(_bi("  - OAuth Consent Screen not published (Testing status)", "  - OAuth Consent Screen не опубликован (статус Testing)"))
        print(_bi("  - Google Ads API not enabled in the project", "  - Google Ads API не включён в проекте"))
        print()
        print(_bi("  Check:", "  Проверьте:"))
        print("  1. https://console.cloud.google.com/apis/credentials")
        print(
            "  2. https://console.cloud.google.com/apis/library/googleads.googleapis.com"
        )
        sys.exit(1)
# FUNCTION_CONTRACT: _update_env_file
# Purpose: Implement the  update env file helper for this module.
# Input: env_path (str), refresh_token (str)
# Output: None
# Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
# Business Rules: Preserves the current validation and control flow for this call path.
# Failure Modes: Propagates upstream exceptions and existing fallback paths.
# LINKS: requirements.xml#UC-001
def _update_env_file(env_path: str, refresh_token: str) -> None:
    try:
        if not os.path.exists(env_path):
            print(_bi(f"  [WARN] File {env_path} not found, creating a new one.", f"  [ВНИМАНИЕ] Файл {env_path} не найден, создаю новый."))
            with open(env_path, "a", encoding="utf-8") as f:
                f.write(f"\nGOOGLE_ADS_REFRESH_TOKEN={refresh_token}\n")
            print(_bi("  ✅ Token written to .env", "  ✅ Токен записан в .env"))
            return

        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith("GOOGLE_ADS_REFRESH_TOKEN"):
                lines[i] = f"GOOGLE_ADS_REFRESH_TOKEN={refresh_token}\n"
                found = True
                break

        if not found:
            lines.append(f"\nGOOGLE_ADS_REFRESH_TOKEN={refresh_token}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(_bi("  ✅ .env updated automatically!", "  ✅ .env обновлён автоматически!"))

    except Exception as e:
        print(_bi(f"  [ERROR] Could not update .env: {e}", f"  [ОШИБКА] Не удалось обновить .env: {e}"))
        print(_bi("  Re-run the generation and choose manual token copy.", "  Повторите генерацию и выберите ручное копирование token."))


if __name__ == "__main__":
    main()
