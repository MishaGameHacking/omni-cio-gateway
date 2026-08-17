# Omni-CIO V10 — WP22A Service Selection Gate

Status: **SELECTED FOR IMPLEMENTATION / NOT YET ACCEPTED**  
Owning package: **WP22A — External Web Access / OWNER Authentication Security Gate**  
Accepted browser-only functional baseline: `7b3d83482f52041ef845681caabcd1baceb19d1b`  
Mutable accepted-base tracking lives only in `V10_WP22A_EXECUTION_CONTRACT.md`; this service-selection record is provider/design evidence, not a second progress/base ledger.

## 1. Required outcome

Select one clientless external-access transport for the existing source-controlled Omni-CIO Web App. The selected design must let the OWNER use an ordinary phone browser without installing a VPN/device client, keep the Lenovo origin non-public, remain automatable from GitHub after bounded bootstrap, preserve server-side sessions and OWNER identity, and add no broker-write/public-multi-user authority.

The browser-only/headless amendment is controlling authority. The closed Tailscale-specific PR #317 is not accepted WP22A authority. The later accepted engineering-governance base is also controlling for pre-CI, all-GREEN merge, OWNER handoff, live-evidence and failure-learning discipline.

## 2. Hard requirements

A candidate fails immediately if it cannot satisfy all of these:

- ordinary mobile browser access with no required native VPN/device client;
- no inbound port or publicly routable origin requirement on the Personal Node;
- authentication before the private Web origin is usable;
- exact OWNER authorization, fail-closed by default;
- source-controlled API/IaC automation after bounded bootstrap;
- explicit rollback that removes external reachability without damaging the accepted local Web;
- no broker credential, private portfolio payload or durable private DB movement into the access provider;
- no new Web App/repository/runtime stack;
- preserved `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and no transfer/withdrawal authority.

## 3. Candidates

### 3.1 Cloudflare Access + Cloudflare Tunnel — SELECTED

Requirement fit:

- Access supports clientless browser access to self-hosted/private Web applications;
- Tunnel is outbound-only from the origin, requiring no public IP or open inbound port;
- Access policies can be restricted to the OWNER account member and selected login method;
- the existing Cloudflare account/member identity path avoids creating a new daily Omni-CIO infrastructure password;
- Cloudflare publishes supported API/Terraform resources for Tunnel, Access policy/application and DNS management;
- remotely managed tunnels can use a runtime-only token file, avoiding token exposure in scheduled-task arguments;
- `cloudflared` can run persistently on Windows;
- the source-controlled implementation pins the currently reviewed Cloudflare Terraform provider and cloudflared binary/hash before Phase B.

Security design consequence:

- Access application/policy must exist before a published hostname is activated;
- `cloudflared` must enforce Access for the tunnel ingress using the exact Access application audience/team binding;
- the backend independently requires the Access identity header plus exact OWNER fingerprint, exact canonical Host, loopback proxy peer, same-origin CSRF on unsafe methods, and server-side Omni-CIO session state;
- the GitHub self-hosted runner remains denied direct access to the loopback backend port;
- no direct origin port is exposed.

TLS and certificate lifecycle for the selected zero-cost Personal path:

- visitor TLS terminates at the Cloudflare edge on a publicly trusted, Cloudflare-managed Universal SSL certificate; the local `cloudflared -> 127.0.0.1:8765` hop remains loopback-only HTTP and does not require an externally trusted origin certificate;
- the selected Phase-B path requires an **active Cloudflare full-DNS zone** and uses exactly one **first-level subdomain** of that zone so Universal SSL coverage is deterministic without a paid certificate add-on;
- the WP22A DNS record remains `Proxied`; Cloudflare owns edge-certificate issuance, renewal and deployment, so no edge private key or certificate bundle is copied to GitHub or Lenovo;
- before the hostname is treated as usable, the protected Phase-B verifier must prove that an active certificate covers the exact hostname and that provider-managed renewal remains enabled;
- `X-Forwarded-Proto` must equal exactly `https` at the loopback application boundary; missing, `http`, or ambiguous values fail closed and may not reach an Omni-CIO remote session;
- if the live OWNER zone is partial/CNAME-only, the desired hostname is deeper than one subdomain level, Universal SSL is inactive, or exact coverage cannot be proven, Phase B stops before cutover. Engineering must not silently buy/enable Advanced Certificate Manager, Total TLS, a custom certificate, or another paid product.

Cost now: **Cloudflare Zero Trust Free is the selected Personal-contour target**, subject to the exact live account/feature checks performed before Phase B. Free service is not treated as having a paid-plan SLA.

Main limitation: an active domain/zone under Cloudflare is required for the normal published-hostname path, and one-time OWNER account/domain/API-credential bootstrap remains unavoidable.

### 3.2 ngrok — compatible fallback, not selected

Strengths:

- clientless browser access;
- managed HTTPS endpoints;
- OAuth-capable access policies;
- no OWNER device client required.

Reasons not selected for current WP22A:

- current free-tier quotas and development-domain constraints are less suitable for the intended persistent OWNER dashboard;
- higher long-term dependency on a proprietary endpoint/traffic-policy model for a function Cloudflare can satisfy together with the selected DNS/IaC path.

Fallback condition: reconsider if Cloudflare domain/bootstrap requirements become impossible or the selected Cloudflare controls cannot pass WP22A security/recovery evidence.

### 3.3 Tailscale Serve — not eligible as normal OWNER phone path

Tailscale Serve remains a strong private machine/tailnet transport and may remain useful for machine-to-machine or engineering infrastructure. It is rejected for the required OWNER product path because normal tailnet access depends on a Tailscale device client, which conflicts with the accepted browser-only amendment.

The closed PR #317 therefore remains historical engineering material only; it is not merged or accepted.

## 4. Selected identity method

For current Personal V10, use the **existing Cloudflare Access identity provider restricted to Cloudflare account members** and an Access policy limited to the current Cloudflare account member.

Rationale:

- the selected outer identity is already controlled by the OWNER Cloudflare account;
- it removes the need to create and custody an additional GitHub OAuth App client secret solely for the infrastructure gate;
- the inner Omni-CIO application still performs exact OWNER identity fingerprinting and issues its own revocable server-side session;
- Terraform reads and validates the existing organization/IdP instead of creating duplicate identity infrastructure.

This outer infrastructure identity does **not** replace Telegram/VK as the ordinary product authentication-provider abstraction and does not enable public registration/multi-user mode.

If later commercial/multi-user activation needs direct GitHub or another IdP in Access, that is a separate reviewed identity/service decision.

## 5. Provider automation model

Provider state must converge through source-controlled Cloudflare API/Terraform automation after one-time bootstrap. The current dormant feature PR validates provider schemas and intent without any real provider credential. Real mutation is deferred until the exact implementation is accepted on `main` and the protected Phase B workflow itself is source-reviewed and accepted.

Minimum provider authority is restricted to the exact resources needed by the reviewed plan: Tunnel, Access application/policy/identity-provider reads required for validation, and the selected zone DNS record. Provider credentials are never committed, logged, copied into Codespaces, exposed to pull-request code or returned through chat.

Tunnel runtime credentials remain runtime-only on the Personal Node. A remotely managed tunnel token is treated as a secret because possession can run the tunnel.

## 6. Provider-independent security requirements reused from PR #317

The clean rebuild keeps the following design ideas but reimplements them against the selected Cloudflare transport:

- remote-specific server-side session lifetime of 2 hours idle / 24 hours absolute;
- host-bound Secure/HttpOnly/SameSite session cookie and host-bound CSRF cookie;
- session rotation on successful outer OWNER authentication;
- exact Host and HTTPS Origin validation;
- fail-closed external protocol binding through exact `X-Forwarded-Proto: https`;
- CSRF cookie/header equality on unsafe methods;
- bounded login/mutation rate limiting;
- HSTS, strict CSP, `nosniff`, restrictive referrer policy, `no-store`;
- CORS deny-by-default;
- accepted local Web TrustedHost boundary retained behind the external gate;
- Web backend remains loopback-only;
- GitHub runner direct-loopback negative test;
- fail-closed provider/runtime rollback;
- exact-head OWNER physical evidence for phone HTTPS access, login and logout/session revocation;
- sanitized evidence only.

Tailscale host patterns, Tailscale identity headers, Serve/Funnel logic and tailnet OWNER evidence are explicitly not reused.

## 7. Exit from service-selection gate

PASS requires this file plus the WP22A execution contract to be source-controlled in the clean WP22A branch and the implementation/tests to prove the selected controls before any provider mutation is authorized.

The service selection itself does not make Cloudflare state accepted, does not activate ingress and does not unlock WP23.
