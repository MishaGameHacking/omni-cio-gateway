# V10 WP22A — External Web Access / OWNER Authentication Security Execution Contract

Status: **IMPLEMENTATION IN PROGRESS**  
Date: 2026-08-14

## 1. Dependency gate

WP22A may execute only after WP22 acceptance and the separate WP22 status transition have both passed exact-main Regression Shield. The accepted starting main for this implementation is:

`4cd81f5d3932264632fd496903ff1081b64fb41f`

WP23+ remains locked until WP22A Exit Gate and the subsequent status acceptance sequence.

## 2. Selected scope

The Personal V10 requirement is remote OWNER browser access without converting the Lenovo node into a public web server. Public ingress is therefore **not required** for this WP22A implementation.

Selected path:

`OWNER browser -> Tailscale tailnet HTTPS -> Tailscale Serve -> 127.0.0.1:8765 -> same Omni-CIO Web/API`

Forbidden path:

`public Internet -> Funnel/public tunnel/open router port -> Omni-CIO`

The selected transport does not change the accepted Omni-CIO identity model. Telegram and VK ID remain the ordinary product login providers. The Tailscale identity is used only as an outer OWNER-only private Personal-node access factor during this pre-public phase.

## 3. Mandatory implementation properties

### Transport

- backend bind remains `127.0.0.1`;
- the application also rejects a non-loopback backend peer as defense in depth;
- HTTPS terminates at Tailscale Serve on the node's exact `*.ts.net` hostname;
- Tailscale Funnel is disabled/not permitted for the Omni-CIO service;
- no inbound router/firewall port opening is introduced;
- no Cloudflare/public reverse proxy is required for the Personal baseline;
- exact host configuration is local runtime state and is not guessed by the application;
- runtime private-remote configuration is ACL-restricted to SYSTEM/Administrators and read-only runtime access; arbitrary principals/CI runner access are rejected by verification.

### Identity and session

- every private-remote request requires the exact configured Tailscale OWNER login fingerprint;
- the `Tailscale-User-Login` value is RFC 2047 decoded when necessary before exact fingerprint comparison;
- raw OWNER login is not committed to GitHub/CI evidence;
- private remote bootstrap rotates the prior browser session and creates a revocable server-side Omni-CIO session;
- remote session idle lifetime is exactly 120 minutes and absolute lifetime is exactly 24 hours;
- any resolved session used on the private OWNER path must be scoped to the canonical OWNER user and OWNER tenant; a valid foreign-user/foreign-tenant session fails closed;
- unsafe remote requests must resolve to a live server-side session before CSRF acceptance;
- browser receives only an opaque session cookie;
- cookie is `Secure`, `HttpOnly`, `SameSite=Strict`;
- logout/revoke-all semantics continue to use accepted session authority;
- Tailscale is not returned from `/auth/providers` and is not an ordinary third product login provider.

### Request/response security

- exact `Host` allowlist;
- CORS deny-by-default;
- unsafe methods require exact HTTPS `Origin` with no permissive suffix/trailing-slash normalization;
- unsafe authenticated methods require a session-bound CSRF token delivered by a no-store same-origin endpoint;
- unsafe requests without UI-origin proof fail closed;
- forged or expired session cookies remain rejected even when the caller can derive the public CSRF transform from the cookie value;
- private login and mutation APIs have bounded per-minute rates;
- ordinary monitoring GETs are not blocked by mutation lockout;
- Telegram Mini App `initData` cannot grant OWNER scope before the Telegram owning WP implements freshness/replay validation;
- private remote responses add `Strict-Transport-Security: max-age=31536000`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer` unless an owning response already sets the relevant header.

### Authority boundaries

WP22A must preserve:

- `app:app` protected gateway entrypoint;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no broker-write authority;
- no transfer/withdrawal authority;
- public multi-user activation OFF;
- private portfolio/broker secret boundaries;
- protected V9 rollback.

## 4. Source-controlled implementation surface

Expected WP22A-owned files include:

- `apps/api/private_remote.py`;
- `omni_cio/web/remote_security_v1.py`;
- `apps/web/src/app-shell/api.ts` and the minimal shell login integration;
- `infrastructure/windows/run_wp22a_private_remote_runtime.ps1`;
- `infrastructure/windows/configure_wp22a_tailscale_serve.ps1`;
- `infrastructure/windows/provision_wp22a_private_remote_runtime.ps1`;
- `infrastructure/windows/finalize_wp22a_private_remote_evidence.ps1`;
- `infrastructure/windows/audit_wp22a_private_remote_runner.ps1`;
- `infrastructure/windows/validate_wp22a_private_runtime_helper.ps1`;
- `scripts/assess_v10_wp22a_owner_evidence.py`;
- this execution contract, ADR-0012, machine-readable security contract and runbook;
- the WP22A threat-model/security-boundary update;
- deterministic WP22A unit/authority/evidence checks, including the OWNER-path tenant-isolation regression;
- dedicated WP22A self-hosted security and OWNER-evidence audit workflows.

The existing local app factory remains accepted and must continue to pass inherited WP16-WP22 regression gates.

## 5. Required deterministic evidence

Before OWNER action is requested, CI must prove on the exact reviewed head:

- non-loopback backend peer rejected even with otherwise valid identity headers;
- invalid host rejected;
- missing/wrong Tailscale OWNER identity rejected;
- RFC 2047 encoded Tailscale identity normalizes to the same exact decoded fingerprint;
- private remote session bootstrap rotates sessions and sets secure cookie attributes;
- remote session lifetime is bounded to 120-minute idle / 24-hour absolute;
- a valid foreign-user/foreign-tenant Omni-CIO session is rejected on the private OWNER path and can only be replaced by a fresh verified OWNER bootstrap;
- stolen session without matching outer OWNER identity rejected;
- forged and expired sessions rejected before unsafe API execution;
- foreign Origin/preflight rejected;
- unsafe direct API call without Origin rejected;
- missing/invalid CSRF rejected;
- valid live session-bound CSRF accepted for synthetic mutation;
- private remote security response headers are present;
- login and mutation rate limits enforced;
- monitoring GET path is not self-DoS rate-limited;
- Telegram `initData` replay/staleness authority unavailable before its owning WP;
- runtime launcher binds only `127.0.0.1`;
- runtime private-config ACL verification rejects non-approved principals;
- Windows runtime account-rights helper compiles without changing account rights;
- temporary OWNER acceptance runtime is exact-head, non-admin, password-logon only, SSPI-backed and contains no PostgreSQL trust/password fallback;
- runner can read only finalized sanitized OWNER evidence and cannot read/write the private Tailscale config or write OWNER evidence;
- Funnel/public-ingress markers are absent from the allowed implementation path;
- no broker-write / Real authority imports or flags are added;
- Ruff/format/mypy, Web typecheck/lint/tests/build, dependency audit, repository guards and authoritative Regression Shield remain GREEN.

The wrong/non-OWNER Tailscale identity case is a mandatory deterministic negative test. WP22A does **not** require the OWNER to create or operate a second foreign Tailscale account merely to duplicate that already deterministic security proof.

## 6. OWNER physical acceptance

CI cannot prove the OWNER's real tailnet/device identity, the externally administered tailnet policy, or an actual second-device browser path. After all deterministic code/security gates are GREEN, and only then, OWNER acceptance must verify on the Lenovo node and one separate OWNER device:

- Tailscale is installed, authenticated and Running;
- node has its expected private `*.ts.net` identity;
- tailnet policy is deny-by-default/narrow and grants only the OWNER identity/device set needed to reach Lenovo HTTPS 443;
- Tailscale Serve maps HTTPS 443 to `http://127.0.0.1:8765`;
- Funnel is not active for the node/service;
- local config contains only host plus exact OWNER-login fingerprint, not raw credentials;
- private config ACL matches the reviewed SYSTEM/Administrators/runtime-read-only boundary;
- temporary private remote runtime runs as `omni-cio-runtime`, non-admin, from the exact reviewed implementation;
- a separate OWNER device can open the cabinet over tailnet HTTPS;
- the accepted local loopback fallback remains recoverable.

The physical rehearsal is finalized into exact-head/source-hash-bound sanitized evidence, then the reviewed finalizer disables the temporary Serve mapping, removes the temporary runtime/task, disables the runtime role again and restores temporary PostgreSQL authentication configuration. The self-hosted runner must subsequently prove that it can read only the sanitized evidence while remaining unable to read/write the private Tailscale config.

No Tailscale auth key, password, raw OWNER identity, raw tailnet hostname, session cookie, broker token, portfolio payload or recovery key may be posted to GitHub/chat/CI evidence.

## 7. Exit Gate

WP22A is complete only when code, deterministic tests, exact-head CI, OWNER private-remote rehearsal, runner-isolation audit, review, squash merge, exact-main post-merge Regression Shield and the separate status acceptance are complete.

Until then:

- Web remains local/private;
- public Internet ingress remains OFF;
- public multi-user activation remains OFF;
- Real approval surface remains unpublished;
- WP23+ remains locked.
