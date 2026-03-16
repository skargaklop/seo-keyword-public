# Настройка Google Ads API

Для работы планировщика ключевых слов требуются данные из Google Ads (объем поиска, конкуренция, цена клика). Чтобы получить эти данные программно, нужно настроить доступ к API.

Вот подробное описание каждого параметра и инструкция, где их взять.

## Что это за параметры?

1. **GOOGLE_ADS_DEVELOPER_TOKEN**: "Пропуск" к API. Выдается в управляющем аккаунте (MCC). Без него запросы не пройдут.
2. **GOOGLE_ADS_CLIENT_ID** и **CLIENT_SECRET**: Логин и пароль вашего *приложения* (скрипта) в глазах Google. Создаются в Google Cloud Console.
3. **GOOGLE_ADS_REFRESH_TOKEN**: Специальный токен, который позволяет скрипту работать от вашего имени *постоянно*, не требуя входить в браузер и нажимать "Разрешить" при каждом запуске.
4. **GOOGLE_ADS_CUSTOMER_ID**: ID рекламного аккаунта (10 цифр), *для которого* мы запрашиваем данные. Обычно это ваш рабочий аккаунт Google Ads.
5. **GOOGLE_ADS_LOGIN_CUSTOMER_ID**: ID управляющего аккаунта (MCC), *через который* вы логинитесь, если используете MCC. Если у вас прямой доступ, это поле иногда можно пропустить, но для стабильности лучше указать MCC ID.

Важно: если OAuth-приложение в Google Cloud находится в режиме `Testing`, `refresh token` живёт только **7 дней**. Проще перевести приложение в `Published`: тогда `refresh token` обычно достаточно сгенерировать один раз и использовать дальше, пока доступ не будет отозван вручную или не изменятся учётные данные.

---

## Пошаговая инструкция

### Шаг 1: Создание аккаунта менеджера (MCC) и получение Developer Token

*Если у вас еще нет управляющего аккаунта (Manager Account), создайте его.*

1. Перейдите на [Google Ads Manager Accounts](https://ads.google.com/home/tools/manager-accounts/) и создайте аккаунт.
2. Войдите в созданный аккаунт.
3. В меню перейдите в **Инструменты и настройки (Tools & Settings)** -> **Настройка (Setup)** -> **Центр API (API Center)**.
4. Вы увидите форму заявки на доступ к API. Заполните её (для базового доступа достаточно описать, что это внутренний инструмент для отчетности).
5. После создания вы увидите **Developer token**. Скопируйте его.
    * *Примечание: Даже с тестовым доступом (Test Access) вы можете выполнять запросы к тестовым аккаунтам, но для реальных данных нужен Basic Access. Обычно Basic Access выдают быстро после заполнения анкеты.*

### Шаг 2: Настройка проекта в Google Cloud Console

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/).
2. Создайте новый проект (New Project), назовите его, например, "SeoKeywordPlanner".
3. **Включите API**:
    * Меню -> **APIs & Services** -> **Library**.
    * Поиск: "Google Ads API".
    * Нажмите **Enable**.
4. **Настройте экран согласия (OAuth Consent Screen)**:
    * Меню -> **APIs & Services** -> **OAuth consent screen**.
    * Выберите **External** (Внешний), если у вас нет организации G-Suite, или **Internal**.
    * Заполните обязательные поля (App name, User support email, Developer contact information). Остальное можно пропустить.
    * Нажмите Save and Continue.
    * На этапе "Test users" добавьте свой email (тот, под которым администрируете Google Ads).
5. **Создайте Credentials (Client ID & Secret)**:
    * Меню -> **APIs & Services** -> **Credentials**.
    * Нажмите **Create Credentials** -> **OAuth client ID**.
    * Application type: **Desktop app**.
    * Name: "SeoPlannerClient".
    * Нажмите **Create**.
    * В появившемся окне скопируйте **Your Client ID** и **Your Client Secret**.

### Шаг 3: Получение Refresh Token

В проекте есть готовый скрипт для генерации токена.

**Способ 1 — Батник (рекомендуется):**

1. Убедитесь, что в `.env` заполнены `GOOGLE_ADS_CLIENT_ID` и `GOOGLE_ADS_CLIENT_SECRET` (из Шага 2).
2. Дважды кликните по файлу `generate_refresh_token.bat`.
3. Откроется браузер — войдите в Google аккаунт с доступом к Google Ads.
4. Скрипт покажет refresh token и предложит автоматически записать его в `.env`.

Если приложение остаётся в режиме `Testing`, этот token придётся перевыпускать примерно раз в 7 дней. Если перевести OAuth Consent Screen в `Published`, обычно достаточно получить token один раз.

**Способ 2 — Через терминал:**

```bash
python generate_refresh_token.py
```

### Шаг 4: Заполнение .env

Теперь у вас есть всё необходимое. Откройте файл `.env` и заполните:

* **GOOGLE_ADS_DEVELOPER_TOKEN**: из Шага 1.
* **GOOGLE_ADS_CLIENT_ID**: из Шага 2.
* **GOOGLE_ADS_CLIENT_SECRET**: из Шага 2.
* **GOOGLE_ADS_REFRESH_TOKEN**: из Шага 3.
* **GOOGLE_ADS_CUSTOMER_ID**: Зайдите в Google Ads, в правом верхнем углу (или левом) найдите 10-значный номер вашего целевого аккаунта (например, 123-456-7890). Впишите его без дефисов: `1234567890`.
* **GOOGLE_ADS_LOGIN_CUSTOMER_ID**: ID вашего MCC аккаунта (тоже 10 цифр).

### Настройка без Google Ads (только LLM)

Если вам НЕ нужны данные о частотности и конкуренции, а только генерация ключевых слов через AI, эти поля можно оставить пустыми. Приложение выдаст предупреждение, но продолжит работать, просто колонки с метриками Google будут пустыми.

### Устранение частых проблем

#### 1. Ошибка `invalid_grant: Bad Request`

Означает, что refresh token стал невалидным. Причины:

* **OAuth Consent Screen в режиме "Testing"** — токены истекают через **7 дней**. Переведите в **Published** в [Google Cloud Console](https://console.cloud.google.com/apis/credentials/consent).
* После перевода приложения в **Published** refresh token обычно достаточно сгенерировать один раз.
* **Пароль Google аккаунта был изменён** — токен автоматически отзывается.
* **Доступ приложения был отозван** — проверьте [myaccount.google.com/permissions](https://myaccount.google.com/permissions).
* **Токен получен с другим Client ID/Secret** — пересоздайте токен.

**Решение:** перегенерируйте refresh token с помощью `generate_refresh_token.bat` (см. Шаг 3).

#### 2. Не могу найти "Google Ads API" в библиотеке (No results found)

Если поиск в Google Cloud Console выдает "No results found", проверьте активные фильтры.

* Убедитесь, что слева под заголовком "Category" **НЕ выбран** фильтр **"Google Workspace"** (серый овал).
* Если он есть, нажмите крестик (x) на нем. Google Ads API не входит в пакет Workspace.

#### 3. Ошибка "ModuleNotFoundError: No module named 'google_auth_oauthlib'"

Установите зависимость:

```bash
pip install google-auth-oauthlib
```

Либо запустите `generate_refresh_token.bat` — он установит её автоматически.

#### 4. Ошибка 403: "Access blocked: app has not completed the Google verification process"

Ваше приложение в режиме "Testing", и ваш email не добавлен в список тестировщиков.

* Зайдите в **Google Cloud Console** -> **APIs & Services** -> **OAuth consent screen**.
* Прокрутите вниз до раздела **"Test users"**.
* Нажмите **+ ADD USERS**.
* Введите **ваш email** (тот же, под которым вы входите).
* Нажмите **Save**.
* Подождите минуту и запустите скрипт снова.
