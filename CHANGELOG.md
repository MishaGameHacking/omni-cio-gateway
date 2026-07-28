# Changelog

Все заметные изменения Omni-CIO фиксируются здесь. Источник истины по коду — ветка `main`; подробности релизов находятся в соответствующих Pull Request.

## [Unreleased]

### Added
- Профиль Custom GPT `Modern Financial Sage — 2026`.
- Современный разговорный русский язык без банковского канцелярита.
- Обязательный перевод сложных финансовых терминов на человеческий язык.
- Понятная шкала риска: зелёный, жёлтый, оранжевый, красный.
- Разделение фактов, аналитических выводов и сценариев.
- Правила умеренной нецензурной лексики без оскорбления пользователя и без подмены анализа эмоциями.
- Отдельный стандарт Telegram-постов: короткие мобильные абзацы, главный вывод в начале, дата и источники.
- Профиль знаний `knowledge/13_COMMUNICATION_STYLE_2026.txt`.
- Компактный рабочий файл `gpt/INSTRUCTIONS_COMPACT.md`, рассчитанный на лимит 8000 символов GPT Editor.

### Changed
- Канонический `gpt/INSTRUCTIONS.md` теперь ориентирован на простые объяснения состояния портфеля, компаний, рисков и денежных потоков.
- GPT Editor использует компактные Instructions, а расширенный документ остаётся проектным источником истины.
- Рекомендуемые conversation starters обновлены для понятного анализа и подготовки Telegram-публикаций.
- Web Search рекомендуется включать для актуального анализа компаний, отчётности, дивидендов, новостей и рыночного контекста.

### Safety
- Стиль не меняет Gateway, Actions, Render services или Telegram command runtime.
- `trading_methods=false` и GET-only контракт сохранены.
- Сильные выводы должны подтверждаться цифрами, датой и источниками.
- Свободный AI-диалог в Telegram через OpenAI API остаётся отдельным будущим этапом.

## [4.0.1] — 2026-07-28

### Added
- Команда `/status` для проверки Telegram Companion, Omni-CIO Gateway и подключения к T-Invest.
- Краткие русские сводки для всех Telegram-команд вместо больших JSON-блоков.
- Безопасное разбиение длинных сообщений с маркировкой частей.
- Необязательный Telegram typing indicator.
- Безопасный reliability profile в `/health` Telegram service.

### Changed
- Временные ошибки Gateway автоматически повторяются по настраиваемой политике.
- Перед первым повтором пользователь получает сообщение о пробуждении основного сервера.
- Ошибки Gateway показываются понятным сообщением без утечки технических секретов.

### Safety
- Повторяются только GET-запросы и только для временных сетевых/HTTP ошибок.
- HTTP 401/403 и другие постоянные ошибки не повторяются.
- `trading_methods=false` сохранён.
- Gateway API v3.9.1 и entrypoint `app:app` не изменены.

## [4.0.0] — 2026-07-28

### Added
- Отдельный FastAPI service `telegram_bot.app:app`.
- Команды `/health`, `/connection`, `/portfolio`, `/cash`, `/analytics`, `/operations`, `/report`, `/report_status`.
- Автоматическая установка Telegram webhook и списка команд при старте.
- Изолированный Render Blueprint `render.telegram.yaml`.
- Ограничение доступа по `TELEGRAM_ALLOWED_USER_IDS` и только личным чатам.
- Webhook secret validation, update deduplication, rate limit и повторное маскирование account ID.
- In-memory удобство для повторного использования `task_id` официального брокерского отчёта.
- Полный runbook и профильный knowledge-файл Telegram Companion.

### Safety
- Telegram вызывает Omni-CIO Gateway только методом GET.
- Торговые команды отсутствуют.
- `trading_methods=false`.
- Gateway component и его entrypoint `app:app` не изменены.
- Telegram и gateway deploy разделены, поэтому сбой Telegram не ломает основной API.

## [3.9.1] — 2026-07-27

### Added
- Асинхронная целостность официального брокерского отчёта.
- Возврат настоящего `task_id` при первом вызове без преждевременного опроса.
- Обработка T-Invest `30058` как штатного состояния `pending`.
- Ограничение периода официального отчёта до `1..31` дня.

### Safety
- `trading_methods=false`.
- Стабильный Render entrypoint `app:app`.

## [3.9.0] — 2026-07-27

- Official Broker Report & Operations Reconciliation.
- Пагинация отчёта, сверка сделок, денежных потоков и комиссий по каждой валюте.

## [3.8.0] — 2026-07-27

- Operations Analytics & Cash Flow Reconciliation.
- Защита от дублей, parent/child и повторного учёта комиссий.

## [3.7.1] — 2026-07-27

- Purchase Capacity Integrity.
- Арифметическая проверка суммы, комиссии и остатка.

## [3.7.0] — 2026-07-27

- Purchase Capacity Preview без создания заявки.

## [3.6.0] — 2026-07-27

- Cash & Liquidity Diagnostics.

## [3.5.0] — 2026-07-27

- Portfolio Analytics Core.

## [3.4.0] — 2026-07-27

- Portfolio Market Snapshot.

## [3.3.3] — 2026-07-27

- Regression Shield, CI и проверка read-only контракта.
