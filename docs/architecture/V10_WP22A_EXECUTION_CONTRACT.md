# Omni-CIO V10 — WP22A Execution Contract

Status: **IMPLEMENTATION IN PROGRESS / CLIENTLESS REBUILD**  
Owning package: **WP22A — External Web Access / OWNER Authentication Security Gate**

## 1. WP identity

- Block: E — Web Platform.
- WP: WP22A.
- Title: External Web Access / OWNER Authentication Security Gate.
- Authorized by current program status: YES.
- Accepted browser-only functional baseline: `7b3d83482f52041ef845681caabcd1baceb19d1b`.
- Current accepted governance base for this PR: `1c05390d9cf31b8cc68a90a5d7cbd6428ffe7791`.
- Prior acceptance: WP22 COMPLETE; browser-only/headless amendment accepted through PR #319/#320 and Regression Shield #1497; engineering-quality governance accepted afterward and is part of the current base.
- WP23 remains LOCKED.

## 2. Purpose

Expose the existing single Omni-CIO Web App to the OWNER from a normal phone browser without a device VPN/client while keeping the Lenovo origin non-public, preserving least privilege, and requiring two independent layers before application data is usable:

1. Cloudflare Access + Tunnel external gate;
2. Omni-CIO exact OWNER binding + server-side session gate.

No public multi-user activation or broker-write capability is introduced.

## 3. Selected provider/transport

The Service Selection Gate in `V10_WP22A_SERVICE_SELECTION.md` selects:

- Cloudflare Zero Trust Access;
- Cloudflare Tunnel;
- Cloudflare DNS for one OWNER-controlled hostname;
- the existing restricted Cloudflare account-member identity provider;
- outbound tunnel to the existing loopback Web backend.

Tailscale Serve is superseded for normal OWNER phone access. PR #317 is closed/unmerged and is not accepted authority.

## 4. Existing implementation to reuse

Reuse without creating a second Web stack:

- `apps/web` — accepted WP16–WP22 source-controlled Web App;
- `apps/api/app.py:create_local_private_app` — accepted local Web/API factory;
- PostgreSQL `PostgresWebSessionRegistryV1` — opaque server-side sessions;
- WP17 server-derived tenant/session scope;
- WP17 READ broker vault and provisioning boundary;
- WP18–WP22 Web services and browser regressions;
- WP15 accepted local Web deployment/reconstruction path;
- WP6 runner/runtime identity separation;
- WP10 recovery principles and exact-evidence discipline.

Provider-independent security patterns from the closed PR #317 may be selectively reimplemented; Tailscale-specific runtime/identity/provisioning logic is prohibited.

## 5. Allowed changes

WP22A may change only the existing repository surfaces needed for this gate:

- `apps/api` external Web factory/wiring;
- `omni_cio/web` external-access security middleware;
- `apps/web` remote-login/status UX only where necessary;
- `infrastructure/windows` WP22A runtime/provision/verify/rollback/evidence scripts;
- `.github/workflows` focused WP22A audits and reviewed provider deployment workflow;
- `infrastructure/cloudflare` source-controlled provider configuration/templates;
- WP22A architecture/operations/security docs and focused tests.

## 6. Explicit non-goals

WP22A must not:

- implement WP23 Telegram Bot Foundation;
- activate public registration/multi-user service;
- replace Telegram/VK product-login abstraction;
- create another website, frontend, database, queue or Gateway;
- add broker-write methods/routes/credentials;
- add transfers/withdrawals;
- move broker/private portfolio state to Cloudflare/GitHub;
- make Render the new V10 Web runtime;
- expose an inbound Lenovo port;
- treat a provider dashboard screenshot as sufficient acceptance;
- synthesize OWNER phone evidence in CI.

## 7. External request boundary

The reviewed network path is:

`OWNER browser -> Cloudflare Access -> Cloudflare edge -> Cloudflare Tunnel -> cloudflared on Lenovo -> 127.0.0.1:8765 -> Omni-CIO Web`.

Required properties:

- no public Lenovo IP/port is required;
- Uvicorn binds only to `127.0.0.1`;
- `cloudflared` is the reviewed external reverse-proxy process;
- the tunnel route targets only the exact local Web port;
- catch-all tunnel ingress rejects unmatched routes;
- Cloudflare Access application/policy exists before the public hostname route is considered usable;
- `cloudflared` Access protection is configured as required for the exact team/application audience;
- the application requires an Access-authenticated identity header and exact OWNER fingerprint before issuing an Omni-CIO remote session;
- requests using the external Host that do not arrive through loopback fail closed;
- the accepted local TrustedHost boundary remains unchanged behind the outer middleware.

## 8. OWNER identity and session model

Cloudflare account membership is an **outer Personal-node access gate**, not a new public product auth provider.

The backend receives the Access-authenticated user identity only after the tunnel's Access validation. The backend:

- normalizes the identity;
- hashes it in memory;
- constant-time compares it to a runtime-only expected OWNER fingerprint;
- does not persist/raw-log the identity;
- creates an Omni-CIO server-side session only after the external gate is verified.

Remote session policy:

- idle lifetime: 2 hours;
- absolute lifetime: 24 hours;
- successful OWNER remote login revokes the currently presented remote session before issuing a fresh token;
- remote session cookie: `__Host-omni_v10_session`, Secure, HttpOnly, SameSite=Strict, Path=/;
- remote CSRF cookie: `__Host-omni_v10_csrf`, Secure, SameSite=Strict, Path=/, readable only so same-origin frontend code can echo it in the CSRF header;
- browser Web Storage for sessions/credentials is forbidden;
- logout/revoke-all revokes the server-side session and clears remote cookies.

A Cloudflare Access cookie alone is never treated as an Omni-CIO data session.

## 9. Request security

External-host requests require:

- exact canonical Host;
- loopback proxy peer;
- Access-authenticated OWNER identity;
- non-empty Access assertion that has already been validated by the reviewed `cloudflared` ingress binding;
- valid Omni-CIO session for protected data routes;
- exact HTTPS Origin on unsafe requests;
- matching CSRF cookie/header on unsafe authenticated requests;
- bounded login and mutation rates.

Responses on the external contour require:

- HSTS;
- strict CSP with `default-src 'self'`, no `unsafe-inline`/`unsafe-eval`;
- `frame-ancestors 'none'`;
- `object-src 'none'`;
- `X-Content-Type-Options: nosniff`;
- restrictive referrer policy;
- `Cache-Control: no-store`;
- CORS deny-by-default.

## 10. Runner/local-process negative boundary

The ordinary self-hosted GitHub runner is considered potentially dangerous.

WP22A must retain a live OS-level denial for the exact runner service identity to the loopback Web port. Acceptance requires the actual runner identity to prove direct TCP access to the backend is denied after OWNER deployment.

The runner must also be unable to create, replace, rename or write OWNER physical evidence. A repository job cannot manufacture acceptance evidence.

The selected Cloudflare design does not treat a bare Internet- or runner-supplied identity header as trustworthy. External identity is established through the reviewed Access-protected tunnel, where `cloudflared` validates the exact team/application assertion before proxying the request, and the runner is blocked from the loopback origin before application authentication. An already compromised OWNER/admin Windows process is classified as a local node compromise rather than something Cloudflare Access can defend against; that boundary is recorded explicitly in `V10_THREAT_MODEL.md` T22.

## 11. Provider configuration and secrets

Source-controlled provider configuration contains only non-secret declarations/placeholders.

Never commit/log/artifact:

- Cloudflare API token;
- tunnel token/credentials;
- raw OWNER identity;
- private domain account identifiers where not required as public configuration;
- broker tokens;
- full broker account IDs;
- private portfolio/database content.

The existing Cloudflare Zero Trust organization is a bootstrap prerequisite. Terraform reads and verifies it instead of creating a duplicate organization. Terraform also discovers the existing Cloudflare identity provider and requires exactly one Cloudflare IdP with account-member restriction; it does not create a second Cloudflare IdP.

A bounded source-controlled Cloudflare API bootstrap may create/update the Zero Trust organization prerequisite when needed, but it cannot publish the Omni-CIO hostname by itself. After that prerequisite is correct, Terraform owns the WP22A Tunnel, Access policy/application, tunnel ingress and DNS record.

Provider API credentials used by GitHub must be narrowly scoped and unavailable to arbitrary PR code. Real provider mutation is allowed only from an explicitly reviewed protected `main` workflow/environment after the dormant implementation is merged and its post-merge Regression Shield is GREEN.

The real provider token is never provided to pull-request workflows. This is a deliberate security boundary: provider credentials cannot be exposed to code that has not yet become accepted `main`.

Tunnel runtime credentials remain runtime-only on Lenovo. A remotely managed tunnel token is secret material. It must not be stored in Terraform state; the reviewed deployment retrieves it separately through the provider API and writes it directly into a protected local runtime file.

## 12. Windows runtime

The runtime reuses the accepted non-admin `omni-cio-runtime` application identity and accepted local Web deployment root. `cloudflared` runs as a separate least-privilege persistent Windows task/service contour using the reviewed installation/version boundary.

The application launcher must:

- set only reviewed WP22A external configuration;
- explicitly disable older local OWNER acceptance flags;
- bind Uvicorn to `127.0.0.1` only;
- disable forwarded-client rewriting when application trust decisions depend on the actual loopback peer;
- use PostgreSQL SSPI/runtime role already accepted;
- keep `app:app` unchanged.

The `cloudflared` binary and Terraform CLI used by the owning workflows are version/hash pinned before execution.

## 13. Two-phase acceptance sequence

### Phase A — dormant implementation merge

Provider and Lenovo mutation remain disabled throughout the feature PR.

Phase A requires:

1. exact-head focused WP22A CI GREEN;
2. exact-head authoritative Windows merge gate GREEN;
3. inherited WP16–WP22 Web gates GREEN;
4. Terraform/provider schema validation GREEN using no real provider credential;
5. security/recovery code review complete and zero unresolved blocking threads;
6. full diff reviewed;
7. feature PR squash-merged while the external contour remains disabled;
8. exact new `main` verified;
9. post-merge Regression Shield GREEN.

Completing Phase A does **not** make WP22A COMPLETE and does not unlock WP23.

### Phase B — provider/Lenovo apply and OWNER acceptance

Only the exact accepted `main` implementation may receive provider credentials or mutate provider/runtime state.

The protected provider/apply workflow, OWNER evidence tooling and any state-handling mechanism that can only be meaningfully exercised after Phase A may be introduced in one or more **source-only WP22A follow-up PRs**. Those PRs receive no real provider credential while open and must themselves pass exact-head authoritative CI, squash merge, exact-`main` verification and post-merge Regression Shield before their privileged workflow is ever run. This keeps provider credentials unavailable to arbitrary PR code while allowing WP22A to remain one work package across the dormant and live-acceptance phases.

Fail-closed apply order:

1. verify accepted `main` SHA and reviewed provider workflow;
2. verify accepted local Web can be reconstructed;
3. bootstrap/verify the existing Zero Trust organization and restricted default Cloudflare IdP without publishing Omni-CIO;
4. plan/apply Access policy/application, Tunnel ingress and DNS from source-controlled provider intent;
5. retrieve the tunnel run token separately from Terraform state and write it directly into the protected Lenovo runtime store;
6. install/verify pinned `cloudflared` runtime and exact runner loopback firewall denial;
7. start remote-specific Omni-CIO Web on loopback;
8. start the tunnel only after Access protection and catch-all deny exist;
9. independently verify provider and Lenovo state;
10. require separate OWNER phone rehearsal before final acceptance.

On any failure after external reachability could exist, rollback first removes/disables the external route/tunnel/local connector contour and then reconstructs the previously accepted local Web. Failure may never leave an unauthenticated published hostname as a convenience fallback.

## 14. Deterministic normal-path tests

Before dormant merge, CI must prove at minimum:

- valid external Host + loopback proxy + expected Access identity/assertion can enter remote login;
- successful remote login creates server-side OWNER scope and rotates prior session;
- protected API works only after both external identity and Omni-CIO session exist;
- same-origin CSRF succeeds;
- logout revokes session and clears cookies;
- local/private accepted Web remains functional;
- provider/IaC configuration is syntactically and schema valid without real credentials;
- all inherited WP16–WP22 browser/API contracts remain GREEN.

## 15. Negative/failure tests

Mandatory negatives include:

- malformed/external host rejected;
- non-loopback external-host request rejected;
- missing/empty Access identity rejected;
- missing Access assertion rejected;
- wrong OWNER identity rejected;
- copied Omni session without expected Access identity rejected;
- legacy local private-test session cannot authorize external host;
- hostile/missing Origin rejected for unsafe requests;
- missing/mismatched CSRF rejected;
- login/mutation rate limits enforced;
- expired/revoked server-side session rejected;
- frontend does not store session/credential in Web Storage;
- CORS is not permissive;
- CSP does not require inline style/script weakening;
- tunnel config requires Access protection and catch-all deny;
- Terraform refuses an unhardened/mismatched Zero Trust organization or missing/unrestricted Cloudflare IdP;
- provider config contains no secrets;
- PR workflows cannot access real provider credentials;
- direct runner loopback access is denied in live OWNER gate;
- corrupt/stale/mismatched OWNER evidence rejected;
- rollback restores local Web and removes external reachability on simulated late failure.

## 16. CI/deployment routing

- hosted Fast/Toolchain: supplementary and subject to the accepted capacity-routing contract; known zero-budget hosted capacity is never treated as evidence that hosted execution occurred;
- focused WP22A Lenovo audit: mandatory for Phase A;
- authoritative self-hosted Windows merge gate: mandatory for Phase A;
- inherited WP16–WP22 Web gates: mandatory for Phase A;
- provider schema validation: mandatory for Phase A, no real provider secret;
- post-feature-merge Regression Shield: mandatory before Phase B;
- provider apply/verify workflow: protected `main`/reviewed-environment only, never arbitrary PR;
- OWNER evidence validator: may read sanitized evidence but may not manufacture OWNER physical facts;
- final status acceptance PR + post-status Regression Shield: mandatory before WP23 begins.

## 17. Required OWNER evidence

OWNER physical evidence cannot be synthesized.

After Phase A is accepted and the reviewed Phase B provider/runtime apply is ready, the OWNER must use a separate ordinary phone browser (no device VPN/client) to prove:

- the reviewed HTTPS hostname is reachable;
- unauthenticated access is blocked by Cloudflare Access;
- the OWNER can authenticate through the selected outer identity path;
- Omni-CIO remote OWNER login/session succeeds;
- representative existing Web pages load through the same source-controlled app;
- logout revokes the Omni-CIO server-side session;
- subsequent stale-session reuse fails or requires a new application login as designed.

Only sanitized booleans/reason codes/fingerprints are retained as acceptance evidence. Private URL/domain, raw identity, session values and private portfolio data are not uploaded.

## 18. Exit Gate

WP22A PASS requires all of:

- selected service gate source-controlled;
- Phase A exact-head focused + authoritative + inherited CI GREEN;
- zero unresolved blocking review threads and full diff review;
- dormant feature PR squash-merged;
- exact implementation `main` verified and post-feature-merge Regression Shield GREEN;
- reviewed provider configuration/applied state matches source-controlled intent;
- loopback-only origin and actual runner denial proven;
- Cloudflare Access is deny-by-default and exact OWNER authorization is proven;
- separate OWNER phone HTTPS/login/logout evidence PASS;
- rollback/recovery rehearsal PASS;
- no secrets/private financial payloads in GitHub/logs/artifacts;
- final status acceptance PR squash-merged;
- exact final `main` verified;
- post-status Regression Shield GREEN;
- official program status updated to WP22A COMPLETE / WP23 NEXT.

Code written or merged without the Phase B provider/OWNER proofs is **not COMPLETE**.

## 19. Safety invariants

Throughout WP22A:

- `app:app` preserved;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no broker-write authority added;
- no transfers/withdrawals;
- public registration/multi-user remains OFF;
- protected V9 rollback remains intact.
