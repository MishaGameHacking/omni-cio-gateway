# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-09-23

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCKS A–E COMPLETE / WP0–WP22A COMPLETE / ACCEPTED IMPLEMENTATION 54% / AMENDMENT 18 ACCEPTED ON MAIN VIA PR #581 / CURRENT AUTHORIZED SYSTEM UPDATE TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED / TW-A ACCEPTED VIA PR #583 WITH EXACT-MAIN POST-MERGE GREEN / TW-B SOURCE-AND-RUNTIME CONSOLIDATION IN PROGRESS / WEB-VISUAL PAUSED / WP23+ LOCKED / PUBLIC USER ACTIVATION FAIL-CLOSED**.

Accepted implementation progress is **54%**.

Blocks A (5%), B (9%), C (12%), D (14%) and E (14%) have passed their owning Exit Gates. WP16–WP22 and the complete **WP22A — External Web Access / Product Authentication Security Gate** are accepted COMPLETE.

Amendment 14 remains accepted **historical evidence**, but Amendment 18 supersedes it for current/future provider selection. The complete `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED` chain remains an accepted historical baseline; its final focused CF-D hardening landed through PR #547.

Amendment 15 records the 2026-08-29 OWNER delivery correction: the four Amendment-14 Cloudflare implementation stages remain ordered and fail-closed but are executed as internal milestones of one `INTEGRATED_SYSTEM_UPDATE`, `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, on default branch `system/cloudflare-public-product`, with one final PR by default. Separate protected-main acceptance between CF-A/CF-B/CF-C/CF-D is no longer required. A real Amendment-12 split trigger discovered during implementation still forces a stop/split.

Neither Amendment 14 nor Amendment 15 by itself deploys Cloudflare, mutates DNS/domain/provider state, provisions secrets, activates public users or authorizes Real money.

`PUBLIC_MULTI_USER_ENABLED=false` remains the **current runtime state, not a V10-wide release lock**. Under Amendment 13, completed capabilities may become live as soon as their own real authentication/runtime/privacy/security/capacity/monitoring gates pass; unrelated unfinished V10 blocks are not a reason to hold a ready capability forever.

Amendment 18 is accepted on protected `main` through PR #581 and retires Cloudflare/Neon/Render/Cloud.ru/VK from current/future V10 provider authority. `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED` is the current authorized System Update. WEB-VISUAL and WP23+ remain paused until the consolidation/public-activation path reaches its owning exit gate.

PR #582 remains the accepted CI/provider-authority split. TW-A then completed through PR #583. Its exact reviewed head `2c4cf7915c02d05e42b269544bc0336c31fa9a87` passed DRAFT and READY certification, and PR #583 was squash-merged to exact main `c7ea5ba549e1bf8e627d61117a15ace8da6387a4`. Post-merge Regression Shield #1647, Engineering Governance #1909, all owning WP audits and Timeweb Read-Only Proof #14 completed `success`. The sanitized provider proof remains `TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY`. The observed Timeweb IPv4 remains fail-closed as `TIMEWEB_IPV4_ORPHAN_PROVENANCE_REQUIRED`; it grants no ingress mutation authority.

TW-A / INVENTORY_AND_AUTHORITY is therefore `CERTIFIED_GREEN / ACCEPTED`. TW-B / SOURCE_AND_RUNTIME_CONSOLIDATION is now the current branch-local milestone on `system/timeweb-platform-consolidation-tw-b`. Focused CA-trust repairs PR #585 and PR #586 were subsequently accepted on protected `main`; the current accepted base for TW-B is exact main `26bdc17c4e5d68c262f47b999e975b1eb8651858`. The branch includes that base with no behind commits at the latest verified checkpoint; its exact head is resolved from PR #584 rather than frozen in this status file. TW-B may change source/runtime composition only; it does not authorize Timeweb production deployment, PostgreSQL production cutover, DNS/TLS cutover, public Telegram activation, broker write or Real-money execution.

TW-B remains `RED_REPAIR_ONLY` until one coherent source-correction batch and the OWNER machine-boundary gate are re-certified. The latest exact-head evidence before that correction showed: Fast PR failed only two changed-file Ruff formatting checks; the authoritative Windows suite reached 3695 passing tests, 912 subtests and 62.20% coverage with one Timeweb synthetic-create runbook marker failure; Sonar Quality Gate passed with zero Security Hotspots but reported one maintainability issue in the Timeweb inventory transitive-consumer validator; and the WP17 OWNER Read Vault audit remained fail-closed on `WP17_OWNER_EVIDENCE_HEAD_DRIFT` with `owner_evidence_ready=true` and direct permission probes intentionally not executed. The repository-side correction must fix those source defects, make the Timeweb inventory governance run read and structurally validate the complete discovered repository tree, and then freeze the replacement head before OWNER evidence is rebound. No Timeweb provider mutation, production DB/DNS cutover, public Telegram activation, broker write or Real-money authority is introduced.

Pre-correction exact-head evidence on `89fb19cf131c509bd2ef49c1eaaa8d7e0ccf868b` proves the whole-repository integrity pass is operational: Engineering Governance read all 1,723 discovered repository files, classified 1,693 as text and 30 as binary, structurally parsed 919 Python and 80 JSON files, and completed `V10_TIMEWEB_PLATFORM_INVENTORY=PASS`. Fast PR and authoritative Windows then independently stopped only on Ruff formatting of that verifier; functional frontend/WP lanes and Engineering Governance itself were successful. The same head's WP17 audit remained correctly blocked by `WP17_OWNER_EVIDENCE_HEAD_DRIFT`. A replacement source head must rerun all exact-head evidence; prior GREEN is not carried forward.

Official Timeweb App Platform documentation was rechecked on 2026-09-23. The existing TW-B source already matches the applicable source constraints: root Dockerfile deployment with `EXPOSE 8080`; process-only `/livez` for platform liveness and DB-aware `/healthz`; external PostgreSQL persistence rather than container-local state; runtime variables/secrets outside Git/image metadata; and an explicit deferred decision for App Platform private-network selection because Timeweb documents that this choice is made at application creation and cannot be changed in place. These are source/planning constraints only; TW-C/TW-D remain the provider-mutation/cutover gates.

Correction head `7ec4a8bf9bb3b02cb8d4571389938def6f17be61` removed the first stale probe and strengthened inventory discovery, then Engineering Governance #1895 correctly failed with `TIMEWEB_CONSOLIDATION_ACTIVE_WORKFLOW_RETIRED_PROVIDER_EXECUTION`: the historical WP22A Phase-5 technical-closeout workflow was a second neutral-name consumer that still compiled and live-ran the same Render Phase-4 probe. Repository search shows these Phase-4 and Phase-5 workflows are the complete Actions consumer set for that retired probe. Both must be archive-in-place/manual hard-disabled before the TW-A checkpoint can be certified.

Exact head `b8c00434d6669dff4fc05d0a0f2576b358b24c0e` then passed the strengthened retired-workflow authority guard but the new inventory guard failed on an internal classification mismatch: `apps/api/cf_d_database_bootstrap.py` remains an active transitive dependency of `hosted_preview.py` and is therefore correctly `TIMEWEB_REPLACE`, not `HISTORY`. The correction keeps that producer in replacement scope until TW-B detaches it; the two retired hosted-acceptance workflows remain historical archive-only.

Exact head `0a4727d3de7329fdeb21274badc364b2dba6b462` passed both strengthened Timeweb authority and provider-inventory guards and compiled the guard set. Its remaining Engineering Governance RED was limited to `tests/test_v10_wp22a_historical_gate_routing.py`, whose old assertions still required the Phase-4/Phase-5 `pull_request.paths` triggers that Amendment 18 now forbids. That regression must be inverted to require archive-only/manual hard-disabled routing; this does not reopen any retired provider authority.

Exact head `d438ce4cd3cf98d1a7cdaee2d6cf90f0b742a030` then reached a narrower systemic RED. Engineering Governance and all observed WP/toolchain/Web lanes completed `success`; Fast PR Checks #3014 failed only because two historical-workflow reads in `tests/test_v10_ru_public_registration_ingress.py` were not in pinned Ruff layout. Authoritative Windows CI #3106 passed compile and protected static quality, then failed the unchanged tracked-content secret detector on two new entropy-shaped verifier literals: the embedded accepted-base SHA in the inventory JSON and one long Cloudflare marker literal in the guard. Sonar additionally reported duplicate-character-class warnings and a ReDoS flow because the verifier executed regular expressions supplied by the repository-controlled JSON contract. The systemic correction is to remove contract-controlled regex execution, use bounded plain-string matcher primitives, keep exact cardinality, expand executable-source hidden-consumer coverage, and structurally remove the entropy-shaped literals without suppression or secret-scan weakening.

Replacement preflight also found two previously unclassified transitive dependencies before remote certification: `apps/web/vite.config.ts` still consumes `RENDER_GIT_COMMIT`, and the active PostgreSQL runtime-role rehearsal still imports `_converge_runtime_role` from the historical Render/Neon provisioner. Both are now explicitly `TIMEWEB_REPLACE`; the current clientless workflow remains `KEEP` only because its retired-provider strings are static negative/source-evidence assertions and its separate execution guard forbids retired provider execution.

Exact head `770b42c80f395d15ab483b20c05831e386bfb510` removed the prior Sonar Quality Gate failure (0 security hotspots), but Engineering Governance #1900 then correctly stopped at `TIMEWEB_INVENTORY_UNCLASSIFIED_RETIRED_CONSUMER:.github/workflows/v10-engineering-governance.yml`. Root cause was verifier-layer conflation, not a new provider execution: the generic content scanner interpreted a static `py_compile` reference to historical provider code as a runtime dependency. The correction separates code/import consumer scanning from GitHub Actions execution scanning and strengthens the latter with direct retired provision/deploy command markers, so static historical verification remains allowed while actual retired-provider execution fails closed.

Exact head `3acb0490893dc4aed81667e5f8145ba2da645501` confirmed that workflow/source separation but exposed one final self-reference of the same class: the current Russia-ingress security guard itself contains retired provider script names as detection data. Whole-source marker enumeration found no other unclassified strong-marker consumer. The correction therefore exempts exactly the two security-verifier source files from consumer scanning while keeping the Russia-ingress execution-aware workflow guard authoritative for provider commands; this avoids broad suppression and keeps any new ordinary `KEEP` source fail-closed.

Exact head `f6ec32b10d6cf2ca39072cd89d14110ca474c140` then passed the new TW-A inventory guard and compiled governance source, but its stdlib regression found a fail-closed ordering defect in `_rule_matches`: unknown matcher keys were checked only after selector evaluation, so a non-matching valid prefix could return `False` before an injected unknown key was rejected. The correction validates the complete matcher shape before any matching operation, preserving bounded non-regex evaluation while making malformed contract input deterministically fatal.

## Amendment 18 — Timeweb-only platform consolidation / Telegram-only login

Accepted historical Cloudflare/Render/Neon chains remain evidence of what earlier code proved, but they do not remain future platform authority after Amendment 18 acceptance.

Final selected operating model:

- ChatGPT = engineering assistant only;
- GitHub = source/review/CI/release provenance;
- Timeweb Cloud = sole selected production infrastructure platform;
- Telegram Login = sole selected human product login provider.

Retirement targets are Cloudflare, Neon, Render, Cloud.ru and VK ID. External review/CI SaaS is also to be removed from the required path after equivalent-or-stronger GitHub-native checks are proven.

The active System Update is `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED`, with ordered milestones TW-A→TW-G. It delivers provider-neutral application source, Timeweb App Platform exact-SHA deployment, Timeweb PostgreSQL 18 production cutover, Timeweb DNS/TLS/no-VPN Russian ingress, Telegram-only activation, then external-provider decommission with legacy repository artifacts left archive-in-place.

No new Cloudflare/Neon/Render/Cloud.ru/VK feature work is authorized. OWNER reported on 2026-09-21 that the previous Cloudflare and Neon external resources/accounts, domains, databases, keys and secrets were manually removed. Screenshots support substantial decommission activity, but provider-side physical deletion/retention is not independently verifiable from GitHub. Cloudflare/Neon must therefore be treated as unavailable rollback targets.

Canonical-domain ambiguity is resolved: OWNER confirmed on 2026-09-21 that **`omnicio.ru`** is the canonical V10 production domain. The `omni-cio.ru` Cloudflare zone shown in the decommission screenshots is not the target production domain. Timeweb DNS/TLS and Telegram production activation remain fail-closed until their technical/provider gates pass.

Git history is not rewritten to remove old provider names. Legacy provider files remain archive-in-place by default; after cutover their live workflow/provider authority is disabled or revoked while historical provenance remains intact.

## Latest accepted Cloudflare runtime/release baseline

The final functional CF-D runtime/release baseline before this documentation-only closeout is:

`b8b27217a177d954ae1efb327b224503fd0e30b0`

It is the squash merge of PR #547, **CF-D: freeze provider secret custody on current main**, and it completes the accepted CF-D provider-secret custody hardening on top of the earlier Cloudflare/Neon convergence and recovery repairs. The exact current protected `main` SHA is always resolved from GitHub; this documentation record intentionally does not try to self-reference the future squash SHA that accepts its own closeout.

Exact-new-main acceptance on `b8b2721...` is proven by:

- Regression Shield #1617 / run `35320951393`: `completed / success`;
- V10 Engineering Governance #1607 / run `35320951440`: `completed / success`;
- the complete applicable exact-main push batch reached terminal `success`;
- V10 Cloudflare Production Release #78 / run `35321810810`: `completed / success` on the same exact main SHA;
- CF-D exact-main database-state/staging-anchor, staging rehearsal/production database-state, gated production promotion and terminal release DAG all concluded `success`;
- hosted staging and production database recovery jobs were correctly `skipped` only because their accepted reusable runtime database bindings were already ready; no required recovery outcome was suppressed;
- the exact accepted main was deployed through the gated Cloudflare Workers Build, the canonical Custom Domain was attached/verified, live production release acceptance passed, and rollback was correctly unnecessary.

This closes the implementation/recovery/security evidence chain for `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`. Issue #510 is completed. Issue #412 is the owning historical System Update dashboard; its issue lifecycle does not override this canonical accepted-state record.

Render is retired from active new-V10 deployment/alignment authority; historical WP22A Render/Neon evidence remains preserved. Protected V9 Render production/recovery and stable entrypoint `app:app` remain separate protected recovery boundaries.

## WP22A technical Exit Gate — COMPLETE

WP22A remains technically COMPLETE and Block E remains COMPLETE. The accepted technical boundary includes:

1. exactly Telegram Login and VK ID product-authentication contracts;
2. browser-bound durable one-time provider-auth transactions with state/PKCE/nonce/provider/redirect binding as applicable;
3. replay, stale, provider-mix-up and browser-swapping negatives;
4. verified external identity -> internal account -> isolated tenant -> server-side session composition;
5. opaque server-side session authority with fixation protection, bounded lifetime, logout/revocation semantics and no browser Web Storage token authority;
6. tenant scope derived only from authenticated server-side state plus PostgreSQL RLS/FORCE-RLS and cross-tenant negatives;
7. CSRF, Origin/Referer, Fetch Metadata, Host, trusted-edge/TLS, CORS, cache and security-header controls;
8. bounded request/provider abuse, rate, capacity and degraded fail-closed behavior;
9. migration/restart/redeploy/recovery/restore-isolation/rollback evidence;
10. hosted ordinary-browser/exact-release technical evidence independent of PROJECT OWNER home availability;
11. complete exact-head DRAFT/READY review chain plus exact-main Regression Shield.

Therefore:

- `wp22a_technical_gate_complete=true`;
- `wp22a_complete=true`;
- Block E is COMPLETE;
- accepted V10 implementation progress is **54%**.

### Historical WP22A hosted acceptance evidence

WP22A Phase 4/5 accepted a zero-cost synthetic Render + Neon PostgreSQL 18 proof-of-product as technical evidence. That historical chain remains valid evidence for the code/security/runtime properties it proved at the time:

- accepted implementation main `bb15739acf82ded8eafb6d006cf222fb3988770d`;
- Regression Shield run `32958019958`: `success`;
- hosted deployment run `32960260373`, attempt 2: `success`;
- fresh zero-charge OWNER attestation: `PASS_FRESH_NO_PAYMENT_METHOD`;
- Neon organization plan: `FREE_VERIFIED`;
- PostgreSQL bootstrap/migrations/runtime-role/grants/synthetic seed: PASS;
- historical Render deploy: `LIVE_EXACT_SHA`;
- historical external HTTPS exact-release probe: PASS;
- historical technical preview: `https://omni-cio-v10-web.onrender.com`.

This is **Render/Neon historical technical evidence**, not current new-V10 provider authority. Amendments 14/15 do not rewrite or delete it. Protected V9 Render production/recovery and stable entrypoint `app:app` also remain protected.

Canonical historical closeout evidence remains:

- `docs/architecture/V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.md`;
- `docs/architecture/V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.json`;
- `.github/workflows/v10-wp22a-phase5-technical-closeout.yml`;
- `docs/architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_CONTRACT.json`.

## Earlier accepted WP22A authority

- WP22A Phase 1 — **ACCEPTED** historical provider/security-selection evidence;
- WP22A Phase 2 — **ACCEPTED**: verified identity -> account -> tenant -> session and tenant/RLS boundary;
- WP22A Phase 3 — **ACCEPTED**: hosted runtime/data/secret/recovery source boundary;
- WP22A Phase 4 — **ACCEPTED**: zero-cost synthetic Render Free + Neon PostgreSQL 18 proof-of-product;
- WP22A Phase 5 — **ACCEPTED**: integrated technical browser/provider/account/tenant/session/security/recovery/abuse closeout;
- WP22A overall — **COMPLETE**.

Provider names inside those accepted historical contracts remain true historical evidence. Amendment 14 supersedes conflicting **current/future** Cloud.ru/Render provider-selection wording for new V10 work without pretending that earlier acceptance happened on Cloudflare.

## Amendment 12 — ACCEPTED governance law

Amendment 12 defines exactly two execution units:

- `FOCUSED_CHANGE` for isolated defects, governance/documentation corrections, maintenance and mandatory split boundaries;
- `INTEGRATED_SYSTEM_UPDATE` for one coherent OWNER-authorized system outcome with ordered member WP/increments.

Mandatory split triggers include DB/migration ordering, security/authority transition, dependency/toolchain boundary, OWNER/provider action, live/temporal evidence, production cutover, Real-money authority and reviewability limit.

Amendment 14 originally represented build integration, runtime compatibility, provider mutation and public cutover as four separately accepted split states. Amendment 15 explicitly supersedes only that delivery granularity for this already-selected provider transition: the same four stages remain internal ordered authority milestones CF-A…CF-D inside one integrated update. Each milestone must pass its branch-local Exit Gate before dependent work begins. A concrete mandatory split trigger still overrides the one-branch default.

The prepared visual product update remains separate:

`WEB-VISUAL-A -> WEB-VISUAL-B -> WEB-VISUAL-C -> WEB-VISUAL-D -> WEB-VISUAL-E -> WEB-VISUAL-F -> WEB-VISUAL-G`

No `apps/web` visual-refresh source is authorized by Amendments 14/15.

## Amendment 13 — progressive capability activation

Amendment 13 remains active and its activation-state vocabulary remains exactly:

`IMPLEMENTED | LIVE_OPERABLE | BLOCKED_EXTERNAL | REAL_MONEY_AUTHORIZED`.

A completed user-facing capability does not need to wait for unrelated later V10 blocks or final `V10.0.0`. It becomes `LIVE_OPERABLE` only after every gate that actually owns that capability is accepted.

A separate user-facing staging product is not required. Local/CI/provider doubles, T-Invest Sandbox and Shadow remain allowed engineering/safety contours but never become a second product or product-auth bypass.

### Current capability activation baseline

| Capability | Current activation state | Current blocker summary |
|---|---|---|
| telegram_login | `BLOCKED_EXTERNAL` | Timeweb canonical runtime/callback + Telegram secret custody + public runtime privacy/capacity/monitoring acceptance |
| public_multi_user_tenant_access | `BLOCKED_EXTERNAL` | live Telegram auth + public-user privacy/legal/capacity/monitoring + accepted Timeweb runtime/database/DNS cutover |
| tinvest_read | `BLOCKED_EXTERNAL` | `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION` + tenant secret-custody/security/privacy/live-connection acceptance |

Current user-facing activation transitions — **BLOCKED_EXTERNAL where listed above**.

Public T-Invest-backed production functionality remains **FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION**. READ/live portfolio/positions/operations are independent from unfinished Real execution, but cannot become public `LIVE_OPERABLE` until broker terms/permission and tenant secret-custody/security/privacy/live acceptance are real and accepted.

## Historical Amendment 14 — Cloudflare Platform & Continuous Release Authority — superseded by Amendment 18

Canonical accepted-on-main sources:

- `docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PLATFORM_AND_CONTINUOUS_RELEASE_AUTHORITY_AMENDMENT.md`;
- `docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json`;
- `scripts/check_v10_cloudflare_platform_authority.py`;
- `.github/workflows/v10-engineering-governance.yml`.

At Amendment 14 acceptance, the historical provider model established:

- GitHub = engineering/source/review/provenance authority rank 1;
- Cloudflare Workers Paid = managed application/edge/build platform rank 2 for new V10 work;
- Cloud.ru Evolution = no longer the selected new-V10 target;
- Render = no longer active new-V10 deployment, zero-charge attestation, hosted-release-alignment or recovery target;
- historical WP22A Render/Neon evidence and protected V9 Render `app:app` remain preserved;
- one canonical public Omni-CIO Web/product-auth/account/tenant/session stack;
- Cloudflare edge security is additive and never substitutes for product authorization or PostgreSQL tenant/RLS authority;
- existing React/Vite Web is the migration source; FastAPI/Python Workers/native dependency compatibility must be proved rather than assumed;
- Neon/PostgreSQL 18 authority stays intact until explicit equivalent migration proof; D1 does not silently replace it; Hyperdrive + PostgreSQL 18 requires compatibility evidence;
- Workers Paid included build capacity may be used only through the owning integration milestone;
- automatic paid overage or higher-plan expansion is not authorized without a fresh OWNER cost decision.

Historical Workers Builds reference values recorded by the Amendment 14 contract on 2026-08-29 remain provenance only; they do not define current Timeweb capacity or cost authority.

### Historical Cloudflare continuous exact-main release law

The formula below is preserved as historical Amendment-14/15 provenance only. It is **not** the current deployment path after Amendment 18; current release authority is GitHub -> exact Timeweb candidate -> accepted Timeweb production promotion.

Historical flow:

`exact-head PR GREEN/review -> squash merge -> exact-main post-merge GREEN -> immutable Cloudflare candidate -> candidate acceptance -> production promotion`

Before promotion the pipeline re-checks current `main`. A superseded candidate must not be promoted. If a newer `main` is not promotable, production stays on the last-known-good version and must expose `UPDATE_PENDING`, `DEPLOYMENT_BLOCKED` or `OUT_OF_SYNC` rather than silently drifting.

Public release identity is event-derived CalVer `YYYY.MM.DD.N` plus exact `source_sha`, `cloudflare_version_id`, `released_at_utc` and release status. It must not create a source-code version-bump commit solely to change the displayed release number.

Cloudflare Worker rollback does not roll back external KV/R2/D1/Durable Object state; schema/storage compatibility and rollback remain separate required evidence.

## Historical Amendment 15 — Cloudflare Public Product Integrated Delivery — superseded by Amendment 18

Canonical proposed/accepted-on-main sources:

- `docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_DELIVERY_AMENDMENT.md`;
- `docs/architecture/V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_CONTRACT.json`;
- `scripts/check_v10_cloudflare_public_product_integrated.py`;
- `.github/workflows/v10-engineering-governance.yml`.

During execution, Amendment 15 established:

- execution unit = `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`;
- execution type = `INTEGRATED_SYSTEM_UPDATE`;
- default branch = `system/cloudflare-public-product`;
- one final PR by default;
- `CF-A / CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` -> `CF-B / CLOUDFLARE-RUNTIME-COMPATIBILITY` -> `CF-C / CLOUDFLARE-CANDIDATE-DEPLOYMENT` -> `CF-D / CLOUDFLARE-PUBLIC-CUTOVER` remain mandatory ordered internal milestones;
- a milestone's branch-local Exit Gate is required before dependent milestone work;
- separate main merge/acceptance between CF-A…CF-D is not required;
- a real Amendment-12 split trigger still forces a stop/split;
- Cloudflare-first replacement is preferred only where semantically equivalent and safe;
- Cloudflare Containers are allowed only for a proven full-Linux/native dependency runtime need;
- PostgreSQL/Neon may remain where Cloudflare lacks an accepted PostgreSQL 18/RLS equivalent;
- active new-V10 Render dependencies must be retired only after replacement parity/consumer/recovery review;
- protected historical WP22A evidence and V9 Render `app:app` remain preserved;
- WEB VISUAL remains separately OWNER-locked.

## Historical post-CF-D functional authority — superseded by Amendment 18

The accepted `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED — Cloudflare Public Product System Update` is **COMPLETE**. Its ordered CF-A -> CF-B -> CF-C -> CF-D implementation/recovery/cutover chain has passed accepted-main production release evidence.

At CF-D completion, no additional functional implementation package was authorized inside the historical Cloudflare System Update.

Focused maintenance, defect repair, security/recovery hardening and documentation/governance corrections remain allowed when they are actually required, but they do not authorize a new product System Update.

At that historical checkpoint, `WEB-VISUAL-INTEGRATED` was the next prepared product package and remained **OWNER START REQUIRED**. Amendment 18 later paused it behind `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED`.

### Prepared product package — WEB-VISUAL-INTEGRATED / OWNER START REQUIRED

`WEB-VISUAL-INTEGRATED — Premium Spatial Financial OS A→G System Update` remains a prepared product update from Amendments 12/13, but Amendment 18 pauses it until the Timeweb consolidation/public-activation path reaches its owning gate.

Prepared member scope remains:

1. `WEB-VISUAL-A` — design-system foundation;
2. `WEB-VISUAL-B` — spatial shell/navigation;
3. `WEB-VISUAL-C` — Portfolio/Assets presentation;
4. `WEB-VISUAL-D` — Watchtower/Research/Risk/Decisions/Plans presentation;
5. `WEB-VISUAL-E` — Execution/Journal/System/Settings presentation;
6. `WEB-VISUAL-F` — atmosphere/optional spatial brand layer;
7. `WEB-VISUAL-G` — visual/performance/accessibility hardening.

**OWNER START REQUIRED.** The exact command remains:

`START V10 WEB VISUAL SYSTEM UPDATE`

Until that separate product execution is authorized and current sequencing is revalidated, do not create the visual-refresh implementation branch or modify `apps/web` merely for visual redesign.

## Amendment 17 — Russian PostgreSQL migration historical pre-Amendment-18 stage

Amendment 17 / RU-PG-A is accepted on protected `main` through PR #560, squash merge `4c0422a5...`, Regression Shield #1625, V10 Engineering Governance #1666 and Cloudflare Production Release #86.

Accepted implementation progress remains **54%**. This migration is a legal/security/provider compatibility prerequisite and does not add product-progress percentage by itself.

At Amendment 17 / RU-PG-A acceptance, the authorized focused stage was **RU-PG-B — provider bootstrap / synthetic PostgreSQL 18 parity**. Amendment 18 later absorbed the active provider/database transition into the ordered TW-A→TW-G consolidation path.

RU-PG-B rules:

- first candidate: Timeweb Cloud Managed PostgreSQL 18 in Moscow / MSK-1 / Terraform location `ru-3`;
- synthetic data only;
- at Amendment 17 acceptance, Neon was still production authority; Amendment 18 later superseded that current-state assumption after OWNER-reported external Neon decommission;
- no production `OMNI_V10_POSTGRES_DSN` mutation;
- no real Telegram/user/session/portfolio/broker data;
- separate bootstrap and least-privilege runtime identities are mandatory;
- the documented minimum Timeweb 1 CPU / 1 GB / 8 GB tier remains unaccepted until real provider evidence proves the identity split without weakening security;
- OWNER-selected beta target: PostgreSQL 18, Moscow, 1 CPU / 2 GB RAM / 20 GB NVMe, recorded base price 790 RUB/month as of 2026-09-19;
- the 790 RUB approval covers the base DBaaS configuration; on 2026-09-20 the OWNER separately approved one public IPv4 up to 200 RUB/month for the RU-PG-B/RU-PG-C connectivity path, while backup-storage and other paid add-ons remain unauthorized; public-IP cost approval does not bypass the owning firewall/TLS security gate;
- scale up only after capacity evidence; Timeweb documents that scale-down is not supported;
- provider credentials never belong in source, chat, PR comments, CI logs or artifacts;
- RU-PG-C remains locked until RU-PG-B is `CERTIFIED_GREEN`.


## Amendment 18 — Timeweb-only platform consolidation / Telegram-only login

Amendment 18 is accepted on protected `main` through PR #581, squash merge
`e8e583f366bb314ef6d37e8057b90cde9a42d4f4`. Accepted implementation progress remains
**54%**; platform consolidation does not add product-progress percentage by itself.

Current exact post-merge evidence on that SHA:

- Regression Shield #1645 / run `35637878697`: `completed / success`;
- V10 Engineering Governance #1862 / run `35637878774`: `completed / success`;
- WP16–WP22A owning audits observed on the exact SHA: `completed / success`;
- legacy V10 Cloudflare Production Release #106 / run `35639134386`: `completed / failure`;
- its first failing provider step reported missing retired Cloudflare credentials and
  `CLOUDFLARE_CF_C_PROVIDER_READINESS=BLOCKED`, then exited 78 before provider mutation;
- V10 RU-PG-B Timeweb Read-Only Proof #12 / run `35639207490`: `completed / skipped`
  because its legacy upstream dependency was the failed Cloudflare release workflow.

This is a **MAIN_RED_STOP active-workflow-graph defect**, not a request to restore
Cloudflare or Neon. The accepted service model is:

`ChatGPT + GitHub + Timeweb Cloud + Telegram Login`

Current correction branch:

`system/timeweb-platform-consolidation`

The branch must archive-in-place all retired Cloudflare live workflows so they cannot
auto-trigger or mutate provider state, and must rewire Timeweb provider proof directly to
successful GitHub-native Regression Shield evidence.

Current production/platform direction:

- GitHub remains source/review/CI/exact-SHA provenance authority;
- Timeweb Cloud is the only selected V10 application/database/domain infrastructure provider;
- Timeweb Managed PostgreSQL 18 is the final relational target;
- Telegram Login is the only human login provider;
- Cloudflare and Neon external rollback are unavailable by OWNER-reported decommission;
- historical provider files remain archive-in-place and do not define active authority;
- no retired provider secret or live workflow may be required for the Timeweb path;
- `omnicio.ru` is the OWNER-confirmed canonical V10 domain;
- Timeweb App Platform candidate deployment remains blocked until TW-A/TW-B source/runtime
  and GitHub-native CI correction are exact-head GREEN;
- canonical DNS/TLS cutover remains a later split gate;
- public registration remains fail-closed until runtime/database/DNS, Telegram,
  privacy/legal/capacity/monitoring and tenant-isolation acceptance pass.

WEB-VISUAL and WP23+ remain independently paused/locked. This consolidation does not
authorize Telegram Bot product features, AI/Cortex, Guardian, broker-write or Real execution.

## Current external activation baseline — BLOCKED_EXTERNAL

Current facts:

- `PUBLIC_MULTI_USER_ENABLED=false`;
- historical Cloudflare CF-D release evidence remains immutable project provenance only;
- Cloudflare/Neon no longer provide active V10 runtime, release, database or rollback authority;
- Timeweb App Platform candidate has not yet been accepted or deployed from the current
  consolidation source branch;
- Timeweb PostgreSQL production cutover has not yet been accepted;
- Telegram Login remains the only selected human identity provider, but public activation
  remains blocked until the Timeweb runtime/domain/provider gates and privacy/legal/capacity/
  monitoring/incident requirements pass;
- VK ID remains retired from deployed product composition;
- public T-Invest remains `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`.

A capability may transition from `BLOCKED_EXTERNAL` to `LIVE_OPERABLE` only when its own
exact provider/runtime/privacy/legal/security/capacity/monitoring/broker gates are accepted.

## Broker / Real execution boundary — unchanged

Unchanged current locks:

- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no transfer/withdrawal/margin/leverage/uncovered-short authority;
- tenant READ/optional TRADE credential separation remains mandatory;
- TRADE/full-access credential is never a fallback for READ operations;
- `TRADE credential connected/verified` is not broker-submit authorization;
- `LIVE_OPERABLE` is not `REAL_MONEY_AUTHORIZED`;
- a GitHub merge, AI output, Cloudflare deployment, public release, System Update, WP22A completion or capability dashboard is never broker-submit authorization.

Real order submission may become `REAL_MONEY_AUTHORIZED` only through its later owning execution gate after representative Sandbox/Shadow evidence, immutable plan, authenticated USER approval, drift/preflight, ambiguous-submit reconciliation, kill switches and actual broker terms/permission.

Protected V9 production/recovery entrypoint remains `app:app`; its rollback boundary is untouched.

## OWNER-approved final V10 product direction

The approved final product remains one public modern multi-user Omni-CIO Web service reachable through ordinary Internet HTTPS without dependency on PROJECT OWNER home IP/Wi-Fi/router/LAN/Lenovo.

Canonical product identity remains:

`Telegram Login -> verified external identity -> OmniCIOUserAccount -> Tenant -> server-side Session -> tenant-scoped product state`

The PROJECT OWNER is an ordinary USER when using the product. GitHub/Timeweb/Windows/CI engineering authority cannot mint/select a tenant.

Initial USER access remains free:

- `BILLING_ENABLED=false`;
- `TRIAL_ENABLED=false`;
- `SUBSCRIPTION_ENFORCEMENT=false`;
- `PREMIUM_FEATURE_GATING=false`.

Future monetization remains `DEFERRED_OPTIONAL`.

## Accepted / current package state

- Block A / WP0 — **COMPLETE (5%)**;
- Block B / WP1–WP4 — **COMPLETE (9%)**;
- Block C / WP5–WP10 incl. WP9A — **COMPLETE (12%)**;
- Block D / WP11–WP15 — **COMPLETE (14%)**;
- Block E / WP16–WP22 — **COMPLETE**;
- Block E / WP22A Phase 1 — **ACCEPTED**;
- Block E / WP22A Phase 2 — **ACCEPTED**;
- Block E / WP22A Phase 3 — **ACCEPTED**;
- Block E / WP22A Phase 4 — **ACCEPTED**;
- Block E / WP22A Phase 5 — **ACCEPTED**;
- Block E / WP22A overall — **COMPLETE**;
- Block E — **COMPLETE (14%)**;
- accepted V10 implementation — **54%**;
- Amendments 14/15 Cloudflare authority — **HISTORICAL ACCEPTED EVIDENCE / SUPERSEDED FOR CURRENT-FUTURE PLATFORM SELECTION BY AMENDMENT 18**;
- Cloudflare Public Product System Update — **HISTORICAL ACCEPTED COMPLETE / ARCHIVE-IN-PLACE**;
- Amendment 18 — **ACCEPTED ON `main` VIA PR #581**;
- current authorized System Update — **TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED**;
- current source branch — **`system/timeweb-platform-consolidation-tw-b`**; the original TW-A branch was squash-merged through PR #583;
- WEB-VISUAL — **PAUSED**;
- Block F / WP23+ — **LOCKED**;
- current user-facing activation transitions — **BLOCKED_EXTERNAL where listed above**;
- broker write / Real execution — **UNCHANGED / NOT AUTHORIZED**.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1–WP4 |
| C. Node / infrastructure baseline | 12% | COMPLETE — WP5–WP10/WP9A |
| D. V10 Core and data | 14% | COMPLETE — WP11–WP15 |
| E. Omni-CIO Web Platform | 14% | COMPLETE — WP16–WP22A |
| F. Telegram | 8% | NOT STARTED — WP23 locked |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED |
| I. Personal Real Execution | 7% | NOT STARTED |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED |
| **TOTAL** | **100% planned** | **54% ACCEPTED** |

## Current next package — TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED — Timeweb-only runtime/database/DNS/Telegram consolidation

OWNER authorization is recorded by Amendment 18.

Target stack:

`ChatGPT + GitHub + Timeweb Cloud + Telegram Login`

Default source branch after Amendment 18 acceptance:

`system/timeweb-platform-consolidation`

Ordered internal milestones:

1. `TW-A` — provider/dependency inventory and authority cleanup;
2. `TW-B` — provider-neutral runtime + Timeweb deployment source + Telegram-only auth + GitHub-native quality replacement;
3. `TW-C` — exact-SHA Timeweb App Platform candidate;
4. `TW-D` — Timeweb PostgreSQL 18 production cutover;
5. `TW-E` — Timeweb canonical DNS/TLS and Russia no-VPN acceptance;
6. `TW-F` — Telegram public registration/multi-user activation after legal/privacy/capacity gates;
7. `TW-G` — external-provider decommission proof and active-authority cleanup while historical repository artifacts remain archive-in-place.

WEB-VISUAL remains paused. WP23+ remains locked. No broker-write or Real-money authority changes.

Amendment-12 mandatory split triggers remain stronger than the one-branch preference. Production DB cutover, DNS/public cutover, destructive provider deletion, OWNER/legal actions and recovery boundaries require independent acceptance.

## Canonical authority

Mandatory current sources include:

- `AGENTS.md`;
- `README.md`;
- `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` for protected V9 runtime state;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`;
- `docs/master-plan/OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_LIVE_USER_OPERABILITY_AND_PROGRESSIVE_CAPABILITY_ACTIVATION_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PLATFORM_AND_CONTINUOUS_RELEASE_AUTHORITY_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_DELIVERY_AMENDMENT.md` when Amendment 15 is accepted;
- `docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json`;
- `docs/architecture/V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json`;
- `docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json`;
- `docs/architecture/V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_CONTRACT.json` when Amendment 15 is accepted;
- `docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md`;
- `docs/updates/V10_CAPABILITY_ACTIVATION_LEDGER_TEMPLATE.md`;
- `docs/architecture/V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.md`;
- `docs/architecture/V10_WP22A_PHASE5_PUBLIC_HOSTED_ACCEPTANCE_CONTRACT.json`;
- `docs/architecture/V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md`;
- accepted active amendments and protected V9/security/recovery contracts.

GitHub remains engineering source of truth. Historical PR text, old screenshots, Cloudflare dashboard state or earlier package-local status headings do not override accepted `main` and this canonical status.

## Permanent safety / rollback invariants

- protected V9 deployment entrypoint remains `app:app`;
- protected V9 service and rollback remain available;
- `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain current protected defaults until the owning execution/Real-money gate explicitly changes them;
- `PUBLIC_MULTI_USER_ENABLED=false` remains the current fail-closed runtime state until all remaining capability-specific authentication/multi-user external gates required for a transition are accepted;
- no broker-write expansion without `REAL_MONEY_AUTHORIZED` owning evidence;
- no transfer/withdrawal/margin/leverage/uncovered-short authority;
- no cross-tenant authority expansion;
- no real broker/Telegram/Timeweb/provider secret values, encryption/recovery keys, private portfolio payloads or full account IDs in GitHub/CI/artifacts/chat;
- no paid Timeweb capacity/add-on expansion beyond currently accepted resources without exact current cost revalidation and explicit OWNER approval;
- RED is RED; skipped/queued/pending/neutral is not applicable-gate PASS;
- exact-head applicable GREEN + zero blockers + squash merge + required post-merge Regression Shield remains mandatory;
- OWNER physical/secret/legal/provider evidence is never synthesized.

## Current next action

1. finish TW-B exact-head verification only on `system/timeweb-platform-consolidation-tw-b`, based on accepted main `26bdc17c4e5d68c262f47b999e975b1eb8651858`;
2. provider-neutral HTTP/PostgreSQL primitives, Timeweb hosted runtime, process-only `/livez`, database-aware `/healthz`, provider-neutral PostgreSQL/recovery/readiness contracts and Telegram-only current auth composition are implemented branch-locally;
3. current Timeweb runtime/proof no longer imports historical Render/Neon/Cloudflare/Cloud.ru/VK provider wrappers, and the provider inventory has no explicit `TIMEWEB_REPLACE` source consumer remaining;
4. deployed source identity is server-validated from `OMNI_V10_RELEASE_SHA`; browser build-time fallback metadata is not release authority;
5. keep `PUBLIC_MULTI_USER_ENABLED=false`, `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`, broker write OFF, `trading_methods=false` and `REAL_TRADING_ENABLED=false`;
6. publish one DRAFT PR only from the reviewed TW-B branch, require all applicable exact-head checks to complete `success`, then perform READY verification on the unchanged exact head;
7. TW-C provider mutation/App Platform candidate deployment remains forbidden until TW-B is `CERTIFIED_GREEN / ACCEPTED`.
