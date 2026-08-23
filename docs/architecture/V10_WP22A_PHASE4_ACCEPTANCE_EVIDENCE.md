# Omni-CIO V10 — WP22A Phase 4 Acceptance Evidence

Status: **PROPOSED ACCEPTANCE / EFFECTIVE ONLY AFTER EXACT-HEAD GREEN MERGE**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**

## Purpose

This record closes the Phase-4 zero-cost synthetic Render + Neon proof only if the transition PR containing this file completes every applicable exact-head DRAFT and fresh READY check with `success`, including the dedicated read-only public acceptance gate, has zero unresolved blocking review threads, and is squash-merged.

It does not accept Phase 5, unlock WP23, enable public multi-user product use, authorize broker write/Real execution, authorize real broker credentials/private portfolio data, or authorize paid Cloud.ru production resources.

## Accepted source and provider-recovery chain

Phase 4 was delivered and repaired through focused increments rather than one speculative rewrite:

1. PR #357 — initial zero-cost Render Free + Neon PostgreSQL 18 synthetic preview implementation — exact main `9814ce151c713711c33c9ee5026f34a6e11255cd`;
2. PR #359 — Frankfurt preview project selection — exact main `21c055a9f9abc1596c4f883801ee75ebd185b32f`;
3. PR #360 — Neon active-region response parsing — exact main `96154892e39f72f3d647aea089d44a3d000a112c`;
4. PR #364 — accepted-main provisioner import-root correction — exact main `4e10a04376523248cba8d5fa2ec8288de345e1e9`;
5. PR #366 — PostgreSQL 18 runtime-role bootstrap semantics and sanitized stage diagnostics — exact main `3e6a50801e2ac8c75ab872a64d100a9a9424bc06`;
6. PR #368 — Render-assigned public hostname authority — exact main `3aa41fdad9057ad1ca50b32ab5b03f7e4438fbf9`;
7. PR #369 — idempotent existing PostgreSQL runtime-role retry — exact main `38f79cd5425bda1e745bb61a3eb560671db4ee8e`;
8. PR #370 — attempt-correlated secret-safe Render terminal diagnostics — exact main `60ced8498bd6ce64bdbbe04a63eed706d37098a6`;
9. PR #376 — Render startup privilege correction keeping startup read-only under the least-privilege runtime role — exact main `4dd5cf123726a76a08424f5376db5b6b10ba5a31`;
10. PR #378 — unavailable CircleCI provider retirement and migration of real PostgreSQL-18 creator/bootstrap/retry evidence into the existing authoritative Windows gate — exact main `227296afe94212c1ca54b291edfb35740940e0b8`;
11. PR #379 — shared mobile-shell canonical token repair plus deterministic CSS-token and 360px overlay-ownership regression evidence — exact main `235ebfd386d46b74fb2428085ac233aa4494d696`;
12. PR #380 — OWNER-approved future Web visual-refresh brief only — exact main `4b8b0ce71e33c5e7b723e2f748a6fcf334bf6481`; this commit adds documentation only and does not change runtime code relative to `235ebfd386d46b74fb2428085ac233aa4494d696`.

The focused recovery chain preserves one existing React/FastAPI product rather than creating a second Web product, Core, identity system, database source of truth or broker stack.

## Provider/runtime evidence already observed

On exact main `227296afe94212c1ca54b291edfb35740940e0b8`, OWNER-supplied ordinary-browser evidence showed the public Render `/healthz` response with:

- `status = ok`;
- `release_sha = 227296afe94212c1ca54b291edfb35740940e0b8`;
- `database = READY`;
- `synthetic_preview = true`.

That evidence established that the Render service, hosted FastAPI boundary and Neon PostgreSQL 18 runtime were live together. The same OWNER browser session exposed a mobile presentation defect; the defect was not ignored or declared accepted.

PR #379 then repaired the shared shell token drift. Its unchanged-head READY cycle completed all 14 applicable GitHub workflows `success`, including `Self-Hosted Windows CI` #1930, `V10 Toolchain Compatibility` #1873, WP16 #1322 and WP17 #1293. The WP17 gate re-executed responsive browser evidence plus Web typecheck/lint/test/build and dependency audit. Gitar approved the final focused three-file change, both review findings were resolved, unresolved review threads were zero, and Sonar Quality Gate passed with zero new issues/security hotspots.

After PR #379 landed, OWNER ordinary-browser observation confirmed that the corrected public shell was materially improved. No real broker credential or private portfolio/account payload was used for that observation.

## Exact final public acceptance gate

Historical browser evidence is not used as a substitute for exact-main release evidence. This transition therefore adds a dedicated read-only gate:

`.github/workflows/v10-wp22a-phase4-public-acceptance.yml`

The gate runs without provider/broker/private-data secrets and is bound to the exact PR base main encoded in `V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.json`.

Before this transition may merge, it must prove against the provider-returned public preview hostname:

- HTTPS only and the exact expected Render preview host;
- `GET /healthz` returns HTTP 200;
- `status = ok`;
- `release_sha` equals exact accepted runtime main `4b8b0ce71e33c5e7b723e2f748a6fcf334bf6481`;
- `database = READY`;
- `synthetic_preview = true`;
- `Cache-Control` contains `no-store`;
- `Strict-Transport-Security` contains `max-age=31536000`;
- `GET /` returns the expected Omni-CIO HTML application shell;
- no response body or provider/private credential is copied into CI diagnostics.

A timeout, DNS/TLS failure, unexpected HTTP state, stale release SHA, database-not-ready state, missing synthetic marker, header drift or ordinary-shell mismatch keeps this transition RED. It is not converted to documentation-only acceptance.

## Zero-cost and authority evidence

The accepted Phase-4 boundary remains:

- Render Free preview service `omni-cio-v10-web`;
- Neon PostgreSQL 18 Free preview database in the approved Frankfurt boundary;
- migration/bootstrap authority separated from SQL-created least-privilege runtime role `omni_cio_hosted_api`;
- no `neon_superuser`/`BYPASSRLS` runtime authority;
- runtime receives only the pooled least-privilege connection;
- public registration remains disabled;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- public T-Invest-backed production functionality remains fail-closed pending broker permission;
- broker write remains OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- protected V9 `app:app` service/rollback remains untouched;
- recurring authorized infrastructure cost remains `0 RUB/month` / `0 USD/month`;
- no payment/card charge or automatic paid fallback is authorized.

## Phase-4 acceptance boundary

If and only if the exact-head transition PR completes the public acceptance gate plus all ordinary repository gates and is accepted on protected `main`, **WP22A Phase 4 is accepted**.

That acceptance proves the zero-cost synthetic proof-of-product and its exact release/readiness/browser boundary. It does not imply real public-user production acceptance.

Phase 5 still owns:

- normal USER Telegram/VK login binding into the internal account/tenant model;
- normal USER login/logout/session rotation/revocation acceptance;
- real deployed cross-tenant isolation negatives over all applicable private surfaces;
- public-hosted recovery/replacement-runtime and availability evidence;
- measured abuse/rate/capacity controls;
- normal public HTTPS reachability independent of OWNER home infrastructure;
- the Cloud.ru Evolution production apply/cost/legal decision where required;
- sanitized OWNER browser confirmation only for genuinely non-delegable product acceptance facts.

The OWNER-approved `docs/architecture/V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md` remains planning authority only. This Phase-4 acceptance does not authorize its runtime/CSS/TSX implementation.
