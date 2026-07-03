---
name: google-ads-search-terms
description: |
  Export and analyze search terms that triggered ads in Google Ads account.
  Includes sync and batch modes with cache/resume support.
  Triggers: google ads search terms, search term view, gaql search terms,
  поисковые запросы google ads, анализ запросов рекламы, search term report.
---

# google-ads-search-terms

Analyze paid search terms from Google Ads account data.

## Scope

- Uses GAQL `search_term_view` via Google Ads API (REST).
- Supports sync query mode and batch mode with resume cache.
- Does **NOT** fetch organic Google SERP.
- Analyzes **search queries from your ad account** — real terms that triggered your ads.

## Using seos-cli in this skill

Adoption decision: `seos-cli` is optional. Use this skill's copied GAQL scripts to export real Google Ads search terms. Use `seos-cli` only after terms are exported or otherwise prepared as one term per line and the task needs downstream project enrichment.

Useful enrichment command:

```powershell
seos-cli config check
seos-cli run --from-file search_terms.txt --steps ads,serp,trends,merge,export --format xlsx --out outputs/search-terms-enriched.xlsx
```

Input requirement: `search_terms.txt` must be UTF-8 text with one search term per line. `seos-cli` does not directly parse arbitrary Google Ads search-term CSV schemas in this adoption pass.

Do not use `seos-cli` for the primary search-term export, campaign/date filtering, GAQL troubleshooting, or batch resume. Those remain owned by this skill's scripts until a direct CSV ingestion feature is implemented.

## Config

Prefer the project-level Google Ads configuration verified by `seos-cli config check`.
Standalone copied scripts can still read `config/.env` for local debugging, but do not store real credentials in the copied skill package or commit them.

## Workflow

### STOP! Before any analysis

1. **ASK user about date range:**

   ```text
   "За какой период выгрузить поисковые запросы?
   - Последние 30 дней (по умолчанию)
   - Конкретный диапазон (какой?)"
   ```

2. **ASK about campaign scope:**

   ```text
   "Все кампании или конкретные?
   Если конкретные — укажите ID или названия."
   ```

### After getting answers

1. Auth/access check:

```bash
bash scripts/auth_check.sh
# Windows
.\scripts\auth_check.ps1
```

1. Find geo targets (if needed):

```bash
bash scripts/geo_lookup.sh --query "Moscow" --country-code RU
# Windows
.\scripts\geo_lookup.ps1 -Query "Moscow" -CountryCode RU
```

1. Sync export:

```bash
bash scripts/search_terms_sync.sh \
  --date-from 2026-01-01 --date-to 2026-01-31 \
  --min-impressions 10 --limit 1000 --csv export.csv
# Windows
.\scripts\search_terms_sync.ps1 -DateFrom 2026-01-01 -DateTo 2026-01-31 `
  -MinImpressions 10 -Limit 1000 -Csv export.csv
```

1. Batch by date chunks with all campaigns:

```bash
bash scripts/search_terms_batch.sh \
  --date-from 2026-01-01 --date-to 2026-02-15 \
  --step-days 7 --all-campaigns --csv full_export.csv
# Windows
.\scripts\search_terms_batch.ps1 -DateFrom 2026-01-01 -DateTo 2026-02-15 `
  -StepDays 7 -AllCampaigns -Csv full_export.csv
```

1. Batch by specific campaigns:

```bash
bash scripts/search_terms_batch.sh \
  --date-from 2026-01-01 --date-to 2026-02-15 \
  --step-days 7 --campaign-ids 111,222
# Windows
.\scripts\search_terms_batch.ps1 -DateFrom 2026-01-01 -DateTo 2026-02-15 `
  -StepDays 7 -CampaignIds 111,222
```

1. Resume unfinished batch:

```bash
bash scripts/search_terms_batch.sh --resume --csv export.csv
# Windows
.\scripts\search_terms_batch.ps1 -Resume -Csv export.csv
```

## Scripts

Each script has a Bash (`.sh`) and PowerShell (`.ps1`) version.

### Bash (Linux/macOS)

- `scripts/common.sh` — shared OAuth/token/API helpers.
- `scripts/auth_check.sh` — auth and API smoke check.
- `scripts/search_terms_sync.sh` — one GAQL export call.
- `scripts/search_terms_batch.sh` — chunked execution with cache/resume.
- `scripts/geo_lookup.sh` — geo_target_constant lookup via GAQL.

### PowerShell (Windows)

- `scripts/common.ps1` — shared OAuth/token/API helpers (Invoke-RestMethod).
- `scripts/auth_check.ps1` — auth and API smoke check.
- `scripts/search_terms_sync.ps1` — one GAQL export call.
- `scripts/search_terms_batch.ps1` — chunked execution with cache/resume.
- `scripts/geo_lookup.ps1` — geo_target_constant lookup via GAQL.

Cache layout:

- `cache/results/*.json` — result sets.
- `cache/ops/*.json` — operation states (`pending`, `done`, `error`).

## Output fields

Rows contain:

- `search_term`
- `campaign` / `campaign_id`
- `ad_group` / `ad_group_id`
- `impressions`
- `clicks`
- `cost_micros`
- `conversions`
- `status`

## Notes

- `GOOGLE_ADS_API_VERSION` defaults to `v22`.
- For MCC, set `GOOGLE_ADS_LOGIN_CUSTOMER_ID`.
- Old Yandex script names are kept as compatibility wrappers.
- `--csv` exports UTF-8 with BOM, semicolon-delimited (for Russian Excel).
- **Windows**: PowerShell может блокировать запуск `.ps1` скриптов по умолчанию. Выполните один раз:

  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

## Example Session

```text
User: Покажи поисковые запросы за январь по всем кампаниям

Claude: Проверяю доступ к аккаунту...
        bash scripts/auth_check.sh
        → Auth check completed successfully.

        Выгружаю все поисковые запросы за январь...
        bash scripts/search_terms_batch.sh \
          --date-from 2026-01-01 --date-to 2026-01-31 \
          --all-campaigns --step-days 7 --csv january_terms.csv

        Готово! Найдено 1247 запросов.

        Топ по показам:
        | # | Запрос | Кампания | Показы | Клики | Стоимость |
        |---|--------|----------|--------|-------|-----------|
        | 1 | купить дымоход | Brand | 580 | 45 | 12500000 |
        | 2 | сэндвич дымоход цена | Generic | 340 | 28 | 8900000 |
        | 3 | дымоход для бани | Seasonal | 290 | 22 | 6700000 |

        ❌ Нерелевантные запросы (рекомендую добавить в минус-слова):
        - "чистка дымохода" — сервисный запрос
        - "дымоход своими руками" — DIY

        Полная выгрузка сохранена: january_terms.csv
```

### Key Points

1. **ВСЕГДА спрашивай период и жди ответа**
2. **ВСЕГДА уточняй scope кампаний**
3. **Анализируй нерелевантные запросы и предлагай минус-слова**
4. **Используй `--csv` для экспорта данных**
