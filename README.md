# Omni-CIO — V10 active development program / V9 migration source

Omni-CIO is one investment platform. V10 is the single forward product/runtime line. The accepted V9 repository target `b9e4fabcb54f8f6e0ba206f030c35f2fafa2ce62` is a **V9 migration source** already contained in the current main lineage, not a stale branch that should be merged again.

Current V10 progress and current/next execution authority are defined only by `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## Current V10 snapshot

Repository-front-door snapshot of accepted/current program authority:

- accepted V10 implementation progress: **54%**;
- Amendment 16 governs Green Checkpoint / targeted CI repair; `RED_REPAIR_ONLY` and `CERTIFIED_GREEN` remain mandatory execution states;
- WP0–WP22A remain accepted COMPLETE;
- historical Cloudflare/Render/Neon work remains evidence only;
- OWNER target operating model: **ChatGPT + GitHub + Timeweb Cloud + Telegram Login**;
- current next package: **TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED**;
- Timeweb Cloud is the sole selected future/current V10 production infrastructure target after Amendment 18 acceptance;
- Timeweb Managed PostgreSQL 18 is the final relational target;
- Telegram Login is the only selected human login provider; VK ID is a retirement target;
- Cloudflare, Neon, Render and Cloud.ru are retirement targets; no new feature authority is granted to them;
- GitHub-native verification is the active quality/security authority; external CI/review SaaS is historical and not required for current/future V10 work;
- public multi-user and capability activation remain fail-closed until their Timeweb/Telegram/privacy/legal/capacity gates pass;
- WEB-VISUAL remains paused during platform consolidation; WP23+ remains locked;
- broker-write / Real-execution authority remains unchanged;
- `trading_methods=false`, `REAL_TRADING_ENABLED=false` and tenant/RLS protections remain intact;
- PR #584 now contains the OWNER-approved V9→V10 convergence sequence `V9C-A` through `V9C-F`; no merge to `main` is authorized without a new explicit OWNER instruction.

This box is not a second progress ledger. Exact state is only `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## V9→V10 convergence inside PR #584

Current branch-local checkpoint is `V9C-B / DETERMINISTIC_SOURCE_RELOCATION`. `V9C-A` is branch-local `CERTIFIED_GREEN` on exact head `7b325d7805e4c9b4c571d85d33ebd4875f060d35` (18/18 repository workflows `success`). Remaining deterministic V9 root engines are being relocated into canonical `omni_cio/` packages without financial-semantic rewrite; root implementation paths are removed only after consumers, verifier ownership and parity guards move with them. Runtime-wrapper/provider/GPT retirement remains gated by V9C-C/V9C-D. Git history remains the historical archive.

A stale `v9/*` branch merge is explicitly forbidden: the accepted V9 target is already an ancestor of current main.

## Current platform authority — GitHub + Timeweb + Telegram

Target deployment path:

`accepted GitHub main SHA -> GitHub checks -> exact Timeweb candidate -> Timeweb production`.

Timeweb owns the target App Platform runtime, PostgreSQL 18, domain/DNS/TLS, backups/monitoring and network controls. ChatGPT is an engineering assistant, never production authority. Telegram is identity only.

Final ordinary-user path:

`Russian browser -> omnicio.ru -> Timeweb -> Omni-CIO -> Timeweb PostgreSQL`.

Cloudflare must not remain an unavoidable final hop. Neon must not remain the final DB. VK ID must not remain a product login path.

The historical Cloudflare section below is retained temporarily as migration provenance and is superseded for future provider selection by Amendment 18.

## Historical Cloudflare platform / continuous release authority — superseded for future work

At Amendment 14 acceptance, the historical model selected GitHub as source/review/provenance authority and Cloudflare Workers Paid as the new-V10 managed application/edge/build target. Amendment 18 supersedes that provider selection; this section is provenance only.

Historical implementation assumptions were:

- the purchased Workers Paid baseline could be used only inside the then-authorized CF milestones;
- GitHub/Lenovo CI remained authority until the historical CF-A verifier milestone proved its portable lane;
- existing React/Vite Web remained the migration source and backend/native compatibility had to be proved;
- Containers, Hyperdrive and Cloudflare security/edge services were conditional options inside that historical plan;
- Neon/PostgreSQL 18 tenant/RLS authority remained in force until a separately accepted migration;
- provider deployment/release never granted broker-write or Real-money authority.

The historical Cloudflare candidate/promotion formula remains preserved in Amendment 14 and archived release contracts; it is intentionally not repeated in this live front-door guidance to prevent accidental reuse. The current Timeweb release flow defined above is authoritative. Historical CalVer/Cloudflare version metadata remains provenance only.

## Integrated System Update Execution Law

Amendment 12 defines two execution units without changing the Master Plan block/WP dependency order:

- `FOCUSED_CHANGE` — a genuinely isolated defect, governance/documentation correction, maintenance item or mandatory split boundary;
- `INTEGRATED_SYSTEM_UPDATE` — one coherent OWNER-authorized subsystem outcome with ordered internal WP/increment milestones, one integrated branch and one final PR by default.

Historically, Amendment 15 authorized `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED` as an `INTEGRATED_SYSTEM_UPDATE` with CF-A through CF-D internal milestones. That sequence is accepted provenance only after Amendment 18 and is not a current implementation plan.

For integrated work, internal milestones remain mandatory but are branch-local only. Accepted progress changes only after the complete integrated PR is squash-merged and required exact-main post-merge verification is GREEN.

`INTEGRATION_READY` remains the final whole-update readiness state before final landing review. Amendment 16 permits earlier logical checkpoint publication and certification; every such checkpoint must become `CERTIFIED_GREEN` before the next functional checkpoint or dependent milestone begins.

On material RED, the branch immediately enters `RED_REPAIR_ONLY`: start root-cause/blast-radius repair as soon as useful evidence exists, use same-SHA rerun only for proved unchanged-source transient infrastructure failure, and use a replacement SHA plus targeted proof and full exact-SHA recertification when repository content changes. Temporary verifier commits/PRs and `continue-on-error` fake GREEN remain forbidden.

Every `INTEGRATED_SYSTEM_UPDATE` uses:

- `docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md`;
- `.github/ISSUE_TEMPLATE/v10_integrated_system_update.yml`.

Both are working-state records only and must say `BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`.

The prepared visual update remains **OWNER START REQUIRED**. Do not create its implementation branch or modify `apps/web` merely for visual redesign during the Timeweb consolidation update.

## Product target

Final V10 product path:

```text
ordinary Russian Internet browser
        |
        v
Timeweb public HTTPS / omnicio.ru
        |
        v
Omni-CIO Web/API on Timeweb App Platform
        |
        v
Telegram Login
        |
        v
OmniCIOUserAccount -> Tenant -> server-side Session
        |
        v
Timeweb PostgreSQL 18 / tenant-scoped private state
```

PROJECT OWNER home connectivity and VPN are not allowed to be required production dependencies.

PROJECT OWNER is an ordinary product USER. Engineering access to GitHub/Timeweb does not create product tenant authority.


One account owns one isolated tenant in the baseline. Tenant scope is derived from authenticated server-side sessions, not client-supplied user/tenant IDs. PostgreSQL RLS/FORCE-RLS and cross-tenant negatives remain mandatory.

Public broker credentials remain tenant-owned `BrokerConnection` credentials. There is no shared/global user broker token: no shared/global user broker token is allowed.


Cloudflare/Neon/Render/Cloud.ru/VK working-tree artifacts are migration/retirement inputs under Amendment 20, not current implementation authority. New code must not depend on them; artifacts with zero current consumers may be removed at their owning V9C-D/V9C-E gates while Git history remains the archive.

Public activation still requires Timeweb runtime/database/DNS acceptance plus Telegram, privacy/personal-data, capacity, monitoring and production-security gates.

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
| Green Checkpoint / targeted CI repair law | `docs/master-plan/OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md` |
| Green Checkpoint machine contract | `docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json` |
| Green Checkpoint runbook | `docs/operations/V10_GREEN_CHECKPOINT_CI_RUNBOOK.md` |
| Documentation authority/lifecycle | `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md` |
| Long-lived project context | `knowledge/00_PROJECT_MASTER_CONTEXT.md` |
| Current V9 runtime/applied state | `knowledge/16_CURRENT_PROGRAM_STATUS.md` |
| Current V10 progress / current execution authority | `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` |
| V10 scope/sequence lock | `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md` |
| V10 canonical base program | `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` |
| Active amendments / precedence | `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` |
| Cloudflare platform / continuous release authority | `docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PLATFORM_AND_CONTINUOUS_RELEASE_AUTHORITY_AMENDMENT.md` |
| Cloudflare integrated public-product delivery | `docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_DELIVERY_AMENDMENT.md` |
| Cloudflare machine authority contract | `docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json` |
| Integrated Cloudflare update contract | `docs/architecture/V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_CONTRACT.json` |
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

This is the protected V9 production/recovery baseline, not current new-V10 provider authority. New V10 Render deployment is forbidden. The former V10 Cloudflare cutover remains historical accepted evidence only. Current/future V10 public deployment authority is Timeweb under Amendment 18.

## V10 development law

Use the current execution unit from accepted authority:

`restore authority -> FOCUSED_CHANGE or OWNER-authorized INTEGRATED_SYSTEM_UPDATE -> one logical checkpoint -> focused preflight/root-cause/blast-radius/coupled-surface review -> publish exact checkpoint SHA -> GitHub-native CI/security/review -> RED_REPAIR_ONLY on any material RED -> targeted proof -> replacement SHA if content changed -> full exact-SHA recertification -> CERTIFIED_GREEN -> next functional checkpoint -> final Files changed/review -> squash merge -> exact-main post-merge verification -> status -> next authorized execution unit`.

Do not start Telegram, AI, Real execution or later packages out of sequence. Do not call RED, skipped, queued or pending GREEN. Do not synthesize OWNER physical evidence. Do not create a second Web App/repository/Core/broker stack.

The WP22A technical gate is complete only through its accepted evidence chain. Amendments 14/15 do not reopen it, fabricate public production, expand broker-write authority or start WP23.

WP22A technical closeout is accepted only through its own dedicated technical-closeout evidence chain; it does not itself activate public production, expand broker-write authority or start WP23.

## Protected V9 boundaries

V9 remains owner-accepted controlled maintenance/recovery until an explicit V10 parity/decommission gate safely replaces it. Stable entrypoint remains `app:app`; protected rollback remains available. `START V10`, Amendment 12/13/14/15/16, an internal milestone, AI output, a GitHub merge or provider deployment is never broker-submit authorization.

## Recovery / safety

`REAL_TRADING_ENABLED=false` remains the master Real-money kill switch until its owning future activation gate. `trading_methods=false` remains protected. `PUBLIC_MULTI_USER_ENABLED=false` remains the public activation kill switch until the Timeweb/Telegram/privacy/legal/capacity activation gates and capability-specific acceptance pass. No transfer/withdrawal authority is introduced. Real broker/Telegram/VK/provider/recovery secrets, full account IDs and private portfolio payloads never belong in GitHub/CI/artifacts.
