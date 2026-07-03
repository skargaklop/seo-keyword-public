# seo-eeat-ymyl-google

## seos-cli adoption

`seos-cli` is optional and not used by default for this skill. The core workflow is QRG-first judgment, E-E-A-T/YMYL/Page Quality/Needs Met analysis, scorecard synthesis, and evidence review; the CLI does not perform those verdicts.

Use `seos-cli` only when supplemental project-native page text or SERP evidence is genuinely useful:

```powershell
seos-cli config check
seos-cli scrape --urls https://example.com/page --format json --out outputs/eeat-page-scrape.json
seos-cli serp --keywords "brand query, product query" --format xlsx --out outputs/eeat-serp-evidence.xlsx
```

Skip `seos-cli` when local HTML, WebFetch, reputation research, a scraping subagent, or `scripts/extract_eeat_signals.py` already provides better evidence. Never present CLI output as E-E-A-T scoring or final QRG judgment.

Skill для QRG-first аудита сайтов по `Google Search Quality Rater Guidelines` с фокусом на `E-E-A-T`, `YMYL`, `Page Quality`, `Needs Met`, hard-gates и evidence-first scorecard.

## Что делает skill

- помогает собрать site-wide выборку и пройти QRG workflow;
- извлекает repeatable on-page сигналы из URL или локальных HTML;
- рендерит `scorecard-first` markdown-отчет и опциональную матрицу evidence;
- оставляет финальный judgment за агентом, а не за скриптами.

## Быстрый старт

1. Подготовьте 1 или несколько URL либо локальных HTML-файлов.
2. Запустите extractor:

```powershell
python .\scripts\extract_eeat_signals.py `
  --source "https://example.com/" `
  --source ".\scripts\fixtures\informational-authorship.html" `
  --output ".\tmp\signals.json"
```

3. При необходимости дополните JSON вручную полями для scorecard:
- `site_type`
- `site_type_reason`
- `hard_gate_findings`
- `metrics`
- `metrics.special_flags` можно передавать как одно значение, `N/A` или список флагов
- `page_quality_summary`
- `eeat_explanations`
- `query_context`
- `needs_met_reason`
- `evidence_matrix`
- `priority_actions`

4. Сгенерируйте отчет:

```powershell
python .\scripts\render_scorecard.py `
  --input ".\tmp\signals.json" `
  --output ".\tmp\site-scorecard.md" `
  --evidence-output ".\tmp\page-evidence-matrix.md"
```

5. Проверьте итоговый markdown и внесите финальный human/agent judgment.

## Рекомендуемый рабочий поток

1. Определить тип сайта и `YMYL Tier`.
2. Собрать выборку из 5 ключевых URL.
3. Для scraping/webfetch/reputation-heavy этапов сначала использовать субагента.
4. Пройти hard-gates до выставления оценок.
5. При необходимости прогнать `extract_eeat_signals.py`.
6. Заполнить `Page Quality`, затем `E-E-A-T`, затем `Needs Met` при наличии query context.
7. Собрать финальный отчет по `references/output-contract.md`.

## Полезные файлы

- `SKILL.md` — краткая operational-инструкция для применения skill.
- `references/` — distilled references, rubric и output contract.
- `assets/` — шаблоны итогового отчета.
- `scripts/` — extractor, renderer и fixture-тесты.
- `quick_validate.py` — быстрая проверка структуры, контрактов и smoke-тестов.

## Проверка

```powershell
python .\quick_validate.py
```

Если нужен только быстрый structural check без fixture-тестов:

```powershell
python .\quick_validate.py --skip-fixtures
```

## Ограничения

- Это не crawl engine и не full automation stack.
- Скрипты не должны принимать финальные QRG verdicts вместо агента.
- `Needs Met` не оценивается без query context.
- Narrative без полного metric register считается некорректным output.

## Подробнее для разработчиков

См. `DEVELOPERS.md`.
