# Omni-CIO — V9 protected runtime + V10 active development program

Omni-CIO is one investment platform. The protected owner-accepted Custom GPT v9.0.0 + one production Gateway remains the current production/recovery baseline while V10 is developed sequentially in this same repository.

Current V10 progress and current/next execution authority are defined only by `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## Current V10 snapshot

Repository-front-door snapshot of accepted/current program authority:

- accepted V10 implementation progress: **54%**;
- WP0–WP22A: accepted COMPLETE according to the canonical status/evidence chain;
- **PRODUCT IMPLEMENTATION PAUSED** after the Amendment-12 governance transition;
- next prepared execution unit: **WEB-VISUAL-INTEGRATED — Premium Spatial Financial OS A→G System Update / OWNER START REQUIRED**;
- exact product START required before implementation: `START V10 WEB VISUAL SYSTEM UPDATE`;
- Amendment 12 changes delivery granularity only; it does not advance accepted product progress or runtime authority;
- WP22A technical closeout is accepted only through its Phase-5 evidence/status chain; public-production activation remains a separate fail-closed gate;
- WP23+ remains locked behind acceptance of the complete visual System Update and later Master Plan authorization;
- **public multi-user/global browser service is the approved V10 target**;
- **public Internet ingress remains OFF while the separate production-activation/security/privacy/broker/legal/capacity gates are unfinished**; technical acceptance is not production activation;
- final public production must not depend on PROJECT OWNER home IP, Wi-Fi, router/LAN, home Internet or Lenovo as the production origin;
- final public Web/API/private-state runtime must use the approved managed-cloud production boundary selected by the owning service/security/recovery gate;
- PROJECT OWNER is an ordinary product USER when using Omni-CIO; GitHub/cloud-provider/Windows authority is separate from product identity;
- initial registered-user access is free: billing, trial, subscription enforcement and premium feature gating are disabled for the initial launch;
- normal broker READ and optional TRADE credentials belong only to the authenticated tenant's `BrokerConnection`; no shared/global user broker token is allowed;
- current T-Invest public-service terms remain a separate fail-closed broker gate; user-supplied tokens do not waive broker restrictions;
- broker-write / Real-execution authority remains unchanged;
- `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, `PUBLIC_MULTI_USER_ENABLED=false` and protected V9 rollback remain intact.

This box is a concise repository front door, **not a second progress ledger**. For exact evidence and transitions read `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## Integrated System Update Execution Law

Amendment 12 defines two execution units without changing the Master Plan block/WP dependency order:

- `FOCUSED_CHANGE` — a genuinely isolated defect, governance/documentation correction, maintenance item or mandatory split boundary;
- `INTEGRATED_SYSTEM_UPDATE` — one coherent OWNER-authorized subsystem outcome with ordered internal WP/increment milestones, one integrated branch and one final PR by default.

For integrated work, internal milestones remain mandatory but are branch-local only. Accepted progress changes only after the complete integrated PR is squash-merged and required exact-main post-merge verification is GREEN.

Before first external verification publication, the integrated branch must reach `INTEGRATION_READY`: all member milestones complete, known preflight defects fixed, full diff/coupled surfaces reviewed, regression guards present and mandatory split triggers cleared.

After a verification SHA is published, **HEAD FREEZE** applies while safe independent checks reach terminal state. Findings are consolidated and grouped by root cause/blast radius before one coherent correction batch. Temporary verifier commits/PRs and `continue-on-error` fake GREEN are forbidden. A new commit invalidates prior final exact-head evidence.

Every `INTEGRATED_SYSTEM_UPDATE` uses:

- `docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md`;
- `.github/ISSUE_TEMPLATE/v10_integrated_system_update.yml`.

Both are working-state records only and must say `BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`.

The prepared visual update remains **OWNER START REQUIRED**. Do not create its implementation branch or modify `apps/web` until `START V10 WEB VISUAL SYSTEM UPDATE` is explicitly issued after Amendment 12 is accepted.

## Product target

Final V10 product path:

```text
ordinary Internet browser
        |
        v
public HTTPS / reviewed edge
        |
        v
approved managed-cloud Omni-CIO Web/API
        |
        v
product authentication (Telegram Login / VK ID)
        |
        v
OmniCIOUserAccount -> Tenant -> tenant-scoped private state
        |
        +-- tenant BrokerConnection READ credential
        `-- optional tenant BrokerConnection TRADE credential (later gated)
```

The PROJECT OWNER's home public IP, Wi-Fi, cable/fiber/mobile uplink, router/NAT/LAN and Lenovo laptop are **not** allowed to be required public-production dependencies. Lenovo remains engineering/self-hosted CI/controlled acceptance/recovery/rollback infrastructure.

One account owns one isolated tenant in the baseline. Tenant scope is derived from authenticated server-side sessions, not from client-supplied user/tenant IDs. Public activation requires API + database-enforced cross-tenant isolation, secure sessions, abuse controls, backup/recovery, privacy/personal-data, broker-terms, regulatory, capacity and production-security acceptance.

## Initial access model

Initial public USER access is fully free:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`;
- no payment method required to register/sign in.

Earlier trial/prepaid architecture remains historical/future optional planning. Monetization is `DEFERRED_OPTIONAL` and requires a later explicit OWNER-approved amendment; it does not control the initial launch.

## Broker credential model

For public V10:

`USER -> Tenant -> BrokerConnection -> READ / TRADE_OPTIONAL -> verified broker-account bindings`

A credential entered by one USER belongs only to that tenant. Raw credentials are never returned to browser storage and never enter GitHub, CI logs or artifacts. They require an approved encrypted tenant-scoped cloud secret/data boundary. Cortex, ordinary CI and unrelated tenants never receive them.

Real execution is not enabled by this planning direction. Exact same-tenant READ/TRADE account intersection, immutable-plan approval, fresh preflight, own-cash/own-position, idempotency/reconciliation and no transfer/withdrawal/margin/short safeguards remain mandatory.

## Where to look first

| Need | Canonical source |
|---|---|
| Mandatory engineering rules | `AGENTS.md` |
| Documentation authority/lifecycle | `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md` |
| Long-lived project context | `knowledge/00_PROJECT_MASTER_CONTEXT.md` |
| Current V9 runtime/applied state | `knowledge/16_CURRENT_PROGRAM_STATUS.md` |
| Current V10 progress / current execution authority | `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` |
| V10 scope/sequence lock | `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md` |
| V10 canonical base program | `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` |
| Active amendments / precedence | `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` |
| Integrated System Update Execution Law | `docs/master-plan/OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md` |
| Machine execution-unit contract | `docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json` |
| Integrated branch ledger template | `docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md` |
| USER vs PROJECT OWNER boundary | `docs/master-plan/OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md` |
| Public/free/hosted target | `docs/master-plan/OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md` |
| Machine public-hosting contract | `docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json` |
| WP22A technical acceptance | `docs/architecture/V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.md` |
| Prepared visual-refresh content authority | `docs/architecture/V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md` |
| V10 system/security architecture | `docs/architecture/` |
| Protected V9 release/recovery history | `CHANGELOG.md`, `gpt/`, `knowledge/16_CURRENT_PROGRAM_STATUS.md` |

Historical PR text, closed issues, dated WP records and old screenshots remain historical evidence and do not override accepted `main`, the current status file or later accepted amendments.

## Current production / recovery versus V10 target

Protected current V9 baseline remains:

```text
GitHub main -> Render / omni-cio-gateway (`app:app`)
                  |
                  +-- production read-only contour
                  +-- optional virtual Sandbox contour
                  `-- protected Real-execution contour (disabled by kill switch)
```

V10 does not silently replace this baseline. Public hosted V10 cutover occurs only through the responsible future accepted package/release/recovery gates.

## V10 development law

Use the current execution unit from accepted authority:

`restore authority -> FOCUSED_CHANGE or OWNER-authorized INTEGRATED_SYSTEM_UPDATE -> root-cause/blast-radius + coupled-surface preflight -> implementation/internal milestones -> INTEGRATION_READY when applicable -> one published head -> HEAD FREEZE -> all applicable exact-head checks SUCCESS -> independent review -> coherent correction batch if required -> fresh final exact-head verification -> READY GREEN -> zero blockers -> squash merge -> exact-main post-merge verification -> status -> next major System Update`.

Do not start Telegram, AI, Real execution or later packages out of sequence. Do not call RED, skipped, queued or pending GREEN. Do not synthesize OWNER physical evidence. Do not create a second Web App/repository/Core/broker stack.

The WP22A technical gate is complete only through its accepted evidence chain. Amendment 12 does not reopen it, activate public production, mutate the final provider, expand broker-write authority or start WP23.

## Protected V9 boundaries

V9 remains owner-accepted controlled maintenance/recovery until an explicit V10 parity/decommission gate safely replaces it. Stable entrypoint remains `app:app`; protected rollback remains available. `START V10`, Amendment 12, an internal milestone, AI output or a GitHub merge is never broker-submit authorization.

## Recovery / safety

`REAL_TRADING_ENABLED=false` remains the master Real-money kill switch until its owning future activation gate. `trading_methods=false` remains protected. `PUBLIC_MULTI_USER_ENABLED=false` remains the public activation kill switch. No transfer/withdrawal authority is introduced. Real broker/Telegram/VK/provider/recovery secrets, full account IDs and private portfolio payloads never belong in GitHub/CI/artifacts.
