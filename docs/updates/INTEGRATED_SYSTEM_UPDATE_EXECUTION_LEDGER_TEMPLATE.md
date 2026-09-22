# Integrated System Update Execution Ledger Template

Status: **BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY**

This ledger is mandatory for `INTEGRATED_SYSTEM_UPDATE` work. It records branch-local execution state only. Accepted V10 progress/current-next authority remains `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` on protected `main`.

## 1. Identity

- Update ID:
- Title:
- Execution unit: `INTEGRATED_SYSTEM_UPDATE`
- Branch:
- Accepted base SHA:
- Current accepted-main SHA rechecked at:
- OWNER authority / START evidence:
- GitHub dashboard issue:
- Governing amendment/contracts:

## 2. Member milestones — ordered

Use the owning architecture/dependency order. Do not mark a later member `IN_PROGRESS` before every required predecessor is `DONE` and the current published logical checkpoint is `CERTIFIED_GREEN`.

| Order | Member WP/increment | State (`DONE/IN_PROGRESS/TODO/BLOCKED`) | Branch-local Exit evidence | Notes |
|---:|---|---|---|---|
| 1 |  | TODO |  |  |
| 2 |  | TODO |  |  |
| 3 |  | TODO |  |  |

Internal milestone `DONE` is branch-local implementation progress only. It does not advance accepted V10 percentage, change `main`, unlock a later major update, activate public production or authorize broker/Real execution.

## 3. Current execution state

- Current exact work item:
- Current logical checkpoint ID:
- Current checkpoint exact SHA:
- Current checkpoint state: `PENDING` / `RED_REPAIR_ONLY` / `TARGET_REPAIRED` / `CERTIFIED_GREEN`
- Next exact action:
- Blockers:
- Known defects:
- Scope/non-goals still intact: YES/NO
- Main drift since accepted base: NONE / describe

## 4. Integration-ready preflight

- [ ] Every required member milestone is complete.
- [ ] Current published checkpoint is `CERTIFIED_GREEN`.
- [ ] Known focused/preflight failures are fixed.
- [ ] Complete changed surface reviewed.
- [ ] Directly coupled producers/consumers/config/workflows reviewed.
- [ ] Analogous repository patterns searched where material.
- [ ] Reasonable adjacent failure modes inspected.
- [ ] Deterministic regression guards added for reusable defect classes.
- [ ] Security/authority/secret/recovery consequences reviewed.
- [ ] Full diff reviewed against current accepted base.
- [ ] Required local/focused type/lint/test/build/browser checks completed.
- [ ] Mandatory split triggers evaluated below.
- [ ] Ledger state may be marked `INTEGRATION_READY`.

`INTEGRATION_READY` is the final whole-update readiness state before final landing review. Earlier meaningful checkpoints may be published/certified under Amendment 16.

Preflight commands/evidence:

```text

```

## 5. Mandatory split-trigger review

Record `CLEAR`, `TRIGGERED` or `N/A` with evidence. A triggered item requires a documented split at the owning boundary.

| Trigger | State | Evidence / consequence |
|---|---|---|
| DB/migration ordering |  |  |
| Security/authority transition |  |  |
| Dependency/toolchain boundary |  |  |
| OWNER/provider action |  |  |
| Live/temporal evidence |  |  |
| Production cutover |  |  |
| Real-money authority |  |  |
| Reviewability limit |  |  |

Split decision: `NO_SPLIT_REQUIRED` / describe approved split and evidence.

## 6. Protected authority checklist

- [ ] Protected V9 entrypoint remains `app:app` unless an owning accepted migration explicitly replaces it.
- [ ] `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged unless its separate activation gate is the owning authorized change.
- [ ] `trading_methods=false` remains unchanged unless its owning future gate explicitly changes it.
- [ ] `REAL_TRADING_ENABLED=false` remains unchanged unless its owning future Real activation gate explicitly changes it.
- [ ] Broker write remains OFF unless explicitly authorized by the owning future gate.
- [ ] No transfer/withdrawal/margin/leverage/uncovered-short authority is introduced.
- [ ] Tenant isolation remains fail-closed.
- [ ] No real secret/private payload/full account ID is stored in GitHub/CI/artifacts.
- [ ] No paid/provider/public mutation occurs without exact OWNER authority.
- [ ] Deterministic Core remains financial truth authority.

## 7. Green Checkpoint certification

Each meaningful published checkpoint follows:

`CHECKPOINT -> GitHub-native CI/security + independent review -> CERTIFIED_GREEN -> NEXT FUNCTIONAL CHECKPOINT`

Any material RED immediately changes the checkpoint state to `RED_REPAIR_ONLY`; unrelated feature work stops. Begin root-cause/blast-radius diagnosis as soon as useful evidence exists. Relevant findings from other independent checks must still be inspected before the corrected checkpoint is finalized.

### Checkpoint N

- Logical checkpoint ID:
- Exact SHA:
- Published at:
- DRAFT/READY state:
- Checkpoint state:
- Applicable workflows/checks:
- GitHub-native lint/type/test/coverage/dependency/SAST/secret/security evidence:
- Browser/review/additional security evidence:
- Terminal conclusions:
- Safety-abort required: NO / describe
- Material findings:

```text

```

Only `CERTIFIED_GREEN` permits the next functional checkpoint or dependent member milestone.

## 8. Root-cause inventory and targeted repair

For every material defect class:

| Finding / class | Root cause | Blast radius / analogous locations | Coupled surfaces | Adjacent failure modes | Why preflight missed it | Permanent guard | Repair |
|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |

Repair law:

`material RED -> RED_REPAIR_ONLY -> systemic diagnosis -> smallest canonical targeted proof -> replacement SHA if repository content changed -> full exact-SHA recertification -> CERTIFIED_GREEN`

Same-SHA rerun is allowed only for unchanged source/config plus an evidence-based transient/infrastructure-only failure; prefer rerunning only the specific failed job. Repeated identical failure is not retried until lucky GREEN.

- Same-SHA rerun used: YES/NO + reason/evidence
- Targeted proof command/run:
- Targeted proof result:
- Replacement SHA, if content changed:
- Prior final evidence invalidated: YES/NO
- Full exact-SHA recertification result:

## 9. Main-drift record

Before final `INTEGRATION_READY` / landing review, re-check accepted `main`.

- New accepted-main SHA (if changed):
- Intersects this update: YES/NO
- Re-anchor required: YES/NO
- Affected milestones/preflight rerun:
- Result:

## 10. Final lifecycle

- [ ] All required internal member milestones complete in dependency order
- [ ] Current exact head `CERTIFIED_GREEN`
- [ ] `INTEGRATION_READY`
- [ ] DRAFT PR opened
- [ ] All applicable exact-head project checks `success`
- [ ] GitHub-native quality/security requirements satisfied when applicable
- [ ] Independent review complete
- [ ] Zero unresolved blocking review threads
- [ ] Full final Files changed/manual diff review complete
- [ ] Any content-changing repair has fresh exact-head CI/review evidence
- [ ] READY transition completed without head change, or any state-dependent applicable checks completed `success`
- [ ] Squash merge
- [ ] Exact new `main` SHA recorded
- [ ] Regression Shield / owning post-merge gates all `success`
- [ ] Accepted status transition recorded when program progress/authority actually changes

## 11. Handoff

- Exact accepted/main or current head SHA:
- Current update/member milestone:
- Current checkpoint state:
- What is complete:
- Checks actually run:
- CI state:
- What remains:
- Blockers:
- Next lawful action:

Do not create a competing current-status document from this ledger.
