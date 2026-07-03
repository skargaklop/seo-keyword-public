# LEAK Audit Report

- Site: {{site_url}}
- Generated: {{generated_at}}
- Pages crawled: {{pages_crawled}}
- Checks with issues: {{checks_with_issues}}

## Pipeline Summary

{{pipeline_summary}}

## Data Sources Used

{{data_sources_section}}

## URL Aliases / Duplicates

{{url_aliases_section}}

## Proxy Metrics

{{proxy_metrics}}

## Metric Coverage Matrix

{{metric_coverage_section}}

## Authority Graph Panel

{{authority_graph_section}}

## Noindex Pages

{{noindex_section}}

## Check Results

{{checks_section}}

## NavBoost Panel

{{navboost_section}}

## Growth Point Mapping

{{growth_section}}

## Confidence Notes

This report uses proxy-based diagnostics inspired by leaked/internal attributes.
Confidence grows with richer data (GSC/GA4/Playwright).

## Non-Observable Leak Metrics (Guidance)

The leak references additional internal attributes that cannot be measured directly from crawling and typical GSC/GA4 exports. Use this section as a **risk checklist**:

### `site2vecEmbeddingEncoded` (site-level embedding)
- Meaning: a compressed semantic vector representing the site’s topical identity.
- Do: keep strict topical pillars, prune off-topic clusters, reinforce internal hubs with consistent semantics.
- Avoid: expanding into unrelated niches, mixing intents across templates/categories.

### `navDemotion` (NavBoost demotion)
- Meaning: demotion triggered by poor satisfaction signals (e.g., pogo-sticking / short clicks).
- Do: deliver an answer-first block above the fold, align SERP promise with the first screen, remove friction and intrusive UI.
- Avoid: clickbait titles without fast intent fulfillment, slow pages, interstitials that block content.

### `docImages` (original visuals / media load)
- Meaning: content effort signal tied to original imagery/visual evidence on the document.
- Do: add proprietary photos/diagrams/infographics, real tables, unique screenshots; use captions and meaningful `alt`.
- Avoid: stock-only visuals, repeating the same images across many pages, thin pages without evidence.

### `babyPandaDemotion` (low-quality content demotion)
- Meaning: persistent quality demotion for thin/duplicated/templated content.
- Do: consolidate near-duplicates, raise originality and evidence density, enforce editorial QA.
- Avoid: mass programmatic pages with little unique value, rewritten/duplicated blocks at scale.

### `titlematchScore` (title ↔ intent/content match)
- Meaning: how well the title matches the query intent and on-page content.
- Do: keep title/H1/intro aligned, make the page deliver what the title promises, use unique titles per URL.
- Avoid: bait-and-switch titles, keyword stuffing, duplicated title patterns across pages.

### `hostAge` (host/domain history)
- Meaning: host/domain age & history; young/unstable hosts may face trust constraints (“sandbox”-like behavior).
- Do: maintain domain stability, build a consistent publishing history and brand signals, grow links naturally.
- Avoid: frequent domain changes, aggressive churn, expired-domain “reset” tactics.
