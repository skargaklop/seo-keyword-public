# Google Ads Keyword Planner Skill

## seos-cli adoption

`seos-cli` is useful for this skill when the goal is a project-native keyword report or an enriched Ads/SERP/Trends export.

Recommended commands:

```powershell
seos-cli config check
seos-cli ads --keywords "seed keyword, second seed" --format xlsx --out outputs/google-ads-keyword-plan.xlsx
seos-cli run --keywords "seed keyword" --steps ads,serp,trends,merge,export --format xlsx --out outputs/keyword-plan-enriched.xlsx
```

Use the copied scripts instead for raw Google Ads API operations such as geo lookup, token troubleshooting, monthly metric experiments, and missed-demand helper workflows. Do not store real `.env` files in the copied skill folder; rely on the project config checked by `seos-cli config check`.

## Описание

Этот навык предназначен для исследования ключевых слов и оценки спроса с помощью официального Google Ads Keyword Plan Idea Service. Он помогает находить новые идеи для поисковых кампаний, получать их исторические метрики, искать целевые регионы и проводить сложный анализ упущенного спроса.

Важная особенность навыка — методология работы: строгая проверка целевого интента (намерения пользователя совершить покупку) для отсеивания "мусорного" трафика через веб-поиск.

## Что умеет

1. **Подбор ключевых слов** (`keyword_ideas`): генерация свежих идей на основе базовых слов или URL конкурентов.
2. **Анализ исторического спроса** (`historical_metrics`): получение точных данных по частотности (avg monthly searches), конкуренции и ставкам.
3. **Помесячная динамика** (`search_volume`): анализ сезонности за последние 12 месяцев.
4. **Справочник гео-таргетингов** (`geo_lookup`): поиск точных ID регионов и городов для точного прицеливания рекламы.
5. **Оценка упущенного спроса** (`missed_demand.py`): сбор широкой семантики и прогноз потенциального трафика через сложные OR-запросы.

Все скрипты кроссплатформенные: поддерживают как Bash (`.sh`), так и продвинутый PowerShell (`.ps1`) с безопасным кэшированием OAuth-токенов.

## Как начать пользоваться

### 1. Настройка доступов

Навык использует Google Ads API REST.
Вам нужно скопировать пример файла конфигурации и внести свои данные:
Перейдите в папку `google-ads-keyword-planner/config/` и настройте файл `.env`, заполнив параметры: `GOOGLE_ADS_DEVELOPER_TOKEN`, `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_REFRESH_TOKEN` и `GOOGLE_ADS_CUSTOMER_ID` (а также `LOGIN_CUSTOMER_ID` при работе через MCC-аккаунт).

### 2. Проверка подключения

Убедитесь, что ключи настроены верно:

- **Bash (Linux/Mac):** `bash google-ads-keyword-planner/scripts/health_check.sh`
- **PowerShell (Windows):** `.\google-ads-keyword-planner\scripts\health_check.ps1`

### 3. Базовый сценарий использования

Сначала определите ID региона для таргетинга (например, США):
`.\google-ads-keyword-planner\scripts\geo_lookup.ps1 -Query "United States"`

Затем соберите идеи (подставив нужный GeoID и LanguageID):
`.\google-ads-keyword-planner\scripts\keyword_ideas.ps1 --seed "buy chimney" --geo-ids 2840 --language-id 1000`
