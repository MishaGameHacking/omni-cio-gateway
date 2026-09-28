# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-09-28

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCKS A–E COMPLETE / WP0–WP22A COMPLETE / ACCEPTED IMPLEMENTATION 54% / CURRENT AUTHORIZED SYSTEM UPDATE TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED / CURRENT ACCEPTED MAIN `f57e088d4188da4ceec387c82f8b3b847fc6e0bb` VIA ACCEPTED APP-PLATFORM PRIVATE POSTGRESQL ROUTE REPAIR / CURRENT LIVE P3 OBSERVE STOP `TIMEWEB_PG_PRODUCTION_FIREWALL_SERVICE_GROUP_NOT_EXCLUSIVE` IS A REPOSITORY/PROVIDER-SEMANTICS DEFECT / FOCUSED RED REPAIR PR #597 `fix/timeweb-production-firewall-group-union` / PHYSICAL APP CREATION REMAINS PAUSED UNTIL P3 OBSERVE -> PREPARE -> RECOVERY PREREQUISITES ARE PROVED / WEB-VISUAL PAUSED / WP23+ LOCKED / PUBLIC USER ACTIVATION FAIL-CLOSED**.

Accepted implementation progress is **54%**. The PR #584 merge does not by itself invent a new percentage; this ledger changes the percentage only through explicit accepted program authority.

### 2026-09-28 P3 observe #4 firewall-group cardinality defect

Accepted protected main is `f57e088d4188da4ceec387c82f8b3b847fc6e0bb`, the squash merge of PR #596. That repair preserves the Timeweb technical PostgreSQL hostname for `verify-full` TLS identity while binding App Platform runtime TCP to the scoped private PostgreSQL address, and requires technical-candidate `/healthz database=READY` before P3 acceptance.

Manual `V10 Timeweb PostgreSQL Production Cutover #4` on that exact main passed exact-main authority, P3 source, GitHub Environment and input validation, then stopped before database authentication with sanitized code `TIMEWEB_PG_PRODUCTION_FIREWALL_SERVICE_GROUP_NOT_EXCLUSIVE`.

Fresh official Timeweb Firewall documentation proves the repository assumption behind that code is invalid: a service may belong to multiple firewall groups of the same type and the rules are combined. The focused RED repair is PR #597 / branch `fix/timeweb-production-firewall-group-union`. It replaces invented single-group and per-group-rule cardinality with a complete effective-union proof: all attached groups must remain allowlist/`DROP`, all group identities and provider rule identities must be unique, each group must link only the exact production database resource, and the effective rule union must contain the exact ingress TCP/5432 verifier `/32` rule and no other semantic rule. Rule-less same-type groups and duplicate equivalent rules are tolerated only because they do not widen the documented effective union. Two-pass provider snapshot stability remains mandatory.

This repair is read-only provider verification. It does not mutate Timeweb firewall state, PostgreSQL, App Platform, DNS/TLS, Telegram/public-user state, broker authority or Real Trading. Do not rerun P3 from old main. Exact-head repository verification, squash merge, exact-main post-merge verification and then a fresh P3 `observe` are required.

### 2026-09-27 synthetic create #6 start-readiness defect

PR #594 is accepted on protected `main = dee72c4fadd775ffcf878ce7dd7484aa57ed35f1`.
The subsequent manual `V10 RU-PG-B Timeweb Synthetic Create #6` reached the provider mutation/recovery step and stopped with the sanitized code `TIMEWEB_CLUSTER_START_TIMEOUT`.

Current source proves that this code is emitted only after provider state has been observed while terminal `status=started` has not been proved before the local start-readiness budget expires. The accepted source budget was only 288 seconds. This is therefore an asynchronous-provider readiness defect class, not evidence that a second create POST is safe or required.

The focused repair branch is `fix/timeweb-synthetic-start-readiness`. It may change only observation/recovery semantics needed to make the existing single-create state machine robust: extend the GET-only readiness budget, bound nested control-plane read retries so the GitHub workflow cannot preempt semantic timeout classification, preserve complete wall-clock workflow headroom, add a specific persistent-`starting` sanitized timeout class, strengthen tests/guards/runbook/failure-learning evidence, and keep restart recovery GET-only for an already-existing exact target.

The repair must not issue another create for an existing target, delete or resize the cluster, widen network exposure, enable IPv6/backups/replication, mutate production DSN/DNS/TLS, activate Telegram/public users, enable broker write or enable Real Trading. A remaining `starting` state after the new bounded waiter is still fail-closed and requires read-only reconciliation.

Pre-merge full-path review found a second defect in the same readiness-budget class: the first 20-minute workflow correction counted only the 708 seconds of explicit sleeps, while every readiness GET can itself perform up to three bounded control-plane attempts. A subsequent challenge expanded that calculation to the complete provider phase: credential/type/preset/target reads, the one create request, ambiguous-create GET-only reconciliation, startup observation and final project-custody verification. The branch now bounds every synthetic-create control-plane read to 10 seconds, the one create request to 30 seconds, and the job ceiling to 60 minutes; regression math requires at least 1,200 seconds of worst-case headroom after the complete provider phase. This prevents Actions from killing the job before sanitized reconciliation/readiness semantics can be emitted.

### 2026-09-27 downstream topology / executable-chain audit

The current OWNER-provided Timeweb project screenshot is treated as external provider observation, not API acceptance evidence. It shows two PostgreSQL services present, the single current public IPv4 attached to the production PostgreSQL target, the synthetic PostgreSQL target without a displayed public IPv4, and `omnicio.ru` present as an externally managed domain.

Repository authority must not infer from that screenshot that the production-bound IPv4 may be moved. Current IPv4 custody code already treats a managed resource bound to another target as `TIMEWEB_IPV4_CUSTODY_BOUND_ELSEWHERE`; production transport must remain protected from synthetic-test reuse.

The full sequential audit also found a live evidence gap beyond the current create waiter: the RU-PG-B parity contract still says `SOURCE_READY_PROVIDER_EVIDENCE_PENDING`, and no accepted live `RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS` evidence is present in the owning issue/repository history. The parity Python harness exists, but there is no dedicated protected-main GitHub workflow that binds its synthetic DSN/certificate custody and executes the real parity proof. Therefore source-level P2/P3/P4/P5/P6 machinery must not be interpreted as proof that the complete provider sequence has already executed.

This gap is a mandatory split after the current focused #595 repair: database parity execution and any replacement network transport require their own reviewed authority. Do not move the production IPv4 back to the synthetic cluster, buy a replacement IP, enable IPv6, mutate production PostgreSQL, attach DNS, or activate Telegram merely to close the sequence. Observation/reconciliation may be automated; network, database-cutover, DNS and public-login mutations stay fail-closed one-shot gates.

### 2026-09-27 hosted-runtime database route defect class

The sequential audit found a separate pre-publication production-network defect class in accepted source contracts. P3 currently proves production PostgreSQL ingress as `DROP + one TCP/5432 verifier /32` where the allowed source is the current self-hosted verification runner. P2/hosted runtime later expects Timeweb App Platform to open `OMNI_V10_POSTGRES_DSN` to that same production PostgreSQL endpoint. No accepted contract proves that App Platform outbound traffic will originate from that verifier /32, and current official Timeweb documentation does not provide that guarantee.

Therefore P3 verifier reachability is not application-runtime reachability. A production cutover must not be accepted merely because the self-hosted verifier can connect while the future App Platform container may remain blocked by the exact firewall rule.

Official Timeweb App Platform documentation also makes private-network selection an application-creation decision that cannot be changed in place later. This creates a mandatory network/security split **before physical App Platform creation**: the final App-to-PostgreSQL route must be selected and proved first. A preferred target may use a shared Timeweb private network only after an owning contract proves provider compatibility, TLS/hostname verification, PostgreSQL identity, recovery and routing; it must not silently replace the currently accepted public verify-full path.

Until that gate is accepted, do not create the production App Platform application with an arbitrary/no-private-network choice, widen the production PostgreSQL firewall, assume a stable App Platform public egress IP, or treat P3 `source=/32` evidence as hosted-runtime connectivity proof.

### 2026-09-27 accepted-main read-only proof #24 defect

PR #593 was squash-merged to accepted `main = 2bfa6c2b55caab0d474f890792f4e44c745a7744`.
On that exact SHA the repository-owned regression/governance/security baseline is GREEN:
Engineering Governance and the full Windows quality/contracts/coverage job succeeded;
the whole-tree Timeweb verifier read 1,768 tracked files and reported
`V10_TIMEWEB_REPOSITORY_INTEGRITY=PASS` plus
`V10_TIMEWEB_PLATFORM_INVENTORY=PASS`; the full Python suite reported 3,959 passing tests,
962 passing subtests and 65.21% measured coverage.

The post-merge `V10 RU-PG-B Timeweb Read-Only Proof #24` then stopped only in its
provider-observation job. The control-plane probe successfully proved PostgreSQL 18/project/
preset authority and reported
`cluster_name_available=true existing_target=false`. The immediately following IPv4
custody observer interpreted that same valid pre-create state as fatal
`TIMEWEB_IPV4_TARGET_NOT_FOUND`. This is a repository producer/consumer contract defect,
not a Timeweb authentication failure, PostgreSQL authentication failure, Telegram defect or
permission-expansion request.

The correction must keep provider access GET-only, inspect the complete account-level
floating-IP inventory even when the target database does not exist, report target-specific
recovery as explicitly BLOCKED, and never synthesize a target id, custody marker, binding,
network readiness or mutation authority. Malformed/truncated provider inventory remains
terminal. No production database mutation, DNS/TLS change, Telegram activation, broker write
or Real-money authority is granted by this correction.

### 2026-09-26 accepted-main / live-cutover continuation

PR #584 was squash-merged and accepted on protected `main` as `a3e96287f6f29f9a17f14758223a653b37abb50c`. Its exact-main post-merge evidence completed GREEN. PR #587 repaired the existing-IPv4 provider-identity contract. PR #588 then repaired the combined public-IPv4/TLS provider transition, passed DRAFT and READY exact-head certification, and was squash-merged as current `main = 86294ebb0e5b6eb0a56aa8d4b28f1692f483a8d8`.

The existing-IPv4 allocation path remains beyond the earlier orphan-provenance blocker: live evidence proves `managed_unbound=1 unproven_unbound=0` and the durable allocation prerequisite. Public IPv4/TLS workflow ordinal #6 on current main no longer hit the prior HTTP 400. It entered the separated provider transition path and stopped only at `TIMEWEB_PUBLIC_IPV4_TLS_READY_TIMEOUT` after the source exhausted its fixed `2+3+5+8+15+20+30 = 83` second GET-only TLS/domain readiness waiter.

The current failure boundary is asynchronous provider readiness reconciliation, not OWNER input, verifier CIDR, allocation custody or another deterministic mutation rejection. Timeweb's API contract permits a successful mutation response while a resource remains in transition, while its PostgreSQL TLS guidance requires waiting for protected-connection setup to complete and documents no 83-second SLA. The focused repair `fix/timeweb-tls-readiness-timeout` therefore extends only the bounded GET-only TLS/domain readiness budget and adds sanitized predicate-specific timeout classification. It preserves one mutation per transition, unsafe-status hard stops, exact managed-IP/firewall verification, rollback, and the existing-only/no-second-purchase authority boundary. No further live transport run is authorized until this replacement source is exact-head certified and accepted.

No production PostgreSQL cutover, `omnicio.ru` DNS/TLS cutover, Telegram public activation, broker write or Real-money authority has been accepted by this live evidence. `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain unchanged.

Blocks A (5%), B (9%), C (12%), D (14%) and E (14%) have passed their owning Exit Gates. WP16–WP22 and the complete **WP22A — External Web Access / Product Authentication Security Gate** are accepted COMPLETE.

Amendment 14 remains accepted **historical evidence**, but Amendment 18 supersedes it for current/future provider selection. The complete `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED` chain remains an accepted historical baseline; its final focused CF-D hardening landed through PR #547.

Amendment 15 records the 2026-08-29 OWNER delivery correction: the four Amendment-14 Cloudflare implementation stages remain ordered and fail-closed but are executed as internal milestones of one `INTEGRATED_SYSTEM_UPDATE`, `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, on default branch `system/cloudflare-public-product`, with one final PR by default. Separate protected-main acceptance between CF-A/CF-B/CF-C/CF-D is no longer required. A real Amendment-12 split trigger discovered during implementation still forces a stop/split.

Neither Amendment 14 nor Amendment 15 by itself deploys Cloudflare, mutates DNS/domain/provider state, provisions secrets, activates public users or authorizes Real money.

`PUBLIC_MULTI_USER_ENABLED=false` remains the **current runtime state, not a V10-wide release lock**. Under Amendment 13, completed capabilities may become live as soon as their own real authentication/runtime/privacy/security/capacity/monitoring gates pass; unrelated unfinished V10 blocks are not a reason to hold a ready capability forever.

Amendment 18 is accepted on protected `main` through PR #581 and retires Cloudflare/Neon/Render/Cloud.ru/VK from current/future V10 provider authority. `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED` is the current authorized System Update. WEB-VISUAL and WP23+ remain paused until the consolidation/public-activation path reaches its owning exit gate.

PR #582 remains the accepted CI/provider-authority split. TW-A then completed through PR #583. Its exact reviewed head `2c4cf7915c02d05e42b269544bc0336c31fa9a87` passed DRAFT and READY certification, and PR #583 was squash-merged to exact main `c7ea5ba549e1bf8e627d61117a15ace8da6387a4`. Post-merge Regression Shield #1647, Engineering Governance #1909, all owning WP audits and Timeweb Read-Only Proof #14 completed `success`. The sanitized provider proof remains `TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY`. The observed Timeweb IPv4 remains fail-closed as `TIMEWEB_IPV4_ORPHAN_PROVENANCE_REQUIRED`; it grants no ingress mutation authority.

TW-A / INVENTORY_AND_AUTHORITY is therefore `CERTIFIED_GREEN / ACCEPTED`. Focused CA-trust repairs PR #585 and PR #586 were subsequently accepted on protected `main`. The historical PR #584 base was `26bdc17c4e5d68c262f47b999e975b1eb8651858`; PR #584 is now accepted on main and must not be treated as an open execution branch.

P1 / SOURCE_RUNTIME_CONVERGENCE is branch-local `CERTIFIED_GREEN` on exact head `738d8c623d3002fd2eb312a6bce96c35bd45f75f`: all 25 observed exact-head checks completed `success`, including the authoritative Windows merge gate, Engineering Governance, Fast PR/toolchain/WP owning audits and SonarCloud with 0 new issues / 0 Security Hotspots. V9C-A→V9C-F are therefore closed as P1 evidence. P2 / TIMEWEB_EXACT_SHA_CANDIDATE is branch-local `CERTIFIED_GREEN` on exact head `ba43fa4be350340557fcf6d8532b6c089022a8ca`: all 19 observed repository workflows completed `success`, SonarCloud reported 0 new issues / 0 Security Hotspots, and unresolved review threads were zero. P3 / POSTGRES18_PRODUCTION_CUTOVER repository-side implementation is branch-local `CERTIFIED_GREEN` on exact head `7a9051bf8775977b1ae1324fe6d1b460c1d21aec`: all 25 exact-head checks completed `success`, including authoritative Windows, Governance, Fast PR/toolchain/WP audits and SonarCloud with 0 new issues / 0 Security Hotspots; unresolved review threads were zero and the branch was ahead-only with no conflicts. This certifies the P3 source checkpoint only and does not fabricate physical production database cutover or recovery acceptance. P4 / OMNICIO_RU_DNS_TLS repository-side public-ingress machinery is branch-local `CERTIFIED_GREEN` on exact head `d2240886ba3e7484622898670ac9b37ee45a7c6c`: all 19 applicable repository workflows completed `success` and unresolved review threads were zero. This does not fabricate physical DNS/TLS, Russian no-VPN or public-user acceptance. P5 / TELEGRAM_PUBLIC_ACTIVATION repository-side source machinery is branch-local `CERTIFIED_GREEN` on exact head `ad50273642cc66f537070b4800f319857f7d0096`: all 19 applicable repository workflows completed `success`, SonarCloud reported 0 new issues / 0 Security Hotspots / 0 annotations, unresolved review threads were zero, and the branch was ahead-only with `behind_by=0`. This certifies source machinery only; provider credentials, legal/privacy/regulatory acceptance, capacity/monitoring, public-user activation and real-user evidence remain independently fail-closed. P5.5 / TIMEWEB_WORKTREE_CONVERGENCE repository implementation is complete: dormant clientless Cloudflare/WP22A paths are removed, current Timeweb runtime reachability rejects retired-provider modules, Telegram-only auth is the current product identity path, and live documentation delegates mutable checkpoint state to this canonical ledger. Exact head `46ae2e447692de0f72b03ef001ad887e835083d2` established the pre-closing baseline with every repository-owned GitHub check successful, zero unresolved review threads, and only the non-final external Sonar Automatic Analysis check provider-cancelled with zero annotations. This closing state commit intentionally invalidates that SHA as final merge evidence; its replacement head must rerun exact-head verification. P6 source machinery is complete and adds a deterministic, secret-free exact-main production acceptance seal binding P2/P3/P4/P5 and rollback evidence; production acceptance can execute only after squash merge on exact protected main and does not fabricate external acceptance.

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
head `ddc780b43e74797bc0adea31a741db35eeb06605`. At that historical stage, the next internal checkpoint was
**V9C-D / GPT_AND_RETIRED_PROVIDER_WORKTREE_RETIREMENT**; later P1 evidence closed V9C-D/V9C-E/V9C-F. Current GPT development
authority is Timeweb/Telegram under Amendments 18–21; protected V9 GPT/Render recovery
material remains explicitly non-current; the supported V10 runtime must have zero
retired-provider module imports.
Ordered convergence is V9C-A authority/inventory -> V9C-B deterministic source relocation -> V9C-C runtime
entrypoint convergence -> V9C-D GPT/retired-provider working-tree retirement -> V9C-E
CI/recovery convergence -> V9C-F whole-tree legacy absence proof.

Legacy files may be deleted only after replacement, producer/consumer migration,
parity/contract regression, zero required current consumers, and recovery/security
proof. Git history is retained. This was the pre-landing Amendment-20 rule; PR #584
was later explicitly authorized, squash-merged and accepted on 2026-09-26.

This Amendment-20 authority by itself did not deploy TW-C, cut over production
PostgreSQL, mutate DNS/TLS or activate public Telegram users. Amendment 21 now supersedes
that **branch-local implementation-scope limit only**, allowing those later delivery
controls to be implemented in PR #584 while their external mutations remain independently
gated. Broker write, Real money, WEB-VISUAL and WP23+ remain locked.

## Amendment 21 — accepted Timeweb production-delivery source implementation from PR #584

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

1. finish the focused Timeweb App-to-PostgreSQL private-route source repair and require a fresh exact-head Draft verification cycle after every corrective commit;
2. keep the physical App Platform order paused until the source repair is accepted on protected main and its exact-main post-merge regression/governance shield is GREEN;
3. on accepted main, execute the production PostgreSQL sequence in its owning gate: read-only observe, prepare the canonical schema/runtime ACL/RLS state, then complete the required physical-backup and separate-restore recovery evidence;
4. create `omni-cio-v10` once through the Timeweb panel in the already selected production private network, with Dockerfile deployment, autodeploy off and `/livez` process health; do not attach `omnicio.ru` yet;
5. after Timeweb assigns the technical HTTPS hostname, add it to the App runtime configuration, redeploy the same accepted main identity and require both exact-SHA `/livez` and `/healthz database=READY synthetic_preview=false`;
6. only after that current physical candidate proof may P3 final acceptance proceed, followed by the later canonical-domain/TLS and Telegram public-activation gates;
7. preserve the production public IPv4/firewall verifier route, tenant/RLS/FORCE-RLS boundaries, broker write OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, and fail closed on any provider or runtime ambiguity.

### P5 source certification / P5.5 worktree-convergence transition — 2026-09-25

Exact head `ad50273642cc66f537070b4800f319857f7d0096` completed all 19
applicable repository workflows with `success`. The authoritative Windows merge gate
completed its Regression Shield, dependency audit and SAST successfully; SonarQube
Cloud completed `success` with 0 new issues, 0 Security Hotspots and 0 annotations;
unresolved review threads were zero and the branch remained `behind_by=0`.

This certifies P5 repository-side Telegram/public-user activation machinery only.
`PUBLIC_MULTI_USER_ENABLED=false`, `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`,
`OMNI_V10_VK_ID_LOGIN_ENABLED=false`, broker write, `trading_methods=false` and
`REAL_TRADING_ENABLED=false` remain unchanged. No production Telegram credential,
public-user activation, legal/privacy acceptance or real-user evidence is fabricated.

OWNER-authorized destructive repository cleanup therefore advances to the internal
P5.5 Timeweb worktree-convergence phase in the same PR #584. The first coherent
subsystem removes the dormant Cloudflare/WP22A clientless remote implementation and
its dedicated workflow/tests from the current worktree, preserves protected V9
`app:app` recovery and accepted immutable PostgreSQL migrations, and installs a
fail-closed guard that rejects reintroduction of the retired subtree or workflow/runtime
references. Ordinary non-sensitive history remains available in Git history rather than
being kept executable in the current tree.

## Timeweb App private PostgreSQL route repair — 2026-09-27

Fresh accepted protected `main` for this checkpoint is `3326da2314010f510fb48775e21209a3ba165b0f`. Focused branch `fix/timeweb-app-private-postgres-route` is the only active source-repair branch for the discovered App Platform database-route defect.

OWNER panel evidence confirms, without recording credential values or private provider identifiers, that the canonical production PostgreSQL target already belongs to the same Timeweb private network offered by the `omni-cio-v10` App Platform creation flow, that PostgreSQL exposes a private TCP/5432 endpoint, and that protected connection remains enabled. The existing production public IPv4 stays attached and is not repurposed.

The prior hosted runtime incorrectly inherited the P3 self-hosted verifier's public-address invariant and P2 accepted exact-SHA `/livez` without proving App-to-PostgreSQL reachability. The focused repair now separates the two routes: P3 remains public/firewall-scoped; the Timeweb App runtime uses an explicit scoped private PostgreSQL address while retaining the technical-domain DSN for `verify-full` TLS identity. P2 candidate acceptance is being strengthened to require `/healthz status=ok database=READY synthetic_preview=false` in addition to exact-SHA `/livez`.

The pre-merge challenge also found two downstream live-only contract defects and repaired them in the same route/readiness class. First, a real hosted-runtime JSON 503 from `/healthz` was previously collapsed into a generic transient HTTP failure before its sanitized dependency state could be classified; runtime 503 evidence is now schema-bounded and terminates specifically as database-not-ready, while proxy-shaped 503 responses remain generic. Second, P3 still assumed undecorated GitHub-provider `repository.full_name` metadata even though the accepted Timeweb bootstrap uses repository-by-URL; P3 now consumes the same canonical clone-URL identity predicate as P2 so a valid URL-connected App cannot disappear at final database acceptance.

A further provider-specification review found a third creation-time defect before payment: current Timeweb documentation gives the panel health-check path precedence over Dockerfile `HEALTHCHECK`, while the repository contracts had that precedence reversed. P2 and full-delivery contracts now require the panel path `/livez`, preserve Dockerfile `/livez` as the identical fallback, and keep database-aware `/healthz` outside platform liveness. The execution ledger, runbook and regression guards are aligned; FL-048 records the prevention rule.

Physical `omni-cio-v10` creation remains paused until this branch is fully certified, accepted, squash-merged and exact-new-main post-merge GREEN. The subsequent live order is now fail-closed and non-circular: current-main P3 observe -> P3 prepare -> required recovery evidence -> one App creation in the already accepted private network -> technical-domain bootstrap -> exact-SHA P2 `/livez` plus `/healthz database=READY` proof -> P3 accept -> later P4 canonical-domain/TLS gate. The intended App creation parameters already observed are Dockerfile backend, `main`, autodeploy off, Moscow MSK-1, selected production private network, provider-assigned private App address, `/livez` platform health path and technical Timeweb HTTPS hostname first. `omnicio.ru`, public users and Telegram activation remain later gates.

