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
- accepted production Instructions remain `v8.4.1` until Sandbox owner acceptance.

## Sandbox execution backend accepted into main

PR #160 — `Sandbox: add confirmed T-Invest virtual trade execution` — was squash-merged after exact-head Regression Shield run #909 completed successfully on both jobs:

- Quality, contracts and coverage — success;
- Dependency, code and secret security — success.

Merged Sandbox backend provides an **optional virtual execution contour only**. It does not enable real-money trading.

Key properties:

- T-Invest Sandbox egress is hard-bound to `sandbox-invest-public-api.tbank.ru/rest`;
- uses only separate `TINVEST_SANDBOX_TOKEN`;
- `TINVEST_TOKEN` remains the existing production read-only token;
- server kill switch: `SANDBOX_TRADING_ENABLED`;
- default/off state preserves the existing 14-GET production Action surface;
- BUY/SELL is two-phase: proposal/preflight → exact short-lived confirmation → submit;
- confirmation is bound to immutable order parameters;
- own-funds/own-position limits are checked during prepare and again immediately before submit;
- UUID request/order id provides idempotency;
- duplicate successful execution does not submit twice;
- ambiguous timeout/5xx after submit never auto-retries;
- margin confirmation is hard-disabled;
- Sandbox account identifiers are masked in user-facing payloads;
- withdrawal/transfer, real broker writes, stop-order automation and automatic replace are absent.

Candidate GPT Instructions for Sandbox acceptance:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt`

Owner runbook:

`docs/operations/SANDBOX_TRADING_RUNBOOK.md`

## Production baseline

Until the owner explicitly enables Sandbox in Render and refreshes GPT OpenAPI/Instructions:

- Custom GPT: `Omni-CIO API | Управляющий и аналитик v8.4`;
- production Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`;
- recommended model: `Thinking 5.6`;
- user-visible timezone: `Europe/Moscow` / MSK;
- production endpoint: `https://omni-cio-gateway.onrender.com`;
- production Render service: `omni-cio-gateway`;
- entrypoint: `app:app`;
- real broker Action surface: exactly 14 GET Actions while Sandbox is disabled;
- real-money `trading_methods=false`;
- real `TINVEST_TOKEN` remains read-only.

## Render topology

Intended topology remains one active Render Web Service:

- `omni-cio-gateway`;
- no active Blueprint instance;
- obsolete Telegram service removed;
- obsolete duplicate/alternate Gateway service removed;
- service connected to `Misha2304/omni-cio-gateway` / `main`;
- `render.yaml` remains only a declarative/recovery contract.

Sandbox does **not** require a second Render service. It is an optional isolated contour inside the same Gateway.

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

Render separation:

- `TINVEST_TOKEN` — production read-only;
- `TINVEST_SANDBOX_TOKEN` — Sandbox only;
- `GATEWAY_API_KEY` — GPT → Gateway Bearer secret.

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

### Optional Sandbox contour after owner enable

- Sandbox status/accounts;
- virtual account bootstrap/funding;
- virtual portfolio/positions;
- BUY/SELL proposal and preflight;
- explicit confirmed virtual submit;
- order-state verification;
- explicit confirmed Sandbox cancellation.

Real-money order submission/cancellation/replace, withdrawal and transfer remain unsupported.

## Immediate owner acceptance remaining

Code development and automated Regression Shield for the Sandbox backend are complete. External acceptance now requires owner-side secrets/configuration because GitHub cannot create T-Invest tokens or edit Render/GPT Editor secrets.

Required sequence:

1. Create a dedicated **Sandbox token** in T-Invest. Do not replace or elevate the existing production read-only token.
2. In Render `omni-cio-gateway → Environment` add:
   - `TINVEST_SANDBOX_TOKEN=<dedicated sandbox token>`;
   - `SANDBOX_TRADING_ENABLED=true`;
   - `SANDBOX_CONFIRMATION_TTL_SECONDS=120`.
3. Keep unchanged:
   - `TINVEST_TOKEN` (read-only);
   - `GATEWAY_API_KEY`;
   - `SSL_TBANK_VERIFY=True`.
4. Wait for healthy redeploy and verify `getSandboxTradingStatus`.
5. In GPT Editor replace Instructions with `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_5_0.txt`.
6. Re-import production `/openapi.json`; expect 14 baseline + 8 Sandbox Actions and no real-money mutation Actions.
7. Keep the same 10 Knowledge files.
8. Run the virtual BUY, SELL, order-state, duplicate, expiry, tamper and kill-switch acceptance in `docs/operations/SANDBOX_TRADING_RUNBOOK.md`.
9. Press `Update` only after acceptance passes.

## Next development stage

After full Sandbox owner acceptance, open a **separate** real-money execution design/release. That future stage must use a separate account-scoped full-access token and an equally strict confirmation/reconciliation/kill-switch boundary. It must not silently promote `TINVEST_TOKEN`, and it must not include transfer-access unless separately designed and explicitly approved.
