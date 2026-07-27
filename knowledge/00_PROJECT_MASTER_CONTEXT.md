# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-07-28  
Текущий system release: **v4.0.0 Telegram Companion — Read-Only Control Center**  
Gateway API component: **v3.9.1 Broker Report Async Integrity**

Этот документ — единая обезличенная проектная память. Его нужно читать первым при продолжении работы в новом чате, IDE, GitHub Copilot, Codex или другом проекте.

## 1. Назначение проекта

Omni-CIO Bot — инвестиционный AI-ассистент и аналитический кабинет. Цели:

- безопасно получать данные брокера;
- строить проверяемую аналитику портфеля;
- показывать происхождение каждой цифры;
- выявлять неполноту, расхождения и двойной учёт;
- помогать пользователю понимать портфель, риски и денежные потоки;
- предоставлять одинаковые read-only возможности через Custom GPT и Telegram;
- не совершать сделки и не изменять брокерский счёт.

Основной существующий сайт, который нужно сохранять:

`https://omni-cio-bot.ervinwilliams97920.chatgpt.site`

Не создавать дубликат сайта или новый frontend вместо существующего без прямого решения владельца.

## 2. Архитектура v4.0.0

```text
Custom GPT ──────┐
                 ├── Omni-CIO Gateway ── T-Invest API
Telegram Bot ────┘
```

### 2.1. Omni-CIO Gateway

Репозиторий: `Misha2304/omni-cio-gateway`.

Gateway отвечает за:

- health и connection;
- снимки портфеля;
- обогащение инструментов;
- рыночные данные;
- аналитику структуры портфеля;
- деньги и ликвидность;
- preview покупательной способности без создания заявки;
- историю и аналитику операций;
- официальный брокерский отчёт T-Invest;
- сверку отчёта и операций.

Gateway entrypoint: `app:app`.  
Gateway API version: `3.9.1`.  
Пользовательские Gateway Actions: только `GET`.

### 2.2. Telegram Companion

Telegram Companion — отдельный FastAPI web service в `telegram_bot/`.

Entrypoint: `telegram_bot.app:app`.  
Service version: `4.0.0`.  
Deployment contract: `render.telegram.yaml`.

Он:

- принимает Telegram webhook;
- проверяет secret header;
- разрешает доступ только указанным Telegram user IDs;
- принимает только личные чаты;
- вызывает Gateway только методом GET;
- показывает безопасно отформатированные ответы;
- не имеет OpenAI API в первом релизе;
- не синхронизирует историю ChatGPT и Telegram.

Команды v4.0.0:

- `/help`;
- `/health`;
- `/connection`;
- `/portfolio`;
- `/cash`;
- `/analytics`;
- `/operations [days]`;
- `/report`;
- `/report_status [task_id]`.

### 2.3. Custom GPT

Custom GPT остаётся отдельным интерфейсом внутри ChatGPT. Канонические инструкции и каталог Actions хранятся в `gpt/`. Секретный Bearer key и состояние публикации остаются в GPT Editor.

### 2.4. Веб-интерфейс Omni-CIO Bot

Исходный frontend-проект пока не найден и не зарегистрирован. До его определения нельзя создавать копию сайта. Состояние внешних активов ведётся в `docs/inventory/PROJECT_ASSETS.md`.

## 3. Источники данных

Разделять источники и не подменять один другим:

- T-Invest API — оперативные данные подключённого T-Invest счёта;
- официальный брокерский отчёт T-Invest — бухгалтерская сверка T-Invest;
- HTML-отчёт СберИнвестиций — планируемый отдельный импорт для веб-кабинета;
- MOEX ISS — отдельная текущая рыночная оценка;
- пользовательское подтверждение — контекст, но не замена технической проверки.

Telegram Companion не меняет значения и не выполняет собственные финансовые расчёты поверх Gateway. Он только безопасно доставляет ответ.

## 4. Главный принцип безопасности

Запрещены:

- создание заявки;
- отправка заявки;
- замена заявки;
- отмена заявки;
- стоп-заявки;
- скрытое подтверждение операции;
- автоматическая торговля;
- управление брокерским счётом из Telegram;
- хранение токенов и ключей в GitHub.

Обязательные инварианты:

- `trading_methods=false`;
- Gateway Actions только GET;
- Telegram вызывает Gateway только GET;
- единственный публичный POST Telegram service — входящий `/telegram/webhook`;
- Gateway entrypoint остаётся `app:app`;
- Telegram entrypoint остаётся `telegram_bot.app:app`;
- счёт маскируется;
- валюты не смешиваются без подтверждённого FX.

## 5. Секреты и внешняя конфигурация

GitHub не хранит:

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- `OMNI_GATEWAY_API_KEY`;
- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_WEBHOOK_SECRET`;
- реальные `TELEGRAM_ALLOWED_USER_IDS`;
- полный ID брокерского счёта;
- реальные отчёты, операции и позиции;
- Render secrets;
- секретный GPT Bearer key.

Gateway Render service хранит T-Invest token и Gateway key. Telegram Render service хранит Telegram token, webhook secret, user allowlist и копию Gateway key под именем `OMNI_GATEWAY_API_KEY`.

## 6. Gateway v3.9.1

Ключевые возможности:

- Regression Shield;
- portfolio market snapshot;
- portfolio analytics;
- cash and liquidity diagnostics;
- purchase capacity preview;
- arithmetic and commission integrity;
- operations analytics and cash-flow reconciliation;
- official broker report generation;
- broker report and operations reconciliation;
- обработка T-Invest `30058` как `pending`.

### Асинхронный цикл отчёта

1. Первый вызов выполняется без `task_id`.
2. При `wait_seconds=0` Gateway возвращает `pending` и настоящий `task_id`.
3. Следующий вызов передаёт тот же `task_id`.
4. Пока T-Invest возвращает `30058`, состояние остаётся `pending`.
5. После готовности загружаются все страницы и выполняется сверка.
6. `complete=true` допустим только после успешных проверок.
7. Период одного официального отчёта: `1..31` день.

## 7. Telegram Companion v4.0.0

### Webhook security

Telegram `setWebhook` настраивается с `secret_token`. Каждый update должен содержать `X-Telegram-Bot-Api-Secret-Token`. Сравнение выполняется constant-time.

### Access control

- только private chat;
- только `TELEGRAM_ALLOWED_USER_IDS`;
- неизвестный пользователь не вызывает Gateway;
- повторный `update_id` игнорируется;
- действует per-user rate limit.

### Automatic startup setup

При полной конфигурации и `TELEGRAM_AUTO_CONFIGURE=true` сервис вызывает:

1. `getMe`;
2. `setMyCommands`;
3. `setWebhook`.

Webhook URL строится из `TELEGRAM_PUBLIC_BASE_URL` или Render `RENDER_EXTERNAL_URL`. Ошибка bootstrap не раскрывает секреты и отражается через degraded health.

### Broker report in Telegram

`/report` запускает отчёт за 31 день и сохраняет `task_id` в памяти для удобства. `/report_status` использует сохранённый ID или принимает явный ID. После restart in-memory cache может быть потерян, поэтому task ID всегда показывается пользователю.

### Ограничения первого релиза

- нет свободного AI-диалога;
- нет синхронизации истории ChatGPT;
- нет постоянной базы Telegram sessions;
- нет GitHub/Render admin-команд;
- нет торговли;
- длинные ответы могут сокращаться.

## 8. Обязательный контракт ответов Gateway

Где применимо:

- `status`;
- `version`;
- `retrieved_at`;
- маскированный `account`;
- `pagination`;
- `reconciliation`;
- `quality`;
- `complete`;
- `component_errors`;
- `warnings`;
- `trading_methods=false`.

Частичный результат нельзя объявлять полным.

## 9. Денежные расчёты

- считать отдельно по каждой валюте;
- не складывать валюты без курса и времени FX;
- использовать безопасную десятичную арифметику;
- не складывать повторно top-level payment, nested commission, child operations и embedded trades;
- хранить комиссии раздельно, если источник их различает;
- для облигаций учитывать номинал, процентную цену и НКД;
- не путать количество инструментов и лоты.

## 10. Планы HTML-импорта СберИнвестиций

Для веб-кабинета запланирован безопасный импорт официального HTML-отчёта:

- без фото и OCR;
- без исполнения HTML/JS/CSS;
- с MIME, encoding, size и structure validation;
- с SHA-256 и защитой от дублей;
- с автоматическим определением периода;
- с preview и подтверждением;
- с маскированием счёта;
- без логирования чувствительных данных;
- по возможности в браузере;
- с полным удалением данных.

Статусы:

- `Формат брокера распознан`;
- `Формат распознан частично`;
- `Файл не поддерживается`;
- `Подлинность подтверждена электронной подписью` — только после реальной криптографической проверки.

HTML-отчёт является источником истины для состава портфеля на конец периода, денежных остатков, сделок, комиссий, купонов и дивидендов. MOEX используется только для отдельной текущей оценки.

## 11. Формулы и ограничения аналитики

- стоимость позиции = количество × цена;
- стоимость облигации = количество × номинал × цена% / 100;
- полная стоимость облигации = рыночная стоимость + НКД;
- чистый внешний поток = пополнения − выводы;
- результат периода = стоимость на конец − стоимость на начало − чистый внешний поток.

Не рассчитывать точную среднюю цену, реализованную/нереализованную прибыль или точную доходность, если данных недостаточно. Показывать `Недостаточно данных в выбранном отчёте`.

## 12. Требования к интерфейсу

Навигация сайта:

- Обзор;
- Отчёты;
- Портфель;
- Операции;
- Аналитика;
- Ребалансировка;
- AI-стратег и публикации;
- Источники и настройки.

Светлая тема по умолчанию, рабочая тёмная тема, ширина от 360 px, skeleton loaders, empty states, ошибки и подтверждения.

## 13. Приоритеты

### P0

- стабильность Gateway v3.9.1;
- безопасный Telegram Companion v4.0.0;
- безопасный HTML-import без OCR;
- парсинг обязательных разделов;
- preview, подтверждение и сверка итогов.

### P1

- постоянное хранение Telegram report task state;
- Telegram-кнопки и компактные summary-форматы;
- архив отчётов и сравнение периодов;
- редизайн, графики, MOEX, mobile и dark theme.

### P2

- свободный AI-диалог Telegram через OpenAI API;
- расширенный AI-анализ;
- сценарии ребалансировки;
- новости и Telegram-публикации;
- расширенная история доходности.

## 14. Definition of Done

Изменение завершено, когда:

- код в отдельной ветке и PR;
- тесты не используют реальный API;
- Regression Shield проходит;
- read-only инвариант сохранён;
- секреты не попали в diff;
- документация и knowledge обновлены;
- после merge проверен production health каждого затронутого сервиса;
- новый чат может понять изменение только по GitHub.

## 15. Как продолжать в новом чате

Прочитать:

- `AGENTS.md`;
- `README.md`;
- `docs/README.md`;
- этот файл;
- `gpt/INSTRUCTIONS.md`;
- `gpt/ACTIONS_CATALOG.md`;
- профильный `knowledge/` файл.

Для Telegram дополнительно:

- `knowledge/12_TELEGRAM_COMPANION.txt`;
- `docs/operations/TELEGRAM_COMPANION_RUNBOOK.md`.

Код в `main` имеет приоритет над старой перепиской.
