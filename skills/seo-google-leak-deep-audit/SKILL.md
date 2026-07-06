---
name: seo-google-leak-deep-audit
description: SEO audit of a website through the lens of the Google Content Warehouse API leak and the logic of Mustang -> Twiddlers -> NavBoost. Checks 12 structural errors, builds an evidence-based report, and generates an action plan across 7 strategic growth points.
metadata:
  triggers:
    - "Google leak"
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

## Before running (mandatory questions)

1. Target URL and crawl limit (`--max-pages`, default `300`).
2. Target language/languages (or auto-detection).
3. Are there any CSV exports available (which ones and how to get them):
   - GSC Pages
     - Where: Google Search Console -> `Performance` -> `Search results`.
     - How: `Search type: Web` -> set period (recommended `Last 3 months`, minimum 28 days) -> `Pages` tab -> `Export` -> `Download CSV`.
     - What should be in CSV: URL/Page + metrics `Clicks`, `Impressions`, `CTR`, `Position`.
     - Recommended file name: `gsc_pages.csv`.
   - GSC Queries
     - Where: same GSC report `Performance -> Search results`.
     - How: keep the same period and filters, switch to `Queries` tab -> `Export` -> `Download CSV`.
     - What should be in CSV: Query + (preferably) `Clicks`, `Impressions`, `CTR`, `Position`.
     - Recommended file name: `gsc_queries.csv`.
   - GA4
     - Where: Google Analytics 4 -> `Reports` -> `Engagement` -> `Pages and screens`.
     - How: set the same period as in GSC -> Primary dimension: `Page path + query string and screen class` (or `Page location`) -> `Share this report` / `Export file` -> CSV.
     - What should be in CSV: URL/Page path (`pagePath`/`pageLocation`) + metrics `Views`, `Users`, `Engagement rate`, `Average engagement time`, `Bounce rate` (if available).
     - Recommended file name: `ga4_pages.csv`.
   - Before running, check that all CSVs are in UTF-8 and passed to the CLI like this:
     - `--gsc-pages "D:/data/gsc_pages.csv" --gsc-queries "D:/data/gsc_queries.csv" --ga4 "D:/data/ga4_pages.csv"`
4. Is the Playwright visual mode needed (`auto|true|false`).
5. Include noindex pages in the analysis? (`--include-noindex`, default `false` — noindex pages are not part of the 12 checks, but always appear in a separate block in the report to detect accidental noindex).

## What the skill does

- Crawls the site with a safe, limited traversal.
- Extracts proxy signals for Mustang, Twiddlers, NavBoost.
- Computes 12 checks from the methodology and provides evidence URLs.
- If GSC/GA4 are present, prioritizes NavBoost-risk pages.
- Generates:
  - `reports/LEAK-AUDIT-REPORT.md`
  - `reports/LEAK-ACTION-PLAN.md`
  - `cache/crawl.jsonl`
  - `cache/analysis.json`

## How to run

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

With external data:

```bash
python scripts/leak_audit.py https://example.com ^
  --sitemap "https://example.com/sitemap.xml" ^
  --sitemap-page "https://example.com/site-map" ^
  --gsc-pages "D:/data/gsc_pages.csv" ^
  --gsc-queries "D:/data/gsc_queries.csv" ^
  --ga4 "D:/data/ga4_pages.csv"
```

## Quick smoke-check

```bash
python scripts/leak_audit.py https://example.com --max-pages 30
```

## Limitations v1

- Proxy metrics are used, not real internal Google signals.
- Visual checks require Playwright to be installed.
- There are no integrations with Ahrefs/Semrush API in v1.

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

- The `hostAge` metric is now determined automatically by domain from the input `site_url`.
- Source: RDAP (`https://rdap.org/domain/<domain>`), without hardcoding the domain in the skill or scripts.
- In `cache/external.json`, an `rdap_whois` block is saved if the `registration` event was successfully obtained.
- In `analysis.json -> proxy_metrics`, the following appear:
  - `hostAge_proxy_years`
  - `hostAge_proxy_days`
- In the `Metric Coverage Matrix`, the `hostAge` metric gets the status `implemented` if RDAP returned a registration date.
- If RDAP is unavailable or did not return a `registration` event, `hostAge` remains in the `missing-data` status.
