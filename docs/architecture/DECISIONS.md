# Архитектурные решения Omni-CIO

## ADR-001 — Gateway остаётся read-only

**Статус:** принято.

User-facing Gateway не содержит broker write methods. Контроль: GET-only routes, `trading_methods=false`, code guards and Regression Shield.

## ADR-002 — Production entrypoint остаётся `app:app`

**Статус:** принято.

Render и GPT Actions зависят от стабильного FastAPI app. `app_v371.py`, `app_v360.py` и `main.py` остаются, пока `app.py` импортирует их. Консолидация wrappers требует отдельной compatibility migration.

## ADR-003 — Единственный пользовательский интерфейс — Custom GPT

**Статус:** принято.

Не поддерживать параллельный frontend/publishing transport как отдельный продукт без нового решения владельца. Текущий UI — `Omni-CIO API | Управляющий и аналитик v8.4` внутри ChatGPT.

## ADR-004 — GitHub является источником кода и эталонной конфигурации

**Статус:** принято.

`main` + tests/contracts являются источником runtime truth. `gpt/` содержит воспроизводимый эталон GPT configuration.

GitHub не является live storage фактически применённых GPT Editor settings: Instructions/Knowledge/Bearer secret после изменений применяются вручную и проверяются Preview.

## ADR-005 — Один production Instructions file

**Статус:** принято.

Production GPT Editor использует только:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`

Параллельные compact/canonical Instructions copies не поддерживаются, чтобы не создавать конфликтующие источники истины.

## ADR-006 — Один setup entrypoint

**Статус:** принято.

Настройка, восстановление и update flow начинаются с `gpt/SETUP_INDEX.md`. Отдельные competing setup guides не создаются, если информацию можно добавить туда или в disaster-recovery runbook.

## ADR-007 — Secrets остаются вне GitHub

**Статус:** принято.

`TINVEST_TOKEN` хранится только в Render Environment. `GATEWAY_API_KEY` хранится в Render и как GPT Action Bearer secret. GitHub не содержит значения secrets, full account IDs или private broker payloads.

## ADR-008 — Production Gateway endpoint единственный

**Статус:** принято.

Canonical service:

`https://omni-cio-gateway.onrender.com`

GPT Actions не должны ссылаться на старые альтернативные Render service names.

## ADR-009 — Portfolio management is tool-first

**Статус:** принято.

До содержательного portfolio advice GPT выполняет:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics`

Exact-action user request имеет приоритет и не запускает другие Actions.

## ADR-010 — Fresh market gate before exact sizing

**Статус:** принято.

Если рынок не готов, нет fresh best ask или доступен stale last price, exact personalized lot sizing блокируется. Technical affordability не превращается автоматически в recommendation.

## ADR-011 — Moscow is user-visible timezone

**Статус:** принято.

User-visible dates/times показываются по `Europe/Moscow`/MSK. Market open/closed определяется broker/Gateway trading status, а не только часами.

## ADR-012 — CI/dependency supply chain fail-closed

**Статус:** принято.

- human-edited dependencies live in `.in` constraints;
- lock files pin exact transitive versions + SHA-256 hashes;
- external GitHub Actions pin full commit SHA;
- Regression Shield blocks merge on contract/quality/security failures;
- generated locks are not hand-edited.

## ADR-013 — Master plan сохраняется как исходная спецификация этого проекта

**Статус:** принято.

`docs/master-plan/` не является мусором: он описывает развитие Omni-CIO. Однако будущие цели из master plan не считаются реализованными без current code, tests and acceptance.

## ADR-014 — Repository cleanup must preserve real dependencies

**Статус:** принято.

Перед удалением файла проверяются imports, tests, configuration and runtime references. Исторически названный файл не считается мусором автоматически. Cleanup changes проходят через branch/PR/Regression Shield.
