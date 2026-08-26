# Omni-CIO V10 — Work Package / Execution Unit Template

**Status:** OWNER-APPROVED PLANNING TEMPLATE  
**Purpose:** every implementation execution unit and every member WP/increment must answer these questions before it is considered ready to code or to advance branch-local milestone state.

This template is deliberately strict. It exists so an authorized developer/AI session does not invent scope, architecture, delivery granularity or acceptance criteria during implementation.

Amendment 12 / Integrated System Update Execution Law adds two valid execution units without changing Master Plan dependency order:

- `FOCUSED_CHANGE` — isolated defect/governance/maintenance/mandatory split;
- `INTEGRATED_SYSTEM_UPDATE` — one coherent OWNER-authorized system update with ordered member WP/increments, one integrated branch and one final PR by default.

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

For `INTEGRATED_SYSTEM_UPDATE`, a member milestone may become branch-local `DONE` only after its own internal Exit criteria pass. That state does not advance accepted V10 progress, change `main`, unlock a later major update, authorize public production or authorize broker/Real execution.

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

Public-production mutation remains separately fail-closed. Planning, an Integrated System Update, a GitHub merge or AI output never by itself authorizes provider apply, public cutover or a paid resource.

## 11. Normal-path acceptance tests

List deterministic tests proving the intended behavior.

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
- fail-closed money/authority behavior.

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

## 16. Rollback/recovery

State exactly how to return to the accepted prior state without losing broker/reconciliation truth.

## 17. Exit Gate

Define a binary PASS/FAIL gate for this WP/member milestone. “Looks good”, “page opens”, or “tests mostly pass” is not sufficient.

For an integrated member milestone, branch-local PASS is not accepted-main completion.

Final merge/normal PR closure requires:

- current exact head;
- all applicable checks actually ran and concluded `success`;
- full diff review;
- zero unresolved blocking review threads;
- no unresolved P0/P1 blocker;
- required security/recovery evidence;
- all required integrated member milestones branch-local PASS;
- mandatory split review clear;
- final integrated acceptance only after squash merge and exact-main post-merge gates.

## 18. Required acceptance evidence

List exact evidence such as:

- tests/run IDs;
- deterministic fixture results;
- screenshots only when UI visual acceptance is material;
- release manifest/provenance;
- migration/recovery rehearsal;
- parity ledger status change;
- owner approval if specifically required.

OWNER product acceptance is normally **post-merge and post-Regression-Shield**. Before merge, OWNER action is allowed only for a genuinely non-delegable prerequisite needed to make engineering verifiable (account/consent/domain/payment/narrow credential/UAC-admin/physical action/Master Plan decision).

If OWNER action is required, acceptance evidence must also state that the handoff used the verified direct-link/expected-result/STOP/do-not-do/minimum-return contract and did not expose secrets or private runtime URLs.

## 19. Documentation/status updates in the same PR

State which files must change with the implementation so GitHub remains the engineering memory.

For `INTEGRATED_SYSTEM_UPDATE`, the branch Execution Ledger and GitHub System Update dashboard are working-state records and must say:

`BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`.

They never replace `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

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

## 21. Scope-discovery rule

Any discovered work not required for this WP/member milestone or parent execution-unit outcome must be classified as one of:

- current blocker/defect with written justification;
- future-WP/System-Update issue/backlog;
- architecture/program amendment requiring OWNER decision;
- mandatory split with evidence.

It must not be silently implemented “while we are here”.
