# Omni-CIO V10 WP22A — Private Remote Access Runbook

Status: **IMPLEMENTATION / OWNER ACCEPTANCE NOT YET AUTHORIZED**  
Transport: **Tailscale Serve, tailnet-only**

## Safety state

Until the WP22A deterministic CI gates are GREEN and engineering explicitly reaches the OWNER-only acceptance point:

- do **not** install/configure Tailscale for Omni-CIO from this runbook;
- do **not** open router/firewall ports;
- do **not** enable Tailscale Funnel;
- do **not** create a public DNS record/tunnel;
- do **not** paste Tailscale auth keys, broker tokens, Telegram/VK credentials, recovery keys, private portfolio data, or raw account IDs into chat/GitHub.

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

Tailscale Funnel/public ingress is not part of the selected WP22A path.

## Runtime configuration

Local non-secret/private configuration is stored at:

`C:\ProgramData\OmniCIO\wp22a\private-remote.json`

It contains only:

- exact node `*.ts.net` hostname;
- SHA-256 fingerprint of the OWNER Tailscale login;
- backend loopback host/port;
- explicit false public/Real flags.

The raw OWNER login is not written by the reviewed configurator. Tailscale authentication material is owned by Tailscale and must not be copied into Omni-CIO files.

## Reviewed configuration command

The owning script is:

`infrastructure\windows\configure_wp22a_tailscale_serve.ps1`

When OWNER acceptance is explicitly authorized, run PowerShell as Administrator from the exact reviewed checkout. `-Apply` prompts locally for the OWNER Tailscale login when it is not supplied; the script hashes it before writing configuration. It then turns Funnel off on HTTPS 443 and configures Tailscale Serve HTTPS 443 to the loopback backend.

The safe final evidence emitted by `-AsJson` contains only booleans plus a hostname hash. Do not share the local config file itself.

## Runtime launcher

The backend launcher is:

`infrastructure\windows\run_wp22a_private_remote_runtime.ps1`

It must run as the existing non-admin `omni-cio-runtime` identity and refuses elevation. It verifies the exact deployment SHA marker and local private configuration, forces:

- `OMNI_V10_WEB_PRIVATE_ACCEPTANCE=0`;
- `OMNI_V10_WP15_LIVE_ACCEPTANCE=0`;
- `OMNI_V10_WP22A_PUBLIC_INGRESS=0`;
- `PUBLIC_MULTI_USER_ENABLED=0`;
- `REAL_TRADING_ENABLED=0`;

and launches Uvicorn only on `127.0.0.1`.

## Tailnet policy requirement

WP22A acceptance requires a narrow deny-by-default Tailscale policy. New policy work should use Tailscale grants. Only the OWNER identity/device set required for the Personal cabinet should be able to reach the Lenovo Omni-CIO HTTPS service.

A default allow-all tailnet policy is **not accepted evidence** for the WP22A Exit Gate.

The exact tailnet policy is OWNER-controlled external configuration and is not modified by CI.

## Browser/session behavior

Remote requests must arrive with Tailscale Serve identity headers. The backend compares only a fingerprint of `Tailscale-User-Login` with the locally configured OWNER fingerprint.

On the login screen, `Приватный OWNER доступ` is an acceptance-only bootstrap. It is not returned as an ordinary identity provider and does not alter the canonical Telegram/VK account model.

The remote session cookie is `Secure`, `HttpOnly`, `SameSite=Strict`. Any unsafe authenticated API call additionally requires exact same-origin proof and a session-bound CSRF token obtained from a no-store same-origin endpoint. Session logout/revoke-all remains server-side.

## Recovery / rollback

If private remote access is degraded:

1. keep the accepted local loopback Web path available;
2. stop the private-remote runtime;
3. disable the Serve HTTPS mapping with the matching `tailscale serve ... off` command or reset the reviewed Serve configuration if explicitly required;
4. do not enable Funnel as a workaround;
5. diagnose Tailscale/node policy independently of broker/read data;
6. preserve V9 rollback.

No broker credential rotation is required merely because the remote transport is disabled.

## OWNER acceptance evidence

The eventual OWNER rehearsal must prove only sanitized facts:

- exact reviewed implementation SHA;
- Tailscale Running;
- private Serve mapping present;
- Funnel absent for the Omni-CIO service;
- backend loopback only;
- config ACL/private state valid;
- OWNER remote browser reaches the cabinet;
- a non-OWNER identity cannot bootstrap the session;
- local fallback remains usable.

Raw tailnet identity/login, raw hostname, auth keys, cookies, broker credentials, portfolio values, account IDs, or screenshots containing private investment data are not accepted evidence artifacts.
