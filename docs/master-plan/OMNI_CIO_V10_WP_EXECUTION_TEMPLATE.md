# Omni-CIO V10 — Work Package Execution Template

**Status:** OWNER-APPROVED PLANNING TEMPLATE  
**Purpose:** every implementation WP must answer these questions before it is considered ready to code.

This template is deliberately strict. It exists so an authorized developer/AI session does not invent scope, architecture or acceptance criteria during implementation.

## 1. WP identity

- Block:
- WP:
- Title:
- Authorized by current program status: YES/NO
- Prior Exit Gate proven by:

## 2. Accepted baseline

- Accepted `main` SHA:
- Protected V9/V10 runtime baseline:
- Relevant Master Plan/amendment sections:
- Relevant ADRs/contracts:

## 3. Purpose

State the one concrete outcome of this WP.

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
- full branch diff review.

Known preflight failures must be fixed before triggering the full exact-head gate.

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

List exact domains/directories/interfaces this WP may change.

## 7. Explicit non-goals

List adjacent work this WP must not perform.

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

## 10. Security/authority effects

State whether this WP changes:

- secret access;
- broker authority;
- OS/runtime privileges;
- GitHub permissions;
- Web/Telegram ingress;
- AI tool authority;
- Real execution path.

If any boundary changes, reference the threat review/ADR.

### 10.1 Runtime/hosting and external-provider boundary

For any Web/runtime/provider work state explicitly:

- primary application/runtime host;
- whether V10 Web/API remains on the approved Lenovo/replacement Personal Node;
- whether any provider is access/security transport versus application/private-state hosting;
- whether any recurring paid cloud hosting is proposed and, if so, the OWNER-approved amendment that authorizes it;
- how the protected V9 Render.com `app:app` baseline remains untouched until its owning parity/decommission gate.

Default V10 rule: Personal Node hosts/builds/renders/serves V10; Render.com is not the V10 runtime target; an external-access provider must not silently become a second application/private-state host.

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

For any material defect discovered during this WP, define the review method before retrying full CI:

- root cause;
- repository-wide analogous pattern search;
- directly coupled producers/consumers/config/workflows;
- reasonable adjacent failure modes;
- permanent regression/guard;
- why prior preflight did not catch the failure.

Do not assume a one-line failing location means a one-line defect class.

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

## 14. CI routing

- Cheap/focused preflight commands:
- Fast hosted checks:
- Hosted clean-room compatibility required: YES/NO + reason
- Lenovo authoritative checks:
- GPU AI eval required: YES/NO + reason
- Release/recovery matrix required: YES/NO + reason
- Full exact-head CI may start only after pre-CI readiness: PASS/FAIL

Project GREEN definition for an applicable gate is `success` only. `skipped`, `neutral`, `cancelled`, pending/in-progress states and infrastructure/billing failures do not count as GREEN merge evidence.

If a workflow is not applicable, route/trigger it so it does not appear as a misleading skipped/cancelled gate.

Any commit after final GREEN invalidates prior final evidence and requires the applicable exact-head cycle again.

## 15. Rollback/recovery

State exactly how to return to the accepted prior state without losing broker/reconciliation truth.

## 16. Exit Gate

Define a binary PASS/FAIL gate. “Looks good”, “page opens”, or “tests mostly pass” is not sufficient.

Merge/normal PR closure requires:

- current exact head;
- all applicable checks actually ran and concluded `success`;
- full diff review;
- zero unresolved blocking review threads;
- no unresolved P0/P1 blocker;
- required security/recovery evidence.

## 17. Required acceptance evidence

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

## 18. Documentation/status updates in the same PR

State which files must change with the implementation so GitHub remains the engineering memory.

### 18.1 Failure-learning update

If an unexpected material RED occurred after the branch had been considered preflight-ready, answer:

- Why was the branch believed ready?
- What evidence/assumption was missing?
- What other locations were searched for the same failure class?
- What permanent guard was added?
- Does `docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md` need a reusable entry?

Do not store secrets/private payloads in the ledger.

## 19. Next WP unlock

Name the next authorized WP and the exact evidence that unlocks it.

The next WP remains locked until implementation merge, required post-merge Regression Shield, any required OWNER acceptance and status transition are all complete.

## 20. Scope-discovery rule

Any discovered work not required for this WP Exit Gate must be classified as one of:

- current-WP blocker/defect with written justification;
- future-WP issue/backlog;
- architecture/program amendment requiring OWNER decision.

It must not be silently implemented “while we are here”.
