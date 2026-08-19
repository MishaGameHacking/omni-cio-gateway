# WP22A — Supplemental Linux CI Decision

Status: **DRAFT IMPLEMENTATION / CIRCLECI FREE LINUX GATES PROVEN / LENOVO UNCHANGED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**  
Accepted base `main`: `67223469e0031b94d0ada7c5c0d92e3e4efb8d22`

## 1. Purpose

The existing Lenovo `omni-cio-ci` GitHub self-hosted Windows runner remains the established Windows merge-continuity path. The PROJECT OWNER cannot provide routine physical access or PowerShell interaction, so ordinary engineering must not depend on manual Lenovo intervention.

This decision adds a **supplemental zero-cost hosted Linux clean-room lane**. It does not replace Lenovo, change the production provider, alter GitHub as engineering source of truth or unlock another WP.

Target CI topology:

`GitHub source of truth -> Lenovo self-hosted Windows authoritative gate + CircleCI Free supplemental Linux governance/PostgreSQL portability evidence`

## 2. Non-negotiable boundaries

The supplemental lane must preserve:

- canonical source only in `MishaGameHacking/omni-cio-gateway`;
- PR and exact-head discipline;
- `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- `PUBLIC_MULTI_USER_ENABLED=false` until its owning gate;
- no broker-write expansion;
- no real broker/Telegram/VK/provider/recovery secrets in CI;
- protected V9 rollback;
- WP23+ locked until WP22A Exit Gate;
- no GitHub budget/payment mutation and no paid CircleCI plan.

CircleCI is execution infrastructure only. It is not repository authority, product identity authority, tenant authority, provider-apply authority or production secret custody.

## 3. Why Linux is supplemental rather than a Lenovo replacement

The final accepted WP22A production boundary is managed-cloud Linux/amd64, so an independent Linux clean-room lane adds useful portability evidence for source/governance/Web/API/PostgreSQL work. Windows-only and PowerShell semantics remain materially different and are not silently declared covered by Linux.

GitHub self-hosted execution does not consume GitHub-hosted Actions minutes. Therefore keeping the existing Lenovo runner does not consume the private-repository hosted-minute allowance. The external Linux lane is justified as independent clean-room evidence and as a way to reduce dependence on finite GitHub-hosted capacity, not as a reason to retire working OWNER infrastructure.

## 4. Candidate selection

CircleCI Cloud Free was selected for the bounded supplemental proof because current first-party documentation provides:

- a Free plan with a finite included credit pool and core hosted execution capabilities;
- no requirement to move the canonical repository away from GitHub;
- small hosted Docker/Linux execution;
- Windows execution availability if a future compatibility proof is specifically justified;
- GitHub status reporting for jobs/workflows;
- GitHub integration suitable for the private canonical repository.

The exact external Free-plan credit allowance is mutable provider state and must be revalidated from current CircleCI billing/plan UI or documentation before any capacity estimate. No source contract assumes a permanent monthly credit number.

Azure Pipelines remains a fallback candidate, not an active dependency.

No paid CI provider is authorized.

## 5. Actual proof evidence and failure learning

The PROJECT OWNER completed the unavoidable one-time CircleCI/GitHub repository authorization for only the canonical project. All subsequent diagnosis and source correction was performed through GitHub/CircleCI status evidence without requesting a CircleCI API token or routine OWNER interaction.

Reusable failure learning from the bounded proof:

1. **Future image tag:** the first source probe used `cimg/base:2026.08` before that monthly image existed and failed at environment start. Use only currently published image identities.
2. **Wrong source assertion:** a combined safety probe searched for `trading_methods=false` in the wrong canonical file. The failure domain was split; Linux environment/private checkout and the other immutable markers were independently GREEN; the assertion was corrected to the accepted README boundary.
3. **CircleCI config-expression collision:** a PostgreSQL readiness command used a normal shell/Python heredoc containing `<<`. CircleCI config 2.1 preprocesses `<< ... >>` expressions, so the config failed before creating jobs. The heredoc form was removed from the durable config.
4. **Unpublished PostgreSQL patch-style tag:** direct A/B execution of identical migration/catalog code proved `cimg/postgres:18.4` GREEN while `cimg/postgres:18.4.0` failed. Current public image inventory exposes `18.4`, not `18.4.0`; do not infer an image tag from the upstream PostgreSQL three-part version.
5. **Source-root parity:** the accepted Windows WP13 wrapper explicitly prepends repository root to `PYTHONPATH` before invoking `scripts/rehearse_v10_wp13_persistence.py`. Linux direct-file execution must preserve the same source-root import contract instead of assuming script-directory resolution is equivalent.
6. **Bounded failure-domain proof:** separate Linux jobs proved the Docker executor, private GitHub checkout, hash-locked runtime install, PostgreSQL 18 service, psycopg connectivity/version, migration-race serialization, exact catalog round-trip and concurrent incident revision before collapsing diagnostics back to the durable gate.

Exact head `a9a50eb871e3a7710f83b3323a634b10a7542afa` first proved the bounded source/capacity path GREEN. Exact head `c989ce4a342200e386c64944bb10f0f9a8b537db` then proved both durable jobs GREEN together: `supplemental_linux_governance` and the complete accepted WP13 PostgreSQL-18 rehearsal.

Those heads are historical diagnostic evidence only after any later commit. Final acceptance requires a fresh all-GREEN cycle on the final exact head.

No provider deployment, production mutation, billing mutation or real secret was used by these proofs.

## 6. Durable supplemental gates

### 6.1 Linux governance / source-policy lane

The durable `supplemental_linux_governance` job uses exact Python `3.12.10` on the smallest adequate CircleCI Linux Docker resource class.

It must:

- check out the exact `CIRCLE_SHA1`;
- verify protected V10 safety markers;
- run portable engineering-governance/documentation/public-plan/CI-cost/Regression-Shield contract guards;
- compile those guards;
- run the portable stdlib CI-contract regression tests;
- state explicitly that Lenovo is not replaced and no production/billing/secret mutation occurred.

### 6.2 Linux PostgreSQL 18 portability lane

The durable `supplemental_linux_postgres18` job adds a synthetic PostgreSQL 18.4 service container and reuses the already accepted WP13 persistence rehearsal rather than inventing a second database acceptance model.

It must:

- check out the exact `CIRCLE_SHA1`;
- use exact Python `3.12.10`;
- install runtime dependencies only from the committed hash-locked `requirements.txt`;
- use only a synthetic local CI database/user/password;
- preserve the accepted repository-root Python import boundary with `PYTHONPATH=.`;
- wait with a finite deadline for PostgreSQL readiness;
- verify the PostgreSQL major version is 18 before the rehearsal;
- execute `scripts/rehearse_v10_wp13_persistence.py exercise` unchanged;
- prove migration race serialization, migration replay idempotency, canonical round-trip, Decimal/numeric semantics, append-only rejection, conflicting replay rejection, concurrent write idempotency, owner-scope rejection, content-hash idempotency, bounded cache retention and state/migration digest semantics;
- never use or emit a real database, broker credential or private portfolio payload.

The current CircleCI `cimg/postgres:18.4` linux/amd64 image was verified from the published registry and the durable source pins the proven linux/amd64 manifest digest rather than using `latest`, `current` or the nonexistent `18.4.0` tag.

A green supplemental Linux job is useful independent evidence. It does not replace any applicable Windows-only, PostgreSQL-on-Windows or authoritative Lenovo gate.

## 7. Cost discipline

CircleCI Free is a finite external capacity pool, not permission for unbounded CI multiplication.

Rules:

- use the smallest adequate resource class;
- keep the durable topology compact (governance + one full PostgreSQL portability rehearsal);
- diagnostic fan-out exists only while isolating a failure and must be removed afterward;
- do not duplicate every historical WP workflow mechanically;
- add heavier Linux/Web/PostgreSQL checks only when they materially improve current-WP evidence;
- keep PostgreSQL rehearsal synthetic and bounded;
- exhausted CircleCI credits are an infrastructure condition, never permission to call missing evidence PASS;
- no automatic upgrade or credit-card requirement may be introduced by this decision.

## 8. GitHub Actions routing observation

The current repository still launches multiple historical WP16-WP22 GitHub/Lenovo audits for a PR whose final changed surface is only supplemental CI configuration plus this CI decision record. This is broader than the accepted `irrelevant_workflow_should_not_trigger` target and creates unnecessary queue pressure on a single Windows runner.

This focused PR records the defect but does **not** weaken or silently skip existing workflows merely to obtain a green merge. A separate source-routing correction is warranted only after the current required merge-continuity path is available and the directly coupled workflow path surfaces are reviewed. GitHub path-filter behaviour must also be handled carefully because a required workflow skipped by path filtering can remain Pending.

## 9. Production remains separate

This CI decision does not change the accepted WP22A production boundary. Cloud.ru Evolution remains the selected managed-cloud production/security target under the accepted staged free-first service-selection decision.

CircleCI cannot become the application runtime, durable production database, tenant secret store, product authentication system or production availability anchor.

## 10. Acceptance boundary for this focused CI change

Before merge:

1. obsolete one-off GitHub-hosted Windows probe and temporary diagnostic code are absent from the final diff;
2. durable CircleCI exact-head supplemental Linux governance job succeeds;
3. durable CircleCI exact-head supplemental Linux PostgreSQL 18 rehearsal succeeds;
4. existing applicable GitHub/Lenovo gates execute and succeed on the exact head;
5. full diff/review shows no weakening of Windows authoritative semantics or cost/security guards;
6. zero unresolved blocking threads;
7. fresh READY exact-head cycle succeeds;
8. squash merge;
9. exact-main post-merge verification succeeds.

Only then may PR #336 be updated onto the new accepted `main` and use the supplemental Linux lanes as additional evidence. WP22A Phase 2 acceptance remains governed by `V10_WP22A_EXECUTION_CONTRACT.md`; WP23 remains locked.
