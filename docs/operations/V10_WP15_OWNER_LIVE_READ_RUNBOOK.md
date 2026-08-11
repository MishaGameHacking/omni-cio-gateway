# Omni-CIO V10 — WP15 Deferred Live Read-Only Acceptance Runbook

Status: **WEB SUPPORT PATH UNDER REVIEW — OWNER ACTION FORBIDDEN UNTIL SUPPORT PR MERGE + POST-MERGE GREEN**

Authority: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`, the accepted Identity/Multi-Tenant amendment, `docs/architecture/V10_WP15_TINVEST_READONLY_CONTRACT.md`, and `docs/architecture/V10_WP15_LIVE_WEB_ACCEPTANCE_CONTRACT.json`.

## 1. Purpose

This runbook completes only the deferred WP15 live READ acceptance after WP16/WP17. It does not implement WP18 Portfolio Dashboard feature work and does not activate public ingress, public multi-user registration, TRADE credentials, broker write authority, transfers/withdrawals, or Real execution.

Normal broker credential entry remains:

`authenticated Omni-CIO Web -> Settings -> Broker Connections -> T-Invest READ token`.

The raw broker token is never an OWNER PowerShell argument, GitHub secret, environment-variable input, chat value, CI value, log field or evidence artifact. The browser sends it once to the local/private Web backend, clears the form after validation, and never receives it back.

## 2. Hard prerequisites before any real token

Do **not** perform the live procedure until all of the following are true:

1. the WP15 live Web support PR is squash-merged;
2. the exact merge SHA is confirmed as `main`;
3. mandatory post-merge Regression Shield is GREEN on that exact SHA;
4. the reviewed support workflow is GREEN on the accepted implementation;
5. OWNER is given that exact implementation SHA for the local procedure.

Until then, `broker_read` may remain unprovisioned and no real T-Invest token is required.

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

The temporary scheduled task uses password logon because the acceptance runtime must have both network access to T-Invest and access to the DPAPI-protected READ vault. S4U is explicitly not used because Windows documents that S4U scheduled tasks have no network or encrypted-file access.

## 4. OWNER preparation after support acceptance

Only after the prerequisites in section 2 are satisfied, use the exact accepted `main` checkout on the Lenovo node.

Open **PowerShell as Administrator** in the repository and verify:

```powershell
git rev-parse HEAD
git status --porcelain
```

The SHA must exactly equal the implementation SHA provided for the gate and `git status --porcelain` must be empty.

Do not `git pull` or switch revisions inside the privileged live procedure unless separately instructed and reviewed.

## 5. Start the temporary acceptance runtime

From the same elevated, clean exact checkout:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_wp15_live_web_acceptance.ps1" -ExpectedImplementationSha "<EXACT_MAIN_SHA>" -Apply -AsJson
```

Expected safe result includes:

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

If `ready` is false or the command fails, do not bypass a check and do not edit PostgreSQL/ACL/task state manually. Use the reviewed cleanup procedure in section 9 and report only the fixed reason/error code.

## 6. Provision READ credential through Web

On the Lenovo itself, open:

`http://127.0.0.1:8765/settings`

The local acceptance login surface is visible only on loopback. Click **Локальный OWNER acceptance**. This is an acceptance-only local identity switch and is not a third production login provider; ordinary product login remains Telegram/VK ID.

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
4. binds hashes of the provisioner/runtime/database/finalizer/auditor scripts;
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

These references justify the transport/runtime mechanics only; V10 authority and Exit Gate ordering remain defined by the source-controlled Master Plan and amendments.
