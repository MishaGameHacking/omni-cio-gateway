# Архитектурные решения

## ADR-001 — Шлюз остаётся read-only

**Статус:** принято.

Публичный gateway не содержит методов создания, отправки, замены или отмены заявок. Контроль выполняют GET-only routes, `trading_methods=false` и Regression Shield.

## ADR-002 — Gateway entrypoint остаётся `app:app`

**Статус:** принято.

Render и GPT Actions зависят от стабильного FastAPI app. Исторические wrappers сохраняются до отдельной compatibility migration.

## ADR-003 — GitHub является источником проектной памяти

**Статус:** принято.

Новые чаты используют `AGENTS.md`, `knowledge/`, `gpt/`, `docs/` и код `main`, а не старую переписку.

## ADR-004 — Секреты и реальные данные остаются вне GitHub

**Статус:** принято.

GitHub не хранит T-Invest token, Gateway key, Telegram token, webhook secret, реальные Telegram user IDs, полный номер счёта, реальные отчёты и финансовые данные.

## ADR-005 — Frontend нельзя дублировать до определения источника

**Статус:** принято.

Существующий сайт Omni-CIO сохраняется. Новый frontend не создаётся до регистрации настоящего исходного проекта.

## ADR-006 — Одноразовые workflow не живут в main

**Статус:** принято.

Release-patcher workflow допускаются только во временной ветке. В `main` остаётся постоянный Regression Shield.

## ADR-007 — Telegram является отдельным service, а не частью Gateway

**Статус:** принято.

Telegram webhook имеет иной сетевой и эксплуатационный профиль, чем GPT Actions. Поэтому Telegram Companion запускается через `telegram_bot.app:app` и `render.telegram.yaml`. Сбой или неправильная конфигурация Telegram не должны ломать `app:app`.

## ADR-008 — Telegram v4.0.0 использует команды без OpenAI API

**Статус:** принято.

Первый релиз использует фиксированные read-only команды. Это снижает стоимость, уменьшает неоднозначность маршрутизации и позволяет проверить безопасность. Свободный AI-диалог остаётся отдельным будущим релизом.

## ADR-009 — Webhook настраивается автоматически при старте

**Статус:** принято.

Telegram service использует Render `RENDER_EXTERNAL_URL`, вызывает `getMe`, `setMyCommands` и `setWebhook`, а webhook защищается secret token. Ошибка auto setup не раскрывает секреты и отражается degraded health.

## ADR-010 — Telegram не дублирует Gateway business logic

**Статус:** принято.

Telegram service вызывает существующие Gateway GET endpoints и не обращается к T-Invest напрямую. Он не пересчитывает финансовые показатели, а только маскирует, ограничивает длину и доставляет ответ.
