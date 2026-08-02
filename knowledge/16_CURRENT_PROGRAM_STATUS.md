# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-02

## Accepted cleanup baseline

Repository cleanup package:

- PR #147 — `Cleanup: reduce repository to active Omni-CIO bot and Gateway`;
- cleanup squash commit: `2032c4d9be66892af25cbaf995f0eb29922436c3`;
- exact-head Regression Shield run #871 completed successfully;
- PR #148 synchronized this status after the cleanup and also passed a fresh Regression Shield before merge;
- PR #149 removed the self-referential latest-main SHA from this status and passed Regression Shield run #875 before squash merge.

Do not hardcode the ever-changing latest `main` SHA in this status document: merging the document itself changes `main`. For the exact current SHA, read the GitHub `main` ref.

Previous product/configuration behavior package:

- PR #146 — tool-first Custom GPT portfolio routing;
- production read-only Instructions baseline was `v8.4.1`;
- canonical Sandbox-enabled Instructions are `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt`.

## Sandbox execution backend accepted into main

PR #160 — `Sandbox: add confirmed T-Invest virtual trade execution` — was squash-merged after exact-head Regression Shield run #909 completed successfully.

PR #162 — `Sandbox: fix Render TLS for T-Invest REST` — was squash-merged as main commit `95daa1670d637a09153745a2b79c1b9c6edb333c` after exact-head Regression Shield passed. It fixes the Sandbox REST TLS/CA path used from Render without weakening certificate verification.

Merged Sandbox backend provides an **optional virtual execution contour only**. It does not enable real-money trading.

Key properties:

- T-Invest Sandbox egress is hard-bound to `sandbox-invest-public-api.tbank.ru/rest`;
- uses only separate `TINVEST_SANDBOX_TOKEN`;
- production `TINVEST_TOKEN` remains read-only;
- server kill switch: `SANDBOX_TRADING_ENABLED`;
- default/off state preserves the existing 14-GET production Action surface;
- enabled state adds 8 Sandbox Actions and no real-money mutation Actions;
- BUY/SELL is two-phase: proposal/preflight → exact short-lived confirmation → submit;
- confirmation is bound to immutable order parameters;
- own-funds/own-position limits are checked during prepare and again immediately before submit;
- UUID request/order id provides idempotency;
- duplicate successful execution does not submit twice;
- ambiguous timeout/5xx after submit never auto-retries;
- margin confirmation is hard-disabled;
- Sandbox account identifiers are masked in user-facing payloads;
- withdrawal/transfer, real broker writes, stop-order automation and automatic replace are absent.

Canonical Sandbox Instructions:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt`

Owner runbook:

`docs/operations/SANDBOX_TRADING_RUNBOOK.md`

## Owner Preview acceptance observed on 2026-08-02

The owner enabled the isolated Sandbox contour in Render with a dedicated Sandbox token, refreshed the GPT Action surface, and performed live Preview acceptance against the deployed Gateway.

Observed successful scenarios:

- `getSandboxTradingStatus` returned healthy Sandbox state with `real_money=false`;
- Sandbox account creation required the exact owner confirmation phrase;
- virtual account funding required a separate exact owner confirmation phrase;
- `getSandboxPortfolio` reflected virtual cash and later virtual positions;
- SBER instrument identity and market snapshot were resolved before trading tests;
- MARKET BUY proposal required a short-lived exact confirmation and executed only after a new user message;
- MARKET SELL executed against an existing Sandbox position;
- SELL without an owned position was blocked before execution;
- expired confirmation was rejected and required a fresh proposal;
- wrong confirmation phrase returned `SANDBOX_CONFIRMATION_MISMATCH` and did not change the portfolio;
- duplicate confirmation of an already submitted proposal returned replay/idempotency protection instead of creating a second order;
- LIMIT BUY remained active in `NEW`, was queried by `getSandboxOrderState`, cancelled through `cancelSandboxOrder`, and subsequently reported `CANCELLED` with zero lots filled;
- portfolio checks after negative-confirmation tests confirmed no extra virtual position was created;
- throughout the observed tests responses remained `sandbox=true`, `real_money=false`, `sandbox_trading_methods=true`, `real_trading_methods=false`.

This is strong evidence that the core Sandbox execution path and confirmation/replay/cancel protections work through the real GPT → Render → T-Invest Sandbox chain.

### Remaining Sandbox hardening acceptance

The owner has **not yet externally exercised every destructive/recovery scenario from the runbook**. Before treating the full Sandbox runbook as exhausted, still verify when convenient:

- kill-switch rollback: `SANDBOX_TRADING_ENABLED=false` removes Sandbox routes from OpenAPI;
- multiple-open-Sandbox-account fail-closed behavior;
- proposal invalidation after Render restart;
- ambiguous post-submit timeout/5xx recovery via `unknown_do_not_resubmit` + order-state reconciliation.

These remaining checks do not justify enabling any real-money trading method.

## Current production boundary

- Custom GPT product: `Omni-CIO API | Управляющий и аналитик v8.4`;
- recommended model: `Thinking 5.6`;
- user-visible timezone: `Europe/Moscow` / MSK;
- production endpoint: `https://omni-cio-gateway.onrender.com`;
- production Render service: `omni-cio-gateway`;
- entrypoint: `app:app`;
- real broker contour remains read-only;
- production `TINVEST_TOKEN` remains read-only;
- `real_trading_methods=false`;
- no real order create/submit/cancel/replace endpoint is published;
- withdrawal/transfer methods are absent.

When `SANDBOX_TRADING_ENABLED=false`, expected Action surface remains exactly 14 GET Actions. When explicitly enabled, the separate Sandbox surface is available in addition to the read-only production Actions.

## Render topology

Intended topology remains one active Render Web Service:

- `omni-cio-gateway`;
- no active Blueprint instance;
- obsolete Telegram service removed;
- obsolete duplicate/alternate Gateway service removed;
- service connected to `Misha2304/omni-cio-gateway` / `main`;
- `render.yaml` remains only a declarative/recovery contract.

Sandbox does **not** require a second Render service. It is an optional isolated contour inside the same Gateway.

Render secret/config separation:

- `TINVEST_TOKEN` — production read-only;
- `TINVEST_SANDBOX_TOKEN` — Sandbox only;
- `GATEWAY_API_KEY` — GPT → Gateway Bearer secret;
- `SANDBOX_TRADING_ENABLED` — Sandbox kill switch;
- `SANDBOX_CONFIRMATION_TTL_SECONDS` — short-lived confirmation TTL.

## Repository structure

Repository remains organized around one supported product:

`Omni-CIO Custom GPT → Omni-CIO Gateway → T-Invest API`

Primary areas:

- runtime/wrappers — root + `omni_cio/`;
- Sandbox execution — `omni_cio/sandbox/` only;
- GPT configuration — `gpt/`;
- engineering/domain memory — `knowledge/`;
- master plan — `docs/master-plan/`;
- active architecture/runbooks — `docs/architecture/`, `docs/operations/`;
- regression/security — `tests/`, `scripts/`, `.github/`.

`app_v371.py`, `app_v360.py` and `main.py` remain runtime dependencies and must not be deleted as legacy without a separate compatibility refactor.

## Accepted read-only Preview baseline

Previously observed owner Preview tests confirmed:

- broker connection;
- money/balance query;
- current portfolio query;
- 90-day operations query;
- exact single-Action isolation;
- portfolio-management routing;
- masked account display;
- Moscow time display.

Portfolio-management baseline:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`

Fresh-market gate blocks exact personalized lot sizing without market readiness/fresh best ask.

## Secret boundary

GitHub stores no real values of:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- future real full-access/transfer-access broker token values;
- `GATEWAY_API_KEY`;
- Authorization headers;
- full account IDs;
- private broker payloads as configuration.

## Supported capability scope

### Real production contour

Still read-only:

- health/T-Invest connection;
- portfolio and enriched positions;
- instrument search;
- market snapshots;
- portfolio analytics;
- cash/liquidity diagnostics;
- purchase-capacity preview;
- operations history/analytics;
- official broker-report reconciliation;
- final decision review;
- relevant public web/news context through GPT Web Search.

### Optional Sandbox contour after explicit enable

- Sandbox status/accounts;
- virtual account bootstrap/funding;
- virtual portfolio/positions;
- BUY/SELL proposal and preflight;
- explicit confirmed virtual submit;
- order-state verification;
- explicit confirmed Sandbox cancellation.

Real-money order submission/cancellation/replace, withdrawal and transfer remain unsupported.

## Next development stage

The next engineering package is a **separate real-money execution design/release program**. Development may proceed in isolated branches, but real broker writes remain disabled until the new release has its own threat model, tests, exact-head Regression Shield and owner acceptance.

Mandatory design boundary for that future release:

- never promote or overwrite the existing `TINVEST_TOKEN`;
- use a separate account-scoped trading token with only the minimum broker permissions required for orders;
- keep withdrawal/transfer completely absent from the Action surface and implementation;
- separate real-trading kill switch, default `false`;
- proposal/preflight first, then an exact short-lived owner confirmation in a new message, then submit;
- revalidate instrument, account, quantity, price/market state, own funds/position and risk limits immediately before submit;
- immutable proposal parameters and UUID/idempotency protection;
- fail closed on stale/incomplete/contradictory data;
- ambiguous submit must never auto-resubmit and must reconcile order state;
- hard per-order and daily notional/lot limits configurable server-side;
- production order state and portfolio must be reconciled after execution;
- account IDs remain masked;
- explicit audit trail without tokens, full account IDs or private payload dumps;
- no margin automation, no stop-order automation, no auto-replace in the first real-money release.

Until that separate release passes, `real_trading_methods=false` is an invariant.
