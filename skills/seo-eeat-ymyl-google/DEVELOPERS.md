# DEVELOPERS

## Назначение

`seo-eeat-ymyl-google` — skill для site-wide аудита качества и доверия по `Google Search Quality Rater Guidelines`. Его задача не автоматизировать финальный SEO-аудит целиком, а дать:

- компактный operational workflow для агента;
- repeatable extraction on-page signals;
- нормализованный `scorecard-first` output;
- жесткие контракты по evidence, метрикам и структуре отчета.

Главный принцип: сначала evidence и hard-gates, потом `Page Quality`, потом `E-E-A-T`, и только при наличии query context — `Needs Met`.

## Состав skill

- `SKILL.md`
  Короткая инструкция для runtime-применения skill.
- `references/qrg-page-quality.md`
  Логика hard-gates и шкалы `Page Quality`.
- `references/ymyl-thresholds.md`
  Классы `YMYL`, тематические классы и логика `Experience vs Expertise`.
- `references/eeat-scorecard-model.md`
  Практический rubric по `Experience`, `Expertise`, `Authoritativeness`, `Trustworthiness`, `Overall E-E-A-T`.
- `references/needs-met-and-intent.md`
  Когда нужен `Needs Met`, какие бывают intent-ы и как читать шкалу.
- `references/qrg-metric-catalog.md`
  Формальный реестр метрик с `metric_id`, `label`, `allowed_values`, `source_logic`, `required_evidence`, `report_required`.
- `references/output-contract.md`
  Контракт итогового markdown-отчета.
- `assets/site-scorecard-template.md`
  Основной шаблон итогового отчета.
- `assets/page-evidence-matrix-template.md`
  Шаблон отдельного sidecar-файла для evidence matrix.
- `assets/action-plan-template.md`
  Шаблон блока приоритетных действий.
- `scripts/extract_eeat_signals.py`
  Извлекает repeatable сигналы со страниц.
- `scripts/render_scorecard.py`
  Рендерит markdown-отчет из JSON.
- `scripts/fixtures/`
  Smoke-тесты и sample fixtures.
- `quick_validate.py`
  Structural validation + fixture smoke tests.

## Основные рабочие потоки

### Поток 1. Runtime-применение skill агентом

1. Определить тип сайта и `YMYL Tier`.
2. Собрать репрезентативную выборку URL:
- homepage;
- money/service/product page;
- informational page;
- trust/about/contact/author page;
- highest-risk YMYL or transaction page.
3. Для тяжелого `webfetch`, scraping, репутационных проверок и массового чтения страниц использовать субагента.
4. До scoring пройти hard-gates:
- harmful purpose;
- deceptive purpose/design;
- spam или scaled low-value content;
- site reputation abuse;
- hidden/blocked main content;
- unsafe requests for sensitive data;
- untrustworthy YMYL claims.
5. При необходимости прогнать extractor.
6. Заполнить `Page Quality`.
7. Заполнить `E-E-A-T Scorecard`.
8. Только при наличии query context заполнить `Needs Met`.
9. Собрать финальный `scorecard-first` отчет.

### Поток 2. Работа со скриптами

1. Собрать источники: URL или локальные HTML.
2. Запустить `extract_eeat_signals.py`.
3. Получить компактный JSON с `pages` и `site_summary`.
4. Дополнить JSON аналитическими полями, которых extractor не знает сам:
- hard-gates;
- metric values;
- explanations;
- priority actions;
- optional query context.
5. Запустить `render_scorecard.py`.
6. Проверить markdown-отчет и доработать judgment вручную.

### Поток 3. Разработка и изменение skill

1. Изменить references, templates или scripts.
2. Если меняется behavior, сначала обновить/добавить fixture или validation check.
3. Прогнать `python .\quick_validate.py --skip-fixtures`.
4. Прогнать `python .\scripts\fixtures\run_fixture_tests.py`.
5. Прогнать `python .\quick_validate.py`.
6. Только после этого считать изменение готовым.

## Скрипт `extract_eeat_signals.py`

### Назначение

Скрипт извлекает repeatable on-page сигналы из:

- `http/https` URL;
- локальных HTML-файлов.

Он не выносит финальных QRG verdicts и не должен сам решать, какая у страницы итоговая `Page Quality`.

### CLI

```powershell
python .\scripts\extract_eeat_signals.py --source "<url-or-file>" [--source "<url-or-file>"] [--output "<path.json>"]
```

### Вход

- `--source`
  Повторяемый параметр. Принимает URL или путь к HTML-файлу.
- `--output`
  Необязательный путь к JSON. Если не передан, JSON печатается в stdout.

### Внутренние обязанности

- чтение HTML из URL или файла;
- попытка корректно декодировать `utf-8`, `cp1251`, `windows-1251`, `koi8-r`;
- извлечение `title`, `meta description`, `h1-h3`;
- извлечение JSON-LD и author/person signals;
- извлечение organization/service signals;
- подсчет внутренних и внешних ссылок;
- поиск trust pages: `about`, `contact`, `policy`, `terms`, `returns`, `editorial`, `medical_review`, `authors`;
- поиск citation signals;
- поиск media presence;
- поиск content structure signals: списки, таблицы, FAQ-like blocks, answer-first;
- поиск UGC/discussion hints;
- поиск UI-risk hints: overlays, sticky/fixed элементы, misleading CTA, clickbait, spammy phrases;
- эвристическое определение `page_role_hint`.

### Контракт вывода extractor

Корневой JSON содержит:

- `sources: string[]`
- `pages: object[]`
- `site_summary: object`

### Контракт `pages[]`

Каждый page object содержит:

- `url`
- `page_role_hint`
- `title`
- `meta_description`
- `headings`
- `word_count`
- `top_terms`
- `author`
- `organization`
- `links`
- `citations`
- `media`
- `content_structure`
- `ugc`
- `ui_risk_hints`
- `spam_flags`
- `text_excerpt`

### Контракт `author`

- `has_person_schema: bool`
- `author_names: string[]`
- `author_links: string[]`
- `same_as: string[]`
- `credential_hints: string[]`

### Контракт `organization`

- `has_organization_schema: bool`
- `has_service_schema: bool`
- `organization_names: string[]`
- `service_names: string[]`
- `contact_signal_count: number`
- `address_hint: bool`

### Контракт `links`

- `internal_count: number`
- `external_count: number`
- `trust_pages: object`
- `external_examples: object[]`

### Контракт `citations`

- `citation_count: number`
- `external_link_count: number`
- `external_link_examples: object[]`

### Контракт `content_structure`

- `list_count: number`
- `table_count: number`
- `faq_like_sections: number`
- `answer_first: object`
- `year_mentions: number[]`

### Контракт `ugc`

- `has_ugc_discussion: bool`
- `comment_like_blocks: number`
- `unique_comment_author_hints: number`

### Контракт `ui_risk_hints`

- `fixed_elements: number`
- `sticky_elements: number`
- `overlay_keyword_hits: number`
- `misleading_cta_hits: number`
- `clickbait_title: bool`
- `spammy_phrase_hits: number`

### Контракт `spam_flags`

- `spammy_phrase_hits: number`
- `cta_risk_hits: number`
- `clickbait_title: bool`

### Контракт `site_summary`

- `page_count`
- `pages_with_person_schema`
- `pages_with_citations`
- `pages_with_ugc`
- `pages_with_ui_risks`
- `trust_page_coverage`

## Скрипт `render_scorecard.py`

### Назначение

Скрипт рендерит markdown-отчет из JSON-данных и шаблонов. Он:

- нормализует структуру вывода;
- локализует часть narrative-фраз;
- подставляет evidence table и action plan;
- валидирует metric values по `references/qrg-metric-catalog.md`.

Скрипт не должен:

- выставлять hard-gates без входных данных;
- придумывать evidence rows;
- делать silent auto-conclusions beyond provided data;
- заменять финальный аналитический judgment агента.

### CLI

```powershell
python .\scripts\render_scorecard.py `
  --input ".\tmp\signals.json" `
  --output ".\tmp\site-scorecard.md" `
  --evidence-output ".\tmp\page-evidence-matrix.md"
```

### Вход

- `--input`
  JSON для рендера.
- `--output`
  Путь к основному `site-scorecard.md`.
- `--evidence-output`
  Необязательный путь к отдельному `page-evidence-matrix.md`.
- `--template`
  Необязательный override для шаблона отчета.
- `--matrix-template`
  Необязательный override для шаблона evidence matrix.
- `--action-template`
  Необязательный override для шаблона action plan.

### Поддерживаемые формы входного JSON

#### Вариант A. Полный scorecard payload

Если JSON уже содержит `metrics`, скрипт считает, что это scorecard payload, и рендерит его как есть.

Ожидаемые поля:

- `site_type`
- `site_type_reason`
- `ymyl_tier`
- `sampled_urls`
- `hard_gate_findings`
- `metrics`
- `page_quality_summary`
- `eeat_explanations`
- `query_context`
- `needs_met_reason`
- `evidence_matrix`
- `priority_actions`

#### Вариант B. Сырым входом является extractor output

Если `metrics` нет, `build_default_payload()` превращает extractor output в заготовку:

- `sampled_urls` берутся из `pages`;
- большинство аналитических полей остаются пустыми;
- в markdown будут placeholders вместо неуказанных значений.

### Контракт `metrics`

Значения проверяются по `references/qrg-metric-catalog.md`. Для неизвестных или недопустимых значений renderer падает с ошибкой.

Ключевые правила:

- `needs_met` и `special_flags` по умолчанию получают `N/A`;
- остальные метрики по умолчанию получают `Unclear`;
- `overall_eeat` допускает целое значение `0-100`;
- ordinal и binary значения должны точно совпадать со списком `allowed_values`.
- `special_flags` может быть строкой, `N/A` или списком нескольких допустимых флагов; `N/A` нельзя смешивать с другими значениями.

### Контракт `hard_gate_findings`

Каждый finding должен содержать:

- `signal`
- `page_url`
- `observed_evidence`
- `rating_impact`

### Контракт `evidence_matrix`

Каждая строка должна содержать:

- `signal`
- `page_url`
- `observed_evidence`
- `rating_impact`

Если `evidence_matrix` отсутствует или пуст, renderer подставляет placeholder-table и не должен invent evidence rows.

### Контракт `priority_actions`

Поддерживаются ключи:

- `critical` или `Critical`
- `high` или `High`
- `medium` или `Medium`

Пустые списки заменяются placeholder-строками.

## Подробное описание итогового вывода

Главный deliverable — `scorecard-first` markdown-отчет. Narrative без полного metric register считается некорректным output.

### 1. `Тип сайта / YMYL Tier`

Что должно быть:

- краткое описание типа сайта;
- итоговый `YMYL Tier`;
- короткое evidence-based обоснование.

Зачем это нужно:

- зафиксировать risk context;
- понять, насколько жесткими должны быть требования к `Trustworthiness`, формальной `Expertise` и transaction-trust signals.

### 2. `Выборка URL`

Что должно быть:

- список sampled URLs;
- роль каждой страницы в выборке.

Зачем это нужно:

- показать, что аудит охватывает не только homepage;
- отразить trust pages, money pages и high-risk страницы.

### 3. `Hard-Gate Findings`

Что должно быть:

- список подтвержденных hard-gate находок;
- для каждой: сигнал, URL, observed evidence, rating impact.

Зачем это нужно:

- hard-gates могут принудительно понизить итоговый результат;
- здесь нельзя писать догадки без evidence.

### 4. `Реестр QRG-метрик`

Что должно быть:

- полный перечень всех метрик из `references/qrg-metric-catalog.md`;
- явное значение для каждой метрики;
- `Unclear` или `N/A`, если данных не хватает.

Зачем это нужно:

- skill задуман как scorecard-first, а не prose-only аудит;
- это основной машинно- и человеко-читаемый реестр результата.

### 5. `Сводка по Page Quality`

Что должно быть:

- итоговая оценка `Page Quality`;
- короткие reasons, почему оценка именно такая.

Зачем это нужно:

- отделить summary-вердикт по качеству страницы от полного реестра метрик;
- зафиксировать основные driver-ы оценки.

### 6. `E-E-A-T Scorecard`

Что должно быть:

- `Experience`
- `Expertise`
- `Authoritativeness`
- `Trustworthiness`
- `Overall E-E-A-T`

Для каждого значения должно быть краткое пояснение, на чем оно основано.

Зачем это нужно:

- держать компоненты `E-E-A-T` раздельно;
- не подменять `Expertise` личным опытом и не перекрывать trust gaps брендом или риторикой.

### 7. `Optional Needs Met`

Что должно быть:

- `Needs Met`, если есть query context;
- `N/A`, если query context отсутствует;
- при наличии контекста — краткое обоснование.

Зачем это нужно:

- не смешивать usefulness с `Page Quality`;
- отделять релевантность запросу от внутреннего качества страницы.

### 8. `Матрица evidence`

Что должно быть:

- таблица с signal, URL страницы, observed evidence, rating impact.

Зачем это нужно:

- связать claims в отчете с наблюдаемыми фактами;
- облегчить последующую ручную ревизию и доработку отчета.

### 9. `Приоритетные действия`

Что должно быть:

- действия по категориям `Critical`, `High`, `Medium`.

Зачем это нужно:

- превратить findings в исполнимый action plan;
- развести блокеры и улучшения по уровню срочности.

## Реестр метрик

Обязательные метрики:

- `Purpose Clarity`
- `Beneficial Purpose`
- `Potential Harm`
- `Deceptive Purpose/Design`
- `YMYL Tier`
- `Need for Formal Expertise`
- `Need for First-Hand Experience`
- `Main Content Quality`
- `Main Content Effort/Originality`
- `Main Content Accuracy/Trustworthiness`
- `Supporting Content Helpfulness`
- `Ads/Monetization Interference`
- `Title Helpfulness / Exaggeration Risk`
- `Website Information Sufficiency`
- `Content Creator Information Sufficiency`
- `Customer Service / Transaction Trust Signals`
- `Website Reputation`
- `Content Creator Reputation`
- `Experience`
- `Expertise`
- `Authoritativeness`
- `Trustworthiness`
- `Overall E-E-A-T`
- `Page Quality`
- `Needs Met`
- `Special Flags`

Полные allowed values и source logic находятся в `references/qrg-metric-catalog.md`.

## Валидация и тестирование

### Быстрые команды

```powershell
python .\quick_validate.py --skip-fixtures
python .\scripts\fixtures\run_fixture_tests.py
python .\quick_validate.py
```

### Что проверяет `quick_validate.py`

- обязательные файлы skill;
- UTF-8 для текстовых файлов;
- структуру metric catalog;
- наличие metric allowed values в output contract;
- правила и структуру `SKILL.md`;
- наличие тематических классов в `ymyl-thresholds.md`;
- компактность `SKILL.md`;
- наличие обязательных headings в шаблонах;
- fixture smoke tests.

### Что проверяют fixture-тесты

- extractor на transactional, informational-authorship и spammy/deceptive HTML;
- корректную работу с nested author schema;
- локализацию рендера;
- наличие metric register и evidence matrix;
- отсутствие silent invented evidence;
- падение renderer на invalid metric values;
- корректный workflow order в `SKILL.md`.

## Правила внесения изменений

- Не превращать skill в crawl-heavy automation stack.
- Не добавлять full automatic E-E-A-T verdicting.
- Не смешивать `Page Quality` и `Needs Met`.
- Не убирать полный metric register из output.
- Не писать bilingual-дубли в runtime docs и templates.
- Если меняется output contract, одновременно обновлять:
  - `references/output-contract.md`
  - `references/qrg-metric-catalog.md`, если меняются метрики
  - `assets/*.md`
  - fixture-тесты
  - `quick_validate.py`, если меняются structural assumptions

## Рекомендуемый локальный цикл разработки

```powershell
python .\quick_validate.py --skip-fixtures
python .\scripts\fixtures\run_fixture_tests.py
python .\quick_validate.py
```

Если вы меняли только docs, все равно полезно прогнать хотя бы `python .\quick_validate.py --skip-fixtures`, чтобы не сломать structural assumptions skill.
