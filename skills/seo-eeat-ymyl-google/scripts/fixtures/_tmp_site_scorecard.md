# Тип сайта / YMYL Tier

- Тип сайта: Медицинский информационный сайт
- YMYL Tier: Clear YMYL
- Обоснование: Основная выборка состоит из информационной статьи, страницы доверия и YMYL-контента.

# Выборка URL

- `https://example-health.test/` — роль: `общая`
- `https://example-health.test/articles/colonoscopy-prep` — роль: `информационная`

# Hard-Gate Findings

- сигнал: недостоверные YMYL claims | url: https://example-health.test/offers/instant-cure | наблюдаемое подтверждение: Обнаружены обещания результата без медицинского обоснования. | влияние: Понижает доверие и может тянуть Page Quality вниз.

# Реестр QRG-метрик

| Метрика | Значение | Допустимые значения |
| --- | --- | --- |
| Purpose Clarity | Yes | Yes \| No \| Unclear |
| Beneficial Purpose | Yes | Yes \| No \| Unclear |
| Potential Harm | Unclear | Yes \| No \| Unclear |
| Deceptive Purpose/Design | No | Yes \| No \| Unclear |
| YMYL Tier | Clear YMYL | Non-YMYL \| Possible YMYL \| Clear YMYL \| Unclear |
| Need for Formal Expertise | Yes | Yes \| No \| Unclear |
| Need for First-Hand Experience | Yes | Yes \| No \| Unclear |
| Main Content Quality | High | Lowest \| Low \| Medium \| High \| Highest \| Unclear |
| Main Content Effort/Originality | High | Lowest \| Low \| Medium \| High \| Highest \| Unclear |
| Main Content Accuracy/Trustworthiness | High | Lowest \| Low \| Medium \| High \| Highest \| Unclear |
| Supporting Content Helpfulness | High | Lowest \| Low \| Medium \| High \| Highest \| Unclear |
| Ads/Monetization Interference | Medium | Lowest \| Low \| Medium \| High \| Highest \| Unclear |
| Title Helpfulness / Exaggeration Risk | High | Lowest \| Low \| Medium \| High \| Highest \| Unclear |
| Website Information Sufficiency | High | Lowest \| Low \| Medium \| High \| Highest \| Unclear |
| Content Creator Information Sufficiency | High | Lowest \| Low \| Medium \| High \| Highest \| Unclear |
| Customer Service / Transaction Trust Signals | Medium | Lowest \| Low \| Medium \| High \| Highest \| Unclear |
| Website Reputation | Unclear | Lowest \| Low \| Medium \| High \| Highest \| Unclear |
| Content Creator Reputation | Medium | Lowest \| Low \| Medium \| High \| Highest \| Unclear |
| Experience | 4 | 0 \| 1 \| 2 \| 3 \| 4 \| 5 \| Unclear |
| Expertise | 4 | 0 \| 1 \| 2 \| 3 \| 4 \| 5 \| Unclear |
| Authoritativeness | 3 | 0 \| 1 \| 2 \| 3 \| 4 \| 5 \| Unclear |
| Trustworthiness | 4 | 0 \| 1 \| 2 \| 3 \| 4 \| 5 \| Unclear |
| Overall E-E-A-T | 78 | 0-100 \| Unclear |
| Page Quality | High | Lowest \| Low \| Medium \| High \| Highest \| Unclear |
| Needs Met | N/A | ПС \| ВС \| СС \| НС \| ОС \| N/A |
| Special Flags | N/A | Porn \| Foreign Language \| Did Not Load \| Upsetting-Offensive \| N/A |

# Сводка по Page Quality

- Итоговая оценка: `High`
- Структура страницы помогает быстро понять ответ.
- Есть сильные сигналы авторства и источники.
- Внешняя репутация требует отдельной проверки.

# E-E-A-T Scorecard

- Experience: `4`
  Обоснование: Есть повествование на основе личного опыта и конкретные детали подготовки.
- Expertise: `4`
  Обоснование: Видна медицинская проверка и корректная терминология.
- Authoritativeness: `3`
  Обоснование: Нишевой авторитет просматривается, но внешняя репутация подтверждена не полностью.
- Trustworthiness: `4`
  Обоснование: Есть страницы доверия, автор, процесс проверки и источники.
- Overall E-E-A-T: `78`
  Обоснование: Профиль сильный, но остается внешний пробел в подтверждении репутации.

# Optional Needs Met

- `Needs Met`: `N/A`
- Контекст запроса отсутствует.

# Матрица evidence

| Сигнал | URL страницы | Наблюдаемое подтверждение | Влияние на оценку |
| --- | --- | --- | --- |
| schema `Person` | https://example-health.test/articles/colonoscopy-prep | Указан автор и рецензент в schema и в тексте страницы. | Повышает Expertise и Trustworthiness. |
| источники | https://example-health.test/articles/colonoscopy-prep | Есть ссылки на рекомендации и публикация в профильном издании. | Поддерживает точность и доверие. |

# Приоритетные действия

## Critical

- Убрать или переписать страницы с неподтвержденными медицинскими обещаниями.

## High

- Добавить отдельную страницу с редакционным процессом и политика медицинской проверки.

## Medium

- Усилить блок внешней репутации сайта и профилей авторов.

