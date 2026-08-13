# Omni-CIO V10 — WP18 Execution Contract

Status: **IMPLEMENTATION / NOT YET ACCEPTED**

This document instantiates `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md` for WP18. It does not itself prove completion.

## 1. WP identity

- Block: E — Omni-CIO Web Platform.
- WP: WP18.
- Title: Portfolio Dashboard and Assets.
- Authorized by current program status: YES.
- Prior Exit Gate proven by: Block D/WP15 accepted, WP16 COMPLETE, WP17 COMPLETE, PR #302 squash-merged, and post-merge Regression Shield SUCCESS on accepted `main` `8b6780dc2d0c6cb3f70577e6f24a5e8ca11def07`.

## 2. Accepted baseline

- Accepted `main` SHA: `8b6780dc2d0c6cb3f70577e6f24a5e8ca11def07`.
- Protected runtime baseline: V9 remains owner-accepted rollback/reference; V10 local/private Web remains non-public.
- Master Plan authority: WP18 — Portfolio Dashboard and Assets.
- Status authority: `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.
- Relevant accepted contracts: WP15 T-Invest READ-only contract and adapters, WP16 Design System contract, WP17 Application Shell/session/Broker Connections contracts, V10 canonical portfolio/common/analytics/risk contracts.

## 3. Purpose

Give the authenticated OWNER a transparent, current-on-demand read-only view of capital in the existing V10 Web App without requiring GPT and without widening broker authority.

## 4. Inputs and prerequisites

- accepted WP15 connection-scoped T-Invest READ adapters;
- accepted WP17 server-side session and tenant scope;
- accepted WP17 Broker Connections repository and OWNER-controlled read vault;
- accepted WP16 design-system primitives;
- canonical Decimal/UTC portfolio contracts;
- exact accepted `main` above;
- Lenovo `omni-cio-ci` authoritative Windows runner.

## 5. Existing implementation to reuse

- `apps/web`: reuse the single accepted React/Vite/TypeScript Web App; no second frontend.
- `omni_cio/web/session_v1.py`: reuse server-side session/tenant boundary.
- `omni_cio/web/persistence_v1.py`: reuse BrokerConnection/account bindings.
- `omni_cio/web/broker_vault_v1.py`: reuse protected READ credential storage.
- `omni_cio/adapters/tinvest_read_v1.py`: reuse normalized portfolio/cash/freshness/quality semantics.
- `omni_cio/adapters/tinvest_market_v1.py`: reuse bounded last-price READ path.
- `omni_cio/adapters/tinvest_connection_v1.py`: reuse exact account binding.
- `omni_cio/contracts/v1/portfolio.py`: reuse canonical money/position identity semantics.
- `omni_cio/contracts/v1/analytics.py` and `risk.py`: reuse explicit missing issuer/sector semantics rather than invent classifications.

No accepted financial engine is rewritten by WP18.

## 6. Allowed changes

WP18 may change only the existing local/private Web product path and focused contracts/tests/audits required to display portfolio/assets truthfully:

- `apps/web/**`;
- local/private `apps/api/app.py` composition only;
- focused `omni_cio/web/portfolio_dashboard_v1.py` product projection;
- focused WP18 tests, docs and CI workflow.

## 7. Explicit non-goals

WP18 does not implement:

- WP19 Watchtower/alerts UI;
- WP20 Research Dossier UI;
- public Internet ingress or public multi-user activation;
- Telegram;
- AI/Cortex;
- report-import accounting redesign;
- broker WRITE/TRADE methods, orders, transfers or withdrawals;
- FX conversion engine or universal cross-currency aggregation;
- sector/issuer guesses derived from display names or tickers;
- Real execution.

## 8. Interfaces/contracts

### `GET /api/v10/web/portfolio-dashboard`

- producer: local/private FastAPI Web runtime;
- consumer: existing `apps/web` Portfolio/Assets routes;
- auth scope: tenant comes only from accepted server-side session;
- cache: `no-store`;
- compatibility: additive WP18 v1 product projection; browser receives no raw provider account ID, account fingerprint, token or `secret_ref`;
- Decimal: money/quantity/weights transported as decimal strings;
- unknown/null: absence stays null/unavailable and is never silently converted to zero;
- stale/partial: explicit freshness/completeness/warnings with timestamps;
- source/time: displayed financial values must carry or visibly inherit source plus `as_of`/retrieved/evaluated time.

### Refresh/current semantics

WP18 v1 is **manual pull-to-refresh**. Opening Portfolio/Assets performs one bounded READ snapshot; the explicit Refresh action performs another. There is no silent polling and no claim that an old snapshot is continuously live. `generated_at`, broker `retrieved_at`, market `retrieved_at` and stale state remain visible.

### Broker versus market value

Broker-reported portfolio/position data is separate from `GetLastPrices`. Current-market monetary conversion is performed only where the available instrument metadata makes the formula semantically unambiguous. Unsupported asset-specific conversions remain visibly unavailable.

## 9. Data/persistence effects

- migration required: NO.
- forward migration: none.
- rollback: remove WP18 product route/UI projection and return to accepted WP17 placeholders; existing sessions, Broker Connections, vault and broker data remain untouched.
- private data: portfolio values remain runtime/browser response data only and are not written to GitHub/CI artifacts.
- backup/recovery consequence: none beyond existing accepted WP10/WP13/WP17 recovery boundaries.

## 10. Security/authority effects

WP18 changes no security authority boundary:

- secret access: unchanged; server reads existing READ vault only;
- broker authority: READ_ONLY unchanged;
- OS/runtime privileges: unchanged;
- GitHub permissions: unchanged;
- Web ingress: local/private unchanged;
- AI tool authority: none;
- Real execution: unchanged/off.

Permanent invariants: `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`.

## 11. Normal-path acceptance tests

Required deterministic coverage:

- golden normal portfolio fixture;
- Decimal/currency preservation;
- broker total/cash/positions rendering contract;
- same-currency weights and concentration;
- source/timestamp visibility;
- broker/current-market distinction;
- authenticated session-derived tenant scope;
- Portfolio and Assets routes inside accepted WP17 shell.

## 12. Negative/failure tests

Required coverage:

- empty broker configuration;
- partial/unresolved broker positions;
- stale broker snapshot;
- missing/stale/unavailable market quotes;
- optional/unknown data stays null, not zero;
- unsupported asset-specific market conversion remains unavailable;
- unauthenticated API request returns 401;
- token/secret reference/fingerprint are absent from browser payload;
- downstream account failure emits explicit unavailable state with no fabricated values.

## 13. Observability

- user-visible state: READY/PARTIAL/STALE/DEGRADED/EMPTY/UNAVAILABLE as applicable;
- visible broker connection state;
- visible freshness/completeness/unresolved counts;
- sanitized warnings only;
- source/time metadata visible beside or inherited by displayed numeric groups;
- no private portfolio payload in CI evidence.

## 14. CI routing

- Fast hosted checks: existing hosted fast policy/source/frontend paths; billing failure remains infrastructure degradation, not PASS.
- Hosted clean-room compatibility required: existing path-aware matrix remains authoritative when GitHub starts it; no weakening if unavailable for billing.
- Lenovo authoritative checks: V10 authoritative merge gate plus dedicated `V10 WP18 Portfolio Dashboard Audit`, and WP16/WP17 regressions.
- GPU AI eval required: NO.
- Release/recovery matrix required: no new migration/runtime privilege; existing permanent guards and post-merge Regression Shield remain required.

## 15. Rollback/recovery

Squash merge provides one revertable WP18 change set. Revert restores WP17 Portfolio/Assets placeholders while preserving DB schema, sessions, Broker Connections, vault material and protected V9 rollback. No broker state mutation is performed by WP18.

## 16. Exit Gate

PASS only if all are true on one exact PR head:

1. Every displayed financial/derived number has a visible source and relevant timestamp or an explicit inherited provenance rule visible in the same UI context.
2. Empty, unknown, partial, stale and unavailable states are not hidden or converted to zero.
3. Golden, Decimal/currency, empty, partial and stale tests pass.
4. Issuer/sector/class coverage is either obtained from reviewed authoritative metadata or explicitly represented as unavailable without guessing; no required field is silently omitted.
5. Position identity/detail is visible and links to already-owned incident/research contracts only where deterministic linkage exists.
6. Broker/current-market semantics are explicit and unsupported conversion fails closed.
7. WP16/WP17 regression gates, dedicated WP18 gate and authoritative merge gate are GREEN on the exact head.
8. Zero unresolved blocking review threads; full diff reviewed.
9. Squash merge is followed by exact-main Regression Shield SUCCESS before WP18 is declared COMPLETE.

## 17. Required acceptance evidence

- exact PR head SHA;
- dedicated WP18 audit run ID and SUCCESS;
- WP16/WP17 regression SUCCESS on same head;
- authoritative merge gate SUCCESS on same head;
- deterministic golden/Decimal/empty/partial/stale test results;
- final reviewed diff and zero blocking threads;
- squash merge SHA;
- post-merge Regression Shield SUCCESS on that exact main.

No OWNER physical evidence is required by current WP18 scope unless a later test discovers a truly non-delegable local/private parity action.

## 18. Documentation/status updates in the same PR

Before merge, update as appropriate:

- `docs/architecture/V10_WP18_PORTFOLIO_DASHBOARD_CONTRACT.md`;
- this execution contract;
- `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` only when exact-head Exit Gate evidence is complete and the status transition can be truthfully prepared.

The final accepted program status is not effective until post-merge Regression Shield passes.

## 19. Next WP unlock

WP19 — Watchtower / Alerts UI remains LOCKED. It unlocks only after WP18 Exit Gate, squash merge, exact-main post-merge Regression Shield SUCCESS and official status update.

## 20. Scope-discovery rule

Any adjacent work discovered during WP18 is classified explicitly as:

- WP18 blocker/defect only if required by the Exit Gate above;
- future-WP backlog if not required now;
- architecture/program amendment if it changes authority, sequence or OWNER-approved scope.

No later-WP implementation is smuggled into WP18.
