# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-09-25

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCKS A–E COMPLETE / WP0–WP22A COMPLETE / ACCEPTED IMPLEMENTATION 54% / AMENDMENT 18 ACCEPTED ON MAIN VIA PR #581 / CURRENT AUTHORIZED SYSTEM UPDATE TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED / TW-A ACCEPTED VIA PR #583 WITH EXACT-MAIN POST-MERGE GREEN / P1 SOURCE-RUNTIME CONVERGENCE BRANCH-LOCAL CERTIFIED GREEN ON 738d8c623d3002fd2eb312a6bce96c35bd45f75f / P2 TIMEWEB EXACT-SHA CANDIDATE BRANCH-LOCAL CERTIFIED GREEN ON ba43fa4be350340557fcf6d8532b6c089022a8ca / P3 POSTGRES18 PRODUCTION CUTOVER SOURCE MACHINERY BRANCH-LOCAL CERTIFIED GREEN ON 7a9051bf8775977b1ae1324fe6d1b460c1d21aec / P4 OMNICIO.RU PUBLIC-INGRESS SOURCE MACHINERY BRANCH-LOCAL CERTIFIED GREEN ON d2240886ba3e7484622898670ac9b37ee45a7c6c / P5 TELEGRAM PUBLIC-ACTIVATION IMPLEMENTATION ACTIVE / AMENDMENT 21 FULL PRODUCTION DELIVERY IMPLEMENTATION AUTHORIZED IN PR #584 / WEB-VISUAL PAUSED / WP23+ LOCKED / PUBLIC USER ACTIVATION FAIL-CLOSED**.

Accepted implementation progress is **54%**.

Blocks A (5%), B (9%), C (12%), D (14%) and E (14%) have passed their owning Exit Gates. WP16–WP22 and the complete **WP22A — External Web Access / Product Authentication Security Gate** are accepted COMPLETE.

Amendment 14 remains accepted **historical evidence**, but Amendment 18 supersedes it for current/future provider selection. The complete `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED` chain remains an accepted historical baseline; its final focused CF-D hardening landed through PR #547.

Amendment 15 records the 2026-08-29 OWNER delivery correction: the four Amendment-14 Cloudflare implementation stages remain ordered and fail-closed but are executed as internal milestones of one `INTEGRATED_SYSTEM_UPDATE`, `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, on default branch `system/cloudflare-public-product`, with one final PR by default. Separate protected-main acceptance between CF-A/CF-B/CF-C/CF-D is no longer required. A real Amendment-12 split trigger discovered during implementation still forces a stop/split.

Neither Amendment 14 nor Amendment 15 by itself deploys Cloudflare, mutates DNS/domain/provider state, provisions secrets, activates public users or authorizes Real money.

`PUBLIC_MULTI_USER_ENABLED=false` remains the **current runtime state, not a V10-wide release lock**. Under Amendment 13, completed capabilities may become live as soon as their own real authentication/runtime/privacy/security/capacity/monitoring gates pass; unrelated unfinished V10 blocks are not a reason to hold a ready capability forever.

Amendment 18 is accepted on protected `main` through PR #581 and retires Cloudflare/Neon/Render/Cloud.ru/VK from current/future V10 provider authority. `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED` is the current authorized System Update. WEB-VISUAL and WP23+ remain paused until the consolidation/public-activation path reaches its owning exit gate.

PR #582 remains the accepted CI/provider-authority split. TW-A then completed through PR #583. Its exact reviewed head `2c4cf7915c02d05e42b269544bc0336c31fa9a87` passed DRAFT and READY certification, and PR #583 was squash-merged to exact main `c7ea5ba549e1bf8e627d61117a15ace8da6387a4`. Post-merge Regression Shield #1647, Engineering Governance #1909, all owning WP audits and Timeweb Read-Only Proof #14 completed `success`. The sanitized provider proof remains `TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY`. The observed Timeweb IPv4 remains fail-closed as `TIMEWEB_IPV4_ORPHAN_PROVENANCE_REQUIRED`; it grants no ingress mutation authority.

TW-A / INVENTORY_AND_AUTHORITY is therefore `CERTIFIED_GREEN / ACCEPTED`. Focused CA-trust repairs PR #585 and PR #586 were subsequently accepted on protected `main`; the current accepted base for PR #584 remains exact main `26bdc17c4e5d68c262f47b999e975b1eb8651858`.

P1 / SOURCE_RUNTIME_CONVERGENCE is branch-local `CERTIFIED_GREEN` on exact head `738d8c623d3002fd2eb312a6bce96c35bd45f75f`: all 25 observed exact-head checks completed `success`, including the authoritative Windows merge gate, Engineering Governance, Fast PR/toolchain/WP owning audits and SonarCloud with 0 new issues / 0 Security Hotspots. V9C-A→V9C-F are therefore closed as P1 evidence. P2 / TIMEWEB_EXACT_SHA_CANDIDATE is branch-local `CERTIFIED_GREEN` on exact head `ba43fa4be350340557fcf6d8532b6c089022a8ca`: all 19 observed repository workflows completed `success`, SonarCloud reported 0 new issues / 0 Security Hotspots, and unresolved review threads were zero. P3 / POSTGRES18_PRODUCTION_CUTOVER repository-side implementation is branch-local `CERTIFIED_GREEN` on exact head `7a9051bf8775977b1ae1324fe6d1b460c1d21aec`: all 25 exact-head checks completed `success`, including authoritative Windows, Governance, Fast PR/toolchain/WP audits and SonarCloud with 0 new issues / 0 Security Hotspots; unresolved review threads were zero and the branch was ahead-only with no conflicts. This certifies the P3 source checkpoint only and does not fabricate physical production database cutover or recovery acceptance. P4 / OMNICIO_RU_DNS_TLS repository-side public-ingress machinery is branch-local `CERTIFIED_GREEN` on exact head `d2240886ba3e7484622898670ac9b37ee45a7c6c`: all 19 applicable repository workflows completed `success` and unresolved review threads were zero. This does not fabricate physical DNS/TLS, Russian no-VPN or public-user acceptance. The current internal checkpoint is P5 / TELEGRAM_PUBLIC_ACTIVATION repository implementation; external provider credential custody, legal/privacy/regulatory, capacity/monitoring and real-user evidence remain independently fail-closed.

On 2026-09-24 the OWNER explicitly widened PR #584 branch-local implementation authority through Amendment 21. The same integrated branch may now implement the complete repository-side six-milestone production-delivery chain: source/runtime convergence; exact-SHA Timeweb App Platform candidate/release control; PostgreSQL 18 production cutover/recovery control; `omnicio.ru` DNS/TLS/public-ingress acceptance; Telegram-only public activation control; and post-merge production acceptance/rollback proof. External paid/provider/network, database cutover, DNS/TLS, secret, legal/privacy, public activation, destructive cleanup and merge actions remain independent fail-closed gates and are not fabricated by source implementation.

The branch is therefore no longer limited to TW-B source composition, but accepted-main progress remains 54% until the final integrated PR is accepted. No broker-write or Real-money authority is introduced.

Exact head `e9ac1475ed64d99454544478ac4cbd5dcdf7db71` completed all 19 applicable repository workflows `success` with zero unresolved review threads and no accepted-main divergence, establishing the P5 pre-hardening GREEN baseline. New preventive hardening intentionally invalidates that SHA as final merge evidence and requires a fresh exact-head cycle. P5 preventive hardening now closes two production-only classes before public activation. Telegram identity continuity is bound to public SHA-256 fingerprint metadata in `OMNI_V10_IDENTITY_BINDING_FINGERPRINT_SHA256`; silent identity-key rotation remains forbidden and a future intentional rekey requires reviewed migration/recovery. The Timeweb runtime also replaces its single serialized PostgreSQL connection with a bounded four-connection pool with five-second acquisition, transaction-local affinity and validated reconnect; authenticated session lookup is offloaded from the ASGI event loop. Because provider-auth abuse limits remain process-local, horizontal App Platform fan-out/Load Balancer topology remains forbidden until distributed abuse control is separately accepted. External provider, legal/privacy, capacity/load and real-user acceptance remain fail-closed.

P2 implementation is intentionally bounded. It may observe the exact existing Timeweb application and issue only one explicit exact-commit deploy after protected-main equality, application identity, autodeploy-off, fail-closed runtime flags and candidate liveness/release-SHA checks pass. It does not create/resize/delete an App Platform resource, patch provider settings, attach `omnicio.ru`, mutate production PostgreSQL, provision Telegram credentials or enable public users. Ambiguous deploy POST outcomes are reconciled by GET-only provider state rather than blind mutation retry. The GitHub workflow is manual-only and provider binding access is environment-scoped.

Earlier TW-B RED evidence is retained below as failure-learning history. The latest exact-head evidence before that correction showed: Fast PR failed only two changed-file Ruff formatting checks; the authoritative Windows suite reached 3695 passing tests, 912 subtests and 62.20% coverage with one Timeweb synthetic-create runbook marker failure; Sonar Quality Gate passed with zero Security Hotspots but reported one maintainability issue in the Timeweb inventory transitive-consumer validator; and the WP17 OWNER Read Vault audit remained fail-closed on `WP17_OWNER_EVIDENCE_HEAD_DRIFT` with `owner_evidence_ready=true` and direct permission probes intentionally not executed. The repository-side correction must fix those source defects, make the Timeweb inventory governance run read and structurally validate the complete discovered repository tree, and then freeze the replacement head before OWNER evidence is rebound. No Timeweb provider mutation, production DB/DNS cutover, public Telegram activation, broker write or Real-money authority is introduced.

Pre-correction exact-head evidence on `89fb19cf131c509bd2ef49c1eaaa8d7e0ccf868b` proves the whole-repository integrity pass is operational: Engineering Governance read all 1,723 discovered repository files, classified 1,693 as text and 30 as binary, structurally parsed 919 Python and 80 JSON files, and completed `V10_TIMEWEB_PLATFORM_INVENTORY=PASS`. Fast PR and authoritative Windows then independently stopped only on Ruff formatting of that verifier; functional frontend/WP lanes and Engineering Governance itself were successful. The same head's WP17 audit remained correctly blocked by `WP17_OWNER_EVIDENCE_HEAD_DRIFT`. A replacement source head must rerun all exact-head evidence; prior GREEN is not carried forward.

Official Timeweb App Platform documentation was rechecked on 2026-09-23. The existing TW-B source already matches the applicable source constraints: root Dockerfile deployment with `EXPOSE 8080`; process-only `/livez` for platform liveness and DB-aware `/healthz`; external PostgreSQL persistence rather than container-local state; runtime variables/secrets outside Git/image metadata; and an explicit deferred decision for App Platform private-network selection because Timeweb documents that this choice is made at application creation and cannot be changed in place. These are source/planning constraints only; TW-C/TW-D remain the provider-mutation/cutover gates.

The same official-doc review exposed one material TW-C-preventive build defect in TW-B: the canonical runtime lock contacts the official T-Bank Python package index, but the Timeweb Docker image previously ran pip without the reviewed Russian Trusted Root CA augmentation. TW-B now reuses the accepted pinned ephemeral `PIP_CERT` builder for the Docker dependency-install step only and enables `SSL_TBANK_VERIFY=True` for the locked T-Invest SDK runtime. TLS/hostname verification remains enabled, no dependency version/source is changed, and no broker/Telegram/PostgreSQL secret is baked into the image. This is source/runtime hardening only, not Timeweb deployment or broker activation authority.

Correction head `7ec4a8bf9bb3b02cb8d4571389938def6f17be61` removed the first stale probe and strengthened inventory discovery, then Engineering Governance #1895 correctly failed with `TIMEWEB_CONSOLIDATION_ACTIVE_WORKFLOW_RETIRED_PROVIDER_EXECUTION`: the historical WP22A Phase-5 technical-closeout workflow was a second neutral-name consumer that still compiled and live-ran the same Render Phase-4 probe. Repository search shows these Phase-4 and Phase-5 workflows are the complete Actions consumer set for that retired probe. Both must be archive-in-place/manual hard-disabled before the TW-A checkpoint can be certified.

Exact head `b8c00434d6669dff4fc05d0a0f2576b358b24c0e` then passed the strengthened retired-workflow authority guard but the new inventory guard failed on an internal classification mismatch: `apps/api/cf_d_database_bootstrap.py` remains an active transitive dependency of `hosted_preview.py` and is therefore correctly `TIMEWEB_REPLACE`, not `HISTORY`. The correction keeps that producer in replacement scope until TW-B detaches it; the two retired hosted-acceptance workflows remain historical archive-only.

Exact head `0a4727d3de7329fdeb21274badc364b2dba6b462` passed both strengthened Timeweb authority and provider-inventory guards and compiled the guard set. Its remaining Engineering Governance RED was limited to `tests/test_v10_wp22a_historical_gate_routing.py`, whose old assertions still required the Phase-4/Phase-5 `pull_request.paths` triggers that Amendment 18 now forbids. That regression must be inverted to require archive-only/manual hard-disabled routing; this does not reopen any retired provider authority.

Exact head `d438ce4cd3cf98d1a7cdaee2d6cf90f0b742a030` then reached a narrower systemic RED. Engineering Governance and all observed WP/toolchain/Web lanes completed `success`; Fast PR Checks #3014 failed only because two historical-workflow reads in `tests/test_v10_ru_public_registration_ingress.py` were not in pinned Ruff layout. Authoritative Windows CI #3106 passed compile and protected static quality, then failed the unchanged tracked-content secret detector on two new entropy-shaped verifier literals: the embedded accepted-base SHA in the inventory JSON and one long Cloudflare marker literal in the guard. Sonar additionally reported duplicate-character-class warnings and a ReDoS flow because the verifier executed regular expressions supplied by the repository-controlled JSON contract. The systemic correction is to remove contract-controlled regex execution, use bounded plain-string matcher primitives, keep exact cardinality, expand executable-source hidden-consumer coverage, and structurally remove the entropy-shaped literals without suppression or secret-scan weakening.

Replacement preflight also found two previously unclassified transitive dependencies before remote certification: `apps/web/vite.config.ts` still consumes `RENDER_GIT_COMMIT`, and the active PostgreSQL runtime-role rehearsal still imports `_converge_runtime_role` from the historical Render/Neon provisioner. Both are now explicitly `TIMEWEB_REPLACE`; the current clientless workflow remains `KEEP` only because its retired-provider strings are static negative/source-evidence assertions and its separate execution guard forbids retired provider execution.

Exact head `770b42c80f395d15ab483b20c05831e386bfb510` removed the prior Sonar Quality Gate failure (0 security hotspots), but Engineering Governance #1900 then correctly stopped at `TIMEWEB_INVENTORY_UNCLASSIFIED_RETIRED_CONSUMER:.github/workflows/v10-engineering-governance.yml`. Root cause was verifier-layer conflation, not a new provider execution: the generic content scanner interpreted a static `py_compile` reference to historical provider code as a runtime dependency. The correction separates code/import consumer scanning from GitHub Actions execution scanning and strengthens the latter with direct retired provision/deploy command markers, so static historical verification remains allowed while actual retired-provider execution fails closed.

Exact head `3acb0490893dc4aed81667e5f8145ba2da645501` confirmed that workflow/source separation but exposed one final self-reference of the same class: the current Russia-ingress security guard itself contains retired provider script names as detection data. Whole-source marker enumeration found no other unclassified strong-marker consumer. The correction therefore exempts exactly the two security-verifier source files from consumer scanning while keeping the Russia-ingress execution-aware workflow guard authoritative for provider commands; this avoids broad suppression and keeps any new ordinary `KEEP` source fail-closed.

Exact head `f6ec32b10d6cf2ca39072cd89d14110ca474c140` then passed the new TW-A inventory guard and compiled governance source, but its stdlib regression found a fail-closed ordering defect in `_rule_matches`: unknown matcher keys were checked only after selector evaluation, so a non-matching valid prefix could return `False` before an injected unknown key was rejected. The correction validates the complete matcher shape before any matching operation, preserving bounded non-regex evaluation while making malformed contract input deterministically fatal.

## Amendment 20 — V9-to-V10 convergence / legacy working-tree retirement (branch-local)

OWNER decision on 2026-09-24 extends the current `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED`
update inside PR #584. This is branch-local implementation authority until an
OWNER-authorized merge; accepted-main progress remains 54%.

The accepted V9 repository target
`b9e4fabcb54f8f6e0ba206f030c35f2fafa2ce62` is already an ancestor of current
accepted main. Therefore stale `v9/*` branch heads are not merged into PR #584.
V9 is now the migration source for the one forward V10/Timeweb runtime.

`V9C-A / AUTHORITY_AND_INVENTORY` is branch-local **CERTIFIED_GREEN** on exact head `7b325d7805e4c9b4c571d85d33ebd4875f060d35`: all 18 repository workflows completed `success`, including Fast PR, authoritative Windows CI, Engineering Governance, Toolchain and the owning WP audits. V9C-C / RUNTIME_ENTRYPOINT_CONVERGENCE is branch-local **CERTIFIED_GREEN** on exact
head `ddc780b43e74797bc0adea31a741db35eeb06605`. Current internal checkpoint is
**V9C-D / GPT_AND_RETIRED_PROVIDER_WORKTREE_RETIREMENT**. Current GPT development
authority is Timeweb/Telegram under Amendments 18–21; protected V9 GPT/Render recovery
material remains explicitly non-current; the supported V10 runtime must have zero
retired-provider module imports.
Ordered convergence is V9C-A authority/inventory -> V9C-B deterministic source relocation -> V9C-C runtime
entrypoint convergence -> V9C-D GPT/retired-provider working-tree retirement -> V9C-E
CI/recovery convergence -> V9C-F whole-tree legacy absence proof.

Legacy files may be deleted only after replacement, producer/consumer migration,
parity/contract regression, zero required current consumers, and recovery/security
proof. Git history is retained. PR #584 must not be merged to `main` without a new
explicit OWNER instruction.

This Amendment-20 authority by itself did not deploy TW-C, cut over production
PostgreSQL, mutate DNS/TLS or activate public Telegram users. Amendment 21 now supersedes
that **branch-local implementation-scope limit only**, allowing those later delivery
controls to be implemented in PR #584 while their external mutations remain independently
gated. Broker write, Real money, WEB-VISUAL and WP23+ remain locked.

## Amendment 21 — full Timeweb production-delivery implementation in PR #584

OWNER decision on 2026-09-24 authorizes one integrated branch/PR to contain all
repository-side implementation required for the six delivery milestones. This is
branch-local authority, not accepted-main progress and not permission to synthesize
provider/legal/secret evidence.

Production identity remains exact-SHA and fail-closed:
`accepted main SHA -> exact Timeweb deploy -> /livez exact SHA -> owning acceptance`.
Autodeploy is not production authority. Production mismatch is
`OUT_OF_SYNC/DEPLOYMENT_BLOCKED`, with last-known-good rollback preserved.

The canonical public origin remains `https://omnicio.ru`; Telegram callback remains
`https://omnicio.ru/api/v10/web/auth/telegram/callback`. Public flags remain false until
the Telegram capability's real runtime/database/DNS/privacy/legal/capacity gates pass.

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

Current TW-B exact-head RED evidence on `c74e0ad8394076b866119c642e63bbe81b1bc680`: all observed functional/governance lanes passed except Fast PR, authoritative Windows and WP17 OWNER evidence. Fast PR reported only Ruff quoting format in the two new Docker CA regression tests. Authoritative Windows passed the functional suite and failed later at Bandit B314/CWE-20 because the whole-repository audit parsed arbitrary XML with stdlib ElementTree. The first replacement attempted to use defusedxml, but Engineering Governance runs this inventory guard before dependency installation and correctly failed with `ModuleNotFoundError`. The next correction uses the repository's accepted dependency-free stdlib Expat hardening pattern with DTD/entity/external-entity rejection plus the malicious-DTD/entity regression; scanner suppression is forbidden. WP17 remains separately fail-closed on exact-head OWNER evidence binding.

## Telegram identity / bot separation

Canonical product authentication is `Telegram USER account OIDC Login -> verified identity -> OmniCIOUserAccount -> Tenant -> server-side Session`. Registration/login does not require a bot chat, `/start`, a bot-link record or `telegram:bot_access`; the source scope remains exactly `openid`. Telegram's BotFather-managed login application registration is provider client metadata, not product bot linkage. The optional Omni-CIO Telegram bot is a distinct future WP23+ companion capability and may be linked only after an Omni-CIO account and authenticated server-side session already exist. It cannot create accounts, mint/select tenants or replace Telegram Login.

## Amendment 19 — no manual OWNER-laptop dependency for the Timeweb PR path

OWNER explicitly directed on 2026-09-23 that Timeweb consolidation continue without requiring manual commands on the personal laptop. The prior WP17 `WP17_OWNER_EVIDENCE_HEAD_DRIFT` result remains valid historical evidence about the local Windows vault, but that local vault is not part of the deployed Timeweb runtime. Amendment 19 therefore supersedes the machine-local ACL proof as a blocking Timeweb PR prerequisite. The required check name is retained for branch-protection continuity and now proves, on a GitHub-hosted runner, that current Timeweb source has no Windows-vault dependency and that hosted broker credential mutation remains fail-closed until a tenant-scoped encrypted hosted backend passes its own gate. The old Windows audit is preserved as manual historical evidence only. No broker secret, provider secret or private payload is moved into GitHub by this transition.

A new commit implementing Amendment 19 invalidates all earlier exact-head GREEN evidence by design. The branch returns to `PENDING` for a complete fresh exact-head verification batch; TW-C remains blocked until that replacement head is fully GREEN and accepted.

## TW-B exact-head repair — Amendment 19 producer/consumer closure

Exact head `01cb544e87e71827aec6b22e0ada3292d96233e1` completed Engineering Governance,
Sonar, the new GitHub-hosted WP17 Timeweb source-security audit and the observed
functional WP13/WP15/WP16/WP18-WP22A lanes successfully. It exposed two remaining
repository defects: Ruff formatting drift in the newly added Amendment-19 guard/test,
and a stale WP17 local-vault regression that still required the **active** Timeweb
workflow to execute the historical Windows ACL auditor. The latter caused both WP17
Application Shell and WP15 Live Web Support to fail the same test.

The repair class is producer/consumer closure, not an OWNER action. The first
replacement also exposed a current-guidance guard coupled to the literal Amendment-18
heading; that validator must bind to durable Timeweb/Telegram/no-laptop semantics rather
than an amendment-number string. The active Timeweb
contract/guard/test path must state that OWNER/Admin ACL evidence does not block the
Timeweb PR, while the old DPAPI/ACL scripts and direct negative permission proof remain
preserved behind the manual historical workflow. Hosted broker credential mutation
continues fail-closed until an accepted tenant-scoped encrypted hosted custody backend
exists. WP17 exact-head then reached all Web/browser checks successfully and stopped only at Ruff formatting of three long `failures.append(...)` lines in the new security guard. The correction is formatter-only and preserves every assertion. A replacement commit invalidates all prior exact-head evidence and must receive
a fresh complete certification batch before TW-B can leave `RED_REPAIR_ONLY`.

## Current next action

1. treat exact head `2d16dbe20e558c33fed6f8b130847f71149e2ade` as the completed V9C-B branch-local GREEN checkpoint only; every new commit invalidates it for final acceptance;
2. implement Amendment 21 production-delivery contracts/guards first, then continue the six ordered milestones in the same PR #584 branch without creating a competing Web/runtime stack;
3. keep every provider/payment/network/database/DNS/secret/legal/public-activation mutation behind its explicit evidence gate; repository implementation may advance, external state may not be invented;
4. require exact accepted-main SHA binding for Timeweb deployment and runtime `/livez`; production autodeploy is not authority;
5. keep `PUBLIC_MULTI_USER_ENABLED=false` and `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false` until the final Telegram activation gate; VK stays absent;
6. keep broker write OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, tenant/RLS/FORCE-RLS protections intact;
7. after each material checkpoint, require a fresh exact-head verification batch before advancing; final PR landing still requires the normal explicit exact-head merge confirmation.
