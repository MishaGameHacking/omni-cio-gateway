# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-31  
Фактическая вершина программы после merge этого пакета: **PR-99**  
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
- **PR-94…PR-98:** fixed official ACRA issuer-level national-RU source, bounded
  cache, privacy-safe telemetry, global alert policy and terminal evidence;
- **PR-99:** separate fixed Expert RA issuer-level national-Russia rating-action
  source with agency-specific contracts and protected HTML transport.

## PR-81…PR-83 authenticated owner lifecycle

Existing Bearer auth and exact compact-response validation create a trusted
server context. A fresh typed Decision/intent/capacity/pro-forma snapshot is
selected by exact scenario, correlation, operation and masked account, rebound
to existing owner ports and invoked at most once. Bounded redacted evidence is
retained. Startup performs no owner, calculator, portfolio, network or broker
call. Public response and OpenAPI remain unchanged.

## PR-84…PR-88 CBR lifecycle

The fixed Bank of Russia source provides typed Decimal observations, protected
XML parsing, bounded HTTPS streaming and redacted failures. The exact-range
cache exposes explicit fresh/stale/unavailable state, single-flight refresh and
no-silent-stale behavior. Observability contains operational metadata only.
Alerting uses bounded operational thresholds, cooldown and recovery; the final
lifecycle retains only bounded fired/recovered evidence without startup fetch.

## PR-89…PR-93 MOEX lifecycle

- fixed official public `stock/shares/TQBR` endpoint and strict SECID identity;
- allowlisted JSON tables, Decimal prices and Moscow time normalization;
- public feed marked potentially delayed, non-realtime and informational-only;
- exact `(TQBR, normalized SECID)` cache with separate retrieval TTL and market
  age derived from `quote.as_of`;
- stale exposure only after refresh failure and explicit trusted policy;
- status/freshness telemetry without price, SECID, account or raw JSON;
- global-only operational alert policy with forged-event rejection;
- deterministic event -> evaluation -> bounded fired/recovered evidence;
- no external notification transport and no startup network call.

Broker `getMarketSnapshot` remains primary for execution-style calculations.
MOEX and broker values are never silently averaged.

## PR-94…PR-98 ACRA lifecycle

The ACRA chain uses one fixed official issuer-action endpoint and separate
agency-specific `(RU)` contracts. It supports issuer-level assigned, affirmed,
upgraded, downgraded and withdrawn actions, rejects malformed supported titles,
skips issue/international/multi-target scope and never converts scales.

The one-entry cache provides explicit fresh/stale/unavailable state,
single-flight refresh and no-silent-stale behavior. Telemetry contains only
operational metadata. The global alert policy accepts only complete canonical
events and rejects duplicate or forged metrics. PR-98 composes event,
evaluation and bounded terminal evidence under one `RLock`. Evidence and sink
results contain no issuer, rating, outlook, release, account, broker or financial
payload and no exception text.

## PR-99 Expert RA fixed issuer-action source

### External verification and fixed identity

The package was started only after current external verification that:

- Bank of Russia infrastructure materials list the current credit-rating-agency
  register;
- the Bank of Russia decision dated 7 July 2026 identifies AO Expert RA and its
  national `ru...` scale;
- the official Russian site publishes rating actions under stable
  `https://raexpert.ru/releases/{year}/{slug}` identities.

Runtime identity is fixed:

- endpoint `https://raexpert.ru/`;
- provider `Expert RA`;
- source id `EXPERT_RA.home.rating_actions`;
- accepted official release hosts are `raexpert.ru` and fixed alias
  `www.raexpert.ru`;
- stored canonical release host is always `raexpert.ru`;
- release path exactly `/releases/{20xx}/{monDD[a-z]?}`;
- source language Russian.

Caller-controlled URLs, redirects for the owned client, English/secondary hosts,
query strings, fragments and arbitrary release paths are not allowed. The fixed
`www` alias is never selected dynamically and cannot change the endpoint.

### Supported data and grammar

PR-99 uses separate `ExpertRa...` contracts rather than ACRA records. It accepts
singular issuer-level assigned, affirmed, upgraded, downgraded and withdrawn
credit-rating actions only.

The parser supports the agency-specific Russian national scale `ruAAA…ruD`.
Visual Cyrillic/Latin A/B/C/R/D variants inside rating tokens are normalized and
then checked against a closed allowlist. Stable, positive, negative and
developing outlooks are captured only when explicitly present in a supported
title, including a bounded optional continuation about status under observation.

Extraction is confined to the visible homepage section from `Рейтинговые
действия` up to `Аналитика`. Similar links outside this section cannot enter the
snapshot.

The parser skips bond/issue/series/tranche/structured-finance actions, ESG and
other non-credit ratings, plural actions and unsupported scales. A malformed
title that clearly claims a singular supported issuer credit-rating action fails
closed.

### Transport and data safety

- fixed HTTPS GET;
- HTML/XHTML only;
- bounded declared and streamed bytes;
- UTF-8/UTF-8-BOM only;
- scripts/styles/noscript ignored;
- exact visible page-section boundary required;
- adjacent valid publication dates with future-date rejection;
- canonical release URL and duplicate-conflict checks;
- bounded newest-first records;
- raw title/HTML/body/exception text not stored;
- source text treated only as data and external instructions never executed.

Contracts declare informational use only, no software-authorized redistribution,
not an investment recommendation, no credentials/full account ID, no broker
write, no order creation and `trading_methods=false`.

## Compatibility and safety after PR-99

- `app:app` unchanged;
- 14 GET Actions unchanged: 13 authenticated and public health;
- no route, request body, public response field or frontend component;
- no dependency, database, secret or Render migration;
- no source fetch at import/startup;
- no cache, observability, alert or evidence behavior for Expert RA yet;
- no webhook, email, Telegram, pager or external transport;
- no T-Invest call or broker write method;
- `trading_methods=false`.

## Frontend/owner discovery state

Repository search has not identified a registered existing frontend/dashboard
owner or production caller for the CBR/MOEX/ACRA/Expert RA fields. These packages
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

- add bounded Expert RA cache, telemetry and operational lifecycle only through
  separate reviewed packages;
- add other recognized rating agencies only through separate fixed contracts;
- locate exact market-data callers and bind lifecycles lazily;
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

## Следующий пакет после PR-99

Ближайший независимый пакет — one-entry bounded Expert RA cache v1:

- accept only typed PR-99 snapshots with exact provider/source identity;
- fresh, stale and unavailable states;
- retrieval freshness derived only from `snapshot.retrieved_at`;
- publication dates retained as separate source evidence;
- single-flight refresh under one lock;
- stale hidden unless refresh failed and trusted `allow_stale=true`;
- fully expired state pruned;
- bounded controls, restart-empty and explicit clear;
- no source fetch at import/startup;
- no route, Action, frontend, external notification or broker method.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что PR-99 слит и CI
зелёный. Полный релиз требует внешней Render/Gateway/GPT acceptance evidence,
точного production owner binding и завершения оставшихся master-plan блоков.
