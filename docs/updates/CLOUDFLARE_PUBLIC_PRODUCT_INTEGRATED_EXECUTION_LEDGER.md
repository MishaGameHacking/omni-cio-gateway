# Cloudflare Public Product Integrated Execution Ledger

Status: **BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY**

This ledger records branch-local execution state for the active Cloudflare integrated
update. Accepted V10 progress and current-next authority remain in
`knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` on protected `main`, interpreted through
the newest accepted-main evidence chain and accepted amendments.

## 1. Identity

- Update ID: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`
- Title: Cloudflare Public Product System Update
- Execution unit: `INTEGRATED_SYSTEM_UPDATE`
- Branch: `system/cloudflare-public-product`
- Accepted base SHA: `2106f1b1792bc710c8eaa68d6be87e04455c0263`
- Current accepted-main SHA rechecked before CF-D source work:
  `2106f1b1792bc710c8eaa68d6be87e04455c0263`
- OWNER authority / START evidence: accepted Amendments 14 and 15 plus canonical
  current status
- GitHub dashboard issue: `#412`
- Final integrated DRAFT PR: `#413`
- Governing contracts: Amendments 12, 14 and 15 plus the integrated-update,
  Cloudflare-platform, Cloudflare-public-product and release-acceptance contracts

## 2. Member milestones — ordered

| Order | Member WP/increment | State | Branch-local Exit evidence | Notes |
|---:|---|---|---|---|
| 1 | CF-A / `CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` | DONE | Source-controlled verifier contract, shards and governance checks passed | No provider mutation |
| 2 | CF-B / `CLOUDFLARE-RUNTIME-COMPATIBILITY` | DONE | Worker, Static Assets, Container, Python/Node and Neon compatibility accepted | Protected V9 recovery retained |
| 3 | CF-C / `CLOUDFLARE-CANDIDATE-DEPLOYMENT` | DONE | Exact-head Cloudflare staging Worker + Container, isolated Neon PostgreSQL 18 runtime role, exact-SHA release/health/database acceptance and trigger quarantine passed | Production promotion not performed |
| 4 | CF-D / `CLOUDFLARE-PUBLIC-CUTOVER` | IN PROGRESS | Post-merge release/cutover source boundary is being added; production mutation remains forbidden on the DRAFT branch | Actual production promotion is post-merge only |

Internal milestone `DONE` is branch-local implementation progress only. It does not
advance accepted V10 percentage, change `main`, unlock another major update, activate
public multi-user access or authorize broker/Real execution.

## 3. Current execution state

- Current exact work item: source-control the CF-D post-merge exact-main release gate,
  gated production Workers Build, production database-secret bootstrap/reuse,
  canonical `.ru` Custom Domain attachment, live exact-SHA acceptance and bounded
  rollback path.
- Current branch head before this CF-D source batch:
  `bf26ffcaaf1753c2b8b364990be5685f3019e458`.
- Exact-head state on that parent: all current GitHub Actions runs are `success`,
  including Cloudflare Provider Readiness and real CF-C Candidate Deployment;
  independent Sonar/Semgrep/Gitar review is clear and unresolved blocking review
  threads are zero.
- CF-C evidence is real provider evidence, not synthetic GREEN: Workers Builds,
  Container rollout, isolated Neon staging, exact release SHA and database health
  reached accepted terminal state, with staging trigger quarantine/cleanup.
- CF-D architecture correction discovered during full release-path review:
  Cloudflare direct Git production auto-deploy on each `main` push would race ahead
  of required exact-main post-merge gates, so it is forbidden. Production release is
  instead triggered only after `Regression Shield` completes and rechecks all observed
  same-SHA `push` workflows plus current `main` immediately before promotion.
- Lenovo has no accepted local Container build dependency for CF-D. Production
  Worker+Container deployment therefore reuses Cloudflare Workers Builds through a
  temporary sentinel-gated manual exact-main trigger that is quarantined after the
  terminal build.
- A provider-side production Build can outlive a failed/killed GitHub job. Before the
  rollback snapshot CF-D validates/deletes only its owned sentinel trigger and cancels
  every nonterminal Build targeting the exact production Worker; unknown triggers fail
  closed. The production runner repeats quarantine before creating the new trigger.
- Production PostgreSQL runtime credentials are bootstrap-once/reuse. Re-provisioning
  and rotating the production runtime password on every release is explicitly
  forbidden because it could invalidate the currently serving Worker before the next
  release is accepted.
- First production creation uses a 503/no-store Worker bootstrap anchor with
  `workers_dev=false`, then installs the database secret, quarantines stale provider
  activity, snapshots the active version for rollback, deploys the exact accepted main
  and only then attaches the canonical Custom Domain.
- WEB VISUAL remains excluded. Telegram/VK public activation remains outside this
  infrastructure cutover. Broker write/Real execution remain OFF.
- Main drift since accepted base: NONE at the pre-source recheck.

## 4. Integration-ready preflight

- [ ] Every required branch-local source milestone is complete on the new CF-D head.
- [x] CF-A complete.
- [x] CF-B complete.
- [x] Real CF-C staging acceptance complete on the parent exact head.
- [x] CF-D root-cause/blast-radius/producer-consumer review complete before source change.
- [x] Direct Cloudflare Git production auto-deploy rejected as a post-merge-gate bypass.
- [x] Local-Docker dependency rejected; gated Cloudflare Workers Builds retained.
- [x] Production DB credential-rotation outage mode addressed by bootstrap-if-missing reuse.
- [x] Custom-domain authority, exact-main recheck and rollback boundaries designed fail-closed.
- [x] Stale provider-build race reviewed; production Builds are quarantined before rollback snapshot.
- [x] Security/authority/secret/recovery consequences reviewed.
- [x] Mandatory split triggers evaluated below.
- [ ] New CF-D source batch focused checks pass.
- [ ] Fresh new-head DRAFT checks/reviews all conclude `success`.
- [ ] Ledger may be marked `INTEGRATION_READY`.

CF-D focused preflight is designed to include:

```text
python -m py_compile <new/changed CF-D Python files>
python -m unittest \
  tests.test_v10_cloudflare_release_acceptance \
  tests.test_v10_cloudflare_postmerge_release_gate \
  tests.test_v10_cloudflare_production_manager \
  tests.test_v10_cloudflare_gated_production \
  tests.test_v10_cloudflare_worker_anchor_environments \
  tests.test_v10_cloudflare_gated_candidate_source_branch
python scripts/check_v10_cloudflare_release_acceptance.py
python scripts/check_v10_cloudflare_candidate_delivery.py
python -m ruff check <changed Python files>
python -m ruff format --check <changed Python files>
```

## 5. Mandatory split-trigger review

| Trigger | State | Evidence / consequence |
|---|---|---|
| DB/migration ordering | CLEAR | No schema migration. Production role is provisioned only if the Worker secret is absent; existing production credentials are reused. |
| Security/authority transition | CLEAR / POST-MERGE BOUNDARY | Production mutation is authorized only after protected-main merge and exact-main post-merge SUCCESS; DRAFT branch cannot promote. |
| Dependency/toolchain boundary | CLEAR | Existing pinned Wrangler/Containers/Node/Python provider toolchain is reused. |
| OWNER/provider action | CLEAR / POSSIBLE EXTERNAL BLOCKER | Source is autonomous. Missing canonical domain/zone secret custody remains a bounded OWNER/provider prerequisite if not already configured. |
| Live/temporal evidence | CLEAR / POST-MERGE BOUNDARY | Exact production live evidence must be gathered after merge; branch-local source checks cannot synthesize it. |
| Production cutover | TRIGGERED AS TIMING BOUNDARY | Amendment 15 explicitly keeps actual CF-D mutation after merge; it does not require a separate implementation branch. |
| Real-money authority | N/A | Broker write and Real execution remain disabled. |
| Reviewability limit | CLEAR | CF-D source is one coherent release/cutover boundary with dedicated tests and deterministic guards. |

Split decision: `NO_ADDITIONAL_BRANCH_SPLIT_REQUIRED`; provider production mutation remains
an explicit post-merge timing/authority boundary.

## 6. Protected authority checklist

- [x] Protected V9 entrypoint remains `app:app`.
- [x] `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- [x] `trading_methods=false`, `REAL_TRADING_ENABLED=false` and broker write OFF remain unchanged.
- [x] No transfer, withdrawal, margin, leverage or uncovered-short authority is introduced.
- [x] Tenant isolation and PostgreSQL FORCE RLS remain fail-closed.
- [x] No real credential value, database DSN, private portfolio payload or full provider
  identifier is added to source, PR comments or artifacts.
- [x] Production database DSN is read only from a runner-temporary file and uploaded as
  Cloudflare secret text; it is never printed.
- [x] Direct Cloudflare Git production auto-deploy is forbidden.
- [x] Persistent production Workers Build triggers are forbidden.
- [x] Production `workers.dev` exposure is disabled; staging `workers.dev` remains enabled
  only for isolated candidate acceptance.
- [x] Deterministic Core remains financial truth authority.

## 7. Verification batches / HEAD FREEZE

### Accepted parent checkpoint before CF-D source batch

- Verification SHA: `bf26ffcaaf1753c2b8b364990be5685f3019e458`
- DRAFT/READY state: DRAFT.
- Terminal conclusions: all current exact-head GitHub Actions runs `success`, including
  Cloudflare Provider Readiness and Candidate Deployment; Sonar Quality Gate passed;
  Semgrep and Gitar passed; unresolved blocking review threads = 0.
- CF-C provider acceptance: PASS.
- Production promotion: NOT PERFORMED.
- Prior final evidence invalidated by this CF-D source commit: YES.

### CF-D source batch

- Verification SHA: assigned when the coherent source batch is published.
- DRAFT/READY state: DRAFT / HEAD FREEZE begins after publication.
- Applicable checks: full fresh exact-head repository workflows plus independent review.
- Terminal conclusions: PENDING until publication and verification.

## 8. CF-D root-cause inventory and permanent hardening

| Finding / class | Root cause / risk | Permanent boundary |
|---|---|---|
| Direct Git production deployment races governance | Cloudflare Git production branch deploys on `main` push before repository post-merge gates can finish | Production Git auto-deploy forbidden; GitHub `workflow_run` release waits for Regression Shield and every observed same-SHA push workflow |
| Current-main drift during long release | A newer `main` may land while a prior release is preparing | Current `main` SHA is rechecked before candidate and immediately before production promotion; superseded SHA fails closed |
| Local production Container build is not an accepted dependency | Lenovo candidate path deliberately uses Cloudflare Builds because local Container tooling is absent/untrusted | Production image build/deploy also uses a temporary gated Cloudflare Workers Build with exact `main` SHA |
| Persistent build trigger could bypass release gate | A normal production branch trigger would reintroduce auto-deploy | Production trigger uses an impossible sentinel branch, manual exact-main start only, terminal cleanup; unknown trigger authority fails closed |
| Stale provider Build can race a later rollback snapshot | A killed runner does not prove an already-started Cloudflare Build stopped | Pre-snapshot quarantine cancels all nonterminal Builds for the exact production Worker after trigger-authority validation; normal runner repeats quarantine before new trigger creation |
| Production DB role rotation could interrupt current release | Re-provisioning changes password before next Worker is accepted | Probe Cloudflare secret; reuse existing credential. Provision/rotate only on first missing-secret bootstrap |
| First production Worker cannot receive secret before it exists | Secret API is script-scoped | Create 503/no-route bootstrap Worker with `workers_dev=false`, then upload secret, snapshot rollback version, then deploy |
| Failed production live acceptance can leave bad version active | Container rollout is not treated as equivalent to health acceptance | Capture prior 100% Worker version before mutation and explicitly roll back to it on deploy/domain/live failure |
| Wrong domain/zone could capture another service | Host/zone metadata is provider authority | Require one `.ru` zone, host within that zone, exact Worker service match and exact zone ID/name; mismatch fails closed |

## 9. Main-drift record

- Accepted main before CF-D source batch:
  `2106f1b1792bc710c8eaa68d6be87e04455c0263`.
- Intersects this update: NO.
- Re-anchor required before source publication: NO.
- Production workflow independently rechecks current main at runtime before any promotion.

## 10. Final lifecycle

- [ ] `INTEGRATION_READY`
- [x] Integrated implementation branch and DRAFT PR exist.
- [x] CF-A branch-local DONE.
- [x] CF-B branch-local DONE.
- [x] CF-C branch-local real provider acceptance DONE on parent exact head.
- [ ] CF-D source/release boundary complete and exact-head verified.
- [ ] Fresh unchanged-head READY verification all `success`.
- [ ] Squash merge into protected `main`.
- [ ] Exact-new-main Regression Shield and every applicable post-merge gate `success`.
- [ ] Exact-main isolated staging rehearsal passes post-merge.
- [ ] CF-D gated production Workers Build succeeds.
- [ ] Canonical `.ru` Custom Domain attached/verified.
- [ ] Exact-main `/api/v10/release` and `/healthz` live acceptance passes.
- [ ] Russian-network/no-VPN public-path acceptance recorded without private data.
- [ ] Canonical current status transitions only after the entire accepted evidence chain.

## 11. Handoff

- Exact parent head before CF-D source batch:
  `bf26ffcaaf1753c2b8b364990be5685f3019e458`.
- Current milestone: CF-D source/release boundary.
- What is complete: CF-A, CF-B, real CF-C staging acceptance and all parent exact-head
  source/review checks.
- What remains: publish one coherent CF-D source batch, fresh exact-head DRAFT review/CI,
  mark `INTEGRATION_READY`, fresh READY cycle, squash merge, exact-main post-merge gates,
  gated production cutover, live/custom-domain/public-path acceptance and status closeout.
- Next lawful action after source publication: observe all applicable exact-head checks to
  terminal state under HEAD FREEZE; do not call the branch GREEN while any applicable
  check is failed, pending, queued, cancelled, skipped or neutral.

This document is not a competing current-status authority.
