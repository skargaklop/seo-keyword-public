---
name: seo-google-leak-deep-audit
description: SEO-аудит сайта через призму утечки Google Content Warehouse API и логики Mustang -> Twiddlers -> NavBoost. Проверяет 12 структурных ошибок, строит evidence-based отчет и формирует action plan по 7 стратегическим точкам роста.
metadata:
  triggers:
    - "утечка Google"
    - "Content Warehouse API"
    - "Mustang"
    - "Twiddlers"
    - "NavBoost"
    - "siteAuthority"
    - "NSR"
    - "siteRadius"
    - "siteFocusScore"
    - "contentEffort"
    - "clutterScore"
    - "anchorMismatchDemotion"
---

# SEO Google Leak Skill

## Using seos-cli in this skill

Adoption decision: `seos-cli` is optional and not used for the core leak audit by default. This skill's own scripts handle bounded crawling, GSC/GA4 imports, RDAP, visual checks, proxy metric extraction, and leak-specific report generation.

Use `seos-cli` only as supplemental evidence when the audit specifically needs project-native scrape, SERP, or Trends exports outside the core pipeline:

```powershell
seos-cli config check
seos-cli scrape --urls https://example.com/page --format json --out outputs/leak-audit-scrape.json
seos-cli serp --keywords "target query" --format xlsx --out outputs/leak-audit-serp.xlsx
seos-cli trends --keywords "target keyword, competitor keyword" --format xlsx --out outputs/leak-audit-trends.xlsx
```

Do not use `seos-cli` instead of `scripts/leak_audit.py` for crawl limits, proxy checks, GSC/GA4 CSV imports, RDAP host-age data, Playwright visual checks, or final action-plan generation. Do not claim `seos-cli` computes Google leak metrics.

## Перед запуском (обязательные вопросы)

1. Целевой URL и лимит обхода (`--max-pages`, по умолчанию `300`).
2. Целевой язык/языки (или автоопределение).
3. Есть ли CSV-экспорты (какие именно и как получить):
   - GSC Pages
     - Где: Google Search Console -> `Performance` -> `Search results`.
     - Как: `Search type: Web` -> выставить период (рекомендуется `Last 3 months`, минимум 28 дней) -> вкладка `Pages` -> `Export` -> `Download CSV`.
     - Что должно быть в CSV: URL/Page + метрики `Clicks`, `Impressions`, `CTR`, `Position`.
     - Рекомендуемое имя файла: `gsc_pages.csv`.
   - GSC Queries
     - Где: тот же отчет GSC `Performance -> Search results`.
     - Как: оставить тот же период и фильтры, переключиться на вкладку `Queries` -> `Export` -> `Download CSV`.
     - Что должно быть в CSV: Query + (желательно) `Clicks`, `Impressions`, `CTR`, `Position`.
     - Рекомендуемое имя файла: `gsc_queries.csv`.
   - GA4
     - Где: Google Analytics 4 -> `Reports` -> `Engagement` -> `Pages and screens`.
     - Как: выставить тот же период, что и в GSC -> Primary dimension: `Page path + query string and screen class` (или `Page location`) -> `Share this report` / `Export file` -> CSV.
     - Что должно быть в CSV: URL/Page path (`pagePath`/`pageLocation`) + метрики `Views`, `Users`, `Engagement rate`, `Average engagement time`, `Bounce rate` (если доступен).
     - Рекомендуемое имя файла: `ga4_pages.csv`.
   - Перед запуском проверь, что все CSV в UTF-8 и передаются в CLI так:
     - `--gsc-pages "D:/data/gsc_pages.csv" --gsc-queries "D:/data/gsc_queries.csv" --ga4 "D:/data/ga4_pages.csv"`
4. Нужен ли визуальный режим Playwright (`auto|true|false`).
5. Включать ли noindex-страницы в анализ? (`--include-noindex`, по умолчанию `false` — noindex-страницы не участвуют в 12 checks, но всегда отображаются отдельным блоком в отчёте для обнаружения случайного noindex).

## Что делает skill

- Краулит сайт безопасным ограниченным обходом.
- Извлекает прокси-сигналы для Mustang, Twiddlers, NavBoost.
- Считает 12 checks из методологии и дает evidence URL.
- При наличии GSC/GA4 приоритизирует NavBoost-risk страницы.
- Формирует:
  - `reports/LEAK-AUDIT-REPORT.md`
  - `reports/LEAK-ACTION-PLAN.md`
  - `cache/crawl.jsonl`
  - `cache/analysis.json`

## Как запускать

```bash
cd "D:/Projects/auto-seo-keyword-planner/skills/seo-google-leak-deep-audit"
python scripts/leak_audit.py https://example.com ^
  --max-pages 300 ^
  --concurrency 5 ^
  --delay-ms 200 ^
  --respect-robots true ^
  --sitemap "https://example.com/sitemap.xml" ^
  --sitemap "D:/data/sitemap.xml" ^
  --sitemap-page "https://example.com/site-map" ^
  --use-playwright auto ^
  --include-noindex false ^
  --out-dir reports ^
  --cache-dir cache
```

С внешними данными:

```bash
python scripts/leak_audit.py https://example.com ^
  --sitemap "https://example.com/sitemap.xml" ^
  --sitemap-page "https://example.com/site-map" ^
  --gsc-pages "D:/data/gsc_pages.csv" ^
  --gsc-queries "D:/data/gsc_queries.csv" ^
  --ga4 "D:/data/ga4_pages.csv"
```

## Быстрая smoke-проверка

```bash
python scripts/leak_audit.py https://example.com --max-pages 30
```

## Ограничения v1

- Используются proxy metrics, а не реальные внутренние сигналы Google.
- Визуальные проверки требуют установленного Playwright.
- Интеграций с Ahrefs/Semrush API в v1 нет.

## Metric Coverage Expansion Inputs

Additional optional exports are now supported for richer NavBoost and metric coverage:

- `--gsc-timeseries "D:/data/gsc_timeseries.csv"`
  - CSV headers: `Date,Page,Clicks,Impressions,CTR,Position`
  - Export from GSC Performance report with `Date` + `Page` dimensions.
- `--ga4-traffic "D:/data/ga4_traffic.csv"`
  - CSV headers: `Page,Sessions,Direct Sessions`
  - Export from GA4 report filtered by page URL/path.
- `--ga4-scroll "D:/data/ga4_scroll.csv"`
  - CSV headers: `Page,Scroll Events,Users`
  - Export from GA4 events report with `scroll` event counts.

Example:

```bash
python scripts/leak_audit.py https://example.com ^
  --gsc-pages "D:/data/gsc_pages.csv" ^
  --gsc-queries "D:/data/gsc_queries.csv" ^
  --ga4 "D:/data/ga4_pages.csv" ^
  --gsc-timeseries "D:/data/gsc_timeseries.csv" ^
  --ga4-traffic "D:/data/ga4_traffic.csv" ^
  --ga4-scroll "D:/data/ga4_scroll.csv"
```

Report outputs now include:

- Data Sources Used
- Metric Coverage Matrix
- Authority Graph Panel
- NavBoost Panel (COEC + demotion candidates + direct/scroll proxies)

## RDAP / hostAge

- Метрика `hostAge` теперь определяется автоматически по домену из входного `site_url`.
- Источник: RDAP (`https://rdap.org/domain/<domain>`), без хардкода домена в skill или скриптах.
- В `cache/external.json` сохраняется блок `rdap_whois`, если удалось получить `registration` event.
- В `analysis.json -> proxy_metrics` появляются:
  - `hostAge_proxy_years`
  - `hostAge_proxy_days`
- В `Metric Coverage Matrix` метрика `hostAge` получает статус `implemented`, если RDAP вернул дату регистрации.
- Если RDAP недоступен или не отдал `registration` event, `hostAge` остаётся в статусе `missing-data`.
