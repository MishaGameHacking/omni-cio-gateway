# ADR-0012 — WP22A Private Remote Access Before Public Ingress

Status: **PROPOSED FOR WP22A ACCEPTANCE**  
Date: 2026-08-14  
Owner: Omni-CIO V10 / WP22A

## Context

WP22A exists to prevent the accepted local Personal cabinet from becoming a public attack surface merely because remote browser access is desirable. The Master Plan requires an explicit decision on whether public ingress is needed at all and requires private remote access to be evaluated first.

The accepted V10 boundaries already provide one source-controlled Web App, server-side sessions, tenant-scoped authorization, runtime-only secrets, `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, and a protected V9 rollback. WP22A must not create a second website, second identity product, second data plane, or broker-write path.

## Decision

For Personal V10, **public ingress is not required**. The selected remote transport is **Tailscale Serve inside the OWNER tailnet**.

The application process remains bound to `127.0.0.1`. Tailscale Serve terminates HTTPS for the node's exact `*.ts.net` name and reverse-proxies only to the loopback backend. Tailscale Funnel is not permitted for the Omni-CIO service. The runtime configuration is source-controlled by scripts/contracts while the actual tailnet identity, hostname, and OWNER identity fingerprint remain local runtime state.

The private remote backend validates all of the following before the application receives a request:

- exact configured `*.ts.net` Host;
- Tailscale `Tailscale-User-Login` identity fingerprint equal to the configured OWNER fingerprint;
- foreign Origin rejection and exact HTTPS Origin on every unsafe request;
- session-bound CSRF for unsafe authenticated requests;
- bounded private-login and mutation rates, while monitoring GETs are not placed behind mutation lockout;
- explicit rejection of Telegram Mini App `initData` authority before its owning WP implements replay/freshness verification.

The private OWNER bootstrap creates a normal revocable Omni-CIO server-side browser session and rotates any existing session token. It is an **outer Personal-node private acceptance factor**, not a third ordinary Omni-CIO product login provider. The ordinary product identity providers remain exactly Telegram and VK ID under the accepted identity amendment.

## Why Tailscale Serve

Current Tailscale documentation distinguishes Serve from Funnel: Serve is reachable only within the tailnet, access controls apply, HTTPS is terminated by Tailscale, and identity headers are added for tailnet requests while spoofed incoming identity headers are stripped. Tailscale also recommends keeping a backend on localhost when identity headers are used. This matches the accepted V10 least-privilege boundary.

Tailscale grants are the preferred policy primitive for new access policies and support deny-by-default, least-privilege source-to-destination rules. The WP22A OWNER acceptance therefore requires a narrow OWNER-to-Lenovo HTTPS grant rather than a default allow-all tailnet policy.

Primary references:

- https://tailscale.com/docs/features/tailscale-serve
- https://tailscale.com/docs/reference/tailscale-cli/serve
- https://tailscale.com/docs/features/access-control/grants
- https://owasp.org/www-project-application-security-verification-standard/

## Alternatives considered

### Public Tailscale Funnel

Rejected for WP22A Personal baseline. Funnel intentionally exposes a local service to the public Internet. Public reachability is not required for current Personal V10 and would enlarge the attack surface without product value at this stage.

### Cloudflare Tunnel / Access

Technically viable for a later explicitly approved public or identity-aware ingress design, but not selected now. It adds a separate external public/Zero Trust control plane and is unnecessary when the requirement is OWNER-only private remote access.

### Open inbound router/firewall port

Rejected. The Lenovo node must not be converted into a directly Internet-addressable web server for WP22A.

## Consequences

- Remote OWNER browser access can be rehearsed without public Internet ingress.
- Backend Host/identity headers are trusted only because the backend remains loopback-only and Tailscale Serve is the sole remote proxy path.
- Tailscale installation/sign-in, tailnet grant approval, and final remote browser rehearsal are OWNER-controlled physical/account actions and cannot be synthesized by CI.
- The Web remains local/private until those checks and the full WP22A Exit Gate pass.
- Public multi-user activation remains OFF.
- Telegram/VK provider implementation order is unchanged.
- No broker-write or Real execution authority is added.

## Rollback

Disable the Tailscale Serve mapping on HTTPS 443, stop the WP22A private-remote runtime, and return to the accepted loopback local Web runtime. No portfolio, broker, session schema, or secret-store rollback is required by the transport decision itself.
