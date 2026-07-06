---
name: seo-eeat-ymyl-google
description: Apply when a site-wide audit according to Google Search Quality Rater Guidelines is needed with a focus on E-E-A-T, YMYL, Page Quality, and Needs Met for medical, financial/transactional, and standard content sites with a scorecard-first output.
---

# SEO E-E-A-T YMYL Google

## Using seos-cli in this skill

Adoption decision: `seos-cli` is optional and not used by default. This skill's core work is QRG judgment, hard-gate analysis, E-E-A-T scoring, and evidence-matrix synthesis; `seos-cli` does not perform that reasoning.

Use `seos-cli` only as supplemental evidence collection when project-native page text or SERP evidence would materially help the audit:

```powershell
seos-cli config check
seos-cli scrape --urls https://example.com/page --format json --out outputs/eeat-page-scrape.json
seos-cli serp --keywords "brand query, product query" --format xlsx --out outputs/eeat-serp-evidence.xlsx
```

Do not use `seos-cli` when local HTML, WebFetch, a subagent scrape, reputation research, or `scripts/extract_eeat_signals.py` already provides the evidence needed by this skill. Do not claim `seos-cli` performs E-E-A-T scoring, YMYL classification, Page Quality, Needs Met, or final QRG verdicts.

## Overview

QRG-first skill for site-wide quality, trust, and risk audit according to Google Search Quality Rater Guidelines 2025.

Core principle: hard-gates and evidence first, then `Page Quality`, then E-E-A-T scorecard. `Needs Met` is evaluated only if a query context is available.

## When to apply

- A site audit or URL sample audit is needed for `E-E-A-T`, `YMYL`, `Page Quality`, `trust`, `reputation`, `harm`.
- Need to separate low-trust YMYL/transaction pages from standard informational pages.
- Need to generate a `scorecard-first` report, not a narrative without metrics.
- Need to quickly and repeatedly extract on-page signals before manual judgment.

Do not use as a crawl-heavy technical audit. For leak/proxy models, graph scoring, and massive crawling, use other skills.

## Discovery scenarios

- Medical site: check YMYL-risks, trust-signals, author, and review process.
- Financial/transactional site: check safety, transaction transparency, and customer-service trust signals.
- Standard content site without obvious YMYL: check usefulness, content quality, and basic trust.

## Expected input

- Domain or list of URLs.
- If available: query or query-cluster for `Needs Met`.
- If necessary: local HTML files for selective checking.

## Workflow

1. Determine the site type and `YMYL Tier`: `Non-YMYL | Possible YMYL | Clear YMYL`.
2. Collect a sample of 5 URLs: homepage, money/service/product, informational, trust/about/contact/author, highest-risk YMYL or transaction.
3. For webfetch, scraping, external reputation search, and mass page reading, invoke a subagent first.
4. Pass hard-gates: harmful purpose, deceptive purpose/design, scaled low-value content, reputation abuse, hidden/blocked main content, unsafe sensitive-data requests, untrustworthy YMYL claims.
5. If necessary, run `scripts/extract_eeat_signals.py` to get a compact JSON for the pages.
6. Assign `Page Quality`: `Lowest | Low | Medium | High | Highest`.
7. Fill out the E-E-A-T scorecard: `Experience`, `Expertise`, `Authoritativeness`, `Trustworthiness`, `Overall E-E-A-T`.
8. If there is a query context, evaluate `Needs Met` separately.
9. Generate the final report according to `references/output-contract.md`. If desired, use `scripts/render_scorecard.py` only to prefill the template, not for final judgment.

Mandatory rules:

- Do not mix `Page Quality` and `Needs Met`.
- If query context is missing, set `N/A` for `Needs Met`.
- hard-gate findings can forcefully lower the result regardless of the formal score.
- Explicitly distinguish `Experience` and `Expertise`; in high-risk YMYL, do not substitute formal expertise with personal experience.
- `scripts/render_scorecard.py` can be used only for prefill and structure normalization, but not for automatic verdicting.

## What to read

- `references/qrg-page-quality.md`: hard-gates and `Page Quality` logic.
- `references/ymyl-thresholds.md`: `YMYL Tier`, trust requirements, `experience vs expertise`.
- `references/eeat-scorecard-model.md`: rubric for E-E-A-T scoring.
- `references/needs-met-and-intent.md`: when and how to use `Needs Met`.
- `references/qrg-metric-catalog.md`: full metric register that must be included in the report.
- `references/output-contract.md`: mandatory sections, evidence format, and wording rules.

## Lite Scripts

`scripts/extract_eeat_signals.py`
- Extracts on-page signals from URLs or local HTML.
- Returns a compact JSON for scorecard prep.

`scripts/render_scorecard.py`
- Renders the markdown report template and evidence matrix.
- Does not make final decisions instead of the agent.

## Language and context rules

- Write the main text of the skill, reference files, templates, and report in English.
- Use English terms only as standard labels: `E-E-A-T`, `YMYL`, `Page Quality`, `Needs Met`, `Lowest`, `Highest`, `Person schema`.
- Do not create bilingual duplicates.
- Delegate long scraping/webfetch/reputation-heavy stages to a subagent; the main agent receives only a compressed summary, extracted signals, and findings.
- Keep decision-making, scorecard assembly, and final report synthesis local.
