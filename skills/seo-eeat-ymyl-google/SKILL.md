---
name: seo-eeat-ymyl-google
description: Применяй, когда нужен site-wide аудит по Google Search Quality Rater Guidelines с фокусом на E-E-A-T, YMYL, Page Quality и Needs Met для медицинских, финансовых/transactional и обычных контентных сайтов со scorecard-first output.
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

QRG-first skill для site-wide аудита качества, доверия и риска по Google Search Quality Rater Guidelines 2025.

Основной принцип: сначала hard-gates и доказательства, потом `Page Quality`, потом E-E-A-T scorecard. `Needs Met` оценивается только при наличии query context.

## Когда применять

- Нужен аудит сайта или выборки URL по `E-E-A-T`, `YMYL`, `Page Quality`, `trust`, `reputation`, `harm`.
- Нужно отделить low-trust YMYL/transaction pages от обычных информационных страниц.
- Нужно собрать `scorecard-first` отчет, а не narrative без метрик.
- Нужно быстро повторяемо извлечь on-page сигналы перед ручным judgment.

Не применять как crawl-heavy технический аудит. Для leak/proxy модели, graph scoring и массового краулинга использовать другие skills.

## Discovery-сценарии

- Медицинский сайт: проверка YMYL-рисков, trust-сигналов, автора и review-процесса.
- Финансовый/transactional сайт: проверка safety, прозрачности транзакций и customer-service trust signals.
- Обычный контентный сайт без явного YMYL: проверка полезности, качества контента и базового доверия.

## Ожидаемый вход

- Домен или список URL.
- При наличии: query или query-cluster для `Needs Met`.
- При необходимости: локальные HTML-файлы для выборочной проверки.

## Workflow

1. Определи тип сайта и `YMYL Tier`: `Non-YMYL | Possible YMYL | Clear YMYL`.
2. Собери выборку из 5 URL: homepage, money/service/product, informational, trust/about/contact/author, highest-risk YMYL or transaction.
3. Для webfetch, scraping, внешнего поиска репутации и массового чтения страниц сначала вызывай субагента.
4. Пройди hard-gates: harmful purpose, deceptive purpose/design, scaled low-value content, reputation abuse, hidden/blocked main content, unsafe sensitive-data requests, untrustworthy YMYL claims.
5. При необходимости запусти `scripts/extract_eeat_signals.py`, чтобы получить компактный JSON по страницам.
6. Присвой `Page Quality`: `Lowest | Low | Medium | High | Highest`.
7. Заполни E-E-A-T scorecard: `Experience`, `Expertise`, `Authoritativeness`, `Trustworthiness`, `Overall E-E-A-T`.
8. Если есть query context, отдельно оцени `Needs Met`.
9. Сформируй итоговый отчет по `references/output-contract.md`. При желании используй `scripts/render_scorecard.py` только для prefill шаблона, не для финального judgment.

Обязательные правила:

- `Page Quality` и `Needs Met` не смешивать.
- Если query context отсутствует, для `Needs Met` ставить `N/A`.
- hard-gate findings могут принудительно понижать итог независимо от формального score.
- Явно различать `Experience` и `Expertise`; в high-risk YMYL не подменять формальную компетентность личным опытом.
- `scripts/render_scorecard.py` можно использовать только для prefill и нормализации структуры, но не для автоматического verdicting.

## Что читать

- `references/qrg-page-quality.md`: hard-gates и логика `Page Quality`.
- `references/ymyl-thresholds.md`: `YMYL Tier`, trust requirements, `experience vs expertise`.
- `references/eeat-scorecard-model.md`: rubric для E-E-A-T scoring.
- `references/needs-met-and-intent.md`: когда и как использовать `Needs Met`.
- `references/qrg-metric-catalog.md`: полный metric register, который обязан попасть в отчет.
- `references/output-contract.md`: обязательные секции, формат evidence и wording rules.

## Lite Scripts

`scripts/extract_eeat_signals.py`
- Извлекает on-page сигналы из URL или локальных HTML.
- Возвращает компактный JSON для scorecard prep.

`scripts/render_scorecard.py`
- Рендерит markdown-заготовку отчета и evidence matrix.
- Не принимает окончательные решения вместо агента.

## Правила языка и контекста

- Основной текст skill-а, reference-файлов, шаблонов и отчета писать на русском.
- Английские термины использовать только как стандартные метки: `E-E-A-T`, `YMYL`, `Page Quality`, `Needs Met`, `Lowest`, `Highest`, `Person schema`.
- Не делать bilingual-дубли.
- Длинные scraping/webfetch/reputation-heavy этапы отдавать субагенту; основной агент получает только сжатую сводку, extracted signals и findings.
- Локально оставлять decision-making, scorecard сборку и финальный report synthesis.
