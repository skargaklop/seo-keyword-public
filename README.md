# Auto SEO Keyword Planner

Streamlit-приложение для сбора семантики, получения идей ключевых слов из Google Ads и генерации SEO-текстов по URL или keyword seed.

Важно: работа с `Keyword Planner` через Google Ads API требует доступа уровня `Basic`. Автоматически созданный API token сам по себе не даёт доступ к `Keyword Planner`, поэтому для включения этой части API нужно отдельно обращаться в поддержку Google Ads и запрашивать `Basic access`.

Автору не нравится интерфейс Google Ads, поэтому эта утилита была сделана как более удобная оболочка для повседневной работы с семантикой, идеями ключевых слов и SEO-текстами.

## Возможности

- 3 режима работы:
  - `URL -> LLM -> Ads`
  - `URL -> Ads ideas`
  - `Keyword seed -> Ads ideas`
- Извлечение текста со страниц и поиск коммерческих ключевых слов через LLM.
- Получение метрик Google Ads: volume, competition, `Low CPC`, `High CPC`, валюта CPC.
- Генерация SEO-текстов по выбранным ключевым словам.
- История запусков с восстановлением checkpoint и повторным использованием данных.
- Экспорт результатов в Excel и CSV, включая отдельный экспорт SEO-текстов.
- Настраиваемые retention-политики для API-логов и истории.
- Настраиваемые лимиты загрузки файлов (`.txt`, `.csv`).
- Блокировка небезопасных URL для scraping: internal/private/loopback endpoints не допускаются.

## Установка

1. Перейдите в папку проекта:

   ```bash
   cd auto-seo-keyword-planner
   ```

2. Создайте и активируйте виртуальное окружение:

   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. Установите зависимости:

   ```bash
   pip install -r requirements.txt
   ```

4. Настройте переменные окружения:
   - Скопируйте `.env.example` в `.env`
   - Заполните хотя бы один ключ LLM-провайдера:
     - `OPENAI_API_KEY`
     - `ANTHROPIC_API_KEY`
     - `GEMINI_API_KEY`
     - `XAI_API_KEY`
     - `GROQ_API_KEY`
     - `DEEPSEEK_API_KEY`
     - `MINIMAX_API_KEY`
     - `MOONSHOT_API_KEY`
     - `OPENROUTER_API_KEY`
     - `CEREBRAS_API_KEY`
     - `ZAI_API_KEY`
   - Если нужны Google Ads метрики, заполните:
     - `GOOGLE_ADS_DEVELOPER_TOKEN`
     - `GOOGLE_ADS_CUSTOMER_ID`
     - `GOOGLE_ADS_LOGIN_CUSTOMER_ID`
     - `GOOGLE_ADS_CLIENT_ID`
     - `GOOGLE_ADS_CLIENT_SECRET`
     - `GOOGLE_ADS_REFRESH_TOKEN`

## Конфигурация

Основной конфиг находится в `config/settings.yaml`. Те же параметры можно менять из боковой панели приложения; изменения сохраняются обратно в YAML.

### Что настраивается

- `retry.max_attempts`, `retry.delay_seconds`, `retry.backoff_factor`
- `llm.timeout_seconds`
- `llm.delay_between_requests_seconds`
- `llm.max_keywords_per_url`
- `llm.models.*`
- `llm.prompts.keyword_extraction`
- `llm.prompts.seo_description`
- `google_ads.location_id`
- `google_ads.language_id`
- `google_ads.currency_code`
- `cleanup.max_age_days`
- `logging.app_level`
- `logging.console_enabled`
- `logging.console_level`
- `logging.api_enabled`
- `logging.api_level`
- `logging.api_retention_days`
- `logging.error_level`
- `logging.log_test_runs`
- `history.retention_days`
- `uploads.max_file_size_mb`
- `uploads.max_rows`
- `ui.language`
- `ui.provider`
- `ui.model`
- `ui.max_keywords`

### Sidebar

В sidebar доступны отдельные секции:

- язык интерфейса
- LLM provider и model
- Google Ads
- API parameters
- system prompts
- export and cleanup
- storage and limits
- logging

### Текущие модели по умолчанию

Значения берутся из `config/settings.yaml`:

- `openai`: `gpt-5.2`
- `anthropic`: `claude-sonnet-4-6`
- `google`: `gemini-3-flash-preview`
- `xai`: `grok-4-1-fast-reasoning`
- `groq`: `openai/gpt-oss-120b`
- `deepseek`: `deepseek-chat`
- `minimax`: `MiniMax-M2.5`
- `moonshot`: `moonshot/kimi-k2.5`
- `openrouter`: `openrouter/free`
- `cerebras`: `gpt-oss-120b`
- `zai`: `glm-4.7`

### Переопределение endpoint'ов через `.env`

При необходимости можно переопределить base URL через `.env`:

- `OPENAI_BASE_URL=https://api.openai.com/v1`
- `ANTHROPIC_BASE_URL=https://api.anthropic.com`
- `GEMINI_BASE_URL=https://generativelanguage.googleapis.com`

- `XAI_BASE_URL=https://api.x.ai/v1`
- `GROQ_BASE_URL=https://api.groq.com/openai/v1`
- `DEEPSEEK_BASE_URL=https://api.deepseek.com/v1`
- `MINIMAX_BASE_URL=https://api.minimax.io/v1`
- `MOONSHOT_BASE_URL=https://api.moonshot.cn/v1`
- `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`
- `CEREBRAS_BASE_URL=https://api.cerebras.ai/v1`
- `ZAI_BASE_URL=https://api.z.ai/api/coding/paas/v4`

## Запуск

### Windows

```bash
run_app.bat
```

`run_app.bat` проверяет наличие Python и критичных зависимостей перед запуском приложения.

### Прямой запуск Streamlit

```bash
streamlit run app.py
```

Обычно приложение открывается по адресу `http://localhost:8501`.

## Использование

1. Выберите язык интерфейса, LLM-провайдера и модель в sidebar.
2. При необходимости настройте Google Ads, API parameters, prompts и export behavior.
3. Выберите `Workflow mode`:
   - `URL -> LLM -> Ads`: scraping страницы, извлечение ключей через LLM, затем метрики Google Ads.
   - `URL -> Ads ideas`: генерация идей через Google Ads по URL seed без предварительного LLM-этапа.
   - `Keyword seed -> Ads ideas`: генерация идей из вручную введённых ключевых слов или загруженного файла.
4. Введите данные вручную или загрузите `.txt` / `.csv`.
5. Нажмите кнопку запуска анализа.
6. Просмотрите результаты и при необходимости выберите ключевые слова для генерации SEO-текстов.
7. Скачайте результаты в Excel или CSV.
8. При необходимости используйте историю, чтобы:
   - восстановить checkpoint
   - повторно запустить генерацию ключевых слов
   - продолжить работу с сохранённым набором данных

## История и хранение данных

- История сохраняется в `data/history.json`.
- История содержит checkpoint, включая данные, нужные для восстановления UI-состояния и продолжения работы.
- Старые записи истории удаляются по `history.retention_days`.
- Старые API-логи удаляются по `logging.api_retention_days`.
- Очистка `outputs/`, API-логов и history выполняется на старте приложения.

Если `retention_days = 0`, автоматическая очистка отключена.

## Лимиты загрузки

- Поддерживаются файлы `.txt` и `.csv`.
- Максимальный размер файла задаётся через `uploads.max_file_size_mb`.
- Максимальное число строк задаётся через `uploads.max_rows`.
- При превышении лимитов файл отклоняется до запуска workflow.

## Логирование

Приложение пишет несколько логов:

- `logs/app.log`: общая информация о работе приложения
- `logs/api_requests.log`: API-запросы и служебная отладочная информация
- `logs/errors.log`: ошибки

Управление логированием идёт через `logging.*` в `config/settings.yaml` и через sidebar.

## Вспомогательные скрипты

| Файл | Назначение |
|---|---|
| `run_app.bat` | Проверка зависимостей и запуск приложения |
| `run_tests.bat` | Запуск тестов |
| `generate_refresh_token.bat` | Генерация OAuth2 refresh token для Google Ads API |
| `generate_refresh_token.py` | CLI-скрипт генерации refresh token |

При успешной генерации `generate_refresh_token.py` предлагает записать token в `.env`. Если пользователь отказывается, token выводится один раз для ручного копирования.

## Безопасность scraping

- Разрешены только `http` и `https`.
- Private, loopback, localhost, link-local и другие internal endpoints блокируются.
- Redirect target проходит ту же проверку безопасности.

## Тесты

```bash
run_tests.bat
```

Или:

```bash
python -m pytest tests -q
```

## Дополнительно

- Инструкция по настройке Google Ads API: [GOOGLE_ADS_SETUP.md](GOOGLE_ADS_SETUP.md)
- Пример переменных окружения: [`.env.example`](.env.example)
