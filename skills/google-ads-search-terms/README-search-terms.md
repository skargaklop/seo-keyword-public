# Google Ads Search Terms Skill

## seos-cli adoption

`seos-cli` is optional for this skill. The copied GAQL scripts remain the correct path for exporting account search terms by date range, campaign scope, status, and batch resume.

Use `seos-cli` only after you have prepared a UTF-8 text file with one search term per line and need downstream Ads/SERP/Trends enrichment:

```powershell
seos-cli config check
seos-cli run --from-file search_terms.txt --steps ads,serp,trends,merge,export --format xlsx --out outputs/search-terms-enriched.xlsx
```

Current limitation: `seos-cli` does not directly ingest arbitrary Google Ads search-term CSV exports. Treat direct CSV ingestion as backlog, not as existing behavior.

## Описание

Этот навык предназначен для выгрузки и анализа реальных поисковых запросов пользователей (Search Terms), по которым состоялись показы вашей рекламы в Google Ads.

Анализ фактических запросов — важнейший процесс оптимизации кампаний: он позволяет находить новые глубокие минус-слова, экономить рекламный бюджет, отсекая нецелевой трафик, и находить дешевые конверсионные ключевые фразы.

## Что умеет

1. **Быстрая выгрузка (Sync-режим)** (`search_terms_sync`): оперативный экспорт топа поисковых запросов и их эффективности (показы, клики, стоимость, конверсии). Идеально для быстрых проверок аккаунта.
2. **Глубокая пакетная выгрузка (Batch-режим)** (`search_terms_batch`): разбивка многомесячных выгрузок на порции (chunks) с кэшированием прогресса. Отличное решение для "крупных" аккаунтов. Поддерживает параметр `--resume` (возобновление при ошибках сети).
3. **Гибкая фильтрация**: поддержка фильтров по датам (`--date-from`, `--date-to`), конкретным кампаниям (`--campaign-ids`) и статусу добавления слов на аккаунте (`--status`).

Все скрипты представлены в двух надежных вариантах: классический Bash (`.sh`) и глубоко проработанный PowerShell (`.ps1`) с атомарным обновлением кэша OAuth и парсерами API-ошибок.

## Как начать пользоваться

### 1. Настройка доступов

Как и Keyword Planner, навык требует настройки `.env` с ключами Google Ads API.
Настройте файл в папке `google-ads-search-terms/config/.env`. Если доступы уже есть, вы можете использовать тот же набор ключей.

### 2. Smoke Test

Проверьте авторизацию:

- **Bash (Linux/Mac):** `bash google-ads-search-terms/scripts/auth_check.sh`
- **PowerShell (Windows):** `.\google-ads-search-terms\scripts\auth_check.ps1`

### 3. Экспорт поисковых запросов

Выгрузите запросы за последний месяц (30 дней по умолчанию) напрямую в CSV файл для работы в Microsoft Excel/Google Таблицах:

- **Windows:** `.\google-ads-search-terms\scripts\search_terms_sync.ps1 --limit 1000 --csv my_search_terms.csv`

Скрипт распечатает краткую таблицу (превью) прямо в консоль, а полные данные с затратами и конверсиями запишет в CSV.
