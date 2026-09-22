# Omni-CIO V10 — WP15 Deferred Live Read-Only Acceptance Runbook

Status: **SUPPORT PATH ACCEPTED — REAL OWNER LIVE ACTION REQUIRED / WP18 LOCKED**

Current canonical live-evidence marker remains:

`LIVE_EVIDENCE_STATUS=DEFERRED_TO_WEB_PROVISIONING`

This marker remains authoritative until real OWNER Web parity evidence and the independent non-admin runner audit are both accepted. The support path is accepted, but the real T-Invest READ evidence is still absent. Outside the accepted authenticated local/private Web form, **do not provision a real T-Invest READ token** through PowerShell or any other normal path.

Authority: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`, the accepted Identity/Multi-Tenant amendment, `docs/architecture/V10_WP15_TINVEST_READONLY_CONTRACT.md`, and `docs/architecture/V10_WP15_LIVE_WEB_ACCEPTANCE_CONTRACT.json`.

Accepted support history as of 2026-08-12:

- PR #284 — deferred live Web support path;
- PR #285 — Windows-native OWNER-audit cleanup hardening;
- PR #286 — locale-independent Administrators SID validation;
- PR #287 — Windows PowerShell 5.1 native npm stderr handling;
- PR #290 — battery-safe temporary Task Scheduler settings plus sanitized `task_state` / numeric `LastTaskResult` startup diagnostics;
- PR #292 — acceptance-only temporary `SeBatchLogonRight` starter with exact restore semantics;
- PR #293 — canonical OWNER tenant/user bootstrap before local session creation;
- PR #294 — explicit OWNER session persistence/readiness under PostgreSQL transaction boundaries;
- PR #295 — archived runtime session-probe source binding;
- PR #296 — serialized authenticated Web request transaction contexts on the acceptance-only Psycopg connection;
- PR #297 — revoked READ connections retained durably but hidden from active Settings/live-acceptance listing;
- PR #298 — immutable broker-account record reuse for the same verified READ account reconnect;
- PR #299 — fail-safe self-hosted Windows runner diagnostic/recovery with exact service executable binding and privacy-safe actual-node verification.

Latest accepted runtime/operational implementation baseline before this documentation synchronization is `6bd4e2c683386269ee573f25f50cbc8780ac9ff5`. The OWNER physical procedure must use the exact accepted `main` SHA supplied after this documentation/status transition itself is merged and its required post-merge gates are GREEN; do not substitute the older implementation-baseline SHA merely because runtime code is unchanged.

Product/live Web support was last post-merge exercised on immediately preceding `bc5842e019ffa5c612b1a0b6cffe00e9c5d2718a`: Regression Shield #1481 / run `31620202000`, WP15 Live Web Support Audit #106 / run `31620202006`, WP16 Audit #205 / run `31620202052`, and WP17 Audit #176 / run `31620202030` are SUCCESS. WP15 OWNER Audit #14 / run `31620201999` is expected `OWNER_ACTION_REQUIRED` because real sanitized OWNER evidence does not exist yet.

PR #299 changed only runner operational support. Its exact reviewed head passed Self-Hosted Windows CI #874 / run `31627886479` (including protected Regression Shield, dependency audit, SAST, tracked-content secret scan and Windows runner smoke), WP16 #221 / run `31627886484`, and WP17 #192 / run `31627886513`. Hosted Fast PR Checks #782 and Toolchain Compatibility #817 did not start because of the existing GitHub account billing/spending-limit condition; they remain infrastructure failures, not PASS. After squash merge, exact-main Regression Shield #1482 / run `31629149440`, WP16 #222 / run `31629149358`, and WP17 #193 / run `31629149359` are SUCCESS.

The earlier real OWNER startup rehearsal exposed Task Scheduler state `Ready` with numeric `LastTaskResult=267011` (`0x00041303`, task has not yet run). The accepted correction introduced an acceptance-only starter that can grant only the exact non-admin runtime role the temporary `SeBatchLogonRight` required for password-logon scheduled-task startup. Later focused corrections through PR #298 closed local identity/session/request/reconnect defects exposed by deterministic acceptance testing, and PR #299 made the non-admin GitHub runner recovery path fail-safe before the next physical attempt.

## 1. Purpose

This runbook completes only the deferred WP15 live READ acceptance after WP16/WP17. It does not implement WP18 Portfolio Dashboard feature work and does not activate public ingress, public multi-user registration, TRADE credentials, broker write authority, transfers/withdrawals, or Real execution.

Normal broker credential entry remains:

`authenticated Omni-CIO Web -> Settings -> Broker Connections -> T-Invest READ token`.

The raw broker token is never an OWNER PowerShell argument, GitHub secret, environment-variable input, chat value, CI value, log field or evidence artifact. The browser sends it once to the local/private Web backend, clears the form after validation, and never receives it back.

## 2. Hard prerequisites before any real token

Do **not** perform the live procedure until all of the following are true:

1. every current WP15 live Web support/hardening PR required for the attempt is squash-merged;
2. the exact accepted checkout SHA for the physical gate is confirmed as current `main` after all prerequisite documentation/status transitions;
3. mandatory post-merge Regression Shield is GREEN on that exact SHA;
4. the most recent applicable reviewed WP15 live support workflow is GREEN, and any later accepted operational-only change has passed its own exact-head and post-merge owning gates;
5. OWNER is given that exact checkout SHA for the local procedure.

If `main` changes again before OWNER execution, re-confirm the exact accepted checkout and required post-merge gates instead of reusing a stale SHA.

Until the real procedure is finalized, `broker_read` may remain unprovisioned and no real T-Invest token is required outside the local/private Web form.

WP18 remains locked until the final sanitized OWNER evidence and independent non-admin runner audit both pass.

## 3. Security contour

The acceptance runtime is temporary and loopback-only:

- HTTP bind: `127.0.0.1:8765` only;
- Windows principal: existing non-admin `omni-cio-runtime` role anchor;
- temporary task: `OmniCIO.V10.WP15LiveAcceptance`;
- permanent WP9 Web task/service definition is not modified;
- runtime deployment is an exact `git archive` of the reviewed SHA;
- the runtime may read only the accepted WP17 READ connection vault and may write only its private pending-evidence directory;
- GitHub runner has no data read/write authority to the pending private boundary or broker secret payload;
- PostgreSQL 18 is accessed over loopback SSPI using exact username maps and a dedicated least-privilege `omni_cio_runtime` database role;
- `trust` authentication and persisted database passwords are forbidden;
- OWNER-only PostgreSQL migration/bootstrap authority is removed from the runtime before the Web task starts.

The temporary scheduled task uses password logon because the acceptance runtime must have both network access to T-Invest and access to the DPAPI-protected READ vault. S4U is explicitly not used because Windows documents that S4U scheduled tasks have no network or encrypted-file access. The temporary task is explicitly allowed to start on battery and is not stopped by an AC-to-battery transition; these settings affect only the acceptance task and do not change permanent WP9 runtime policy.

Password-logon scheduled-task startup also requires batch-logon capability for the task principal. The reviewed acceptance starter therefore manages `SeBatchLogonRight` narrowly:

- it resolves and validates only the exact WP6-owned `omni-cio-runtime` SID;
- the account must remain non-admin and must start disabled;
- a direct `SeDenyBatchLogonRight` causes fail-closed rejection and is never removed or bypassed;
- a pre-existing `SeBatchLogonRight` is preserved unchanged;
- if the right is absent, the starter adds only `SeBatchLogonRight`, invokes the existing reviewed provisioner, and removes that temporary right in `finally` before the starter exits;
- no `SeServiceLogonRight`, interactive-logon right, Administrator membership or broker authority is added;
- the runtime account password remains generated only inside the child provisioner and is never logged/exported.

## 4. OWNER preparation after support acceptance

Only after the prerequisites in section 2 are satisfied, use the exact accepted `main` checkout on the Lenovo node.

Open **PowerShell as Administrator** in the repository and verify:

```powershell
git rev-parse HEAD
git status --porcelain
```

The SHA must exactly equal the checkout SHA provided for the gate and `git status --porcelain` must be empty.

Do not `git pull` or switch revisions inside the privileged live procedure unless separately instructed and reviewed. If the checkout is clean but behind the accepted `main`, stop before provisioning and use a separately reviewed fast-forward-only synchronization procedure; never merge/rebase arbitrary local work as part of the live gate.

### 4.1 Retry after a partial failed provisioning attempt

If a prior startup attempt failed after creating any owned WP15 live runtime state, do not rerun startup blindly. From the same elevated, clean exact checkout, run the marker-guarded cleanup first as **one complete PowerShell command on one physical line**:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_wp15_live_web_acceptance.ps1" -ExpectedImplementationSha "<EXACT_MAIN_SHA>" -Cleanup -AsJson
```

Require successful cleanup before continuing. Cleanup is ownership-marker guarded and must not be replaced by manual deletion, ACL weakening or PostgreSQL edits.

For OWNER copy/paste commands in this runbook, prefer a complete single-line invocation rather than PowerShell backtick line continuation. Microsoft documents that backtick continuation is fragile: an extra trailing space breaks continuation and can make a visually similar pasted command execute only partially.

## 5. Start the temporary acceptance runtime

From the same elevated, clean exact checkout, run the reviewed starter as **one complete PowerShell command on one physical line**:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\start_wp15_live_web_acceptance.ps1" -ExpectedImplementationSha "<EXACT_MAIN_SHA>" -AsJson
```

Do not call the underlying provisioner's `-Apply` mode directly for normal OWNER startup. The starter performs exact-head/worktree/runtime-role checks, temporarily supplies only the scheduled-task batch-logon capability when required, invokes the existing provisioner, and restores the pre-start account-right state before returning.

Expected safe result from the child provisioner includes:

```text
runtime_root_owned: true
deployment_bound: true
pending_boundary_ready: true
temporary_task_running: true
runtime_role_enabled: true
loopback_runtime_ready: true
postgres_authentication: SSPI
postgres_trust_used: false
database_password_persisted: false
broker_write_authority_added: false
trading_methods: false
gateway_entrypoint: app:app
ready: true
```

This command does **not** ask for the T-Invest token.

If `ready` is false or the command fails, do not bypass a check and do not edit PostgreSQL/ACL/task/account-right state manually. Use the reviewed cleanup procedure in section 9 and report only the fixed reason/error code. A loopback-start timeout may additionally report sanitized `task_state` and numeric `last_task_result`; those two diagnostic fields are safe to return to engineering and replace raw task/Event Log collection.

## 6. Provision READ credential through Web

On the Lenovo itself, open:

`http://127.0.0.1:8765/settings`

The local acceptance login surface is visible only on loopback. Click **Локальный OWNER acceptance**. This is an accepted historical acceptance-only identity switch, not a production login provider and not part of the Timeweb runtime. Under Amendment 18, current/future ordinary product login is Telegram Login only; VK ID is retired.

In **Settings -> Broker Connections**:

1. paste the real T-Invest **READ-only** token into the password field;
2. choose **Проверить READ-token**;
3. confirm that only the intended masked broker accounts are offered;
4. select the intended account(s);
5. choose **Подключить выбранные счета**.

Do not paste the token into PowerShell, chat, GitHub, browser developer tools, screenshots or notes. Do not send full broker account IDs, account fingerprints, portfolio values or position details outside the local acceptance browser.

The backend must reject broader/unknown authority; there is no FULL/TRADE fallback.

## 7. Perform deferred WP15 parity check

For the intended connected account choose **Live READ acceptance**.

The browser displays a short-lived, `no-store` acceptance challenge containing only what OWNER must compare locally:

- masked account label;
- portfolio total/currency;
- one deterministic sample position label, quantity, unit price and sample value;
- freshness state/timestamp/age.

Compare those values against the intended T-Invest broker view at the same time. Check each confirmation box **only when it is actually true**:

- intended masked account is correct;
- portfolio summary matches;
- sample position quantity/value matches;
- snapshot freshness is acceptable.

Then choose **Подтвердить live acceptance**.

The private displayed values remain only in the short-lived browser/in-memory challenge. Durable pending evidence contains only booleans/status/timestamps/count and implementation identity; it contains no raw token, full account ID/fingerprint, portfolio total, quantity, price or position payload.

## 8. OWNER finalization and automatic runtime cleanup

After successful Web confirmation, return to **PowerShell as Administrator** in the same clean exact checkout and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\finalize_wp15_live_web_evidence.ps1" -AsJson
```

The finalizer:

1. validates the exact pending schema and exact implementation SHA;
2. requires every real OWNER parity boolean;
3. rejects stale/implausible timestamps and forbidden private fields;
4. binds hashes of the reviewed acceptance security scripts;
5. removes the temporary task;
6. disables the runtime role anchor again;
7. restores the pre-acceptance `pg_hba.conf` and `pg_ident.conf`;
8. removes the runtime/pending directory;
9. writes only sanitized final evidence under `C:\ProgramData\OmniCIO\wp15-live` with protected ACLs.

A successful final JSON may be shared because it is designed to contain only sanitized booleans/reason/hash metadata. Do not share screenshots of the browser comparison screen.

## 9. Abort / recovery before finalization

If the live browser procedure cannot be completed, close the browser and run from the same exact elevated checkout:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_wp15_live_web_acceptance.ps1" -ExpectedImplementationSha "<EXACT_MAIN_SHA>" -Cleanup -AsJson
```

Cleanup is ownership-marker guarded. It removes only the temporary WP15 live runtime/task, disables the runtime role anchor and restores the saved PostgreSQL authentication files when they were changed.

The acceptance starter restores any `SeBatchLogonRight` that it itself added before it exits. Cleanup therefore must not manually edit local security policy or account rights.

Do not manually delete `C:\ProgramData\OmniCIO\runtime\wp15-live`, edit PostgreSQL authentication files, alter the runner identity, or weaken ACLs as a shortcut.

## 10. Independent runner acceptance

OWNER finalization is necessary but not sufficient. The source-controlled `V10 WP15 Live Web OWNER Audit` must then run on the exact accepted implementation using the non-admin Lenovo GitHub runner.

The runner audit must independently prove:

- final evidence exists and is readable but not writable by the runner;
- exact implementation and script hashes match;
- forbidden private fields are absent;
- temporary acceptance task is absent;
- `omni-cio-runtime` is disabled again and has no final-evidence access;
- runner still cannot read/write the accepted READ-vault deny sentinel/connection boundary;
- `app:app`, `trading_methods=false` and no broker-write authority remain intact.

Only after that audit is GREEN may the program status credit the deferred WP15 live evidence / Block D Exit Gate and consider WP18 unlock.

## 11. Evidence that must never be sent

Never send or upload:

- T-Invest token;
- BitLocker/recovery/encryption keys;
- full broker account ID or account fingerprint;
- portfolio totals;
- position names/quantities/prices/values from the private comparison screen;
- private portfolio payload;
- DPAPI ciphertext or secret-vault files.

Only the sanitized finalizer/auditor result is acceptable as external evidence.

## 12. Upstream implementation references

PostgreSQL 18 SSPI and explicit username-map behavior:

- `https://www.postgresql.org/docs/18/sspi-auth.html`
- `https://www.postgresql.org/docs/18/auth-username-maps.html`

Windows Task Scheduler password/S4U logon semantics:

- `https://learn.microsoft.com/windows/win32/taskschd/taskfolder-registertaskdefinition`

Windows account-right management used by the acceptance-only starter:

- `https://learn.microsoft.com/windows/win32/api/ntsecapi/nf-ntsecapi-lsaaddaccountrights`
- `https://learn.microsoft.com/windows/win32/api/ntsecapi/nf-ntsecapi-lsaremoveaccountrights`
- `https://learn.microsoft.com/windows/win32/api/ntsecapi/nf-ntsecapi-lsaenumerateaccountrights`

PowerShell line-continuation guidance:

- `https://learn.microsoft.com/powershell/module/microsoft.powershell.core/about/about_parsing`

These references justify the transport/runtime/command/account-right mechanics only; V10 authority and Exit Gate ordering remain defined by the source-controlled Master Plan and amendments.
