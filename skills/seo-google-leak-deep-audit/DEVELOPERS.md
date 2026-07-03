# DEVELOPERS — seo-google-leak-deep-audit

Документ для разработчиков/SEO‑инженеров: как устроен пайплайн, какие файлы/контракты данных генерируются, и **словарь всех метрик**, которые встречаются в отчёте.

## Принципы

1) **Proxy, not ground truth**  
Мы никогда не заявляем, что считаем реальные внутренние сигналы Google. Каждый leaked/internal атрибут представлен **прокси‑формулой**, источниками данных и confidence.

2) **Evidence‑based**  
Каждая из 12 проверок даёт `evidence_urls` (до 20) и пошаговые `fix_steps`.

3) **Deterministic & safe crawl**  
Краулер ограничен по страницам, избегает URL‑ловушек, умеет сидировать обход через sitemap и (по умолчанию) уважает `robots.txt`.
Параметры по умолчанию: `--delay-ms 200` (пауза **между стартами запросов**), `--concurrency 10` (до 10 одновременных in‑flight запросов при соблюдении `delay`).
Куки между страницами не переносятся, чтобы не ловить массовые `400` на e‑commerce (переполнение Cookie header).

4) **Coverage matrix как договор с пользователем**  
Если данных нет (например, нет `ga4_pages` или `gsc_timeseries`) — метрика помечается `missing-data`, а action plan показывает “что добавить”.

## Архитектура пайплайна

Точка входа: `scripts/leak_audit.py`.

1) Crawl → `cache/crawl.jsonl`  
`scripts/crawl_site.py` + `scripts/extract_signals.py`.

2) Visual (опционально) → `cache/visual.json`  
`scripts/visual_checks.py` (Playwright).

3) External imports (опционально) → `cache/external.json`  
Импортеры CSV:
- `scripts/import_gsc_csv.py` (`--gsc-pages`, `--gsc-queries`)
- `scripts/import_gsc_timeseries_csv.py` (`--gsc-timeseries`)
- `scripts/import_ga4_csv.py` (`--ga4`)
- `scripts/import_ga4_traffic_csv.py` (`--ga4-traffic`)
- `scripts/import_ga4_scroll_csv.py` (`--ga4-scroll`)

4) Analyze → `cache/analysis.json`  
`scripts/analyze_leak_checks.py`: 12 checks + proxy_metrics + metric_coverage + growth_actions.

5) Render reports → `reports/*.md`  
Шаблоны:
- `templates/report.md`
- `templates/action-plan.md`

## Контракты данных

### `cache/crawl.jsonl` (по строке на страницу)

Ключевые поля (не исчерпывающе):

- `url`, `requested_url`, `source`, `aliases[]`, `alias_sources{}`, `status`, `depth`, `fetch_error`, `content_type`
- `is_noindex`, `robots`, `canonical`, `viewport_present`
- `title`, `meta_description`, `headings` (`h1/h2/h3`)
- `word_count`, `tokens`, `top_terms[]`
- `schema[]` (JSON‑LD), `author{...}`, `answer_first{...}`, `intro_text`
- `links{internal[], external[]}`, `pagination_links[]`
- `content_features{list_count, table_count, image_count, image_with_alt_count, image_alt_coverage, image_internal_src_count, image_external_src_count, image_data_uri_count, citation_count, qa_blocks, templated_phrase_hits, year_mentions, ugc_discussion{...}}`
- `dates{time_tags[], year_mentions[]}`
- `ui_hints{fixed_elements, sticky_elements, overlay_keyword_hits, popup_keyword_hits, interstitial_policy_risk}`
- `clickbait_title`

### `cache/external.json`

Содержит только то, что реально было передано флагами. Структуры:

- `gsc`: `{ rows[], by_url{} }`
- `gsc_queries`: `{ rows[], by_url{} }`
- `gsc_timeseries`: `{ rows[], by_url_date{} }`
- `ga4`: `{ rows[], by_url{} }`
- `ga4_traffic`: `{ rows[], by_url{} }` (включая `direct_share`)
- `ga4_scroll`: `{ rows[], by_url{} }` (включая `scroll_depth_proxy`)

### `cache/visual.json`

- `enabled` + `reason` + `results[]`
- `results[]` содержит флаги overlay/interstitial/horizontal scroll/heavy JS и вычисленный `violates_mobile_interstitial_policy_proxy`.

### `cache/analysis.json`

Top-level ключи:

- `summary`
- `data_sources` (булевы флаги: `crawl`, `playwright`, `gsc_pages`, `ga4_pages`, `gsc_timeseries`, и т.д.)
- `url_aliases` (сводка URL-алиасов/дублей из редиректов: сколько неканоничных URL ведут на один каноничный)
- `proxy_metrics` (агрегаты для таблицы Proxy Metrics)
- `metric_coverage` (матрица покрытия leaked‑метрик из `METRIC_REGISTRY`)
- `authority_graph`, `navboost_panel`
- `checks` (12 результатов)
- `growth_actions` (7 точек роста, привязанных к провалам)
- вспомогательные списки: `navboost_risk_pages`, `serp_demotion_pages`, `title_rewrite_risk_pages`, `ugc_low_effort_urls`, `noindex_pages`

## Метрики отчёта (словарь)

Ниже — “что означает каждая метрика” так, как она появляется в отчёте.

### A) Proxy Metrics (секция `Proxy Metrics`)

Эти ключи выводятся из `analysis.json -> proxy_metrics` и обычно лежат в диапазоне `0..1` (если не указано иное).

#### Топик/фокус
- `siteRadius_proxy` — доля “off-topic” страниц (`off_topic_ratio`). Чем выше, тем сильнее размыта тематика.
- `siteFocusScore_proxy` — `1 - siteRadius_proxy`. Чем выше, тем лучше фокус.
- `site2vecEmbeddingEncoded_proxy` — детерминированный “отпечаток” семантики сайта (SimHash64 по топ‑термам), без ML‑эмбеддера. Полезен для сравнения прогонов (насколько “съехала” тематика/лексика), но это **не** внутренний embedding Google.

#### Контент: effort / оригинальность
- `contentEffort_proxy_avg` — среднее “качество усилия” по страницам (длина/структура/цитирования/медиа/answer‑first минус шаблонность). Чем выше, тем лучше.
- `docImages_proxy` — прокси “насыщенности визуальными доказательствами” (blend: доля страниц с изображениями + среднее число изображений/страницу + alt‑coverage). Чем выше, тем лучше.
- `docImages_pages_with_images_ratio_proxy` — доля страниц, где найдено хотя бы одно изображение (`0..1`).
- `docImages_avg_images_per_page_proxy` — среднее число изображений на страницу (может быть большим на e‑commerce из‑за иконок/галерей).
- `docImages_alt_coverage_avg_proxy` — среднее покрытие `alt` по изображениям (`0..1`).
- `duplicateRisk_proxy` — доля near‑duplicate страниц. Чем выше, тем хуже (каннибализация/Панда‑риски).
- `babyPandaDemotion_proxy` — прокси риска low‑quality демоушена: `0.65*duplicateRisk_proxy + 0.35*(1-contentEffort_proxy_avg)` (чем выше, тем хуже).
- `originalContentScore_proxy` — `1 - duplicateRisk_proxy`. Чем выше, тем лучше.

#### NavBoost / поведенческие прокси
- `navboostRiskRatio_proxy` — доля страниц, помеченных как NavBoost‑risk (интент/обещание/удовлетворённость). Чем выше, тем хуже.
- `navDemotion_proxy` — прокси риска “NavBoost демоушена” как композит (answer‑first misses + UI/mobile friction + title rewrite risk + др.; при наличии GA4/GSC усиливается поведенческими сигналами). Чем выше, тем хуже.
- `goodClicks_proxy` — медиана `engagement_rate` (GA4), нормализованная к `0..1`. Требует `--ga4`.
- `badClicks_proxy` — `1 - goodClicks_proxy`.
- `lastLongestClicks_proxy` — медиана `avg_engagement_time` (сек) / 180, ограниченная `0..1`. Требует `--ga4`.
- `COEC_proxy_site_median` — медианный COEC по сайту (`actual_clicks/expected_clicks`), диапазон `0..3`. Требует `--gsc-timeseries`.
- `serpDemotion_proxy_count` — число URL с низким COEC (`< 0.75`) и заметными показами (>=100). Требует `--gsc-timeseries`.
- `scrollDepth_proxy` — медиана `scroll_events/users` (GA4), “скролл‑событий на пользователя”. Требует `--ga4-scroll`.
- `directUrlVisits_proxy` — медиана `direct_sessions/sessions` (GA4), доля прямого трафика. Требует `--ga4-traffic`.

#### UI / Mobile
- `clutterScore_proxy` — доля страниц с UI‑риском (оверлеи/fixed/sticky/попап‑хинты). Чем выше, тем хуже.
- `uiSmearing_proxy` — насколько UI‑штраф “размазан” по шаблонам (доля template‑кластеров с риском). Чем выше, тем хуже.
- `mobileRisk_proxy` — доля страниц с mobile friction (оверлеи/гор. скролл/heavy JS/viewport hints). Чем выше, тем хуже.
- `smartphoneOptimized_proxy` — `1 - mobileRisk_proxy`. Чем выше, тем лучше.
- `violatesMobileInterstitialPolicy_proxy` — доля страниц, где сработала эвристика interstitial‑policy риска. Чем выше, тем хуже.

#### Автор / сущности
- `authorEntityCoverage_proxy` — `1 - missing_author_ratio`: доля контента с сигналами автора/Person schema. Чем выше, тем лучше.
- `sameAs_links_total_proxy` — суммарное количество `sameAs` ссылок, извлечённых из Person schema.

#### Ссылки / анкоры / токсичность
- `anchorConsistency_proxy` — `1 - (проблемные URL / все URL)` по проверке анкоров. Чем выше, тем лучше.
- `toxicityOutlinks_proxy` — доля рискованных dofollow outlinks. Чем выше, тем хуже.

#### Freshness
- `syntacticDate_proxy` — доля страниц с “синтаксическими” датами (time‑теги/дат‑паттерны). Само по себе не “хорошо/плохо”.
- `semanticDateInfo_proxy` — доля страниц с “семантическими” актуальными годами (упоминания текущего года/фактов). Чем выше, тем лучше для freshness.
- `freshnessIntegrity_proxy` — `1 - freshness_mismatch_ratio`: насколько “обновления” выглядят содержательными, а не косметическими. Чем выше, тем лучше.

#### Passage / extractability
- `passageReadinessRisk_proxy` — доля страниц с низкой извлекаемостью (нет Q/A блоков, плохая структурность). Чем выше, тем хуже.

#### Конверсионные хабы / внутренний граф
- `conversionIsolation_proxy` — доля money‑страниц, которые “изолированы” (глубоко/мало внутренних ссылок). Чем выше, тем хуже.
- `onsiteProminence_proxy` — средняя “проминентность” money‑страниц по входящим ссылкам (нормировано по max inlinks). Чем выше, тем лучше.
- `internalPageRank_proxy` — максимум внутреннего PageRank по графу ссылок. Чем выше, тем сильнее есть доминирующая страница‑хаб.
- `iPullRank_proxy` — средний внутренний PageRank (обычно маленький, ~1/N).
- `anchorStats_proxy` — объект `{ unique_anchors, total_internal_links }`.

#### Композиты качества/доверия
- `NSR_proxy` — `1 - (сумма severity‑штрафов / 12)` по всем checks с evidence. Чем выше, тем лучше.
- `predictedDefaultNsr_proxy` — сейчас равен `NSR_proxy` (fallback без внешних authority данных).
- `lowQuality_proxy` — `1 - NSR_proxy`. Чем выше, тем хуже.
- `siteAuthority_proxy` — `(internalPageRank_proxy + NSR_proxy) / 2`. Чем выше, тем лучше.

#### Titles/snippets (Goldmine)
- `dupTokens_proxy` — доля страниц с дублирующимися “подписями” title‑токенов. Чем выше, тем выше риск переписывания.
- `title_h1_intro_overlap_proxy` — среднее пересечение токенов title с H1+intro. Чем выше, тем лучше согласованность.
- `titlematchScore_proxy` — прокси соответствия title ↔ контенту/интенту (в v1 равен `title_h1_intro_overlap_proxy`). Чем выше, тем лучше.
- `goldmineBlockbertFactor_proxy` — средний интегральный фактор риска переписывания title. Чем выше, тем хуже.
- `titleRewriteRisk_proxy` — доля страниц с высоким rewrite‑risk (порог ≥ 0.65). Чем выше, тем хуже.

#### UGC / reviews (расширенные прокси)
- `ugcDiscussionEffortScore_proxy` — средний effort‑score дискуссий (глубина + уникальные авторы + объём контента). Чем выше, тем “здоровее” обсуждение.
- `productReviewPUhqPage_proxy` — доля review‑страниц, проходящих пороги “качественного обзора” (длина, citations, таблица/список, Person schema).

### B) Metric Coverage Matrix (секция `Metric Coverage Matrix`)

Это `analysis.json -> metric_coverage`, построенное из `METRIC_REGISTRY` в `scripts/analyze_leak_checks.py`.

Поля:
- `status`: `implemented | missing-data | unavailable`
- `proxy_key`, `proxy_value` (если реализовано)
- `proxy_formula` (человекочитаемая формула)
- `data` (какие источники нужны)
- `data_required` (каких источников не хватает)
- `confidence`
- `used_in`

Метрики, которые трекаются (полный список из `METRIC_REGISTRY`):

- `siteRadius`, `siteFocusScore`, `site2vecEmbeddingEncoded`
- `contentEffort`, `docImages`, `OriginalContentScore`
- `goodClicks`, `badClicks`, `lastLongestClicks`
- `clutterScore`, `isSmearedSignal`
- `authorReputationScore`, `isAuthor`, `sameAs`
- `anchorMismatchDemotion`
- `shingleInfo`, `pandaDemotion`, `babyPandaDemotion`
- `isSmartphoneOptimized`, `mobileCwv`
- `onsiteProminence`, `homepagePagerankNs`
- `syntacticDate`, `semanticDateInfo`, `lastSignificantUpdate`
- `PageRank`, `PageRankPerDocData`, `anchorStats`, `perDocData`, `iPullRank`
- `NSR`, `predictedDefaultNsr`, `nsrDataProto`, `lowQuality`, `siteAuthority`
- `COEC`, `serpDemotion`, `scrollDepth`, `directUrlVisits`, `navDemotion`
- `Goldmine`, `AlternativeTitlesAnnotator`, `titlematchScore`, `dupTokens`, `goldmineBlockbertFactor`
- `violatesMobileInterstitialPolicy`
- `ugcDiscussionEffortScore`, `productReviewPUhqPage`
- `hostAge` (теперь через `rdap_whois`), `unsquashedClicks`, `chromeInTotal`, `authorObfuscatedGaiaStr`

#### Справочник leaked/internal метрик (как они интерпретируются в v1)

Таблица ниже описывает **все** метрики, которые могут появиться в `Metric Coverage Matrix` отчёта (и в `analysis.json -> metric_coverage`).

| Metric | Proxy key (в отчёте) | Смысл (в v1) | Data |
|---|---|---|---|
| `siteRadius` | `siteRadius_proxy` | Доля страниц, “вываливающихся” из topical centroid (размывание тематики). | `crawl` |
| `siteFocusScore` | `siteFocusScore_proxy` | `1 - siteRadius_proxy` (топик‑фокус). | `crawl` |
| `site2vecEmbeddingEncoded` | `site2vecEmbeddingEncoded_proxy` | Детерминированный “отпечаток” семантики сайта (SimHash64 по распределению топ‑термов), без ML‑эмбеддера. | `crawl` |
| `contentEffort` | `contentEffort_proxy_avg` | Композит “усилия” контента (структура/цитаты/медиа/answer‑first минус шаблонность). | `crawl` |
| `docImages` | `docImages_proxy` | Прокси визуального effort: доля страниц с изображениями + среднее кол-во изображений + alt‑coverage (в v1). | `crawl` |
| `OriginalContentScore` | `originalContentScore_proxy` | `1 - duplicateRisk_proxy` (прокси оригинальности). | `crawl` |
| `goodClicks` | `goodClicks_proxy` | Прокси удовлетворённости по GA4 engagement rate (медиана, `0..1`). | `ga4_pages` |
| `badClicks` | `badClicks_proxy` | `1 - goodClicks_proxy`. | `ga4_pages` |
| `lastLongestClicks` | `lastLongestClicks_proxy` | Прокси “длинных кликов”: медиана avg engagement time, норм. к 180с. | `ga4_pages` |
| `navDemotion` | `navDemotion_proxy` | Прокси риска NavBoost‑демоушена (композит: answer‑first + UI/mobile friction + title rewrite risk; GA4/GSC при наличии повышают точность). | `crawl` |
| `clutterScore` | `clutterScore_proxy` | Доля страниц с UI‑перекрытиями/оверлеями (clutter). | `crawl` |
| `isSmearedSignal` | `uiSmearing_proxy` | “Размазывание” UI‑проблем по шаблонам (template clusters). | `crawl` |
| `authorReputationScore` | `authorEntityCoverage_proxy` | Покрытие сигналами автора/Person schema + sameAs + автор‑хабы. | `crawl` |
| `isAuthor` | `authorEntityCoverage_proxy` | Доля long‑form страниц с авторскими сигналами (используем тот же proxy key). | `crawl` |
| `sameAs` | `sameAs_links_total_proxy` | Суммарные `sameAs` ссылки (Person schema). | `crawl` |
| `anchorMismatchDemotion` | `anchorConsistency_proxy` | Прокси нестыковок анкоров: чем больше проблемных URL, тем ниже consistency. | `crawl` |
| `shingleInfo` | `duplicateRisk_proxy` | Прокси near‑duplicate/шинглов: доля похожих страниц. | `crawl` |
| `pandaDemotion` | `duplicateRisk_proxy` | Прокси Panda‑риска: комбинация duplicate + low effort (в v1 свёрнуто в duplicate proxy). | `crawl` |
| `babyPandaDemotion` | `babyPandaDemotion_proxy` | Прокси low‑quality демоушена: `0.65*duplicateRisk + 0.35*(1-contentEffort)` (чем выше, тем хуже). | `crawl` |
| `isSmartphoneOptimized` | `smartphoneOptimized_proxy` | `1 - mobileRisk_proxy` (смартфон‑готовность). | `crawl` |
| `mobileCwv` | `mobileRisk_proxy` | Прокси mobile CWV (оверлеи/гор. скролл/heavy JS/viewport hints). | `crawl` |
| `onsiteProminence` | `onsiteProminence_proxy` | Проминентность money‑страниц по inlinks (нормировано). | `crawl` |
| `homepagePagerankNs` | `internalPageRank_proxy` | Прокси “потока” PageRank от хабов: максимум internal PageRank. | `crawl` |
| `syntacticDate` | `syntacticDate_proxy` | Доля страниц с синтаксическими маркерами свежести (time/даты). | `crawl` |
| `semanticDateInfo` | `semanticDateInfo_proxy` | Доля страниц с актуальными year‑mentions (семантика свежести). | `crawl` |
| `lastSignificantUpdate` | `freshnessIntegrity_proxy` | `1 - freshness_mismatch_ratio` (насколько обновления “не косметические”). | `crawl` |
| `PageRank` | `internalPageRank_proxy` | Internal PageRank по графу внутренних ссылок (итеративный, нормированный). | `crawl` |
| `PageRankPerDocData` | `internalPageRank_proxy` | Документ‑уровневые значения internal PageRank (в v1 репортим через тот же proxy key). | `crawl` |
| `anchorStats` | `anchorStats_proxy` | Статистика анкоров: `unique_anchors`, `total_internal_links`. | `crawl` |
| `perDocData` | `internalPageRank_proxy` | Документ‑уровневая оценка authority (в v1: производная от graph PR). | `crawl` |
| `iPullRank` | `iPullRank_proxy` | Средний internal PageRank (сайт‑уровень). | `crawl` |
| `NSR` | `NSR_proxy` | Композит качества: `1 - weighted severity penalties / 12`. | `crawl` |
| `predictedDefaultNsr` | `predictedDefaultNsr_proxy` | Fallback‑версия NSR (в v1 равна NSR). | `crawl` |
| `nsrDataProto` | `NSR_proxy` | “Контейнер” для NSR‑логики (в v1: агрегат severity/evidence). | `crawl` |
| `lowQuality` | `lowQuality_proxy` | `1 - NSR_proxy`. | `crawl` |
| `siteAuthority` | `siteAuthority_proxy` | `(internalPageRank_proxy + NSR_proxy) / 2`. | `crawl` |
| `COEC` | `COEC_proxy_site_median` | Clicks Over Expected Clicks: клики/ожидаемые клики по CTR‑кривой (медиана). | `gsc_timeseries` |
| `serpDemotion` | `serpDemotion_proxy_count` | Кол-во URL с низким COEC и достаточными показами (кандидаты на demotion). | `gsc_timeseries` |
| `scrollDepth` | `scrollDepth_proxy` | Медиана `scroll_events/users` по страницам. | `ga4_scroll` |
| `directUrlVisits` | `directUrlVisits_proxy` | Медиана `direct_sessions/sessions` по страницам. | `ga4_traffic` |
| `Goldmine` | `titleRewriteRisk_proxy` | Переписывание тайтлов: риск на основе overlap/dup/clickbait/answer‑first. | `crawl` |
| `AlternativeTitlesAnnotator` | `title_h1_intro_overlap_proxy` | Согласованность title с H1+intro (overlap). | `crawl` |
| `titlematchScore` | `titlematchScore_proxy` | Прокси соответствия title ↔ контенту/интенту (в v1: overlap title с H1+intro). | `crawl` |
| `dupTokens` | `dupTokens_proxy` | Доля страниц с повторяющимися “подписями” title‑токенов (dup patterns). | `crawl` |
| `goldmineBlockbertFactor` | `goldmineBlockbertFactor_proxy` | Интегральный фактор rewrite‑risk (среднее по страницам). | `crawl` |
| `violatesMobileInterstitialPolicy` | `violatesMobileInterstitialPolicy_proxy` | Доля страниц с эвристикой interstitial‑policy нарушения (Playwright повышает точность). | `crawl` |
| `ugcDiscussionEffortScore` | `ugcDiscussionEffortScore_proxy` | Прокси effort дискуссий: глубина/авторы/объём. | `crawl` |
| `productReviewPUhqPage` | `productReviewPUhqPage_proxy` | Прокси “качественных обзоров”: доля review‑страниц, проходящих пороги. | `crawl` |
| `hostAge` | `hostAge_proxy_years` | Возраст домена в годах по `registration` event из RDAP-ответа; дополнительно в `proxy_metrics` пишется `hostAge_proxy_days`. | `rdap_whois` |
| `unsquashedClicks` | n/a | Недоступно без proprietary click logs (в v1: `unavailable`). | `google_internal_logs` |
| `chromeInTotal` | n/a | Недоступно без Chrome telemetry totals (в v1: `unavailable`). | `chrome_telemetry` |
| `authorObfuscatedGaiaStr` | n/a | Недоступно без KG internal IDs (в v1: `unavailable`). | `kg_internal_ids` |

### C) Метрики внутри блоков `Check Results` (поле `proxy_metric`)

У каждой из 12 проверок есть JSON‑объект `proxy_metric` с дополнительными диагностическими значениями:

1) `check_01_topical_dilution`
   - `off_topic_ratio`, `siteFocusScore_proxy`, `mean_topical_overlap`
2) `check_02_low_effort_originality`
   - `contentEffort_proxy_avg`, `low_effort_ratio`
3) `check_03_intent_click_mismatch`
   - `risk_ratio`, `risk_pages`, `coec_site_median`, `title_rewrite_risk_ratio`
4) `check_04_ui_penalty_smearing`
   - `ui_risk_ratio`, `template_clusters`, `playwright_enabled`
5) `check_05_broken_author_entity_graph`
   - `missing_author_ratio`, `site_has_author_hub`, `sameAs_links_total`
6) `check_06_toxic_outgoing_neighborhood`
   - `risky_outlinks`, `toxic_outlink_ratio`
7) `check_07_syntactic_semantic_date_mismatch`
   - `freshness_mismatch_ratio`, `current_year`
8) `check_08_anchor_inconsistency`
   - `overused_commercial_anchors`, `mismatch_target_count`
9) `check_09_lexical_cannibalization`
   - `duplicate_url_ratio`, `duplicate_pairs`
10) `check_10_mobile_experience_failure`
   - `mobile_risk_ratio`, `playwright_enabled`
11) `check_11_no_passage_architecture`
   - `low_extractability_ratio`
12) `check_12_conversion_hubs_isolated`
   - `isolated_money_ratio`, `isolated_money_count`

Кратко “что означает”:

- `off_topic_ratio` — доля страниц с очень низким пересечением с centroid (в v1: overlap < 0.15).
- `mean_topical_overlap` — средний overlap страниц с centroid (чем выше, тем сайт однороднее тематически).
- `low_effort_ratio` — доля страниц с effort‑score ниже порога.
- `risk_ratio` — доля страниц, попавших в NavBoost‑risk список.
- `risk_pages` — количество NavBoost‑risk страниц.
- `coec_site_median` — медианный COEC по сайту (если есть `gsc_timeseries`).
- `title_rewrite_risk_ratio` — доля страниц с высоким title rewrite risk.
- `ui_risk_ratio` — доля страниц с UI‑рисками (оверлеи/fixed/sticky и т.п.).
- `template_clusters` — кластеры шаблонов (по первому сегменту пути), где UI‑риски повторяются.
- `playwright_enabled` — использовался ли Playwright в этом прогоне.
- `missing_author_ratio` — доля страниц без авторских сигналов.
- `site_has_author_hub` — найден ли “author hub” (страницы /author, /team, /about и т.п.).
- `sameAs_links_total` — сколько `sameAs` ссылок найдено в Person schema (суммарно).
- `risky_outlinks` — количество рискованных внешних ссылок (эвристики доменов/паттернов).
- `toxic_outlink_ratio` — доля рискованных outlinks (от общего числа внешних ссылок).
- `freshness_mismatch_ratio` — доля “обновлённых” страниц без признаков содержательного обновления.
- `current_year` — год, который считается “актуальным” при проверке (текущий UTC год).
- `overused_commercial_anchors` — список переиспользуемых exact‑match/коммерческих анкоров.
- `mismatch_target_count` — количество целей, где контекст анкоров плохо совпадает с контентом цели (прокси mismatch).
- `duplicate_url_ratio` — доля страниц, которые похожи на другие страницы выше порога (near‑duplicates).
- `duplicate_pairs` — примеры пар/кластеров near‑duplicate URL.
- `mobile_risk_ratio` — доля страниц с mobile friction сигналами.
- `low_extractability_ratio` — доля страниц, плохо пригодных для passage extraction (монолитный текст без структурных блоков).
- `isolated_money_ratio` — доля money‑страниц, изолированных в внутреннем графе.
- `isolated_money_count` — количество таких money‑страниц.

### D) Non‑Observable Leak Metrics (Guidance)

В шаблонах отчёта есть блок‑подсказка для метрик, которые невозможно посчитать краулингом и типовыми экспортами:

- `site2vecEmbeddingEncoded` — site‑level embedding (держите строгие topical pillars, избегайте расширения “вширь”).
- `navDemotion` — демоушены NavBoost по удовлетворённости (answer‑first, без трения UI, без кликбейта).
- `docImages` — сигнал effort по оригинальным визуалам (уникальные фото/схемы/таблицы, осмысленный `alt`).
- `babyPandaDemotion` — persistent quality demotion за thin/duplicate (консолидация, повышение уникальности, редакционный QA).
- `titlematchScore` — соответствие title ↔ интенту/контенту (title/H1/intro alignment, без bait‑and‑switch).
- `hostAge` — возраст/история домена (стабильность домена и публикаций, без агрессивного churn).

## Как расширять метрики/проверки

- Добавить новую leaked‑метрику в coverage:
  1) дописать её в `METRIC_REGISTRY` (`scripts/analyze_leak_checks.py`);
  2) вычислить `proxy_key` в `proxy_metrics` (или пометить `status: unavailable`);
  3) при необходимости добавить новый импортёр/источник (`data_sources`).
- Добавить новый сигнал на уровне страницы: расширять `scripts/extract_signals.py` и убедиться, что поле попадает в `crawl.jsonl`.
- Для регрессии использовать `scripts/fixtures/run_fixture_tests.py` и добавлять HTML/CSV фикстуры в `scripts/fixtures/`.

## Тестирование (локально)

Smoke:

```powershell
python scripts\leak_audit.py https://example.com --max-pages 30
```

Фикстуры:

```powershell
python scripts\fixtures\run_fixture_tests.py
```
