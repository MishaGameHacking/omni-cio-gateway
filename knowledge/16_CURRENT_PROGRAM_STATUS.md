# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-31  
Фактическая вершина программы после merge этого пакета: **PR-98**  
Точная версия определяется текущей вершиной ветки `main`.

## Назначение документа

Это оперативная карта программы. Код в `main` остаётся окончательным источником
истины; стратегические правила и Definition of Done определяются `AGENTS.md`,
`knowledge/00_PROJECT_MASTER_CONTEXT.md` и исходным master plan.

## Неизменяемые границы

- `trading_methods=false`;
- ровно 14 пользовательских GET Actions: 13 authenticated и public `/health`;
- Render entrypoint `app:app`;
- отсутствие создания, отправки, замены и отмены заявок;
- отсутствие переводов и вывода денег;
- отсутствие margin, short и derivatives execution;
- отдельная ветка и Pull Request для каждого пакета;
- squash merge только после полного Regression Shield.

## Завершённая release chain

- **PR-50…PR-63:** compact final review, exact identity, private GET route,
  trusted publication и end-to-end fail-closed orchestration;
- **PR-64:** production-acceptance evidence contract и offline collector;
- **PR-65…PR-83:** typed workflow bridge, producer, source acquisition,
  calculator handoff, approved owner installation and authenticated evidence;
- **PR-84…PR-88:** official CBR source, cache, safe observability, bounded alert
  policy and deterministic fired/recovered evidence lifecycle;
- **PR-89…PR-93:** official MOEX TQBR source, exact cache, safe observability,
  global operational alert policy and deterministic fired/recovered evidence;
- **PR-94…PR-98:** fixed official ACRA issuer-level national-RU rating-action
  source, bounded cache, privacy-safe telemetry, strict global alert policy and
  deterministic fired/recovered evidence lifecycle.

## PR-81…PR-83 authenticated owner lifecycle

Existing Bearer auth and exact compact-response validation create a trusted
server context. A fresh typed Decision/intent/capacity/pro-forma snapshot is
selected by exact scenario, correlation, operation and masked account, rebound
to existing owner ports and invoked at most once. Bounded redacted evidence is
retained. Startup performs no owner, calculator, portfolio, network or broker
call. Public response and OpenAPI remain unchanged.

## CBR lifecycle — PR-84…PR-88

The fixed Bank of Russia source provides typed Decimal observations, protected
XML parsing, bounded HTTPS streaming and redacted failures. The cache exposes
explicit fresh/stale/unavailable state, single-flight refresh and no-silent-stale
behavior. Observability contains operational metadata only. Alerting uses
bounded thresholds, cooldown and recovery; the lifecycle retains only bounded
fired/recovered evidence without startup fetch.

## MOEX lifecycle — PR-89…PR-93

- fixed official public TQBR endpoint and strict SECID identity;
- allowlisted JSON tables, Decimal prices and Moscow time normalization;
- public feed marked potentially delayed and informational-only;
- exact `(TQBR, SECID)` cache with separate retrieval TTL and market age;
- stale exposure only after refresh failure and explicit trusted policy;
- telemetry without price, SECID, account or raw JSON;
- global operational alert policy with forged-event rejection;
- bounded fired/recovered evidence and no external notification transport.

Broker `getMarketSnapshot` remains primary for execution-style calculations.
MOEX and broker values are never silently averaged.

## ACRA source/cache/operations — PR-94…PR-98

### Fixed source and cache

- fixed official ACRA issuer-level press-release source;
- national-Russia assigned, affirmed, upgraded, downgraded and withdrawn actions;
- unsupported issue-level, international-scale and multi-target scope skipped;
- malformed supported issuer records fail closed;
- bounded HTML transport; raw HTML/body/exception text not retained;
- one fixed-source cache with fresh TTL 900 seconds and stale retention 86400;
- stale records hidden unless refresh failed and trusted `allow_stale=true`;
- publication date remains separate from retrieval freshness;
- no source/cache call at import or startup.

### PR-96 privacy-safe telemetry

Typed source/cache results map to immutable operational events containing only
status, safe counts, latency, freshness, cache/refresh/stale/display flags,
provider, fixed operation and safe error codes. Events exclude issuer, rating,
outlook, action, release URL, publication date, raw HTML, account and broker
payload.

### PR-97 global alert policy

- immutable scope `global_acra_rating_actions_feed`;
- source unavailable, cache unavailable, stale exposure and failed-refresh
  conditions only;
- exact canonical event/metric profile with duplicate metrics rejected;
- bounded thresholds, saturating counters, cooldown, recovery and retention;
- forged same-name events fail closed before state mutation;
- no issuer/rating/financial thresholds or external notification delivery.

### PR-98 evidence lifecycle

PR-98 composes already-produced typed results as:

```text
PR-94/95 result → PR-96 event → PR-97 evaluation → PR-98 evidence
```

The process-local lifecycle:

- stores only `fired` and `recovered` evidence;
- rejects pending, ignored and cooldown-suppressed evidence;
- retains opaque identifiers, UTC time, global operational kind, severity,
  counters, threshold and safe error code only;
- excludes issuer, rating, outlook, action, release URL, publication date,
  financial values, account, raw HTML and exception text;
- uses bounded retention/capacity, oldest-first eviction and explicit clear;
- holds one `RLock` across evaluation, evidence mutation and safe sink handoff;
- calls the event sink before evidence sinks for one observation;
- reduces sink exceptions to `sink_failure_count`;
- performs no source/cache call, emission or registration at startup.

## Compatibility and safety after PR-98

- `app:app` unchanged;
- 14 GET Actions unchanged: 13 authenticated and public health;
- no route, request body, public response field or frontend component;
- no dependency, database, secret or Render migration;
- no network call or lifecycle execution at import/startup;
- no T-Invest call or broker write method;
- `trading_methods=false`.

## Frontend/owner discovery state

Repository search did not find a registered existing frontend/dashboard owner or
production caller for the CBR/MOEX/ACRA fields. These packages do not invent a
duplicate UI, silently change an Action response or start network calls. Exact
owner discovery remains mandatory before production binding.

## Production acceptance state

PR-64 still requires eight real external evidence cases:

1. Render commit;
2. cache-busted health;
3. auth-negative;
4. exact-route-positive;
5. GPT schema import;
6. authenticated Preview;
7. Action-list inspection;
8. rollback restore.

Green CI cannot mark these external cases passed.

## Что остаётся до полного релиза

### Backend and operations

- add other recognized rating agencies only through separate fixed contracts;
- locate exact CBR/MOEX/ACRA callers and bind lifecycles lazily;
- build production-grade news and corporate-event ingestion;
- execute real Render/Gateway/GPT acceptance and record evidence;
- add external versioned RAG with freshness and citation controls;
- expand operational runbooks and monitoring acceptance.

### Web cabinet

- найти и зарегистрировать исходный frontend существующего сайта;
- не создавать дубликат frontend;
- реализовать безопасный HTML-импорт СберИнвестиций без OCR;
- архив, сравнение периодов, расхождения, мобильный UI и обе темы;
- проверить production site и интерактивные элементы.

### Торговые этапы

Shadow, paper, preview и final-review инфраструктура не являются разрешением на
реальную торговлю. Confirm-before-trade, idempotency, TTL confirmation, kill
switch, partial-fill и timeout reconciliation требуют отдельной программы
допуска и решения владельца. Автономная торговля без подтверждения не включена.

## Следующий пакет после PR-98

Ближайший независимый безопасный пакет определяется после повторной проверки
roadmap и доступных официальных источников. Допустимые направления:

- отдельный fixed-source contract другого признанного рейтингового агентства;
- production acceptance/runbook hardening;
- lazy owner binding только после обнаружения точного существующего caller;
- news/corporate-event ingestion с provenance и injection controls.

Запрещено придумывать frontend, незаметно расширять Action response или запускать
сетевые вызовы при старте.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что PR-98 слит и CI
зелёный. Полный релиз требует внешней Render/Gateway/GPT acceptance evidence,
точного production owner binding и завершения оставшихся master-plan блоков.
