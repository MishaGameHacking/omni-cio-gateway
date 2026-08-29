# Omni-CIO V10 — Cloudflare Public Product Integrated Delivery Amendment

**Status:** OWNER-APPROVED / EFFECTIVE ONLY WHEN ACCEPTED ON PROTECTED `main`  
**OWNER decision:** 2026-08-29  
**Execution effect:** delivery/rollout granularity for the already selected Cloudflare transition only  
**Product progress effect:** NONE by itself  
**WEB VISUAL effect:** NONE; `START V10 WEB VISUAL SYSTEM UPDATE` remains separately required

## 1. Purpose

This amendment records the OWNER decision that the already-authorized Cloudflare transition must be implemented as one coherent `INTEGRATED_SYSTEM_UPDATE` rather than four separately merged implementation branches.

The integrated update ID is:

`CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`

Default implementation branch:

`system/cloudflare-public-product`

The target outcome is one publicly reachable, protected Cloudflare-hosted Omni-CIO V10 product using the existing accepted Web/API/product-auth/account/tenant/session architecture and activating only capabilities whose own gates are real and satisfied.

## 2. Explicit supersession of Amendment 14 delivery granularity

Amendment 14 remains authoritative for GitHub/Cloudflare rank, provider selection, continuous exact-main release, security, database, cost and protected invariants.

This amendment supersedes only the requirement that these four Cloudflare stages be accepted through four separate implementation PR/main states:

1. `CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION`;
2. `CLOUDFLARE-RUNTIME-COMPATIBILITY`;
3. `CLOUDFLARE-CANDIDATE-DEPLOYMENT`;
4. `CLOUDFLARE-PUBLIC-CUTOVER`.

They become ordered internal milestones of one integrated branch and one final PR by default.

The order itself is NOT removed. Each milestone must pass its own branch-local internal gate before dependent milestone work begins. No later milestone may consume an unproved earlier boundary.

## 3. Why the Amendment-12 split triggers remain satisfied

This OWNER decision does not abolish mandatory split triggers. It changes how they are represented for this one update:

- provider/security authority was already selected and accepted by Amendment 14;
- build integration, runtime compatibility, provider mutation and cutover remain separate internal authority milestones;
- provider mutation is forbidden before the build/runtime compatibility internal gates pass;
- public promotion is forbidden before immutable candidate acceptance passes;
- database migration ordering, Real-money authority, destructive migration, unresolved OWNER-only action, or reviewability evidence may still force a later split if actually encountered;
- one huge branch is not permission to bypass a real safety boundary.

If a mandatory split trigger becomes real during implementation, record it in the Execution Ledger and stop dependent work until the required accepted state exists.

## 4. Ordered internal milestones

### CF-A — Portable verifier / repository integration

Outcome:

- machine-readable verifier/shard/impact/provenance contract;
- exact-source identity validation;
- `CHECKPOINT_FULL`, `TARGETED_REPAIR`, `TARGETED_CLEAN`, `FINAL_FULL`, `POST_MERGE` verification modes;
- work-conserving safe concurrency;
- Workers Builds included-capacity and no-paid-overage guards;
- no synthetic GREEN for quota/provider outage/missing shards;
- Lenovo retained for genuine Windows/PowerShell/ACL/PostgreSQL-native semantics.

CF-A performs no production promotion and no public-user activation.

### CF-B — Runtime and dependency compatibility

Outcome:

- existing React/Vite Web adapted to current Cloudflare Workers Static Assets/Vite path;
- backend compatibility proved with migration preference `REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`;
- Python Workers used only where current dependency/runtime evidence proves equivalence;
- Cloudflare Containers may be used on Workers Paid where a full Linux/runtime/native dependency boundary is required and cost/runtime evidence is accepted;
- accepted PostgreSQL/Neon tenant/RLS authority remains until an explicit proven migration replaces it;
- D1 does not silently replace financial/tenant truth;
- Hyperdrive + PostgreSQL 18 is not assumed compatible;
- product auth/session/tenant/security/degraded/recovery contracts remain intact.

### CF-C — Immutable Cloudflare candidate

Outcome:

- provider mutation creates an immutable candidate only after CF-A/CF-B internal gates pass;
- candidate is bound to exact source SHA/release identity;
- candidate health, browser/API/security/tenant/recovery/rollback evidence is collected;
- no superseded candidate may be promoted;
- candidate state is not itself public-user activation or broker authority.

### CF-D — Public cutover and live-operability activation

Outcome:

- canonical Cloudflare domain/DNS/TLS/routing;
- applicable DDoS/WAF/rate/Turnstile/Access controls within the actually purchased/available plan capabilities;
- runtime secret custody, logs/observability, incident/rollback and release provenance;
- production promotion only from the latest accepted promotable exact `main` candidate;
- real-user activation only for capabilities whose own provider/privacy/legal/security/capacity/monitoring/broker gates are satisfied;
- truthful `BLOCKED_EXTERNAL`, `UPDATE_PENDING`, `DEPLOYMENT_BLOCKED` or `OUT_OF_SYNC` states otherwise.

## 5. Cloudflare-first dependency policy

For new V10 infrastructure, prefer an included/appropriate Cloudflare service when it is semantically equivalent and does not weaken security, correctness, recovery or data authority.

Evaluate, do not blindly adopt:

- Workers / Static Assets for Web/edge compute;
- Containers for incompatible full Linux/native runtime needs;
- Workers Builds for portable hosted verification;
- KV for configuration/cache/non-authoritative edge data;
- R2 for blobs/exports/recovery artifacts;
- Durable Objects for justified strongly coordinated per-entity state;
- Queues/Workflows/Cron for owning async/durable/scheduled execution roles;
- Secrets/Secrets Store for runtime secret custody;
- Workers Logs/Web Analytics/Analytics Engine where appropriate for observability;
- DNS/TLS/DDoS/WAF/rate/Turnstile/Access for outer security;
- Hyperdrive only after exact database compatibility evidence.

Do not adopt a Cloudflare feature merely because it is available.

External services are removed only after an equivalent Cloudflare replacement is proven and recovery/consumer analysis permits retirement. GitHub remains engineering authority rank 1. Telegram/VK/T-Invest remain external product/provider interfaces. PostgreSQL/Neon remains permitted where Cloudflare does not provide an accepted equivalent of the current PostgreSQL 18/RLS financial truth boundary.

## 6. Render retirement boundary

No new V10 Render deployment, preview, hosted release alignment, attestation or recovery mutation is allowed.

The integrated update must identify and retire active new-V10 Render code/config/workflows/dependencies once replacement parity is proved.

Historical WP22A Render/Neon evidence and protected V9 Render `app:app` production/recovery are immutable historical/recovery boundaries and must not be deleted merely for repository cleanliness.

## 7. Public capability activation

The integrated update aims to make the current safe product publicly usable, but it may not fabricate missing external authority.

- `PUBLIC_MULTI_USER_ENABLED` may become true only when its own public-runtime/product-auth/privacy/security/capacity/monitoring gate passes in CF-D;
- Telegram Login / VK ID become `LIVE_OPERABLE` only after real provider registration/callback/secret/runtime evidence;
- T-Invest READ becomes `LIVE_OPERABLE` only after broker terms/permission and tenant secret-custody/live-connection acceptance;
- broker write remains OFF;
- `trading_methods=false` remains protected;
- `REAL_TRADING_ENABLED=false` remains protected;
- transfer/withdrawal/margin/leverage/uncovered-short authority remains forbidden;
- public deployment or USER registration never grants Real-money authority.

## 8. WEB VISUAL remains separate and locked

This integrated Cloudflare update deploys the existing accepted product presentation. It does not authorize the prepared visual refresh.

Do not start `WEB-VISUAL-INTEGRATED`, create its implementation branch, or change product source merely for visual redesign until the OWNER issues exactly:

`START V10 WEB VISUAL SYSTEM UPDATE`

## 9. Integrated execution law

The Cloudflare update follows Amendment 12 `INTEGRATED_SYSTEM_UPDATE` law:

- one integrated branch / one final PR by default;
- branch Execution Ledger and GitHub System Update dashboard required;
- internal milestones are branch-local evidence only;
- before external verification the branch must reach `INTEGRATION_READY`;
- after publication use HEAD FREEZE, consolidated findings, root-cause/blast-radius diagnosis and coherent correction batches;
- final merge eligibility requires one fresh complete exact-head applicable `FINAL_FULL`, independent review, zero blocking threads and SUCCESS-only applicable conclusions;
- squash merge only;
- exact-new-main Regression Shield and owning post-merge gates required.

## 10. Protected invariants

This amendment does not change:

- one canonical Omni-CIO product/Web/account/tenant/session line;
- protected V9 `app:app` recovery baseline;
- GitHub engineering/source/review/provenance authority rank 1;
- Cloudflare platform authority rank 2;
- PostgreSQL tenant/RLS truth requirements unless a later explicit migration is accepted;
- secret/private-data exclusion from GitHub/chat/CI/artifacts;
- exact-head SUCCESS-only merge law;
- broker/Real-money locks;
- WP23+ lock;
- WEB VISUAL OWNER START lock.

## Acceptance law

This amendment is authority only after its focused governance PR completes the normal exact-head DRAFT review, independent review, unchanged-head READY verification, squash merge and exact-new-main Regression Shield/governance acceptance.

Only after that acceptance may `system/cloudflare-public-product` begin implementation.