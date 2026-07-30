# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-96**  
Точная версия определяется текущей вершиной ветки `main`.

## Назначение документа

Это оперативная карта программы. Код в `main` остаётся окончательным источником
истины; стратегические правила и Definition of Done определяются `AGENTS.md`,
`knowledge/00_PROJECT_MASTER_CONTEXT.md` и исходным master plan.

## Неизменяемые границы

- `trading_methods=false`;
- пользовательские Gateway Actions только `GET`;
- ровно 14 authenticated Actions;
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
- **PR-94…PR-96:** fixed official ACRA issuer-level national-RU rating-action
  source, bounded freshness cache and privacy-safe source/cache telemetry.

## PR-81…PR-83 authenticated owner lifecycle

Existing Bearer auth and exact compact-response validation create a trusted
server context. A fresh typed Decision/intent/capacity/pro-forma snapshot is
selected by exact scenario, correlation, operation and masked account, rebound
to existing owner ports and invoked at most once. Bounded redacted evidence is
retained. Startup performs no owner, calculator, portfolio, network or broker
call. Public response and OpenAPI remain unchanged.

## PR-84…PR-88 CBR lifecycle

PR-84 provides the fixed Bank of Russia `DailyInfo.KeyRateXML` source with typed
Decimal observations, protected XML parsing, bounded HTTPS streaming and
redacted failures. PR-85 adds exact-range fresh/stale/unavailable cache state,
single-flight refresh and no-silent-stale policy. PR-86 emits allowlisted
operational metadata without rate, date range, XML, account or upstream text.
PR-87 evaluates operational conditions only with bounded thresholds, cooldown
and recovery. PR-88 deterministically retains fired/recovered evidence without
source fetch at import/startup.

## PR-89…PR-93 MOEX lifecycle

- fixed official public `stock/shares/TQBR` endpoint and strict SECID identity;
- allowlisted JSON tables, Decimal prices and Moscow time normalization;
- public feed permanently marked potentially delayed, non-realtime and
  informational-only;
- exact `(TQBR, normalized SECID)` cache with separate retrieval TTL and market
  age derived from `quote.as_of`;
- stale exposure only after refresh failure and explicit trusted policy;
- pure status/freshness observability without price, SECID, account or raw JSON;
- global-only operational alert policy with forged-event rejection;
- deterministic event → evaluation → bounded fired/recovered evidence;
- no external notification transport and no startup network call.

Broker `getMarketSnapshot` remains primary for execution-style calculations.
MOEX and broker values are never silently averaged.

## PR-94 official ACRA issuer rating action source

### Fixed source

- endpoint:
  `https://www.acra-ratings.ru/press-releases/?count=30&lang=en`;
- provider `ACRA`;
- source id `ACRA.press_releases.issuer_rating_actions`;
- release identity limited to numeric official `/press-releases/{id}/?lang=en`;
- no caller-controlled host, path, agency, language or generic URL.

### Supported issuer records

V1 accepts simple issuer-level Russian national-scale assigned, affirmed,
upgraded, downgraded and withdrawn actions. Each record contains normalized
subject name, fixed issuer scope, agency-specific rating, action, explicit
outlook when published, publication date and canonical official release URL.

Issue/bond/note/tranche/RMBS/series/class/security actions, international-scale
actions and multi-target/multi-rating titles are skipped as unsupported scope. A
title that clearly presents one national-RU issuer action but no longer matches
the allowlisted grammar fails closed.

Transport uses fixed HTTPS scope, redirects disabled, bounded streamed bytes,
HTML/XHTML content validation, script/style/noscript exclusion and fixed typed
errors. Raw HTML, body and exception text are not retained. Import/startup make
no source call.

## PR-95 bounded ACRA rating-action cache

- one fixed-source process-local entry; capacity is structurally one;
- fresh TTL 900 seconds and stale retention 86400 seconds;
- future-source tolerance 30 seconds;
- retrieval freshness derives only from `snapshot.retrieved_at`;
- record `published_on` dates remain separate source evidence;
- one `RLock` provides single-flight refresh and protects prune/clear state;
- still-fresh fallback after failed force refresh is explicit;
- stale records remain hidden unless refresh failed and trusted
  `allow_stale=true` was supplied;
- fully expired entries are removed before refresh;
- wrong type, source identity, future timestamp and unavailable source fail
  closed with fixed cache error codes;
- only typed PR-94 snapshots are retained; restart starts empty.

## PR-96 safe ACRA source/cache observability

PR-96 maps only typed PR-94/95 results to existing immutable
`ObservabilityEventV1`.

### Source events

- source available/unavailable outcome and severity;
- provider `ACRA`, fixed operation and optional validated latency;
- safe record count and fixed-source/issuer-scope boolean metrics;
- fixed source error code on failure.

### Cache events

- explicit fresh/stale/unavailable freshness;
- cache hit, refresh attempted/succeeded, stale available/exposed and display
  allowed metrics;
- external call `not_called` for cache hit without refresh;
- successful refresh as success;
- failed force refresh with fresh fallback as degraded/warning;
- stale as degraded/warning and unavailable as failure/error.

Events intentionally omit issuer name, rating, rating scale, outlook, action,
release URL/id, publication date, raw HTML/title, account, portfolio, broker
payload and upstream exception/body. Builders are pure: no automatic emission,
logging, alerting or source/cache call.

## Compatibility and safety after PR-96

- `app:app` unchanged;
- exactly 14 authenticated GET Actions unchanged;
- no route, request body, public response field or frontend component;
- no dependency, database, secret or Render migration;
- no source/cache call or event emission at import/startup;
- no T-Invest call or broker write method;
- `trading_methods=false`.

## Frontend/owner discovery state

Repository search did not find a registered existing frontend/dashboard owner or
production caller for the CBR/MOEX/ACRA fields. These source packages therefore
do not invent a duplicate UI, silently change an Action response or start
network calls. Exact owner discovery remains mandatory before production binding.

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

- add a bounded global operational ACRA alert/evidence lifecycle only after
  canonical-event validation; no per-issuer or per-rating semantics;
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

## Следующий пакет после PR-96

Ближайший независимый безопасный пакет — bounded global ACRA operational alert
policy v1:

- accept canonical PR-96 events only;
- conditions limited to source/cache availability, stale exposure and failed
  refresh while fresh cache remains usable;
- no issuer, rating, outlook, release or financial thresholds;
- bounded thresholds, deduplication, cooldown, recovery and retention;
- no webhook, email, Telegram, pager or other outbound transport;
- no route, Action, frontend field or broker method.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что PR-96 слит и CI
зелёный. Полный релиз требует внешней Render/Gateway/GPT acceptance evidence,
точного production owner binding и завершения оставшихся master-plan блоков.
