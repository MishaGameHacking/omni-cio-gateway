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

## 13. Observability

Define:

- health/status;
- logs (sanitized);
- metrics/job state;
- correlation IDs;
- user-visible degraded state;
- evidence retained for acceptance.

## 14. CI routing

- Fast hosted checks:
- Hosted clean-room compatibility required: YES/NO + reason
- Lenovo authoritative checks:
- GPU AI eval required: YES/NO + reason
- Release/recovery matrix required: YES/NO + reason

## 15. Rollback/recovery

State exactly how to return to the accepted prior state without losing broker/reconciliation truth.

## 16. Exit Gate

Define a binary PASS/FAIL gate. “Looks good”, “page opens”, or “tests mostly pass” is not sufficient.

## 17. Required acceptance evidence

List exact evidence such as:

- tests/run IDs;
- deterministic fixture results;
- screenshots only when UI visual acceptance is material;
- release manifest/provenance;
- migration/recovery rehearsal;
- parity ledger status change;
- owner approval if specifically required.

## 18. Documentation/status updates in the same PR

State which files must change with the implementation so GitHub remains the engineering memory.

## 19. Next WP unlock

Name the next authorized WP and the exact evidence that unlocks it.

## 20. Scope-discovery rule

Any discovered work not required for this WP Exit Gate must be classified as one of:

- current-WP blocker/defect with written justification;
- future-WP issue/backlog;
- architecture/program amendment requiring OWNER decision.

It must not be silently implemented “while we are here”.
