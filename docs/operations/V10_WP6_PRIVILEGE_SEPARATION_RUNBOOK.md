# Omni-CIO V10 — WP6 Privilege Separation Runbook

Status: **WP6 implementation runbook**  
Applies only to the dedicated Lenovo Omni-CIO node.

## 1. Goal

Prove that compromise of the ordinary GitHub self-hosted CI identity does not automatically expose a future real-money execution secret or privileged runtime control.

This runbook does not provision any real token or private database material.

## 2. Safety model

WP6 creates only:

- disabled local role anchor `omni-cio-runtime`;
- disabled local role anchor `omni-cio-execution`;
- `C:\ProgramData\OmniCIO\secrets\execution` as the future execution-only secret boundary;
- a fixed **non-secret** sentinel file used solely for negative ACL tests;
- a local owner-only backup of the pre-WP6 ACL descriptors for the runner root and reviewed sensitive GitHub runner configuration files.

The sentinel contains no account data, broker data, credential or token.

The GitHub runner receives only `ReadPermissions` on the sentinel ACL so CI can inspect ACL metadata; it receives no file-data read grant. The execution role receives read-only data access. The ordinary runtime role receives no execution-secret access.

WP6 explicitly denies both future runtime identities (`omni-cio-runtime` and `omni-cio-execution`) access to the entire `C:\actions-runner` tree. This closes the parent-directory delete/rename/replace path rather than protecting only individual configuration files. The deny is identity-specific and does not change the runner service identity or its own permissions.

WP6 additionally hardens only the existing sensitive runner configuration surfaces that are present under `C:\actions-runner`: `.runner`, `.credentials`, `.credentials_rsaparams`, `.service`. Their original ACL descriptors and the original runner-root ACL are backed up locally under the owner-only `C:\ProgramData\OmniCIO\wp6` state directory. The hardened sensitive-file ACL permits only SYSTEM, local Administrators and the actual runner service identity; the runner identity retains `Modify` so the existing service can continue operating. The script does not change the runner registration, service account or normal CI work-directory behavior.

## 3. Preconditions

Before any mutating action:

1. PR #253 exact-head hosted/static checks are green;
2. the privacy-safe WP6 Identity Audit has run and its blockers are understood;
3. the GitHub runner service is running and is **not LocalSystem**;
4. no real secret has been placed under the WP6 secret path;
5. run the provisioning script first without `-Apply`.

If the runner is LocalSystem, stop. Do not weaken the contract or provision around a privileged CI service identity.

### 3.1 Reviewed checkout hand-off — no OWNER-side network fetch

The OWNER-admin apply step must not depend on an interactive `git fetch`, `git pull`, branch checkout, credential helper, proxy, Schannel/TLS session or other OWNER-side GitHub network operation.

The reviewed source hand-off is the authoritative `V10 WP6 Identity Audit` job itself:

1. run/rerun the audit on the reviewed PR head;
2. require its `actions/checkout` step to complete successfully on the Lenovo self-hosted runner;
3. read the PR merge commit SHA from the same audit log / PR metadata;
4. after that job finishes, use the existing worktree at `C:\actions-runner\_work\omni-cio-gateway\omni-cio-gateway`;
5. in the elevated OWNER-admin shell, run only `git rev-parse HEAD` locally and require it to equal that reviewed PR merge commit SHA before `-Apply`.

Do **not** run `git fetch` or `git pull` from the OWNER-admin apply session. A failed interactive GitHub network handshake is therefore not a reason to weaken the WP6 gate or to improvise another checkout. Instead, rerun the authoritative audit so Actions refreshes the reviewed worktree through its own short-lived read-only checkout credentials.

This hand-off preserves `persist-credentials: false`: the OWNER session receives no GitHub credential from Actions and needs no repository credential to perform the privileged local ACL mutation.

## 4. Dry-run

From an OWNER-admin capable session, but without elevation required for dry-run:

```powershell
cd C:\actions-runner\_work\omni-cio-gateway\omni-cio-gateway
git rev-parse HEAD
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\provision_wp6_privilege_boundary.ps1
```

The reported `HEAD` must equal the reviewed PR merge commit SHA from the latest completed authoritative audit before continuing.

Expected provisioning output contains:

- `WP6 privilege provisioning preflight: PASS`;
- runner account class only, never its raw account name;
- count of reviewed sensitive runner config files found;
- `Real secret values used: NO`;
- `DRY RUN ONLY`.

## 5. Apply

Apply is an OWNER-admin action because it creates local Windows role accounts and protected ACLs. After the reviewed-checkout hand-off above, no network Git command is required:

```powershell
git rev-parse HEAD
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\provision_wp6_privilege_boundary.ps1 -Apply
```

Stop if `HEAD` is not the merge SHA from the latest reviewed WP6 audit.

The script is fail-closed:

- it refuses LocalSystem runner identity;
- it refuses unexpected pre-existing accounts with the reserved role names;
- it refuses a non-empty unexpected secret root;
- it never prints or stores the generated role-account passwords;
- it disables both role anchors immediately;
- it removes either role from the local Administrators group if necessary;
- it backs up the original runner-root and reviewed runner-config ACL descriptors locally before hardening them;
- it adds inheritable explicit deny rules for the two future runtime identities on `C:\actions-runner`;
- it hardens only the reviewed sensitive runner config files and keeps the actual runner identity authorized;
- it does not change the GitHub runner registration or service account;
- it creates no real secret.

## 6. Verification

The authoritative verification is the GitHub Actions workflow:

`V10 WP6 Identity Audit`

It runs as the actual `omni-cio-ci` service identity and produces only sanitized role classes/booleans/status values.

Required result:

- runner service running/automatic;
- runner non-admin and distinct from OWNER;
- runner process identity matches the configured runner service identity;
- runtime/execution role anchors present and non-admin;
- explicit runner-root deny rule present for runtime and execution identities;
- sentinel present;
- runner data-read attempt returns `ACCESS_DENIED`;
- runtime has no direct execution-secret read grant;
- execution role has the intended read grant;
- no broad Users/Authenticated Users/Everyone read exposure;
- runtime has no write grant on any reviewed sensitive runner configuration file;
- no broad write exposure on any reviewed sensitive runner configuration file;
- all privacy flags false.

## 7. Why disabled role anchors are acceptable in WP6

WP6 establishes identity and ACL separation. It does not yet install the Core/Web/AI/execution Windows services. Enabling/configuring an actual service under the owning runtime identity belongs to later node bootstrap/service WPs. Keeping these anchors disabled prevents interactive/service logon before that owning package exists while preserving stable local SIDs for ACL validation.

## 8. Rollback

Rollback is available only for WP6-owned state:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\rollback_wp6_privilege_boundary.ps1
```

Dry-run is default. To apply:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\rollback_wp6_privilege_boundary.ps1 -Apply
```

Rollback:

- validates and restores the exact locally backed-up ACL descriptor for the runner root;
- validates and restores exact ACL descriptors for only `.runner`, `.credentials`, `.credentials_rsaparams`, `.service` entries present in the backup;
- refuses an unexpected runner-config path name or malformed security descriptor;
- refuses to remove an account without the exact WP6 ownership marker;
- refuses to remove an enabled role account;
- refuses an unexpected sentinel payload;
- refuses a directory containing non-WP6 material.

It never removes/re-registers the GitHub runner or changes its service account.

## 9. Incidents / fail-closed behavior

If any WP6 audit or provisioning step fails:

- do not add real secrets;
- do not run the workflow elevated as a workaround;
- do not grant Users/Authenticated Users/Everyone access to the execution-secret boundary;
- do not remove the runtime/execution deny from the runner root as a workaround;
- do not broaden runner-config write access;
- do not change `trading_methods=false`;
- do not add broker write credentials to GitHub Actions;
- preserve current V9 production/recovery state and fix the identity/ACL cause first.

## 10. Exit Gate evidence

WP6 can be accepted only after:

1. exact-head Fast PR / Toolchain / Self-Hosted CI are green;
2. exact-head `V10 WP6 Identity Audit` is green on real Lenovo ACLs;
3. static workflow/AI/runtime negative tests are green;
4. no unresolved review blocker remains;
5. squash merge completes;
6. post-merge Regression Shield succeeds on the exact `main` merge SHA.
