# Omni-CIO V10 — WP8 Local Secret Store Runbook

Status: **WP8 operator runbook / proposed until merge**

This runbook covers only the WP8 local secret-store boundary. It never asks for a real broker, Telegram or encryption value during WP8 acceptance.

## Safety rules

- Work only from the exact reviewed PR merge checkout supplied in the WP8 PR.
- Run OWNER apply/rollback only in an elevated local PowerShell.
- Do not use `git pull`/`git fetch` during the evidence hand-off unless the PR instructions explicitly change.
- Do not paste any real secret into a command line, environment variable, GitHub comment, ChatGPT message, screenshot or log.
- WP8 acceptance uses generated non-secret sentinels only.
- `C:\ProgramData\OmniCIO\secrets` is local runtime state, never a GitHub artifact.
- A successful WP8 apply does not enable trading or start an Omni-CIO application service.

## 1. Preview

From the reviewed repository checkout:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\provision_wp8_secret_store.ps1
```

Preview is non-mutating. Before initial apply, `OWNER_ACTION_REQUIRED` is expected.

Machine-readable preview:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\provision_wp8_secret_store.ps1 -AsJson
```

The JSON is deliberately privacy-safe and must not contain SIDs, usernames, hostnames, secret/ciphertext values, hashes derived from values or account identifiers.

## 2. WP8 acceptance apply

Only after the PR says the exact merge checkout is reviewed, verify:

```powershell
git rev-parse HEAD
```

Then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\provision_wp8_secret_store.ps1 -Apply
```

Expected properties:

- WP6 secret root and execution sentinel are present and left untouched;
- runtime/execution identities remain disabled non-admin role anchors;
- the CI runner identity is resolved internally but never printed;
- WP8 class directories and protected ACLs are created/repaired;
- non-secret DPAPI sentinel material is created;
- broker-read and Telegram rotation rehearsals pass;
- no active real secret blob is created;
- real secret values used: `NO`.

Repeat the same apply once. It must remain safe and must never overwrite a future active secret blob.

## 3. Verify

OWNER-side verification:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\provision_wp8_secret_store.ps1 -Verify
```

The authoritative GitHub WP8 workflow then runs as the ordinary non-admin `omni-cio-ci` runner and must prove its data reads are denied.

## 4. Future real-value entry/rotation

**Do not perform this during WP8 acceptance.** A later owning contour will explicitly request it when needed.

The reviewed manager never accepts a plaintext value argument. Example future flow:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\manage_wp8_secret.ps1 `
  -Operation Set `
  -SecretClass broker_read `
  -AcknowledgeContourReady
```

PowerShell prompts locally with `Read-Host -AsSecureString`. Nothing typed is sent to GitHub.

Rotation uses the same local prompt:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\manage_wp8_secret.ps1 `
  -Operation Rotate `
  -SecretClass broker_read `
  -AcknowledgeContourReady
```

Revocation removes the local active ciphertext and marks sanitized lifecycle state. If the external credential may have been exposed, its issuer-side revocation/rotation is still required; deleting the local blob is not remote revocation.

## 5. Compromise handling

If a real value is suspected to have appeared in Git, Actions logs, diagnostics, UI, a screenshot or any untrusted place:

1. stop the affected contour;
2. treat exposure as P0;
3. revoke/rotate at the external issuer;
4. do not paste the compromised value into an issue/PR/chat while investigating;
5. inspect Git/log history using hashes/pattern metadata only where possible;
6. restore only through the reviewed local manager after the incident is resolved.

## 6. Rollback

Preview:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\rollback_wp8_secret_store.ps1
```

Apply:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\rollback_wp8_secret_store.ps1 -Apply
```

Rollback is allowed only when WP8 metadata proves all real secret classes are unprovisioned/revoked and no active real blob exists. It removes only WP8-owned children/evidence. It does not remove:

- the WP6 secret root;
- the WP6 execution sentinel;
- WP6 identities/runner ACLs;
- WP7 prerequisites/directories;
- Windows prerequisites;
- any V9 production/recovery asset.

## 7. Evidence that is safe to share

Safe:

- exact Git SHA;
- PASS/FAIL and reason codes;
- class-directory present booleans;
- intended-grant/runner-deny booleans;
- `ACCESS_DENIED` result labels;
- rotation-rehearsal boolean;
- lifecycle state/version when no value/hash/ciphertext is included;
- `real_secret_values_used: false`.

Never share:

- raw secret value;
- encrypted blob bytes;
- DPAPI payload;
- SID or raw service username;
- full account number;
- private portfolio payload;
- secret-derived hash/fingerprint.
