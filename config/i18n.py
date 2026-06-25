from typing import Dict

import streamlit as st

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # --- App main ---
    "app_title": {
        "ru": "🚀 Auto SEO Keyword Planner",
        "uk": "🚀 Auto SEO Keyword Planner",
        "en": "🚀 Auto SEO Keyword Planner",
    },
    "app_description": {
        "ru": "Извлечение коммерческих ключевых слов из URL, обогащение метриками Google Ads и экспорт в Excel.",
        "uk": "Збір комерційних ключових слів з URL, збагачення метриками Google Ads та експорт в Excel.",
        "en": "Extract commercial keywords from URLs, enrich them with Google Ads metrics, and export to Excel.",
    },
    "app_console_title": {
        "ru": "Auto SEO Keyword Planner",
        "uk": "Auto SEO Keyword Planner",
        "en": "Auto SEO Keyword Planner",
    },
    "no_api_keys": {
        "ru": "⚠️ Не найдено ни одного API ключа. Проверьте файл .env.",
        "uk": "⚠️ Не знайдено жодного API ключа. Перевірте файл .env.",
        "en": "⚠️ No API keys found. Check your .env file.",
    },
    "enter_url_header": {
        "ru": "1. Ввод URL",
        "uk": "1. Введення URL",
        "en": "1. URL input",
    },
    "enter_url_placeholder": {
        "ru": "Введите URL (по одному на строку)",
        "uk": "Введіть URL (по одному на рядок)",
        "en": "Enter one URL per line",
    },
    "upload_file": {
        "ru": "Или загрузите файл (txt/csv)",
        "uk": "Або завантажте файл (txt/csv)",
        "en": "Or upload a file (txt/csv)",
    },
    "upload_button": {
        "ru": "Загрузить",
        "uk": "Завантажити",
        "en": "Upload",
    },
    "status_header": {
        "ru": "Статус",
        "uk": "Статус",
        "en": "Status",
    },
    "show_logs": {
        "ru": "Показать логи",
        "uk": "Показати логи",
        "en": "Show logs",
    },
    "start_analysis": {
        "ru": "🚀 Запустить",
        "uk": "🚀 Запустити",
        "en": "🚀 Start",
    },
    "enter_url_warning": {
        "ru": "Пожалуйста, введите URL.",
        "uk": "Будь ласка, введіть URL.",
        "en": "Please enter at least one URL.",
    },
    # --- Sidebar ---
    "settings_header": {
        "ru": "⚙️ Настройки",
        "uk": "⚙️ Налаштування",
        "en": "⚙️ Settings",
    },
    "ui_language": {
        "ru": "🌐 Язык интерфейса",
        "uk": "🌐 Мова інтерфейсу",
        "en": "Interface language",
    },
    "llm_provider": {
        "ru": "LLM Провайдер",
        "uk": "LLM Провайдер",
        "en": "LLM provider",
    },
    "no_api_keys_sidebar": {
        "ru": "В .env не найдены API ключи. Пожалуйста, настройте хотя бы одного провайдера.",
        "uk": "В .env не знайдено API ключів. Будь ласка, налаштуйте хоча б одного провайдера.",
        "en": "No provider API keys were found in .env. Please configure at least one provider.",
    },
    "select_provider": {
        "ru": "Выберите провайдера",
        "uk": "Оберіть провайдера",
        "en": "Select provider",
    },
    "model_name": {
        "ru": "Название модели",
        "uk": "Назва моделі",
        "en": "Model name",
    },
    "max_keywords_per_url": {
        "ru": "Макс. слов на URL",
        "uk": "Макс. слів на URL",
        "en": "Max keywords per URL",
    },
    "location": {
        "ru": "Локация",
        "uk": "Локація",
        "en": "Location",
    },
    "language": {
        "ru": "Язык",
        "uk": "Мова",
        "en": "Language",
    },
    "currency": {
        "ru": "Валюта",
        "uk": "Валюта",
        "en": "Currency",
    },
    "currency_help": {
        "ru": "В этой валюте будут показаны и экспортированы Low CPC / High CPC.",
        "uk": "У цій валюті будуть показані та експортовані Low CPC / High CPC.",
        "en": "Low CPC and High CPC will be displayed and exported in this currency.",
    },
    "api_params": {
        "ru": "🔧 Параметры API",
        "uk": "🔧 Параметри API",
        "en": "🔧 API parameters",
    },
    "request_timeout": {
        "ru": "Таймаут ответа API (сек)",
        "uk": "Таймаут відповіді API (сек)",
        "en": "API response timeout (sec)",
    },
    "request_timeout_help": {
        "ru": "Максимальное время ожидания ответа от API. Не управляет паузой между повторными попытками.",
        "uk": "Максимальний час очікування відповіді від API. Не керує паузою між повторними спробами.",
        "en": "Maximum time to wait for an API response. This does not control the pause between retries.",
    },
    "delay_between_requests": {
        "ru": "Задержка между обычными запросами (сек)",
        "uk": "Затримка між звичайними запитами (сек)",
        "en": "Delay between normal requests (sec)",
    },
    "delay_between_requests_help": {
        "ru": "Пауза между последовательными обычными запросами к API для снижения риска rate-limit.",
        "uk": "Пауза між послідовними звичайними запитами до API для зниження ризику rate-limit.",
        "en": "Pause between sequential API requests to reduce rate-limit risk.",
    },
    "retry_count": {
        "ru": "Количество повторных попыток",
        "uk": "Кількість повторних спроб",
        "en": "Retry attempts",
    },
    "retry_count_help": {
        "ru": "Сколько раз повторять запрос при ошибке API перед тем, как сдаться.",
        "uk": "Скільки разів повторювати запит при помилці API перед тим, як здатися.",
        "en": "How many times to retry a failed API request before giving up.",
    },
    "retry_delay": {
        "ru": "Задержка между retry (сек)",
        "uk": "Затримка між retry (сек)",
        "en": "Delay between retries (sec)",
    },
    "retry_delay_help": {
        "ru": "Пауза перед каждой повторной попыткой после ошибки API.",
        "uk": "Пауза перед кожною повторною спробою після помилки API.",
        "en": "Pause before each retry after an API error.",
    },
    "system_prompts": {
        "ru": "📝 Системные промпты",
        "uk": "📝 Системні промпти",
        "en": "📝 System prompts",
    },
    "keyword_prompt_label": {
        "ru": "Промпт: Извлечение ключевых слов",
        "uk": "Промпт: Збір ключових слів",
        "en": "Prompt: Keyword extraction",
    },
    "keyword_prompt_desc": {
        "ru": "**Промпт для сбора ключевых слов**\n\nДоступные переменные:\n- `{max_keywords}` — максимальное количество ключевых слов для извлечения",
        "uk": "**Промпт для збору ключових слів**\n\nДоступні змінні:\n- `{max_keywords}` — максимальна кількість ключових слів для збору",
        "en": "**Prompt for keyword extraction**\n\nAvailable variables:\n- `{max_keywords}` - maximum number of keywords to extract",
    },
    "seo_prompt_label": {
        "ru": "Промпт: SEO описание",
        "uk": "Промпт: SEO опис",
        "en": "Prompt: SEO description",
    },
    "seo_prompt_desc": {
        "ru": "**Промпт для генерации SEO описания**\n\nДоступные переменные:\n- `{language}` — язык генерации (например, Russian, Ukrainian)\n- `{keywords_list}` — список ключевых слов с объёмами поиска\n- `{content}` — текст, полученный из URL\n- `{page_type}` — тип страницы (product, category, blog post или пользовательский)",
        "uk": "**Промпт для генерації SEO опису**\n\nДоступні змінні:\n- `{language}` — мова генерації (наприклад, Russian, Ukrainian)\n- `{keywords_list}` — список ключових слів з обсягами пошуку\n- `{content}` — текст, отриманий з URL\n- `{page_type}` — тип сторінки (product, category, blog post або користувацький)",
        "en": "**Prompt for SEO text generation**\n\nAvailable variables:\n- `{language}` - generation language (for example, English, Russian, Ukrainian)\n- `{keywords_list}` - list of keywords with search volumes\n- `{content}` - content scraped from the URL\n- `{page_type}` - page type (product, category, blog post, or a custom value)",
    },
    "export_header": {
        "ru": "📁 Экспорт",
        "uk": "📁 Експорт",
        "en": "📁 Export",
    },
    "auto_save_excel": {
        "ru": "Автосохранение Excel в outputs/",
        "uk": "Автозбереження Excel в outputs/",
        "en": "Auto-save Excel files to outputs/",
    },
    "cleanup_days_label": {
        "ru": "Удалять файлы из outputs/ старше (дней)",
        "uk": "Видаляти файли з outputs/ старше (днів)",
        "en": "Delete files from outputs/ older than (days)",
    },
    "cleanup_days_help": {
        "ru": "Автоматически удалять файлы из папки outputs/ старше указанного количества дней. 0 = не удалять.",
        "uk": "Автоматично видаляти файли з папки outputs/ старше вказаної кількості днів. 0 = не видаляти.",
        "en": "Automatically delete files from outputs/ older than the specified number of days. 0 = keep everything.",
    },
    "storage_limits_header": {
        "ru": "Хранение и лимиты",
        "uk": "Зберігання та ліміти",
        "en": "Storage and limits",
    },
    "api_retention_days_label": {
        "ru": "Хранить API-логи (дней)",
        "uk": "Зберігати API-логи (днів)",
        "en": "Keep API logs (days)",
    },
    "api_retention_days_help": {
        "ru": "Удалять API-логи старше указанного количества дней. 0 = не удалять.",
        "uk": "Видаляти API-логи старші за вказану кількість днів. 0 = не видаляти.",
        "en": "Delete API logs older than the specified number of days. 0 = keep everything.",
    },
    "history_retention_days_label": {
        "ru": "Хранить историю (дней)",
        "uk": "Зберігати історію (днів)",
        "en": "Keep history (days)",
    },
    "history_retention_days_help": {
        "ru": "Удалять записи истории старше указанного количества дней. 0 = не удалять.",
        "uk": "Видаляти записи історії старші за вказану кількість днів. 0 = не видаляти.",
        "en": "Delete history entries older than the specified number of days. 0 = keep everything.",
    },
    "history_clear_cache_button": {
        "ru": "Очистить историю и кеш",
        "uk": "Очистити історію та кеш",
        "en": "Clear history and cache",
    },
    "history_clear_cache_success": {
        "ru": "История и кеш очищены.",
        "uk": "Історію та кеш очищено.",
        "en": "History and cache cleared.",
    },
    "history_clear_cache_error": {
        "ru": "Не удалось очистить историю и кеш.",
        "uk": "Не вдалося очистити історію та кеш.",
        "en": "Failed to clear history and cache.",
    },
    "history_clear_cache_confirm_title": {
        "ru": "Очистить историю и кеш?",
        "uk": "Очистити історію та кеш?",
        "en": "Clear history and cache?",
    },
    "history_clear_cache_confirm_body": {
        "ru": "Это действие удалит всю историю и записи кеша без возможности восстановления. Продолжить?",
        "uk": "Ця дія видалить усю історію та записи кешу без можливості відновлення. Продовжити?",
        "en": "This action will delete all history and cache records permanently. Continue?",
    },
    "history_clear_cache_confirm_yes": {
        "ru": "Да, очистить",
        "uk": "Так, очистити",
        "en": "Yes, clear",
    },
    "history_clear_cache_confirm_cancel": {
        "ru": "Отмена",
        "uk": "Скасувати",
        "en": "Cancel",
    },
    "upload_max_file_size_mb_label": {
        "ru": "Максимальный размер файла (MB)",
        "uk": "Максимальний розмір файлу (MB)",
        "en": "Maximum file size (MB)",
    },
    "upload_max_file_size_mb_help": {
        "ru": "Файлы больше этого лимита будут отклонены при загрузке.",
        "uk": "Файли більші за цей ліміт буде відхилено під час завантаження.",
        "en": "Files larger than this limit will be rejected during upload.",
    },
    "upload_max_rows_label": {
        "ru": "Максимум строк/значений из файла",
        "uk": "Максимум рядків/значень з файлу",
        "en": "Maximum rows/values from file",
    },
    "upload_max_rows_help": {
        "ru": "После чтения файла будет использовано не больше этого количества строк/значений.",
        "uk": "Після читання файлу буде використано не більше цієї кількості рядків/значень.",
        "en": "After reading a file, no more than this number of rows/values will be accepted.",
    },
    "upload_file_too_large": {
        "ru": "Файл {filename} превышает лимит {max_size_mb} MB.",
        "uk": "Файл {filename} перевищує ліміт {max_size_mb} MB.",
        "en": "File {filename} exceeds the limit of {max_size_mb} MB.",
    },
    "upload_file_too_many_rows": {
        "ru": "Файл {filename} содержит больше допустимых строк/значений ({max_rows}).",
        "uk": "Файл {filename} містить більше допустимих рядків/значень ({max_rows}).",
        "en": "File {filename} contains more than the allowed number of rows/values ({max_rows}).",
    },
    "upload_file_unsupported_format": {
        "ru": "Неподдерживаемый формат файла: {filename}. Используйте .txt или .csv.",
        "uk": "Непідтримуваний формат файлу: {filename}. Використовуйте .txt або .csv.",
        "en": "Unsupported file format: {filename}. Use .txt or .csv.",
    },
    "upload_file_parse_error": {
        "ru": "Не удалось прочитать файл {filename}: {error}",
        "uk": "Не вдалося прочитати файл {filename}: {error}",
        "en": "Could not read file {filename}: {error}",
    },
    "save_settings": {
        "ru": "💾 Сохранить настройки",
        "uk": "💾 Зберегти налаштування",
        "en": "💾 Save settings",
    },
    "settings_saved": {
        "ru": "✅ Настройки сохранены!",
        "uk": "✅ Налаштування збережено!",
        "en": "✅ Settings saved.",
    },
    "settings_save_error": {
        "ru": "Ошибка сохранения",
        "uk": "Помилка збереження",
        "en": "Failed to save settings",
    },
    "logging_header": {
        "ru": "Логирование",
        "uk": "Логування",
        "en": "Logging",
    },
    "log_app_level": {
        "ru": "Уровень app.log",
        "uk": "Рівень app.log",
        "en": "app.log level",
    },
    "log_console_enabled": {
        "ru": "Включить вывод в консоль",
        "uk": "Увімкнути вивід у консоль",
        "en": "Enable console output",
    },
    "log_console_level": {
        "ru": "Уровень консоли",
        "uk": "Рівень консолі",
        "en": "Console level",
    },
    "log_api_enabled": {
        "ru": "Включить лог API-запросов",
        "uk": "Увімкнути лог API-запитів",
        "en": "Enable API request logging",
    },
    "log_api_level": {
        "ru": "Уровень API-лога",
        "uk": "Рівень API-логу",
        "en": "API log level",
    },
    "log_error_level": {
        "ru": "Уровень errors.log",
        "uk": "Рівень errors.log",
        "en": "errors.log level",
    },
    "log_test_runs": {
        "ru": "Логировать pytest/test-запуски",
        "uk": "Логувати pytest/test-запуски",
        "en": "Log pytest/test runs",
    },
    "pipeline_validating_urls": {
        "ru": "Проверка URL...",
        "uk": "Перевірка URL...",
        "en": "Validating URLs...",
    },
    "pipeline_invalid_urls_skipped": {
        "ru": "⚠️ Пропущено некорректных URL: {count}",
        "uk": "⚠️ Пропущено некоректних URL: {count}",
        "en": "⚠️ Invalid URLs skipped: {count}",
    },
    "pipeline_no_valid_urls": {
        "ru": "Нет валидных URL для обработки.",
        "uk": "Немає валідних URL для обробки.",
        "en": "No valid URLs to process.",
    },
    "pipeline_scraping_content": {
        "ru": "Скрапинг контента...",
        "uk": "Скрапінг контенту...",
        "en": "Scraping content...",
    },
    "pipeline_no_content_scraped": {
        "ru": "Не удалось получить контент ни для одного URL. Проверьте доступность сайта и SSL-сертификат.",
        "uk": "Не вдалося отримати контент ні для жодного URL. Перевірте доступність сайту та SSL-сертифікат.",
        "en": "Could not extract content for any URL. Check that the site is reachable and its SSL certificate is valid.",
    },
    "pipeline_extracting_keywords": {
        "ru": "Извлечение ключевых слов через AI...",
        "uk": "Збір ключових слів через AI...",
        "en": "Extracting keywords with AI...",
    },
    "pipeline_analyzing_url": {
        "ru": "Анализ {idx}/{total}: {url}",
        "uk": "Аналіз {idx}/{total}: {url}",
        "en": "Analyzing {idx}/{total}: {url}",
    },
    "pipeline_processing_deduplicating": {
        "ru": "Обработка и дедупликация...",
        "uk": "Обробка та дедуплікація...",
        "en": "Processing and deduplicating...",
    },
    "pipeline_no_keywords_found": {
        "ru": "Не найдено ключевых слов, подходящих под критерии.",
        "uk": "Не знайдено ключових слів, що відповідають критеріям.",
        "en": "No keywords matching the criteria were found.",
    },
    "pipeline_fetching_metrics": {
        "ru": "Получение метрик для {count} ключевых слов...",
        "uk": "Отримання метрик для {count} ключових слів...",
        "en": "Fetching metrics for {count} keywords...",
    },
    "pipeline_querying_google_ads": {
        "ru": "Запрос к Google Ads API...",
        "uk": "Запит до Google Ads API...",
        "en": "Querying Google Ads API...",
    },
    "pipeline_finalizing_report": {
        "ru": "Финализация отчета...",
        "uk": "Фіналізація звіту...",
        "en": "Finalizing report...",
    },
    "pipeline_done": {
        "ru": "Готово!",
        "uk": "Готово!",
        "en": "Done!",
    },
    "pipeline_analysis_complete": {
        "ru": "Анализ завершен!",
        "uk": "Аналіз завершено!",
        "en": "Analysis complete!",
    },
    # --- Results ---
    "results_header": {
        "ru": "📊 Результаты",
        "uk": "📊 Результати",
        "en": "📊 Results",
    },
    "autosave_error": {
        "ru": "Ошибка автосохранения Excel",
        "uk": "Помилка автозбереження Excel",
        "en": "Excel auto-save failed",
    },
    "download_excel": {
        "ru": "📥 Скачать Excel",
        "uk": "📥 Завантажити Excel",
        "en": "📥 Download Excel",
    },
    "export_error": {
        "ru": "Ошибка подготовки экспорта",
        "uk": "Помилка підготовки експорту",
        "en": "Failed to prepare export",
    },
    "download_csv": {
        "ru": "📥 Скачать CSV",
        "uk": "📥 Завантажити CSV",
        "en": "📥 Download CSV",
    },
    "scroll_to_top_label": {
        "ru": "Наверх",
        "uk": "Нагору",
        "en": "Back to top",
    },
    "csv_error": {
        "ru": "Ошибка подготовки CSV",
        "uk": "Помилка підготовки CSV",
        "en": "Failed to prepare CSV",
    },
    "total_keywords_stat": {
        "ru": "Всего уникальных слов: {count} | Обработано источников: {sources}",
        "uk": "Всього унікальних слів: {count} | Оброблено джерел: {sources}",
        "en": "Total unique keywords: {count} | Sources processed: {sources}",
    },
    "scraping_preview": {
        "ru": "🔍 Предпросмотр скрапинга",
        "uk": "🔍 Попередній перегляд скрапінгу",
        "en": "🔍 Scraping preview",
    },
    "keyword_selection_header": {
        "ru": "🔑 Выбор ключевых слов",
        "uk": "🔑 Вибір ключових слів",
        "en": "🔑 Keyword selection",
    },
    "select_keywords_desc": {
        "ru": "Выберите ключевые слова для генерации SEO текстов:",
        "uk": "Оберіть ключові слова для генерації SEO текстів:",
        "en": "Select the keywords to use for SEO text generation:",
    },
    "add_keyword_manual": {
        "ru": "➕ Добавить свои ключевые слова (одно ключевое слово на строку)",
        "uk": "➕ Додати свої ключові слова (одне ключове слово на рядок)",
        "en": "➕ Add your own keywords (one keyword per line)",
    },
    "for_which_url": {
        "ru": "Для какого URL добавить?",
        "uk": "Для якого URL додати?",
        "en": "Which URL should receive this keyword?",
    },
    "add_button": {
        "ru": "Добавить",
        "uk": "Додати",
        "en": "Add",
    },
    "keywords_count": {
        "ru": "ключевых слов",
        "uk": "ключових слів",
        "en": "keywords",
    },
    "select_all": {
        "ru": "Выбрать все",
        "uk": "Обрати все",
        "en": "Select all",
    },
    "selected_keywords_stat": {
        "ru": "Выбрано ключевых слов: {selected} из {total} для {urls} URL",
        "uk": "Обрано ключових слів: {selected} з {total} для {urls} URL",
        "en": "Selected keywords: {selected} of {total} for {urls} URLs",
    },
    "keyword_ideas_header": {
        "ru": "💡 Идеи ключевых слов Keyword Planner",
        "uk": "💡 Ідеї ключових слів Keyword Planner",
        "en": "💡 Keyword Planner ideas",
    },
    "keyword_ideas_desc": {
        "ru": "Сгенерируйте дополнительные идеи ключевых слов из Google Keyword Planner перед переходом к генерации SEO-текстов.",
        "uk": "Згенеруйте додаткові ідеї ключових слів із Google Keyword Planner перед переходом до генерації SEO-текстів.",
        "en": "Generate additional keyword ideas from Google Keyword Planner before moving on to SEO text generation.",
    },
    "keyword_ideas_seed_keywords": {
        "ru": "Ключевые слова для KeywordSeed",
        "uk": "Ключові слова для KeywordSeed",
        "en": "KeywordSeed keywords",
    },
    "keyword_ideas_seed_keywords_stat": {
        "ru": "Выбрано для KeywordSeed: {selected} из {total} (лимит запроса: {limit})",
        "uk": "Обрано для KeywordSeed: {selected} з {total} (ліміт запиту: {limit})",
        "en": "Selected for KeywordSeed: {selected} of {total} (request limit: {limit})",
    },
    "use_url_as_seed": {
        "ru": "Использовать URL как seed",
        "uk": "Використовувати URL як seed",
        "en": "Use URL as seed",
    },
    "keyword_only_seed": {
        "ru": "Только ключевые слова",
        "uk": "Лише ключові слова",
        "en": "Keywords only",
    },
    "generate_keyword_ideas_button": {
        "ru": "💡 Сгенерировать идеи Keyword Planner",
        "uk": "💡 Згенерувати ідеї Keyword Planner",
        "en": "💡 Generate Keyword Planner ideas",
    },
    "keyword_ideas_generating": {
        "ru": "Генерация идей ключевых слов...",
        "uk": "Генерація ідей ключових слів...",
        "en": "Generating keyword ideas...",
    },
    "keyword_ideas_processing_url": {
        "ru": "Обработка {url} | Режим: {mode}",
        "uk": "Обробка {url} | Режим: {mode}",
        "en": "Processing {url} | Mode: {mode}",
    },
    "keyword_ideas_skip_no_seed_keywords": {
        "ru": "Пропуск {url}: не выбрано ни одного ключевого слова для KeywordSeed.",
        "uk": "Пропуск {url}: не обрано жодного ключового слова для KeywordSeed.",
        "en": "Skipping {url}: no keywords selected for KeywordSeed.",
    },
    "keyword_ideas_seed_limit_notice": {
        "ru": "Для {url} выбрано {selected} ключевых слов. Google Ads поддерживает только {limit}, поэтому будут использованы первые {used}.",
        "uk": "Для {url} обрано {selected} ключових слів. Google Ads підтримує лише {limit}, тому буде використано перші {used}.",
        "en": "Selected {selected} keywords for {url}. Google Ads supports only {limit}, so the first {used} will be used.",
    },
    "keyword_ideas_generation_complete": {
        "ru": "Идеи Keyword Planner сгенерированы.",
        "uk": "Ідеї Keyword Planner згенеровано.",
        "en": "Keyword ideas generated.",
    },
    "keyword_ideas_empty": {
        "ru": "Keyword Planner не вернул новых идей для выбранного seed-режима.",
        "uk": "Keyword Planner не повернув нових ідей для вибраного seed-режиму.",
        "en": "Keyword Planner returned no ideas for the selected seed mode.",
    },
    "keyword_ideas_add_button": {
        "ru": "Добавить выбранные идеи в список ключевых слов",
        "uk": "Додати вибрані ідеї до списку ключових слів",
        "en": "Add selected ideas to the keyword list",
    },
    "keyword_ideas_select_warning": {
        "ru": "Выберите хотя бы одну идею перед добавлением.",
        "uk": "Оберіть хоча б одну ідею перед додаванням.",
        "en": "Select at least one idea before adding it.",
    },
    "keyword_ideas_added_success": {
        "ru": "Добавлено идей ключевых слов: {count}",
        "uk": "Додано ідей ключових слів: {count}",
        "en": "Added keyword ideas: {count}",
    },
    "seo_generation_header": {
        "ru": "📝 Генерация SEO текстов",
        "uk": "📝 Генерація SEO текстів",
        "en": "📝 SEO text generation",
    },
    "seo_generation_desc": {
        "ru": "Генерация SEO текста из выбранных ключевых слов.",
        "uk": "Генерація SEO тексту з обраних ключових слів.",
        "en": "Generate SEO text from the selected keywords.",
    },
    "generate_seo_button": {
        "ru": "✨ Сгенерировать SEO тексты",
        "uk": "✨ Згенерувати SEO тексти",
        "en": "✨ Generate SEO texts",
    },
    "generating": {
        "ru": "Генерация текстов...",
        "uk": "Генерація текстів...",
        "en": "Generating texts...",
    },
    "generating_progress": {
        "ru": "Генерация...",
        "uk": "Генерація...",
        "en": "Generating...",
    },
    "generating_url": {
        "ru": "Генерация {idx}/{total}: {url}",
        "uk": "Генерація {idx}/{total}: {url}",
        "en": "Generating {idx}/{total}: {url}",
    },
    "processing_url": {
        "ru": "Обработка: {url}",
        "uk": "Обробка: {url}",
        "en": "Processing: {url}",
    },
    "no_content_for_url": {
        "ru": "Нет контента для {url}",
        "uk": "Немає контенту для {url}",
        "en": "No content available for {url}",
    },
    "generation_complete": {
        "ru": "Генерация завершена!",
        "uk": "Генерацію завершено!",
        "en": "Generation complete!",
    },
    "seo_success": {
        "ru": "SEO тексты успешно сгенерированы! Смотрите результаты ниже.",
        "uk": "SEO тексти успішно згенеровано! Дивіться результати нижче.",
        "en": "SEO texts were generated successfully. See the results below.",
    },
    "seo_results_header": {
        "ru": "📝 Результаты генерации текстов",
        "uk": "📝 Результати генерації текстів",
        "en": "📝 SEO text results",
    },
    "seo_results_desc": {
        "ru": "Сгенерированный текст и контроли перегенерации.",
        "uk": "Згенерований текст та керування перегенерацією.",
        "en": "Generated text and regeneration controls.",
    },
    "regenerate_seo_button": {
        "ru": "🔄 Перегенерировать (без кэша)",
        "uk": "🔄 Перегенерувати (без кешу)",
        "en": "🔄 Regenerate (bypass cache)",
    },
    "regenerate_seo_started": {
        "ru": "Перегенерация SEO-текстов (кэш игнорируется)...",
        "uk": "Перегенерація SEO-текстів (кеш ігнорується)...",
        "en": "Regenerating SEO texts (cache bypassed)...",
    },
    "regenerate_seo_success": {
        "ru": "SEO-тексты перегенерированы",
        "uk": "SEO-тексти перегенеровані",
        "en": "SEO texts regenerated",
    },
    "download_texts_excel": {
        "ru": "📥 Скачать тексты (Excel)",
        "uk": "📥 Завантажити тексти (Excel)",
        "en": "📥 Download texts (Excel)",
    },
    "download_texts_csv": {
        "ru": "📥 Скачать тексты (CSV)",
        "uk": "📥 Завантажити тексти (CSV)",
        "en": "📥 Download texts (CSV)",
    },
    "seo_autosave_error": {
        "ru": "Ошибка автосохранения SEO текстов",
        "uk": "Помилка автозбереження SEO текстів",
        "en": "SEO text auto-save failed",
    },
    "export_error_generic": {
        "ru": "Ошибка экспорта",
        "uk": "Помилка експорту",
        "en": "Export failed",
    },
    "csv_export_error": {
        "ru": "Ошибка CSV экспорта",
        "uk": "Помилка CSV експорту",
        "en": "CSV export failed",
    },
    "history_header": {
        "ru": "📜 История запросов",
        "uk": "📜 Історія запитів",
        "en": "📜 Request history",
    },
    "history_empty": {
        "ru": "История пуста.",
        "uk": "Історія порожня.",
        "en": "History is empty.",
    },
    "no_logs_yet": {
        "ru": "Логов пока нет.",
        "uk": "Логів поки немає.",
        "en": "No logs yet.",
    },
    "chars": {
        "ru": "символов",
        "uk": "символів",
        "en": "characters",
    },
    "col_keywords": {
        "ru": "Ключевые слова",
        "uk": "Ключові слова",
        "en": "Keywords",
    },
    "col_seo_text": {
        "ru": "SEO текст",
        "uk": "SEO текст",
        "en": "SEO text",
    },
    "workflow_mode_label": {
        "ru": "Режим сценария",
        "uk": "Режим сценарію",
        "en": "Workflow mode",
    },
    "workflow_mode_url_llm": {
        "ru": "URL -> LLM -> Ads",
        "uk": "URL -> LLM -> Ads",
        "en": "URL -> LLM -> Ads",
    },
    "workflow_mode_url_seed": {
        "ru": "URL -> Идеи Ads",
        "uk": "URL -> Ідеї Ads",
        "en": "URL -> Ads ideas",
    },
    "workflow_mode_keyword_seed": {
        "ru": "Ключевые слова -> Идеи Ads",
        "uk": "Ключові слова -> Ідеї Ads",
        "en": "Keyword seed -> Ads ideas",
    },
    "keyword_seed_header": {
        "ru": "1. Ввод ключевых слов",
        "uk": "1. Введення ключових слів",
        "en": "1. Keyword input",
    },
    "keyword_seed_placeholder": {
        "ru": "Введите по одному ключевому слову на строку",
        "uk": "Введіть по одному ключовому слову на рядок",
        "en": "Enter one keyword per line",
    },
    "keywords_restrict_to_input": {
        "ru": "Ограничить вывод только введёнными ключевыми словами",
        "uk": "Обмежити вивід лише введеними ключовими словами",
        "en": "Restrict output to input keywords only",
    },
    "keywords_restrict_to_input_help": {
        "ru": "Убрать идеи Google Ads, которых нет в вашем списке (без синонимов и похожих ключей). Применяется к режиму «Ключевые → идеи Ads».",
        "uk": "Прибрати ідеї Google Ads, яких немає у вашому списку (без синонімів та схожих ключів). Застосовується до режиму «Ключові → ідеї Ads».",
        "en": "Drop Google Ads ideas that are not in your input list (no synonyms or similar keywords). Applies to the Keyword → Ads ideas workflow.",
    },
    "keyword_seed_warning": {
        "ru": "Пожалуйста, введите хотя бы одно ключевое слово.",
        "uk": "Будь ласка, введіть хоча б одне ключове слово.",
        "en": "Please enter at least one keyword seed.",
    },
    "url_seed_start_seo": {
        "ru": "Перейти к написанию SEO текста",
        "uk": "Перейти до написання SEO тексту",
        "en": "Continue to SEO",
    },
    "url_seed_start_seo_help": {
        "ru": "Скрапинг выбранных URL запустится только тогда, когда вы будете готовы генерировать SEO-текст.",
        "uk": "Скрапінг вибраних URL запуститься лише тоді, коли ви будете готові генерувати SEO-текст.",
        "en": "Scraping for the selected URLs will start only when you are ready to generate SEO text.",
    },
    "keyword_seed_source_label": {
        "ru": "Ручной ввод ключевых слов",
        "uk": "Ручне введення ключових слів",
        "en": "Manual keyword input",
    },
    "history_restore_checkpoint": {
        "ru": "Восстановить checkpoint",
        "uk": "Відновити checkpoint",
        "en": "Restore checkpoint",
    },
    "history_restore_success": {
        "ru": "Checkpoint из истории восстановлен.",
        "uk": "Checkpoint з історії відновлено.",
        "en": "Checkpoint restored from history.",
    },
    "history_regenerate_keywords": {
        "ru": "Перегенерировать ключевые слова",
        "uk": "Перегенерувати ключові слова",
        "en": "Regenerate keywords",
    },
    "history_show_cache_records": {
        "ru": "Показать записи кеша",
        "uk": "Показати записи кешу",
        "en": "Show cache records",
    },
    "history_hide_cache_records": {
        "ru": "Скрыть записи кеша",
        "uk": "Приховати записи кешу",
        "en": "Hide cache records",
    },
    "history_cache_title_prefix": {
        "ru": "Кеш",
        "uk": "Кеш",
        "en": "Cache",
    },
    "history_cache_kind_label": {
        "ru": "Тип",
        "uk": "Тип",
        "en": "Type",
    },
    "history_cache_provider_label": {
        "ru": "Провайдер",
        "uk": "Провайдер",
        "en": "Provider",
    },
    "history_cache_key_label": {
        "ru": "Ключ",
        "uk": "Ключ",
        "en": "Key",
    },
    "history_cache_hits_label": {
        "ru": "Хиты",
        "uk": "Хіти",
        "en": "Hits",
    },
    "history_card_kind_serp": {
        "ru": "SERP-анализ",
        "uk": "SERP-аналіз",
        "en": "SERP Analysis",
    },
    "history_card_kind_ads": {
        "ru": "Google Ads запрос",
        "uk": "Google Ads запит",
        "en": "Google Ads Query",
    },
    "history_card_kind_llm_extract": {
        "ru": "LLM извлечение ключевых слов",
        "uk": "LLM збір ключових слів",
        "en": "LLM Keyword Extraction",
    },
    "history_card_kind_llm_generate": {
        "ru": "LLM генерация SEO текста",
        "uk": "LLM генерація SEO тексту",
        "en": "LLM SEO Text Generation",
    },
    "history_card_kind_crawl": {
        "ru": "Скрапинг страниц",
        "uk": "Скрапінг сторінок",
        "en": "Page Crawling",
    },
    "history_card_kind_math": {
        "ru": "Математический SEO-анализ",
        "uk": "Математичний SEO-аналіз",
        "en": "SEO Math Analysis",
    },
    "history_card_kind_trends": {
        "ru": "Google Trends",
        "uk": "Google Trends",
        "en": "Google Trends",
    },
    "history_card_kind_model_fetch": {
        "ru": "Загрузка моделей",
        "uk": "Завантаження моделей",
        "en": "Model Fetch",
    },
    "history_card_kind_unknown": {
        "ru": "Кеш-запись",
        "uk": "Кеш-запис",
        "en": "Cache Record",
    },
    "history_restore_cache": {
        "ru": "Восстановить из кеша",
        "uk": "Відновити з кешу",
        "en": "Restore from cache",
    },
    "history_restore_cache_success": {
        "ru": "Данные восстановлены из кеша.",
        "uk": "Дані відновлено з кешу.",
        "en": "Data restored from cache.",
    },
    "history_restore_cache_unsupported": {
        "ru": "Этот тип кеша не поддерживает восстановление.",
        "uk": "Цей тип кешу не підтримує відновлення.",
        "en": "This cache type does not support restoration.",
    },
    "history_card_cache_request_summary": {
        "ru": "Параметры запроса",
        "uk": "Параметри запиту",
        "en": "Request parameters",
    },
    "history_card_cache_keywords_count": {
        "ru": "Ключевых слов в запросе",
        "uk": "Ключових слів у запиті",
        "en": "Keywords in request",
    },
    "history_card_cache_urls_count": {
        "ru": "URL в запросе",
        "uk": "URL у запиті",
        "en": "URLs in request",
    },
    # --- Human-friendly history card labels ---
    "history_card_process_type": {
        "ru": "Процесс",
        "uk": "Процес",
        "en": "Process",
    },
    "history_card_status": {
        "ru": "Статус",
        "uk": "Статус",
        "en": "Status",
    },
    "history_card_status_success": {
        "ru": "✅ Успешно",
        "uk": "✅ Успішно",
        "en": "✅ Success",
    },
    "history_card_status_error": {
        "ru": "❌ Ошибка",
        "uk": "❌ Помилка",
        "en": "❌ Error",
    },
    "history_card_status_partial": {
        "ru": "⚠️ Частично",
        "uk": "⚠️ Частково",
        "en": "⚠️ Partial",
    },
    "history_card_status_cached": {
        "ru": "💾 Из кеша",
        "uk": "💾 З кешу",
        "en": "💾 Cached",
    },
    "history_card_processed_data": {
        "ru": "Обработанные данные",
        "uk": "Оброблені дані",
        "en": "Processed data",
    },
    "history_card_urls": {
        "ru": "URL-адреса",
        "uk": "URL-адреси",
        "en": "URLs",
    },
    "history_card_keywords": {
        "ru": "Ключевые слова",
        "uk": "Ключові слова",
        "en": "Keywords",
    },
    "history_card_keyword_preview_more": {
        "ru": "ещё {count}",
        "uk": "ще {count}",
        "en": "{count} more",
    },
    "history_card_timestamp": {
        "ru": "Время",
        "uk": "Час",
        "en": "Time",
    },
    "history_card_cache_provider": {
        "ru": "Провайдер кеша",
        "uk": "Провайдер кешу",
        "en": "Cache provider",
    },
    "history_card_cache_hits": {
        "ru": "Использований кеша",
        "uk": "Використань кешу",
        "en": "Cache hits",
    },
    "history_card_cache_kind": {
        "ru": "Тип кеша",
        "uk": "Тип кешу",
        "en": "Cache type",
    },
    "history_card_no_data": {
        "ru": "Нет данных для отображения",
        "uk": "Немає даних для відображення",
        "en": "No data to display",
    },
    "history_card_workflow_url_llm": {
        "ru": "URL → LLM → Google Ads",
        "uk": "URL → LLM → Google Ads",
        "en": "URL → LLM → Google Ads",
    },
    "history_card_workflow_url_seed": {
        "ru": "URL → Идеи Google Ads",
        "uk": "URL → Ідеї Google Ads",
        "en": "URL → Google Ads Ideas",
    },
    "history_card_workflow_keyword_seed": {
        "ru": "Ключевые слова → Google Ads",
        "uk": "Ключові слова → Google Ads",
        "en": "Keywords → Google Ads",
    },
    "history_card_workflow_serp_analysis": {
        "ru": "SERP-анализ",
        "uk": "SERP-аналіз",
        "en": "SERP Analysis",
    },
    "history_card_workflow_keyword_llm": {
        "ru": "Ключевые слова → LLM SEO текст",
        "uk": "Ключові слова → LLM SEO текст",
        "en": "Keywords → LLM SEO Text",
    },
    "history_card_workflow_unknown": {
        "ru": "Неизвестный процесс",
        "uk": "Невідомий процес",
        "en": "Unknown process",
    },
    "history_card_record_type_history": {
        "ru": "Запись истории",
        "uk": "Запис історії",
        "en": "History record",
    },
    "history_card_record_type_cache": {
        "ru": "Запись кеша",
        "uk": "Запис кешу",
        "en": "Cache record",
    },
    "history_filter_all": {
        "ru": "Все записи",
        "uk": "Усі записи",
        "en": "All records",
    },
    "history_filter_history": {
        "ru": "Только история",
        "uk": "Тільки історія",
        "en": "History only",
    },
    "history_filter_cache": {
        "ru": "Только кеш",
        "uk": "Тільки кеш",
        "en": "Cache only",
    },
    "history_load_more": {
        "ru": "Загрузить ещё ({remaining} осталось)",
        "uk": "Завантажити ще ({remaining} залишилось)",
        "en": "Load more ({remaining} remaining)",
    },
    "history_showing_all": {
        "ru": "Показаны все записи",
        "uk": "Показано всі записи",
        "en": "Showing all records",
    },
    # --- Merged Report Export ---
    "export_merged_report": {
        "ru": "Экспорт объединенного отчета",
        "uk": "Експорт об'єднаного звіту",
        "en": "Export merged report",
    },
    "export_merged_report_success": {
        "ru": "Объединенный отчет успешно экспортирован",
        "uk": "Об'єднаний звіт успішно експортовано",
        "en": "Merged report exported successfully",
    },
    # --- SERP Analysis ---
    "serp_mode_label": {
        "ru": "Анализ SERP",
        "uk": "Аналіз SERP",
        "en": "SERP Analysis",
    },
    "crawl_mode_label": {
        "ru": "Отчет сканирования",
        "uk": "Звіт сканування",
        "en": "Crawl Report",
    },
    "crawl_seed_input_header": {
        "ru": "1. Введите URL для отчета сканирования",
        "uk": "1. Введіть URL-адреси для звіту сканування",
        "en": "1. Enter URLs for crawl report",
    },
    "crawl_seed_input_placeholder": {
        "ru": "Введите URL (по одному на строку)",
        "uk": "Введіть URL-адреси (по одному на рядок)",
        "en": "Enter URLs (one per line)",
    },
    "crawl_no_seed_urls": {
        "ru": "Введите хотя бы один URL для отчета сканирования.",
        "uk": "Введіть хоча б одну URL-адресу для звіту сканування.",
        "en": "Enter at least one URL for the crawl report.",
    },
    "crawl_running": {
        "ru": "Выполняется анализ сканирования для {count} URL...",
        "uk": "Виконується аналіз сканування для {count} URL-адрес...",
        "en": "Running crawl analysis for {count} URL(s)...",
    },
    "crawl_report_complete": {
        "ru": "Отчет сканирования готов: {count} страниц(ы).",
        "uk": "Звіт сканування завершено: {count} сторінок.",
        "en": "Crawl report complete: {count} page(s).",
    },
    "crawl_report_header": {
        "ru": "Математический отчет сканирования",
        "uk": "Математичний звіт сканування",
        "en": "Crawl Mathematical Report",
    },
    "crawl_pages_stat": {
        "ru": "Страницы",
        "uk": "Сторінки",
        "en": "Pages",
    },
    "crawl_visited_stat": {
        "ru": "Посещено",
        "uk": "Відвідано",
        "en": "Visited",
    },
    "crawl_errors_stat": {
        "ru": "Ошибки",
        "uk": "Помилки",
        "en": "Errors",
    },
    "crawl_aggregate_terms": {
        "ru": "Топ терминов сайта",
        "uk": "Топ термінів сайту",
        "en": "Top Site Terms",
    },
    "crawl_ngram_details": {
        "ru": "Детали N-грамм",
        "uk": "Деталі N-грам",
        "en": "N-gram Details",
    },
    "crawl_page_details": {
        "ru": "Страницы отчета",
        "uk": "Сторінки звіту",
        "en": "Report Pages",
    },
    "crawl_page_title_label": {
        "ru": "Заголовок страницы",
        "uk": "Заголовок сторінки",
        "en": "Title",
    },
    "crawl_page_url_label": {
        "ru": "URL",
        "uk": "URL",
        "en": "URL",
    },
    "crawl_page_meta_description_label": {
        "ru": "Мета-описание",
        "uk": "Мета-опис",
        "en": "Meta description",
    },
    "crawl_page_heading_count_label": {
        "ru": "Количество заголовков",
        "uk": "Кількість заголовків",
        "en": "Heading count",
    },
    "crawl_page_headings_label": {
        "ru": "Заголовки",
        "uk": "Заголовки",
        "en": "Headings",
    },
    "crawl_page_analysis_evidence_label": {
        "ru": "Доказательства анализа",
        "uk": "Докази аналізу",
        "en": "Analysis evidence",
    },
    "crawl_page_intent_label": {
        "ru": "Интент",
        "uk": "Інтент",
        "en": "Intent",
    },
    "crawl_page_tfidf_terms_label": {
        "ru": "Топ TF-IDF термины",
        "uk": "Топ TF-IDF терміни",
        "en": "Top TF-IDF terms",
    },
    "crawl_page_top_ngrams_label": {
        "ru": "Топ N-граммы",
        "uk": "Топ N-грами",
        "en": "Top n-grams",
    },
    "crawl_select_keywords": {
        "ru": "Выберите скрапинг-ключевые слова для SERP или Ads",
        "uk": "Виберіть скрапінг-ключові слова для SERP або Ads",
        "en": "Select crawl keywords for SERP or Ads",
    },
    "crawl_settings_header": {
        "ru": "Настройки скрапера",
        "uk": "Налаштування скрапера",
        "en": "Crawler Settings",
    },
    "crawl_enabled": {
        "ru": "Включить скрапинг-воркфлоу",
        "uk": "Увімкнути скрапінг-воркфлоу",
        "en": "Enable crawler workflow",
    },
    "crawl_enabled_help": {
        "ru": "Скрапер опционален и применяет строгие ограничения на размер ответа и обход только того же домена.",
        "uk": "Скрапер опціональний і застосовує суворі обмеження на розмір відповіді та обхід лише того самого домену.",
        "en": "Crawler is opt-in and uses strict same-domain and response-size limits.",
    },
    "crawl_max_pages": {
        "ru": "Макс. страниц для скрапинга",
        "uk": "Макс. сторінок для скрапінгу",
        "en": "Max crawl pages",
    },
    "crawl_max_pages_help": {
        "ru": "Максимальное количество страниц для скрапинга (включая связанные страницы)",
        "uk": "Максимальна кількість сторінок для скрапінгу (включаючи пов'язані сторінки)",
        "en": "Maximum number of pages to crawl (including linked pages)",
    },
    "crawl_max_depth": {
        "ru": "Макс. глубина скрапинга",
        "uk": "Макс. глибина скрапінгу",
        "en": "Max crawl depth",
    },
    "crawl_same_domain_only": {
        "ru": "В пределах того же домена",
        "uk": "У межах того самого домену",
        "en": "Same domain only",
    },
    "crawl_timeout_seconds": {
        "ru": "Тайм-аут сканирования (секунды)",
        "uk": "Тайм-аут сканування (секунди)",
        "en": "Crawl timeout (seconds)",
    },
    "crawl_max_response_bytes": {
        "ru": "Макс. байт ответа",
        "uk": "Макс. байт відповіді",
        "en": "Max response bytes",
    },
    "crawl_max_retries": {
        "ru": "Макс. попыток сканирования",
        "uk": "Макс. спроб сканування",
        "en": "Max crawl retries",
    },
    "crawl_disabled_warning": {
        "ru": "Сначала включите рабочий процесс сканирования в настройках боковой панели.",
        "uk": "Спочатку увімкніть робочий процес сканування в налаштуваннях бічної панелі.",
        "en": "Enable crawler workflow in sidebar settings first.",
    },
    "serp_keyword_input_header": {
        "ru": "1. Ввод ключевых слов для SERP",
        "uk": "1. Введення ключових слів для SERP",
        "en": "1. Enter keywords for SERP analysis",
    },
    "serp_keyword_input_placeholder": {
        "ru": "Введите ключевые слова (по одному на строку)",
        "uk": "Введіть ключові слова (по одному на рядок)",
        "en": "Enter keywords (one per line)",
    },
    "serp_no_api_key": {
        "ru": "API ключ для SERP не настроен. Проверьте .env.",
        "uk": "API ключ для SERP не налаштовано. Перевірте .env.",
        "en": "SERP API key not configured. Check your .env file.",
    },
    "serp_results_header": {
        "ru": "📊 Результаты SERP анализа",
        "uk": "📊 Результати SERP аналізу",
        "en": "📊 SERP Analysis Results",
    },
    "serp_organic_header": {
        "ru": "Органические результаты",
        "uk": "Органічні результати",
        "en": "Organic Results",
    },
    "serp_position_col": {
        "ru": "Позиция",
        "uk": "Позиція",
        "en": "Position",
    },
    "serp_title_col": {
        "ru": "Заголовок",
        "uk": "Заголовок",
        "en": "Title",
    },
    "serp_url_col": {
        "ru": "URL",
        "uk": "URL",
        "en": "URL",
    },
    "serp_snippet_col": {
        "ru": "Сниппет",
        "uk": "Сніппет",
        "en": "Snippet",
    },
    "serp_provider_col": {
        "ru": "Провайдер",
        "uk": "Провайдер",
        "en": "Provider",
    },
    # --- Phase 9 Column Names ---
    "url_match_type_col": {
        "ru": "Тип совпадения URL",
        "uk": "Тип збігу URL",
        "en": "URL Match Type",
    },
    "matched_source_url_col": {
        "ru": "Совпадающий URL источника",
        "uk": "Відповідна URL-адреса джерела",
        "en": "Matched Source URL",
    },
    "matched_source_domain_col": {
        "ru": "Совпадающий домен источника",
        "uk": "Відповідна домен джерела",
        "en": "Matched Source Domain",
    },
    "page_url_in_serp_col": {
        "ru": "URL страницы в SERP",
        "uk": "URL-адреса сторінки в SERP",
        "en": "Page URL in SERP",
    },
    "serp_rank_col": {
        "ru": "Позиция в SERP",
        "uk": "Позиція в SERP",
        "en": "SERP Rank",
    },
    # --- Original Phase 2 SERP strings ---
    "serp_related_header": {
        "ru": "🔗 Похожие запросы",
        "uk": "🔗 Схожі запити",
        "en": "🔗 Related Searches",
    },
    "serp_paa_header": {
        "ru": "❓ Люди также спрашивают",
        "uk": "❓ Люди також запитують",
        "en": "❓ People Also Ask",
    },
    "serp_no_results": {
        "ru": "SERP результаты не найдены.",
        "uk": "SERP результатів не знайдено.",
        "en": "No SERP results found.",
    },
    "serp_keyword_warning": {
        "ru": "Пожалуйста, введите хотя бы одно ключевое слово.",
        "uk": "Будь ласка, введіть хоча б одне ключове слово.",
        "en": "Please enter at least one keyword.",
    },
    "serp_querying": {
        "ru": "Запрос SERP данных для {count} ключевых слов...",
        "uk": "Запит SERP даних для {count} ключових слів...",
        "en": "Querying SERP data for {count} keywords...",
    },
    "serp_querying_keyword": {
        "ru": "Анализ {idx}/{total}: {keyword}",
        "uk": "Аналіз {idx}/{total}: {keyword}",
        "en": "Analyzing {idx}/{total}: {keyword}",
    },
    "serp_analysis_complete": {
        "ru": "SERP анализ завершен!",
        "uk": "SERP аналіз завершено!",
        "en": "SERP analysis complete!",
    },
    "serp_total_stat": {
        "ru": "Всего результатов: {count} для {keywords} ключевых слов",
        "uk": "Всього результатів: {count} для {keywords} ключових слів",
        "en": "Total results: {count} for {keywords} keywords",
    },
    "serp_export_related": {
        "ru": "Экспорт похожих запросов",
        "uk": "Експорт схожих запитів",
        "en": "Export Related Data",
    },
    "serp_export_related_csv": {
        "ru": "Скачать CSV (похожие запросы)",
        "uk": "Завантажити CSV (схожі запити)",
        "en": "Download CSV (Related Data)",
    },
    "serp_chain_header": {
        "ru": "🔗 Отправить в Ads",
        "uk": "🔗 Надіслати в Ads",
        "en": "🔗 Chain to Ads",
    },
    "serp_chain_select_all": {
        "ru": "Выбрать все запросы",
        "uk": "Вибрати всі запити",
        "en": "Select all queries",
    },
    "serp_chain_button": {
        "ru": "Анализировать выбранные запросы в Google Ads",
        "uk": "Аналізувати обрані запити в Google Ads",
        "en": "Analyze selected queries in Google Ads",
    },
    "serp_chain_no_queries": {
        "ru": "Нет выбранных запросов для анализа.",
        "uk": "Немає обраних запитів для аналізу.",
        "en": "No queries selected for analysis.",
    },
    "serp_chain_selected_stat": {
        "ru": "Выбрано: {selected} из {total} запросов",
        "uk": "Обрано: {selected} з {total} запитів",
        "en": "Selected: {selected} of {total} queries",
    },
    "serp_chain_querying": {
        "ru": "Запрос Ads метрик для {count} ключевых слов...",
        "uk": "Запит Ads метрик для {count} ключових слів...",
        "en": "Querying Ads metrics for {count} keywords...",
    },
    "serp_chain_complete": {
        "ru": "Ads анализ завершен! Найдено {count} ключевых слов с метриками.",
        "uk": "Ads аналіз завершено! Знайдено {count} ключових слів з метриками.",
        "en": "Ads analysis complete! Found {count} keywords with metrics.",
    },
    "serp_chain_results_header": {
        "ru": "📊 Результаты Ads анализа (из SERP)",
        "uk": "📊 Результати Ads аналізу (з SERP)",
        "en": "📊 Ads Analysis Results (from SERP)",
    },
    "serp_chain_limit_notice": {
        "ru": "Лимит Google Ads: использовано {used} из {selected} выбранных запросов.",
        "uk": "Ліміт Google Ads: використано {used} з {selected} обраних запитів.",
        "en": "Google Ads limit: using {used} of {selected} selected queries.",
    },
    "serp_chain_empty": {
        "ru": "Ads результаты не найдены для выбранных запросов.",
        "uk": "Ads результатів не знайдено для обраних запитів.",
        "en": "No Ads results found for selected queries.",
    },
    # --- Dynamic Models & Custom Providers ---
    "model_refresh_button": {
        "ru": "🔄 Обновить модели",
        "uk": "🔄 Оновити моделі",
        "en": "🔄 Refresh models",
    },
    "model_refreshing": {
        "ru": "Обновление списка моделей...",
        "uk": "Оновлення списку моделей...",
        "en": "Refreshing model list...",
    },
    "model_refresh_complete": {
        "ru": "Модели обновлены! Загружено для {count} провайдеров.",
        "uk": "Моделі оновлено! Завантажено для {count} провайдерів.",
        "en": "Models refreshed! Loaded for {count} providers.",
    },
    "model_refresh_error": {
        "ru": "Ошибка обновления моделей",
        "uk": "Помилка оновлення моделей",
        "en": "Error refreshing models",
    },
    "model_select_label": {
        "ru": "Выберите модель",
        "uk": "Оберіть модель",
        "en": "Select model",
    },
    "model_manual_entry": {
        "ru": "Ввести модель вручную",
        "uk": "Ввести модель вручну",
        "en": "Enter model manually",
    },
    "model_no_models_cached": {
        "ru": "Нет кэшированных моделей. Нажмите «Обновить модели».",
        "uk": "Немає кешованих моделей. Натисніть «Оновити моделі».",
        "en": "No cached models. Click 'Refresh models'.",
    },
    "custom_provider_header": {
        "ru": "🔧 Пользовательский провайдер",
        "uk": "🔧 Користувацький провайдер",
        "en": "🔧 Custom provider",
    },
    "custom_provider_name": {
        "ru": "Название провайдера",
        "uk": "Назва провайдера",
        "en": "Provider name",
    },
    "custom_provider_base_url": {
        "ru": "Base URL (OpenAI-совместимый)",
        "uk": "Base URL (OpenAI-сумісний)",
        "en": "Base URL (OpenAI-compatible)",
    },
    "custom_provider_api_key_env": {
        "ru": "Имя переменной .env для API ключа",
        "uk": "Ім'я змінної .env для API ключа",
        "en": ".env variable name for API key",
    },
    "custom_provider_add_button": {
        "ru": "Добавить провайдер",
        "uk": "Додати провайдера",
        "en": "Add provider",
    },
    "custom_provider_remove": {
        "ru": "Удалить",
        "uk": "Видалити",
        "en": "Remove",
    },
    "custom_provider_validation_error": {
        "ru": "Ошибка: {error}",
        "uk": "Помилка: {error}",
        "en": "Error: {error}",
    },
    "custom_provider_duplicate_name": {
        "ru": "Провайдер «{name}» уже существует.",
        "uk": "Провайдер «{name}» вже існує.",
        "en": "Provider '{name}' already exists.",
    },
    # --- SERP UI & Model Search ---
    "serp_provider_header": {
        "ru": "🔍 Поставщик SERP",
        "uk": "🔍 Постачальник SERP",
        "en": "🔍 SERP Provider",
    },
    "serp_provider_select": {
        "ru": "Выберите поставщика",
        "uk": "Оберіть постачальника",
        "en": "Select provider",
    },
    "serp_no_keys": {
        "ru": "Нет ключей SERP API. Добавьте ключ в .env.",
        "uk": "Немає ключів SERP API. Додайте ключ у .env.",
        "en": "No SERP API keys. Add key to .env.",
    },
    "serp_num_results": {
        "ru": "Количество результатов",
        "uk": "Кількість результатів",
        "en": "Number of results",
    },
    "serp_location": {
        "ru": "Геолокация (gl)",
        "uk": "Геолокація (gl)",
        "en": "Geolocation (gl)",
    },
    "serp_language": {
        "ru": "Язык (hl)",
        "uk": "Мова (hl)",
        "en": "Language (hl)",
    },
    "model_search_placeholder": {
        "ru": "🔍 Поиск модели...",
        "uk": "🔍 Пошук моделі...",
        "en": "🔍 Search models...",
    },
    "serp_pre_step_label": {
        "ru": "Анализ SERP перед обработкой",
        "uk": "Аналіз SERP перед обробкою",
        "en": "SERP analysis before processing",
    },
    # --- SERP Advanced Options ---
    "serp_device": {
        "ru": "Устройство",
        "uk": "Пристрій",
        "en": "Device",
    },
    "serp_search_type": {
        "ru": "Тип поиска",
        "uk": "Тип пошуку",
        "en": "Search Type",
    },
    "serp_time_period": {
        "ru": "Период времени",
        "uk": "Період часу",
        "en": "Time Period",
    },
    "serp_safe_search": {
        "ru": "Безопасный поиск",
        "uk": "Безпечний пошук",
        "en": "Safe Search",
    },
    "serp_google_domain": {
        "ru": "Домен Google",
        "uk": "Домен Google",
        "en": "Google Domain",
    },
    "serp_city": {
        "ru": "Город (location)",
        "uk": "Місто (location)",
        "en": "City (location)",
    },
    "serp_uule": {
        "ru": "Закодированное местоположение (uule)",
        "uk": "Закодоване місцезнаходження (uule)",
        "en": "Encoded Location (uule)",
    },
    "serp_local_headless": {
        "ru": "Локальный SERP: запускать браузер headless",
        "uk": "Локальний SERP: запускати браузер headless",
        "en": "Local SERP: run browser headless",
    },
    # --- Workflow i18n for Task 6 (PLAN 08-01) ---
    "serp_needs_keywords_warning": {
        "ru": "SERP анализ доступен только после извлечения ключевых слов. Сначала запустите анализ.",
        "uk": "SERP аналіз доступний тільки після збору ключових слів. Спочатку запустіть аналіз.",
        "en": "SERP analysis is only available after keyword extraction. Run analysis first.",
    },
    "serp_no_keywords_eligible": {
        "ru": "Нет ключевых слов для SERP анализа (URL не поддерживаются).",
        "uk": "Немає ключових слів для SERP аналізу (URL не підтримуються).",
        "en": "No keywords available for SERP analysis (URLs not supported).",
    },
    "keyword_stage_ready": {
        "ru": "Ключевые слова извлечены. Теперь можно запустить SERP анализ и Google Ads.",
        "uk": "Ключові слова зібрано. Тепер можна запустити SERP аналіз і Google Ads.",
        "en": "Keywords extracted. You can now run SERP analysis and Google Ads.",
    },
    "select_keywords_for_serp": {
        "ru": "Выберите ключевые слова для SERP анализа",
        "uk": "Оберіть ключові слова для SERP аналізу",
        "en": "Select keywords for SERP analysis",
    },
    "send_selected_to_serp": {
        "ru": "Отправить выбранные в SERP",
        "uk": "Надіслати обрані в SERP",
        "en": "Send selected to SERP",
    },
    "serp_results_after_ads_header": {
        "ru": "SERP результаты после Ads",
        "uk": "SERP результати після Ads",
        "en": "SERP Results after Ads",
    },
    "serp_results_after_ads_desc": {
        "ru": "Связанные SERP результаты остаются видимыми после передачи в Ads.",
        "uk": "Пов'язані SERP результати залишаються видимими після переходу в Ads.",
        "en": "Chained SERP results stay visible after Ads handoff.",
    },
    "send_selected_to_ads": {
        "ru": "Отправить выбранные в Google Ads",
        "uk": "Надіслати обрані в Google Ads",
        "en": "Send selected to Google Ads",
    },
    "ads_then_serp": {
        "ru": "Сначала Ads, затем SERP",
        "uk": "Спочатку Ads, потім SERP",
        "en": "Ads first, then SERP",
    },
    "serp_then_ads": {
        "ru": "Сначала SERP, затем Ads",
        "uk": "Спочатку SERP, потім Ads",
        "en": "SERP first, then Ads",
    },
    "merged_ads_serp_header": {
        "en": "Merged Ads + SERP results",
        "ru": "Объединённые Ads + SERP",
        "uk": "Об'єднані Ads + SERP",
    },
    "merged_ads_serp_desc": {
        "en": "Ads metrics enriched with per-keyword SERP aggregates (merged into one file).",
        "ru": "Метрики Ads, обогащённые агрегатами SERP по ключевым словам (объединено в один файл).",
        "uk": "Метрики Ads, збагачені агрегатами SERP за ключовими словами (об'єднано в один файл).",
    },
    "merged_ads_trends_header": {
        "en": "Merged Ads + Trends results",
        "ru": "Объединённые Ads + Trends",
        "uk": "Об’єднані Ads + Trends",
    },
    "merged_ads_trends_desc": {
        "en": "Ads metrics enriched with per-keyword Google Trends interest (merged into one file).",
        "ru": "Метрики Ads, обогащённые интересом Google Trends по ключевым словам (объединено в один файл).",
        "uk": "Метрики Ads, збагачені інтересом Google Trends за ключовими словами (об’єднано в один файл).",
    },
    "trends_results_after_ads_header": {
        "en": "Google Trends after Ads",
        "ru": "Google Trends после Ads",
        "uk": "Google Trends після Ads",
    },
    "trends_results_after_ads_desc": {
        "en": "Trends metrics for keywords analyzed from the Ads selection.",
        "ru": "Метрики Trends для ключевых слов, отобранных из Ads.",
        "uk": "Метрики Trends для ключових слів, відібраних з Ads.",
    },
    "url_input_no_serp": {
        "ru": "URL нельзя отправить напрямую в SERP. Сначала извлеките ключевые слова.",
        "uk": "URL не можна надіслати безпосередньо в SERP. Спочатку зберіть ключові слова.",
        "en": "URL input cannot be sent directly to SERP. Extract keywords first.",
    },
    # SEO Math Analysis (Plan 08-02)
    "seo_math_header": {
        "ru": "Математический SEO анализ",
        "uk": "Математичний SEO аналіз",
        "en": "Mathematical SEO Analysis",
    },
    "seo_math_enabled": {
        "ru": "Включить математический анализ",
        "uk": "Увімкнути математичний аналіз",
        "en": "Enable mathematical analysis",
    },
    "seo_math_enabled_help": {
        "ru": "Анализировать SERP результаты с помощью n-gram, TF-IDF, co-occurrence и intent scoring",
        "uk": "Аналізувати SERP результати за допомогою n-gram, TF-IDF, co-occurrence та intent scoring",
        "en": "Analyze SERP results using n-grams, TF-IDF, co-occurrence, and intent scoring",
    },
    "seo_math_analyze_ngrams": {
        "ru": "Анализировать n-grams",
        "uk": "Аналізувати n-grams",
        "en": "Analyze n-grams",
    },
    "seo_math_analyze_tfidf": {
        "ru": "Анализировать TF-IDF",
        "uk": "Аналізувати TF-IDF",
        "en": "Analyze TF-IDF",
    },
    "seo_math_analyze_cooccurrence": {
        "ru": "Анализировать co-occurrence terms",
        "uk": "Аналізувати co-occurrence terms",
        "en": "Analyze co-occurrence terms",
    },
    "seo_math_analyze_intent": {
        "ru": "Анализировать search intent",
        "uk": "Аналізувати search intent",
        "en": "Analyze search intent",
    },
    "seo_math_analyze_generation_quality": {
        "ru": "Анализировать качество генерации",
        "uk": "Аналізувати якість генерації",
        "en": "Analyze generation quality",
    },
    "seo_math_analyze_generated_text": {
        "ru": "Мат-анализ сгенерированного текста",
        "uk": "Мат-аналіз згенерованого тексту",
        "en": "Math analysis of generated text",
    },
    "gen_math_report_header": {
        "ru": "Математический анализ сгенерированного текста",
        "uk": "Математичний аналіз згенерованого тексту",
        "en": "Mathematical Analysis of Generated Text",
    },
    "gen_math_report_desc": {
        "ru": "Агрегированный математический анализ из сгенерированного SEO текста.",
        "uk": "Агрегований математичний аналіз із згенерованого SEO тексту.",
        "en": "Aggregate math analysis from generated SEO text.",
    },
    "gen_math_no_text": {
        "ru": "Нет сгенерированного текста для анализа.",
        "uk": "Немає згенерованого тексту для аналізу.",
        "en": "No generated text available for analysis.",
    },
    "gen_math_corpus_source": {
        "ru": "Источник корпуса: сгенерированный SEO-текст",
        "uk": "Джерело корпусу: згенерований SEO-текст",
        "en": "Corpus source: generated SEO text",
    },
    "gen_math_url_label": {
        "ru": "URL",
        "uk": "URL",
        "en": "URL",
    },
    "gen_math_keyword_label": {
        "ru": "Ключевые слова",
        "uk": "Ключові слова",
        "en": "Keywords",
    },
    "gen_math_elements": {
        "ru": "Элементы текста",
        "uk": "Елементи тексту",
        "en": "Text elements",
    },
    "seo_math_advanced": {
        "ru": "Расширенные настройки",
        "uk": "Розширені налаштування",
        "en": "Advanced settings",
    },
    "seo_math_ngram_min": {
        "ru": "Мин. размер n-gram",
        "uk": "Мін. розмір n-gram",
        "en": "Min n-gram size",
    },
    "seo_math_ngram_max": {
        "ru": "Макс. размер n-gram",
        "uk": "Макс. розмір n-gram",
        "en": "Max n-gram size",
    },
    "seo_math_top_terms": {
        "ru": "Топ терминов",
        "uk": "Топ термінів",
        "en": "Top terms",
    },
    "seo_math_min_count": {
        "ru": "Мин. количество вхождений",
        "uk": "Мін. кількість входжень",
        "en": "Min count",
    },
    "seo_math_min_df": {
        "ru": "Мин. документ. частота",
        "uk": "Мін. документ. частота",
        "en": "Min doc frequency",
    },
    "seo_math_use_related": {
        "ru": "Использовать Related Searches",
        "uk": "Використовувати Related Searches",
        "en": "Use Related Searches",
    },
    "seo_math_use_paa": {
        "ru": "Использовать People Also Ask",
        "uk": "Використовувати People Also Ask",
        "en": "Use People Also Ask",
    },
    "seo_math_strip_suffixes": {
        "ru": "Лемматизация слов (реальная морфология)",
        "uk": "Лематизація слів (реальна морфологія)",
        "en": "Lemmatize words (real morphology)",
    },
    "seo_math_strip_suffixes_help": {
        "ru": "Лемматизирует отдельные слова (не URL) настоящим морфоанализатором перед анализом: pymorphy3 для русского/украинского, simplemma для остальных языков. Сводит формы к одной лемме — «купить», «купил», «куплю» → «купить», что повышает точность TF-IDF, n-грамм, BM25F и распознавания интента. Зависимости опциональные и подгружаются лениво: без них настройка бездействует (слова не меняются). Для включения выполните: pip install pymorphy3 pymorphy3-dicts-uk simplemma.",
        "uk": "Лематизує окремі слова (не URL) справжнім морфоаналізатором перед аналізом: pymorphy3 для російської/української, simplemma для решти мов. Зводить форми до однієї леми — «купити», «купив», «куплю» → «купити», що підвищує точність TF-IDF, n-грам, BM25F та розпізнавання інтенту. Залежності опційні та підвантажуються ліниво: без них налаштування бездіяльне (слова не змінюються). Для ввімкнення виконайте: pip install pymorphy3 pymorphy3-dicts-uk simplemma.",
        "en": "Lemmatizes individual words (not URLs) with a real morphological analyzer before analysis: pymorphy3 for Russian/Ukrainian, simplemma for other languages. Collapses word forms to one lemma — «купить», «купил», «куплю» → «купить», improving TF-IDF, n-gram, BM25F, and intent detection accuracy. Dependencies are optional and lazy-loaded: without them this setting is a no-op (words are left unchanged). To enable, run: pip install pymorphy3 pymorphy3-dicts-uk simplemma.",
    },
    "lemmatizer_dependency_status_header": {
        "ru": "Статус библиотек лемматизации",
        "uk": "Стан бібліотек лематизації",
        "en": "Lemmatizer library status",
    },
    "lemmatizer_dependency_name_pymorphy3": {
        "ru": "pymorphy3 (морфология RU)",
        "uk": "pymorphy3 (морфологія RU)",
        "en": "pymorphy3 (RU morphology)",
    },
    "lemmatizer_dependency_name_pymorphy3_dicts_uk": {
        "ru": "pymorphy3-dicts-uk (словарь UK)",
        "uk": "pymorphy3-dicts-uk (словник UK)",
        "en": "pymorphy3-dicts-uk (UK dictionary)",
    },
    "lemmatizer_dependency_name_simplemma": {
        "ru": "simplemma (лемматизация EN/др.)",
        "uk": "simplemma (лематизація EN/ін.)",
        "en": "simplemma (EN/other lemmatizer)",
    },
    "lemmatizer_dependencies_ready": {
        "ru": "Все библиотеки лемматизации установлены и готовы к работе.",
        "uk": "Усі бібліотеки лематизації встановлені та готові до роботи.",
        "en": "All lemmatizer libraries are installed and ready.",
    },
    "lemmatizer_dependencies_missing_prompt": {
        "ru": "Включена лемматизация, но не все библиотеки установлены. Без них настройка бездействует. Установите команду ниже.",
        "uk": "Увімкнено лематизацію, але не всі бібліотеки встановлено. Без них налаштування бездіяльне. Виконайте команду нижче.",
        "en": "Lemmatization is enabled but not all libraries are installed. Without them this setting is a no-op. Run the command below.",
    },
    "lemmatizer_install_scope_label": {
        "ru": "Область установки",
        "uk": "Область встановлення",
        "en": "Install scope",
    },
    "lemmatizer_install_scope_project": {
        "ru": "Проект (текущий интерпретатор)",
        "uk": "Проєкт (поточний інтерпретатор)",
        "en": "Project (current interpreter)",
    },
    "lemmatizer_install_scope_global": {
        "ru": "Глобально (user site-packages)",
        "uk": "Глобально (user site-packages)",
        "en": "Global (user site-packages)",
    },
    "lemmatizer_install_command_label": {
        "ru": "Команда установки",
        "uk": "Команда встановлення",
        "en": "Install command",
    },
    "seo_math_partial_data_warning": {
        "ru": "Часть SERP-полей была пустой. Анализ использует только доступные данные.",
        "uk": "Частина SERP-полів була порожньою. Аналіз використовує лише доступні дані.",
        "en": "Some SERP fields were empty. Analysis uses available data only.",
    },
    "seo_math_top_ngrams_header": {
        "ru": "Топ N-граммы",
        "uk": "Топ N-грами",
        "en": "Top N-Grams",
    },
    "seo_math_tfidf_header": {
        "ru": "Топ TF-IDF термины",
        "uk": "Топ TF-IDF терміни",
        "en": "Top TF-IDF Terms",
    },
    "seo_math_cooccurrence_header": {
        "ru": "Связанные термины (co-occurrence)",
        "uk": "Пов'язані терміни (co-occurrence)",
        "en": "Related Topical Terms (Co-occurrence)",
    },
    "seo_math_intent_header": {
        "ru": "Поисковый intent",
        "uk": "Пошуковий intent",
        "en": "Search Intent",
    },
    "seo_math_intent_type": {
        "ru": "Тип intent",
        "uk": "Тип intent",
        "en": "Intent Type",
    },
    "seo_math_intent_score": {
        "ru": "Оценка",
        "uk": "Оцінка",
        "en": "Score",
    },
    "seo_math_intent_confidence": {
        "ru": "Уверенность",
        "uk": "Впевненість",
        "en": "Confidence",
    },
    "seo_math_intent_commercial": {
        "ru": "Коммерческий",
        "uk": "Комерційний",
        "en": "Commercial",
    },
    "seo_math_intent_informational": {
        "ru": "Информационный",
        "uk": "Інформаційний",
        "en": "Informational",
    },
    "seo_math_intent_transactional": {
        "ru": "Транзакционный",
        "uk": "Транзакційний",
        "en": "Transactional",
    },
    "seo_math_intent_navigational": {
        "ru": "Навигационный",
        "uk": "Навігаційний",
        "en": "Navigational",
    },
    "seo_math_intent_mixed": {
        "ru": "Смешанный",
        "uk": "Змішаний",
        "en": "Mixed",
    },
    "seo_math_intent_undetermined": {
        "ru": "Не определён",
        "uk": "Не визначений",
        "en": "Undetermined",
    },
    "seo_math_intent_matched_signals": {
        "ru": "Обнаруженные сигналы:",
        "uk": "Виявлені сигнали:",
        "en": "Matched Signals:",
    },
    "seo_math_related_queries_header": {
        "ru": "Связанные запросы из SERP",
        "uk": "Пов'язані запити з SERP",
        "en": "Related Queries from SERP",
    },
    "seo_math_related_searches_label": {
        "ru": "Связанные поисковые запросы",
        "uk": "Пов'язані пошукові запити",
        "en": "Related Searches",
    },
    "seo_math_paa_label": {
        "ru": "People Also Ask",
        "uk": "People Also Ask",
        "en": "People Also Ask",
    },
    "seo_math_bm25f_scores_header": {
        "ru": "Оценки BM25F",
        "uk": "Оцінки BM25F",
        "en": "BM25F Scores",
    },
    "crawl_bm25f_scores_header": {
        "ru": "Оценки BM25F для краулинга",
        "uk": "Оцінки BM25F для краулінгу",
        "en": "Crawl BM25F Scores",
    },
    "seo_math_bm25f_doc_id_column": {
        "ru": "ID документа",
        "uk": "ID документа",
        "en": "Doc ID",
    },
    "seo_math_bm25f_text_column": {
        "ru": "Текст",
        "uk": "Текст",
        "en": "Text",
    },
    "seo_math_bm25f_score_column": {
        "ru": "Оценка",
        "uk": "Оцінка",
        "en": "Score",
    },
    "seo_math_bm25f_coverage_column": {
        "ru": "Покрытие",
        "uk": "Покриття",
        "en": "Coverage",
    },
    "seo_math_bm25f_field_contributions_column": {
        "ru": "Вклад полей",
        "uk": "Внесок полів",
        "en": "Field Contributions",
    },
    "seo_math_bm25f_matched_terms_column": {
        "ru": "Совпавшие термины",
        "uk": "Збіги термінів",
        "en": "Matched Terms",
    },
    "export_math_analysis": {
        "ru": "Экспорт SEO-анализа",
        "uk": "Експорт SEO-аналізу",
        "en": "Export Math Analysis",
    },
    # --- Phase 10: BM25F, Cache, Google Trends, Browser Scraper ---
    "seo_math_analyze_bm25f": {
        "ru": "Анализировать BM25F",
        "uk": "Аналізувати BM25F",
        "en": "Analyze BM25F",
    },
    "seo_math_bm25f_params": {
        "ru": "Параметры BM25F",
        "uk": "Параметри BM25F",
        "en": "BM25F Parameters",
    },
    "seo_math_field_weights": {
        "ru": "Веса полей BM25F",
        "uk": "Ваги полів BM25F",
        "en": "BM25F Field Weights",
    },
    "seo_math_signals": {
        "ru": "Сигналы SEO",
        "uk": "Сигнали SEO",
        "en": "SEO Signals",
    },
    "cache_header": {
        "ru": "Кэш запросов",
        "uk": "Кеш запитів",
        "en": "Request Cache",
    },
    "cache_enabled": {
        "ru": "Включить кэширование",
        "uk": "Увімкнути кешування",
        "en": "Enable caching",
    },
    "cache_default_ttl_hours": {
        "ru": "TTL по умолчанию (часы)",
        "uk": "TTL за замовчуванням (години)",
        "en": "Default TTL (hours)",
    },
    "cache_max_records": {
        "ru": "Макс. записей кэша",
        "uk": "Макс. записів кешу",
        "en": "Max cache records",
    },
    "cache_force_refresh": {
        "ru": "Принудительное обновление",
        "uk": "Примусове оновлення",
        "en": "Force refresh",
    },
    "cache_hit_label": {
        "ru": "Из кэша",
        "uk": "З кешу",
        "en": "From cache",
    },
    "google_trends_header": {
        "ru": "Google Trends",
        "uk": "Google Trends",
        "en": "Google Trends",
    },
    "google_trends_default_geo": {
        "ru": "Геолокация по умолчанию",
        "uk": "Геолокація за замовчуванням",
        "en": "Default geo",
    },
    "google_trends_default_timeframe": {
        "ru": "Временной период по умолчанию",
        "uk": "Часовий період за замовчуванням",
        "en": "Default timeframe",
    },
    "google_trends_cache_ttl_hours": {
        "ru": "TTL кэша Trends (часы)",
        "uk": "TTL кешу Trends (години)",
        "en": "Trends cache TTL (hours)",
    },
    "google_trends_max_keywords_per_request": {
        "ru": "Макс. ключевых слов за запуск Trends",
        "uk": "Макс. ключових слів за запуск Trends",
        "en": "Max Trends keywords per run",
    },
    "google_trends_max_keywords_per_request_help": {
        "ru": "Лимит ключевых слов, которые локальный браузерный провайдер обработает за один запуск. Для больших списков увеличьте задержки между ключами.",
        "uk": "Ліміт ключових слів, які локальний браузерний провайдер обробить за один запуск. Для великих списків збільште затримки між ключами.",
        "en": "Keyword limit processed by the local browser Trends provider in one run. Increase per-keyword delays for larger batches.",
    },
    "google_trends_provider_selectbox": {
        "ru": "Провайдер Google Trends",
        "uk": "Провайдер Google Trends",
        "en": "Google Trends Provider",
    },
    "trends_provider_local_browser": {
        "ru": "Локальный Cloakbrowser + Playwright",
        "uk": "Локальний Cloakbrowser + Playwright",
        "en": "Local Cloakbrowser + Playwright",
    },
    "trends_provider_serpapi": {
        "ru": "SerpApi (требует SERPAPI_KEY)",
        "uk": "SerpApi (потрібен SERPAPI_KEY)",
        "en": "SerpApi (requires SERPAPI_KEY)",
    },
    "trends_provider_dataforseo": {
        "ru": "DataForSEO (требует DATAFORSEO_LOGIN + PASSWORD)",
        "uk": "DataForSEO (потрібні DATAFORSEO_LOGIN + PASSWORD)",
        "en": "DataForSEO (requires DATAFORSEO_LOGIN + PASSWORD)",
    },
    "trends_provider_scrapebadger": {
        "ru": "ScrapeBadger (требует SCRAPEBADGER_KEY)",
        "uk": "ScrapeBadger (потрібен SCRAPEBADGER_KEY)",
        "en": "ScrapeBadger (requires SCRAPEBADGER_KEY)",
    },
    "trends_show_confidence_metadata": {
        "ru": "Показывать метаданные уверенности",
        "uk": "Показувати метадані впевненості",
        "en": "Show confidence metadata",
    },
    "google_trends_default_category": {
        "ru": "Категория",
        "uk": "Категорія",
        "en": "Category",
    },
    "google_trends_default_property": {
        "ru": "Тип данных (Property)",
        "uk": "Тип даних (Property)",
        "en": "Data Type (Property)",
    },
    "google_trends_default_language": {
        "ru": "Язык",
        "uk": "Мова",
        "en": "Language",
    },
    "google_trends_default_timezone": {
        "ru": "Часовой пояс",
        "uk": "Часовий пояс",
        "en": "Timezone",
    },
    "google_trends_force_refresh": {
        "ru": "Принудительное обновление кэша",
        "uk": "Примусове оновлення кешу",
        "en": "Force cache refresh",
    },
    "google_trends_provider_available": {
        "ru": "Доступен",
        "uk": "Доступний",
        "en": "Available",
    },
    "google_trends_provider_unavailable": {
        "ru": "Недоступен",
        "uk": "Недоступний",
        "en": "Unavailable",
    },
    "trends_local_settings_header": {
        "en": "Local Browser Trends Settings",
        "ru": "Настройки локального парсинга Google Trends",
        "uk": "Налаштування локального парсингу Google Trends",
    },
    "google_trends_local_headless": {
        "en": "Local Trends: run browser headless",
        "ru": "Локальный Trends: запускать браузер headless",
        "uk": "Локальний Trends: запускати браузер headless",
    },
    "trends_local_warmup_wait": {
        "en": "Manual warmup wait (seconds)",
        "ru": "Время ручной разминки (сек)",
        "uk": "Час ручної розминки (сек)",
    },
    "trends_local_warmup_wait_help": {
        "en": "On first run, the browser opens Google Trends homepage for this many seconds to establish session. Set to 0 after initial warmup to reuse saved state.",
        "ru": "При первом запуске браузер открывает домашнюю страницу Google Trends на это количество секунд для установки сессии. Установите 0 после первоначальной разминки для повторного использования сохранённого состояния.",
        "uk": "При першому запуску браузер відкриває домашню сторінку Google Trends на цю кількість секунд для встановлення сесії. Встановіть 0 після початкової розминки для повторного використання збереженого стану.",
    },
    "trends_local_min_delay": {
        "en": "Min delay between keywords (sec)",
        "ru": "Мин. задержка между ключевыми словами (сек)",
        "uk": "Мін. затримка між ключовими словами (сек)",
    },
    "trends_local_max_delay": {
        "en": "Max delay between keywords (sec)",
        "ru": "Макс. задержка между ключевыми словами (сек)",
        "uk": "Макс. затримка між ключовими словами (сек)",
    },
    "trends_local_state_file": {
        "en": "Session state file",
        "ru": "Файл состояния сессии",
        "uk": "Файл стану сесії",
    },
    "trends_local_constraint_note": {
        "en": "Google can rate-limit local browser batches. Tune the keyword limit and delays for your IP/session.",
        "ru": "Google может ограничивать локальные браузерные пакеты. Настройте лимит ключевых слов и задержки под ваш IP/сессию.",
        "uk": "Google може обмежувати локальні браузерні пакети. Налаштуйте ліміт ключових слів і затримки під ваш IP/сесію.",
    },
    "trends_csv_blocked": {
        "en": "Google blocked the request (429)",
        "ru": "Google заблокировал запрос (429)",
        "uk": "Google заблокував запит (429)",
    },
    "trends_csv_empty": {
        "en": "Downloaded CSV is empty",
        "ru": "Загруженный CSV пуст",
        "uk": "Завантажений CSV порожній",
    },
    "trends_csv_downloaded": {
        "en": "Trends CSV downloaded successfully",
        "ru": "CSV Google Trends успешно загружен",
        "uk": "CSV Google Trends успішно завантажено",
    },
    "trends_local_warming_up": {
        "en": "Warming up session...",
        "ru": "Разминка сессии...",
        "uk": "Розминка сесії...",
    },
    "trends_local_state_saved": {
        "en": "Session state saved for reuse",
        "ru": "Состояние сессии сохранено для повторного использования",
        "uk": "Стан сесії збережено для повторного використання",
    },
    "trends_local_state_loaded": {
        "en": "Session state loaded (skipping warmup)",
        "ru": "Состояние сессии загружено (пропуск разминки)",
        "uk": "Стан сесії завантажено (пропуск розминки)",
    },
    "trends_local_rate_limited": {
        "en": "Rate-limited after {count} queries. Increase delays, lower the keyword limit, or change IP/session.",
        "ru": "Ограничение после {count} запросов. Увеличьте задержки, уменьшите лимит ключевых слов или смените IP/сессию.",
        "uk": "Обмеження після {count} запитів. Збільште затримки, зменште ліміт ключових слів або змініть IP/сесію.",
    },
    "trends_local_processing_keyword": {
        "en": "Processing keyword: {keyword}",
        "ru": "Обработка ключевого слова: {keyword}",
        "uk": "Обробка ключового слова: {keyword}",
    },
    "scraper_header": {
        "ru": "Браузерный скрапер (OPT-IN)",
        "uk": "Браузерний скрапер (OPT-IN)",
        "en": "Browser Scraper (OPT-IN)",
    },
    "scraper_browser_enabled": {
        "ru": "Включить браузерный скрапинг",
        "uk": "Увімкнути браузерний скрапінг",
        "en": "Enable browser scraping",
    },
    "scraper_browser_enabled_help": {
        "ru": "OPT-IN: Требует установки cloakbrowser (pip install cloakbrowser)",
        "uk": "OPT-IN: Потрібна встановлення cloakbrowser (pip install cloakbrowser)",
        "en": "OPT-IN: Requires cloakbrowser (pip install cloakbrowser)",
    },
    "scraper_not_installed_warning": {
        "ru": "Браузерный скрапинг включен, но зависимости не установлены. Установите: pip install cloakbrowser",
        "uk": "Браузерний скрапінг увімкнено, але залежності не встановлено. Встановіть: pip install cloakbrowser",
        "en": "Browser scraping is enabled, but optional dependencies are missing or unusable.",
    },
    "scraper_dependency_status_header": {
        "ru": "Статус дополнительных инструментов браузера",
        "uk": "Стан додаткових інструментів браузера",
        "en": "Optional browser tool status",
    },
    "scraper_dependency_name_col": {
        "ru": "Инструмент",
        "uk": "Інструмент",
        "en": "Tool",
    },
    "scraper_dependency_status_col": {
        "ru": "Статус",
        "uk": "Стан",
        "en": "Status",
    },
    "scraper_dependency_name_cloakbrowser": {
        "ru": "CloakBrowser (Chromium+Stealth)",
        "uk": "CloakBrowser (Chromium+Stealth)",
        "en": "CloakBrowser (Chromium+Stealth)",
    },
    "scraper_dependency_name_trafilatura": {
        "ru": "Trafilatura (HTML парсер)",
        "uk": "Trafilatura (HTML парсер)",
        "en": "Trafilatura (HTML parser)",
    },
    "scraper_dependency_status_available": {
        "ru": "Доступен",
        "uk": "Доступний",
        "en": "Available",
    },
    "scraper_dependency_status_missing": {
        "ru": "Отсутствует",
        "uk": "Відсутній",
        "en": "Missing",
    },
    "scraper_dependency_status_unknown": {
        "ru": "Неизвестно",
        "uk": "Невідомо",
        "en": "Unknown",
    },
    "scraper_dependency_status_unusable": {
        "ru": "Установлен, но недоступен",
        "uk": "Встановлено, але недоступний",
        "en": "Installed but unusable",
    },
    "scraper_dependencies_ready": {
        "ru": "Все дополнительные инструменты браузера доступны.",
        "uk": "Усі додаткові інструменти браузера доступні.",
        "en": "All optional browser tools are available.",
    },
    "scraper_dependencies_missing_prompt": {
        "ru": "Некоторые дополнительные инструменты браузера отсутствуют или несовместимы. Выберите место для установки или обновления.",
        "uk": "Деякі додаткові інструменти браузера відсутні або несумісні. Виберіть місце для встановлення або оновлення.",
        "en": "Some optional browser tools are missing or incompatible. Choose where to install or upgrade them.",
    },
    "scraper_install_scope_label": {
        "ru": "Место установки",
        "uk": "Місце встановлення",
        "en": "Install location",
    },
    "scraper_install_scope_project": {
        "ru": "Окружение проекта",
        "uk": "Оточення проєкту",
        "en": "Project environment",
    },
    "scraper_install_scope_global": {
        "ru": "Глобальный Python пользователя",
        "uk": "Глобальний Python користувача",
        "en": "Global user Python",
    },
    "scraper_install_command_label": {
        "ru": "Команда установки",
        "uk": "Команда встановлення",
        "en": "Install command",
    },
    "workflow_mode_trends": {
        "ru": "Google Trends",
        "uk": "Google Trends",
        "en": "Google Trends",
    },
    "google_trends_keyword_input_header": {
        "ru": "Ключевые слова Google Trends",
        "uk": "Ключові слова Google Trends",
        "en": "Google Trends keywords",
    },
    "google_trends_keyword_input_placeholder": {
        "ru": "Введите по одному ключевому слову на строку. URL не принимаются.",
        "uk": "Введіть по одному ключовому слову на рядок. URL не приймаються.",
        "en": "Enter one keyword per line. URLs are not accepted.",
    },
    "google_trends_keyword_warning": {
        "ru": "Выберите хотя бы одно ключевое слово для Google Trends. Прямые URL не принимаются.",
        "uk": "Оберіть хоча б одне ключове слово для Google Trends. Прямі URL не приймаються.",
        "en": "Select at least one keyword for Google Trends. Bare URLs are not accepted.",
    },
    "google_trends_disabled_warning": {
        "ru": "Google Trends отключен в настройках.",
        "uk": "Google Trends вимкнено в налаштуваннях.",
        "en": "Google Trends is disabled in settings.",
    },
    "google_trends_querying": {
        "ru": "Запрос Google Trends для {count} кл. слов(а)...",
        "uk": "Запит Google Trends для {count} кл. слів(а)...",
        "en": "Querying Google Trends for {count} keyword(s)...",
    },
    "google_trends_complete": {
        "ru": "Анализ Google Trends завершен.",
        "uk": "Аналіз Google Trends завершено.",
        "en": "Google Trends analysis complete.",
    },
    "google_trends_no_results": {
        "ru": "Google Trends не вернул подходящих данных.",
        "uk": "Google Trends не повернув придатних даних.",
        "en": "Google Trends returned no usable rows.",
    },
    "google_trends_results_header": {
        "ru": "Результаты Google Trends",
        "uk": "Результати Google Trends",
        "en": "Google Trends results",
    },
    "google_trends_results_desc": {
        "ru": "Относительные метрики, связанные термины и экспортные наборы.",
        "uk": "Відносні метрики, пов'язані терміни та експортні набори.",
        "en": "Relative metrics, related terms, and export bundles.",
    },
    "google_trends_provider_label": {
        "ru": "Провайдер",
        "uk": "Провайдер",
        "en": "Provider",
    },
    "google_trends_data_confidence_label": {
        "ru": "Доверие к данным",
        "uk": "Довіра до даних",
        "en": "Data confidence",
    },
    "google_trends_blocked_warning": {
        "ru": "Google Trends вернул заблокированные или непригодные данные.",
        "uk": "Google Trends повернув заблоковані або непридатні дані.",
        "en": "Google Trends returned blocked or unusable data.",
    },
    "google_trends_degraded_warning": {
        "ru": "Google Trends вернул частичные или ухудшенные данные.",
        "uk": "Google Trends повернув часткові або погіршені дані.",
        "en": "Google Trends returned degraded or partial data.",
    },
    "google_trends_provider_metadata_header": {
        "ru": "Метаданные провайдера",
        "uk": "Метадані провайдера",
        "en": "Provider metadata",
    },
    "google_trends_cache_metadata_header": {
        "ru": "Метаданные кеша",
        "uk": "Метадані кешу",
        "en": "Cache metadata",
    },
    "google_trends_relative_scale_caveat": {
        "ru": "Примечание: web UI Google Trends показывает относительную шкалу 0-100, а не абсолютные объёмы.",
        "uk": "Примітка: web UI Google Trends показує відносну шкалу 0-100, а не абсолютні обсяги.",
        "en": "Note: the web UI uses a relative 0-100 scale, not absolute volumes.",
    },
    "google_trends_official_alpha_caveat": {
        "ru": "Официальный alpha-провайдер может возвращать масштабированные данные.",
        "uk": "Офіційний alpha-провайдер може повертати масштабовані дані.",
        "en": "The official alpha provider may return scaled data.",
    },
    "google_trends_interest_header": {
        "ru": "Популярность во времени",
        "uk": "Популярність у часі",
        "en": "Interest over time",
    },
    "google_trends_related_header": {
        "ru": "Похожие запросы и темы Trends",
        "uk": "Схожі запити та теми Trends",
        "en": "Related Trends queries and topics",
    },
    "google_trends_related_desc": {
        "ru": "Связанные запросы с селекторами для дальнейшего выбора.",
        "uk": "Пов'язані запити з селекторами для подальшого вибору.",
        "en": "Related queries with downstream selectors.",
    },
    "google_trends_region_header": {
        "ru": "Популярность по регионам",
        "uk": "Популярність за регіонами",
        "en": "Regional interest",
    },
    "google_trends_selected_stat": {
        "ru": "Выбрано: {selected} / {total} запросов Trends",
        "uk": "Вибрано: {selected} / {total} запитів Trends",
        "en": "Selected: {selected} / {total} Trends queries",
    },
    "google_trends_ads_results_header": {
        "ru": "Результаты Google Trends в Ads",
        "uk": "Результати Google Trends в Ads",
        "en": "Google Trends to Ads results",
    },
    "google_trends_ads_results_desc": {
        "ru": "Запросы, выбранные в Trends, переданы в Ads.",
        "uk": "Запити, обрані в Trends, передано до Ads.",
        "en": "Trends-selected queries passed to Ads.",
    },
    "send_selected_to_trends": {
        "ru": "Отправить выбранные в Trends",
        "uk": "Надіслати вибрані в Trends",
        "en": "Send selected to Trends",
    },
    "send_selected_to_seo": {
        "ru": "Сгенерировать SEO-текст",
        "uk": "Згенерувати SEO-текст",
        "en": "Generate SEO text",
    },
    "send_related_to_trends": {
        "ru": "Отправить похожие в Trends",
        "uk": "Надіслати схожі в Trends",
        "en": "Send related to Trends",
    },
    "trends_from_serp": {
        "ru": "Тренды из SERP",
        "uk": "Тренди з SERP",
        "en": "Trends from SERP",
    },
    "trends_from_ads": {
        "ru": "Тренды из Ads",
        "uk": "Тренди з Ads",
        "en": "Trends from Ads",
    },
    "trends_from_keywords": {
        "ru": "Тренды из Keywords",
        "uk": "Тренди з Keywords",
        "en": "Trends from Keywords",
    },
    "trends_from_crawl": {
        "ru": "Тренды из Crawl",
        "uk": "Тренди з Crawl",
        "en": "Trends from Crawl",
    },
    "trends_stage_header": {
        "ru": "Анализ трендов",
        "uk": "Аналіз трендів",
        "en": "Analyze Trends",
    },
    "google_trends_browser_fallback": {
        "ru": "Используем браузер (cloakbrowser) из-за блокировки HTTP-запросов...",
        "uk": "Використовуємо браузер (cloakbrowser) через блокування HTTP-запитів...",
        "en": "Using browser (cloakbrowser) due to HTTP request blocking...",
    },
    "google_trends_http_blocked_info": {
        "ru": "Google блокирует прямые HTTP-запросы. Попробуйте позже или используйте VPN.",
        "uk": "Google блокує прямі HTTP-запити. Спробуйте пізніше або використайте VPN.",
        "en": "Google is blocking direct HTTP requests. Try again later or use a VPN.",
    },
    "trends_no_keywords_selected": {
        "ru": "Не выбрано ключевых слов для анализа трендов",
        "uk": "Не вибрано ключових слів для аналізу трендів",
        "en": "No keywords selected for Trends analysis",
    },
    # --- Phase 14: Keyword-to-LLM Workflow & SERP Domain Math ---
    "workflow_mode_keyword_llm": {
        "ru": "Ключевые слова -> LLM SEO текст",
        "uk": "Ключові слова -> LLM SEO текст",
        "en": "Keywords -> LLM SEO Text",
    },
    "keyword_llm_input_header": {
        "ru": "1. Ввод ключевых слов для генерации SEO текста",
        "uk": "1. Введення ключових слів для генерації SEO тексту",
        "en": "1. Enter keywords for SEO text generation",
    },
    "keyword_llm_input_placeholder": {
        "ru": "По одному ключевому слову на строку или несколько через запятую",
        "uk": "По одному ключовому слову на рядок або кілька через кому",
        "en": "One keyword per line, or several separated by commas",
    },
    "keyword_llm_input_help": {
        "ru": "Введите ключевые слова для генерации SEO-текста. Правила разбиения на группы:\n- Каждый перенос строки начинает новую группу (отдельный SEO-текст).\n- В одной строке можно указать несколько ключевых слов через запятую (`,`), точку с запятой (`;`) или вертикальную черту (`|`) — они попадут в одну группу и будут обработаны вместе (один общий SEO-текст).\n- Пустые строки игнорируются.\nПример:\nкупить кофе, кофемашина цена\n\"эспрессо машина\"",
        "uk": "Введіть ключові слова для генерації SEO-тексту. Правила розбивки на групи:\n- Кожен перенос рядка починає нову групу (окремий SEO-текст).\n- В одному рядку можна вказати кілька ключових слів через кому (`,`), крапку з комою (`;`) або вертикальну риску (`|`) — вони потраплять у одну групу й будуть оброблені разом (один спільний SEO-текст).\n- Порожні рядки ігноруються.\nПриклад:\nкупити каву, ціна кавомашини\n\"машина еспресо\"",
        "en": "Enter keywords to generate SEO text. Grouping rules:\n- Each line break starts a new group (a separate SEO text).\n- A single line may contain several keywords separated by comma (`,`), semicolon (`;`), or pipe (`|`) — they form one group and are processed together (one combined SEO text).\n- Empty lines are ignored.\nExample:\nbuy coffee, coffee machine price\n\"espresso machine\"",
    },
    "keyword_llm_warning": {
        "ru": "Введите хотя бы одно ключевое слово.",
        "uk": "Введіть хоча б одне ключове слово.",
        "en": "Please enter at least one keyword.",
    },
    "keyword_llm_language_label": {
        "ru": "Язык генерации (Keyword -> LLM)",
        "uk": "Мова генерації (Keyword -> LLM)",
        "en": "Generation language (Keyword -> LLM)",
    },
    "keyword_llm_language_help": {
        "ru": "Язык для генерации SEO текста во всех режимах с генерацией текста.",
        "uk": "Мова для генерації SEO тексту в усіх режимах із генерацією тексту.",
        "en": "Language for SEO text generation across all text-generation workflows.",
    },
    "page_type_label": {
        "ru": "Тип страницы (Keyword -> LLM)",
        "uk": "Тип сторінки (Keyword -> LLM)",
        "en": "Page type (Keyword -> LLM)",
    },
    "page_type_help": {
        "ru": "Тип страницы, под который генерируется SEO-текст: карточка товара, категория, блог или свой вариант. Значение подставляется в промпт как {page_type}.",
        "uk": "Тип сторінки, під який генерується SEO-текст: картка товару, категорія, блог або свій варіант. Значення підставляється в промпт як {page_type}.",
        "en": "The page type the SEO text is generated for: product page, category, blog post, or a custom value. The value is injected into the prompt as {page_type}.",
    },
    "page_type_user_defined": {
        "ru": "Другой / Свой",
        "uk": "Інший / Свій",
        "en": "Other / Custom",
    },
    "page_type_custom_label": {
        "ru": "Свой тип страницы",
        "uk": "Свій тип сторінки",
        "en": "Custom page type",
    },
    "page_type_custom_placeholder": {
        "ru": "Например: лендинг, новость, услуга",
        "uk": "Наприклад: лендинг, новина, послуга",
        "en": "e.g. landing page, news, service",
    },
    "keyword_llm_generating": {
        "ru": "Генерация SEO текста для {count} ключевых слов...",
        "uk": "Генерація SEO тексту для {count} ключових слів...",
        "en": "Generating SEO text for {count} keywords...",
    },
    "keyword_llm_generating_keyword": {
        "ru": "Генерация {idx}/{total}: {keyword}",
        "uk": "Генерація {idx}/{total}: {keyword}",
        "en": "Generating {idx}/{total}: {keyword}",
    },
    "keyword_llm_complete": {
        "ru": "Генерация SEO текстов завершена! {count} текстов.",
        "uk": "Генерація SEO текстів завершена! {count} текстів.",
        "en": "SEO text generation complete! {count} texts.",
    },
    "serp_domain_math_header": {
        "ru": "Анализ доменов в SERP",
        "uk": "Аналіз доменів у SERP",
        "en": "SERP Domain Analysis",
    },
    "serp_domain_avg_position": {
        "ru": "Средняя позиция",
        "uk": "Середня позиція",
        "en": "Average Position",
    },
    "serp_domain_keyword_serps": {
        "ru": "Ключевые SERPs",
        "uk": "Ключові SERPs",
        "en": "Keyword SERPs",
    },
    "serp_domain_result_frequency": {
        "ru": "Частота в результатах",
        "uk": "Частота у результатах",
        "en": "Result Frequency",
    },
    "serp_domain_export_sheet": {
        "ru": "Домены SERP",
        "uk": "Домени SERP",
        "en": "SERP Domains",
    },
    "serp_domain_mentioned": {
        "ru": "Упоминаний домена",
        "uk": "Згадок домену",
        "en": "Domain Mentioned",
    },
    "serp_domain_visibility": {
        "ru": "Видимость домена",
        "uk": "Видимість домену",
        "en": "Domain Visibility",
    },
    # --- Hardcoded strings (Phase 15 i18n cleanup) ---
    "chain_to_analysis": {
        "ru": "🔗 Цепочка к анализу",
        "uk": "🔗 Ланцюжок до аналізу",
        "en": "Chain to Analysis",
    },
    "chain_to_analysis_desc": {
        "ru": "Переключайте выбранные строки между SERP, Ads и Trends.",
        "uk": "Перемикайте обрані рядки між SERP, Ads та Trends.",
        "en": "Move selected rows between SERP, Ads, and Trends.",
    },
    "no_keywords_selected": {
        "ru": "Ключевые слова не выбраны",
        "uk": "Ключові слова не вибрані",
        "en": "No keywords selected",
    },
    "no_ads_metrics_for_keywords": {
        "ru": "Метрики Google Ads не найдены для выбранных ключевых слов",
        "uk": "Метрики Google Ads не знайдено для вибраних ключових слів",
        "en": "No Ads metrics found for selected keywords",
    },
    "ads_metric_enrichment": {
        "ru": "📊 Обогащение метриками Ads",
        "uk": "📊 Збагачення метриками Ads",
        "en": "Ads Metric Enrichment",
    },
    "serp_ads_overlap_gaps": {
        "ru": "🔄 Пересечения и пробелы SERP/Ads",
        "uk": "🔄 Перетини та прогалини SERP/Ads",
        "en": "SERP/Ads Overlap and Gaps",
    },
    "handoff_to_analysis": {
        "ru": "➡️ Передача на анализ",
        "uk": "➡️ Передача на аналіз",
        "en": "Handoff to Analysis",
    },
    "handoff_to_analysis_desc": {
        "ru": "Отправьте выбранные термины на следующий этап анализа.",
        "uk": "Надішліть обрані терміни на наступний етап аналізу.",
        "en": "Send selected terms into the next analysis stage.",
    },
    "send_selected_to_google_ads": {
        "ru": "Отправить выбранные в Google Ads",
        "uk": "Надіслати вибрані до Google Ads",
        "en": "Send selected to Google Ads",
    },
    "select_terms_first": {
        "ru": "Сначала выберите термины",
        "uk": "Спочатку виберіть терміни",
        "en": "Select terms first",
    },
    "math_ads_started": {
        "ru": "Запуск Google Ads анализа для {count} терминов…",
        "uk": "Запуск Google Ads аналізу для {count} термінів…",
        "en": "Starting Google Ads analysis for {count} terms…",
    },
    "math_ads_complete": {
        "ru": "Google Ads анализ завершён!",
        "uk": "Google Ads аналіз завершено!",
        "en": "Google Ads analysis complete!",
    },
    "math_serp_started": {
        "ru": "Запуск SERP анализа для {count} терминов…",
        "uk": "Запуск SERP аналізу для {count} термінів…",
        "en": "Starting SERP analysis for {count} terms…",
    },
    "math_serp_complete": {
        "ru": "SERP анализ завершён!",
        "uk": "SERP аналіз завершено!",
        "en": "SERP analysis complete!",
    },
    "no_generated_text_to_analyze": {
        "ru": "Нет сгенерированного текста для анализа",
        "uk": "Немає згенерованого тексту для аналізу",
        "en": "No generated text to analyze.",
    },
    "generation_quality_report": {
        "ru": "📋 Отчет о качестве генерации",
        "uk": "📋 Звіт про якість генерації",
        "en": "Generation Quality Report",
    },
    "improvement_suggestions": {
        "ru": "💡 Предложения по улучшению",
        "uk": "💡 Пропозиції щодо покращення",
        "en": "Improvement Suggestions",
    },
    "regenerate_with_quality_feedback": {
        "ru": "🔄 Перегенерировать с учетом обратной связи",
        "uk": "🔄 Перегенерувати з урахуванням зворотного зв'язку",
        "en": "Regenerate with Quality Feedback",
    },
    "max_regeneration_reached": {
        "ru": "Достигнут лимит перегенераций. Просмотрите и скорректируйте вручную.",
        "uk": "Досягнуто ліміт перегенерацій. Перегляньте та скоригуйте вручну.",
        "en": "Maximum regeneration attempts reached. Review and adjust manually.",
    },
    "google_ads_header": {
        "ru": "📢 Google Ads",
        "uk": "📢 Google Ads",
        "en": "Google Ads",
    },
}

# --- UI refresh ---
TRANSLATIONS.update(
    {
        "app_workflow_intro": {
            "ru": "Выберите режим работы и запустите анализ.",
            "uk": "Оберіть режим роботи та запустіть аналіз.",
            "en": "Choose a workflow mode and start the analysis.",
        },
        "app_step_discover_seeds_title": {
            "ru": "1. Поиск seed-запросов",
            "uk": "1. Пошук seed-запитів",
            "en": "1. Discover seed queries",
        },
        "app_step_discover_seeds_desc": {
            "ru": "Соберите стартовые запросы и URL для дальнейшей обработки.",
            "uk": "Зберіть стартові запити та URL для подальшої обробки.",
            "en": "Collect starter queries and URLs for downstream processing.",
        },
        "app_step_score_cluster_title": {
            "ru": "2. Оценка и кластеризация",
            "uk": "2. Оцінка та кластеризація",
            "en": "2. Score and cluster",
        },
        "app_step_score_cluster_desc": {
            "ru": "Проверьте релевантность, сгруппируйте термины и отберите кандидаты.",
            "uk": "Перевірте релевантність, згрупуйте терміни та відберіть кандидати.",
            "en": "Check relevance, group terms, and pick candidates.",
        },
        "app_step_review_serps_title": {
            "ru": "3. Проверка SERP",
            "uk": "3. Перевірка SERP",
            "en": "3. Review SERPs",
        },
        "app_step_review_serps_desc": {
            "ru": "Сопоставьте выдачу, Ads и подсказки перед экспортом.",
            "uk": "Зіставте видачу, Ads та підказки перед експортом.",
            "en": "Compare SERP, Ads, and suggestions before export.",
        },
        "app_step_export_artifacts_title": {
            "ru": "4. Экспорт артефактов",
            "uk": "4. Експорт артефактів",
            "en": "4. Export artifacts",
        },
        "app_step_export_artifacts_desc": {
            "ru": "Сохраните Excel, CSV и сопутствующие результаты.",
            "uk": "Збережіть Excel, CSV та супровідні результати.",
            "en": "Save Excel, CSV, and supporting outputs.",
        },
        "app_summary_workflow_title": {
            "ru": "Сценарий",
            "uk": "Сценарій",
            "en": "Workflow",
        },
        "app_summary_current_route_desc": {
            "ru": "Текущий маршрут обработки и активный шаг.",
            "uk": "Поточний маршрут обробки та активний крок.",
            "en": "Current processing route and active step.",
        },
        "app_summary_provider_title": {
            "ru": "Провайдер",
            "uk": "Провайдер",
            "en": "Provider",
        },
        "app_summary_model_not_set_desc": {
            "ru": "Модель не задана. Проверьте выбранного провайдера.",
            "uk": "Модель не задано. Перевірте вибраного провайдера.",
            "en": "Model not set. Check the selected provider.",
        },
        "app_summary_exports_title": {
            "ru": "Экспорт",
            "uk": "Експорт",
            "en": "Exports",
        },
        "app_summary_excel_output_desc": {
            "ru": "Excel-вывод и связанные файлы результата.",
            "uk": "Excel-вивід і пов'язані файли результату.",
            "en": "Excel output and related result files.",
        },
        "ui_enabled": {
            "ru": "Включено",
            "uk": "Увімкнено",
            "en": "Enabled",
        },
        "ui_disabled": {
            "ru": "Выключено",
            "uk": "Вимкнено",
            "en": "Disabled",
        },
        "serp_pre_step_suffix": {
            "ru": "Режим SERP",
            "uk": "Режим SERP",
            "en": "SERP mode",
        },
        "status_desc": {
            "ru": "Живой журнал и состояние очистки.",
            "uk": "Живий журнал і стан очищення.",
            "en": "Live log output and cleanup state.",
        },
        "results_spreadsheet_desc": {
            "ru": "Табличный вывод для быстрой проверки и экспорта.",
            "uk": "Табличний вивід для швидкої перевірки та експорту.",
            "en": "Spreadsheet-style output for quick review and export.",
        },
        "keyword_results_rows_title": {
            "ru": "Строки",
            "uk": "Рядки",
            "en": "Rows",
        },
        "keyword_results_rows_desc": {
            "ru": "Количество строк в текущем наборе результатов.",
            "uk": "Кількість рядків у поточному наборі результатів.",
            "en": "Current result set row count.",
        },
        "keyword_results_sources_title": {
            "ru": "Источники",
            "uk": "Джерела",
            "en": "Sources",
        },
        "keyword_results_sources_desc": {
            "ru": "Уникальные URL и связанные источники входных данных.",
            "uk": "Унікальні URL та пов'язані джерела вхідних даних.",
            "en": "Unique URLs and linked input sources.",
        },
        "keyword_results_autosave_title": {
            "ru": "Автосохранение",
            "uk": "Автозбереження",
            "en": "Auto-save",
        },
        "keyword_results_autosave_desc": {
            "ru": "Сохраняет ли интерфейс результаты при каждом обновлении.",
            "uk": "Чи зберігає інтерфейс результати під час кожного оновлення.",
            "en": "Whether the UI saves results on each refresh.",
        },
        "scraping_preview_desc": {
            "ru": "Промежуточный просмотр извлеченного текста и данных.",
            "uk": "Проміжний перегляд витягнутого тексту та даних.",
            "en": "Intermediate preview of extracted text and data.",
        },
        "keyword_selection_desc": {
            "ru": "Выбор ключевых слов с учетом источника и результата.",
            "uk": "Вибір ключових слів з урахуванням джерела та результату.",
            "en": "Keyword selection with source-aware context.",
        },
        "history_header_desc": {
            "ru": "Последние запуски, кеш и сохраненные записи.",
            "uk": "Останні запуски, кеш і збережені записи.",
            "en": "Recent runs, cache, and saved entries.",
        },
        "history_runs_title": {
            "ru": "Запуски",
            "uk": "Запуски",
            "en": "Runs",
        },
        "history_runs_desc": {
            "ru": "Недавние выполнения в текущем сеансе.",
            "uk": "Недавні виконання у поточному сеансі.",
            "en": "Recent executions in the current session.",
        },
        "history_cache_title": {
            "ru": "Кеш",
            "uk": "Кеш",
            "en": "Cache",
        },
        "history_cache_desc": {
            "ru": "Сколько данных остается доступным для повторного использования.",
            "uk": "Скільки даних залишається доступним для повторного використання.",
            "en": "How much data remains available for reuse.",
        },
        "history_total_title": {
            "ru": "Всего",
            "uk": "Усього",
            "en": "Total",
        },
        "history_total_desc": {
            "ru": "Совокупный объем сохраненных результатов и источников.",
            "uk": "Сукупний обсяг збережених результатів і джерел.",
            "en": "Aggregate size of saved results and sources.",
        },
        "serp_results_desc": {
            "ru": "Набор результатов SERP для текущего профиля.",
            "uk": "Набір результатів SERP для поточного профілю.",
            "en": "SERP results for the current profile.",
        },
        "serp_results_legend": {
            "ru": "Легенда отображения результатов SERP.",
            "uk": "Легенда відображення результатів SERP.",
            "en": "Legend for SERP result display.",
        },
        "serp_results_rows_title": {
            "ru": "Строки SERP",
            "uk": "Рядки SERP",
            "en": "SERP rows",
        },
        "serp_results_rows_desc": {
            "ru": "Число строк, показанных в выборке выдачи.",
            "uk": "Кількість рядків, показаних у вибірці видачі.",
            "en": "Rows shown in the SERP sample.",
        },
        "serp_results_keywords_title": {
            "ru": "Ключевые слова",
            "uk": "Ключові слова",
            "en": "Keywords",
        },
        "serp_results_keywords_desc": {
            "ru": "Термины, найденные в текущем SERP-профиле.",
            "uk": "Терміни, знайдені в поточному SERP-профілі.",
            "en": "Terms found in the current SERP profile.",
        },
        "serp_results_matches_title": {
            "ru": "Совпадения",
            "uk": "Збіги",
            "en": "Matches",
        },
        "serp_results_matches_desc": {
            "ru": "Сопоставление запросов, подсказок и найденных терминов.",
            "uk": "Зіставлення запитів, підказок і знайдених термінів.",
            "en": "Match-up of queries, suggestions, and found terms.",
        },
        "serp_related_desc": {
            "ru": "Связанные запросы и блок People Also Ask.",
            "uk": "Пов'язані запити та блок People Also Ask.",
            "en": "Related queries and People Also Ask.",
        },
        "serp_chain_desc": {
            "ru": "Результат Chain Ads остается рядом с SERP-данными.",
            "uk": "Результат Chain Ads залишається поруч із даними SERP.",
            "en": "Chained Ads output stays adjacent to SERP data.",
        },
        "serp_chain_results_desc": {
            "ru": "Связанные результаты, проверенные по текущему SERP.",
            "uk": "Пов'язані результати, перевірені за поточним SERP.",
            "en": "Related results validated against the current SERP.",
        },
        "candidate_selector_desc": {
            "ru": "Выбор кандидатов с учетом источника и связи с результатом.",
            "uk": "Вибір кандидатів з урахуванням джерела та зв'язку з результатом.",
            "en": "Candidate selection stays source-aware.",
        },
        "serp_domain_math_desc": {
            "ru": "Концентрация SERP и видимость на уровне домена.",
            "uk": "Концентрація SERP і видимість на рівні домену.",
            "en": "Domain-level SERP concentration and visibility.",
        },
        "seo_math_top_ngrams_desc": {
            "ru": "Топ n-грамм, сгруппированных по размеру.",
            "uk": "Топ n-грам, згрупованих за розміром.",
            "en": "Top n-grams grouped by size.",
        },
        "seo_math_tfidf_desc": {
            "ru": "Взвешивание терминов по текущему корпусу.",
            "uk": "Зважування термінів у поточному корпусі.",
            "en": "Term weighting across the current corpus.",
        },
        "seo_math_cooccurrence_desc": {
            "ru": "Термины, которые встречаются вместе.",
            "uk": "Терміни, що трапляються разом.",
            "en": "Terms that travel together.",
        },
        "seo_math_intent_desc": {
            "ru": "Разбор поискового намерения для корпуса.",
            "uk": "Розбір пошукового наміру для корпусу.",
            "en": "Search intent breakdown for the corpus.",
        },
        "seo_math_related_queries_desc": {
            "ru": "Связанные запросы и кандидаты из блока PAA.",
            "uk": "Пов'язані запити та кандидати з блоку PAA.",
            "en": "Related queries and PAA candidates.",
        },
        "ads_metric_enrichment_desc": {
            "ru": "Метрики Ads, обогащенные контекстом SERP.",
            "uk": "Метрики Ads, збагачені контекстом SERP.",
            "en": "Ads metrics enriched with SERP context.",
        },
        "serp_ads_overlap_gaps_desc": {
            "ru": "Пересечения и пробелы между SERP и Ads.",
            "uk": "Перетини та прогалини між SERP і Ads.",
            "en": "Overlap and gaps between SERP and Ads.",
        },
        "crawl_report_desc": {
            "ru": "Математические сигналы из обхода и итоговые экспортируемые данные.",
            "uk": "Математичні сигнали з обходу та підсумкові дані для експорту.",
            "en": "Crawl-derived math signals and downstream exports.",
        },
        "crawl_aggregate_terms_desc": {
            "ru": "Сводные текстовые сигналы из просканированных страниц.",
            "uk": "Зведені текстові сигнали зі сканованих сторінок.",
            "en": "Aggregate text signals from crawled pages.",
        },
        "generation_quality_report_desc": {
            "ru": "Скоринг элементов и обратная связь для регенерации.",
            "uk": "Скоринг елементів і зворотний зв'язок для регенерації.",
            "en": "Element scoring and regeneration feedback.",
        },
        "improvement_suggestions_desc": {
            "ru": "Подсказки для точечной переработки текста.",
            "uk": "Підказки для точкового переписування тексту.",
            "en": "Targeted rewrite hints.",
        },
        "seo_math_bm25f_scores_desc": {
            "ru": "BM25F-оценки для текущего профиля.",
            "uk": "BM25F-оцінки для поточного профілю.",
            "en": "BM25F scores for the current profile.",
        },
        "gen_math_tfidf_desc": {
            "ru": "Сигналы по TF-IDF из сгенерированного текста.",
            "uk": "Сигнали TF-IDF із згенерованого тексту.",
            "en": "High-signal terms from generated text.",
        },
        "gen_math_cooccurrence_desc": {
            "ru": "Сигналы ко-употребления из сгенерированного текста.",
            "uk": "Сигнали спільної зустрічності із згенерованого тексту.",
            "en": "Co-occurrence signals from generated text.",
        },
        "sidebar_settings_desc": {
            "ru": "Настройте интерфейс, провайдера и маршрут анализа.",
            "uk": "Налаштуйте інтерфейс, провайдера та маршрут аналізу.",
            "en": "Configure the active interface, provider, and analysis route.",
        },
        "sidebar_provider_desc": {
            "ru": "Выберите модель и параметры провайдера.",
            "uk": "Оберіть модель і параметри провайдера.",
            "en": "Select the active model and provider settings.",
        },
        "sidebar_serp_desc": {
            "ru": "Настройки поиска, выдачи и SERP-аналитики.",
            "uk": "Налаштування пошуку, видачі та SERP-аналітики.",
            "en": "Search routing, SERP settings, and analysis controls.",
        },
        "sidebar_seo_math_desc": {
            "ru": "Метрики, связанные с анализом текста и корпуса.",
            "uk": "Метрики, пов'язані з аналізом тексту та корпусу.",
            "en": "Enabled analysis for text and corpus metrics.",
        },
        "sidebar_cache_desc": {
            "ru": "Кеш, сохранение и политика обновления.",
            "uk": "Кеш, збереження та політика оновлення.",
            "en": "Cache retention and refresh policy.",
        },
        "sidebar_trends_desc": {
            "ru": "Поставщики трендов и параметры источников.",
            "uk": "Постачальники трендів та параметри джерел.",
            "en": "Trends providers and source settings.",
        },
        "sidebar_trends_local_desc": {
            "ru": "Локальный браузерный провайдер и его состояние.",
            "uk": "Локальний браузерний провайдер і його стан.",
            "en": "Local browser-backed provider status.",
        },
        "sidebar_scraper_desc": {
            "ru": "Опции браузера и сбор данных со страниц.",
            "uk": "Опції браузера та збір даних зі сторінок.",
            "en": "Optional browser and page scraping settings.",
        },
        "sidebar_crawl_desc": {
            "ru": "Ограничения обхода и параметры краулинга.",
            "uk": "Обмеження обходу та параметри краулінгу.",
            "en": "Crawl limits and follow-on settings.",
        },
        "sidebar_ads_desc": {
            "ru": "Параметры Ads и связанный контекст выдачи.",
            "uk": "Параметри Ads і пов'язаний контекст видачі.",
            "en": "Ads metrics enriched with SERP context.",
        },
        "sidebar_api_desc": {
            "ru": "Таймауты, повторы и параметры запросов.",
            "uk": "Таймаути, повтори та параметри запитів.",
            "en": "Timeouts and retry settings.",
        },
        "sidebar_prompts_desc": {
            "ru": "Текст промптов и их редактирование.",
            "uk": "Текст промптів та їх редагування.",
            "en": "Prompt text and prompt editing.",
        },
        "sidebar_storage_desc": {
            "ru": "Хранение, сроки и политика очистки.",
            "uk": "Зберігання, строки та політика очищення.",
            "en": "Retention limits and storage policy.",
        },
        "sidebar_logging_desc": {
            "ru": "Логи, отладка и вывод консоли.",
            "uk": "Логи, налагодження та вивід консолі.",
            "en": "Console, API, and log output.",
        },
        "sidebar_export_desc": {
            "ru": "Форматы вывода и настройки экспорта.",
            "uk": "Формати виводу та налаштування експорту.",
            "en": "Export defaults and output formats.",
        },
        # --- Collapsible top block: per-workflow 4-stage labels ---
        # Stage 4 (export) is shared across all workflows; stages 1-3 adapt per route.
        "app_top_show_details": {
            "ru": "Подробности и этапы",
            "uk": "Подробиці та етапи",
            "en": "Details and stages",
        },
        "app_stage_1_title": {
            "ru": "1. Ввод",
            "uk": "1. Введення",
            "en": "1. Input",
        },
        "app_stage_2_title": {
            "ru": "2. Обработка",
            "uk": "2. Обробка",
            "en": "2. Processing",
        },
        "app_stage_3_title": {
            "ru": "3. Анализ",
            "uk": "3. Аналіз",
            "en": "3. Analysis",
        },
        "app_stage_4_title": {
            "ru": "4. Экспорт",
            "uk": "4. Експорт",
            "en": "4. Export",
        },
        # Workflow-specific stage titles (keys namespaced by stage slot + mode)
        # URL -> LLM -> Ads (url_llm)
        "stage_url_input_desc": {
            "ru": "Исходные URL для извлечения ключевых слов.",
            "uk": "Вихідні URL для збору ключових слів.",
            "en": "Source URLs for keyword extraction.",
        },
        "stage_llm_keywords_desc": {
            "ru": "LLM извлекает коммерческие ключевые слова из контента.",
            "uk": "LLM збирає комерційні ключові слова з контенту.",
            "en": "LLM extracts commercial keywords from content.",
        },
        "stage_llm_keywords_title": {
            "ru": "2. LLM-ключевые слова",
            "uk": "2. LLM-ключові слова",
            "en": "2. LLM keywords",
        },
        "stage_ads_metrics_desc": {
            "ru": "Google Ads добавляет объёмы, конкуренцию и CPC.",
            "uk": "Google Ads додає обсяги, конкуренцію та CPC.",
            "en": "Google Ads adds volume, competition, and CPC.",
        },
        "stage_ads_metrics_title": {
            "ru": "3. Метрики Ads",
            "uk": "3. Метрики Ads",
            "en": "3. Ads metrics",
        },
        "stage_export_seo_desc": {
            "ru": "Экспорт в Excel/CSV и генерация SEO-текста.",
            "uk": "Експорт в Excel/CSV та генерація SEO-тексту.",
            "en": "Excel/CSV export and SEO text generation.",
        },
        "stage_export_seo_title": {
            "ru": "4. Экспорт + SEO",
            "uk": "4. Експорт + SEO",
            "en": "4. Export + SEO",
        },
        # URL -> Ads ideas (url_seed)
        "stage_url_input_title": {
            "ru": "1. Ввод URL",
            "uk": "1. Введення URL",
            "en": "1. URL input",
        },
        "stage_ads_ideas_desc": {
            "ru": "Google Ads подбирает идеи ключевых слов по теме URL.",
            "uk": "Google Ads підбирає ідеї ключових слів за темою URL.",
            "en": "Google Ads suggests keyword ideas for the URL topic.",
        },
        "stage_ads_ideas_title": {
            "ru": "2. Идеи Ads",
            "uk": "2. Ідеї Ads",
            "en": "2. Ads ideas",
        },
        "stage_select_desc": {
            "ru": "Отбор и кластеризация релевантных кандидатов.",
            "uk": "Відбір та кластеризація релевантних кандидатів.",
            "en": "Select and cluster the relevant candidates.",
        },
        "stage_select_title": {
            "ru": "3. Отбор",
            "uk": "3. Відбір",
            "en": "3. Selection",
        },
        "stage_export_desc": {
            "ru": "Сохраните Excel, CSV и связанные артефакты.",
            "uk": "Збережіть Excel, CSV та пов'язані артефакти.",
            "en": "Save Excel, CSV, and related artifacts.",
        },
        # Keyword seed -> Ads ideas (keyword_seed)
        "stage_keywords_title": {
            "ru": "1. Ключевые слова",
            "uk": "1. Ключові слова",
            "en": "1. Keywords",
        },
        "stage_keywords_desc": {
            "ru": "Стартовые запросы для расширения через Ads.",
            "uk": "Стартові запити для розширення через Ads.",
            "en": "Starter queries to expand through Ads.",
        },
        "stage_serp_ads_desc": {
            "ru": "SERP и Ads обогащают ключевые слова контекстом и метриками.",
            "uk": "SERP та Ads збагачують ключові слова контекстом і метриками.",
            "en": "SERP and Ads enrich keywords with context and metrics.",
        },
        "stage_serp_ads_title": {
            "ru": "3. SERP + Ads",
            "uk": "3. SERP + Ads",
            "en": "3. SERP + Ads",
        },
        # Keyword -> LLM SEO (keyword_llm)
        "stage_seo_gen_desc": {
            "ru": "LLM генерирует SEO-оптимизированный текст по ключевым словам.",
            "uk": "LLM генерує SEO-оптимізований текст за ключовими словами.",
            "en": "LLM generates SEO-optimized text from keywords.",
        },
        "stage_seo_gen_title": {
            "ru": "2. SEO-генерация",
            "uk": "2. SEO-генерація",
            "en": "2. SEO generation",
        },
        "stage_quality_report_desc": {
            "ru": "Отчёт качества и предложение улучшений.",
            "uk": "Звіт якості та пропозиція покращень.",
            "en": "Quality report and improvement suggestions.",
        },
        "stage_quality_report_title": {
            "ru": "3. Отчёт качества",
            "uk": "3. Звіт якості",
            "en": "3. Quality report",
        },
        # SERP analysis (serp_analysis)
        "stage_collect_serp_desc": {
            "ru": "Сбор результатов выдачи Google по ключевым словам.",
            "uk": "Збір результатів видачі Google за ключовими словами.",
            "en": "Gather Google SERP results for the keywords.",
        },
        "stage_collect_serp_title": {
            "ru": "2. Сбор SERP",
            "uk": "2. Збір SERP",
            "en": "2. Collect SERP",
        },
        "stage_serp_review_desc": {
            "ru": "Анализ конкурентов, контента и пробелов выдачи.",
            "uk": "Аналіз конкурентів, контенту та прогалин видачі.",
            "en": "Analyze competitors, content, and SERP gaps.",
        },
        "stage_serp_review_title": {
            "ru": "3. Анализ выдачи",
            "uk": "3. Аналіз видачі",
            "en": "3. SERP analysis",
        },
        # Crawl report (crawl_report)
        "stage_crawl_desc": {
            "ru": "Сканирование страниц и сбор структуры контента.",
            "uk": "Сканування сторінок та збір структури контенту.",
            "en": "Crawl pages and collect content structure.",
        },
        "stage_crawl_title": {
            "ru": "2. Сканирование",
            "uk": "2. Сканування",
            "en": "2. Crawling",
        },
        "stage_math_report_desc": {
            "ru": "Отчёт по метрикам и качеству собранного контента.",
            "uk": "Звіт за метриками та якістю зібраного контенту.",
            "en": "Metrics and quality report for crawled content.",
        },
        "stage_math_report_title": {
            "ru": "3. Отчёт math",
            "uk": "3. Звіт math",
            "en": "3. Math report",
        },
        # Google Trends (google_trends)
        "stage_trends_request_desc": {
            "ru": "Запрос данных популярности по ключевым словам.",
            "uk": "Запит даних популярності за ключовими словами.",
            "en": "Request popularity data for the keywords.",
        },
        "stage_trends_request_title": {
            "ru": "2. Запрос Trends",
            "uk": "2. Запит Trends",
            "en": "2. Trends request",
        },
        "stage_trends_analysis_desc": {
            "ru": "Анализ динамики, связанных запросов и сезонности.",
            "uk": "Аналіз динаміки, пов'язаних запитів та сезонності.",
            "en": "Analyze dynamics, related queries, and seasonality.",
        },
        "stage_trends_analysis_title": {
            "ru": "3. Анализ трендов",
            "uk": "3. Аналіз трендів",
            "en": "3. Trends analysis",
        },
    }
)

SUPPORTED_LANGUAGES = {"ru", "uk", "en"}

# MODULE_CONTRACT: config/i18n
# Purpose: Internationalization support providing UI string translations for Russian, Ukrainian, and English
# Rationale: Centralizes all user-facing strings so the UI can switch languages without code changes
# Dependencies: streamlit (session state for current language)
 # Exports: TRANSLATIONS, SUPPORTED_LANGUAGES, get_lang, t
# LINKS: requirements.xml#UC-001, knowledge-graph.xml#MOD-001
# MODULE_MAP: config/i18n.py
# Public Functions: get_lang, t
# Private Helpers: (none)
# Key Semantic Blocks: block_i18n_translations_dict_data, block_i18n_lookup_lang_resolve
# Critical Flows: every UI component calls t() for display strings
# Verification: V-SUITE
# CHANGE_SUMMARY: Added module-level contracts; replaced module docstring with GRACE header; added FUNCTION_CONTRACT blocks for get_lang and t; removed post-declaration docstrings
# FUNCTION_CONTRACT: get_lang
# Purpose: Resolve the current UI language from session state with a safe default
# Input: (none)
# Output: str — one of SUPPORTED_LANGUAGES
# Side Effects: reads st.session_state["ui_lang"]
# Business Rules: defaults to "ru" if unset or unsupported
# Failure Modes: never raises
# LINKS: requirements.xml#UC-001
def get_lang() -> str:
    lang = st.session_state.get("ui_lang", "ru")
    return lang if lang in SUPPORTED_LANGUAGES else "ru"


# FUNCTION_CONTRACT: t
# Purpose: Retrieve a translated string by key for the current UI language, with optional format interpolation
# Input: key (str) — translation key, **kwargs — format variables
# Output: str — translated and formatted string, or bracketed key fallback
# Side Effects: reads st.session_state["ui_lang"] via get_lang()
# Business Rules: falls back to Russian if current language missing; falls back to "[key]" placeholder if key absent
# Failure Modes: never raises; returns "[key]" placeholder for missing keys
# LINKS: requirements.xml#UC-001
def t(key: str, **kwargs) -> str:
    lang = get_lang()
    entry = TRANSLATIONS.get(key, {})
    text = entry.get(lang, entry.get("ru", f"[{key}]"))
    if kwargs:
        text = text.format(**kwargs)
    return text
