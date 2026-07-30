# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-80**  
Точная версия определяется текущей вершиной ветки `main`.

## Назначение

Этот файл определяет активный этап программы. Код и тесты в `main` остаются
окончательным источником истины. Стратегические границы определяются
`AGENTS.md`, `knowledge/00_PROJECT_MASTER_CONTEXT.md` и исходным master plan.

## Неизменяемые границы

- `trading_methods=false`;
- пользовательские Gateway Actions только `GET`;
- Render entrypoint `app:app`;
- нет создания, отправки, замены или отмены заявок;
- нет вывода или перевода денег и ценных бумаг;
- нет margin, short или derivatives execution;
- каждый пакет разрабатывается в отдельной ветке и Pull Request;
- release merge выполняется только после Regression Shield.

## Завершённые контуры

### P0 — безопасность и воспроизводимость

В `main` находятся read-only broker allowlist, Telegram retirement,
hash-locked dependencies, Ruff, formatting, mypy, coverage, SCA, SAST,
secret scan, маскирование счёта, стабильный `app:app` и GET-only release
contract.

### P1 — аналитический backend

Реализованы versioned read-only слои portfolio, cash, operations,
broker-report reconciliation, provenance, data quality, analytics,
concentration, stress, conservative risk, market evidence, safe news,
instrument assessments, Decision Engine, rebalancing, purchase/sell previews,
shadow/paper workflows, OOS stability и market-capacity gating.

### Final-review chain

PR-50…PR-79 построили:

- unified directional pre-trade review;
- risk and pro-forma binding;
- compact final response and release eligibility;
- private `GET /decision/final-review` with bounded internal registry;
- exact input identity, publication, orchestration and acceptance contracts;
- typed workflow producer, source acquisition and production source stores;
- fixed existing-calculator provider routing;
- one-shot trusted owner composition;
- approved fresh server-context owner acquisition.

Production OpenAPI остаётся ровно 14 authenticated GET Actions.

## PR-79 — approved owner acquisition

PR-79 принимает только typed immutable
`FinalDecisionReviewApprovedServerContextV1`. Из него выводятся invocation,
scenario, correlation, operation и masked account. До PR-78 должны быть
доступны и свежи Decision Engine, exact intent, capacity, explicit
`ProFormaRiskScenarioV1` и ровно один directional preview owner.

Missing, failed, stale, future-dated или mismatched evidence блокирует все
финансовые owner calls и возвращает внутренний `unavailable`, который
соответствует существующему HTTP `503`. Startup использует fixed missing
loaders и не выполняет context, owner, portfolio, network или broker calls.

## PR-80 — concrete typed owner installation

PR-80 добавляет
`FinalDecisionReviewApprovedOwnerInstallationV1` — внутренний adapter между
уже существующими PR-78 owner ports и PR-79 acquisition.

Контракт пакета:

- принимает один immutable approved server context;
- принимает один typed purchase или sell PR-78 owner-port bundle;
- проверяет operation до установки loaders;
- создаёт fixed loaders для Decision, intent, capacity, explicit pro-forma
  scenario и выбранного directional preview;
- не устанавливает и не вызывает противоположный preview direction;
- связывает каждый loader с exact immutable context;
- вызывает временный PR-79 acquisition ровно один раз;
- сохраняет все PR-79 freshness/account/source gates;
- сохраняет все PR-78 materialization, provider-routing и cleanup gates;
- не принимает raw calculator payloads, credentials, full account IDs,
  request body или user-selected provider names;
- не добавляет public route, Action или broker write method.

`FinalDecisionReviewProductionRuntimeV1` регистрирует installer на том же
PR-78 composition object. Startup installation и owner calls отсутствуют.

## Remaining production boundary

PR-80 закрывает concrete typed loader-installation gap, но не создаёт
несуществующий authenticated request lifecycle. До следующего reviewed
пакета production остаётся fail-closed:

- `app.py` не фабрикует approved server context;
- публичный Action не передаёт callables или raw financial values;
- owner-callable и final-review registries пусты после restart;
- missing context продолжает давать безопасный `503`;
- `trading_methods=false` и отсутствие broker writes сохраняются.

## Production acceptance

Восемь реальных PR-64 cases всё ещё `not_executed`:

- Render source commit;
- cache-busted health;
- auth-negative check;
- exact-route positive check;
- GPT Editor schema import;
- authenticated Preview;
- full Action-list inspection;
- rollback restore.

Зелёный CI не заменяет эти внешние проверки.

## Следующий доказанный пакет

Ближайший gap после PR-80:

- определить фактический authenticated server request lifecycle;
- после успешной Gateway authentication создать exact masked
  `FinalDecisionReviewApprovedServerContextV1`;
- выбрать только существующие typed Decision, intent, capacity, explicit
  post-change scenario и directional preview owner ports;
- вызвать PR-80 без raw Action calculator values, credentials, full account IDs
  или dynamic provider selection;
- сохранить safe `503` при любой недоступности или устаревании;
- не менять 14-GET OpenAPI surface.

Отдельно остаются production acceptance, live market/news/rating ingestion,
external versioned RAG, observability hardening, поиск исходного frontend и
safe SberInvestments HTML import без OCR.

## Запрет ложного завершения

Проект не считается полностью завершённым после одного PR или зелёного CI.
Финальное завершение возможно только после всех согласованных пакетов,
production acceptance и отдельной проверки полного Definition of Done.
