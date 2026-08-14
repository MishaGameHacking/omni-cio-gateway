# Omni-CIO V10 — WP22A Execution Contract

Status: **IMPLEMENTATION IN PROGRESS / PRIVATE REMOTE ACCESS PATH**  
Owning package: **WP22A — External Web Access / OWNER Authentication Security Gate**

## 1. Accepted baseline

WP22A starts only after WP22 and its status transition are accepted on `main`.

The accepted baseline already provides:

- one source-controlled Web App under `apps/web`;
- one FastAPI Web/API runtime under `apps/api` and `omni_cio.web`;
- PostgreSQL-backed opaque server-side sessions with idle/absolute expiry and revoke/revoke-all;
- local/private OWNER acceptance and connection-scoped T-Invest READ provisioning;
- tenant-scoped Web requests derived from session context;
- local-only TrustedHost protection;
- `app:app` as the protected V9 Gateway entrypoint;
- no public ingress, no public multi-user activation and no broker-write authority.

## 2. WP22A ingress decision

The first accepted candidate is **private remote access through Tailscale Serve**, not public Internet ingress.

Security consequences:

- the Omni-CIO Web backend remains bound to loopback only;
- Tailscale Serve is the only reviewed reverse-proxy path for this WP22A candidate;
- Tailscale Funnel/public exposure is outside this implementation and remains prohibited;
- a canonical `*.ts.net` host is allowlisted exactly at runtime;
- Tailscale Serve identity headers are accepted only when the backend request itself arrives through the local loopback proxy path;
- the expected OWNER login is represented to the application by a SHA-256 fingerprint supplied as runtime-only configuration; the raw login value is not committed;
- the existing internal local-only TrustedHost boundary is retained. After the outer WP22A middleware validates the canonical remote Host, the request forwarded into the accepted local Web application is normalized back to loopback Host rather than widening the older allowlist globally.

This decision does not activate a public registration service. Telegram Login and VK ID remain the ordinary product authentication providers defined by the accepted identity amendment. Tailnet OWNER identity is a private network access gate for the Personal-node deployment and must not be represented as a third public authentication provider.

## 3. Session and browser security

Remote OWNER access requires all of the following:

- existing server-side opaque session state;
- a `Secure`, `HttpOnly`, `SameSite=Strict`, path-scoped session cookie;
- a separate high-entropy CSRF token delivered only after successful private OWNER authentication;
- unsafe remote requests require an exact same-origin HTTPS `Origin` and matching CSRF cookie/header token;
- Host values outside exact loopback or the configured canonical tailnet host fail closed;
- requests for the remote host that do not reach the backend through loopback fail closed;
- CORS remains deny-by-default because no permissive CORS middleware is introduced;
- successful remote responses emit HSTS, `X-Content-Type-Options: nosniff`, and a restrictive referrer policy;
- login attempts and authenticated mutations use bounded rate limits.

The browser never stores the session identifier in Web Storage and never receives a broker credential back from the backend.

## 4. Authority boundaries

WP22A must preserve:

- `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- READ credential never becomes trading credential;
- no transfer/withdrawal authority;
- no new broker submit route;
- no Real approval endpoint exposed remotely;
- no public multi-user registration/activation;
- V9 rollback and recovery protections.

`OMNI_V10_WEB_PRIVATE_REMOTE=1` enables only the reviewed private remote Web factory. It is not evidence that public ingress or public multi-user mode is enabled.

## 5. Runtime-only configuration

Required runtime inputs for the private remote candidate are:

- `OMNI_V10_WEB_PRIVATE_REMOTE=1`;
- `OMNI_V10_WEB_EXTERNAL_HOST=<exact approved node tailnet DNS name>`;
- `OMNI_V10_TAILSCALE_OWNER_LOGIN_SHA256=<sha256 of normalized OWNER Tailscale login>`.

The actual OWNER login, broker credentials, Tailscale authentication material, certificate private keys, private portfolio data and full broker account identifiers must not be stored in GitHub or CI artifacts.

## 6. Required deterministic checks

Before OWNER deployment evidence, CI must prove at minimum:

- invalid/non-tailnet host configuration rejected;
- malformed OWNER identity binding rejected;
- wrong Tailscale identity rejected;
- direct/non-loopback identity-header spoof path rejected;
- hostile Host rejected;
- hostile/missing Origin rejected for unsafe remote requests;
- missing/mismatched CSRF rejected;
- valid same-origin CSRF accepted;
- login rate limit enforced;
- session cookie is Secure/HttpOnly/SameSite=Strict;
- server-side session expiry remains effective;
- cross-origin responses do not gain permissive CORS;
- the existing local-only TrustedHost middleware still composes correctly behind the outer remote-access guard;
- frontend Web API sends the CSRF header only when the CSRF cookie exists;
- full repository quality/security/Regression Shield remains green.

## 7. OWNER evidence boundary

CI cannot prove a real Lenovo is joined to the intended OWNER tailnet, that Tailscale Serve is configured privately rather than Funnel, or that a separate authorized OWNER device can reach the exact Web URL.

After code, static checks, focused tests and authoritative CI are GREEN, WP22A may require a single reviewed OWNER-local/private rehearsal. Any such rehearsal must return only sanitized PASS/FAIL evidence and must not expose Tailscale credentials, raw OWNER login, broker credentials, full account IDs or private portfolio values.

Until that evidence and the WP22A Exit Gate are accepted, the current accepted Web remains local/private and Block F stays locked.
