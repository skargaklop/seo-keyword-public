# Auto SEO Keyword Planner

<!--
MODULE_CONTRACT: README
Purpose: Document Auto SEO Keyword Planner workflows, configuration, dependencies, and GRACE phase behavior.
Rationale: Provides the documentation implementation surface for the MOD-DOC graph module.
Dependencies: docs/development-plan.xml, docs/knowledge-graph.xml, docs/verification-plan.xml.
Exports: user-facing project documentation.
LINKS: knowledge-graph.xml#MOD-DOC
MODULE_MAP: README.md
Public Functions: documentation sections.
Private Helpers: none.
Key Semantic Blocks: none.
Critical Flows: describe workflows -> document configuration -> record browser/Trends/cache/SEO math caveats.
Verification: verification-plan.xml#V-09-DOCS, verification-plan.xml#V-12-DOCS-GRACE
CHANGE_SUMMARY: Added GRACE documentation module contract linking README to MOD-DOC.
-->

> **Русская версия.** [English version](README.md)

Streamlit-приложение для сбора семантики, получения идей ключевых слов из Google Ads и генерации SEO-текстов по URL или keyword seed.

## Возможности

### Режимы работы

- **SERP Analysis** — анализ Google SERP для ключевых слов с информацией о позициях, PAA (People Also Ask) и Related Searches
- **Google Trends** — анализ Google Trends с interest over time, related queries/topics и региональными данными (стandalone или как optional stage)
- **URL -> LLM -> Ads** — scraping страницы, извлечение ключевых слов через LLM, затем метрики Google Ads с выбором ключей
- **URL -> Ads ideas** — генерация идей через Google Ads по URL seed
- **Keyword seed -> Ads ideas** — генерация идей из ключевых слов
- **Ключевые слова -> LLM SEO текст** — генерация SEO-текста напрямую из выбранных ключевых слов с выбором языка
- **Crawl Report** — математический анализ контента на нескольких страницах с keyword extraction, BM25F и leak-inspired signals

### Основные функции

- **SERP Analysis**: многопровайдерный клиент с адаптерами для Serper, SerpApi, Brave, Zenserp, SearchApi.io, ScraperAPI, DataForSEO, Serpstat
- **Context-aware chaining**: выбранные ключевые слова и результаты можно передавать в SERP, Ads, Trends и SEO из URL- и keyword-driven workflows
- **Mathematical SEO**:
  - **BM25F scoring**: field-weighted BM25F анализ с настраиваемыми весами полей (title, H1, snippet, body, anchor text)
  - **BM25+ formula**: используется BM25+ вариант с сглаживанием IDF (`+1` для предотвращения отрицательных значений)
  - **Leak-inspired signals**: title alignment, content effort score, topical overlap, SimHash64 fingerprinting
  - **Traditional metrics**: n-grams (1-3), TF-IDF, co-occurrence (с Jaccard similarity), intent analysis, content gaps для SERP и scraped контента
- **SEO text generation**: генерация SEO-текстов с оценками качества и возможностью регенерации
- **Source context propagation**: URL workflows сохраняют source_url через весь пайплайн для SERP match highlighting
- **SERP match highlighting**: в UI и Excel-экспорте подсвечиваются совпадения URL/domain из source URLs
- **SERP rank enrichment**: таблицы Google Ads дополняются колонками `Page URL in SERP` и `SERP Rank`
- **Bidirectional SERP↔Ads merge**: при наличии одновременно таблицы Google Ads и SERP-анализа по тем же ключевым словам (в любом порядке) таблица Ads дополняется тремя по ключевым словам SERP-колонками — `SERP #results`, `SERP top position` и `SERP top3 domains` (топ-3 уникальных домена по рангу). Слияние запускается автоматически как побочный эффект **Send to SERP**, когда оба набора данных присутствуют, независимо от того, что выполнялось первым, и экспортируется одним файлом
- **Bidirectional Ads↔Trends merge**: аналогично, при наличии таблицы Google Ads и averages Google Trends таблица Ads дополняется колонками `Trends Avg Interest`, `Trends Geo` и `Trends Timeframe`. После **Send to Trends** показываются и сырая таблица averages Trends, и объединённая таблица Ads; слияние работает в любом порядке выполнения и экспортируется одним файлом
- **URL LLM staged extraction**: URL → LLM workflow всегда делает паузу для выбора ключевых слов перед downstream actions
- **Prompt content injection**: опциональная подстановка `{content}` (scraped page text) в SEO prompt с лимитом 5000 символов
- **History-backed cache**: персистентный кэш для всех API запросов и анализа с TTL, force refresh и cache-relevant settings hash
- **Google Trends integration**:
  - Standalone workflow mode для анализа Google Trends
  - Опциональная stage после любого keyword-producing workflow step
  - Interest over time, related queries, related topics, region data
  - Относительные значения 0-100 с опциональным anchor rescaling
  - Rate limiting и кэширование для избежания 429 errors
- **OPT-IN browser scraping**: опциональный browser-based fallback для Google Trends и SERP (требует дополнительных зависимостей)
- **Export**: Excel с styling для URL matches, CSV с метаданными, включая BM25F/signal/Trends/cache метаданные
- **Merged report export**: объединенный Excel отчет с Summary, SERP Analysis, Ads Data, Math Analysis sheets. (Не путать с по-ключевым SERP↔Ads и Ads↔Trends объединениями колонок, описанными выше, — они расширяют одну таблицу Ads, а не объединяют отдельные листы.)
- **History**: checkpoint-based история с восстановлением состояния
- **Retention policies**: настраиваемые политики для API-логов и истории
- **File upload limits**: `.txt`, `.csv` с настраиваемыми лимитами размера и строк
- **URL safety**: internal/private/loopback endpoints блокируются для scraping

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

   The refreshed console UI dependencies include `streamlit-shadcn-ui` and `streamlit-extras`; both packages are included in the pinned requirements list above for the refreshed UI toolkit.

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
   - Если нужны SERP результаты, заполните хотя бы один SERP API key:
     - `SERPER_API_KEY` (Google via Serper)
     - `SERPAPI_KEY` (SerpApi)
     - `BRAVE_SEARCH_API_KEY` (Brave Search)
     - `ZENSERP_KEY` (Zenserp)
     - `SEARCHAPI_IO_KEY` (SearchApi.io)
     - `SCRAPERAPI_KEY` (ScraperAPI)
     - `DATAFORSEO_LOGIN` и `DATAFORSEO_PASSWORD` (DataForSEO)
     - `SERPSTAT_TOKEN` (Serpstat)
   - Если нужны Google Ads метрики, заполните:
     - `GOOGLE_ADS_DEVELOPER_TOKEN`
     - `GOOGLE_ADS_CUSTOMER_ID`
     - `GOOGLE_ADS_LOGIN_CUSTOMER_ID`
     - `GOOGLE_ADS_CLIENT_ID`
     - `GOOGLE_ADS_CLIENT_SECRET`
     - `GOOGLE_ADS_REFRESH_TOKEN`

**Опционально: Browser Scraping (OPT-IN)**
Для использования browser-based scraping fallback для Google Trends и SERP:
- Установите дополнительные зависимости:
  ```bash
  python -m pip install --upgrade cloakbrowser trafilatura
  ```
  Global user Python option:
  ```bash
  python -m pip install --user --upgrade cloakbrowser trafilatura
  ```
  The sidebar checks `cloakbrowser` and `trafilatura`. If a tool is missing or installed but does not expose the expected API, the workflow shows a status table and asks whether to use the project-environment install command or the global user Python command.
- Установите `scraper.browser_enabled: true` в `config/settings.yaml` или через sidebar
- Browser scraping отключён по умолчанию и не требуется для базовой функциональности

## Конфигурация

Приложение настраивается тремя способами. **Приоритет:** переменные окружения (`.env`) > параметры `config/settings.yaml` > значения по умолчанию в коде. Параметры из `settings.yaml` дублируются в боковой панели приложения — кнопка **«Сохранить настройки»** записывает изменения обратно в YAML.

| Источник | Назначение |
|---|---|
| `.env` | API-ключи, учётные данные OAuth, переопределение endpoint'ов, поведенческие флаги |
| `config/settings.yaml` | Вся логика: retry, LLM, SERP, SEO Math, Crawler, Cache, Trends, Browser Scraper, cleanup/logging/storage |
| Боковая панель (UI) | Редактируемый слой над `settings.yaml`; несколько переключателей работают только в текущей сессии |

> Имена переменных окружения и ключей чувствительны к регистру. В примерах ниже используется точное написание из кода — например `ZENSERP_KEY` (не `ZENSERP_API_KEY`), `SERPSTAT_TOKEN` (не `SERPSTAT_API_KEY`), `SERPAPI_KEY` одним словом.

---

### A. Переменные окружения (`.env`)

Загружаются через `python-dotenv` (`config/settings.py`, `override=True`) и читаются во время выполнения через `os.getenv`/`os.environ.get`. Скопируйте `.env.example` в `.env` и заполните нужные.

#### Google Ads — учётные данные

Нужны все обязательные учётные данные Google Ads, чтобы получить метрики. Без них приложение работает, но метрики недоступны. `GOOGLE_ADS_REFRESH_TOKEN` генерируется через `generate_refresh_token.py`.

| Переменная | Описание | Значения |
|---|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Developer token Google Ads API | строка токена |
| `GOOGLE_ADS_CUSTOMER_ID` | ID клиентского аккаунта (CID) | числовая строка, дефисы опц. (`123-456-7890`) |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | CID менеджерского аккаунта (MCC) | числовая строка; опционально для прямых аккаунтов |
| `GOOGLE_ADS_CLIENT_ID` | OAuth 2.0 Client ID | `*.apps.googleusercontent.com` |
| `GOOGLE_ADS_CLIENT_SECRET` | OAuth 2.0 Client Secret | строка секрета |
| `GOOGLE_ADS_REFRESH_TOKEN` | OAuth refresh token | строка токена (`1//...`) |

#### LLM — API-ключи провайдеров

Ключи читаются динамически как `{ПРОВАЙДЕР}_API_KEY`. В боковой панели видны только провайдеры, у которых задан ключ.

| Переменная | Описание |
|---|---|
| `OPENAI_API_KEY` | OpenAI (`sk-...`) |
| `ANTHROPIC_API_KEY` | Anthropic / Claude (`sk-ant-...`) |
| `GEMINI_API_KEY` | Google Gemini (`AIza...`) |
| `XAI_API_KEY` | xAI / Grok |
| `GROQ_API_KEY` | Groq (`gsk_...`) |
| `DEEPSEEK_API_KEY` | DeepSeek (`sk-...`) |
| `MINIMAX_API_KEY` | MiniMax |
| `MOONSHOT_API_KEY` | Moonshot / Kimi (`sk-...`) |
| `OPENROUTER_API_KEY` | OpenRouter (`sk-or-...`) — провайдер по умолчанию для fallback |
| `CEREBRAS_API_KEY` | Cerebras |
| `ZAI_API_KEY` | Z.AI / GLM |
| `MISTRAL_API_KEY` | Mistral (только отображение в списке провайдеров) |

Ключи для **пользовательских провайдеров** (см. `llm.custom_providers` ниже) читаются по имени env-переменной, указанной в `api_key_env`. Пример: запись `omniroute` использует `OMNIROUTE_API_KEY`.

#### LLM — переопределение endpoint'ов (опционально)

`{ПРОВАЙДЕР}_BASE_URL` переопределяет адрес API (для Azure, прокси, локальных серверов). Пустое значение → официальный endpoint провайдера.

| Переменная | Значение по умолчанию (из `.env.example`) |
|---|---|
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com` |
| `XAI_BASE_URL` | `https://api.x.ai/v1` |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` |
| `MINIMAX_BASE_URL` | `https://api.minimax.io/v1` |
| `MOONSHOT_BASE_URL` | `https://api.moonshot.cn/v1` |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` |
| `CEREBRAS_BASE_URL` | `https://api.cerebras.ai/v1` |
| `ZAI_BASE_URL` | `https://api.z.ai/api/coding/paas/v4` |

#### SERP — API-ключи провайдеров

Каждый ключ соответствует провайдеру из реестра `utils/serp_client.py` (`PROVIDER_REGISTRY`). В боковой панели видны только провайдеры с заданным ключом.

| Переменная | Провайдер (id) |
|---|---|
| `SERPER_API_KEY` | Serper.dev (`serper_dev`) |
| `SERPAPI_KEY` | SerpApi (`serpapi`) — также для Google Trends |
| `BRAVE_SEARCH_API_KEY` | Brave Search (`brave_search`) |
| `SEARCHAPI_IO_KEY` | SearchApi.io (`searchapi_io`) |
| `ZENSERP_KEY` | Zenserp (`zenserp`) |
| `SCRAPERAPI_KEY` | ScraperAPI (`scraperapi`) |
| `DATAFORSEO_LOGIN` + `DATAFORSEO_PASSWORD` | DataForSEO (`dataforseo`) — нужны оба |
| `SERPSTAT_TOKEN` | Serpstat (`serpstat`) |
| `SERPSTACK_KEY` | Serpstack (`serpstack`) |
| `SCALESERP_KEY` | ScaleSERP (`scaleserp`) |
| `VALUESERP_KEY` | ValueSERP (`valueserp`) |

#### Google Trends — опциональные ключи

| Переменная | Описание |
|---|---|
| `SCRAPEBADGER_KEY` | ScrapeBadger — generic web-scrape fallback для Trends (отправляется как `x-api-key`) |

#### Поведенческие флаги

| Переменная | Описание | Значения |
|---|---|---|
| `ALLOW_LOCALHOST_PROVIDERS` | Разрешает `localhost`/приватные IP в base URL пользовательских провайдеров (для локальных LLM — Ollama, LM Studio и т.п.) | truthy: `1`, `true`, `yes` (без учёта регистра); всё прочее = выкл. По умолчанию выкл. |

---

### B. Параметры `config/settings.yaml`

Основной конфигурационный файл. Загружается один раз через `config/settings.py` (`load_config()`); секции экспортируются как константы (`SERP_CONFIG`, `SEO_MATH_CONFIG` и т.д.). Значения по умолчанию берутся через `.get(key, fallback)` — отсутствующий ключ не ломает запуск.

#### `retry`

| Ключ | Описание | Значения | По умолчанию |
|---|---|---|---|
| `retry.max_attempts` | Макс. попыток retry для LLM/SERP/Trends | целое ≥ 1 | `3` |
| `retry.delay_seconds` | Базовая пауза между retry (с) | целое ≥ 0 | `4` |
| `retry.backoff_factor` | Множитель экспоненциального backoff (Trends) | float > 0 | `1.5` |

#### `llm`

| Ключ | Описание | Значения | По умолчанию |
|---|---|---|---|
| `llm.fallback_provider` | Провайдер при ошибке основного | id провайдера | `openrouter` |
| `llm.fallback_model` | Модель для fallback | id модели | `openrouter/free` |
| `llm.timeout_seconds` | Таймаут запроса к LLM (с) | целое 10–300 (в UI) | `180` |
| `llm.max_keywords_per_url` | Лимит ключей, извлекаемых с одного URL | целое | `20` |
| `llm.generation_language` | Устаревший язык генерации (fallback) | строка языка | `Russian` |
| `llm.keyword_llm_generation_language` | Язык SEO-генерации в Keyword→LLM | `Russian`/`Ukrainian`/`English`/`German`/`French`/`Spanish`/`Italian`/`Portuguese`/`Polish` | `Ukrainian` |
| `llm.page_type` | Тип страницы для плейсхолдера `{page_type}` | `product`/`category`/`blog post`/своя строка | `product` |
| `llm.delay_between_requests_seconds` | Пауза между запросами LLM (с) | целое 0–60 (в UI) | `2` |
| `llm.prompts.keyword_extraction` | Системный промпт извлечения ключей | multiline; подстав. `{max_keywords}` | (текст в YAML) |
| `llm.prompts.seo_description` | Системный промпт SEO-генерации | multiline; подстав. `{language}`, `{keywords_list}`, `{content}`, `{page_type}` | (текст в YAML) |

**`llm.models`** — id модели по умолчанию для каждого провайдера:

| провайдер | модель |
|---|---|
| `openai` | `gpt-5.2` |
| `anthropic` | `claude-sonnet-4-6` |
| `google` | `gemini-3-flash-preview` |
| `xai` | `grok-4-1-fast-reasoning` |
| `groq` | `openai/gpt-oss-120b` |
| `deepseek` | `deepseek-chat` |
| `minimax` | `MiniMax-M2.5` |
| `moonshot` | `moonshot/kimi-k2.5` |
| `openrouter` | `openrouter/free` |
| `cerebras` | `gpt-oss-120b` |
| `zai` | `glm-4.7` |

**`llm.custom_providers`** — список пользовательских OpenAI-совместимых провайдеров. Каждый объект: `name` (id), `display_name`, `base_url`, `api_key_env` (имя env-переменной с ключом). По умолчанию одна запись — `omniroute` (`http://localhost:20128/v1`, ключ `OMNIROUTE_API_KEY`). Управляется через expander «Пользовательские провайдеры» в боковой панели.

#### `keywords`

| Ключ | Описание | Значения | По умолчанию |
|---|---|---|---|
| `keywords.allowed_languages` | Белый список языков ключей | список 2-букв. кодов | `[ru, uk]` |
| `keywords.min_keyword_length` | Мин. длина ключа (символы) | целое ≥ 1 | `3` |

#### `scraping`

| Ключ | Описание | Значения | По умолчанию |
|---|---|---|---|
| `scraping.timeout_seconds` | Таймаут HTTP для базового `requests`-скрапера (с) | целое | `30` |
| `scraping.max_urls_per_batch` | Макс. URL в одном батче скрапинга | целое | `20` |

#### `google_ads`

| Ключ | Описание | Значения | По умолчанию |
|---|---|---|---|
| `google_ads.location_id` | Geo-target criterion id | числовая строка (`2804` Украина, `2643` Россия, `2840` США …) | `'2804'` |
| `google_ads.language_id` | Language criterion id | строка или список (`1031` RU, `1036` UK, `1000` EN, `1001` DE, `1002` FR, `1003` ES, `1004` IT, `1014` PT, `1015` PL) | `[1031, 1036]` |
| `google_ads.currency_code` | Валюта метрик (ISO 4217) | `UAH`/`USD`/`EUR` | `UAH` |
| `google_ads.max_keywords_per_request` | Лимит ключей на запрос Keyword Plan | целое | `1000` |

#### `serp`

| Ключ | Описание | Значения | По умолчанию |
|---|---|---|---|
| `serp.provider` | Активный провайдер | `serper_dev`/`serpapi`/`brave_search`/`searchapi_io`/`zenserp`/`scraperapi`/`dataforseo`/`serpstat`/`serpstack`/`scaleserp`/`valueserp`/`browser_cloakbrowser` | `browser_cloakbrowser` |
| `serp.num_results` | Кол-во organic-результатов | целое 1–100 | `10` |
| `serp.gl` | Геолокация (страна) | `ua`/`us`/`ru`/`de`/`uk`/`pl` | `ua` |
| `serp.hl` | Язык интерфейса Google | `uk`/`ru`/`en`/`de`/`pl` | `uk` |
| `serp.timeout_seconds` | Таймаут запроса SERP (с) | целое | `30` |
| `serp.device` | Устройство | `` `` `` (не задано)/`desktop`/`mobile`/`tablet` | `''` |
| `serp.search_type` | Тип поиска | `web`/`images`/`videos`/`news`/`shopping` | `web` |
| `serp.time_period` | Период времени | `any`/`hour`/`day`/`week`/`month`/`year` | `any` |
| `serp.safe_search` | Безопасный поиск | `off`/`active` | `'off'` |
| `serp.google_domain` | Домен Google | `google.com`/`google.co.uk`/`google.de`/`google.fr`/`google.com.ua`/`google.ru`/`google.com.tr`/`google.pl` | `google.com.ua` |
| `serp.location` | Текстовое название локации (город) | строка | `''` |
| `serp.uule` | Закодированный сигнал UULE | base64-строка | `''` |

#### `seo_math`

| Ключ | Описание | Значения | По умолчанию |
|---|---|---|---|
| `seo_math.enabled` | Мастер-переключатель движка анализа | boolean | `true` |
| `seo_math.analyze_ngrams` | Анализ n-грамм | boolean | `true` |
| `seo_math.analyze_tfidf` | TF-IDF анализ | boolean | `true` |
| `seo_math.analyze_cooccurrence` | Co-occurrence анализ | boolean | `true` |
| `seo_math.analyze_intent` | Анализ интента | boolean | `true` |
| `seo_math.analyze_generation_quality` | Оценка качества генерации | boolean | `true` |
| `seo_math.analyze_generated_text` | Скоринг сгенерированного SEO-текста | boolean | `false` |
| `seo_math.analyze_bm25f` | BM25F field-weighted анализ | boolean | `true` |
| `seo_math.ngram_min` | Мин. размер n-граммы | целое 1–2 | `1` |
| `seo_math.ngram_max` | Макс. размер n-граммы | целое 2–4 | `4` |
| `seo_math.top_terms_limit` | Сколько топ-терминов учитывать | целое 10–50 | `50` |
| `seo_math.min_ngram_count` | Мин. вхождений n-граммы | целое 1–5 | `2` |
| `seo_math.min_document_frequency` | Мин. document frequency | целое 1–5 | `2` |
| `seo_math.use_related_searches` | Включать Related Searches в корпус | boolean | `true` |
| `seo_math.use_people_also_ask` | Включать People Also Ask | boolean | `true` |
| `seo_math.strip_suffixes` | Срезать RU/UK суффиксы при токенизации | boolean | `false` |

**`seo_math.bm25f_params`** — параметры формулы BM25+:

| Ключ | Значения | По умолчанию |
|---|---|---|
| `k1` | float 0.1–5.0 | `1.2` |
| `b_body` | float 0.0–1.0 | `0.75` |
| `b_title` | float 0.0–1.0 | `0.5` |
| `b_snippet` | float 0.0–1.0 | `0.6` |

**`seo_math.field_weights`** — веса полей (float 0.0–10.0):

| поле | по умолчанию | | поле | по умолчанию |
|---|---|---|---|---|
| `serp_title` | 3.0 | | `related_searches` | 1.2 |
| `page_title` | 3.0 | | `people_also_ask` | 1.1 |
| `h1` | 2.5 | | `trends_related` | 1.2 |
| `meta_description` | 1.5 | | `body_text` | 1.0 |
| `serp_snippet` | 1.5 | | `anchor_text` | 1.4 |

**`seo_math.signals`** — leak-inspired сигналы (все boolean, по умолчанию `true`): `title_alignment`, `content_effort`, `topical_overlap`, `simhash`.

#### `crawler`

| Ключ | Описание | Значения | По умолчанию |
|---|---|---|---|
| `crawler.enabled` | Включён ли crawler | boolean | `true` |
| `crawler.max_pages` | Макс. страниц за обход | целое 1–100 | `1` |
| `crawler.max_depth` | Глубина перехода по ссылкам (0 = только seed) | целое 0–5 | `3` |
| `crawler.same_domain_only` | Только тот же домен | boolean | `true` |
| `crawler.timeout_seconds` | Общий дедлайн обхода (с) | целое 10–600 | `120` |
| `crawler.max_response_bytes` | Макс. байт на один ответ | целое 1 048 576–52 428 800 | `10485760` |
| `crawler.max_retries` | Доп. попытки на запрос | целое 0–2 | `1` |

#### `cache`

| Ключ | Описание | Значения | По умолчанию |
|---|---|---|---|
| `cache.enabled` | Включён ли персистентный кэш | boolean | `true` |
| `cache.default_ttl_hours` | TTL по умолчанию (часы); реальный TTL зависит от типа записи | целое 1–8760 | `168` |
| `cache.max_cache_records` | Макс. записей в кэше | целое 100–100000 | `10000` |
| `cache.cache_relevant_subset` | Список настроек, влияющих на хэш кэша | список dotted-путей | (см. YAML) |

Фактический TTL по типам записей: SERP/Ads/Crawl/Math = 168 ч, LLM extract/generate/model_fetch = 720 ч, Trends = 24 ч.

#### `google_trends`

| Ключ | Описание | Значения | По умолчанию |
|---|---|---|---|
| `google_trends.provider` | Предпочитаемый провайдер Trends | `browser_scraper_trends`/`dataforseo_trends`/`serpapi_trends`/`scrapebadger_web` | `browser_scraper_trends` |
| `google_trends.provider_order` | Порядок fallback | список id провайдеров | `[browser_scraper_trends, dataforseo_trends, serpapi_trends, scrapebadger_web]` |
| `google_trends.show_confidence_metadata` | Показывать метаданные доверия | boolean | `true` |
| `google_trends.default_geo` | 2-букв. геокод | ISO-код (`UA`, `US`, `GB`, `DE`, `PL`, `RU` …) | `UA` |
| `google_trends.default_timeframe` | Период времени Trends | строка Trends (`today 12-m`, `today 5-y`, `today 1-m`, `now 1-h` …) | `today 12-m` |
| `google_trends.default_category` | Категория Trends (0 = все) | строка из `["", "5", "10", "17", "18", "22", "29", "47", "71", "91", "284", "366"]` → int | `0` |
| `google_trends.default_property` | Вертикаль (gprop) | `` `` ``/`images`/`news`/`youtube`/`froogle` | `''` |
| `google_trends.default_language` | Язык Trends-запроса | `["", "en","ru","uk","de","fr","es","it","pt","ja","ko","zh"]` | `en-US` |
| `google_trends.default_timezone` | Часовой пояс | `["", "0","1","2","3","-1","-2","-3","-5","-8"]` | `0` |
| `google_trends.cache_ttl_hours` | TTL кэша Trends (часы) | целое 1–8760 | `24` |
| `google_trends.max_keywords_per_request` | Максимум ключевых слов, которые локальный браузерный Trends-провайдер обработает за один запуск | целое между `max_keywords_per_request_min` и `max_keywords_per_request_max` | `10` |
| `google_trends.max_keywords_per_request_min` | Нижняя граница UI-контрола лимита ключевых слов | целое | `1` |
| `google_trends.max_keywords_per_request_max` | Верхняя граница UI-контрола лимита ключевых слов | целое | `100` |
| `google_trends.batch_delay_seconds` | Пауза между батч-запросами (с) | float | `2` |
| `google_trends.manual_start_wait` | Ожидание прогрева браузера (с) | целое 0–300 | `0` |
| `google_trends.min_delay` | Мин. случайная пауза между скрапами (с) | целое 1–1800 | `10` |
| `google_trends.max_delay` | Макс. случайная пауза между скрапами (с) | целое 10–1800 | `60` |
| `google_trends.state_file` | Файл состояния сессии браузера | имя файла | `trends_state.json` |
| `google_trends.headless` | Headless-режим браузера Trends | boolean | `false` |

#### `scraper` (browser scraper, OPT-IN)

| Ключ | Описание | Значения | По умолчанию |
|---|---|---|---|
| `scraper.browser_enabled` | Включить browser-based скрапер | boolean | `true` |
| `scraper.engine` | Движок браузера | `cloakbrowser`/`playwright`/`auto` | `cloakbrowser` |
| `scraper.parser` | HTML-парсер | `trafilatura` | `trafilatura` |
| `scraper.headless` | Headless-режим | boolean | `true` |
| `scraper.timeout_seconds` | Таймаут навигации (с) | целое | `30` |
| `scraper.retry_on_failure` | Кол-во retry при ошибке | целое | `3` |

#### `cleanup`, `history`, `uploads`, `logging`

| Ключ | Описание | Значения | По умолчанию |
|---|---|---|---|
| `cleanup.max_age_days` | Возраст файлов `outputs/` для удаления (0 = выкл.) | целое 0–365 | `30` |
| `history.retention_days` | Хранение истории (0 = выкл.) | целое 0–365 | `30` |
| `uploads.max_file_size_mb` | Макс. размер загружаемого файла (MiB) | целое 1–100 | `5` |
| `uploads.max_rows` | Макс. строк из загруженного файла | целое 1–100000 | `1000` |
| `logging.app_level` | Уровень `app.log` | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` | `INFO` |
| `logging.console_enabled` | Логирование в консоль | boolean | `true` |
| `logging.console_level` | Уровень логов консоли | уровень | `INFO` |
| `logging.api_enabled` | Писать `api_requests.log` | boolean | `true` |
| `logging.api_level` | Уровень API-лога | уровень | `WARNING` |
| `logging.api_retention_days` | Хранение API-логов (0 = выкл.) | целое 0–365 | `30` |
| `logging.error_level` | Уровень `errors.log` | уровень | `WARNING` |
| `logging.log_test_runs` | Писать логи во время pytest | boolean | `false` |

#### `ui`

| Ключ | Описание | Значения | По умолчанию |
|---|---|---|---|
| `ui.language` | Язык интерфейса | `ru`/`uk`/`en` | `ru` |
| `ui.provider` | Последний выбранный LLM-провайдер (display name) | строка | `Omniroute` |
| `ui.model` | Последняя выбранная модель | id модели | `vertex/gemini-3.1-pro-preview` |
| `ui.max_keywords` | Значение слайдера «макс. ключей на URL» | целое 5–100 | `50` |

---

### C. Настройки боковой панели (UI)

Боковая панель (`components/sidebar.py`) — это редактируемый слой над `config/settings.yaml`. **Все перечисленные в части B параметры, у которых указан диапазон/перечисление значений, редактируются из UI и сохраняются в YAML кнопкой «Сохранить настройки».** Ниже — секции панели и принадлежащие им контролы (значения см. в таблицах выше).

- **Язык интерфейса** → `ui.language`
- **LLM Provider / Model** → `ui.provider`, `ui.model`; слайдер «Макс. слов на URL» → `ui.max_keywords`; кнопка «Обновить модели» (обновляет кэш моделей); expander «Пользовательские провайдеры» → `llm.custom_providers`
- **SERP Provider** → `serp.provider`, `serp.num_results`, `serp.gl`, `serp.hl`, `serp.device`, `serp.search_type`, `serp.time_period`, `serp.safe_search`, `serp.google_domain`, `serp.location`, `serp.uule`
- **SEO Math Analysis** → `seo_math.enabled` и все `analyze_*`, расширенные параметры (n-gram, BM25F, field weights, signals)
- **Google Trends** → `google_trends.provider`, `default_geo/timeframe/category/property/language/timezone`, `cache_ttl_hours`, `max_keywords_per_request`, локальные настройки (`manual_start_wait`, `min/max_delay`, `state_file`)
- **Cache** → `cache.enabled`, `cache.default_ttl_hours`, `cache.max_cache_records`
- **Scraper (OPT-IN)** → `scraper.browser_enabled` (показывает таблицу статусов зависимостей cloakbrowser/trafilatura)
- **Crawler** → `crawler.*` (max_pages, max_depth, same_domain_only, timeout, max_response_bytes, max_retries)
- **Google Ads** → `google_ads.location_id`, `google_ads.language_id`, `google_ads.currency_code`
- **API Parameters** → `llm.timeout_seconds`, `llm.delay_between_requests_seconds`, `retry.max_attempts`, `retry.delay_seconds`
- **System Prompts** → `llm.prompts.keyword_extraction`, `llm.prompts.seo_description`, `llm.keyword_llm_generation_language`, `llm.page_type`
- **Storage & Limits** → `logging.api_retention_days`, `history.retention_days`, `uploads.max_file_size_mb`, `uploads.max_rows`
- **Logging** → `logging.app_level`, `logging.console_enabled/level`, `logging.api_enabled/level`, `logging.error_level`, `logging.log_test_runs`
- **Export & Cleanup** → `cleanup.max_age_days` + кнопка «Сохранить настройки»

**Контролы только для текущей сессии (не сохраняются в YAML):**
- **Cache — «Принудительное обновление»** (bypass кэша на текущий запуск)
- **Trends — «Force Refresh»** (bypass кэша Trends)
- **Export — «Автосохранение Excel»**

**В основной панели** (`app.py`):
- **Режим сценария** (`workflow_mode`) — selectbox с 7 режимами: `url_llm` (URL → LLM → Ads), `url_seed` (URL → Идеи Ads), `keyword_seed` (Ключевые → Идеи Ads), `keyword_llm` (Ключевые слова -> LLM SEO текст), `serp_analysis` (SERP Analysis), `crawl_report` (Crawl Report), `google_trends` (Google Trends)
- Загрузка файлов — `.txt`/`.csv` (субъект лимитов `uploads.*`)
- Кнопки chaining/regenerate (Send selected → SERP/Ads/Trends/SEO, «Сгенерировать SEO текст», «Перегенерировать»)

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

1. **Выберите язык интерфейса, LLM-провайдера и модель** в sidebar.
2. **Настройте SERP provider** (Serper, SerpApi, Brave и т.д.) при необходимости.
3. **При необходимости включите SEO Math Analysis** для n-grams, TF-IDF, co-occurrence анализа SERP/контента.
4. **При необходимости включите Crawler** для crawl report workflow (опционально, opt-in).
5. **Выберите `Workflow mode`**:
   - **SERP Analysis** — анализ Google SERP для ключевых слов с organic позициями, PAA и Related Searches
   - **Google Trends** — анализ Google Trends (interest over time, related queries, regional data)
   - **URL -> LLM → Ads** — scraping страницы, извлечение ключей через LLM (с паузой для выбора), затем метрики Google Ads
   - **URL -> Ads ideas** — генерация идей через Google Ads по URL seed
   - **Keyword seed → Ads ideas** — генерация идей из ключевых слов
   - **Ключевые слова -> LLM SEO текст** — генерация SEO-текста напрямую из выбранных ключевых слов
   - **Crawl Report** — математический анализ контента на нескольких страницах с BM25F и signals
6. **Введите данные вручную** или загрузите `.txt` / `.csv`.
7. **Нажмите кнопку запуска анализа**.
8. **Для URL workflows** — SERP/Ads results подсвечивают URL/domain совпадения с source URLs (bold+underline для full URL, bold для domain).
9. **Используйте кнопки chaining** для передачи результатов между SERP, Ads, Trends и SEO там, где это доступно.
10. **Выберите ключевые слова** для генерации SEO-текстов (checkbox selector).
11. **Скачайте результаты в Excel** (с styling для URL matches) или **CSV** (с метаданными).
12. **При необходимости используйте историю** для восстановления checkpoint и повторного использования данных.

## История и хранение данных

- История сохраняется в `data/history.json`.
- История содержит checkpoint, включая данные, нужные для восстановления UI-состояния и продолжения работы.
- **Cache records** (schema version 2): персистентный кэш для всех API запросов и анализа с TTL, force refresh и cache-relevant settings hash
- **Cache visibility toggle**: опциональное отображение cache records в истории (по умолчанию скрыты)
- Старые записи истории удаляются по `history.retention_days`.
- Старые API-логи удаляются по `logging.api_retention_days`.
- Очистка `outputs/`, API-логов и history выполняется на старте приложения.
- Cache-eviction политика основана на TTL и cache hit count
- Cache key включает normalized request параметры, provider, и settings hash (только cache-relevant settings)

Если `retention_days = 0`, автоматическая очистка отключена.

## Google Trends Integration

Google Trends доступен как standalone workflow mode и как optional stage в других workflows:

### Standalone Workflow
1. Выберите режим **Google Trends** в workflow selector
2. Введите ключевые слова вручную или загрузите файл
3. Настройте параметры Trends (geo, timeframe, category)
4. Запустите анализ для получения interest over time, related queries/topics и regional данных

### Optional Stage
После любого keyword-producing workflow step (SERP related searches, Ads ideas, LLM extraction, crawl report):
1. Выберите ключевые слова с помощью checkbox selector
2. Нажмите кнопку **Analyze with Google Trends**
3. Результаты Trends добавятся к текущему workflow

### Trends Caveats
- **Relative values**: все значения относительные (0-100), не абсолютные search volume
- **Anchor rescaling**: опциональная feature для cross-batch comparison; при disabled результаты independent batches не следует сравнивать
- **Rate limiting**: встроенные rate limits и кэширование для избежания 429 errors
- **Cache**: результаты кэшируются на 24 часа (настраивается)

## BM25F и Leak-Inspired Signals

### BM25F Analysis
BM25F (Best Matching 25 with Field weighting) — улучшенная версия BM25 для multi-field документов:

**Formula (BM25+ variant):**
```
IDF = log((N - df + 0.5) / (df + 0.5) + 1)
score = sum(IDF * (tf * (k1 + 1)) / (tf + k1 * ((1 - b) + b * field_len / avg_field_len)) * field_weight)
```

**Field Weights (настраиваемые):**
- SERP title: 3.0
- Page title: 3.0
- H1: 2.5
- Meta description/SERP snippet: 1.5
- Related Searches: 1.2
- People Also Ask: 1.1
- Trends related query/topic: 1.2
- Body text: 1.0
- Anchor text: 1.4

### Leak-Inspired Signals
Детерминистические text signals для SEO analysis:
- **Title alignment**: overlap между title и H1/intro, duplicate title signature risk
- **Content effort score**: word count, list/table counts, citation count, media count
- **Topical centroid overlap**: для crawl/report batches
- **SimHash64**: site-wide top-term fingerprinting с collision detection

## Browser Scraping (OPT-IN)

Browser-based scraping доступен как fallback для Google Trends и SERP когда API unavailable:

### Установка зависимостей
```bash
python -m pip install --upgrade cloakbrowser trafilatura
```

Global user Python option:
```bash
python -m pip install --user --upgrade cloakbrowser trafilatura
```

### Активация
- Установите `scraper.browser_enabled: true` в settings или через sidebar
- If optional browser tools are missing, unknown, or installed but unusable, the sidebar shows the dependency statuses (`Available`, `Missing`, `Installed but unusable`, `Unknown`) and asks which install scope to use: project environment or global user Python.
- Engine is set to `cloakbrowser` for stealth
- Настройте parser (trafilatura)

### Anti-Bot Handling
- Browser engines (Cloakbrowser/Webwright) обрабатывают CAPTCHAs и basic anti-bot
- Rate limiting с configurable delay
- Proxy support (опционально)
- Graceful degradation при CAPTCHA/rate limiting

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
