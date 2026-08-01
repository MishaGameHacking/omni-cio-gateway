# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-01  
Фактическая слитая функциональная вершина `main`: **PR-104**  
Последний merge commit: `34708f82d20e054bdd420ac1e9993c6d117e12d7`  
Текущий режим: **read-only audit hold**

## Назначение документа

Это оперативная карта программы. Код в `main` остаётся окончательным
источником истины. Стратегические требования и Definition of Done определяются
`AGENTS.md`, `knowledge/00_PROJECT_MASTER_CONTEXT.md` и canonical master plan.

Состояние открытых Pull Requests, GitHub Actions, Render, GPT Editor и внешних
сервисов нельзя считать зафиксированным только этим файлом: перед каждым новым
пакетом их нужно проверять повторно.

## Неизменяемые границы

- `trading_methods=false`;
- ровно 14 пользовательских GET Actions: 13 authenticated и public `/health`;
- Render entrypoint `app:app`;
- отсутствие создания, отправки, замены и отмены заявок;
- отсутствие переводов и вывода денег;
- отсутствие margin, short и derivatives execution;
- отдельная ветка и Pull Request для каждого пакета;
- squash merge только после полного Regression Shield на exact head;
- green CI не заменяет внешнюю Render/Gateway/GPT acceptance evidence.

## Завершённая release chain в `main`

- **PR-50…PR-83:** private read-only final-review production chain, acceptance
  collector, workflow/owner acquisition and authenticated evidence;
- **PR-84…PR-88:** official CBR source, cache, safe observability, bounded global
  alert policy and deterministic terminal evidence lifecycle;
- **PR-89…PR-93:** official MOEX TQBR source, exact cache, privacy-safe
  telemetry, global operational alert policy and terminal evidence;
- **PR-94…PR-98:** fixed official ACRA issuer-level national-RU source, bounded
  cache, privacy-safe telemetry, global alert policy and terminal evidence;
- **PR-99…PR-103:** fixed Expert RA source, cache, observability, global alert
  policy and deterministic terminal evidence lifecycle;
- **PR-104:** fixed official NCR issuer-level national-Russia rating-action
  source with strict release/date identity and isolated read-only transport.

## Текущая слитая функциональная вершина — PR-104

GitHub PR #136 `PR-104: Add fixed NCR issuer rating action source v1` был
squash-merged в `main` commit:

`34708f82d20e054bdd420ac1e9993c6d117e12d7`.

Final Regression Shield run #806 прошёл на exact head
`1ac0db542721c940ed0e3c5bf30ac08dfe8e2dae`:

- 1235 tests passed;
- 19 non-blocking warnings;
- total coverage 61.97%, threshold >=60%;
- mypy: 188 source files, no issues;
- compile, Ruff, formatting, lock and repository-policy checks passed;
- stable `app:app`, exactly 14 GET Actions, forbidden surface count 0 and
  `trading_methods=false` passed;
- pip-audit, Bandit and detect-secrets passed;
- diagnostics artifact was present.

Это подтверждает зелёное состояние `main` на PR-104, но не доказывает внешнюю
production acceptance.

## Audit hold перед продолжением roadmap

По команде владельца функциональная разработка временно приостановлена до
закрытия следующих проверок.

### 1. Draft infrastructure PR #130

PR #130 `CI: make self-hosted Windows runner service diagnosable` остаётся
draft. Старый красный check относился к Regression Shield run #787: security
job прошёл, а quality job упал на одном ACRA deterministic-clock test, который
позже был исправлен отдельным PR #131 и уже находится в `main`.

Повторный аудит самого PR #130 нашёл дополнительные реальные недостатки:

- `.service` marker читался без отдельного byte bound;
- его содержимое могло попасть в PowerShell `Get-Service -Name`, который
  поддерживает wildcard patterns;
- отсутствовали отдельные typed states и tests для missing/invalid/mismatched
  service marker.

PR #130 был усилен fail-closed: bounded `.service`, exact service identity,
no wildcard-first discovery, redacted output и Windows-native regression tests.
Merge запрещён до нового полного Regression Shield на текущем exact head.

### 2. Документационная согласованность

До этого аудита оперативные документы расходились с фактическим `main`:

- этот файл всё ещё называл PR-104 активным незавершённым пакетом после его
  успешного merge;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md` содержал устаревший локальный текст
  о вершине PR-81;
- issue #27 описывал более раннюю вершину и блокер, который уже не соответствует
  состоянию репозитория;
- README подробно перечислял chain только до PR-91, хотя фактическая вершина
  была PR-104.

Каноническое правило: номера active package нельзя считать истиной без проверки
`main`, открытых PR и exact-head Actions. Этот файл обновлён до PR-104; остальные
stale references должны быть устранены в том же audit package или явно
помечены как исторические.

### 3. Dependency queue

В `main` сохраняются отдельно зафиксированные и hash-locked версии:

- `fastapi==0.140.9`;
- `httpx==0.28.1`;
- `t-tech-investments==1.49.2`;
- `uvicorn==0.51.0`;
- `pytest==8.4.2`;
- `pytest-cov==7.1.0`;
- `ruff==0.16.0`;
- `mypy==2.3.0`.

Открытые Dependabot PRs нельзя объединять только по зелёному значку в списке.
Каждый должен получить свежий merge-ref против текущего `main`, review release
notes, regenerated hash locks и полный Regression Shield. Особенно это касается
major переходов pytest и GitHub Actions.

### 4. Warning debt

Последний зелёный Regression Shield всё ещё сообщает 19 warnings. Из ранее
зафиксированных классов требуется отдельная совместимостная проверка:

- Starlette/FastAPI TestClient transition away from deprecated `httpx` path;
- deprecated T-Invest request identity fields based on `figi`;
- Pydantic serializer warnings в final-review tests;
- GitHub Action Node runtime deprecation warnings до завершения Action upgrades.

Warnings не равны текущему падению CI, но не должны бессрочно считаться
безопасными без классификации и regression tests.

## Production acceptance state

Read-only production acceptance по-прежнему требует внешних evidence cases:

1. Render source commit verification;
2. cache-busted `/health`;
3. auth-negative check;
4. exact-route positive check;
5. GPT Editor schema import;
6. authenticated Preview;
7. complete Action-list inspection;
8. rollback restore.

CI не может отметить эти проверки выполненными.

## Что остаётся до полного релиза

### Backend and operations

- завершить и слить PR #130 только после нового exact-head green CI;
- устранить stale project-memory and roadmap references;
- классифицировать и закрыть либо зарегистрировать все warning classes;
- проверить Dependabot packages по одному, без blind auto-merge;
- добавить другие credit-rating agencies только как independent fixed sources;
- определить exact production market-data callers and lazy bindings;
- построить production-grade news and corporate-event ingestion;
- выполнить реальную Render/Gateway/GPT acceptance;
- добавить versioned external RAG with freshness/citation controls;
- расширить operational monitoring and incident runbooks.

### Web cabinet

- найти и зарегистрировать исходный frontend; не создавать дубликат;
- реализовать безопасный официальный SberInvestments HTML import без OCR;
- архивировать отчёты, сравнивать периоды и показывать reconciled differences;
- завершить mobile layout и light/dark themes;
- проверить production controls.

### Trading stages

Shadow, paper, preview и final-review компоненты не разрешают live trading.
Любое будущее исполнение требует отдельной owner-approved admission program с
confirm-before-trade, idempotency, confirmation TTL, kill switch, partial-fill
и timeout reconciliation. Autonomous execution остаётся disabled.

## Следующий безопасный функциональный пакет

После закрытия audit hold следующий логичный кандидат — отдельный
**NCR rating-action cache v1** над PR-104 с explicit
fresh/stale/unavailable semantics, single-flight refresh, bounded retention и
no-silent-stale policy.

Он не должен начинаться или сливаться одновременно с незавершённым audit/CI
package. Другой следующий пакет допустим только после повторной сверки master
plan, issue #27, текущего `main` и внешних приоритетов владельца.

## Запрет ложного завершения

Проект не считается полностью завершённым после одного зелёного PR. Полный
релиз требует внешней production acceptance evidence, exact owner/frontend
binding, remaining market/news/RAG work and completion of planned safety stages.
До этого система остаётся read-only с `trading_methods=false`.
