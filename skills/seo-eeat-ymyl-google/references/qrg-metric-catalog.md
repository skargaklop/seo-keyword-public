# QRG Metric Catalog

Ниже перечислены обязательные метрики итогового отчета. Для каждой метрики обязательно указывать фактическое значение, даже если это `Unclear` или `N/A`.

## Metric Register

### `purpose_clarity`
- `metric_id`: purpose_clarity
- `label`: Purpose Clarity
- `allowed_values`: `Yes | No | Unclear`
- `source_logic`: понятно ли, зачем существует страница и какую задачу решает.
- `required_evidence`: title, h1, intro, CTA, page role.
- `report_required`: yes

### `beneficial_purpose`
- `metric_id`: beneficial_purpose
- `label`: Beneficial Purpose
- `allowed_values`: `Yes | No | Unclear`
- `source_logic`: приносит ли страница реальную пользу пользователю.
- `required_evidence`: назначение страницы, тип задачи, value proposition.
- `report_required`: yes

### `potential_harm`
- `metric_id`: potential_harm
- `label`: Potential Harm
- `allowed_values`: `Yes | No | Unclear`
- `source_logic`: есть ли риск вреда, дезинформации или unsafe guidance.
- `required_evidence`: claims, request for data, YMYL context, warning signs.
- `report_required`: yes

### `deceptive_purpose_design`
- `metric_id`: deceptive_purpose_design
- `label`: Deceptive Purpose/Design
- `allowed_values`: `Yes | No | Unclear`
- `source_logic`: есть ли deceptive CTA, misleading layout, bait-and-switch.
- `required_evidence`: UI hints, button copy, overlays, misleading labels.
- `report_required`: yes

### `ymyl_tier`
- `metric_id`: ymyl_tier
- `label`: YMYL Tier
- `allowed_values`: `Non-YMYL | Possible YMYL | Clear YMYL | Unclear`
- `source_logic`: уровень чувствительности темы и последствий ошибки.
- `required_evidence`: topic, claims, transaction or advice pattern.
- `report_required`: yes

### `need_for_formal_expertise`
- `metric_id`: need_for_formal_expertise
- `label`: Need for Formal Expertise
- `allowed_values`: `Yes | No | Unclear`
- `source_logic`: требует ли тема лицензируемой или профессиональной компетенции.
- `required_evidence`: topic, claim type, user risk.
- `report_required`: yes

### `need_for_first_hand_experience`
- `metric_id`: need_for_first_hand_experience
- `label`: Need for First-Hand Experience
- `allowed_values`: `Yes | No | Unclear`
- `source_logic`: усиливает ли firsthand narrative полезность оценки.
- `required_evidence`: page type, review/how-to/journey content.
- `report_required`: yes

### `main_content_quality`
- `metric_id`: main_content_quality
- `label`: Main Content Quality
- `allowed_values`: `Lowest | Low | Medium | High | Highest | Unclear`
- `source_logic`: насколько качественно ОК выполняет свою задачу.
- `required_evidence`: completeness, structure, readability, usefulness.
- `report_required`: yes

### `main_content_effort_originality`
- `metric_id`: main_content_effort_originality
- `label`: Main Content Effort/Originality
- `allowed_values`: `Lowest | Low | Medium | High | Highest | Unclear`
- `source_logic`: заметны ли effort, originality, talent, depth.
- `required_evidence`: unique details, media, examples, synthesis.
- `report_required`: yes

### `main_content_accuracy_trustworthiness`
- `metric_id`: main_content_accuracy_trustworthiness
- `label`: Main Content Accuracy/Trustworthiness
- `allowed_values`: `Lowest | Low | Medium | High | Highest | Unclear`
- `source_logic`: насколько можно доверять фактам и утверждениям страницы.
- `required_evidence`: citations, correctness cues, disclaimers, review info.
- `report_required`: yes

### `supporting_content_helpfulness`
- `metric_id`: supporting_content_helpfulness
- `label`: Supporting Content Helpfulness
- `allowed_values`: `Lowest | Low | Medium | High | Highest | Unclear`
- `source_logic`: помогает ли ДК понять, найти, выполнить задачу.
- `required_evidence`: nav, FAQ, calculators, support links, breadcrumbs.
- `report_required`: yes

### `ads_monetization_interference`
- `metric_id`: ads_monetization_interference
- `label`: Ads/Monetization Interference
- `allowed_values`: `Lowest | Low | Medium | High | Highest | Unclear`
- `source_logic`: насколько монетизация мешает основной задаче пользователя.
- `required_evidence`: overlays, sticky blocks, CTA pressure, ad density.
- `report_required`: yes

### `title_helpfulness_exaggeration_risk`
- `metric_id`: title_helpfulness_exaggeration_risk
- `label`: Title Helpfulness / Exaggeration Risk
- `allowed_values`: `Lowest | Low | Medium | High | Highest | Unclear`
- `source_logic`: помогает ли title и нет ли clickbait/exaggeration.
- `required_evidence`: title, meta, H1, promise vs content.
- `report_required`: yes

### `website_information_sufficiency`
- `metric_id`: website_information_sufficiency
- `label`: Website Information Sufficiency
- `allowed_values`: `Lowest | Low | Medium | High | Highest | Unclear`
- `source_logic`: достаточно ли сведений о сайте и владельце.
- `required_evidence`: about, contact, company info, policies.
- `report_required`: yes

### `content_creator_information_sufficiency`
- `metric_id`: content_creator_information_sufficiency
- `label`: Content Creator Information Sufficiency
- `allowed_values`: `Lowest | Low | Medium | High | Highest | Unclear`
- `source_logic`: достаточно ли сведений об авторе или редакторе.
- `required_evidence`: byline, bio, credentials, profile link, schema.
- `report_required`: yes

### `customer_service_transaction_trust_signals`
- `metric_id`: customer_service_transaction_trust_signals
- `label`: Customer Service / Transaction Trust Signals
- `allowed_values`: `Lowest | Low | Medium | High | Highest | Unclear`
- `source_logic`: хватает ли transaction-trust signals там, где это нужно.
- `required_evidence`: returns, payments, terms, support, fulfillment details.
- `report_required`: yes

### `website_reputation`
- `metric_id`: website_reputation
- `label`: Website Reputation
- `allowed_values`: `Lowest | Low | Medium | High | Highest | Unclear`
- `source_logic`: внешняя и внутренняя картина репутации сайта.
- `required_evidence`: external mentions, reviews, trusted associations, disclaimers.
- `report_required`: yes

### `content_creator_reputation`
- `metric_id`: content_creator_reputation
- `label`: Content Creator Reputation
- `allowed_values`: `Lowest | Low | Medium | High | Highest | Unclear`
- `source_logic`: репутация автора или reviewer entity.
- `required_evidence`: bio, credentials, profile, citations, recognition.
- `report_required`: yes

### `experience`
- `metric_id`: experience
- `label`: Experience
- `allowed_values`: `0 | 1 | 2 | 3 | 4 | 5 | Unclear`
- `source_logic`: сила firsthand experience signals.
- `required_evidence`: cases, photos, process details, author role.
- `report_required`: yes

### `expertise`
- `metric_id`: expertise
- `label`: Expertise
- `allowed_values`: `0 | 1 | 2 | 3 | 4 | 5 | Unclear`
- `source_logic`: сила компетентности и correctness signals.
- `required_evidence`: credentials, citations, expert review, terminology.
- `report_required`: yes

### `authoritativeness`
- `metric_id`: authoritativeness
- `label`: Authoritativeness
- `allowed_values`: `0 | 1 | 2 | 3 | 4 | 5 | Unclear`
- `source_logic`: сила признания и статуса сайта/автора.
- `required_evidence`: reputation, sameAs, mentions, niche presence.
- `report_required`: yes

### `trustworthiness`
- `metric_id`: trustworthiness
- `label`: Trustworthiness
- `allowed_values`: `0 | 1 | 2 | 3 | 4 | 5 | Unclear`
- `source_logic`: уровень доверия, прозрачности и safety.
- `required_evidence`: site info, policies, contact, honest claims, secure UX.
- `report_required`: yes

### `overall_eeat`
- `metric_id`: overall_eeat
- `label`: Overall E-E-A-T
- `allowed_values`: `0-100 | Unclear`
- `source_logic`: итоговая synthesis-оценка E-E-A-T.
- `required_evidence`: итог по четырем компонентам и hard-gate context.
- `report_required`: yes

### `page_quality`
- `metric_id`: page_quality
- `label`: Page Quality
- `allowed_values`: `Lowest | Low | Medium | High | Highest | Unclear`
- `source_logic`: итоговая Page Quality оценка страницы или выборки.
- `required_evidence`: all major findings + hard-gates.
- `report_required`: yes

### `needs_met`
- `metric_id`: needs_met
- `label`: Needs Met
- `allowed_values`: `ПС | ВС | СС | НС | ОС | N/A`
- `source_logic`: полезность результата относительно конкретного intent.
- `required_evidence`: query context, intent type, page usefulness.
- `report_required`: yes

### `special_flags`
- `metric_id`: special_flags
- `label`: Special Flags
- `allowed_values`: `Porn | Foreign Language | Did Not Load | Upsetting-Offensive | N/A`
- `source_logic`: специальные статусы, влияющие на интерпретацию результата.
- `required_evidence`: observed page state or classification.
- `report_required`: yes
- `value_shape`: одно значение, `N/A` или список нескольких флагов без смешивания с `N/A`
