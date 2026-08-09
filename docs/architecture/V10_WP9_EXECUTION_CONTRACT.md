# V10 WP9 — Autostart, supervision and self-healing execution contract

**Status:** ACTIVE WP9 IMPLEMENTATION CONTRACT  
**Block:** C — Lenovo Omni-CIO Node / infrastructure  
**WP:** WP9  
**Accepted baseline:** `8c0fca1b8a3d6a94dc111e2ffe65576bfbaa1fd8`  
**Authorized by canonical program status:** YES

## 1. WP identity

- Title: **Autostart, supervision и self-healing**.
- Prior Exit Gate: WP8 PR #257 and exact Lenovo secret-store audit PASS; WP8 merged as `422ef68864050eec858e32d980165c995d9e7ecb`.
- Canonical WP8 completion/status PR #258 merged as `8c0fca1b8a3d6a94dc111e2ffe65576bfbaa1fd8`.
- Post-status Regression Shield #1442 / run `31285527628`: required before WP9 implementation and must remain PASS.

## 2. Accepted baseline

Protected V9/V10 invariants remain:

- V9 production/recovery baseline is retained;
- Render/Gateway entrypoint remains `app:app`;
- `trading_methods=false` remains unchanged;
- broker write / Real-money authority is not expanded;
- WP6 OWNER/CI/runtime/execution least-privilege boundaries remain authoritative;
- WP7 exact prerequisite/bootstrap layout remains authoritative;
- WP8 local secret-store DACL/DPAPI separation remains authoritative and no real secret is required for WP9 acceptance.

Relevant authority:

- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` — WP9 only;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
- `docs/architecture/V10_WP6_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP7_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP7_BOOTSTRAP_CONTRACT.json`;
- `docs/architecture/V10_WP8_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP8_SECRET_STORE_CONTRACT.json`;
- `docs/architecture/V10_SECURITY_BOUNDARIES.md`.

## 3. Purpose

After a Windows reboot, the Lenovo node must automatically establish a truthful, safe supervised state and persist a privacy-safe `HEALTHY` or `DEGRADED` health result without manually opening application terminals.

Because Core/Web/Telegram/Watchtower/AI product runtimes belong to later WPs, WP9 must not fabricate them. WP9 creates the OS-level supervision slots, startup/restart policy and health boundary now; unavailable later-WP components remain explicitly sealed/`NOT_READY` and make the current node truthfully `DEGRADED`, not falsely `HEALTHY`.

## 4. Inputs and prerequisites

Required before any WP9 mutation:

- Windows 11 node accepted by WP5;
- healthy persistent GitHub self-hosted runner;
- WP6 local role anchors present, non-admin and with execution role still sealed;
- WP7 prerequisite/bootstrap verification PASS;
- WP8 secret-store verification PASS with no real secret needed;
- PostgreSQL 18.4 machine-visible installation from accepted WP7 bootstrap;
- existing `C:\ProgramData\OmniCIO\services` WP7-owned root.

## 5. Existing implementation to reuse

| Component | Accepted implementation | WP9 decision |
|---|---|---|
| V10 infrastructure root | `infrastructure/`, WP5–WP8 scripts/contracts | **REUSE_AS_IS + extend narrowly**; reuse matrix resolved in this PR |
| WP7 bootstrap/service-slot metadata | `bootstrap-v10.ps1`, `V10_WP7_BOOTSTRAP_CONTRACT.json` | **REUSE_AS_IS**; WP9 must not rewrite the accepted bootstrap |
| WP8 secret boundary | DPAPI LocalMachine + protected NTFS DACL | **REUSE_AS_IS**; health supervisor receives no secret payload grant |
| GitHub hybrid CI | hosted fast/compat + Lenovo authoritative lane | **REUSE_AS_IS** with a focused WP9 compatibility/audit workflow |
| PostgreSQL 18 service | machine-installed prerequisite from WP7 | **WRAP/OBSERVE ONLY**; WP9 does not change DB schema/data/authentication |
| V9 Gateway/domain code | protected V9 runtime | **NO CUTOVER IN WP9** |

No material V9 financial/domain component is rewritten in WP9.

## 6. Allowed changes

WP9 may change only:

- `docs/architecture/V10_WP9_*`;
- `docs/operations/V10_WP9_*`;
- the WP9 ADR/status of already-accepted ADR-020 in `docs/architecture/DECISIONS.md`;
- the infrastructure-root reuse decision in `V10_COMPONENT_REUSE_MATRIX.json`;
- `infrastructure/windows/*wp9*`;
- `scripts/*wp9*`;
- `tests/test_v10_wp9_*`;
- focused `.github/workflows/v10-wp9-*` CI.

## 7. Explicit non-goals

WP9 must not:

- implement Core financial/business logic, Web UI, Telegram product logic, Watchtower portfolio logic or Cortex/AI runtime;
- activate the future execution service or `omni-cio-execution` identity;
- provision a real broker, Telegram, AI, encryption or external-source secret;
- enable broker write / Sandbox / Real submission;
- begin WP9A maintenance/patch policy or WP10 backup/recovery;
- replace PostgreSQL configuration/authentication/schema;
- replace the V9 Render/GPT production path;
- add NSSM/WinSW or another third-party service wrapper when built-in Windows Task Scheduler is sufficient.

## 8. Interfaces and contracts

WP9 introduces:

1. `V10_WP9_SUPERVISION_CONTRACT.json` — versioned machine-readable service/task graph, activation states, dependencies, restart policy, health semantics and privacy constraints.
2. Sanitized local health profile (`schema_version=1`) containing component IDs/states, boot/readiness/recovery evidence and no private values.
3. WP9 OWNER provision/verify/rollback commands with PREVIEW as the default non-mutating mode.

Component state vocabulary is restricted to canonical V10 semantics. For WP9 local supervision the relevant values are:

- `READY` — dependency is actually available and passed its readiness probe;
- `NOT_READY` — later-WP runtime is intentionally not available/activated;
- `DEGRADED` — node remains safe but not all desired components are ready;
- `BLOCKED` — required dependency or boundary prevents activation;
- `ERROR` — supervision itself is invalid or failed.

## 9. Data / persistence effects

No financial/database migration is allowed.

WP9 may create only marker-owned infrastructure state beneath:

- `C:\ProgramData\OmniCIO\services\wp9` — deployed reviewed supervision scripts/contract snapshot;
- `C:\ProgramData\OmniCIO\services\wp9\evidence` — sanitized status/rehearsal/reboot evidence;
- Task Scheduler folder `\OmniCIO\V10\` — WP9-owned scheduled-task definitions.

Rollback removes only marker-owned WP9 tasks/files and refuses to adopt/delete unmarked pre-existing objects. WP5–WP8 state is preserved.

## 10. Security / authority effects

- Secret access: **NO expansion**. The health supervisor must not receive WP8 secret-class payload access.
- Broker authority: **NO change**.
- OS privilege: OWNER Administrator is used only to register/remove machine tasks and guarded acceptance rehearsal state.
- Persistent health supervisor principal: built-in `NT AUTHORITY\LOCAL SERVICE`, not Administrator/SYSTEM; it has minimum local privileges and no password requirement.
- Future product service slots retain their accepted intended roles but stay disabled/sealed until their owning WP supplies a real runtime and activation gate.
- GitHub permissions: `contents: read` only for new workflows.
- Web/Telegram ingress: **NO change**.
- AI tool authority: **NO change**.
- Real execution path: **NO change**.

## 11. Normal-path acceptance tests

WP9 must prove:

- static contract consistency and no later-WP activation;
- Windows PowerShell 5.1 parse compatibility;
- PREVIEW is non-mutating on clean hosted Windows;
- guarded APPLY is idempotent on Lenovo;
- the health-supervisor task is registered under `LOCAL SERVICE`, enabled, startup-triggered and bounded by reviewed settings;
- future product slot tasks are registered in a disabled/sealed state;
- PostgreSQL is discovered/readiness-probed without credentials;
- sanitized status reports `DEGRADED` while later-WP slots are intentionally `NOT_READY`;
- after the final reboot rehearsal, the supervisor ran after the new boot and persisted fresh status without manual application launch.

## 12. Negative / failure tests

Required negative evidence:

- non-admin GitHub runner cannot mutate WP9 task definitions or protected deployed scripts;
- supervisor has no WP8 secret data grant;
- unexpected/unmarked local directories/tasks are never adopted or deleted;
- missing PostgreSQL produces `DEGRADED/BLOCKED`, not a false healthy state;
- a synthetic supervised worker failure demonstrates bounded restart rather than an infinite restart storm;
- a synthetic dependency failure blocks its dependent slot and recovers after dependency restoration;
- restart count/backoff/max attempts are finite and machine-readable;
- stale pre-reboot evidence cannot satisfy the reboot Exit Gate;
- all evidence is privacy-safe and contains no secret, ciphertext, account ID, hostname/raw username or private portfolio payload.

## 13. Observability

WP9 evidence is local-first and sanitized:

- canonical node status: `HEALTHY | DEGRADED | ERROR`;
- per-component state/reason codes;
- UTC `observed_at` and Windows boot time only;
- task readiness/last-result/recovery counters without raw process command lines;
- no diagnostic process dumps;
- no secret path payload, value/hash/ciphertext or private investment data.

On the current pre-Core implementation, successful WP9 acceptance is expected to be **DEGRADED** because later product runtimes remain sealed. That is a valid and safer result than claiming HEALTHY.

## 14. CI routing

- Fast hosted checks: repository/security/static unit tests.
- Hosted Windows clean-room compatibility: **YES** — Task Scheduler/PowerShell 5.1 parsing and non-mutating preview need disposable Windows proof.
- Lenovo authoritative checks: **YES** — actual Task Scheduler ACL/principal, PostgreSQL readiness, restart/dependency rehearsal and reboot evidence are machine-specific.
- GPU AI eval: **NO** — AI runtime is outside WP9.
- Release/recovery matrix: **NO** beyond Regression Shield; WP10 owns backup/recovery.

## 15. Rollback / recovery

`rollback_wp9_supervision.ps1` must default to preview, require OWNER Administrator for `-Apply`, remove only WP9 marker-owned tasks/files, and leave:

- GitHub runner registration/service;
- PostgreSQL installation/data;
- WP6 identities/ACLs;
- WP7 bootstrap roots/prerequisites;
- WP8 secret store/sentinels/lifecycle;
- V9 production/recovery path

untouched.

## 16. Exit Gate

WP9 Exit Gate is binary PASS only when exact-head evidence proves:

1. all remote/static/hosted/self-hosted pre-reboot gates pass;
2. OWNER applies the reviewed exact merge checkout idempotently;
3. bounded restart and dependency-failure rehearsals pass with synthetic non-product processes;
4. future product slots remain sealed and no Real-money authority changes;
5. OWNER performs one reviewed full reboot;
6. after reboot, the self-hosted runner returns automatically and the WP9 supervisor has already produced fresh `HEALTHY` or truthful `DEGRADED` status for the new boot without manual application launch;
7. all privacy/security inherited gates remain PASS.

## 17. Required acceptance evidence

- exact PR head + merge checkout SHA;
- Fast PR Checks / Toolchain / WP9 Compatibility / Self-Hosted Windows gate run IDs;
- authoritative WP9 Lenovo audit with empty blockers except explicitly pre-reboot expected blocker before OWNER action;
- OWNER APPLY output with no secret values;
- synthetic restart/dependency rehearsal PASS;
- post-reboot boot-transition evidence and fresh supervisor status;
- no unresolved review threads;
- post-merge Regression Shield PASS.

## 18. Documentation/status updates in the same PR

Implementation PR updates:

- WP9 execution/machine contract;
- ADR decision;
- operations runbook;
- tests/workflows;
- reuse matrix decision needed by this WP.

Canonical `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` is updated only after WP9 is accepted and merged.

## 19. Next WP unlock

Only **WP9A — Runtime patching, time, observability and controlled restart policy** may start after WP9 Exit Gate PASS, squash merge, post-merge Regression Shield PASS and canonical status update.

## 20. Scope-discovery rule

Anything not required for the WP9 Exit Gate is classified as a WP9 defect/blocker, future-WP work, or OWNER-approved amendment. It is not silently implemented in WP9.