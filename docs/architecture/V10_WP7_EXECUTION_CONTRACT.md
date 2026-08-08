# Omni-CIO V10 — WP7 Execution Contract

Status: **AUTHORIZED / IMPLEMENTATION IN PROGRESS**  
Block: **C — Lenovo Omni-CIO Node / infrastructure**  
WP: **WP7 — One-Time Bootstrap**

## 1. WP identity

- Authorized by current program status: **YES**.
- Accepted `main` baseline: `f9dff89fb60de8749c6a48f112902ad28492ef46`.
- Prior Exit Gate: WP6 PR #253 squash-merged as `c55fb0a32b309628fb86a7abf9182b95af4beca2`; post-WP6 Regression Shield #1437 / run `31270545874` passed on that exact SHA; canonical status PR #254 squash-merged as `f9dff89fb60de8749c6a48f112902ad28492ef46`; post-status Regression Shield #1438 / run `31271202340` passed on that exact `main` SHA.

## 2. Accepted baseline

Protected runtime/recovery baseline remains Omni-CIO v9.0.0 with Render entrypoint `app:app` and the existing money-authority kill switches.

Authoritative WP7 inputs:

- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` — WP7 scope and Exit Gate;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`;
- `docs/architecture/V10_SECURITY_BOUNDARIES.md`;
- `docs/architecture/V10_TOOLCHAIN_BASELINE.json`;
- `docs/architecture/V10_WP6_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json`;
- `docs/operations/SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md`;
- `docs/operations/V10_WP6_PRIVILEGE_SEPARATION_RUNBOOK.md`;
- accepted WP4 release/provenance controls and Regression Shield.

Selected runtime prerequisite targets inherited from WP2 are Python `3.14.6`, Node.js `24.18.0`, npm `11.16.0` and PostgreSQL `18.4` / major `18`.

## 3. Purpose

Reduce first-time Lenovo node setup to one reviewed, repeatable bootstrap procedure plus only those OWNER/UAC interactions that cannot safely be delegated. The bootstrap must be deterministic, dry-run-first, idempotent and recovery-aware.

## 4. Inputs and prerequisites

WP7 begins only after accepted WP6 identity/ACL separation.

Required existing facts:

- Windows node accepted by WP5;
- GitHub runner root `C:\actions-runner` and durable `omni-cio-ci` service accepted by the existing runner runbook;
- WP6-owned disabled non-admin role anchors `omni-cio-runtime` and `omni-cio-execution`;
- WP6 execution-secret boundary remains protected and contains no real secret from WP7;
- exact toolchain targets come from repository policy, not chat or package-manager `latest` resolution.

No real broker, Telegram, database password, encryption key or private portfolio payload is an input to WP7.

## 5. Existing implementation to reuse

WP7 reuses rather than replaces:

- `infrastructure/windows/provision_wp6_privilege_boundary.ps1` for identity/ACL ownership; WP7 verifies its postconditions and must not duplicate or weaken them;
- `scripts/check_self_hosted_windows_runner_service.ps1` for runner-service health; WP7 does not re-register or reconfigure the runner;
- `docs/architecture/V10_TOOLCHAIN_BASELINE.json` as the only version authority for Python/Node/npm/PostgreSQL;
- WP4 reviewed release identity for future deployment source;
- existing `C:\ProgramData\OmniCIO` hierarchy created by WP6; WP7 extends it only with owned non-secret runtime/data/log/bootstrap directories and metadata;
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
- a narrowly scoped WP7 CI workflow if required for sanitized clean-room/Lenovo evidence.

Canonical V10 status changes only after the WP7 Exit Gate and post-merge Regression Shield pass.

## 7. Explicit non-goals

WP7 does **not**:

- provision or accept real broker, Telegram, DB, encryption or other secret values;
- pass secret values as command-line parameters, environment output, log text or console-history material;
- initialize application database schemas or private portfolio state;
- create/enable future Core/Web/Telegram/AI/execution application services before their owning WPs;
- implement autostart/supervision/self-healing owned by WP9;
- implement local secret-store/rotation owned by WP8;
- implement backup/restore owned by WP10;
- install Ollama/Qwen/Cortex, Web product runtime, Telegram product runtime, Guardian/Watchtower V10 runtime or broker-write runtime;
- change `app:app`, `trading_methods=false`, current V9 production/recovery authority, margin/short/transfer/withdrawal policy or Real execution semantics;
- re-register the GitHub runner or consume a runner registration token.

## 8. Interfaces and contracts

### `V10_WP7_BOOTSTRAP_CONTRACT` v1

Machine-readable repository policy defining:

- exact required prerequisite versions and package identities;
- WP7-owned directory layout;
- required existing WP6 identities and runner health;
- planned service-definition names/owners without creating future application services;
- forbidden secret inputs;
- bootstrap/profile schema and Exit-Gate predicates.

### `WP7_BOOTSTRAP_PROFILE` v1

Privacy-safe local evidence. It may contain only booleans/enumerations/version strings from the public selected toolchain and counts/state labels needed for acceptance. It must not contain usernames, SIDs, hostnames, IP/MAC addresses, package-manager tokens, secret values, DB passwords, runner credential contents or private file contents.

### Bootstrap modes

- default invocation: **PREVIEW / non-mutating**;
- `-Apply`: OWNER-admin mutation of WP7-owned non-secret directories/metadata and safe public prerequisites only;
- `-Verify`: fail-closed postcondition verification without mutation;
- cleanup/rollback uses a separate guarded WP7 script.

The implementation may support a bounded test root for clean-room CI, but production `-Apply` must remain rooted at the reviewed Windows paths.

## 9. Data/persistence effects

- Application DB migration: **NO**.
- Private portfolio/database state: **NO**.
- WP7 may create non-secret bootstrap metadata and empty owned directories under `C:\ProgramData\OmniCIO`.
- PostgreSQL acceptance in WP7 is prerequisite/runtime readiness only; no application schema/private dataset is created.
- Any installed public prerequisite is version-checked and recorded only by package/version status, not by machine identity.

## 10. Security / authority effects

WP7 extends the non-secret node filesystem/runtime foundation but does not expand financial authority.

Required invariants:

- WP6 runner/runtime/execution separation remains intact;
- bootstrap mutation requires OWNER-admin, never the CI runner;
- runner registration is checked, never rebuilt by bootstrap;
- future application service definitions are repository metadata only until owning WPs activate them;
- no secret argument or secret-value field is accepted by the bootstrap interface;
- GitHub collaborator access remains independent from machine secret provisioning;
- release/deployment source remains reviewed release identity.

## 11. Normal-path acceptance tests

Deterministically prove:

- bootstrap parses on Windows PowerShell 5.1 and supported PowerShell execution environment;
- preview is non-mutating;
- exact toolchain policy is loaded from the committed WP2 baseline;
- healthy existing runner is recognized through the accepted runner checker;
- WP6 role anchors are recognized without logging raw local identity values;
- WP7-owned directory plan is deterministic;
- apply creates only WP7-owned non-secret paths/metadata and preserves WP6 paths;
- a second apply produces the same accepted state and no duplicate definitions;
- verify passes only when all required postconditions are present;
- cleanup removes/reverts only WP7-owned state and refuses foreign/unmarked state;
- clean/disposable Windows compatibility exercises the non-mutating/sandboxed path where possible.

## 12. Negative/failure tests

Mandatory fail-closed cases:

- non-Windows mutation attempt;
- `-Apply` without Administrator authority;
- missing/invalid toolchain contract;
- unexpected prerequisite version when exact version is required;
- missing/mismatched/non-persistent runner configuration;
- missing or admin WP6 runtime/execution role anchor;
- unexpected pre-existing content in a WP7-owned path without ownership marker;
- attempt to pass a secret-like argument or define a secret-value parameter;
- package-manager command that resolves unpinned `latest` instead of the selected version;
- mutation of WP6 secret boundary, runner credential files, V9 runtime or broker authority;
- cleanup of unowned files/directories;
- partial apply followed by retry must converge safely or fail with a clear bounded blocker.

## 13. Observability and privacy

Allowed evidence:

- bootstrap mode/status;
- prerequisite public product/version + `MATCH | MISSING | MISMATCH | NOT_APPLICABLE`;
- runner health boolean/error code from the sanitized checker;
- role-present/non-admin booleans;
- owned-directory/service-definition booleans;
- idempotence/rollback results;
- `OWNER_ACTION_REQUIRED` with a bounded reason code.

Forbidden evidence:

- usernames/SIDs/hostnames/device IDs/addresses;
- raw runner `.runner`, `.service`, credential files or service account name;
- secret values/hashes of secret values;
- database password/private connection string;
- private portfolio/database content.

## 14. CI routing

- Fast hosted checks: contract/schema/static tests and deterministic Python tests.
- Hosted Windows clean-room compatibility: **YES**, for PowerShell parse/non-mutating bootstrap behavior and clean-node planning where available.
- Lenovo authoritative checks: **YES**, privacy-safe verify after OWNER apply plus repeat/idempotence evidence.
- GPU AI eval: **NO**.
- Release/recovery matrix: **NO** for WP7; WP4 release provenance is a prerequisite, while full backup/recovery belongs to WP10.

A missing local prerequisite is never converted into PASS by weakening the contract; it is classified as `OWNER_ACTION_REQUIRED` or a current-WP implementation defect.

## 15. Rollback / recovery

Before mutation, bootstrap records only WP7-owned pre-existing state needed for guarded recovery. Rollback:

- never touches runner registration/credentials;
- never removes WP6 role anchors or WP6 secret-boundary ACLs;
- never deletes application/private DB state;
- removes only paths/metadata carrying the WP7 ownership marker and only when safe/empty where required;
- does not silently uninstall a prerequisite that pre-existed WP7;
- may uninstall a public prerequisite only if WP7 proves it installed that exact package and no later accepted WP depends on it; before WP7 acceptance the preferred rollback is to remove only WP7-owned configuration and leave verified public prerequisites installed.

## 16. Exit Gate

WP7 is **PASS** only when deterministic repository policy plus clean-room/Lenovo evidence prove that the approved node can be brought to the WP7 baseline through the versioned bootstrap without manual editing of dozens of configuration files, and a repeated bootstrap is idempotent.

Equivalent operational statement: **OWNER performs one reviewed bootstrap action (plus unavoidable UAC/package installer interaction), receives deterministic PASS/OWNER_ACTION_REQUIRED output, and rerunning the same reviewed bootstrap does not damage or duplicate the node.**

## 17. Required acceptance evidence

- exact-head Fast PR and Toolchain Compatibility run IDs;
- hosted Windows clean-room/non-mutating compatibility result;
- authoritative Lenovo preflight/verify result;
- first apply and repeated apply/idempotence evidence from the reviewed checkout;
- rollback/cleanup test evidence without destroying accepted WP6 state;
- no unresolved review blockers;
- squash merge SHA;
- successful post-merge Regression Shield on that exact `main` SHA.

## 18. Documentation/status updates

The implementation PR must include:

- this execution contract;
- machine-readable bootstrap contract;
- OWNER/operator bootstrap and rollback runbook;
- code/tests/workflow required for acceptance.

`knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` changes to `WP7 COMPLETE` only after the Exit Gate and post-merge Regression Shield succeed.

## 19. Next WP unlock

Only **WP8 — Local Secret Store and rotation** may start after WP7 acceptance. No real secret value is introduced as part of unlocking WP8.

## 20. Scope-discovery rule

Discovered work is classified as current-WP blocker, future-WP backlog, or OWNER-required program amendment. It is never implemented merely because it is adjacent.