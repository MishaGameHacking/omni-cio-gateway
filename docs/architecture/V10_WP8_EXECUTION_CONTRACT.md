# Omni-CIO V10 — WP8 Execution Contract

Status: **WP8 implementation contract / proposed until merged**  
Work package: **WP8 — Local Secret Store and rotation**  
Accepted base: `4089ea7dffd79739ac657b52d648eaa627e2a804`  
Depends on: accepted WP6 identity boundary + accepted WP7 bootstrap

## 1. Goal

Store future broker, Telegram, local-encryption and approved external-source credentials outside GitHub and outside ordinary GitHub Actions access, with a local Windows encryption boundary, explicit secret lifecycle metadata, narrow per-role ACLs, rotation/revocation procedures and privacy-safe evidence.

WP8 establishes the **secret-storage boundary only**. It does not activate any application service, broker-write method, Telegram runtime, Web runtime, AI/Cortex runtime, scheduler, backup system or Real-money execution path.

## 2. Non-negotiable inherited invariants

- production/recovery V9 remains protected;
- Render/Gateway entrypoint remains `app:app`;
- legacy marker `trading_methods=false` remains unchanged;
- GitHub engineering access is not secret access and never means money authority;
- ordinary CI runner remains non-admin and may not read secret payload bytes;
- `omni-cio-runtime` remains separate from `omni-cio-execution`;
- runtime role may never receive the future trading credential;
- execution role may receive only its future trading-class credential, not broad secret-store access;
- no transfer/withdrawal authority is introduced;
- no real secret value is required for WP8 acceptance.

## 3. Selected protection architecture

WP8 uses the Windows Data Protection API through `.NET System.Security.Cryptography.ProtectedData` with `DataProtectionScope.LocalMachine` for at-rest encryption of local secret blobs, combined with **protected NTFS DACLs as the same-machine authorization boundary**.

This selection is deliberate:

1. Windows DPAPI is OS-provided and requires no new recurring service, vault daemon or cloud dependency.
2. Local-machine scope allows a future Windows service running under the reviewed non-admin runtime/execution identity to decrypt a blob after that identity is granted file access.
3. Local-machine DPAPI is **not** treated as per-user authorization. Any same-machine principal that obtains the ciphertext could ask DPAPI to unprotect it. Therefore the protected file/directory DACL is mandatory, fail-closed and independently audited.
4. Classic `CurrentUser` DPAPI is not selected for the shared service-secret store because OWNER provisioning would bind the blob to the OWNER profile rather than the future service identity.
5. DPAPI-NG/SID protection remains a possible later hardening option, but WP8 does not depend on undocumented assumptions about standalone-local-account interoperability. Changing the protector later requires an ADR/migration/recovery plan and re-encryption rehearsal.

At-rest security therefore composes:

`BitLocker/full-disk protection from WP5 + DPAPI LocalMachine encryption + protected NTFS DACL + separate non-admin service identities`.

Administrator/SYSTEM compromise remains an OS trust-boundary compromise; WP8 does not claim to defend secrets from a trusted local administrator.

## 4. Secret classes and consumers

The fixed WP8 classes are:

| Secret class | Purpose | Current intended consumer | WP8 real value |
|---|---|---|---|
| `broker_read` | future V10 production read-only broker credential | `omni-cio-runtime` | not provisioned for WP8 acceptance |
| `broker_trading` | future isolated Real BUY/SELL credential | `omni-cio-execution` only | not provisioned for WP8 acceptance |
| `telegram_bot` | future Telegram bot credential | sealed OWNER/SYSTEM until Block F binds a reviewed consumer | not provisioned |
| `local_encryption_key` | future local encryption/recovery material | sealed OWNER/SYSTEM until owning WP binds a consumer | not provisioned |
| `external_source` | approved future external research/source credential | sealed OWNER/SYSTEM until owning adapter binds a consumer | not provisioned |

A future WP may narrow a sealed class to a new reviewed service identity. It may not silently broaden the store or reuse `broker_trading` as a read fallback.

## 5. Filesystem layout

Existing WP6-owned root is reused and **not re-created or weakened**:

`C:\ProgramData\OmniCIO\secrets`

WP8 owns only reviewed children:

- `read-broker\`;
- `execution\wp8-trading\` (child of the existing WP6 execution boundary; WP6 sentinel remains untouched);
- `telegram\`;
- `encryption\`;
- `external\`.

Each class directory contains only WP8-owned marker/sentinel material until a later contour is ready for a real value. The future active blob name is fixed by the machine-readable contract and is binary DPAPI ciphertext.

Privacy-safe audit/lifecycle evidence is stored separately under:

`C:\ProgramData\OmniCIO\wp8`

That evidence root may be readable by the ordinary CI runner because it contains no secret value, ciphertext, secret hash, SID, raw username, hostname, account number or private portfolio payload.

## 6. ACL model

Every WP8 secret-class directory and secret/sentinel file uses inheritance-protected ACLs.

Mandatory principals:

- `SYSTEM`: FullControl;
- built-in `Administrators`: FullControl;
- intended reviewed service identity, only where a consumer exists: read-only data access;
- ordinary CI runner service identity: metadata-only `ReadPermissions`/`ReadAttributes` (and directory traversal where required), **never `ReadData`/ListDirectory/write/delete/change-permissions/take-ownership**.

No broad `Users`, `Authenticated Users`, `Everyone` or inherited read grant may expose secret payload bytes.

For `broker_read`, only `omni-cio-runtime` receives secret data read.  
For `broker_trading`, only `omni-cio-execution` receives secret data read.  
The runtime role has no trading-secret data-read grant.  
The execution role has no read-broker/Telegram/encryption/external data-read grant.

## 7. Secret input and plaintext-memory rules

Real-value set/rotate operations are local OWNER-admin operations only and are never invoked by GitHub Actions.

The manager:

- has no secret/token/password/API-key value parameter;
- refuses secret-changing operations when `GITHUB_ACTIONS=true`;
- obtains a value interactively with `Read-Host -AsSecureString`;
- converts the SecureString to a temporary byte buffer only in memory;
- always calls `Marshal.ZeroFreeBSTR` on the temporary BSTR;
- clears plaintext byte arrays in `finally`;
- never writes plaintext to disk, stdout/stderr, environment variables, command-line arguments, history, metadata or logs;
- never prints encrypted blob bytes either;
- atomically replaces ciphertext during rotation and removes the transient encrypted backup after successful replacement.

No generic CLI command that prints the decrypted secret is introduced in WP8.

## 8. Lifecycle metadata

Each class has sanitized metadata with:

- `secret_class`;
- logical owner (`OWNER_ADMIN`, never a username);
- purpose;
- local scope;
- intended consumer role or sealed state;
- lifecycle state `UNPROVISIONED | ACTIVE | REVOKED | COMPROMISED`;
- integer version;
- rotation/revocation procedure identifier;
- compromise indicator;
- provisioned boolean.

Metadata must not contain:

- secret value;
- ciphertext;
- hash/digest/fingerprint derived from the secret value;
- SID/raw username/hostname;
- full broker account identifier;
- private portfolio payload.

A compromise state requires revocation/rotation of the external credential in its owning system when that contour exists; deleting local ciphertext alone is never described as remote revocation.

## 9. Rotation rehearsal

WP8 acceptance uses generated random **non-secret sentinel material only**.

The OWNER apply performs DPAPI protect/unprotect and replacement rehearsals for the `broker_read` and `telegram_bot` classes without displaying sentinel bytes. The sanitized state records only pass/fail booleans.

Persistent non-secret encrypted sentinel files exist only to prove ACL behavior. The ordinary CI runner must receive `ACCESS_DENIED` when attempting data-read while still being able to inspect the reviewed ACL metadata.

No real broker or Telegram token is required or requested by the WP8 Exit Gate.

## 10. Diagnostics / crash evidence

Repository workflows and WP8 diagnostic scripts:

- never collect the secret root as an artifact;
- never collect process dumps from a secret-changing process;
- never include decrypted/ciphertext secret material in JSON evidence;
- use explicit allowlisted privacy-safe fields only;
- treat any detected raw-secret logging path as P0.

Future real-secret provisioning remains a local interactive operation and must not be combined with diagnostic bundle creation.

## 11. Required verification

Before WP8 acceptance:

1. static contract/tests prove secret-value input surfaces are absent and inherited money-authority boundaries are unchanged;
2. hosted Windows clean-node compatibility proves all WP8 PowerShell parses in Windows PowerShell 5.1 and default preview is non-mutating;
3. Lenovo OWNER apply establishes the class directories, protected DACLs, sanitized evidence and non-secret rotation sentinels;
4. repeated apply is safe and does not overwrite a future real secret;
5. authoritative non-admin Lenovo audit proves:
   - runner data-read attempts on protected sentinels are `ACCESS_DENIED`;
   - runner has no write/control rights;
   - runtime read is limited to `broker_read`;
   - execution read is limited to `broker_trading`;
   - sealed future classes have no service data-read grant;
   - no broad read exposure exists;
   - read-token and Telegram rotation rehearsals passed;
   - no real secret values were used;
6. repository/Git-history secret scan and existing SAST/dependency gates pass;
7. rollback preview/apply is marker-guarded and refuses cleanup if a real secret is marked provisioned.

## 12. Exit Gate

WP8 is PASS only when exact-head CI and Lenovo evidence prove:

- no plaintext secret exists in the repository, CI/log/diagnostic evidence, crash-dump collection owned by WP8, or Web UI;
- no real secret value/hash/ciphertext is uploaded to GitHub;
- ordinary CI cannot read secret payload bytes;
- intended runtime/execution consumers have only their reviewed class read grant;
- trading credential boundary remains execution-only;
- generated read/Telegram rotation rehearsal succeeds;
- no real secret was required for acceptance;
- `app:app`, `trading_methods=false`, service-inactive state and V9 safety/money-authority invariants remain intact.

Only after accepted merge + post-merge Regression Shield + canonical status update may the next Master Plan WP begin.

## 13. Owner participation

WP8 development proceeds without OWNER interruption until the exact reviewed Lenovo apply is the remaining blocker.

For WP8 acceptance, OWNER participation is limited to running the reviewed local provisioning/rehearsal block under elevated PowerShell. **Do not enter real broker/Telegram/encryption credentials for the WP8 acceptance run.** Real values are entered later only when the corresponding owning contour is ready.
