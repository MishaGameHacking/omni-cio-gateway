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
- no conflicting public Funnel configuration for the Omni-CIO Web port.

Never send Tailscale authentication keys, provider credentials, OWNER login, broker credentials or private portfolio values to GitHub/CI/chat.

## Private runtime configuration

The runtime needs three non-source-controlled values:

```text
OMNI_V10_WEB_PRIVATE_REMOTE=1
OMNI_V10_WEB_EXTERNAL_HOST=<exact *.ts.net node hostname>
OMNI_V10_TAILSCALE_OWNER_LOGIN_SHA256=<sha256 fingerprint>
```

The fingerprint is derived locally from the normalized OWNER Tailscale login. The raw login is not a repository setting.

The application factory is:

```text
apps.api.wp22a_remote:create_private_remote_app
```

The Web process remains bound to `127.0.0.1` only.

## Tailscale Serve boundary

The reviewed target is Tailscale **Serve**, not Funnel. Serve proxies the local loopback Web service into the private tailnet HTTPS endpoint. The exact CLI syntax must be checked against the installed Tailscale version before the OWNER-local rehearsal because the Tailscale CLI has changed across releases.

Before acceptance, verify all of the following locally:

- the service target is the loopback Web port;
- the reported URL is the intended `https://<node>.<tailnet>.ts.net` host;
- access is described as available within the tailnet;
- Funnel/public exposure is not enabled for that service;
- the application Web process itself is not listening on a non-loopback address.

## Expected browser behavior

From an authorized OWNER device inside the intended tailnet:

1. Open the exact HTTPS tailnet URL.
2. The application shows `OWNER private access` only when the request reached the backend through the reviewed private remote path.
3. The private access action binds the Tailscale identity to the configured OWNER fingerprint.
4. A successful authentication creates a server-side session and Secure/HttpOnly/SameSite cookie.
5. Unsafe browser requests require the same HTTPS Origin and the per-session CSRF token.
6. Logout and revoke-all continue to invalidate server-side sessions.

A wrong tailnet identity, direct backend request, hostile Host/Origin, missing CSRF token or excessive login attempts must fail closed.

## Sanitized acceptance evidence

If/when OWNER action becomes necessary, the reviewed rehearsal must emit only facts similar to:

```text
WP22A private remote gate: PASS
Exact implementation binding: True
Backend loopback-only: True
Tailscale Serve private: True
Funnel/public ingress: False
OWNER identity binding: True
Secure session: True
CSRF/origin/host enforcement: True
Unauthorized device/path rejection: True
```

Do not include the actual tailnet login, authentication keys, broker token, full account ID, portfolio totals or private position details.

## Rollback

If the private remote path is unsafe or unavailable:

- disable the WP22A private remote runtime activation;
- disable/reset only the Omni-CIO Tailscale Serve configuration;
- keep the existing local/private Web path intact;
- keep `REAL_TRADING_ENABLED=false`;
- do not substitute Funnel/public exposure as a workaround.
