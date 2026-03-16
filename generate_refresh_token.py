"""
Скрипт для генерации Google Ads OAuth2 Refresh Token.

Использование:
    1. Убедитесь, что в .env заполнены GOOGLE_ADS_CLIENT_ID и GOOGLE_ADS_CLIENT_SECRET
    2. Запустите: python generate_refresh_token.py
    3. Откроется браузер — авторизуйтесь в Google аккаунте с доступом к Google Ads
    4. Скопируйте полученный refresh_token в .env -> GOOGLE_ADS_REFRESH_TOKEN

Требования:
    pip install google-auth-oauthlib python-dotenv
"""

import os
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("[ERROR] Модуль google-auth-oauthlib не установлен.")
    print("        Установите: pip install google-auth-oauthlib")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("[ERROR] Модуль python-dotenv не установлен.")
    print("        Установите: pip install python-dotenv")
    sys.exit(1)


def _mask_secret(secret: str, visible_tail: int = 6) -> str:
    if not secret:
        return ""
    if len(secret) <= visible_tail:
        return "*" * len(secret)
    return f"{'*' * (len(secret) - visible_tail)}{secret[-visible_tail:]}"


def main() -> None:
    # Загружаем .env из папки скрипта
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(env_path)

    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("=" * 60)
        print("[ERROR] В .env не заполнены GOOGLE_ADS_CLIENT_ID")
        print("        и/или GOOGLE_ADS_CLIENT_SECRET.")
        print()
        print("  1. Откройте Google Cloud Console:")
        print("     https://console.cloud.google.com/apis/credentials")
        print("  2. Создайте или откройте OAuth 2.0 Client ID")
        print("  3. Скопируйте Client ID и Client Secret в .env")
        print("=" * 60)
        sys.exit(1)

    SCOPES = ["https://www.googleapis.com/auth/adwords"]

    print("=" * 60)
    print("  Google Ads — Генерация Refresh Token")
    print("=" * 60)
    print()
    print(f"  Client ID:     {client_id[:20]}...")
    print(f"  Client Secret: {client_secret[:8]}...")
    print()
    print("  Сейчас откроется браузер для авторизации.")
    print("  Войдите в Google аккаунт, который имеет доступ")
    print("  к Google Ads (Планировщик ключевых слов).")
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
            print("[ERROR] Refresh token не получен.")
            print("        Попробуйте удалить доступ приложения в")
            print("        https://myaccount.google.com/permissions")
            print("        и запустить скрипт заново.")
            sys.exit(1)

        print()
        print("=" * 60)
        print("  ✅ Refresh Token получен успешно!")
        print("=" * 60)
        print()
        print(f"  Masked token: {_mask_secret(refresh_token)}")
        print()

        answer = input("  Записать token в .env автоматически? (y/n): ").strip().lower()
        if answer in ("y", "yes", "д", "да"):
            _update_env_file(env_path, refresh_token)
            print(f"  ✅ Токен сохранён в .env ({_mask_secret(refresh_token)})")
        else:
            print("  Автосохранение отменено. Скопируйте token вручную:")
            print(f"  {refresh_token}")
            print(f"  GOOGLE_ADS_REFRESH_TOKEN={refresh_token}")
        print()
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Ошибка авторизации: {e}")
        print()
        print("  Возможные причины:")
        print("  - Неверные Client ID / Client Secret")
        print("  - OAuth Consent Screen не опубликован (статус Testing)")
        print("  - Google Ads API не включён в проекте")
        print()
        print("  Проверьте:")
        print("  1. https://console.cloud.google.com/apis/credentials")
        print(
            "  2. https://console.cloud.google.com/apis/library/googleads.googleapis.com"
        )
        sys.exit(1)


def _update_env_file(env_path: str, refresh_token: str) -> None:
    """Обновить GOOGLE_ADS_REFRESH_TOKEN в .env файле."""
    try:
        if not os.path.exists(env_path):
            print(f"  [WARN] Файл {env_path} не найден, создаю новый.")
            with open(env_path, "a", encoding="utf-8") as f:
                f.write(f"\nGOOGLE_ADS_REFRESH_TOKEN={refresh_token}\n")
            print("  ✅ Токен записан в .env")
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

        print("  ✅ .env обновлён автоматически!")

    except Exception as e:
        print(f"  [ERROR] Не удалось обновить .env: {e}")
        print("  Повторите генерацию и выберите ручное копирование token.")


if __name__ == "__main__":
    main()
