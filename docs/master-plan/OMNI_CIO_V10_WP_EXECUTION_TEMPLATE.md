# Omni-CIO V10 — Work Package / Execution Unit Template

**Status:** OWNER-APPROVED PLANNING TEMPLATE  
**Purpose:** every implementation execution unit and every member WP/increment must answer these questions before it is considered ready to code or to advance branch-local milestone state.

This template is deliberately strict. It exists so an authorized developer/AI session does not invent scope, architecture, delivery granularity or acceptance criteria during implementation.

Amendment 12 / Integrated System Update Execution Law adds two valid execution units without changing Master Plan dependency order:

- `FOCUSED_CHANGE` — isolated defect/governance/maintenance/mandatory split;
- `INTEGRATED_SYSTEM_UPDATE` — one coherent OWNER-authorized system update with ordered member WP/increments, one integrated branch and one final PR by default.

Amendment 13 / Live User Operability & Progressive Capability Activation Law additionally requires every user-facing execution unit to distinguish accepted implementation from live-user capability activation. Completed user-facing capability must not wait for unrelated later blocks after all gates that actually own that capability are accepted.

## 1. Execution-unit / WP identity

- Execution unit: `FOCUSED_CHANGE` / `INTEGRATED_SYSTEM_UPDATE`
- Update ID/title, if integrated:
- Block:
- WP/member milestone:
- Member milestone order, if integrated:
- Authorized by current program status: YES/NO
- Exact OWNER START evidence, if required:
- Prior dependency/Exit Gate proven by:
- Branch-scoped Execution Ledger path, if integrated:
- GitHub System Update dashboard issue, if integrated:
- User-facing capability IDs affected, if any:
- Capability Activation Ledger/dashboard required: YES/NO + reason

For `INTEGRATED_SYSTEM_UPDATE`, a member milestone may become branch-local `DONE` only after its own internal Exit criteria pass. That state does not advance accepted V10 progress, change `main`, unlock a later major update, authorize public production or authorize broker/Real execution.

For user-facing capability work, an implementation/member milestone PASS also does not by itself mean `LIVE_OPERABLE` or `REAL_MONEY_AUTHORIZED`.

## 2. Accepted baseline

- Accepted `main` SHA:
- Protected V9/V10 runtime baseline:
- Relevant Master Plan/amendment sections:
- Relevant ADRs/contracts:
- Main-drift recheck plan for a long-lived integrated branch:

## 3. Purpose

State the one concrete outcome of this execution unit and, for an integrated update, the one coherent system outcome shared by all member milestones.

## 4. Inputs and prerequisites

List exact prerequisite contracts, files, data fixtures, runtime capabilities and CI gates.

### 4.1 Pre-CI readiness

Define what must be proven **before** an expensive full CI cycle is considered justified:

- cheap deterministic checks;
- focused positive/negative tests;
- static/type/format/compile checks;
- schema/migration/IaC/PowerShell/config validation where applicable;
- dependency/lock validation;
- official current dependency/API review where materially changing an external component;
- secret/private-data guard;
- rollback/recovery review;
- directly coupled producer/consumer/config/workflow review;
- analogous-pattern search where material;
- reasonable adjacent failure-mode review;
- full branch diff review.

Known preflight failures must be fixed before triggering the full exact-head gate.

For `INTEGRATED_SYSTEM_UPDATE`, external publication/verification is forbidden until every required member milestone is complete, mandatory split triggers are clear and the Execution Ledger marks `INTEGRATION_READY`.

### 4.2 OWNER-only prerequisite / handoff contract

If OWNER participation can be required, define it before implementation using `docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md`:

- why the action is genuinely non-delegable;
- exact account/repository/workspace/service/device scope;
- direct official HTTPS link to the exact stable page when available;
- when no stable deep link exists: closest verified official start URL + exact current click path;
- one bounded action only;
- exact expected result;
- explicit STOP conditions;
- adjacent actions that must not be taken;
- exact cost/authority effect before any payment/public-ingress/credential-scope/irreversible confirmation;
- minimum safe non-secret result to return.

The OWNER must not be required to discover the destination page. Routine engineering/CI/debugging/provider automation is not an OWNER prerequisite.

## 5. Existing implementation to reuse

For each material component:

- path/module;
- accepted behavior;
- protecting tests;
- parity ledger ID;
- reuse matrix decision.

No material rewrite begins while its reuse decision is `TBD_AT_OWNING_WP`.

## 6. Allowed changes

List exact domains/directories/interfaces this WP/member milestone may change.

For an integrated update, also list the complete union of allowed changed surfaces so scope creep is visible before publication.

## 7. Explicit non-goals

List adjacent work this WP/member milestone and the parent execution unit must not perform.

## 8. Interfaces/contracts

For every schema/API/tool/event changed:

- name/version;
- producer;
- consumer;
- compatibility rule;
- null/unknown/stale semantics;
- source/time semantics where material.

## 9. Data/persistence effects

- migration required: YES/NO;
- forward migration:
- rollback/forward-recovery rule:
- private-data handling:
- backup/recovery consequence:
- Does expand/migrate/contract or deploy-before-code ordering trigger a mandatory split: YES/NO + evidence

## 10. Security/authority effects

State whether this WP/member milestone changes:

- secret access;
- broker authority;
- OS/runtime privileges;
- GitHub permissions;
- Web/Telegram ingress;
- identity/tenant/session authority;
- AI tool authority;
- Real execution path.

If any boundary changes, reference the threat review/ADR and evaluate the Amendment-12 security/authority mandatory split trigger.

### 10.1 Runtime/hosting and external-provider boundary

For any Web/runtime/provider work state explicitly:

- primary application/runtime host;
- whether the work changes the accepted managed-cloud/public-production boundary;
- whether any provider is access/security transport versus application/private-state hosting;
- whether any recurring paid cloud hosting is proposed and, if so, the exact OWNER-approved authority;
- whether an OWNER/provider action is a mandatory split trigger;
- how the protected V9 Render.com `app:app` baseline remains untouched until its owning parity/decommission gate.

Public-production mutation remains fail-closed. Planning, an Integrated System Update, a GitHub merge or AI output never by itself authorizes provider apply, public cutover or a paid resource.

### 10.2 Progressive Capability Activation / real-user boundary

For every user-facing capability affected, record its accepted current state and proposed post-acceptance state using exactly one of the Amendment-13 states for implemented/activation-tracked capabilities:

- `IMPLEMENTED`;
- `LIVE_OPERABLE`;
- `BLOCKED_EXTERNAL`;
- `REAL_MONEY_AUTHORIZED`.

If the capability is not yet implemented, do not assign a state merely to imply progress.

For each capability state decision record:

- capability ID;
- current state;
- proposed state;
- technical/security owning gates;
- specific real external blockers, if any;
- real-provider/broker/legal/privacy/secret-custody/capacity/monitoring evidence required;
- whether real USER operability can safely be proven on the one canonical Omni-CIO Web;
- real-user acceptance path;
- multi-user/tenant-isolation negative evidence where applicable;
- monitoring/revoke/rollback/recovery evidence;
- truthful UI state when not live;
- kill-switch/current runtime availability separately from accepted capability state.

`V10 is not finished yet` is not a valid external blocker.

For broker capability record explicitly:

- READ remains independent from unfinished Real execution;
- a TRADE/full-access credential is never used as READ fallback;
- `TRADE credential connected/verified` does not authorize broker submit;
- execution eligibility remains `VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`;
- account mismatch fails closed;
- `LIVE_OPERABLE` does not imply `REAL_MONEY_AUTHORIZED`;
- real submit remains forbidden until the owning execution/Real-money gate accepts it;
- transfer/withdrawal/margin/uncovered-short authority is not expanded.

A material activation transition must use `docs/updates/V10_CAPABILITY_ACTIVATION_LEDGER_TEMPLATE.md` plus the GitHub capability activation dashboard. Both are working evidence only and never replace canonical current status.

## 11. Normal-path acceptance tests

List deterministic tests proving the intended behavior.

For user-facing capability that can safely become live, include the applicable real-user path on the canonical deployed Web. Synthetic/provider-double evidence remains engineering evidence and is not a substitute for live-user evidence when live proof is available and required.

## 12. Negative/failure tests

At minimum cover applicable cases:

- invalid input;
- missing dependency;
- stale/partial data;
- duplicate/replay;
- timeout/network failure;
- restart/recovery;
- authorization failure;
- incompatible schema/version;
- secret/private-data leak prevention;
- fail-closed money/authority behavior;
- USER A -> USER B cross-tenant read/write denial for tenant-scoped capability;
- stale/revoked session behavior;
- broker READ/TRADE account mismatch for broker capability;
- live capability temporary safety suspension/kill-switch truthfulness where applicable.

### 12.1 Root-cause / blast-radius plan

For any material defect discovered during this WP/member milestone, define the review method before retrying full CI:

- root cause;
- repository-wide analogous pattern search;
- directly coupled producers/consumers/config/workflows;
- reasonable adjacent failure modes;
- security/authority/recovery impact;
- permanent regression/guard;
- why prior preflight did not catch the failure.

Do not assume a one-line failing location means a one-line defect class.

For an externally published integrated head, apply **HEAD FREEZE** while safe independent checks reach terminal state. Build one consolidated finding inventory, group findings by root cause/defect class, then produce one coherent correction batch rather than one CI cycle per symptom.

## 13. Observability

Define:

- health/status;
- logs (sanitized);
- metrics/job state;
- correlation IDs;
- user-visible degraded state;
- evidence retained for acceptance.

For a `LIVE_OPERABLE` capability, also define how current runtime availability/safety suspension differs from accepted capability state and how the USER sees a truthful bounded reason instead of a silently broken control.

### 13.1 Fault isolation / degraded-mode contract

State how the component fails without causing unnecessary system collapse.

Consider where applicable:

- timeout/deadline;
- bounded retry/idempotency;
- backpressure/circuit breaker;
- durable queue/checkpoint;
- restart/recovery;
- health/readiness/freshness;
- process/service privilege boundary;
- what remains trustworthy when this component is DEGRADED/OFFLINE.

Optional component failure should preserve deterministic Core when safe. Money/security/identity/secret/broker authority always fails closed.

## 14. Integrated publication / mandatory split review

For `FOCUSED_CHANGE`, mark this section `N/A` unless a split question is relevant.

For `INTEGRATED_SYSTEM_UPDATE`, record `CLEAR`, `TRIGGERED` or `N/A` with evidence for every mandatory split trigger:

1. DB/migration ordering;
2. security/authority transition;
3. dependency/toolchain boundary;
4. OWNER/provider action;
5. live/temporal evidence;
6. production cutover;
7. Real-money authority;
8. reviewability limit.

WP numbering alone is not a split trigger. A triggered boundary must be documented in the Execution Ledger and split before publication.

`INTEGRATION_READY`: PASS/FAIL

## 15. CI routing / verification batches

- Cheap/focused preflight commands:
- Fast hosted checks:
- Hosted clean-room compatibility required: YES/NO + reason
- Lenovo authoritative checks:
- GPU AI eval required: YES/NO + reason
- Release/recovery matrix required: YES/NO + reason
- Full exact-head CI may start only after pre-CI readiness: PASS/FAIL
- For integrated work, Ledger `INTEGRATION_READY`: PASS/FAIL

Project GREEN definition for an applicable gate is `success` only. `skipped`, `neutral`, `cancelled`, pending/in-progress states and infrastructure/billing failures do not count as GREEN merge evidence.

If a workflow is not applicable, route/trigger it so it does not appear as a misleading skipped/cancelled gate.

Any commit after final GREEN invalidates prior final evidence and requires the applicable exact-head cycle again.

After a verification SHA is published, **HEAD FREEZE** applies while the safe verification batch is observed. `continue-on-error` must never be used to manufacture GREEN. Safety abort takes precedence if continued execution could expose secrets/private data, reach broker/Real authority, perform destructive migration/provider mutation, create uncontrolled spend or expose another tenant.

Verification batch record:

- exact SHA:
- DRAFT/READY:
- applicable checks and terminal conclusions:
- consolidated findings:
- root-cause groups:
- correction batch SHA, if required:

### 15.1 Files changed / independent review evidence

For every published PR head, record evidence for the **same exact SHA**:

- complete GitHub **Files changed** surface reviewed against accepted base;
- inline review threads and check annotations inspected;
- Sonar, Gitar, SAST/security and any other applicable code/security review outputs inspected;
- every material finding classified against actual code, root cause, blast radius, analogous locations, directly coupled surfaces and adjacent failure modes as applicable;
- real correctness/maintainability/diagnostic/security/review-quality defects fixed and reusable defect classes guarded deterministically;
- bot approval treated as supporting evidence, never a substitute for engineering judgment;
- final manual engineering diff review performed even when independent tools report no findings;
- unresolved blocking review threads = 0.

Any correction commit invalidates both prior final GREEN evidence **and** prior review evidence. The new exact head requires fresh Files changed + review evidence before merge.

Review record:

- exact SHA:
- Files changed review: PASS/FAIL
- independent sources inspected:
- material findings/dispositions:
- unresolved blocking review threads:
- final manual engineering diff review: PASS/FAIL
- fresh after correction commit: YES/NO/N/A

## 16. Rollback/recovery

State exactly how to return to the accepted prior state without losing broker/reconciliation truth.

For a user-facing activation transition, distinguish code rollback, capability-state rollback, runtime kill switch and external/provider revocation. None may leak or lose broker/reconciliation truth.

## 17. Exit Gate

Define a binary PASS/FAIL gate for this WP/member milestone. “Looks good”, “page opens”, or “tests mostly pass” is not sufficient.

For an integrated member milestone, branch-local PASS is not accepted-main completion.

Final merge/normal PR closure requires:

- current exact head;
- all applicable checks actually ran and concluded `success`;
- full diff review;
- complete exact-head GitHub Files changed review;
- applicable inline/check/Sonar/Gitar/SAST/other code-security review outputs inspected and material findings dispositioned;
- final manual engineering diff review after the last code change;
- fresh Files changed + independent review evidence after any correction commit;
- zero unresolved blocking review threads;
- no unresolved P0/P1 blocker;
- required security/recovery evidence;
- all required integrated member milestones branch-local PASS;
- mandatory split review clear;
- final integrated acceptance only after squash merge and exact-main post-merge gates.

Bot approval is supporting independent evidence; it never replaces engineering judgment or the required exact-head CI/security gates.

For each affected user-facing capability, final Exit evidence must also classify:

- accepted implementation state;
- whether the capability remains `BLOCKED_EXTERNAL` or is eligible for `LIVE_OPERABLE`;
- exact external blocker/evidence when blocked;
- real USER end-to-end evidence on canonical Web when live proof is possible and required;
- multi-user/tenant-isolation negatives where applicable;
- monitoring/revoke/rollback/recovery evidence;
- no artificial dependency on unrelated later V10 blocks;
- `REAL_MONEY_AUTHORIZED` only when the full owning execution gate explicitly passes.

## 18. Required acceptance evidence

List exact evidence such as:

- tests/run IDs;
- deterministic fixture results;
- screenshots only when UI visual acceptance is material;
- release manifest/provenance;
- migration/recovery rehearsal;
- parity ledger status change;
- owner approval if specifically required;
- sanitized real-user operability evidence where required;
- sanitized multi-user isolation evidence where applicable;
- capability Activation Ledger/dashboard reference for a material state transition.

OWNER product acceptance is normally **post-merge and post-Regression-Shield**. Before merge, OWNER action is allowed only for a genuinely non-delegable prerequisite needed to make engineering verifiable (account/consent/domain/payment/narrow credential/UAC-admin/physical action/Master Plan decision).

If OWNER action is required, acceptance evidence must also state that the handoff used the verified direct-link/expected-result/STOP/do-not-do/minimum-return contract and did not expose secrets or private runtime URLs.

No real provider/broker secret, Authorization header, full broker account ID or private portfolio payload may be stored as GitHub/CI/activation evidence.

## 19. Documentation/status updates in the same PR

State which files must change with the implementation so GitHub remains the engineering memory.

For `INTEGRATED_SYSTEM_UPDATE`, the branch Execution Ledger and GitHub System Update dashboard are working-state records and must say:

`BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`.

For material capability activation, the Capability Activation Ledger and GitHub dashboard must say:

`WORKING CAPABILITY ACTIVATION STATE — NOT ACCEPTED MAIN AUTHORITY`.

Both classes of working record never replace `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

### 19.1 Failure-learning update

If an unexpected material RED occurred after the branch had been considered preflight-ready, answer:

- Why was the branch believed ready?
- What evidence/assumption was missing?
- What other locations were searched for the same failure class?
- What permanent guard was added?
- Does `docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md` need a reusable entry?

Do not store secrets/private payloads in the ledger.

## 20. Next WP / System Update unlock

Name the next authorized member milestone or next major System Update and the exact evidence that unlocks it.

A later member milestone inside the same authorized integrated update may begin after its required predecessor branch-local Exit criteria pass. A later **major System Update** remains locked until the current integrated PR is merged, required exact-main Regression Shield/owning gates pass, any required OWNER acceptance completes and canonical status transitions from accepted evidence.

Capability activation is separate from Master Plan sequencing: a capability already implemented and accepted may move through its Amendment-13 activation gate without falsely unlocking a later implementation WP/System Update, while an unimplemented later capability remains locked by the plan.

## 21. Scope-discovery rule

Any discovered work not required for this WP/member milestone or parent execution-unit outcome must be classified as one of:

- current blocker/defect with written justification;
- future-WP/System-Update issue/backlog;
- architecture/program amendment requiring OWNER decision;
- mandatory split with evidence.

It must not be silently implemented “while we are here”.
