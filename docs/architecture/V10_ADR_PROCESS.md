# Omni-CIO V10 — ADR Process

Status: **WP0 architecture governance**

## 1. Purpose

Architectural Decision Records (ADRs) prevent V10 from drifting through undocumented chat decisions, account-specific settings or developer preference.

An ADR records **what changed, why, alternatives considered, consequences, migration and rollback**.

## 2. When an ADR is mandatory

Create/update an ADR when a change materially affects one or more of:

- system boundaries or component ownership;
- GitHub vs runtime authority;
- Web/Telegram/AI architecture;
- database/persistence technology or canonical domain model;
- broker read/write authority;
- secret storage/identity/authentication model;
- AI provider/tool authority/RAG trust model;
- execution/approval/idempotency/reconciliation lifecycle;
- external ingress/deployment model;
- recovery/backup strategy;
- source-of-truth order;
- removal/supersession of an accepted V9/V10 architecture decision.

A small implementation detail inside an already accepted design normally does not require an ADR.

## 3. ADR location and numbering

Canonical active decision registry remains:

`docs/architecture/DECISIONS.md`

V10 decisions continue sequential numbering after existing V9 ADRs. If decision volume grows, WP1 may introduce `docs/architecture/adr/` as a repository-owned directory, but there must still be one index/registry and no competing decision logs.

## 4. Required ADR fields

Each ADR contains:

```text
ADR-NNN — Title
Status: proposed | accepted | superseded | rejected
Date:
Current V10 WP:

Context
Decision
Alternatives considered
Security / money-authority impact
Data / migration impact
Operational impact
Failure mode
Rollback
Verification / Exit Gate evidence
Supersedes / superseded by
```

## 5. Status lifecycle

### proposed

May exist on the current focused branch. It has no architectural authority on its own.

### accepted

Merged through the current-WP PR after required review/CI. Becomes architecture authority subject to higher-priority Program Lock/Master Plan.

### superseded

Old rationale is retained for history. The replacement ADR is linked explicitly.

### rejected

Retained only when useful to prevent repeating a considered but unsafe/unsuitable approach.

## 6. Approval rules

- ADR cannot expand scope beyond the current WP without owner-approved program amendment.
- ADR cannot grant Real-money authority merely by being accepted.
- P0 boundaries (broker authority, approval, secrets, idempotency, reconciliation) require explicit security review and negative tests in the implementing WP.
- Account-only/hidden configuration is not an accepted architectural solution when repository-controlled representation is possible.
- `latest` technology is not justification by itself; official documentation, security, license, maintenance, Windows compatibility and rollback must be evaluated.

## 7. Decision conflict rule

Authority order:

1. accepted `main`;
2. `AGENTS.md`;
3. V10 Program Lock;
4. V10 Master Plan;
5. V10 current status;
6. accepted ADRs/current-WP architecture docs.

An ADR that conflicts with a higher authority is invalid until the higher authority is changed through the required owner-reviewed process.

## 8. Rollback requirement

Every ADR that changes runtime architecture must state how to return to the last accepted state or why rollback is impossible and what forward-recovery strategy replaces it.

For money/state paths, rollback may never discard reconciliation evidence merely to make the system appear clean.

## 9. WP review usage

Before coding a current WP:

1. inspect relevant existing ADRs;
2. identify whether the WP changes an architectural boundary;
3. add proposed ADR(s) in the same focused branch when needed;
4. implement/tests must match the accepted decision;
5. PR review checks architecture + code together;
6. on merge, update superseded links/status if required.

## 10. Initial V10 ADR

WP0 adds the first V10 governance decision to `DECISIONS.md`: V10 is the exclusive active feature program, while V9 remains the protected production/recovery runtime until individual V10 boundaries pass their Exit Gates.
