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
- a host-bound `__Host-...` session cookie with `Secure`, `HttpOnly`, `SameSite=Strict` and `Path=/`;
- a separate host-bound `__Host-...` CSRF cookie containing a high-entropy token delivered only after successful private OWNER authentication;
- unsafe remote requests require an exact same-origin HTTPS `Origin` and matching CSRF cookie/header token;
- Host values outside exact loopback or the configured canonical tailnet host fail closed;
- requests for the remote host that do not reach the backend through loopback fail closed;
- CORS remains deny-by-default because no permissive CORS middleware is introduced;
- successful remote responses emit HSTS, `X-Content-Type-Options: nosniff`, a restrictive referrer policy and `Cache-Control: no-store`;
- login attempts and authenticated mutations use bounded rate limits;
- remote logout/revoke-all deletes the host-bound remote cookies while the existing server-side revoke semantics invalidate the opaque session record.

The browser never stores the session identifier in Web Storage and never receives a broker credential back from the backend.

The accepted session policy remains bounded: 12-hour idle lifetime and 30-day absolute lifetime unless a later reviewed security package changes it. Remembered login is therefore a revocable server-side session, not permanent device trust.

## 4. Relevant OWASP ASVS 5.0 mapping

WP22A uses the following ASVS 5.0 requirements as explicit design/test references. This mapping is a focused WP22A control map, **not** a claim of whole-product ASVS certification.

| ASVS 5.0 control | WP22A evidence |
|---|---|
| V3.3.1 / V3.3.3 | Remote cookies use `__Host-` names, `Secure`, no Domain attribute and `Path=/`; the session cookie is also HttpOnly. |
| V3.3.2 | Remote session and CSRF cookies use explicit `SameSite=Strict`. |
| V3.4.1 | Remote responses include HSTS. |
| V3.4.2 | No permissive CORS policy is introduced; cross-origin allow headers are absent by default. |
| V3.4.4 / V3.4.5 | Remote responses include `nosniff` and a restrictive referrer policy. |
| V3.5.1 / V3.5.2 / V3.5.3 | Unsafe functionality uses non-safe methods and requires exact HTTPS Origin plus an anti-forgery header/token; GET is not used for mutations. |
| V6.1.1 | Login anti-automation is documented and bounded; monitoring GET paths are not locked out by the mutation limiter. |
| V6.1.3 | Telegram/VK remain documented ordinary product authentication paths; private tailnet OWNER identity is explicitly a separate Personal-node access gate rather than an implicit provider merge. |
| V7.1.1 | Idle and absolute session lifetimes are documented. |
| V7.4.1 | Logout/revoke semantics invalidate server-side sessions and clear remote cookies. |
| V13.2.2 | The Web runtime remains under the existing least-privilege `omni-cio-runtime` account and PostgreSQL SSPI role. |

Relevant controls that belong to future Telegram/public activation remain locked to their owning work packages and are not marked satisfied merely because WP22A exists.

## 5. Authority boundaries

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

## 6. Runtime-only configuration

Required runtime inputs for the private remote candidate are:

- `OMNI_V10_WEB_PRIVATE_REMOTE=1`;
- `OMNI_V10_WEB_EXTERNAL_HOST=<exact approved node tailnet DNS name>`;
- `OMNI_V10_TAILSCALE_OWNER_LOGIN_SHA256=<sha256 of normalized OWNER Tailscale login>`.

The actual OWNER login, broker credentials, Tailscale authentication material, certificate private keys, private portfolio data and full broker account identifiers must not be stored in GitHub or CI artifacts.

The source-controlled OWNER gate derives the tailnet host and OWNER login fingerprint locally, refuses active Funnel/public ingress and starts the remote Web only as the accepted non-admin runtime identity. The raw login and Tailscale authentication material are not emitted as acceptance evidence.

## 7. Required deterministic checks

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
- remote session cookie is host-bound, Secure/HttpOnly/SameSite=Strict;
- remote CSRF cookie is host-bound, Secure/SameSite=Strict and not HttpOnly so same-origin frontend code can echo the token header;
- remote logout clears host-bound cookies and revokes the server-side session;
- server-side session expiry remains effective;
- cross-origin responses do not gain permissive CORS;
- the existing local-only TrustedHost middleware still composes correctly behind the outer remote-access guard;
- frontend Web API sends the CSRF header only when the CSRF cookie exists;
- Windows provisioning/launcher scripts parse under Windows PowerShell 5.1 without applying changes in CI;
- the source-controlled runtime launcher binds Uvicorn only to loopback and runs as the existing non-admin runtime account during OWNER apply;
- full repository quality/security/Regression Shield remains green.

## 8. OWNER evidence boundary

CI cannot prove a real Lenovo is joined to the intended OWNER tailnet, that Tailscale Serve is configured privately rather than Funnel, or that a separate authorized OWNER device can reach the exact Web URL.

After code, static checks, focused tests and authoritative CI are GREEN, WP22A requires one reviewed OWNER-local/private rehearsal for the selected private remote candidate. The source-controlled gate must first prove exact implementation binding, loopback-only backend, private Serve state, no Funnel, OWNER identity binding and a real HTTPS server-side login/logout cycle. The OWNER then proves the exact link from a separate authorized phone/browser device.

The rehearsal returns only sanitized PASS/FAIL evidence and must not expose Tailscale credentials, raw OWNER login, broker credentials, full account IDs or private portfolio values.

Until that evidence and the WP22A Exit Gate are accepted, the current accepted Web remains local/private and Block F stays locked.
