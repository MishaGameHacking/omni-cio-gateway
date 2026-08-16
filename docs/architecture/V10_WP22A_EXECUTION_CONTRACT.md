# Omni-CIO V10 — WP22A External Web Access / OWNER Authentication Security Gate

Status: **IMPLEMENTATION IN PROGRESS**

## 1. Scope

WP22A is the current authorized package. It secures browser-only remote OWNER access to the already accepted single Omni-CIO Web App. It does not create a second website, activate public multi-user registration, add broker write authority, enable Real trading, or change the protected V9 rollback.

The browser-only/headless operations amendment is accepted authority. Tailscale Serve is therefore not the required OWNER phone path because the normal phone tailnet flow depends on a device client. The selected implementation candidate for this WP is **Cloudflare Access + Cloudflare Tunnel**, subject to code, CI, security/recovery evidence and OWNER acceptance before this document may become ACCEPTED.

## 2. Service-selection result

Initial recommendation: **Cloudflare Zero Trust Free**, only for the bounded Personal V10 OWNER-private application if its final capacity/security checks remain sufficient.

Decisive fit:

- browser-only phone access with no VPN/device client requirement;
- outbound Tunnel from Lenovo, so the Omni-CIO origin keeps no public inbound port;
- Access is a deny-by-default authentication layer in front of the published hostname;
- `cloudflared` can validate the Access JWT before proxying to the loopback origin;
- Cloudflare supports API/Terraform management, allowing GitHub-driven automation after one-time bootstrap;
- the initial small Personal deployment can be evaluated on the free tier before any paid commitment.

Main limitation: a production named Tunnel requires an OWNER-controlled active Cloudflare zone/domain and creates a Cloudflare dependency for remote reachability. Omni-CIO Core/private durable state remains on the Personal Node, and local recovery must continue to work without Cloudflare.

Fallback: another reviewed clientless Zero-Trust reverse proxy with equivalent browser-only identity, outbound-origin, API/IaC, rollback and recovery properties. Tailscale remains eligible for machine/CI use but not as the required OWNER phone transport.

## 3. Target data path

```text
OWNER phone browser
  -> HTTPS public hostname
  -> Cloudflare Access OWNER-only policy
  -> named Cloudflare Tunnel
  -> cloudflared on Lenovo
  -> http://127.0.0.1:8765
  -> same Omni-CIO Web App / PostgreSQL-backed server sessions
```

The public hostname is reachable at the Cloudflare edge but the application is not anonymously public: Access must deny before origin proxying unless the OWNER policy is satisfied. The Lenovo origin remains loopback-only and has no inbound Internet listener.

## 4. Cloudflared enforcement

The accepted Tunnel configuration must set the published hostname to the exact local service and enable Cloudflare Access verification at the connector using all of:

- `access.required = true`;
- exact Access `teamName`;
- exact Access application `audTag`;
- final catch-all ingress rule returning an HTTP error instead of proxying unknown hosts.

The application boundary also requires a syntactically valid `Cf-Access-Jwt-Assertion` on the canonical external host. Cryptographic Access JWT validation is performed by the reviewed `cloudflared` ingress configuration before the request is forwarded to the origin; the app does not treat an arbitrary Internet-supplied header as sufficient because non-loopback peers and non-canonical Hosts are rejected.

The Windows runner/local-user boundary must additionally prevent the non-admin GitHub runner from being used as an alternative direct browser-origin path in final machine evidence.

## 5. OWNER authentication and sessions

For the Personal V10 private remote path, a successful Cloudflare Access policy decision is the outer OWNER reachability gate. The Web login page may then expose `OWNER private access`, which creates the existing Omni-CIO server-side OWNER session. This private route is not a new public identity provider and does not enable public multi-user registration.

Telegram and VK ID remain the product identity providers established by the accepted identity amendment. WP22A does not remove or replace them; it adds the bounded private OWNER route needed for Personal V10 remote acceptance.

Remote session rules:

- opaque server-side PostgreSQL-backed session;
- `__Host-omni_v10_session` cookie;
- `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`;
- explicit logout and revoke-all remain server-side revocations;
- reauthentication rotates the session and revokes the previous remote token;
- the local `omni_v10_session` cookie is ignored on the external path.

## 6. Request boundary

For the canonical external host:

- origin peer must be loopback because only local `cloudflared` may reach the Web listener;
- Host is exact and normalized before the inner local TrustedHost boundary;
- unsafe methods require exact HTTPS `Origin` for the canonical host;
- unsafe non-login requests require double-submit CSRF using `__Host-omni_v10_csrf` plus `X-Omni-CSRF`;
- CORS remains deny-by-default;
- login rate limit is 5 attempts / 60 seconds per validated Access assertion fingerprint;
- mutation rate limit is 120 attempts / 60 seconds per validated Access assertion fingerprint;
- remote responses are `no-store` and include HSTS, CSP, `nosniff`, same-origin resource/opener boundaries and a restrictive Permissions-Policy.

The frontend reads only the non-HttpOnly CSRF cookie and attaches it to unsafe same-origin API requests. It never reads or stores the server session token.

## 7. Secret and custody boundary

Never commit or log:

- Cloudflare API token;
- Tunnel token or Tunnel credentials JSON;
- Access session/JWT values;
- broker credentials;
- private portfolio values.

Provider identifiers that are non-secret configuration may be source-controlled only when the reviewed deployment model requires them and they disclose no private payload. Tunnel credential material remains runtime-only. If a remotely managed Tunnel token is used on Windows, the preferred runtime form is a protected token file consumed by `cloudflared --token-file`, not a token copied into repository files or command logs.

## 8. Automation boundary

After the OWNER completes unavoidable account/domain/credential bootstrap, repeatable Cloudflare resources should be managed through reviewed Terraform/API or equivalent source-controlled GitHub automation. The target minimum API-token permissions are limited to the resources actually created, with the initial Cloudflare-documented Terraform target:

- Account / Cloudflare Tunnel / Edit;
- Account / Access: Apps and Policies / Edit;
- Zone / DNS / Edit.

The exact token scope must be rechecked immediately before OWNER creation. GitHub/CI must not receive more Cloudflare authority than the WP requires.

## 9. Failure and recovery behavior

Cloudflare outage, connector failure, token revocation or DNS failure must not corrupt Omni-CIO private state. Remote Web availability may be degraded, but Core/PostgreSQL/backup and protected V9 rollback stay independent.

Recovery must be reproducible on a replacement Windows node from:

1. GitHub source at an accepted implementation;
2. restored private durable state through the accepted recovery contracts;
3. fresh runtime-only Cloudflare credential reprovisioning by OWNER;
4. source-controlled Tunnel/Access/DNS configuration reapplication;
5. repeat phone HTTPS + logout/revocation acceptance evidence.

No Cloudflare credential is part of GitHub backup evidence.

## 10. Mandatory tests before acceptance

At minimum:

- invalid/malformed Host rejection;
- direct non-loopback origin rejection;
- missing/malformed Access assertion rejection;
- direct API without Omni-CIO session remains unauthorized;
- local legacy cookie does not authenticate the remote path;
- remote session cookie flags and rotation;
- expired/revoked session behavior through inherited session tests;
- exact Origin and CSRF rejection for unsafe requests;
- rate-limit behavior and recovery;
- CORS deny-by-default;
- CSP/no-inline regressions;
- frontend unsafe requests attach CSRF only when the remote CSRF cookie exists;
- Windows origin remains loopback-only;
- `cloudflared` configuration proves Access `required=true`, exact `teamName`/`audTag`, and no wildcard origin escape;
- GitHub runner cannot read the Tunnel token or mutate OWNER acceptance evidence;
- phone browser HTTPS reachability after Access authentication;
- logout invalidates the prior server-side session;
- recovery/reprovision rehearsal is documented and bounded.

## 11. Exit Gate

WP22A is **not COMPLETE** until all of the following are true on the final exact head:

1. code/static/unit/browser/security tests GREEN;
2. authoritative Windows CI GREEN;
3. focused WP22A audit GREEN;
4. final Cloudflare configuration is reviewed and fail-closed;
5. OWNER-controlled runtime secret bootstrap is complete without secret disclosure;
6. phone-browser Access/reachability and logout-revocation evidence is real, not synthetic;
7. runner secret/evidence isolation and replacement/recovery evidence are proven;
8. full diff and review threads are clean;
9. PR is squash-merged;
10. exact new `main` passes mandatory post-merge Regression Shield;
11. only then may status mark WP22A/Block E accepted and unlock WP23.

Until then public unauthenticated ingress remains forbidden and WP23 remains locked.

## 12. Safety invariants

Always preserve:

- `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no transfer/withdrawal authority;
- no broker write expansion;
- GitHub source / private durable state / runtime secrets separation;
- protected V9 rollback.
