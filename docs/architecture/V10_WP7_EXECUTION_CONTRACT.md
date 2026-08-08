# Omni-CIO V10 — WP7 Execution Contract

Status: **AUTHORIZED / IMPLEMENTATION IN PROGRESS**  
Block: **C — Lenovo Omni-CIO Node / infrastructure**  
WP: **WP7 — One-Time Bootstrap**

## 1. WP identity

- Authorized by current program status: **YES**.
- Accepted `main` baseline: `f9dff89fb60de8749c6a48f112902ad28492ef46`.
- Prior Exit Gate: WP6 PR #253 squash-merged as `c55fb0a32b309628fb86a7abf9182b95af4beca2`; canonical status PR #254 squash-merged as `f9dff89fb60de8749c6a48f112902ad28492ef46`; post-merge Regression Shield passed on both accepted exact `main` SHAs.

## 2. Accepted baseline

Protected production/recovery baseline remains Omni-CIO V9 with Render entrypoint `app:app` and the existing money-authority kill switches.

Authoritative WP7 inputs:

- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`;
- `docs/architecture/V10_SECURITY_BOUNDARIES.md`;
- `docs/architecture/V10_TOOLCHAIN_BASELINE.json`;
- accepted WP6 identity/privilege contract and runbook;
- accepted self-hosted Windows runner contract;
- accepted WP4 release/provenance controls and Regression Shield.

Selected runtime targets inherited from WP2 are Python `3.14.6`, Node.js `24.18.0`, npm `11.16.0` and PostgreSQL `18.4` / major `18`. WP7 does not silently replace those reviewed targets with a newer upstream release.

## 3. Purpose

Reduce first-time Lenovo node setup to one reviewed, repeatable bootstrap procedure plus only OWNER/UAC interactions that cannot safely be delegated. Bootstrap must be deterministic, dry-run-first, idempotent, fail-closed and recovery-aware.

## 4. Inputs and prerequisites

WP7 begins only after accepted WP6 identity/ACL separation.

Required facts:

- Windows node accepted by WP5;
- `C:\actions-runner` durable self-hosted runner already accepted;
- immutable GitHub Actions `RUNNER_NAME` for the executing job must match reviewed runner `omni-cio-ci`;
- WP6-owned disabled non-admin anchors `omni-cio-runtime` and `omni-cio-execution`;
- WP6 runner-private files and execution-secret boundary remain protected;
- exact toolchain targets come from repository policy, never package-manager `latest`.

No real broker, Telegram, database password, encryption key or private portfolio payload is an input to WP7.

## 5. Existing implementation to reuse

WP7 reuses rather than replaces:

- WP6 identity/ACL ownership; WP7 verifies its postconditions and must not duplicate or weaken them;
- GitHub's accepted Windows self-hosted service surface (`RUNNER_NAME` plus the `actions.runner.*` Windows service) without reading `.runner`, `.service` or credential files;
- `docs/architecture/V10_TOOLCHAIN_BASELINE.json` as the version authority;
- WP4 reviewed release identity for future deployment source;
- existing `C:\ProgramData\OmniCIO` hierarchy created by WP6;
- Regression Shield and repository security/boundary checks.

No material V9 financial engine is rewritten or migrated by WP7.

## 6. Allowed changes

WP7 may change only bootstrap-owned infrastructure and acceptance surfaces:

- `docs/architecture/V10_WP7_*`;
- `docs/operations/V10_WP7_*`;
- `infrastructure/windows/bootstrap-v10.ps1`;
- `infrastructure/windows/*wp7*` rollback/profile assets;
- `scripts/*wp7*` assessors/checks;
- `tests/test_v10_wp7_*`;
- narrowly scoped WP7 CI workflows required for sanitized hosted/Lenovo evidence.

Canonical V10 status changes only after WP7 Exit Gate and post-merge Regression Shield pass.

## 7. Explicit non-goals

WP7 does **not**:

- provision or accept real broker, Telegram, DB, encryption or other secret values;
- pass secret values through CLI arguments, output, logs or console history;
- initialize application DB schemas or private portfolio state;
- create/enable future Core/Web/Telegram/AI/execution application services;
- implement WP8 secret store, WP9 supervision, WP10 backup/recovery or later application runtimes;
- install Ollama/Qwen/Cortex or broker-write runtime;
- change `app:app`, `trading_methods=false`, V9 recovery authority or money-safety policy;
- re-register the GitHub runner or consume a runner registration token.

## 8. Interfaces and contracts

### `V10_WP7_BOOTSTRAP_CONTRACT` v1

Machine-readable policy defines:

- exact prerequisite versions and installation transports;
- Python official artifact URL, SHA-256 and machine-install policy;
- exact Node/PostgreSQL WinGet identities/versions;
- WP7-owned directory layout;
- required WP6 identities and runner-health predicates;
- future service definitions without activation;
- forbidden secret inputs;
- profile schema and Exit-Gate predicates.

### Python transport

The accepted Python `3.14.6` baseline is installed, when required, from the exact official Python.org x64 installer. The bootstrap verifies the committed SHA-256 and a valid Authenticode signature before execution, then requests all-users installation. This intentionally avoids the current upstream `Python.Python.3.14 --scope machine` scope defect without changing the accepted WP2 Python version.

### Node/PostgreSQL transport

Node and PostgreSQL use exact WinGet IDs and exact reviewed versions with `--exact`, `--version`, `--source winget` and `--scope machine`. PostgreSQL may require unavoidable installer-UI password entry; no password is passed to PowerShell or stored by WP7.

### `WP7_BOOTSTRAP_PROFILE` v1

Privacy-safe evidence may contain only booleans, bounded reason codes, public version strings and acceptance states. It must not contain usernames, SIDs, hostnames, IP/MAC addresses, runner-private content, secret values, DB passwords or private file contents.

### Bootstrap modes

- default invocation: **PREVIEW / non-mutating**;
- `-Apply`: OWNER-admin mutation of WP7-owned non-secret state plus reviewed public prerequisites only;
- `-Verify`: non-mutating fail-closed postcondition verification;
- cleanup/rollback: separate marker-guarded WP7 script.

## 9. Data/persistence effects

- Application DB migration: **NO**.
- Private portfolio/database state: **NO**.
- WP7 may create non-secret bootstrap metadata and empty owned directories under `C:\ProgramData\OmniCIO`.
- PostgreSQL acceptance is prerequisite/runtime readiness only.
- Public prerequisites installed by WP7 are recorded by public artifact/package identity and version/hash metadata only.

## 10. Security / authority effects

WP7 extends non-secret node infrastructure only; financial authority does not expand.

Required invariants:

- WP6 runner/runtime/execution separation remains intact;
- bootstrap mutation requires OWNER-admin, never the CI runner;
- runner registration/private files are not read or modified by WP7 health checks;
- runner health is established through immutable `RUNNER_NAME`, the standard `actions.runner.*` Windows service, service path binding to `C:\actions-runner`, running/automatic state, non-admin service identity and current-process/service-identity equivalence;
- future application service definitions remain metadata only;
- no secret parameter/field is accepted;
- release/deployment source remains reviewed release identity.

## 11. Normal-path acceptance tests

Deterministically prove:

- PowerShell parses on Windows PowerShell 5.1;
- preview is non-mutating;
- exact toolchain policy comes from committed WP2 baseline;
- Python download is exact URL + SHA-256 + Authenticode + all-users policy;
- Node/PostgreSQL package resolution is exact and never `latest`;
- healthy existing runner is recognized without reading protected runner-private files;
- WP6 role anchors are recognized without emitting raw local identities;
- machine prerequisite discovery prefers machine installations over per-user PATH/launcher state;
- WP7-owned directory plan is deterministic;
- apply creates only WP7-owned non-secret paths/metadata;
- second ensure pass produces zero structural changes;
- verify passes only with every required postcondition;
- cleanup removes only WP7-owned marker-guarded state;
- hosted Windows compatibility exercises parse/non-mutating paths.

## 12. Negative/failure tests

Mandatory fail-closed cases:

- non-Windows mutation;
- `-Apply` without Administrator;
- missing/invalid toolchain contract;
- Python URL/hash/signature policy mismatch;
- unexpected machine-visible prerequisite version;
- wrong/missing immutable runner job name;
- missing/ambiguous runner Windows service;
- service not rooted in `C:\actions-runner`;
- service not running/automatic/non-admin;
- executing job identity not equal to runner service identity;
- any attempt to read protected `.runner`, `.service` or credential files in the WP7 audit;
- missing/admin WP6 role anchor;
- unmarked pre-existing WP7 path;
- secret-like bootstrap parameter;
- unpinned package resolution;
- mutation of WP6 secret boundary, runner credentials, V9 runtime or broker authority;
- cleanup of unowned state;
- retry after partial apply must converge or fail with a bounded blocker.

## 13. Observability and privacy

Allowed evidence:

- bootstrap mode/status;
- public prerequisite version + `MATCH | MISSING | MISMATCH | NOT_MACHINE_VISIBLE | UNAVAILABLE`;
- runner health booleans/error code;
- role-present/non-admin booleans;
- owned-directory/service-definition booleans;
- idempotence/rollback state;
- `OWNER_ACTION_REQUIRED` plus bounded reasons.

Forbidden evidence:

- usernames/SIDs/hostnames/device IDs/addresses;
- raw `.runner`, `.service`, credentials or service-account names;
- secret values or secret hashes;
- DB password/private connection string;
- private portfolio/database content.

## 14. CI routing

- Fast hosted checks: contract/static/unit tests.
- Hosted Windows compatibility: PowerShell parse and non-mutating bootstrap behavior.
- Lenovo authoritative checks: privacy-safe preflight/verify plus repeat/idempotence evidence after OWNER apply.
- GPU AI eval: **NO**.
- Release/recovery matrix: **NO** for WP7.

A missing local prerequisite never becomes PASS by weakening the contract; it remains `OWNER_ACTION_REQUIRED` until exact reviewed installation is performed.

## 15. Rollback / recovery

Rollback:

- never touches runner registration/private files;
- never removes WP6 role anchors or WP6 secret-boundary ACLs;
- never deletes private DB/application state;
- removes only WP7 ownership-marked paths/metadata when safe;
- leaves public prerequisites installed by default;
- refuses cleanup once foreign/unexpected state appears or later services exist.

## 16. Exit Gate

WP7 is **PASS** only when repository policy plus hosted/Lenovo evidence prove the approved node can be brought to the WP7 baseline using the versioned bootstrap and a repeated bootstrap is idempotent.

Operationally: OWNER performs one reviewed bootstrap action (plus unavoidable UAC/installer UI), receives deterministic PASS/OWNER_ACTION_REQUIRED output, and rerunning the same reviewed bootstrap does not damage or duplicate state.

## 17. Required acceptance evidence

- exact-head Fast PR and Toolchain Compatibility run IDs;
- hosted Windows compatibility PASS;
- authoritative Lenovo preflight identifying only legitimate OWNER-local blockers;
- OWNER apply and second-pass idempotence evidence;
- authoritative Lenovo `-Verify` PASS;
- rollback guard evidence;
- no unresolved review blockers;
- squash merge SHA;
- post-merge Regression Shield PASS on that exact `main` SHA.

## 18. Documentation/status updates

Implementation PR includes this execution contract, machine-readable bootstrap contract, runbook, code/tests/workflows. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` changes to `WP7 COMPLETE` only after Exit Gate and post-merge Regression Shield succeed.

## 19. Next WP unlock

Only **WP8 — Local Secret Store and rotation** may start after WP7 acceptance. No real secret value is introduced by WP7.

## 20. Scope-discovery rule

Discovered work is classified as current-WP blocker, future-WP backlog or OWNER-required program amendment. It is never implemented merely because it is adjacent.
