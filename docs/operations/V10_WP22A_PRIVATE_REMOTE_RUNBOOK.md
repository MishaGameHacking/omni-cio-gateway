# Omni-CIO V10 WP22A — Private Remote Access Runbook

Status: **IMPLEMENTATION / OWNER ACCEPTANCE NOT YET AUTHORIZED**  
Transport: **Tailscale Serve, tailnet-only**

## Safety state

Until the WP22A deterministic CI gates are GREEN and engineering explicitly reaches the OWNER-only acceptance point:

- do **not** install/configure Tailscale for Omni-CIO from this runbook;
- do **not** open router/firewall ports;
- do **not** enable Tailscale Funnel;
- do **not** create a public DNS record/tunnel;
- do **not** paste Tailscale auth keys, broker tokens, Telegram/VK credentials, recovery keys, private portfolio data, raw account IDs, raw Tailscale OWNER login, raw tailnet hostname, or session cookies into chat/GitHub.

The accepted local/private Web remains the fallback.

## Intended runtime topology

```text
OWNER browser/device
        |
        | Tailscale encrypted tailnet + HTTPS 443
        v
Lenovo Tailscale Serve
        |
        | http://127.0.0.1:8765 only
        v
apps.api.private_remote:create_private_remote_app
        |
        +-- same Web build
        +-- same PostgreSQL
        +-- same tenant/session/broker-read boundaries
```

Tailscale Funnel/public ingress is not part of the selected WP22A path. The Uvicorn launcher binds only loopback, and the application independently rejects a non-loopback backend peer even if otherwise valid-looking proxy identity headers are supplied.

## Runtime configuration

Local non-secret/private configuration is stored at:

`C:\ProgramData\OmniCIO\wp22a\private-remote.json`

It contains only:

- exact node `*.ts.net` hostname;
- SHA-256 fingerprint of the exact decoded OWNER Tailscale login;
- backend loopback host/port;
- explicit false public/Real flags.

The raw OWNER login is not written by the reviewed configurator. Tailscale authentication material is owned by Tailscale and must not be copied into Omni-CIO files.

The configuration directory ACL is protected and accepted only when its allow-principals are exactly the reviewed local authorities: SYSTEM, Administrators and `omni-cio-runtime`. Runtime receives read/execute only; arbitrary additional principals, including the CI runner identity, cause verification to fail closed.

## Tailnet policy requirement

WP22A acceptance requires a narrow deny-by-default Tailscale policy. New policy work uses Tailscale grants. Only the OWNER identity/device set required for the Personal cabinet may reach the Lenovo Omni-CIO HTTPS service on port 443.

A default allow-all tailnet policy is **not accepted evidence** for the WP22A Exit Gate. The exact tailnet policy is OWNER-controlled external configuration and is not modified by CI.

The wrong/non-OWNER identity case is already a deterministic code/security negative test. The OWNER is **not** required to create a second foreign Tailscale account solely to repeat that test physically.

## Private-remote session behavior

Remote requests must arrive through the loopback Tailscale Serve proxy path with Serve identity headers. The backend RFC-2047-decodes `Tailscale-User-Login` when necessary and compares only its SHA-256 fingerprint with the locally configured exact OWNER fingerprint.

On the login screen, `Приватный OWNER доступ` is an acceptance-only bootstrap. It is not returned as an ordinary identity provider and does not alter the canonical Telegram/VK account model.

The private-remote session is deliberately shorter than the earlier local acceptance default:

- idle lifetime: **120 minutes**;
- absolute lifetime: **24 hours**.

Bootstrap rotates the current browser session. The remote session cookie is `Secure`, `HttpOnly`, `SameSite=Strict`. Any unsafe authenticated API call must first resolve a live server-side session, then prove exact same-origin and present a session-bound CSRF token obtained from a no-store same-origin endpoint. A forged/expired cookie is rejected even if the caller can calculate the public CSRF transform from that cookie value. Session logout/revoke-all remains server-side.

Remote responses are hardened with HSTS (`max-age=31536000`), `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer` unless the owning response already sets the relevant header.

## Temporary OWNER acceptance runtime

Physical acceptance does not install a new permanent stack. It temporarily deploys the exact reviewed Git tree under:

`C:\ProgramData\OmniCIO\runtime\wp22a-private`

The owning provisioner is:

`infrastructure\windows\provision_wp22a_private_remote_runtime.ps1`

It reuses the accepted `omni-cio-runtime` non-admin role, creates a random local runtime password only in process memory, temporarily grants `SeBatchLogonRight`, registers a password-logon limited scheduled task, starts the runtime, and removes the temporary batch-logon right. S4U is intentionally not used because this runtime needs network access and the existing DPAPI-protected READ boundary. PostgreSQL runtime authentication remains SSPI; no PostgreSQL `trust` rule or stored DB password is introduced.

The exact source deployment, task principal/action, ACLs, loopback runtime readiness and Tailscale config are all verified before evidence can be finalized.

## OWNER rehearsal commands — use only after engineering explicitly authorizes the gate

Run these from an **Administrator PowerShell** opened in the exact clean reviewed checkout. Engineering will provide the exact accepted PR head when this stage is reached.

First bind the reviewed SHA locally:

```powershell
$expected = (git rev-parse HEAD).Trim().ToLowerInvariant()
if ($expected -notmatch '^[0-9a-f]{40}$') { throw 'STOP: invalid reviewed SHA' }
if (git status --porcelain) { throw 'STOP: working tree is not clean' }
```

Configure and verify Tailscale Serve/private config. `-Apply` prompts locally for the **exact decoded Tailscale OWNER login** when it is not supplied. Do not change its case or send it anywhere. The script hashes it before writing local configuration.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\configure_wp22a_tailscale_serve.ps1" -Apply -AsJson
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\configure_wp22a_tailscale_serve.ps1" -Verify -AsJson
```

Provision and verify the temporary exact-head runtime:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_wp22a_private_remote_runtime.ps1" -ExpectedImplementationSha $expected -Apply -AsJson
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_wp22a_private_remote_runtime.ps1" -ExpectedImplementationSha $expected -Verify -AsJson
```

At this point the OWNER performs only the physical observations that CI cannot synthesize:

1. From a **separate OWNER device already admitted to the reviewed narrow tailnet policy**, open the private `https://<node>.ts.net` cabinet and confirm that the Omni-CIO Web shell opens through Tailscale Serve.
2. On Lenovo, confirm the accepted local loopback Web fallback remains usable.
3. Confirm the tailnet policy is narrow/deny-by-default and grants only the intended OWNER identity/device set access to Lenovo HTTPS 443.

Do not send screenshots containing the hostname, OWNER identity, portfolio, positions, broker data or browser cookies. The final evidence script records only booleans and source hashes.

Finalize the physical evidence only if all three observations are genuinely true:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\finalize_wp22a_private_remote_evidence.ps1" -ExpectedImplementationSha $expected -TailnetPolicyNarrowConfirmed -OwnerRemoteCabinetConfirmed -LocalFallbackConfirmed -AsJson
```

The finalizer then automatically:

- disables the temporary Serve mapping on HTTPS 443;
- explicitly keeps Funnel disabled;
- removes the temporary scheduled task/runtime deployment;
- disables the temporary runtime role again;
- restores the temporary PostgreSQL authentication configuration;
- writes only exact-head/source-hash-bound sanitized evidence under `C:\ProgramData\OmniCIO\wp22a-evidence`.

The CI runner is allowed to read that sanitized evidence but remains unable to modify it or read/write `private-remote.json`.

## Recovery / rollback

If private remote access is degraded before finalization:

1. keep the accepted local loopback Web path available;
2. do **not** enable Funnel as a workaround;
3. use the reviewed provisioner `-Cleanup` path to stop/remove the owned temporary runtime and restore PostgreSQL config;
4. disable the Serve HTTPS mapping;
5. diagnose Tailscale/node policy independently of broker/read data;
6. preserve V9 rollback.

No broker credential rotation is required merely because the remote transport is disabled.

## OWNER acceptance evidence

The eventual OWNER rehearsal proves only sanitized facts:

- exact reviewed implementation SHA and exact source hashes;
- Tailscale private Serve mapping was present;
- Funnel was absent;
- backend was loopback-only;
- private config ACL/state was valid;
- exact temporary runtime ran as non-admin `omni-cio-runtime`;
- narrow OWNER-only tailnet policy was physically confirmed;
- OWNER remote browser reached the cabinet from a separate device;
- local fallback remained usable;
- deterministic wrong-identity denial tests were green;
- Serve/runtime temporary acceptance surface was removed after rehearsal;
- runner can read only sanitized evidence and cannot read/write private Tailscale config.

Raw tailnet identity/login, raw hostname, auth keys, cookies, broker credentials, portfolio values, account IDs, or screenshots containing private investment data are not accepted evidence artifacts.
