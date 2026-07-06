---
name: google-ads-keyword-planner
description: |
  Keyword research and demand estimation via Google Ads Keyword Plan Idea Service.
  Use for keyword ideas, historical metrics, monthly volume dynamics, geo target lookup, and missed demand analysis.
  Triggers: keyword planner, google ads keywords, search demand, missed demand,
  google keyword research, google semantics, keyword ideas, google search volume, missed demand.
---

# google-ads-keyword-planner

Keyword demand analysis inside Google Ads scope.

## Scope

- Uses official Google Ads API only (REST).
- Works with ad-account data and keyword planning endpoints.
- Does NOT parse organic Google SERP.
- For organic Google SERP analysis, use external tools (SerpAPI, ScaleSerp, etc.).

## Using seos-cli in this skill

Adoption decision: use `seos-cli` for standard project-native keyword reports, and keep this skill's copied Google Ads scripts for low-level Google Ads API operations that the CLI does not expose.

Use `seos-cli` when the task needs repeatable exports, checkpointed project workflow, or combined Ads/SERP/Trends enrichment:

```powershell
seos-cli config check
seos-cli ads --keywords "seed keyword, second seed" --format xlsx --out outputs/google-ads-keyword-plan.xlsx
seos-cli run --keywords "seed keyword" --steps ads,serp,trends,merge,export --format xlsx --out outputs/keyword-plan-enriched.xlsx
```

Inputs: comma-separated seed keywords, or `--from-file` with one keyword per line. Output: XLSX/CSV/JSON report at the explicit `--out` path.

Do not use `seos-cli` for geo-target lookup, token refresh, raw Google Ads troubleshooting, or missed-demand OR-query utilities unless the CLI grows those capabilities later. Do not copy secrets into this skill folder; check project credentials through `seos-cli config check` and keep API keys out of reports.

## Required config

- Prefer the project-level Google Ads configuration verified by `seos-cli config check`.
- Standalone copied scripts can still read `config/.env` for local debugging, but do not store real credentials in the copied skill package or commit them.
- Alternative: `config/google-ads.yaml` for Python SDK (see `config/google-ads.yaml.example`).

## Philosophy

1. **Skepticism to non-target demand** — high search volume doesn't mean quality traffic
2. **Creative semantic expansion** — think like a customer, not a marketer
3. **Always clarify region** — ask user for target geo before analysis
4. **Show data in reports** — include competition, bids, and monthly trends for verification
5. **VERIFY INTENT via web search** — always check what people actually want to buy

## CRITICAL: Intent Verification

**Before marking ANY query as "target", verify intent via WebSearch!**

### The Problem

Query "каолиновая вата для дымохода" looks relevant for chimney seller, but:

- People search this to BUY COTTON WOOL, not chimneys
- They already HAVE a chimney and need insulation material
- This is NOT a target query for chimney sales!

### Verification Process

For every promising query, ASK YOURSELF:

1. **What does the person want to BUY?** (not just "what are they interested in")
2. **Will they buy OUR product from this search?**
3. **Or are they looking for something adjacent/complementary?**

### MANDATORY: Use WebSearch

**Always run WebSearch** to check:

```text
WebSearch: "каолиновая вата для дымохода" что ищут покупатели
```

Look at search results:

- What products are shown?
- What questions do people ask?
- Is this informational or transactional intent?

### Red Flags (likely NOT target)

- Query contains "для [вашего продукта]" — they need ACCESSORY, not your product
- Query about materials/components — they DIY, not buy finished product
- Query has "своими руками", "how to make" — informational, not buying
- Query about repair/maintenance — they already own it

### Examples

| Query                         | Looks like     | Actually           | Target? |
|-------------------------------|----------------|--------------------|---------|
| каолиновая вата для дымохода  | chimney buyer  | cotton wool buyer  | ❌ NO   |
| дымоход купить                | chimney buyer  | chimney buyer      | ✅ YES  |
| утепление дымохода            | chimney buyer  | insulation DIYer   | ❌ NO   |
| дымоход сэндвич цена          | chimney buyer  | chimney buyer      | ✅ YES  |
| потерпевший дтп               | lawyer client  | news reader        | ❌ NO   |
| юрист после дтп                | lawyer client  | lawyer client      | ✅ YES  |

## Workflow

### STOP! Before any analysis

1. **ASK user about region and WAIT for answer:**

   ```text
   "For which region should I analyze the demand?
   - Worldwide / specific country?
   - Specific city (which one?)"
   ```

   **DO NOT CONTINUE until the user answers!**

2. **ASK about business goal:**

   ```text
   "What exactly are you selling/promoting?
   This is important to filter out non-target queries."
   ```

### After getting answers

1. **Find geo target ID:**

```bash
# Linux/macOS
bash scripts/geo_lookup.sh --query "Moscow" --country-code RU
# Windows (PowerShell)
.\scripts\geo_lookup.ps1 -Query "Moscow" -CountryCode RU
```

1. **Validate auth and account access:**

```bash
bash scripts/health_check.sh
# Windows
.\scripts\health_check.ps1
```

1. **Generate keyword ideas:**

```bash
bash scripts/keyword_ideas.sh --seed "buy chimney" --geo-ids 2840 --language-id 1000
# Windows
.\scripts\keyword_ideas.ps1 -Seed "buy chimney" -GeoIds 2840 -LanguageId 1000
```

1. **Get historical metrics for specific keywords:**

```bash
bash scripts/historical_metrics.sh --keywords "buy chimney,sandwich chimney" --geo-ids 2840
# Windows
.\scripts\historical_metrics.ps1 -Keywords "buy chimney,sandwich chimney" -GeoIds 2840
```

1. **Monthly volume dynamics:**

```bash
bash scripts/search_volume.sh --keyword "buy chimney" --geo-ids 2840 --months 12
# Windows
.\scripts\search_volume.ps1 -Keyword "buy chimney" -GeoIds 2840 -Months 12
```

1. **Verify intent via WebSearch** for each promising query

2. **Present results** with target/non-target separation

## Match Types (vs Wordstat Operators)

Google Ads does NOT use Wordstat-style operators (`"кавычки"`, `!точная`, `+стоп`).

Instead, Google Ads uses **Match Types** when creating campaigns:

| Match Type   | Syntax       | Behavior                                     |
|--------------|--------------|----------------------------------------------|
| Broad match  | `keyword`    | Shows ads for related searches               |
| Phrase match | `"keyword"`  | Shows ads for searches including the meaning |
| Exact match  | `[keyword]`  | Shows ads for exact meaning searches         |

> Match types apply to **ad targeting**, not to Keyword Planner research.
> In Keyword Planner API, you submit plain keywords — no operators needed.
> To narrow results, use `--geo-ids` and `--language-id` filters.

## Scripts

Each script has a Bash (`.sh`) and PowerShell (`.ps1`) version.

### Bash (Linux/macOS)

- `scripts/common.sh` — shared OAuth/token/API helpers.
- `scripts/health_check.sh` — auth + API smoke check.
- `scripts/keyword_ideas.sh` — GenerateKeywordIdeas.
- `scripts/historical_metrics.sh` — GenerateKeywordHistoricalMetrics.
- `scripts/search_volume.sh` — monthly volume dynamics (monthlySearchVolumes).
- `scripts/geo_lookup.sh` — geo_target_constant lookup via GAQL.
- `scripts/missed_demand.py` — parser + OR-query utilities + demand estimation.
- `scripts/query_total.sh` — wrapper for `missed_demand.py query-total`.

### PowerShell (Windows)

- `scripts/common.ps1` — shared OAuth/token/API helpers (Invoke-RestMethod).
- `scripts/health_check.ps1` — auth + API smoke check.
- `scripts/keyword_ideas.ps1` — GenerateKeywordIdeas.
- `scripts/historical_metrics.ps1` — GenerateKeywordHistoricalMetrics.
- `scripts/search_volume.ps1` — monthly volume dynamics.
- `scripts/geo_lookup.ps1` — geo_target_constant lookup via GAQL.
- `scripts/query_total.ps1` — wrapper for `missed_demand.py query-total`.

### Missed demand tools

- Parse export: `uv run --script scripts/missed_demand.py parse-export file.csv`
- Build OR query: `uv run --script scripts/missed_demand.py build-query`
- Merge segmentation batches: `uv run --script scripts/missed_demand.py merge-slots`
- Estimate query demand:
  - Bash: `bash scripts/query_total.sh --phrase "(buy|order) chimney" --regions "2840"`
  - PowerShell: `.\scripts\query_total.ps1 -Phrase "(buy|order) chimney" -Regions "2840"`
- Details: [MISSED_DEMAND.md](references/MISSED_DEMAND.md)

## Notes

- `GOOGLE_ADS_API_VERSION` defaults to `v22`.
- For MCC, set `GOOGLE_ADS_LOGIN_CUSTOMER_ID`.
- Old Yandex script names are kept as compatibility wrappers and map to Google Ads scripts.
- **Windows**: PowerShell might block running `.ps1` scripts by default. Run this once:

  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

## Limits

- Google Ads API is free with valid Developer Token + MCC account.
- Rate limits: ~1000 requests/day per customer, ~100 requests/minute.
- Keyword Planner may return limited data for accounts without active campaigns.

## Example Session

```text
User: Find queries for chimney advertising

Claude: For which region should I analyze the demand?
        And please specify — do you sell ready-made chimneys or
        materials for their manufacture/insulation?

User: USA, we sell ready-made sandwich chimneys

Claude: [Finds geo target]
        bash scripts/geo_lookup.sh --query "United States"
        → 2840 | United States | Country

        [Checks access]
        bash scripts/health_check.sh
        → Health check completed successfully.

        [Generates ideas]
        bash scripts/keyword_ideas.sh --seed "buy chimney" --seed "sandwich chimney" --geo-ids 2840 --language-id 1000

        Found queries. Checking intent via web search...

        ✅ TARGET (buying chimneys):
        - "sandwich chimney pipe" — 1200 avg/mo, Competition: HIGH
        - "chimney pipe buy online" — 680 avg/mo, Competition: MEDIUM

        ❌ NON-TARGET (buying something else):
        - "chimney insulation wrap" — looking for insulation, not a chimney
        - "chimney repair near me" — service query, not a purchase
        - "how to install chimney" — DIY, informational query

        [Checks monthly dynamics for target queries]
        bash scripts/search_volume.sh --keyword "sandwich chimney pipe" --geo-ids 2840 --months 12
```

### Key Points

1. **ALWAYS ask for the region and wait for an answer**
2. **ALWAYS clarify what exactly the client is selling**
3. **ALWAYS verify intent via WebSearch**
4. **Separate the report into target/non-target with an explanation**
