# seo-google-leak-deep-audit

## seos-cli adoption

`seos-cli` is optional and not used for the core audit by default. This skill already owns bounded crawling, proxy metric extraction, GSC/GA4 imports, RDAP host age, Playwright visual checks, reports, and action plans through its own scripts.

Use `seos-cli` only when supplemental project-native scrape, SERP, or Trends exports are useful outside the core leak-audit pipeline:

```powershell
seos-cli config check
seos-cli scrape --urls https://example.com/page --format json --out outputs/leak-audit-scrape.json
seos-cli serp --keywords "target query" --format xlsx --out outputs/leak-audit-serp.xlsx
seos-cli trends --keywords "target keyword, competitor keyword" --format xlsx --out outputs/leak-audit-trends.xlsx
```

Do not replace `scripts\leak_audit.py` with `seos-cli`. The CLI does not compute leak-specific proxy metrics or generate this skill's final report/action-plan structure.

Прокси‑SEO аудит сайта по мотивам утечки Google (Content Warehouse API) и модели пайплайна ранжирования **Mustang → Twiddlers → NavBoost**.

Инструмент **не** вычисляет “реальные внутренние метрики Google” — он считает **наблюдаемые прокси‑сигналы**, показывает **evidence URL**, помечает **confidence** и строит **action plan**.

## Что делает

- Безопасно краулит сайт (bounded crawl: лимит страниц, задержка, trap‑фильтры, опционально robots.txt).
- Извлекает on‑page сигналы (контент/структура/ссылки/schema/автор/даты/UI‑хинты).
- Считает **12 структурных проверок** (severity + stage + evidence + fix steps).
- Генерирует:
  - `reports/LEAK-AUDIT-REPORT.md`
  - `reports/LEAK-ACTION-PLAN.md`
- Опционально усиливает NavBoost‑часть, если вы дадите выгрузки:
  - GSC (Pages / Queries / Time-series)
  - GA4 (Pages / Traffic / Scroll)
- Опционально запускает Playwright‑проверки для mobile/UI (оверлеи, горизонтальный скролл, heavy JS, interstitial hints).

## Результаты (файлы)

- `reports/LEAK-AUDIT-REPORT.md` — основной отчёт (метрики, coverage, checks, NavBoost panel).
- `reports/LEAK-ACTION-PLAN.md` — приоритизированный план 30‑60‑90 + “какие данные добавить”.
- `cache/crawl.jsonl` — построчный JSONL со всеми извлечёнными сигналами по страницам.
- `cache/external.json` — нормализованные внешние импорты (GSC/GA4), если переданы.
- `cache/visual.json` — результат Playwright mobile/UI проверок.
- `cache/analysis.json` — все агрегаты: proxy metrics, coverage matrix, checks, growth mapping.

## Установка

Требования: **Python 3.10+** и `pip`.

### Вариант A: venv (рекомендуется)

```powershell
cd D:\Projects\auto-seo-keyword-planner\skills\seo-google-leak-deep-audit
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Playwright (опционально, но рекомендуется для mobile/UI):

```powershell
python -m playwright install chromium
```

### Вариант B: глобальная установка (Windows)

Если вы сознательно ставите зависимости в системный Python:

```powershell
.\install-deps-global.bat
```

## Запуск

Минимальный запуск:

```powershell
python scripts\leak_audit.py https://example.com
```

Smoke‑проверка (быстро, чтобы увидеть формат отчёта):

```powershell
python scripts\leak_audit.py https://example.com --max-pages 30
```

Рекомендованный запуск (лимит + robots + sitemap + Playwright auto):

```powershell
python scripts\leak_audit.py https://example.com `
  --max-pages 300 `
  --delay-ms 200 `
  --respect-robots true `
  --sitemap "https://example.com/sitemap.xml" `
  --use-playwright auto
```

Отключить Playwright:

```powershell
python scripts\leak_audit.py https://example.com --use-playwright false
```

Включить анализ `noindex` (по умолчанию `noindex` страницы не участвуют в 12 checks, но попадают в отдельный блок отчёта):

```powershell
python scripts\leak_audit.py https://example.com --include-noindex true
```

## Внешние данные (опционально, но сильно повышают ценность NavBoost части)

### 1) GSC Pages (`--gsc-pages`)

Где: Google Search Console → **Performance** → **Search results** → вкладка **Pages** → Export CSV.  
Нужные колонки: URL/Page + `Clicks`, `Impressions`, `CTR`, `Position`.

### 2) GSC Queries (`--gsc-queries`)

Там же → вкладка **Queries** → Export CSV.  
Нужные колонки: Query + (желательно) `Clicks`, `Impressions`, `CTR`, `Position`.

### 3) GA4 Pages (`--ga4`)

GA4 → Reports → Engagement → Pages and screens → Export CSV.  
Нужные колонки: `Page location`/`Page path` + `Views`, `Users`, `Engagement rate`, `Average engagement time`, `Bounce rate` (если доступно).

### 4) GSC Time-series (`--gsc-timeseries`)

GSC Performance отчёт с измерениями **Date + Page** (экспорт CSV).  
Нужные колонки: `Date,Page,Clicks,Impressions,CTR,Position`.  
Используется для COEC и списка “serp demotion candidates”.

### 5) GA4 Traffic (`--ga4-traffic`)

GA4 выгрузка по страницам с `Sessions` и `Direct Sessions`.  
Используется для прокси `directUrlVisits`.

### 6) GA4 Scroll (`--ga4-scroll`)

GA4 выгрузка по страницам для события `scroll`: `Scroll Events` и `Users`.  
Используется для прокси `scrollDepth`.

### 7) RDAP domain age (automatic)

`hostAge` now resolves automatically from the domain in the audit target URL.

- Source: `https://rdap.org/domain/<domain>`
- Stored in `cache/external.json -> rdap_whois`
- Reported in `analysis.json -> proxy_metrics` as `hostAge_proxy_years` and `hostAge_proxy_days`
- Reflected in `Metric Coverage Matrix` as implemented when the RDAP response includes a registration event

Пример запуска со всеми источниками:

```powershell
python scripts\leak_audit.py https://example.com `
  --gsc-pages "D:\data\gsc_pages.csv" `
  --gsc-queries "D:\data\gsc_queries.csv" `
  --ga4 "D:\data\ga4_pages.csv" `
  --gsc-timeseries "D:\data\gsc_timeseries.csv" `
  --ga4-traffic "D:\data\ga4_traffic.csv" `
  --ga4-scroll "D:\data\ga4_scroll.csv"
```

## Как читать отчёт

- **Pipeline Summary** — как распределяются 12 checks по Mustang/Twiddlers/NavBoost и сколько проблем найдено.
- **Data Sources Used** — какие источники реально использовались (crawl/GSC/GA4/Playwright).
- **Proxy Metrics** — агрегированные site‑level прокси (быстрый “пульс”).
- **Metric Coverage Matrix** — какие leaked‑метрики покрыты прокси, какие “missing-data”, какие “unavailable”.
- **Check Results** — 12 проверок: severity, evidence URLs, fix steps.
- **NavBoost Panel** — поведенческие прокси (COEC/scroll/direct + кандидаты на demotion).
- **Growth Point Mapping / Action Plan** — привязка проблем к 7 точкам роста и план действий 30‑60‑90.

## Ограничения v1

- Все метрики — **прокси**, а не внутренние значения Google.
- Без OAuth/API интеграций: только crawl + ваши CSV экспорты.
- Playwright улучшает качество mobile/UI диагностики, но остаётся опциональным.

## Troubleshooting

- Playwright не установлен → используйте `--use-playwright false` или установите `python -m playwright install chromium`.
- CSV “ломается” → сохраните как UTF‑8 (импортеры читают `utf-8-sig`, но лучше избегать экзотических форматов).
- Сайт блокирует краулинг → уменьшите `--max-pages`, увеличьте `--delay-ms`, проверьте `robots.txt` и WAF.
- RDAP не отдал дату регистрации → проверьте, что домен из `site_url` публично резолвится в RDAP и реестр возвращает `registration` event.
