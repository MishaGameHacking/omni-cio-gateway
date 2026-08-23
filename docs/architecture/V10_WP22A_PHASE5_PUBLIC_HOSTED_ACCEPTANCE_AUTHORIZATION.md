# Omni-CIO V10 — WP22A Phase 5 Public-Hosted Acceptance Authorization

Status: **AUTHORIZED ON PHASE-4 ACCEPTANCE / SOURCE + ACCEPTANCE WORK ONLY / PROVIDER COST APPLY STILL FAIL-CLOSED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**

## Purpose

This contract authorizes the next focused WP22A increment only after the Phase-4 acceptance transition containing this file is accepted on protected `main`.

Phase 5 converts the synthetic hosted proof into a rigorously accepted public-hosted product boundary. It does not start WP23 Telegram Bot Foundation, AI/Cortex, broker write or Real execution.

The normal product path remains:

`ordinary Internet browser -> public HTTPS -> Omni-CIO Web/API -> Telegram Login or VK ID -> verified external identity -> OmniCIOUserAccount -> Tenant -> server-side Session -> tenant-scoped product state`

Provider/GitHub/Windows/CI authority remains outside product identity. The PROJECT OWNER is an ordinary product USER when using Omni-CIO.

## Accepted prerequisite

Phase 4 may be treated as accepted only through `V10_WP22A_PHASE4_ACCEPTANCE_EVIDENCE.md` plus its machine-readable contract and the exact-head public acceptance workflow. The transition is invalid if that gate is RED, stale, skipped, neutral, queued, cancelled or bound to a different base SHA.

## Authorized Phase-5 work

Phase 5 may implement and verify only the public-hosted acceptance/security/recovery surface needed to close WP22A:

1. real public HTTPS reachability from ordinary supported phone/desktop browsers without OWNER home infrastructure as the availability anchor;
2. Telegram Login and VK ID product-auth integrations limited to verified external-identity -> internal-account binding;
3. server-side session creation, fixation protection, rotation, bounded idle/absolute lifetime, logout and revoke-all behavior;
4. tenant scope derived only from authenticated server-side session state;
5. deployed cross-tenant negatives for private records, jobs, queues, caches, notifications, exports and applicable recovery surfaces;
6. tenant-scoped broker-connection custody contracts while public T-Invest-backed functionality remains independently fail-closed unless broker permission is accepted;
7. deployed health/readiness, restart/replacement-runtime and restore verification with tenant isolation preserved;
8. measured rate/abuse/capacity controls and degraded-mode behavior;
9. security headers, cache/privacy behavior, origin/CSRF/CORS/Host/trusted-proxy boundaries;
10. deterministic browser acceptance at canonical responsive viewports plus any genuinely non-delegable OWNER product confirmation;
11. exact release provenance, rollback and post-merge Regression Shield evidence;
12. current provider/SKU/cost/legal revalidation immediately before any production provider mutation.

## Production-provider and cost boundary

The selected final production provider remains **Cloud.ru Evolution**.

This authorization does **not** pre-authorize a paid Cloud.ru purchase or recurring spend.

Current recurring infrastructure authorization remains:

- `0 RUB/month`;
- `0 USD/month`;
- no payment/card charge by implication;
- no automatic paid overage;
- no silent paid fallback.

Before any Cloud.ru production apply that would create a recurring paid commitment, engineering must:

1. revalidate the exact current Cloud.ru SKU/region/price and free/bonus eligibility from official provider information;
2. prove the smallest topology that satisfies the accepted security, private-networking, PostgreSQL, recovery and measured-capacity requirements;
3. state the exact recurring cap and deletion/shutdown path;
4. obtain explicit OWNER approval for that cost commitment when the resulting amount is above the currently authorized zero-cost cap.

If a safe free/bonus path cannot satisfy Phase 5 and payment is required, stop at `OWNER_ACTION_REQUIRED`; do not weaken topology/security to remain free and do not add a card automatically.

## Identity and session boundary

Telegram/VK provider identity is authentication input only. It must never become a tenant identifier or engineering/admin bypass.

Required product-auth properties:

- verified provider callback/assertion validation;
- exact external identity binding to one internal account according to accepted conflict/link policy;
- no client-supplied tenant selector as authorization;
- opaque high-entropy server-side session identifier;
- `Secure`, `HttpOnly`, correctly scoped `SameSite` cookies;
- no auth/session/refresh token in browser Web Storage;
- session rotation on authentication and privilege-sensitive lifecycle transitions;
- bounded idle and absolute expiry;
- explicit logout;
- revoke-all-sessions;
- CSRF and same-origin enforcement for state-changing browser requests;
- fail-closed behavior for invalid, replayed, stale, contradictory or ambiguous identity/session state.

## Tenant and private-data boundary

A normal USER may access only that USER's tenant. Acceptance must include deterministic and deployed IDOR/cross-tenant negatives where applicable.

No OWNER/provider/GitHub/CI identity may mint or select a product tenant.

Raw broker credentials:

- are USER/tenant owned;
- are never returned to the browser after submission;
- are never stored in browser Web Storage;
- never enter GitHub, CI logs, artifacts or screenshots;
- remain encrypted/opaque inside the accepted tenant-scoped custody boundary;
- remain unusable by another tenant.

## Broker/legal boundary

Public site/account/tenant acceptance and public T-Invest-backed functionality are separate gates.

Until accepted broker/partner permission or another explicitly accepted compliant architecture exists:

- public T-Invest-backed functionality remains `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`;
- no public retransmission claim is made;
- broker write remains OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- transfer/withdrawal/margin/uncovered-short authority remains forbidden.

## Activation boundary

`PUBLIC_MULTI_USER_ENABLED=false` remains the safe default while Phase 5 work is in development.

It may change only inside a focused Phase-5 activation increment whose exact-head acceptance proves all owning auth/session/tenant/privacy/recovery/capacity/legal gates. Enabling the flag is not itself evidence that those gates passed.

Initial USER access remains free:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`.

## Web visual-refresh boundary

The OWNER-approved design specification exists at:

`docs/architecture/V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md`

It remains **planning-only** during this Phase-5 authorization unless a later accepted canonical status/amendment explicitly authorizes a named visual-refresh increment in sequence. Phase 5 must not silently absorb a large visual redesign into auth/provider/recovery acceptance work.

If and when that visual-refresh increment is explicitly authorized, its implementation must reuse the existing `apps/web` product and follow the brief rather than creating a competing frontend/design stack.

## Explicit non-goals

Phase 5 must not:

- start WP23 Telegram Bot Foundation;
- start AI/Cortex WPs;
- enable broker write or Real execution;
- create a second Web App/API/Core/identity/database/broker stack;
- treat Render/Cloud.ru/GitHub/Windows identity as product authentication;
- expose real secret/private payloads in source, CI, logs, screenshots or artifacts;
- make Lenovo/home Internet the public production availability anchor;
- accept a paid provider commitment without the required OWNER cost decision;
- claim the Premium Spatial Web redesign is authorized merely because its brief exists.

## Phase-5 Exit Gate

Phase 5 is accepted only after all applicable focused increments are merged through exact-head GREEN cycles and the final deployed product acceptance proves, at minimum:

- public HTTPS normal-browser reachability;
- verified normal USER login/logout/session lifecycle;
- deployed tenant isolation and cross-tenant negatives;
- private-data/credential custody boundaries;
- recovery/replacement-runtime/availability evidence;
- rate/abuse/capacity controls;
- exact release and rollback evidence;
- required security headers/cache/origin/session protections;
- no OWNER-home availability dependency;
- no unresolved P0/P1 or blocking review thread;
- exact-main Regression Shield GREEN;
- any genuinely non-delegable OWNER acceptance recorded without secrets;
- provider/cost/legal/broker gates truthfully classified rather than bypassed.

Only after Phase 5 acceptance may WP22A closeout determine whether WP22A is COMPLETE and whether the Master Plan can unlock WP23. This file never unlocks WP23 by itself.
