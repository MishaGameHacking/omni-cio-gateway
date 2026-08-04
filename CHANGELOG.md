# Changelog

Краткая история заметных изменений текущего Omni-CIO. Подробная инженерная последовательность остаётся в Git/PR history; этот файл фиксирует release/program milestones и не дублирует архитектурные документы целиком.

## [Unreleased]

### Omni-CIO v9 Portfolio Autopilot — program development

Canonical roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`. Стабильный v8.6.1 остаётся защищённым production baseline до WP15.

Завершённые work packages:

- WP0 Baseline freeze — PR #181, Regression Shield #989;
- WP1 Natural Language CIO Router — PR #184, merge `7f677288...`, #1002;
- WP2 Investment Policy Statement Engine — PR #187, merge `75c9ae07...`, #1014;
- WP3 Market Universe Engine — PR #189, merge `5ae81aa9...`, #1019;
- WP4 Deterministic Candidate Funnel — PR #191, merge `3946fc9a...`, #1035;
- WP5 Research & Evidence Engine — PR #194, merge `f8f0bb95...`, #1043;
- WP6 Credit, Rating & Default Engine 2.0 — PR #196, merge `64316008...`, #1057;
- WP7 Fund X-Ray Engine — PR #198, merge `15505272...`, #1064;
- WP8 Portfolio Risk Engine 2.0 — PR #201, merge `24e027f1...`, #1078;
- WP9 Meta-Strategy Selector — PR #204, merge `f758fd73...`, exact-head #1088;
- WP10 Portfolio Optimizer & Capital Scaling — PR #206, squash merge `f73929771bcae4058c3c83b3d0632b8d66b8d05f`, exact-head #1105;
- WP11 Immutable Portfolio Plan Protocol — PR #208, squash merge `7c3006d332041ec352f0c2eab8c7cb70e4c1a6af`, exact-head Regression Shield #1114 on `b97a62412fe8accf8ebec528a63d8ad0b5087154`.

### WP12 — Safe Plan Execution Engine — final merge gate

Tracking: issue #209 / draft PR #211 / branch `v9/wp12-safe-plan-execution`.

Implemented:

- versioned plan-execution contracts for session, immutable instrument binding, stage, attempt, broker snapshot and current read-only state;
- exact canonical WP11 plan SHA plus exact plan-specific owner approval phrase before any real stage can become eligible;
- approval recording is idempotent and performs zero broker submit;
- accepted v8.6.1 `RealTradingServiceV1` remains the only real BUY/SELL submit primitive; WP12 adds no second broker client or token path;
- current portfolio/cash, policy/risk/strategy/optimizer/target-risk identities, instrument UID/ticker/ISIN/lot size, quote freshness, price step, spread, turnover, depth and plan-drift evidence are revalidated immediately before stage preparation and again before submit;
- existing v8.6.1 `GetMaxLots` own-funds/own-position preflight, per-order cap and atomic daily cap remain authoritative;
- only `LIMIT / CURRENCY / DAY`, RUB, cash share/ETF BUY/SELL remains inside the proven real-money surface;
- durable revisioned execution journal with compare-and-swap semantics and production Upstash implementation;
- restart/CAS/stale-writer/tamper/wrong-secret acceptance coverage for the durable journal;
- deterministic broker reconciliation normalizes exact request/proposal state and rejects malformed/overflow broker evidence;
- `NEW` / partial broker state remains active and is never resubmitted;
- broker-terminal state requires independent read-only portfolio/cash reconciliation before the next stage;
- partial terminal fill carries only the broker-confirmed remainder to the following Moscow day;
- possible-submit ambiguity halts all remaining legs and allows only reconciliation of the original request id; replay cannot duplicate `PostOrder`;
- plan expiry blocks new stage preparation/submit but never suppresses reconciliation for an order that already may have reached the broker;
- post-approval strategy/optimizer/target-risk SHA drift fails closed; before first confirmed fill, the starting portfolio snapshot and current-risk SHA must still match WP11 exactly;
- WP11 plan expiry now spans the WP10 `required_execution_days` horizon while retaining the short final-day validity tail;
- multi-leg staged scheduling is tranche-first (`stage_index`) and exact-leg-sequence second, keeping portfolio staging synchronized by day;
- a specific immutable instrument may submit at most one staged slice per Moscow calendar day;
- existing hard caps may make a slice smaller only when the resulting real stage count still fits inside immutable WP11 expiry; otherwise preparation fails with `PLAN_EXECUTION_PLAN_HORIZON_TOO_SHORT` rather than extending the plan or increasing caps;
- permanent `scripts/check_plan_execution_boundary.py` prevents a direct broker/Sandbox mutation path and enforces hard-disabled autonomous/margin/short/withdrawal/transfer authority;
- WP12 package and boundary guard are included in mypy scope;
- architecture, threat-model and data-contract documents are canonicalized under `docs/architecture/`.

Acceptance coverage includes owner approval/no-submit, complete one-submit lifecycle, partial fill, terminal reconciliation, completed replay, already-submitted replay, ambiguous-submit reconciliation-only recovery, expiry semantics, upstream SHA drift, instrument drift, NO_ACTION no-session, deterministic WP10 multi-day staging, tranche ordering, same-instrument daily cadence, hard-cap horizon rejection, durable storage integrity and repository authority boundaries.

WP12 remains **IN PROGRESS** only until the final branch head passes the exact-head Regression Shield, review threads are zero and PR #211 is squash-merged. No GPT Editor change and no real-cap increase is part of this gate.

Next dependency after WP12 merge: **WP13 — Portfolio Watchtower**.

Applied Custom GPT remains v8.6.1 until WP15; current v9 development is not authorization for broader real-money execution.

### Omni-CIO v8.6.1 — released / owner accepted

- GPT Editor uses `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`; full v8.6.0 remains engineering reference.
- UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Production OpenAPI exposes accepted read-only, Sandbox and conditional Real Trading surfaces.
- Durable real journal uses Upstash Redis over HTTPS; Render remains Free.
- Dedicated `TINVEST_TRADING_TOKEN` is separate from read-only `TINVEST_TOKEN`.
- Owner Phase 3 acceptance on 2026-08-03 verified readiness, expiry/mismatch rejection, own-funds guard, exact-action isolation and kill-switch rollback with zero real submit.
- Owner Phase 4 acceptance on 2026-08-03 authorized exactly one controlled SBER LIMIT BUY:
  - one broker submit;
  - `EXECUTION_REPORT_STATUS_FILL`;
  - 1/1 lot at 280.55 RUB;
  - commission 0.84 RUB;
  - portfolio/operations reconciliation;
  - exact confirmation replay returned existing state and created no second submit.
- Real BUY/SELL v1 Definition of Done is complete.

### Real-money execution v1 engineering

- Issue #164 tracks the accepted staged real BUY/SELL release.
- PRs #168/#169/#170 established durable proposal state, conditional real Actions, full behavior reference and Upstash Redis journal.
- Real v1 remains limited to supported cash share/ETF, RUB, BUY/SELL, LIMIT/CURRENCY/DAY, own-funds/own-position.
- Margin/short, MARKET/BESTPRICE, derivatives/currencies, stop automation, ReplaceOrder, transfer/withdrawal and autonomous execution remain absent.
- Immutable/HMAC-bound proposal + exact owner confirmation + repeated preflight + UUID idempotency + broker reconciliation remain mandatory.
- Possible-submit ambiguity is `unknown/do-not-resubmit`; `submitted` is never treated as `filled` without broker proof.
- Missing/unreachable/tampered durable storage publishes no usable real mutation path and never falls back to ephemeral memory.

### T-Invest Sandbox execution

- PR #160 added the isolated optional Sandbox contour; PR #162 fixed verified TLS/CA transport.
- `TINVEST_SANDBOX_TOKEN` never replaces `TINVEST_TOKEN`.
- `SANDBOX_TRADING_ENABLED=false` preserves production baseline surface.
- Sandbox proposal → exact confirmation → submit with repeated limits, UUID idempotency and ambiguous-submit no-retry.
- Margin confirmation, withdrawal/transfer, auto-replace and stop automation remain absent.
- Owner Preview acceptance on 2026-08-02 covered account/funding/portfolio, BUY/SELL, rejection, replay, LIMIT state/cancel and reconciliation.
- Sandbox responses remain `real_money=false`.

### Repository state

- Repository is consolidated around one product: Omni-CIO Custom GPT + Gateway.
- `gpt/SETUP_INDEX.md` is the setup/recovery entry point.
- Current GPT Editor behavior is v8.6.1 Compact; v8.6.0 is full reference.
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` is the canonical program-status index.
- Runtime dependencies `app_v371.py`, `app_v360.py` and `main.py` remain intentionally because current `app.py` still imports them.

## [2026-08-02] Custom GPT v8.4.1 acceptance

- PR #146 made portfolio-management routing tool-first.
- `УПРАВЛЯЙ ПОРТФЕЛЕМ` requires `getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics` before analysis.
- Exact-action requests remain isolated.
- Recommended model was fixed as Thinking 5.6.
- Canonical endpoint: `https://omni-cio-gateway.onrender.com`.
- User-visible timezone: Europe/Moscow / MSK.
- Market gate blocks exact personalized sizing without fresh best ask / market readiness.
- Production Knowledge set: exactly 10 files.

## [2026-08-01] Gateway v3.10.0 baseline

- Read-only Gateway surface stabilized at 14 GET Actions.
- Added private read-only `getFinalDecisionReview` contract.
- Preserved Bearer protection, masked account output and `app:app`.
- Portfolio, market, liquidity, operations, purchase-capacity and broker-report workflows are covered by Regression Shield.
- Security baseline uses pinned/hash-locked locks, lint/type/tests/coverage, dependency audit, SAST and secret scan.

## Historical note

Full engineering history is available in Git commits/issues/PRs. Old versions are not current configuration instructions and must not replace `main`, `README.md`, `knowledge/16_CURRENT_PROGRAM_STATUS.md` or `gpt/SETUP_INDEX.md`.
