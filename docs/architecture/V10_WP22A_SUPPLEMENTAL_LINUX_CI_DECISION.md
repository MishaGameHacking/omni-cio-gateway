# WP22A — Supplemental Linux CI Decision

Status: **DRAFT IMPLEMENTATION / CIRCLECI FREE PROBE GREEN / LENOVO UNCHANGED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**  
Accepted base `main`: `67223469e0031b94d0ada7c5c0d92e3e4efb8d22`

## 1. Purpose

The existing Lenovo `omni-cio-ci` GitHub self-hosted Windows runner remains online, autonomous and authoritative for the established Windows merge-continuity path. The PROJECT OWNER cannot provide routine physical access or PowerShell interaction, so ordinary engineering must not depend on manual Lenovo intervention.

This decision adds a **supplemental zero-cost hosted Linux clean-room lane**. It does not replace Lenovo, change the production provider, alter GitHub as engineering source of truth or unlock another WP.

Target CI topology:

`GitHub source of truth -> Lenovo self-hosted Windows authoritative gate + CircleCI Free supplemental Linux governance/portability evidence`

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

The final accepted WP22A production boundary is managed-cloud Linux/amd64, so an independent Linux clean-room lane adds useful portability evidence for source/governance/Web/API work. Windows-only and PowerShell semantics remain materially different and are not silently declared covered by Linux.

GitHub documents self-hosted Actions execution as free of GitHub Actions usage charges. Therefore keeping the already-running Lenovo runner does not consume the private-repository GitHub-hosted minute allowance. The external Linux lane is justified as independent clean-room evidence and as a way to reduce dependence on finite GitHub-hosted capacity, not as a reason to retire working OWNER infrastructure.

## 4. Candidate selection

CircleCI Cloud Free was selected for the bounded supplemental proof because current first-party documentation provides:

- 30,000 monthly credits for personal/non-open-source Free-plan usage;
- no requirement to move the canonical repository away from GitHub;
- hosted Docker/Linux execution;
- GitHub status reporting for jobs/workflows;
- GitHub integration suitable for private repositories.

Azure Pipelines remains a fallback candidate, not an active dependency.

No paid CI provider is authorized.

## 5. Actual proof evidence

The PROJECT OWNER completed the unavoidable one-time CircleCI/GitHub repository authorization for only the canonical project.

Failure learning during the proof:

1. the first source probe used a future monthly `cimg/base:2026.08` tag before that base image existed and failed at environment start;
2. the image was corrected to an available published tag;
3. a combined safety probe then failed because it searched for `trading_methods=false` in the wrong canonical file;
4. the failure domain was split into environment, private checkout and individual marker jobs;
5. Linux environment and private GitHub checkout passed; only the misplaced source assertion failed;
6. the assertion was corrected to the accepted README boundary;
7. exact-head `a9a50eb871e3a7710f83b3323a634b10a7542afa` reported `ci/circleci: supplemental_linux_capacity_probe = success` back to GitHub.

No provider deployment, production mutation, billing mutation or real secret was used by the proof.

## 6. Durable supplemental gate

The proof is promoted to `v10_supplemental_linux_governance` using exact Python `3.12.10` on a small CircleCI Linux Docker executor.

The durable job must:

- check out the exact `CIRCLE_SHA1`;
- verify protected V10 safety markers;
- run portable engineering-governance/documentation/public-plan/CI-cost/Regression-Shield contract guards;
- compile those guards;
- run the portable stdlib CI-contract regression tests;
- state explicitly that Lenovo is not replaced and no production/billing/secret mutation occurred.

A green supplemental Linux job is useful independent evidence. It does not replace any applicable Windows-only, PostgreSQL-on-Windows or authoritative Lenovo gate.

## 7. Cost discipline

CircleCI Free is a finite external capacity pool, not permission for unbounded CI multiplication.

Rules:

- use the smallest adequate resource class;
- keep jobs source/governance focused until measured need justifies heavier Linux work;
- do not duplicate every historical WP workflow mechanically;
- add heavier Linux/Web/PostgreSQL checks only when they materially improve current-WP evidence;
- exhausted CircleCI credits are an infrastructure condition, never permission to call missing evidence PASS;
- no automatic upgrade or credit-card requirement may be introduced by this decision.

## 8. Production remains separate

This CI decision does not change the accepted WP22A production boundary. Cloud.ru Evolution remains the selected managed-cloud production/security target under the accepted staged free-first service-selection decision.

CircleCI cannot become the application runtime, durable database, tenant secret store, product authentication system or production availability anchor.

## 9. Acceptance boundary for this focused CI change

Before merge:

1. remove obsolete one-off GitHub-hosted Windows probe material from the final diff;
2. durable CircleCI exact-head supplemental Linux governance job succeeds;
3. existing applicable GitHub/Lenovo gates execute and succeed on the exact head;
4. full diff/review shows no weakening of Windows authoritative semantics or cost/security guards;
5. zero unresolved blocking threads;
6. fresh READY exact-head cycle succeeds;
7. squash merge;
8. exact-main post-merge verification succeeds.

Only then may PR #336 be updated onto the new accepted `main` and use the supplemental Linux lane as additional evidence. WP22A Phase 2 acceptance remains governed by `V10_WP22A_EXECUTION_CONTRACT.md`; WP23 remains locked.
