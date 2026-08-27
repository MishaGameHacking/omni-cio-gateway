# Omni-CIO V10 — Integrated System Update Execution Law / Amendment 12

**Status:** OWNER-APPROVED / EFFECTIVE ONLY WHEN ACCEPTED ON PROTECTED `main`  
**OWNER decision:** 2026-08-26  
**Scope:** remaining V10 implementation/governance delivery discipline  
**Product progress effect:** NONE by itself  
**Runtime authority effect:** NONE by itself

## 1. Purpose

This amendment makes the OWNER-approved development model durable GitHub authority so future AI/developer sessions do not depend on chat memory.

The objective is to reduce repeated expensive CI/verification cycles while preserving or strengthening correctness, security, reviewability, recovery and authority boundaries.

The new default unit of delivery is a logically complete **Integrated System Update**, not a mandatory PR per small WP/increment.

This amendment changes delivery granularity only. It does not change the V10 block order, block weights, product scope, financial truth authority, public-production gate, broker permissions, Real-money authority or protected V9 rollback.

## 2. Precedence and explicit supersession

The V10 Master Plan remains the base program and its dependency/Block/WP order remains binding.

Where delivery-granularity wording conflicts, this Amendment 12 explicitly supersedes only the following older defaults:

- `AGENTS.md` / contributor wording that requires one separate focused branch/PR for every individual WP/increment;
- `OMNI_CIO_V10_PROGRAM_LOCK.md` Section 7 only to the extent that “exactly one current WP” requires a separate merge before a directly dependent member milestone inside an OWNER-authorized Integrated System Update;
- Amendment 8 / Engineering Quality wording only to the extent that “focused PR” is interpreted as “one PR per WP” rather than “one coherent PR per authorized execution unit”;
- Amendment 3 / GitHub Pro migration wording that assumes every WP implementation must be an independent PR;
- `V10_WEB_VISUAL_DESIGN_REFRESH_IMPLEMENTATION_BRIEF.md` Section 17 only to the extent that it requires A–G to land as separate PRs.

The design/content/dependency order of WEB-VISUAL A→G remains binding. Only the merge/branch granularity changes.

All non-conflicting requirements from the Program Lock, Master Plan and Amendments 1–11 remain active.

## 3. Execution-unit model

Every material V10 change uses exactly one execution unit:

### 3.1 `FOCUSED_CHANGE`

Use for a genuinely isolated defect, governance/documentation correction, emergency maintenance change, independent migration step or mandatory split boundary.

### 3.2 `INTEGRATED_SYSTEM_UPDATE`

Use when the canonical current status explicitly names one coherent system update and lists its member WP/increments.

An Integrated System Update:

- has one logical product/subsystem outcome;
- has one integrated branch by default;
- has one final PR by default;
- keeps all member WP/increments as ordered internal milestones;
- is not accepted until every required member milestone is complete and the whole update passes the final acceptance lifecycle;
- may not silently absorb unrelated future scope.

Only one V10 product Integrated System Update may be active at a time unless a separate OWNER-approved exception explicitly permits parallel work.

## 4. Internal milestone law

Member WPs/increments do not disappear.

They remain mandatory for:

- architecture and dependency order;
- scope/non-goals;
- contracts/interfaces;
- security/authority review;
- focused positive/negative tests;
- rollback/recovery reasoning;
- internal Definition of Done.

Internal milestones are completed sequentially according to their dependency order.

An internal milestone PASS means only **branch-local implementation progress**. It does not:

- advance accepted V10 percentage;
- change accepted `main`;
- unlock a later major System Update;
- authorize public production;
- authorize broker write or Real execution.

Accepted program progress changes only after the integrated PR lands and required exact-main post-merge verification is GREEN.

## 5. Single Remote Publication Default

Before `INTEGRATION_READY`:

- do not open the final PR;
- do not publish intermediate implementation heads merely to obtain CI feedback;
- do not create temporary verifier commits/branches/PRs;
- do not use GitHub Actions, Sonar, Gitar or the authoritative Windows lane as an interactive debugger;
- perform internal milestone review, focused tests, type/lint/build/static checks, browser checks where applicable, security/data-flow review, regression guards and full-diff inspection first.

The preferred first published implementation state is one coherent completed implementation commit on one integrated branch.

Unpublished local/recovery checkpoints are allowed when needed to prevent work loss. They are not acceptance evidence and must not be used to manufacture verification runs.

A second or later published implementation head is allowed only for a coherent correction batch, base synchronization required by accepted `main`, or a proven mandatory split/repair reason.

## 6. `INTEGRATION_READY` gate

A System Update may be published for external verification only after all of the following are true:

- all required internal milestones are complete;
- known focused/preflight failures are fixed;
- the complete changed surface has been reviewed;
- directly coupled producers/consumers/config/workflows have been reviewed;
- analogous repository patterns have been searched where material;
- reasonable adjacent failure modes have been inspected;
- deterministic regression guards exist for reusable defect classes;
- security/authority/secret/recovery consequences are reviewed;
- mandatory split triggers have been evaluated and none requires separation;
- the branch-local Execution Ledger marks the update `INTEGRATION_READY`.

## 7. HEAD FREEZE and verification-batch observation law

After a verification SHA is published, that head is frozen while the current safe verification batch is observed.

A first ordinary RED is not a signal to immediately push another commit.

The developer/agent must, where safe and technically possible:

1. allow independent applicable checks to reach terminal state;
2. collect all available findings from GitHub Actions, authoritative Windows CI, Sonar, Gitar, SAST/security, browser/E2E and owning gates;
3. create one consolidated finding inventory;
4. group findings by root cause/defect class rather than by first failing line.

For bounded matrix workflows, `strategy.fail-fast: false` may be used when it improves diagnostic completeness without weakening the gate. `continue-on-error` must not be used to make a required failure appear GREEN.

### 7.1 Safety-abort exception

Stop observation immediately and contain the risk if continuing the run can itself create harm, including:

- real secret/private-data exposure;
- unintended broker-write/Real-money path;
- destructive or unsafe migration;
- uncontrolled paid-resource mutation;
- privacy/cross-tenant exposure;
- destructive external/provider mutation.

Safety has priority over diagnostic completeness.

## 8. Systemic diagnosis and batch-correction law

After a RED verification batch, do not fix findings one by one with one CI run per symptom.

Before the next published head, perform for every material defect class:

- root-cause analysis;
- blast-radius analysis;
- repository-wide analogous-pattern search;
- directly coupled producer/consumer review;
- adjacent failure-mode review;
- security/authority/recovery impact review;
- explanation of why the prior preflight missed the defect;
- permanent regression/guard design.

Fix the defect class, not only the symptom. Suppression, weakening coverage, disabling a security check, lowering an acceptance threshold or adding a cosmetic guard solely to obtain GREEN is forbidden.

Then:

`all findings collected -> systemic hardening -> one coherent correction batch -> full focused/local preflight -> one new published head -> fresh complete verification`.

Any new published commit invalidates previous final exact-head GREEN evidence.

## 9. Final acceptance lifecycle

For an Integrated System Update the final protected lifecycle remains:

`INTEGRATION_READY -> one published implementation head -> DRAFT PR -> exact-head applicable verification -> all applicable SUCCESS -> independent review -> corrections if required -> fresh exact-head verification -> READY -> fresh applicable READY SUCCESS -> zero blocking threads -> squash merge -> exact new main -> Regression Shield / owning post-merge gates -> ACCEPTED`.

Project GREEN remains stricter than generic GitHub semantics. For an applicable V10 gate, only `success` is GREEN. `failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` are not accepted GREEN evidence.

Required checks must bind to the current exact head. Historical GREEN or an earlier SHA is never final evidence.

## 10. Execution Ledger and GitHub dashboard law

Every `INTEGRATED_SYSTEM_UPDATE` must have both:

1. a branch-scoped tracked Execution Ledger using `docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md`;
2. one GitHub-visible System Update issue/dashboard using the repository template and Markdown task lists.

The Ledger/dashboard must show at minimum:

- accepted base SHA;
- update ID/title;
- member milestones in order;
- `DONE / IN_PROGRESS / TODO / BLOCKED` state;
- current exact work item;
- next exact action;
- blockers;
- known defects;
- internal focused/preflight evidence;
- mandatory split-trigger review;
- protected authority checklist;
- verification batches and exact SHAs;
- consolidated findings/root causes;
- correction batches;
- final DRAFT/READY/merge/post-merge state.

Updating a checkbox is never by itself a reason to create/push a source commit.

The dashboard and branch Ledger are working-state records only. They must explicitly state:

`BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`.

`knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` remains the only accepted current V10 progress/current-next execution ledger.

## 11. Mandatory split triggers

“One large branch” is the default, not an excuse to cross a real safety or rollout boundary.

The update must split when evidence shows one or more of these triggers:

1. **DB/migration ordering:** deploy-before-code, expand/migrate/contract, or backward-compatibility sequencing requires separate accepted states.
2. **Security/authority transition:** a later part changes identity, tenant, secret, broker, AI-tool, OS/admin or Real-money authority and requires independent acceptance first.
3. **Dependency/toolchain migration:** a material runtime/toolchain/dependency change needs isolated compatibility/rollback evidence before dependent product work.
4. **OWNER/provider action:** a genuinely non-delegable secret/account/payment/provider action is required before later implementation can be proven.
5. **Temporal/live evidence:** Shadow Mode, soak, production observation or other evidence must accumulate before the next authority state can lawfully begin.
6. **Production cutover:** staged public rollout/rollback requires separate accepted release states.
7. **Real-money authority:** broker submit/Real execution activation may never be smuggled into an ordinary integrated feature branch.
8. **Reviewability limit:** the diff has become objectively unsafe to review/validate as one coherent unit.

A split must be documented in the Execution Ledger with evidence. WP numbering alone is not a split trigger.

## 12. Main-drift rule

Long-lived integrated work may not ignore accepted `main` changes.

Before `INTEGRATION_READY`, re-check current accepted `main`. If a critical/maintenance/governance change landed:

- determine whether it intersects the update;
- re-anchor to the new accepted base when required;
- re-run affected internal milestones/preflight;
- record the new base/effect in the Ledger.

After publication, any base synchronization creates a new head and requires fresh exact-head evidence.

## 13. Approved grouping direction for remaining V10

This is delivery grouping, not automatic implementation authorization.

### 13.1 Prepared first System Update

`V10 WEB VISUAL SYSTEM UPDATE`:

`WEB-VISUAL-A -> B -> C -> D -> E -> F -> G`

Default: one integrated branch / one final PR, with A–G as ordered internal milestones.

**Implementation remains PAUSED until a separate explicit OWNER `START V10 WEB VISUAL SYSTEM UPDATE` command is recorded by current authority.**

### 13.2 Future candidates after their sequence unlocks

- `V10 TELEGRAM SYSTEM UPDATE`: WP23–WP26 — default one integrated update.
- `V10 AI CORTEX SYSTEM UPDATE`: WP27–WP33A — default integrated candidate, subject to pre-start mandatory-split review.
- `V10 GUARDIAN SYSTEM UPDATE`: WP34–WP38 — default integrated candidate.

### 13.3 Mandatory caution for later blocks

Block I must not be forced into one branch across WP39 Shadow Mode and subsequent Real-execution authority if the required live evidence/authority boundary has not been accepted.

Block J may require separate release/soak/clean-room evidence states for WP48/WP49 and other physical/temporal gates.

## 14. Protected invariants — unchanged

This amendment never permits weakening or changing by implication:

- protected V9 `app:app` production/recovery baseline;
- V9 rollback availability;
- one canonical Omni-CIO product/repository/Core/Web line;
- `PUBLIC_MULTI_USER_ENABLED=false` until its separate activation gate;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker write OFF until explicitly authorized by its owning future gate;
- READ/optional TRADE tenant credential isolation;
- no transfer/withdrawal/margin/uncovered-short authority;
- deterministic Core as financial truth authority;
- cross-tenant isolation;
- secret/private-data exclusion from GitHub/CI/artifacts;
- public T-Invest fail-closed broker-terms boundary;
- exact-head SUCCESS-only merge policy;
- squash-only protected `main` integration;
- zero unresolved blocking review threads;
- required post-merge Regression Shield/owning gates;
- OWNER-only physical/secret/legal/payment evidence is never synthesized.

## 15. No automatic product START

Acceptance of this governance amendment does **not** start WEB VISUAL, Telegram, AI, Guardian, Real execution or any other product implementation.

After this governance update is post-merge accepted, the canonical state must be:

`PRODUCT IMPLEMENTATION PAUSED`  
`NEXT PREPARED SYSTEM UPDATE: WEB-VISUAL-INTEGRATED / A→G`  
`OWNER START REQUIRED`

A later explicit OWNER START for that exact System Update is required before creating its implementation branch or modifying product source.

## 16. Governance acceptance gate

This Amendment 12 becomes active only when the governance PR containing it and all synchronized live guidance/contracts/guards:

- passes all applicable exact-head DRAFT checks with `success`;
- passes independent review with zero unresolved blocking threads;
- passes a fresh READY exact-head applicable cycle with `success`;
- is squash-merged through protected `main`;
- completes required exact-new-main Regression Shield / governance post-merge checks successfully.

Until then, this file is OWNER-approved proposal content on an unaccepted branch and does not override accepted `main`.
