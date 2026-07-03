# LEAK Action Plan

- Site: {{site_url}}
- Generated: {{generated_at}}

## Prioritized Actions
{{actions_section}}

## Next Data To Add
{{missing_data_section}}

## 30-60-90 Plan

### First 30 Days
{{plan_30}}

### Days 31-60
{{plan_60}}

### Days 61-90
{{plan_90}}

## Non-Observable Leak Metrics (Guidance)

Some leaked/internal attributes cannot be measured directly from crawling and typical GSC/GA4 exports. Treat them as a “do/don’t” checklist:

- `site2vecEmbeddingEncoded`: maintain strict topical focus; avoid unrelated content expansion.
- `navDemotion`: reduce pogo-sticking risk with answer-first UX; avoid clickbait and intrusive UI.
- `docImages`: add proprietary visuals and evidence; avoid stock-only and duplicated media.
- `babyPandaDemotion`: remove thin/duplicate content patterns; avoid mass templated pages.
- `titlematchScore`: keep title/H1/intro aligned to intent; avoid bait-and-switch and title duplication.
- `hostAge`: keep domain stable and build trust over time; avoid churn and “reset” tactics.
