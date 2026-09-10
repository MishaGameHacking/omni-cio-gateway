# Cloudflare Public Product Integrated Execution Ledger

Status: **BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY**

This is the branch-scoped execution ledger required by the accepted Integrated System
Update law. Accepted V10 product progress/current-next authority remains in
`knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` on protected `main`, interpreted through
the newest accepted-main evidence chain and accepted amendments.

## 1. Identity

- Update ID: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`
- Title: Cloudflare Public Product System Update
- Execution unit: `INTEGRATED_SYSTEM_UPDATE`
- Branch: `system/cloudflare-public-product`
- Historical integrated-update base: `2106f1b1792bc710c8eaa68d6be87e04455c0263`
- Final-convergence accepted base: `6b28198550adc09a001de8779df900b13caa5c42`
- Current accepted `main` rechecked immediately before this repair batch:
  `6b28198550adc09a001de8779df900b13caa5c42`
- OWNER authority / START evidence: accepted Amendments 14 and 15 plus the canonical
  current status/evidence chain.
- Green Checkpoint authority: accepted Amendment 16.
- GitHub dashboard issue: `#412`
- Current final integrated DRAFT PR: `#478`
- Historical predecessor PR: `#413`
- Governing contracts: Amendments 12, 14, 15 and 16 plus the integrated-update,
  Cloudflare-platform, Cloudflare-public-product, Green Checkpoint and release-acceptance
  contracts.

## 2. Ordered member milestones

| Order | Member WP/increment | Branch-local state | Evidence / boundary |
|---:|---|---|---|
| 1 | CF-A / `CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` | DONE | Source-controlled verifier contract, shards and governance guards accepted branch-locally. |
| 2 | CF-B / `CLOUDFLARE-RUNTIME-COMPATIBILITY` | DONE | Worker, Static Assets, Container, pinned Python/Node delivery toolchain and Neon PostgreSQL 18 compatibility proven; protected V9 recovery retained. |
| 3 | CF-C / `CLOUDFLARE-CANDIDATE-DEPLOYMENT` | DONE | Real Cloudflare staging Worker + Container, staging PostgreSQL 18 runtime binding, exact-SHA release/health/database acceptance and trigger quarantine succeeded on branch checkpoints. |
| 4 | CF-D / `CLOUDFLARE-PUBLIC-CUTOVER` | SOURCE COMPLETE / CERTIFICATION IN PROGRESS | Post-merge exact-main release gate, direct release-control DB bootstrap, gated production Workers Build, Custom Domain, live acceptance and rollback source are implemented. Production mutation remains post-merge only. |

Internal milestone state is branch-local only. It does not advance accepted V10
percentage, unlock WP23+, activate public multi-user mode, or authorize broker/Real
execution.

## 3. Current exact work item

Current state is `RED_REPAIR_ONLY` under Amendment 16 until the replacement SHA created
by this repair batch completes full exact-head certification.

The immediately preceding head is:

`c8bb15e0a1cdf5179c4e5b27ef7b6cd59b3ac506`

Its authoritative Windows merge-gate run `34452823345` proved all of the following
before stopping:

- repository/CI policy contracts: PASS;
- PostgreSQL 18 runtime-role rehearsal: PASS;
- compile: PASS;
- Ruff check and format check: PASS;
- mypy: PASS;
- full protected regression suite: PASS (`3042` tests plus subtests);
- branch coverage: PASS (`62.2%`, threshold `>=60%`);
- dependency audit: PASS;
- SAST: PASS;
- exact-head Sonar Quality Gate through the independent governance lane: PASS.

The one deterministic RED finding was the tracked-content `detect-secrets` Secret
Keyword hit on a non-secret source-marker constant in
`tests/test_v10_cloudflare_staging_secret_reuse_preflight.py`. FL114 records the defect
class and prevention law. This repair renames the marker semantically and does not
suppress or weaken scanning.

The exact replacement SHA is recorded in PR/dashboard evidence after publication because
a tracked document cannot truthfully self-reference the commit that contains itself.

## 4. Final-convergence defect inventory

| Failure class | Root cause | Permanent correction / guard |
|---|---|---|
| Stable staging DB authority gated by management API | Existing staging runtime binding was not treated as sufficient stable authority | Probe/reuse existing runtime binding first; Neon management recovery only when missing; no routine password rotation. FL110. |
| Production bootstrap used unnecessary public staging relay | Trusted release control already possessed authenticated bootstrap destination evidence | Exact-SHA custody hands a bounded provider target descriptor to release control; GitHub OIDC calls the Neon Function directly. FL111. |
| Direct-bootstrap boundary needed stronger custody constraints | Initial direct handoff retained too much destination material and test fixtures resembled credentials | Persist only bounded branch/cell descriptor in restricted `RUNNER_TEMP`; derive hostname locally; use runtime-generated synthetic fixtures. FL112. |
| TLS trust policy implicit to static analysis | Secure runtime defaults were not explicit enough to prove the minimum protocol policy | Explicit `PROTOCOL_TLS_CLIENT`, minimum TLS 1.2, default server-auth trust roots, hostname verification and certificate requirement. FL113. |
| Secret scanner marker-name collision | Non-secret command marker used credential-shaped variable naming | Rename to runtime-binding marker semantics; retain mandatory tracked-content scan unchanged. FL114. |
| Direct Git production deployment could race governance | Provider Git deployment could promote before exact-main post-merge gates finish | Direct Git production auto-deploy forbidden; release begins only from gated post-merge authority. |
| Current-main drift during release | Long release could target superseded `main` | Exact current-main recheck before candidate and immediately before production promotion. |
| Persistent Build trigger could bypass release gate | Normal production branch trigger reintroduces auto-deploy | Temporary sentinel-gated exact-SHA manual trigger only; terminal quarantine; unknown trigger authority fails closed. |
| Stale provider Build could race rollback snapshot | A terminated GitHub job does not prove an already-started provider Build stopped | Pre-snapshot production Build quarantine and repeat quarantine before new trigger. |
| Production DB role rotation could interrupt serving release | Rotating on each release can invalidate currently serving Worker | Bootstrap only if production runtime binding is missing; otherwise reuse without rotation. |
| Failed live acceptance could leave bad version active | Container rollout alone is not health acceptance | Snapshot prior 100% deployment and perform bounded rollback on deploy/domain/live failure. |
| Wrong domain/zone could capture another service | Domain metadata is provider authority | Require canonical `.ru` host/zone/service relationship; mismatch fails closed. |

## 5. Integration-ready preflight

- [x] CF-A complete.
- [x] CF-B complete.
- [x] Real CF-C staging acceptance complete on branch checkpoints.
- [x] CF-D source implementation complete.
- [x] Root-cause, blast-radius, analogous-pattern and producer/consumer reviews completed for each material RED class.
- [x] Deterministic regression guards exist for reusable defect classes.
- [x] Direct Cloudflare Git production auto-deploy remains forbidden.
- [x] Production database bootstrap is least-privilege, exact-SHA/OIDC bound, bootstrap-if-missing and fail-closed.
- [x] Provider target handoff is bounded, private runner custody and non-artifacted.
- [x] Explicit verified TLS client policy is source-controlled.
- [x] Custom-domain authority, exact-main recheck and rollback boundaries are fail-closed.
- [x] Security/authority/secret/recovery consequences reviewed.
- [x] Mandatory split triggers reviewed; no additional implementation branch split is required.
- [x] No WEB-VISUAL, Telegram/VK, AI/Cortex, broker-write or Real-money scope absorbed.
- [ ] Replacement exact-head checkpoint `CERTIFIED_GREEN`.
- [ ] Complete final Files Changed / independent review remains clear on the replacement SHA.

Source implementation is `INTEGRATION_READY` for final external exact-head certification.
This is not a GREEN claim and not accepted-main authority.

## 6. Mandatory split-trigger review

| Trigger | State | Evidence / consequence |
|---|---|---|
| DB/migration ordering | CLEAR | No schema migration. Existing runtime credentials are reused; production bootstrap occurs only if the Worker binding is absent. |
| Security/authority transition | CLEAR / POST-MERGE BOUNDARY | Production mutation is authorized only after protected-main merge and exact-main post-merge SUCCESS. |
| Dependency/toolchain boundary | CLEAR | Accepted pinned Wrangler/Containers/Node/Python/PostgreSQL toolchain reused; no modernization. |
| OWNER/provider action | CLEAR / EXTERNAL IF MISSING | Source is autonomous. Missing provider/domain custody would remain an external prerequisite rather than a code bypass. |
| Live/temporal evidence | POST-MERGE BOUNDARY | Exact production evidence must be gathered after merge and cannot be synthesized branch-locally. |
| Production cutover | TIMING BOUNDARY | Amendment 15 explicitly keeps actual CF-D mutation after merge; no separate implementation branch is required. |
| Real-money authority | N/A | Broker write and Real execution remain OFF. |
| Reviewability limit | CLEAR | Current PR is one coherent Cloudflare/Neon release-control convergence unit. |

Split decision: `NO_ADDITIONAL_BRANCH_SPLIT_REQUIRED`.

## 7. Protected authority checklist

- [x] Protected V9 entrypoint remains `app:app`.
- [x] `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- [x] `trading_methods=false`, `REAL_TRADING_ENABLED=false` and broker write OFF remain unchanged.
- [x] No transfer, withdrawal, margin, leverage or uncovered-short authority is introduced.
- [x] Neon PostgreSQL 18 remains relational truth; no D1 replacement or speculative Hyperdrive is introduced.
- [x] Tenant isolation / PostgreSQL RLS and FORCE RLS remain fail-closed.
- [x] No real credential, DSN, provider identifier, private portfolio payload or private Function hostname is added to source, PR text or artifacts.
- [x] Production DSN remains restricted runner-temp custody and is uploaded only as Cloudflare secret text; it is never printed.
- [x] Direct Cloudflare Git production auto-deploy is forbidden.
- [x] Persistent production Workers Build triggers are forbidden.
- [x] Production `workers.dev` exposure remains disabled.
- [x] Deterministic Core remains financial truth authority.

## 8. Green Checkpoint history

- `0be132372afa902368b4176ee0700f5b68d75903`: stable staging authority reuse; real Provider Readiness and CF-C candidate SUCCESS.
- `0ce9fbb49ebd5c235b5fd102e0e50ff0c6407490`: direct release-control bootstrap implementation; deterministic module wiring defect found before provider mutation.
- `6caa7bf80946c0a4f3e7627087b66c3ce2d37a78`: wiring repair; real Provider Readiness and staging Worker + Container acceptance SUCCESS; later formatter/Sonar findings superseded final certification.
- `3da2e1c2b9d3f866a45007ca6fbdd7aaefddde50`: custody/security hardening; Sonar identified explicit TLS-policy and cognitive-complexity findings.
- `c8bb15e0a1cdf5179c4e5b27ef7b6cd59b3ac506`: explicit TLS policy + decomposition; Sonar/governance SUCCESS, protected merge gate RED only at FL114 tracked-content scan finding.
- Replacement checkpoint: exact SHA recorded externally after publication; state `PENDING_FULL_RECERTIFICATION` until every applicable exact-head gate reaches terminal SUCCESS.

Every earlier exact-head result is historical after a content-changing repair.

## 9. Main-drift record

- Accepted `main` at final-convergence branch creation:
  `6b28198550adc09a001de8779df900b13caa5c42`.
- Accepted `main` immediately before this repair batch:
  `6b28198550adc09a001de8779df900b13caa5c42`.
- Drift intersecting this update: NONE at the recheck.
- Re-anchor required before publication: NO.
- The production workflow independently rechecks current `main` immediately before mutation.

## 10. Final lifecycle

- [ ] Replacement exact CF-D checkpoint `CERTIFIED_GREEN`.
- [x] Branch-local source implementation `INTEGRATION_READY` for final certification.
- [x] Integrated implementation branch and DRAFT PR exist.
- [x] CF-A branch-local DONE.
- [x] CF-B branch-local DONE.
- [x] CF-C branch-local real provider acceptance DONE.
- [x] CF-D source/release boundary complete.
- [ ] Final independent review / complete Files Changed clear; unresolved blocking threads = 0.
- [ ] PR transition to READY on unchanged certified head.
- [ ] Any READY-state applicable checks conclude `success` on the exact head.
- [ ] Squash merge into protected `main`.
- [ ] Exact-new-main Regression Shield, Engineering Governance and every applicable post-merge gate `success`.
- [ ] Exact-main isolated staging rehearsal passes post-merge.
- [ ] Direct GitHub-OIDC -> Neon Function production bootstrap succeeds if the production runtime binding is absent.
- [ ] CF-D gated production Worker + Container build succeeds.
- [ ] Canonical `.ru` Custom Domain attached/verified.
- [ ] Exact-main `/api/v10/release`, container-source and `/healthz database=READY` live acceptance passes.
- [ ] Russian-network/no-VPN public-path evidence recorded if still required by current accepted authority.
- [ ] Canonical current status/closeout updated only from the complete accepted evidence chain.

## 11. Handoff

- Accepted main/base: `6b28198550adc09a001de8779df900b13caa5c42`.
- Current PR: `#478`.
- Pre-repair RED head: `c8bb15e0a1cdf5179c4e5b27ef7b6cd59b3ac506`.
- Current milestone: CF-D final exact-head certification and post-merge public cutover.
- Completed: CF-A, CF-B, real CF-C, CF-D source path, direct control-plane bootstrap architecture, provider target custody, explicit TLS policy, rollback/domain/release guards.
- Current repair: FL114 non-secret test-marker naming collision; no scanner suppression or gate weakening.
- Next lawful action after publication: full replacement-SHA exact-head certification; no unrelated feature work while RED.
- Post-certification action: READY -> squash merge -> exact-new-main gates -> gated CF-D production release/live acceptance.

This document is not a competing current-status authority.
