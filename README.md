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
CHANGE_SUMMARY: Added English translation of the README; Russian original preserved as README_RU.md.
-->

> **English version.** [Русская версия](README_RU.md)

A Streamlit application for collecting search semantics, pulling keyword ideas from Google Ads, and generating SEO-optimized texts from a URL or a keyword seed.

## Features

### Workflow modes

- **SERP Analysis** — analyze the Google SERP for a set of keywords, including positions, PAA (People Also Ask), and Related Searches
- **Google Trends** — analyze Google Trends with interest over time, related queries/topics, and regional data (standalone mode or as an optional stage)
- **URL -> LLM -> Ads** — scrape a page, extract keywords via an LLM, then pull Google Ads metrics with keyword selection
- **URL -> Ads ideas** — generate keyword ideas directly from a URL seed via Google Ads
- **Keyword seed -> Ads ideas** — generate keyword ideas from a manual keyword list via Google Ads
- **Keywords -> LLM SEO Text** — generate SEO text directly from selected keywords with language control
- **Crawl Report** — mathematical content analysis across multiple pages with keyword extraction, BM25F, and leak-inspired signals

### Core capabilities

- **SERP Analysis**: a multi-provider client with adapters for Serper, SerpApi, Brave, Zenserp, SearchApi.io, ScraperAPI, DataForSEO, and Serpstat
- **Context-aware chaining**: selected keywords and results can be handed off to SERP, Ads, Trends, and SEO from URL and keyword-driven workflows
- **Mathematical SEO**:
  - **BM25F scoring**: field-weighted BM25F analysis with configurable field weights (title, H1, snippet, body, anchor text)
  - **BM25+ formula**: the BM25+ variant is used, with IDF smoothing (`+1` to prevent negative values)
  - **Leak-inspired signals**: title alignment, content-effort score, topical overlap, SimHash64 fingerprinting
  - **Traditional metrics**: n-grams (1-3), TF-IDF, co-occurrence (with Jaccard similarity), intent analysis, and content gaps for both SERP and scraped content
- **SEO text generation**: generate SEO-optimized text with quality scoring and regeneration support
- **Source context propagation**: URL workflows carry the `source_url` through the entire pipeline for SERP match highlighting
- **SERP match highlighting**: the UI and Excel exports highlight URL/domain matches from the source URLs
- **SERP rank enrichment**: Google Ads tables are extended with `Page URL in SERP` and `SERP Rank` columns
- **Bidirectional SERP↔Ads merge**: when both a Google Ads table and a SERP analysis exist for the same keywords (in either order), the Ads table is widened with three per-keyword SERP columns — `SERP #results`, `SERP top position`, and `SERP top3 domains` (the top three distinct ranking domains). The merge fires automatically as a side effect of **Send to SERP** whenever both datasets are present, regardless of which ran first, and exports as one file
- **Bidirectional Ads↔Trends merge**: likewise, when both a Google Ads table and Google Trends averages exist, the Ads table is widened with `Trends Avg Interest`, `Trends Geo`, and `Trends Timeframe`. After **Send to Trends**, both the raw Trends averages table and the merged Ads table are shown; the merge works in either run order and exports as one file
- **URL LLM staged extraction**: the URL → LLM workflow always pauses for keyword selection before any downstream actions
- **Prompt content injection**: optional `{content}` substitution (scraped page text) into the SEO prompt, capped at 5000 characters
- **History-backed cache**: a persistent cache for all API requests and analysis, with TTL, force-refresh, and a cache-relevant settings hash
- **Google Trends integration**:
  - A standalone workflow mode for Google Trends analysis
  - An optional stage after any keyword-producing workflow step
  - Interest over time, related queries, related topics, and regional data
  - Relative 0-100 values with optional anchor rescaling
  - Rate limiting and caching to avoid 429 errors
- **OPT-IN browser scraping**: an optional browser-based fallback for Google Trends and SERP (requires extra dependencies)
- **Export**: Excel with styling for URL matches, CSV with metadata, including BM25F/signal/Trends/cache metadata
- **Merged report export**: a combined Excel report with Summary, SERP Analysis, Ads Data, and Math Analysis sheets. (Distinct from the per-keyword SERP↔Ads and Ads↔Trends column merges above, which widen a single Ads table rather than bundling separate sheets.)
- **History**: checkpoint-based history with state restoration
- **Retention policies**: configurable retention for API logs and history
- **File upload limits**: `.txt` and `.csv` with configurable size and row limits
- **URL safety**: internal/private/loopback endpoints are blocked from scraping

## Installation

1. Navigate to the project folder:

   ```bash
   cd auto-seo-keyword-planner
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   The refreshed console UI dependencies include `streamlit-shadcn-ui` and `streamlit-extras`; both packages are included in the pinned requirements list above for the refreshed UI toolkit.

4. Configure the environment variables:
   - Copy `.env.example` to `.env`
   - Fill in at least one LLM provider key:
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
   - If you need SERP results, fill in at least one SERP API key:
     - `SERPER_API_KEY` (Google via Serper)
     - `SERPAPI_KEY` (SerpApi)
     - `BRAVE_SEARCH_API_KEY` (Brave Search)
     - `ZENSERP_KEY` (Zenserp)
     - `SEARCHAPI_IO_KEY` (SearchApi.io)
     - `SCRAPERAPI_KEY` (ScraperAPI)
     - `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD` (DataForSEO)
     - `SERPSTAT_TOKEN` (Serpstat)
   - If you need Google Ads metrics, fill in:
     - `GOOGLE_ADS_DEVELOPER_TOKEN`
     - `GOOGLE_ADS_CUSTOMER_ID`
     - `GOOGLE_ADS_LOGIN_CUSTOMER_ID`
     - `GOOGLE_ADS_CLIENT_ID`
     - `GOOGLE_ADS_CLIENT_SECRET`
     - `GOOGLE_ADS_REFRESH_TOKEN`

**Optional: Browser Scraping (OPT-IN)**
To use the browser-based scraping fallback for Google Trends and SERP:
- Install the extra dependencies:
  ```bash
  python -m pip install --upgrade cloakbrowser trafilatura
  ```
  Global user Python option:
  ```bash
  python -m pip install --user --upgrade cloakbrowser trafilatura
  ```
  The sidebar checks `cloakbrowser` and `trafilatura`. If a tool is missing or installed but does not expose the expected API, the workflow shows a status table and asks whether to use the project-environment install command or the global user Python command.
- Set `scraper.browser_enabled: true` in `config/settings.yaml` or via the sidebar
- Browser scraping is off by default and is not required for the base functionality

## Configuration

The app is configured in three ways. **Precedence:** environment variables (`.env`) > `config/settings.yaml` > code defaults. The `settings.yaml` parameters are mirrored in the app sidebar — the **"Save settings"** button writes changes back to the YAML.

| Source | Purpose |
|---|---|
| `.env` | API keys, OAuth credentials, endpoint overrides, behavior flags |
| `config/settings.yaml` | All logic: retry, LLM, SERP, SEO Math, Crawler, Cache, Trends, Browser Scraper, cleanup/logging/storage |
| Sidebar (UI) | Editable layer over `settings.yaml`; a few toggles are session-only |

> Environment variable and key names are case-sensitive. The examples below use the exact spelling from the code — for example `ZENSERP_KEY` (not `ZENSERP_API_KEY`), `SERPSTAT_TOKEN` (not `SERPSTAT_API_KEY`), and `SERPAPI_KEY` as a single word.

---

### A. Environment variables (`.env`)

Loaded via `python-dotenv` (`config/settings.py`, `override=True`) and read at runtime through `os.getenv`/`os.environ.get`. Copy `.env.example` to `.env` and fill in the ones you need.

#### Google Ads — credentials

All required Google Ads credentials are needed to get metrics. Without them the app still works, but metrics are unavailable. `GOOGLE_ADS_REFRESH_TOKEN` is generated via `generate_refresh_token.py`.

| Variable | Description | Values |
|---|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Google Ads API developer token | token string |
| `GOOGLE_ADS_CUSTOMER_ID` | Client account ID (CID) | numeric string, dashes optional (`123-456-7890`) |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | Manager account (MCC) CID | numeric string; optional for direct accounts |
| `GOOGLE_ADS_CLIENT_ID` | OAuth 2.0 Client ID | `*.apps.googleusercontent.com` |
| `GOOGLE_ADS_CLIENT_SECRET` | OAuth 2.0 Client Secret | secret string |
| `GOOGLE_ADS_REFRESH_TOKEN` | OAuth refresh token | token string (`1//...`) |

#### LLM — provider API keys

Keys are read dynamically as `{PROVIDER}_API_KEY`. Only providers with a key set are shown in the sidebar.

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI (`sk-...`) |
| `ANTHROPIC_API_KEY` | Anthropic / Claude (`sk-ant-...`) |
| `GEMINI_API_KEY` | Google Gemini (`AIza...`) |
| `XAI_API_KEY` | xAI / Grok |
| `GROQ_API_KEY` | Groq (`gsk_...`) |
| `DEEPSEEK_API_KEY` | DeepSeek (`sk-...`) |
| `MINIMAX_API_KEY` | MiniMax |
| `MOONSHOT_API_KEY` | Moonshot / Kimi (`sk-...`) |
| `OPENROUTER_API_KEY` | OpenRouter (`sk-or-...`) — default fallback provider |
| `CEREBRAS_API_KEY` | Cerebras |
| `ZAI_API_KEY` | Z.AI / GLM |
| `MISTRAL_API_KEY` | Mistral (shown in the provider list only) |

Keys for **custom providers** (see `llm.custom_providers` below) are read by the env-variable name given in `api_key_env`. Example: the `omniroute` entry uses `OMNIROUTE_API_KEY`.

#### LLM — endpoint overrides (optional)

`{PROVIDER}_BASE_URL` overrides the API address (for Azure, proxies, local servers). An empty value falls back to the provider's official endpoint.

| Variable | Default (from `.env.example`) |
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

#### SERP — provider API keys

Each key maps to a provider in the `utils/serp_client.py` registry (`PROVIDER_REGISTRY`). Only providers with a key set are shown in the sidebar.

| Variable | Provider (id) |
|---|---|
| `SERPER_API_KEY` | Serper.dev (`serper_dev`) |
| `SERPAPI_KEY` | SerpApi (`serpapi`) — also used for Google Trends |
| `BRAVE_SEARCH_API_KEY` | Brave Search (`brave_search`) |
| `SEARCHAPI_IO_KEY` | SearchApi.io (`searchapi_io`) |
| `ZENSERP_KEY` | Zenserp (`zenserp`) |
| `SCRAPERAPI_KEY` | ScraperAPI (`scraperapi`) |
| `DATAFORSEO_LOGIN` + `DATAFORSEO_PASSWORD` | DataForSEO (`dataforseo`) — both required |
| `SERPSTAT_TOKEN` | Serpstat (`serpstat`) |
| `SERPSTACK_KEY` | Serpstack (`serpstack`) |
| `SCALESERP_KEY` | ScaleSERP (`scaleserp`) |
| `VALUESERP_KEY` | ValueSERP (`valueserp`) |

#### Google Trends — optional keys

| Variable | Description |
|---|---|
| `SCRAPEBADGER_KEY` | ScrapeBadger — a generic web-scrape fallback for Trends (sent as `x-api-key`) |

#### Behavior flags

| Variable | Description | Values |
|---|---|---|
| `ALLOW_LOCALHOST_PROVIDERS` | Allows `localhost`/private IPs in custom-provider base URLs (for local LLMs — Ollama, LM Studio, etc.) | truthy: `1`, `true`, `yes` (case-insensitive); anything else = off. Off by default. |

---

### B. `config/settings.yaml` parameters

The main configuration file. Loaded once via `config/settings.py` (`load_config()`); sections are exported as constants (`SERP_CONFIG`, `SEO_MATH_CONFIG`, etc.). Defaults are taken via `.get(key, fallback)` — a missing key does not break startup.

#### `retry`

| Key | Description | Values | Default |
|---|---|---|---|
| `retry.max_attempts` | Max retry attempts for LLM/SERP/Trends | integer ≥ 1 | `3` |
| `retry.delay_seconds` | Base delay between retries (s) | integer ≥ 0 | `4` |
| `retry.backoff_factor` | Exponential backoff multiplier (Trends) | float > 0 | `1.5` |

#### `llm`

| Key | Description | Values | Default |
|---|---|---|---|
| `llm.fallback_provider` | Provider used when the primary one fails | provider id | `openrouter` |
| `llm.fallback_model` | Model used for the fallback | model id | `openrouter/free` |
| `llm.timeout_seconds` | Per-request LLM timeout (s) | integer 10–300 (in UI) | `180` |
| `llm.max_keywords_per_url` | Cap on keywords extracted per URL | integer | `20` |
| `llm.generation_language` | Legacy generation language (fallback) | language string | `Russian` |
| `llm.keyword_llm_generation_language` | SEO generation language in Keyword→LLM | `Russian`/`Ukrainian`/`English`/`German`/`French`/`Spanish`/`Italian`/`Portuguese`/`Polish` | `Ukrainian` |
| `llm.page_type` | Page type for the `{page_type}` placeholder | `product`/`category`/`blog post`/custom string | `product` |
| `llm.delay_between_requests_seconds` | Pause between LLM requests (s) | integer 0–60 (in UI) | `2` |
| `llm.prompts.keyword_extraction` | Keyword-extraction system prompt | multiline; substitutes `{max_keywords}` | (text in YAML) |
| `llm.prompts.seo_description` | SEO generation system prompt | multiline; substitutes `{language}`, `{keywords_list}`, `{content}`, `{page_type}` | (text in YAML) |

**`llm.models`** — default model id per provider:

| provider | model |
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

**`llm.custom_providers`** — a list of user-defined OpenAI-compatible providers. Each object: `name` (id), `display_name`, `base_url`, `api_key_env` (env-var name holding the key). Default is one entry — `omniroute` (`http://localhost:20128/v1`, key `OMNIROUTE_API_KEY`). Managed via the "Custom providers" expander in the sidebar.

#### `keywords`

| Key | Description | Values | Default |
|---|---|---|---|
| `keywords.allowed_languages` | Whitelist of keyword languages | list of 2-letter codes | `[ru, uk]` |
| `keywords.min_keyword_length` | Minimum keyword length (characters) | integer ≥ 1 | `3` |

#### `scraping`

| Key | Description | Values | Default |
|---|---|---|---|
| `scraping.timeout_seconds` | HTTP timeout for the basic `requests` scraper (s) | integer | `30` |
| `scraping.max_urls_per_batch` | Max URLs in one scrape batch | integer | `20` |

#### `google_ads`

| Key | Description | Values | Default |
|---|---|---|---|
| `google_ads.location_id` | Geo-target criterion id | numeric string (`2804` Ukraine, `2643` Russia, `2840` USA, …) | `'2804'` |
| `google_ads.language_id` | Language criterion id | string or list (`1031` RU, `1036` UK, `1000` EN, `1001` DE, `1002` FR, `1003` ES, `1004` IT, `1014` PT, `1015` PL) | `[1031, 1036]` |
| `google_ads.currency_code` | Metric currency (ISO 4217) | `UAH`/`USD`/`EUR` | `UAH` |
| `google_ads.max_keywords_per_request` | Keywords per Keyword Plan request | integer | `1000` |

#### `serp`

| Key | Description | Values | Default |
|---|---|---|---|
| `serp.provider` | Active provider | `serper_dev`/`serpapi`/`brave_search`/`searchapi_io`/`zenserp`/`scraperapi`/`dataforseo`/`serpstat`/`serpstack`/`scaleserp`/`valueserp`/`browser_cloakbrowser` | `browser_cloakbrowser` |
| `serp.num_results` | Number of organic results | integer 1–100 | `10` |
| `serp.gl` | Geolocation (country) | `ua`/`us`/`ru`/`de`/`uk`/`pl` | `ua` |
| `serp.hl` | Google interface language | `uk`/`ru`/`en`/`de`/`pl` | `uk` |
| `serp.timeout_seconds` | Per-request SERP timeout (s) | integer | `30` |
| `serp.device` | Device | `` (not set)/`desktop`/`mobile`/`tablet` | `''` |
| `serp.search_type` | Search type | `web`/`images`/`videos`/`news`/`shopping` | `web` |
| `serp.time_period` | Time period | `any`/`hour`/`day`/`week`/`month`/`year` | `any` |
| `serp.safe_search` | SafeSearch | `off`/`active` | `'off'` |
| `serp.google_domain` | Google domain | `google.com`/`google.co.uk`/`google.de`/`google.fr`/`google.com.ua`/`google.ru`/`google.com.tr`/`google.pl` | `google.com.ua` |
| `serp.location` | Free-text location name (city) | string | `''` |
| `serp.uule` | Encoded UULE signal | base64 string | `''` |

#### `seo_math`

| Key | Description | Values | Default |
|---|---|---|---|
| `seo_math.enabled` | Master switch for the analysis engine | boolean | `true` |
| `seo_math.analyze_ngrams` | N-gram analysis | boolean | `true` |
| `seo_math.analyze_tfidf` | TF-IDF analysis | boolean | `true` |
| `seo_math.analyze_cooccurrence` | Co-occurrence analysis | boolean | `true` |
| `seo_math.analyze_intent` | Intent analysis | boolean | `true` |
| `seo_math.analyze_generation_quality` | Generation-quality scoring | boolean | `true` |
| `seo_math.analyze_generated_text` | Score generated SEO text | boolean | `false` |
| `seo_math.analyze_bm25f` | BM25F field-weighted analysis | boolean | `true` |
| `seo_math.ngram_min` | Minimum n-gram size | integer 1–2 | `1` |
| `seo_math.ngram_max` | Maximum n-gram size | integer 2–4 | `4` |
| `seo_math.top_terms_limit` | How many top terms to consider | integer 10–50 | `50` |
| `seo_math.min_ngram_count` | Minimum n-gram occurrences | integer 1–5 | `2` |
| `seo_math.min_document_frequency` | Minimum document frequency | integer 1–5 | `2` |
| `seo_math.use_related_searches` | Include Related Searches in the corpus | boolean | `true` |
| `seo_math.use_people_also_ask` | Include People Also Ask | boolean | `true` |
| `seo_math.strip_suffixes` | Strip RU/UK suffixes when tokenizing | boolean | `false` |

**`seo_math.bm25f_params`** — BM25+ formula parameters:

| Key | Values | Default |
|---|---|---|
| `k1` | float 0.1–5.0 | `1.2` |
| `b_body` | float 0.0–1.0 | `0.75` |
| `b_title` | float 0.0–1.0 | `0.5` |
| `b_snippet` | float 0.0–1.0 | `0.6` |

**`seo_math.field_weights`** — field weights (float 0.0–10.0):

| field | default | | field | default |
|---|---|---|---|---|
| `serp_title` | 3.0 | | `related_searches` | 1.2 |
| `page_title` | 3.0 | | `people_also_ask` | 1.1 |
| `h1` | 2.5 | | `trends_related` | 1.2 |
| `meta_description` | 1.5 | | `body_text` | 1.0 |
| `serp_snippet` | 1.5 | | `anchor_text` | 1.4 |

**`seo_math.signals`** — leak-inspired signals (all boolean, default `true`): `title_alignment`, `content_effort`, `topical_overlap`, `simhash`.

#### `crawler`

| Key | Description | Values | Default |
|---|---|---|---|
| `crawler.enabled` | Whether the crawler is enabled | boolean | `true` |
| `crawler.max_pages` | Max pages per crawl | integer 1–100 | `1` |
| `crawler.max_depth` | Link-follow depth (0 = seed only) | integer 0–5 | `3` |
| `crawler.same_domain_only` | Same domain only | boolean | `true` |
| `crawler.timeout_seconds` | Overall crawl deadline (s) | integer 10–600 | `120` |
| `crawler.max_response_bytes` | Max bytes per response | integer 1,048,576–52,428,800 | `10485760` |
| `crawler.max_retries` | Extra retries per request | integer 0–2 | `1` |

#### `cache`

| Key | Description | Values | Default |
|---|---|---|---|
| `cache.enabled` | Whether the persistent cache is enabled | boolean | `true` |
| `cache.default_ttl_hours` | Default TTL (hours); actual TTL depends on record kind | integer 1–8760 | `168` |
| `cache.max_cache_records` | Max cache records | integer 100–100000 | `10000` |
| `cache.cache_relevant_subset` | Settings that affect the cache hash | list of dotted paths | (see YAML) |

Effective TTL by record kind: SERP/Ads/Crawl/Math = 168h, LLM extract/generate/model_fetch = 720h, Trends = 24h.

#### `google_trends`

| Key | Description | Values | Default |
|---|---|---|---|
| `google_trends.provider` | Preferred Trends provider | `browser_scraper_trends`/`dataforseo_trends`/`serpapi_trends`/`scrapebadger_web` | `browser_scraper_trends` |
| `google_trends.provider_order` | Fallback order | list of provider ids | `[browser_scraper_trends, dataforseo_trends, serpapi_trends, scrapebadger_web]` |
| `google_trends.show_confidence_metadata` | Show data-confidence metadata | boolean | `true` |
| `google_trends.default_geo` | 2-letter geo code | ISO code (`UA`, `US`, `GB`, `DE`, `PL`, `RU`, …) | `UA` |
| `google_trends.default_timeframe` | Trends timeframe | Trends string (`today 12-m`, `today 5-y`, `today 1-m`, `now 1-h`, …) | `today 12-m` |
| `google_trends.default_category` | Trends category (0 = all) | one of `["", "5", "10", "17", "18", "22", "29", "47", "71", "91", "284", "366"]` → int | `0` |
| `google_trends.default_property` | Vertical (gprop) | ``/`images`/`news`/`youtube`/`froogle` | `''` |
| `google_trends.default_language` | Trends request language | `["", "en","ru","uk","de","fr","es","it","pt","ja","ko","zh"]` | `en-US` |
| `google_trends.default_timezone` | Timezone | `["", "0","1","2","3","-1","-2","-3","-5","-8"]` | `0` |
| `google_trends.cache_ttl_hours` | Trends cache TTL (hours) | integer 1–8760 | `24` |
| `google_trends.max_keywords_per_request` | Max keywords processed by the local browser Trends provider in one run | integer between `max_keywords_per_request_min` and `max_keywords_per_request_max` | `10` |
| `google_trends.max_keywords_per_request_min` | Lower bound for the UI keyword-limit control | integer | `1` |
| `google_trends.max_keywords_per_request_max` | Upper bound for the UI keyword-limit control | integer | `100` |
| `google_trends.batch_delay_seconds` | Pause between batch requests (s) | float | `2` |
| `google_trends.manual_start_wait` | Browser warm-up wait (s) | integer 0–300 | `0` |
| `google_trends.min_delay` | Min random pause between scrapes (s) | integer 1–1800 | `10` |
| `google_trends.max_delay` | Max random pause between scrapes (s) | integer 10–1800 | `60` |
| `google_trends.state_file` | Browser session-state file | filename | `trends_state.json` |
| `google_trends.headless` | Trends browser headless mode | boolean | `false` |

#### `scraper` (browser scraper, OPT-IN)

| Key | Description | Values | Default |
|---|---|---|---|
| `scraper.browser_enabled` | Enable the browser-based scraper | boolean | `true` |
| `scraper.engine` | Browser engine | `cloakbrowser`/`playwright`/`auto` | `cloakbrowser` |
| `scraper.parser` | HTML parser | `trafilatura` | `trafilatura` |
| `scraper.headless` | Headless mode | boolean | `true` |
| `scraper.timeout_seconds` | Navigation timeout (s) | integer | `30` |
| `scraper.retry_on_failure` | Retries on failure | integer | `3` |

#### `cleanup`, `history`, `uploads`, `logging`

| Key | Description | Values | Default |
|---|---|---|---|
| `cleanup.max_age_days` | Age of `outputs/` files to delete (0 = off) | integer 0–365 | `30` |
| `history.retention_days` | History retention (0 = off) | integer 0–365 | `30` |
| `uploads.max_file_size_mb` | Max upload file size (MiB) | integer 1–100 | `5` |
| `uploads.max_rows` | Max rows from an uploaded file | integer 1–100000 | `1000` |
| `logging.app_level` | `app.log` level | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` | `INFO` |
| `logging.console_enabled` | Log to console | boolean | `true` |
| `logging.console_level` | Console log level | level | `INFO` |
| `logging.api_enabled` | Write `api_requests.log` | boolean | `true` |
| `logging.api_level` | API log level | level | `WARNING` |
| `logging.api_retention_days` | API-log retention (0 = off) | integer 0–365 | `30` |
| `logging.error_level` | `errors.log` level | level | `WARNING` |
| `logging.log_test_runs` | Write logs during pytest | boolean | `false` |

#### `ui`

| Key | Description | Values | Default |
|---|---|---|---|
| `ui.language` | Interface language | `ru`/`uk`/`en` | `ru` |
| `ui.provider` | Last selected LLM provider (display name) | string | `Omniroute` |
| `ui.model` | Last selected model | model id | `vertex/gemini-3.1-pro-preview` |
| `ui.max_keywords` | Value of the "max keywords per URL" slider | integer 5–100 | `50` |

---

### C. Sidebar settings (UI)

The sidebar (`components/sidebar.py`) is an editable layer over `config/settings.yaml`. **Every part-B parameter that lists a value range/enumeration is editable from the UI and persisted to YAML by the "Save settings" button.** Below are the panel sections and the controls they own (values are in the tables above).

- **Interface language** → `ui.language`
- **LLM Provider / Model** → `ui.provider`, `ui.model`; the "Max keywords per URL" slider → `ui.max_keywords`; a "Refresh models" button (refreshes the model cache); a "Custom providers" expander → `llm.custom_providers`
- **SERP Provider** → `serp.provider`, `serp.num_results`, `serp.gl`, `serp.hl`, `serp.device`, `serp.search_type`, `serp.time_period`, `serp.safe_search`, `serp.google_domain`, `serp.location`, `serp.uule`
- **SEO Math Analysis** → `seo_math.enabled` and all `analyze_*`, advanced parameters (n-gram, BM25F, field weights, signals)
- **Google Trends** → `google_trends.provider`, `default_geo/timeframe/category/property/language/timezone`, `cache_ttl_hours`, `max_keywords_per_request`, local settings (`manual_start_wait`, `min/max_delay`, `state_file`)
- **Cache** → `cache.enabled`, `cache.default_ttl_hours`, `cache.max_cache_records`
- **Scraper (OPT-IN)** → `scraper.browser_enabled` (shows the cloakbrowser/trafilatura dependency-status table)
- **Crawler** → `crawler.*` (max_pages, max_depth, same_domain_only, timeout, max_response_bytes, max_retries)
- **Google Ads** → `google_ads.location_id`, `google_ads.language_id`, `google_ads.currency_code`
- **API Parameters** → `llm.timeout_seconds`, `llm.delay_between_requests_seconds`, `retry.max_attempts`, `retry.delay_seconds`
- **System Prompts** → `llm.prompts.keyword_extraction`, `llm.prompts.seo_description`, `llm.keyword_llm_generation_language`, `llm.page_type`
- **Storage & Limits** → `logging.api_retention_days`, `history.retention_days`, `uploads.max_file_size_mb`, `uploads.max_rows`
- **Logging** → `logging.app_level`, `logging.console_enabled/level`, `logging.api_enabled/level`, `logging.error_level`, `logging.log_test_runs`
- **Export & Cleanup** → `cleanup.max_age_days` + the "Save settings" button

**Session-only controls (not persisted to YAML):**
- **Cache — "Force refresh"** (bypass cache for the current run)
- **Trends — "Force Refresh"** (bypass the Trends cache)
- **Export — "Auto-save Excel"**

**In the main panel** (`app.py`):
- **Workflow mode** (`workflow_mode`) — a selectbox with 7 modes: `url_llm` (URL → LLM → Ads), `url_seed` (URL → Ads ideas), `keyword_seed` (Keywords → Ads ideas), `keyword_llm` (Keywords → LLM SEO Text), `serp_analysis` (SERP Analysis), `crawl_report` (Crawl Report), `google_trends` (Google Trends)
- File upload — `.txt`/`.csv` (subject to the `uploads.*` limits)
- Chaining/regenerate buttons (Send selected → SERP/Ads/Trends/SEO, "Generate SEO text", "Regenerate")

## Running

### Windows

```bash
run_app.bat
```

`run_app.bat` checks for Python and critical dependencies before launching the app.

### Direct Streamlit launch

```bash
streamlit run app.py
```

The app normally opens at `http://localhost:8501`.

## Usage

1. **Pick the interface language, LLM provider, and model** in the sidebar.
2. **Configure the SERP provider** (Serper, SerpApi, Brave, etc.) as needed.
3. **Optionally enable SEO Math Analysis** for n-grams, TF-IDF, and co-occurrence analysis of SERP/content.
4. **Optionally enable the Crawler** for the crawl-report workflow (optional, opt-in).
5. **Select a `Workflow mode`**:
   - **SERP Analysis** — analyze the Google SERP for keywords, with organic positions, PAA, and Related Searches
   - **Google Trends** — analyze Google Trends (interest over time, related queries, regional data)
   - **URL -> LLM → Ads** — scrape a page, extract keywords via the LLM (with a selection pause), then pull Google Ads metrics
   - **URL -> Ads ideas** — generate ideas via Google Ads from a URL seed
   - **Keyword seed → Ads ideas** — generate ideas from a keyword list
   - **Keywords -> LLM SEO Text** — generate SEO text directly from selected keywords
   - **Crawl Report** — mathematical content analysis across multiple pages with BM25F and signals
6. **Enter data manually** or upload a `.txt` / `.csv`.
7. **Press the run-analysis button.**
8. **For URL workflows** — SERP/Ads results highlight URL/domain matches from the source URLs (bold+underline for a full URL, bold for a domain).
9. **Use the chaining buttons** to pass results between SERP, Ads, Trends, and SEO where available.
10. **Select keywords** for SEO text generation (checkbox selector).
11. **Download the results to Excel** (with styling for URL matches) or **CSV** (with metadata).
12. **Use history** to restore checkpoints and reuse data as needed.

## History and data storage

- History is stored in `data/history.json`.
- History contains checkpoints, including the data needed to restore UI state and resume work.
- **Cache records** (schema version 2): a persistent cache for all API requests and analysis, with TTL, force-refresh, and a cache-relevant settings hash
- **Cache visibility toggle**: optionally show cache records in history (hidden by default)
- Old history entries are removed according to `history.retention_days`.
- Old API logs are removed according to `logging.api_retention_days`.
- Cleanup of `outputs/`, API logs, and history runs at app startup.
- Cache eviction is based on TTL and cache-hit count
- The cache key includes normalized request parameters, provider, and a settings hash (cache-relevant settings only)

If `retention_days = 0`, automatic cleanup is disabled.

## Google Trends integration

Google Trends is available as a standalone workflow mode and as an optional stage in other workflows:

### Standalone workflow
1. Select **Google Trends** in the workflow selector
2. Enter keywords manually or upload a file
3. Configure the Trends parameters (geo, timeframe, category)
4. Run the analysis to get interest over time, related queries/topics, and regional data

### Optional stage
After any keyword-producing workflow step (SERP related searches, Ads ideas, LLM extraction, crawl report):
1. Select keywords with the checkbox selector
2. Press the **Analyze with Google Trends** button
3. Trends results are appended to the current workflow

### Trends caveats
- **Relative values**: all values are relative (0-100), not absolute search volume
- **Anchor rescaling**: an optional feature for cross-batch comparison; when disabled, results from independent batches should not be compared
- **Rate limiting**: built-in rate limits and caching to avoid 429 errors
- **Cache**: results are cached for 24 hours (configurable)

## BM25F and Leak-Inspired Signals

### BM25F Analysis
BM25F (Best Matching 25 with Field weighting) is an improved version of BM25 for multi-field documents:

**Formula (BM25+ variant):**
```
IDF = log((N - df + 0.5) / (df + 0.5) + 1)
score = sum(IDF * (tf * (k1 + 1)) / (tf + k1 * ((1 - b) + b * field_len / avg_field_len)) * field_weight)
```

**Field weights (configurable):**
- SERP title: 3.0
- Page title: 3.0
- H1: 2.5
- Meta description / SERP snippet: 1.5
- Related Searches: 1.2
- People Also Ask: 1.1
- Trends related query/topic: 1.2
- Body text: 1.0
- Anchor text: 1.4

### Leak-Inspired Signals
Deterministic text signals for SEO analysis:
- **Title alignment**: overlap between the title and H1/intro; duplicate-title signature risk
- **Content-effort score**: word count, list/table counts, citation count, media count
- **Topical-centroid overlap**: for crawl/report batches
- **SimHash64**: site-wide top-term fingerprinting with collision detection

## Browser Scraping (OPT-IN)

Browser-based scraping is available as a fallback for Google Trends and SERP when an API is unavailable:

### Installing dependencies
```bash
python -m pip install --upgrade cloakbrowser trafilatura
```

Global user Python option:
```bash
python -m pip install --user --upgrade cloakbrowser trafilatura
```

### Activation
- Set `scraper.browser_enabled: true` in settings or via the sidebar
- If optional browser tools are missing, unknown, or installed but unusable, the sidebar shows the dependency statuses (`Available`, `Missing`, `Installed but unusable`, `Unknown`) and asks which install scope to use: project environment or global user Python.
- The engine is set to `cloakbrowser` for stealth
- Configure the parser (trafilatura)

### Anti-bot handling
- Browser engines (Cloakbrowser/Webwright) handle CAPTCHAs and basic anti-bot measures
- Rate limiting with a configurable delay
- Proxy support (optional)
- Graceful degradation on CAPTCHA/rate limiting

## Upload limits

- `.txt` and `.csv` files are supported.
- The maximum file size is set via `uploads.max_file_size_mb`.
- The maximum number of rows is set via `uploads.max_rows`.
- When limits are exceeded, the file is rejected before the workflow runs.

## Logging

The app writes several logs:

- `logs/app.log`: general app-operation info
- `logs/api_requests.log`: API requests and service debug info
- `logs/errors.log`: errors

Logging is controlled via `logging.*` in `config/settings.yaml` and via the sidebar.

## Helper scripts

| File | Purpose |
|---|---|
| `run_app.bat` | Dependency check and app launch |
| `run_tests.bat` | Run the tests |
| `generate_refresh_token.bat` | Generate an OAuth2 refresh token for the Google Ads API |
| `generate_refresh_token.py` | CLI script that generates a refresh token |

On success, `generate_refresh_token.py` offers to write the token to `.env`. If you decline, the token is printed once for manual copying.

## Scraping safety

- Only `http` and `https` are allowed.
- Private, loopback, localhost, link-local, and other internal endpoints are blocked.
- Redirect targets go through the same safety check.

## Tests

```bash
run_tests.bat
```

Or:

```bash
python -m pytest tests -q
```

## More

- Google Ads API setup guide: [GOOGLE_ADS_SETUP.md](GOOGLE_ADS_SETUP.md)
- Example environment variables: [`.env.example`](.env.example)
