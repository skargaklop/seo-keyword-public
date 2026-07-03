# Output Contract

## Основной deliverable

Итоговый deliverable — `scorecard-first` отчет. Narrative без полного metric register считается некорректным output для этого skill.

## Обязательные секции

1. `Тип сайта / YMYL Tier`
2. `Выборка URL`
3. `Находки hard-gates`
4. `Реестр QRG-метрик`
5. `Сводка по Page Quality`
6. `E-E-A-T Scorecard`
7. `Needs Met (опционально)`
8. `Матрица evidence`
9. `Приоритетные действия`

## Правила секций

### `Тип сайта / YMYL Tier`

- тип сайта;
- `YMYL Tier`;
- краткое обоснование.

### `Выборка URL`

- перечислить все sampled pages;
- отметить роль страницы в выборке.

### `Находки hard-gates`

Для каждого finding указать:

- `signal`
- `page URL`
- `observed evidence`
- `rating impact`

### `Реестр QRG-метрик`

- перечислить все метрики из `qrg-metric-catalog.md`;
- для каждой метрики дать значение;
- если данных не хватает, использовать `Unclear` или `N/A`, а не пропуск.

### `Сводка по Page Quality`

- итоговая оценка `Page Quality`;
- объяснение, какие факторы подняли или понизили оценку.

### `E-E-A-T Scorecard`

- `Experience`
- `Expertise`
- `Authoritativeness`
- `Trustworthiness`
- `Overall E-E-A-T`

Для каждого поля кратко объяснить, на чем основан балл.

### `Needs Met (опционально)`

- заполнять только при наличии query context;
- если его нет, явно указать `N/A`.

### `Матрица evidence`

Каждая строка должна содержать:

- signal;
- page URL;
- observed evidence;
- rating impact.

### `Приоритетные действия`

Делить действия на:

- `Critical`
- `High`
- `Medium`

## Wording Rules

- Писать по-русски.
- Английские названия метрик оставлять только как стандартные labels.
- Не утверждать то, чего нет в evidence.
- Не подменять `Unclear` догадками.
- Для action items писать конкретное действие, а не общий лозунг.

## Допустимые значения по метрикам

- `Purpose Clarity`: `Yes | No | Unclear`
- `Beneficial Purpose`: `Yes | No | Unclear`
- `Potential Harm`: `Yes | No | Unclear`
- `Deceptive Purpose/Design`: `Yes | No | Unclear`
- `YMYL Tier`: `Non-YMYL | Possible YMYL | Clear YMYL | Unclear`
- `Need for Formal Expertise`: `Yes | No | Unclear`
- `Need for First-Hand Experience`: `Yes | No | Unclear`
- `Main Content Quality`: `Lowest | Low | Medium | High | Highest | Unclear`
- `Main Content Effort/Originality`: `Lowest | Low | Medium | High | Highest | Unclear`
- `Main Content Accuracy/Trustworthiness`: `Lowest | Low | Medium | High | Highest | Unclear`
- `Supporting Content Helpfulness`: `Lowest | Low | Medium | High | Highest | Unclear`
- `Ads/Monetization Interference`: `Lowest | Low | Medium | High | Highest | Unclear`
- `Title Helpfulness / Exaggeration Risk`: `Lowest | Low | Medium | High | Highest | Unclear`
- `Website Information Sufficiency`: `Lowest | Low | Medium | High | Highest | Unclear`
- `Content Creator Information Sufficiency`: `Lowest | Low | Medium | High | Highest | Unclear`
- `Customer Service / Transaction Trust Signals`: `Lowest | Low | Medium | High | Highest | Unclear`
- `Website Reputation`: `Lowest | Low | Medium | High | Highest | Unclear`
- `Content Creator Reputation`: `Lowest | Low | Medium | High | Highest | Unclear`
- `Experience`: `0 | 1 | 2 | 3 | 4 | 5 | Unclear`
- `Expertise`: `0 | 1 | 2 | 3 | 4 | 5 | Unclear`
- `Authoritativeness`: `0 | 1 | 2 | 3 | 4 | 5 | Unclear`
- `Trustworthiness`: `0 | 1 | 2 | 3 | 4 | 5 | Unclear`
- `Overall E-E-A-T`: `0-100 | Unclear`
- `Page Quality`: `Lowest | Low | Medium | High | Highest | Unclear`
- `Needs Met`: `ПС | ВС | СС | НС | ОС | N/A`
- `Special Flags`: `Porn | Foreign Language | Did Not Load | Upsetting-Offensive | N/A`
  Можно передавать как одно значение, `N/A` или список из нескольких флагов одновременно.
