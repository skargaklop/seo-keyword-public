"""
Internationalization (i18n) module — provides UI string translations.
Supported languages: Russian (ru), Ukrainian (uk), English (en).
"""

import streamlit as st
from typing import Dict


TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # --- App main ---
    "app_title": {
        "ru": "🚀 Auto SEO Keyword Planner",
        "uk": "🚀 Auto SEO Keyword Planner",
    },
    "app_description": {
        "ru": "Извлечение коммерческих ключевых слов из URL, обогащение метриками Google Ads и экспорт в Excel.",
        "uk": "Витяг комерційних ключових слів з URL, збагачення метриками Google Ads та експорт в Excel.",
    },
    "no_api_keys": {
        "ru": "⚠️ Не найдено ни одного API ключа. Проверьте файл .env.",
        "uk": "⚠️ Не знайдено жодного API ключа. Перевірте файл .env.",
    },
    "enter_url_header": {
        "ru": "1. Ввод URL",
        "uk": "1. Введення URL",
    },
    "enter_url_placeholder": {
        "ru": "Введите URL (по одному на строку)",
        "uk": "Введіть URL (по одному на рядок)",
    },
    "upload_file": {
        "ru": "Или загрузите файл (txt/csv)",
        "uk": "Або завантажте файл (txt/csv)",
    },
    "status_header": {
        "ru": "Статус",
        "uk": "Статус",
    },
    "show_logs": {
        "ru": "Показывать логи (Live)",
        "uk": "Показувати логи (Live)",
    },
    "start_analysis": {
        "ru": "🚀 Запустить анализ",
        "uk": "🚀 Запустити аналіз",
    },
    "enter_url_warning": {
        "ru": "Пожалуйста, введите URL.",
        "uk": "Будь ласка, введіть URL.",
    },
    # --- Sidebar ---
    "settings_header": {
        "ru": "⚙️ Настройки",
        "uk": "⚙️ Налаштування",
    },
    "ui_language": {
        "ru": "🌐 Язык интерфейса",
        "uk": "🌐 Мова інтерфейсу",
    },
    "llm_provider": {
        "ru": "LLM Провайдер",
        "uk": "LLM Провайдер",
    },
    "no_api_keys_sidebar": {
        "ru": "В .env не найдены API ключи. Пожалуйста, настройте хотя бы одного провайдера.",
        "uk": "В .env не знайдено API ключів. Будь ласка, налаштуйте хоча б одного провайдера.",
    },
    "select_provider": {
        "ru": "Выберите провайдера",
        "uk": "Оберіть провайдера",
    },
    "model_name": {
        "ru": "Название модели",
        "uk": "Назва моделі",
    },
    "max_keywords_per_url": {
        "ru": "Макс. слов на URL",
        "uk": "Макс. слів на URL",
    },
    "location": {
        "ru": "Локация",
        "uk": "Локація",
    },
    "language": {
        "ru": "Язык",
        "uk": "Мова",
    },
    "currency": {
        "ru": "Валюта",
        "uk": "Валюта",
    },
    "currency_help": {
        "ru": "В этой валюте будут показаны и экспортированы Low CPC / High CPC.",
        "uk": "У цій валюті будуть показані та експортовані Low CPC / High CPC.",
    },
    "api_params": {
        "ru": "🔧 Параметры API",
        "uk": "🔧 Параметри API",
    },
    "request_timeout": {
        "ru": "Таймаут ответа API (сек)",
        "uk": "Таймаут відповіді API (сек)",
    },
    "request_timeout_help": {
        "ru": "Максимальное время ожидания ответа от API. Не управляет паузой между повторными попытками.",
        "uk": "Максимальний час очікування відповіді від API. Не керує паузою між повторними спробами.",
    },
    "delay_between_requests": {
        "ru": "Задержка между обычными запросами (сек)",
        "uk": "Затримка між звичайними запитами (сек)",
    },
    "delay_between_requests_help": {
        "ru": "Пауза между последовательными обычными запросами к API для снижения риска rate-limit.",
        "uk": "Пауза між послідовними звичайними запитами до API для зниження ризику rate-limit.",
    },
    "retry_count": {
        "ru": "Количество повторных попыток",
        "uk": "Кількість повторних спроб",
    },
    "retry_count_help": {
        "ru": "Сколько раз повторять запрос при ошибке API перед тем, как сдаться.",
        "uk": "Скільки разів повторювати запит при помилці API перед тим, як здатися.",
    },
    "retry_delay": {
        "ru": "Задержка между retry (сек)",
        "uk": "Затримка між retry (сек)",
    },
    "retry_delay_help": {
        "ru": "Пауза перед каждой повторной попыткой после ошибки API.",
        "uk": "Пауза перед кожною повторною спробою після помилки API.",
    },
    "system_prompts": {
        "ru": "📝 Системные промпты",
        "uk": "📝 Системні промпти",
    },
    "keyword_prompt_label": {
        "ru": "Промпт: Извлечение ключевых слов",
        "uk": "Промпт: Витяг ключових слів",
    },
    "keyword_prompt_desc": {
        "ru": "**Промпт для сбора ключевых слов**\n\nДоступные переменные:\n- `{max_keywords}` — максимальное количество ключевых слов для извлечения",
        "uk": "**Промпт для збору ключових слів**\n\nДоступні змінні:\n- `{max_keywords}` — максимальна кількість ключових слів для Витяг",
    },
    "seo_prompt_label": {
        "ru": "Промпт: SEO описание",
        "uk": "Промпт: SEO опис",
    },
    "seo_prompt_desc": {
        "ru": "**Промпт для генерации SEO описания**\n\nДоступные переменные:\n- `{language}` — язык генерации (например, Russian, Ukrainian)\n- `{keywords_list}` — список ключевых слов с объёмами поиска",
        "uk": "**Промпт для генерації SEO опису**\n\nДоступні змінні:\n- `{language}` — мова генерації (наприклад, Russian, Ukrainian)\n- `{keywords_list}` — список ключових слів з обсягами пошуку",
    },
    "export_header": {
        "ru": "📁 Экспорт",
        "uk": "📁 Експорт",
    },
    "auto_save_excel": {
        "ru": "Автосохранение Excel в outputs/",
        "uk": "Автозбереження Excel в outputs/",
    },
    "cleanup_days_label": {
        "ru": "Удалять файлы из outputs/ старше (дней)",
        "uk": "Видаляти файли з outputs/ старше (днів)",
    },
    "cleanup_days_help": {
        "ru": "Автоматически удалять файлы из папки outputs/ старше указанного количества дней. 0 = не удалять.",
        "uk": "Автоматично видаляти файли з папки outputs/ старше вказаної кількості днів. 0 = не видаляти.",
    },
    "storage_limits_header": {
        "ru": "Хранение и лимиты",
        "uk": "Зберігання та ліміти",
    },
    "api_retention_days_label": {
        "ru": "Хранить API-логи (дней)",
        "uk": "Зберігати API-логи (днів)",
    },
    "api_retention_days_help": {
        "ru": "Удалять API-логи старше указанного количества дней. 0 = не удалять.",
        "uk": "Видаляти API-логи старші за вказану кількість днів. 0 = не видаляти.",
    },
    "history_retention_days_label": {
        "ru": "Хранить историю (дней)",
        "uk": "Зберігати історію (днів)",
    },
    "history_retention_days_help": {
        "ru": "Удалять записи истории старше указанного количества дней. 0 = не удалять.",
        "uk": "Видаляти записи історії старші за вказану кількість днів. 0 = не видаляти.",
    },
    "upload_max_file_size_mb_label": {
        "ru": "Максимальный размер файла (MB)",
        "uk": "Максимальний розмір файлу (MB)",
    },
    "upload_max_file_size_mb_help": {
        "ru": "Файлы больше этого лимита будут отклонены при загрузке.",
        "uk": "Файли більші за цей ліміт буде відхилено під час завантаження.",
    },
    "upload_max_rows_label": {
        "ru": "Максимум строк/значений из файла",
        "uk": "Максимум рядків/значень з файлу",
    },
    "upload_max_rows_help": {
        "ru": "После чтения файла будет использовано не больше этого количества строк/значений.",
        "uk": "Після читання файлу буде використано не більше цієї кількості рядків/значень.",
    },
    "upload_file_too_large": {
        "ru": "Файл {filename} превышает лимит {max_size_mb} MB.",
        "uk": "Файл {filename} перевищує ліміт {max_size_mb} MB.",
    },
    "upload_file_too_many_rows": {
        "ru": "Файл {filename} содержит больше допустимых строк/значений ({max_rows}).",
        "uk": "Файл {filename} містить більше допустимих рядків/значень ({max_rows}).",
    },
    "upload_file_unsupported_format": {
        "ru": "Неподдерживаемый формат файла: {filename}. Используйте .txt или .csv.",
        "uk": "Непідтримуваний формат файлу: {filename}. Використовуйте .txt або .csv.",
    },
    "upload_file_parse_error": {
        "ru": "Не удалось прочитать файл {filename}: {error}",
        "uk": "Не вдалося прочитати файл {filename}: {error}",
    },
    "save_settings": {
        "ru": "💾 Сохранить настройки",
        "uk": "💾 Зберегти налаштування",
    },
    "settings_saved": {
        "ru": "✅ Настройки сохранены!",
        "uk": "✅ Налаштування збережено!",
    },
    "settings_save_error": {
        "ru": "Ошибка сохранения",
        "uk": "Помилка збереження",
    },
    "logging_header": {
        "ru": "Логирование",
        "uk": "Логування",
    },
    "log_app_level": {
        "ru": "Уровень app.log",
        "uk": "Рівень app.log",
    },
    "log_console_enabled": {
        "ru": "Включить вывод в консоль",
        "uk": "Увімкнути вивід у консоль",
    },
    "log_console_level": {
        "ru": "Уровень консоли",
        "uk": "Рівень консолі",
    },
    "log_api_enabled": {
        "ru": "Включить лог API-запросов",
        "uk": "Увімкнути лог API-запитів",
    },
    "log_api_level": {
        "ru": "Уровень API-лога",
        "uk": "Рівень API-логу",
    },
    "log_error_level": {
        "ru": "Уровень errors.log",
        "uk": "Рівень errors.log",
    },
    "log_test_runs": {
        "ru": "Логировать pytest/test-запуски",
        "uk": "Логувати pytest/test-запуски",
    },
    "pipeline_validating_urls": {
        "ru": "Проверка URL...",
        "uk": "Перевірка URL...",
    },
    "pipeline_invalid_urls_skipped": {
        "ru": "⚠️ Пропущено некорректных URL: {count}",
        "uk": "⚠️ Пропущено некоректних URL: {count}",
    },
    "pipeline_no_valid_urls": {
        "ru": "Нет валидных URL для обработки.",
        "uk": "Немає валідних URL для обробки.",
    },
    "pipeline_scraping_content": {
        "ru": "Скрапинг контента...",
        "uk": "Скрапінг контенту...",
    },
    "pipeline_no_content_scraped": {
        "ru": "Не удалось получить контент ни для одного URL. Проверьте доступность сайта и SSL-сертификат.",
        "uk": "Не вдалося отримати контент ні для жодного URL. Перевірте доступність сайту та SSL-сертифікат.",
    },
    "pipeline_extracting_keywords": {
        "ru": "Извлечение ключевых слов через AI...",
        "uk": "Витяг ключових слів через AI...",
    },
    "pipeline_analyzing_url": {
        "ru": "Анализ {idx}/{total}: {url}",
        "uk": "Аналіз {idx}/{total}: {url}",
    },
    "pipeline_processing_deduplicating": {
        "ru": "Обработка и дедупликация...",
        "uk": "Обробка та дедуплікація...",
    },
    "pipeline_no_keywords_found": {
        "ru": "Не найдено ключевых слов, подходящих под критерии.",
        "uk": "Не знайдено ключових слів, що відповідають критеріям.",
    },
    "pipeline_fetching_metrics": {
        "ru": "Получение метрик для {count} ключевых слов...",
        "uk": "Отримання метрик для {count} ключових слів...",
    },
    "pipeline_querying_google_ads": {
        "ru": "Запрос к Google Ads API...",
        "uk": "Запит до Google Ads API...",
    },
    "pipeline_finalizing_report": {
        "ru": "Финализация отчета...",
        "uk": "Фіналізація звіту...",
    },
    "pipeline_done": {
        "ru": "Готово!",
        "uk": "Готово!",
    },
    "pipeline_analysis_complete": {
        "ru": "Анализ завершен!",
        "uk": "Аналіз завершено!",
    },
    # --- Results ---
    "results_header": {
        "ru": "📊 Результаты",
        "uk": "📊 Результати",
    },
    "autosave_error": {
        "ru": "Ошибка автосохранения Excel",
        "uk": "Помилка автозбереження Excel",
    },
    "download_excel": {
        "ru": "📥 Скачать Excel",
        "uk": "📥 Завантажити Excel",
    },
    "export_error": {
        "ru": "Ошибка подготовки экспорта",
        "uk": "Помилка підготовки експорту",
    },
    "download_csv": {
        "ru": "📥 Скачать CSV",
        "uk": "📥 Завантажити CSV",
    },
    "csv_error": {
        "ru": "Ошибка подготовки CSV",
        "uk": "Помилка підготовки CSV",
    },
    "total_keywords_stat": {
        "ru": "Всего уникальных слов: {count} | Обработано источников: {sources}",
        "uk": "Всього унікальних слів: {count} | Оброблено джерел: {sources}",
    },
    "scraping_preview": {
        "ru": "🔍 Предпросмотр скрапинга",
        "uk": "🔍 Попередній перегляд скрапінгу",
    },
    "keyword_selection_header": {
        "ru": "🔑 Выбор ключевых слов",
        "uk": "🔑 Вибір ключових слів",
    },
    "select_keywords_desc": {
        "ru": "Выберите ключевые слова для генерации SEO текстов:",
        "uk": "Оберіть ключові слова для генерації SEO текстів:",
    },
    "add_keyword_manual": {
        "ru": "➕ Добавить ключевое слово вручную (введите и нажмите Enter)",
        "uk": "➕ Додати ключове слово вручну (введіть і натисніть Enter)",
    },
    "for_which_url": {
        "ru": "Для какого URL добавить?",
        "uk": "Для якого URL додати?",
    },
    "add_button": {
        "ru": "Добавить",
        "uk": "Додати",
    },
    "keywords_count": {
        "ru": "ключевых слов",
        "uk": "ключових слів",
    },
    "select_all": {
        "ru": "Выбрать все",
        "uk": "Обрати все",
    },
    "selected_keywords_stat": {
        "ru": "Выбрано ключевых слов: {selected} из {total} для {urls} URL",
        "uk": "Обрано ключових слів: {selected} з {total} для {urls} URL",
    },
    "keyword_ideas_header": {
        "ru": "💡 Идеи ключевых слов Keyword Planner",
        "uk": "💡 Ідеї ключових слів Keyword Planner",
    },
    "keyword_ideas_desc": {
        "ru": "Сгенерируйте дополнительные идеи ключевых слов из Google Keyword Planner перед переходом к генерации SEO-текстов.",
        "uk": "Згенеруйте додаткові ідеї ключових слів із Google Keyword Planner перед переходом до генерації SEO-текстів.",
    },
    "keyword_ideas_seed_keywords": {
        "ru": "Ключевые слова для KeywordSeed",
        "uk": "Ключові слова для KeywordSeed",
    },
    "keyword_ideas_seed_keywords_stat": {
        "ru": "Выбрано для KeywordSeed: {selected} из {total} (лимит запроса: {limit})",
        "uk": "Обрано для KeywordSeed: {selected} з {total} (ліміт запиту: {limit})",
    },
    "use_url_as_seed": {
        "ru": "Использовать URL как seed",
        "uk": "Використовувати URL як seed",
    },
    "keyword_only_seed": {
        "ru": "Только ключевые слова",
        "uk": "Лише ключові слова",
    },
    "generate_keyword_ideas_button": {
        "ru": "💡 Сгенерировать идеи Keyword Planner",
        "uk": "💡 Згенерувати ідеї Keyword Planner",
    },
    "keyword_ideas_generating": {
        "ru": "Генерация идей ключевых слов...",
        "uk": "Генерація ідей ключових слів...",
    },
    "keyword_ideas_processing_url": {
        "ru": "Обработка {url} | Режим: {mode}",
        "uk": "Обробка {url} | Режим: {mode}",
    },
    "keyword_ideas_skip_no_seed_keywords": {
        "ru": "Пропуск {url}: не выбрано ни одного ключевого слова для KeywordSeed.",
        "uk": "Пропуск {url}: не обрано жодного ключового слова для KeywordSeed.",
    },
    "keyword_ideas_seed_limit_notice": {
        "ru": "Для {url} выбрано {selected} ключевых слов. Google Ads поддерживает только {limit}, поэтому будут использованы первые {used}.",
        "uk": "Для {url} обрано {selected} ключових слів. Google Ads підтримує лише {limit}, тому буде використано перші {used}.",
    },
    "keyword_ideas_generation_complete": {
        "ru": "Идеи Keyword Planner сгенерированы.",
        "uk": "Ідеї Keyword Planner згенеровано.",
    },
    "keyword_ideas_empty": {
        "ru": "Keyword Planner не вернул новых идей для выбранного seed-режима.",
        "uk": "Keyword Planner не повернув нових ідей для вибраного seed-режиму.",
    },
    "keyword_ideas_add_button": {
        "ru": "Добавить выбранные идеи в список ключевых слов",
        "uk": "Додати вибрані ідеї до списку ключових слів",
    },
    "keyword_ideas_select_warning": {
        "ru": "Выберите хотя бы одну идею перед добавлением.",
        "uk": "Оберіть хоча б одну ідею перед додаванням.",
    },
    "keyword_ideas_added_success": {
        "ru": "Добавлено идей ключевых слов: {count}",
        "uk": "Додано ідей ключових слів: {count}",
    },
    "seo_generation_header": {
        "ru": "📝 Генерация SEO текстов",
        "uk": "📝 Генерація SEO текстів",
    },
    "generate_seo_button": {
        "ru": "✨ Сгенерировать SEO тексты",
        "uk": "✨ Згенерувати SEO тексти",
    },
    "generating": {
        "ru": "Генерация текстов...",
        "uk": "Генерація текстів...",
    },
    "generating_progress": {
        "ru": "Генерация...",
        "uk": "Генерація...",
    },
    "generating_url": {
        "ru": "Генерация {idx}/{total}: {url}",
        "uk": "Генерація {idx}/{total}: {url}",
    },
    "processing_url": {
        "ru": "Обработка: {url}",
        "uk": "Обробка: {url}",
    },
    "no_content_for_url": {
        "ru": "Нет контента для {url}",
        "uk": "Немає контенту для {url}",
    },
    "generation_complete": {
        "ru": "Генерация завершена!",
        "uk": "Генерацію завершено!",
    },
    "seo_success": {
        "ru": "SEO тексты успешно сгенерированы! Смотрите результаты ниже.",
        "uk": "SEO тексти успішно згенеровано! Дивіться результати нижче.",
    },
    "seo_results_header": {
        "ru": "📝 Результаты генерации текстов",
        "uk": "📝 Результати генерації текстів",
    },
    "download_texts_excel": {
        "ru": "📥 Скачать тексты (Excel)",
        "uk": "📥 Завантажити тексти (Excel)",
    },
    "download_texts_csv": {
        "ru": "📥 Скачать тексты (CSV)",
        "uk": "📥 Завантажити тексти (CSV)",
    },
    "seo_autosave_error": {
        "ru": "Ошибка автосохранения SEO текстов",
        "uk": "Помилка автозбереження SEO текстів",
    },
    "export_error_generic": {
        "ru": "Ошибка экспорта",
        "uk": "Помилка експорту",
    },
    "csv_export_error": {
        "ru": "Ошибка CSV экспорта",
        "uk": "Помилка CSV експорту",
    },
    "history_header": {
        "ru": "📜 История запросов",
        "uk": "📜 Історія запитів",
    },
    "history_empty": {
        "ru": "История пуста.",
        "uk": "Історія порожня.",
    },
    "chars": {
        "ru": "символов",
        "uk": "символів",
    },
    "col_keywords": {
        "ru": "Ключевые слова",
        "uk": "Ключові слова",
    },
    "col_seo_text": {
        "ru": "SEO текст",
        "uk": "SEO текст",
    },
    "workflow_mode_label": {
        "ru": "Режим сценария",
        "uk": "Режим сценарію",
    },
    "workflow_mode_url_llm": {
        "ru": "URL -> LLM -> Ads",
        "uk": "URL -> LLM -> Ads",
    },
    "workflow_mode_url_seed": {
        "ru": "URL -> Идеи Ads",
        "uk": "URL -> Ідеї Ads",
    },
    "workflow_mode_keyword_seed": {
        "ru": "Ключевые слова -> Идеи Ads",
        "uk": "Ключові слова -> Ідеї Ads",
    },
    "keyword_seed_header": {
        "ru": "1. Ввод ключевых слов",
        "uk": "1. Введення ключових слів",
    },
    "keyword_seed_placeholder": {
        "ru": "Введите по одному ключевому слову на строку",
        "uk": "Введіть по одному ключовому слову на рядок",
    },
    "keyword_seed_warning": {
        "ru": "Пожалуйста, введите хотя бы одно ключевое слово.",
        "uk": "Будь ласка, введіть хоча б одне ключове слово.",
    },
    "url_seed_start_seo": {
        "ru": "Перейти к написанию SEO текста",
        "uk": "Перейти до написання SEO тексту",
    },
    "url_seed_start_seo_help": {
        "ru": "Скрапинг выбранных URL запустится только тогда, когда вы будете готовы генерировать SEO-текст.",
        "uk": "Скрапінг вибраних URL запуститься лише тоді, коли ви будете готові генерувати SEO-текст.",
    },
    "keyword_seed_source_label": {
        "ru": "Ручной ввод ключевых слов",
        "uk": "Ручне введення ключових слів",
    },
    "history_restore_checkpoint": {
        "ru": "Восстановить checkpoint",
        "uk": "Відновити checkpoint",
    },
    "history_restore_success": {
        "ru": "Checkpoint из истории восстановлен.",
        "uk": "Checkpoint з історії відновлено.",
    },
    "history_regenerate_keywords": {
        "ru": "Перегенерировать ключевые слова",
        "uk": "Перегенерувати ключові слова",
    },
}

SUPPORTED_LANGUAGES = {"ru", "uk", "en"}

EN_TRANSLATIONS: Dict[str, str] = {
    "app_title": "🚀 Auto SEO Keyword Planner",
    "app_description": "Extract commercial keywords from URLs, enrich them with Google Ads metrics, and export to Excel.",
    "no_api_keys": "⚠️ No API keys found. Check your .env file.",
    "enter_url_header": "1. URL input",
    "enter_url_placeholder": "Enter one URL per line",
    "upload_file": "Or upload a file (txt/csv)",
    "status_header": "Status",
    "show_logs": "Show logs (Live)",
    "start_analysis": "🚀 Start analysis",
    "enter_url_warning": "Please enter at least one URL.",
    "settings_header": "⚙️ Settings",
    "ui_language": "Interface language",
    "llm_provider": "LLM provider",
    "no_api_keys_sidebar": "No provider API keys were found in .env. Please configure at least one provider.",
    "select_provider": "Select provider",
    "model_name": "Model name",
    "max_keywords_per_url": "Max keywords per URL",
    "location": "Location",
    "language": "Language",
    "currency": "Currency",
    "currency_help": "Low CPC and High CPC will be displayed and exported in this currency.",
    "api_params": "🔧 API parameters",
    "request_timeout": "API response timeout (sec)",
    "request_timeout_help": "Maximum time to wait for an API response. This does not control the pause between retries.",
    "delay_between_requests": "Delay between normal requests (sec)",
    "delay_between_requests_help": "Pause between sequential API requests to reduce rate-limit risk.",
    "retry_count": "Retry attempts",
    "retry_count_help": "How many times to retry a failed API request before giving up.",
    "retry_delay": "Delay between retries (sec)",
    "retry_delay_help": "Pause before each retry after an API error.",
    "system_prompts": "📝 System prompts",
    "keyword_prompt_label": "Prompt: Keyword extraction",
    "keyword_prompt_desc": "**Prompt for keyword extraction**\n\nAvailable variables:\n- `{max_keywords}` - maximum number of keywords to extract",
    "seo_prompt_label": "Prompt: SEO description",
    "seo_prompt_desc": "**Prompt for SEO text generation**\n\nAvailable variables:\n- `{language}` - generation language (for example, English, Russian, Ukrainian)\n- `{keywords_list}` - list of keywords with search volumes",
    "export_header": "📁 Export",
    "auto_save_excel": "Auto-save Excel files to outputs/",
    "cleanup_days_label": "Delete files from outputs/ older than (days)",
    "cleanup_days_help": "Automatically delete files from outputs/ older than the specified number of days. 0 = keep everything.",
    "save_settings": "💾 Save settings",
    "settings_saved": "✅ Settings saved.",
    "settings_save_error": "Failed to save settings",
    "logging_header": "Logging",
    "log_app_level": "app.log level",
    "log_console_enabled": "Enable console output",
    "log_console_level": "Console level",
    "log_api_enabled": "Enable API request logging",
    "log_api_level": "API log level",
    "log_error_level": "errors.log level",
    "log_test_runs": "Log pytest/test runs",
    "pipeline_validating_urls": "Validating URLs...",
    "pipeline_invalid_urls_skipped": "⚠️ Invalid URLs skipped: {count}",
    "pipeline_no_valid_urls": "No valid URLs to process.",
    "pipeline_scraping_content": "Scraping content...",
    "pipeline_no_content_scraped": "Could not extract content for any URL. Check that the site is reachable and its SSL certificate is valid.",
    "pipeline_extracting_keywords": "Extracting keywords with AI...",
    "pipeline_analyzing_url": "Analyzing {idx}/{total}: {url}",
    "pipeline_processing_deduplicating": "Processing and deduplicating...",
    "pipeline_no_keywords_found": "No keywords matching the criteria were found.",
    "pipeline_fetching_metrics": "Fetching metrics for {count} keywords...",
    "pipeline_querying_google_ads": "Querying Google Ads API...",
    "pipeline_finalizing_report": "Finalizing report...",
    "pipeline_done": "Done!",
    "pipeline_analysis_complete": "Analysis complete!",
    "results_header": "📊 Results",
    "autosave_error": "Excel auto-save failed",
    "download_excel": "📥 Download Excel",
    "export_error": "Failed to prepare export",
    "download_csv": "📥 Download CSV",
    "csv_error": "Failed to prepare CSV",
    "total_keywords_stat": "Total unique keywords: {count} | Sources processed: {sources}",
    "scraping_preview": "🔍 Scraping preview",
    "keyword_selection_header": "🔑 Keyword selection",
    "select_keywords_desc": "Select the keywords to use for SEO text generation:",
    "add_keyword_manual": "➕ Add a keyword manually (type it and press Enter)",
    "for_which_url": "Which URL should receive this keyword?",
    "add_button": "Add",
    "keywords_count": "keywords",
    "select_all": "Select all",
    "selected_keywords_stat": "Selected keywords: {selected} of {total} for {urls} URLs",
    "keyword_ideas_header": "💡 Keyword Planner ideas",
    "keyword_ideas_desc": "Generate additional keyword ideas from Google Keyword Planner before moving on to SEO text generation.",
    "keyword_ideas_seed_keywords": "KeywordSeed keywords",
    "keyword_ideas_seed_keywords_stat": "Selected for KeywordSeed: {selected} of {total} (request limit: {limit})",
    "use_url_as_seed": "Use URL as seed",
    "keyword_only_seed": "Keywords only",
    "generate_keyword_ideas_button": "💡 Generate Keyword Planner ideas",
    "keyword_ideas_generating": "Generating keyword ideas...",
    "keyword_ideas_processing_url": "Processing {url} | Mode: {mode}",
    "keyword_ideas_skip_no_seed_keywords": "Skipping {url}: no keywords selected for KeywordSeed.",
    "keyword_ideas_seed_limit_notice": "Selected {selected} keywords for {url}. Google Ads supports only {limit}, so the first {used} will be used.",
    "keyword_ideas_generation_complete": "Keyword ideas generated.",
    "keyword_ideas_empty": "Keyword Planner returned no ideas for the selected seed mode.",
    "keyword_ideas_add_button": "Add selected ideas to the keyword list",
    "keyword_ideas_select_warning": "Select at least one idea before adding it.",
    "keyword_ideas_added_success": "Added keyword ideas: {count}",
    "seo_generation_header": "📝 SEO text generation",
    "generate_seo_button": "✨ Generate SEO texts",
    "generating": "Generating texts...",
    "generating_progress": "Generating...",
    "generating_url": "Generating {idx}/{total}: {url}",
    "processing_url": "Processing: {url}",
    "no_content_for_url": "No content available for {url}",
    "generation_complete": "Generation complete!",
    "seo_success": "SEO texts were generated successfully. See the results below.",
    "seo_results_header": "📝 SEO text results",
    "download_texts_excel": "📥 Download texts (Excel)",
    "download_texts_csv": "📥 Download texts (CSV)",
    "seo_autosave_error": "SEO text auto-save failed",
    "export_error_generic": "Export failed",
    "csv_export_error": "CSV export failed",
    "history_header": "📜 Request history",
    "history_empty": "History is empty.",
    "chars": "characters",
    "col_keywords": "Keywords",
    "col_seo_text": "SEO text",
    "workflow_mode_label": "Workflow mode",
    "workflow_mode_url_llm": "URL -> LLM -> Ads",
    "workflow_mode_url_seed": "URL -> Ads ideas",
    "workflow_mode_keyword_seed": "Keyword seed -> Ads ideas",
    "keyword_seed_header": "1. Keyword input",
    "keyword_seed_placeholder": "Enter one keyword per line",
    "keyword_seed_warning": "Please enter at least one keyword seed.",
    "url_seed_start_seo": "Continue to SEO",
    "url_seed_start_seo_help": "Scraping for the selected URLs will start only when you are ready to generate SEO text.",
    "keyword_seed_source_label": "Manual keyword input",
    "history_restore_checkpoint": "Restore checkpoint",
    "history_restore_success": "Checkpoint restored from history.",
    "history_regenerate_keywords": "Regenerate keywords",
}

EN_TRANSLATIONS.update(
    {
        "storage_limits_header": "Storage and limits",
        "api_retention_days_label": "Keep API logs (days)",
        "api_retention_days_help": "Delete API logs older than the specified number of days. 0 = keep everything.",
        "history_retention_days_label": "Keep history (days)",
        "history_retention_days_help": "Delete history entries older than the specified number of days. 0 = keep everything.",
        "upload_max_file_size_mb_label": "Maximum file size (MB)",
        "upload_max_file_size_mb_help": "Files larger than this limit will be rejected during upload.",
        "upload_max_rows_label": "Maximum rows/values from file",
        "upload_max_rows_help": "After reading a file, no more than this number of rows/values will be accepted.",
        "upload_file_too_large": "File {filename} exceeds the limit of {max_size_mb} MB.",
        "upload_file_too_many_rows": "File {filename} contains more than the allowed number of rows/values ({max_rows}).",
        "upload_file_unsupported_format": "Unsupported file format: {filename}. Use .txt or .csv.",
        "upload_file_parse_error": "Could not read file {filename}: {error}",
    }
)

for key, entry in TRANSLATIONS.items():
    entry.setdefault("en", EN_TRANSLATIONS.get(key, entry.get("ru", f"[{key}]")))


def get_lang() -> str:
    """Get current UI language from session state."""
    lang = st.session_state.get("ui_lang", "ru")
    return lang if lang in SUPPORTED_LANGUAGES else "ru"


def t(key: str, **kwargs) -> str:
    """
    Get translated string by key for the current UI language.

    Usage:
        t("app_title")
        t("total_keywords_stat", count=42, sources=3)
    """
    lang = get_lang()
    entry = TRANSLATIONS.get(key, {})
    text = entry.get(lang, entry.get("ru", f"[{key}]"))
    if kwargs:
        text = text.format(**kwargs)
    return text
