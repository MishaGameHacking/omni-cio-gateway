# Omni-CIO V10 — WP22A Private Remote Access Runbook

Status: **IMPLEMENTATION / DO NOT APPLY UNTIL WP22A CI IS GREEN**

## Purpose

This runbook covers the WP22A private remote access candidate. It intentionally uses the existing Omni-CIO Web App and keeps the Web backend loopback-only. It does not authorize public Internet ingress, Tailscale Funnel, public multi-user registration, broker-write authority or Real execution.

## Runtime shape

```text
AUTHORIZED OWNER DEVICE
        |
        | encrypted tailnet access
        v
Tailscale Serve / HTTPS
        |
        | local reverse proxy + Tailscale identity headers
        v
127.0.0.1:<web-port>
        |
        v
apps.api.wp22a_remote:create_private_remote_app
        |
        +--> existing Web/API routes
        +--> PostgreSQL server-side sessions
        +--> existing tenant-scoped READ broker connection flow
```

The backend must not listen on a LAN/Tailscale/public interface when Tailscale identity headers are used for the private OWNER gate.

## Pre-application requirements

Do not perform the OWNER-local step until the reviewed WP22A PR has passed its code/static/security gates.

The Lenovo must have:

- the reviewed exact WP22A Git head;
- the accepted PostgreSQL/Web runtime baseline;
- Tailscale installed and already joined to the intended OWNER-controlled tailnet;
- HTTPS/Serve support available in the installed Tailscale version;
- no active Funnel/public configuration on the Personal node;
- no unrelated existing Serve configuration that would be overwritten by the Omni-CIO root route.

The phone or other OWNER browser device must join the same authorized tailnet before the separate-device rehearsal.

Never send Tailscale authentication keys, provider credentials, OWNER login, broker credentials or private portfolio values to GitHub/CI/chat.

## Source-controlled deployment boundary

WP22A adds two reviewed Windows scripts:

```text
infrastructure/windows/run_wp22a_private_remote_runtime.ps1
infrastructure/windows/provision_wp22a_private_remote_access.ps1
```

The runtime launcher:

- runs only as the existing non-admin `omni-cio-runtime` identity;
- requires an exact source-controlled deployment SHA marker;
- binds Uvicorn only to `127.0.0.1`;
- uses PostgreSQL SSPI under the existing runtime role;
- activates only `apps.api.wp22a_remote:create_private_remote_app`.

The provisioning gate:

- requires an exact clean reviewed Git head;
- reuses the accepted WP15/WP17 Web deployment and broker READ-vault boundary instead of creating a second Web stack;
- derives the local `*.ts.net` DNS name and OWNER Tailscale login fingerprint from local Tailscale status without writing the raw login to GitHub;
- rejects active Funnel/public ingress;
- refuses to overwrite an unrelated existing Serve configuration;
- installs a limited scheduled task with restart-on-failure and startup trigger;
- verifies that the Web listener is loopback-only;
- configures Tailscale Serve in background mode to the loopback Web port;
- performs a real HTTPS OWNER identity/session/login/logout probe through Serve;
- still leaves a separate phone/browser reachability rehearsal as OWNER evidence.

## Private runtime configuration

The runtime receives three non-source-controlled values through the local scheduled-task boundary:

```text
OMNI_V10_WEB_PRIVATE_REMOTE=1
OMNI_V10_WEB_EXTERNAL_HOST=<exact *.ts.net node hostname>
OMNI_V10_TAILSCALE_OWNER_LOGIN_SHA256=<sha256 fingerprint>
```

The fingerprint is derived locally from the normalized OWNER Tailscale login. The raw login is not a repository setting or output field.

The application factory is:

```text
apps.api.wp22a_remote:create_private_remote_app
```

The Web process remains bound to `127.0.0.1` only.

## Tailscale Serve boundary

The reviewed target is Tailscale **Serve**, not Funnel. Serve proxies the local loopback Web service into the private tailnet HTTPS endpoint. Current Tailscale CLI documentation defines `tailscale serve --bg <target>` for background sharing and `tailscale serve status` / `status --json` for verification; the installed client remains the runtime source of truth if CLI syntax changes again.

The provisioning gate fails closed rather than enabling Funnel. Before acceptance it verifies all of the following locally:

- the service target is the loopback Web port;
- the reported URL is the intended `https://<node>.<tailnet>.ts.net` host;
- the Serve route is present only after the backend is ready;
- Funnel/public exposure is absent;
- the application Web process itself is not listening on a non-loopback address;
- a real HTTPS request through Serve receives the expected OWNER identity and can create/revoke a server-side session.

## OWNER-local commands — only after exact-head CI GREEN

From an elevated PowerShell in the exact clean reviewed checkout, the reviewed apply command is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_wp22a_private_remote_access.ps1" -ExpectedImplementationSha "<EXACT_REVIEWED_HEAD>" -Apply -AsJson
```

The script returns the private HTTPS URL locally. Do not paste the raw Tailscale login or any credentials into the command.

A non-mutating verification after apply is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_wp22a_private_remote_access.ps1" -ExpectedImplementationSha "<EXACT_REVIEWED_HEAD>" -Verify -AsJson
```

Rollback is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_wp22a_private_remote_access.ps1" -ExpectedImplementationSha "<EXACT_REVIEWED_HEAD>" -Cleanup -AsJson
```

Cleanup disables the WP22A Serve route and remote task and attempts to restart the accepted local Web task. It does not enable Funnel as a fallback.

## Expected phone/browser behavior

From an authorized OWNER device inside the intended tailnet:

1. Open the exact HTTPS tailnet URL printed locally by the provisioning gate.
2. The application shows `OWNER private access` only when the request reached the backend through the reviewed private remote path.
3. Select the private access action. The backend binds the Tailscale identity to the configured OWNER fingerprint.
4. A successful authentication creates a server-side session and Secure/HttpOnly/SameSite cookie.
5. Navigate through Portfolio, Watchtower, Research, Decisions/Risk/Plans and System to prove the existing single Web App is reachable remotely.
6. Logout, reopen the URL and verify the server-side session state changes as expected.

A wrong tailnet identity, direct backend request, hostile Host/Origin, missing CSRF token or excessive login attempts must fail closed. These negative paths are deterministic CI obligations; the OWNER is not asked to perform hostile tests manually on the phone.

## Sanitized acceptance evidence

If/when OWNER action becomes necessary, return only facts similar to:

```text
WP22A private remote gate: PASS
Exact implementation binding: True
Backend loopback-only: True
Tailscale Serve private: True
Funnel/public ingress: False
OWNER identity binding: True
Secure session: True
Phone HTTPS reachability: True
Logout/session revoke: True
```

Do not include the actual tailnet login, authentication keys, broker token, full account ID, portfolio totals or private position details. The private `*.ts.net` URL does not need to be sent back to engineering if the sanitized booleans are sufficient.

## Rollback

If the private remote path is unsafe or unavailable:

- run the reviewed `-Cleanup` mode;
- keep the existing local/private Web path intact;
- keep `REAL_TRADING_ENABLED=false`;
- do not substitute Funnel/public exposure as a workaround;
- preserve the last accepted V9 rollback and current main until WP22A is accepted.
