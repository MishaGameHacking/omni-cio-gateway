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
- tagged Lenovo nodes are rejected for this OWNER gate because Tailscale Serve does not populate the required user identity headers for tagged devices;
- the expected OWNER login is represented to the application by a SHA-256 fingerprint supplied as runtime-only configuration; the raw login value is not committed;
- the existing internal local-only TrustedHost boundary is retained. After the outer WP22A middleware validates the canonical remote Host, the request forwarded into the accepted local Web application is normalized back to loopback Host rather than widening the older allowlist globally.

Tailscale Serve activation is also an OWNER-consent boundary. The provisioner must not use `--yes` or accept HTTPS/privacy terms unattended. The CLI invocation is bounded, any consent URL remains in memory and is reduced to a symbolic reason, and a timeout/nonzero result triggers the existing local rollback. A partial state with remote task/listener/firewall present but Serve absent is never accepted and never authorizes Verify/finalization.

Tailscale Serve itself strips incoming `Tailscale-User-*` values before proxying and derives identity from the Tailscale source address. Traffic originating from the Serve machine itself is not assigned a remote user identity. WP22A therefore treats a Lenovo-to-its-own-Serve request as a **negative anti-spoof probe**, never as positive OWNER authentication evidence: a forged incoming OWNER header sent through the local machine's Serve endpoint must result in HTTP 403. Positive OWNER identity, private login, server-side session and logout/revocation evidence must come from the separate authorized OWNER phone/browser rehearsal.

Loopback-only binding by itself does not prove that a second process on the Lenovo cannot forge the same HTTP identity headers. This matters because the accepted WP6 threat model treats the ordinary GitHub self-hosted runner as a potentially dangerous identity distinct from the runtime. WP22A therefore adds a Windows identity-scoped outbound firewall rule that blocks the exact GitHub runner service SID from connecting to the WP22A loopback Web port. The rule is OWNER-admin provisioned, repository-defined, removed on rollback and verified both structurally and by a live negative TCP probe executed as the actual runner identity after OWNER deployment.

The same runner audit closes the self-Serve hairpin path. It derives the current local tailnet identity without emitting the hostname or login, proves that the running task is bound to that exact host/fingerprint, then sends a no-proxy HTTPS request through the node's own Serve endpoint with a forged incoming OWNER identity header. The protected session endpoint must return HTTP 403. A runner that can connect directly to the backend or authenticate through its own Serve endpoint is a WP22A Exit-Gate failure.

This decision does not activate a public registration service. Telegram Login and VK ID remain the ordinary product authentication providers defined by the accepted identity amendment. Tailnet OWNER identity is a private network access gate for the Personal-node deployment and must not be represented as a third public authentication provider.

## 3. Session and browser security

Remote OWNER access requires all of the following:

- existing server-side opaque session state;
- a WP22A remote-specific session policy of **2 hours idle / 24 hours absolute**; this shortens only the private remote contour and does not silently change the accepted local Web session baseline;
- every successful private OWNER authentication rotates the remote session identifier: if the browser presents an existing remote session token, that token is revoked server-side before a fresh high-entropy token is created;
- a host-bound `__Host-...` session cookie with `Secure`, `HttpOnly`, `SameSite=Strict` and `Path=/`;
- a separate host-bound `__Host-...` CSRF cookie containing a high-entropy token delivered only after successful private OWNER authentication;
- every remote request other than the non-sensitive readiness/status probe must still carry the current Tailscale Serve identity that matches the configured OWNER fingerprint; a copied session cookie or copied session+CSRF pair presented through a wrong or missing tailnet identity fails before the request reaches the inner application;
- unsafe remote requests require an exact same-origin HTTPS `Origin` and matching CSRF cookie/header token;
- Host values outside exact loopback or the configured canonical tailnet host fail closed;
- requests for the remote host that do not reach the backend through loopback fail closed;
- the remote boundary strips the accepted local-only legacy session-cookie name from remote requests and injects an inner local session cookie only from the validated host-bound remote session cookie;
- CORS remains deny-by-default because no permissive CORS middleware is introduced;
- remote responses emit HSTS, strict CSP with `default-src 'self'`, `object-src 'none'` and `frame-ancestors 'none'`, `Cross-Origin-Opener-Policy: same-origin-allow-popups`, `X-Content-Type-Options: nosniff`, a restrictive referrer policy and `Cache-Control: no-store`;
- the Web source contains no React inline `style={{...}}` attributes that would require weakening the remote CSP with `unsafe-inline`;
- login attempts and authenticated mutations use bounded rate limits;
- remote logout/revoke-all deletes the host-bound remote cookies while the existing server-side revoke semantics invalidate the opaque session record.

The browser never stores the session identifier in Web Storage and never receives a broker credential back from the backend. Session rotation and expiry remain server-authoritative; remembered access is never permanent device trust.

## 4. Relevant OWASP ASVS 5.0 mapping

WP22A uses the following ASVS 5.0 requirements as explicit design/test references. This mapping is a focused WP22A control map, **not** a claim of whole-product ASVS certification.

| ASVS 5.0 control | WP22A evidence |
|---|---|
| V3.3.1 / V3.3.3 | Remote cookies use `__Host-` names, `Secure`, no Domain attribute and `Path=/`; the session cookie is also HttpOnly. |
| V3.3.2 | Remote session and CSRF cookies use explicit `SameSite=Strict`. |
| V3.4.1 | Remote responses include HSTS. |
| V3.4.2 | No permissive CORS policy is introduced; cross-origin allow headers are absent by default. |
| V3.4.3 / V3.4.6 | Remote responses include an enforced CSP without `unsafe-inline`/`unsafe-eval`; framing is blocked with `frame-ancestors 'none'`. |
| V3.4.4 / V3.4.5 | Remote responses include `nosniff` and a restrictive referrer policy. |
| V3.5.1 / V3.5.2 / V3.5.3 | Unsafe functionality uses non-safe methods and requires exact HTTPS Origin plus an anti-forgery header/token; GET is not used for mutations. |
| V6.1.1 | Login anti-automation is documented and bounded; monitoring GET paths are not locked out by the mutation limiter. |
| V6.1.3 | Telegram/VK remain documented ordinary product authentication paths; private tailnet OWNER identity is explicitly a separate Personal-node access gate rather than an implicit provider merge. |
| V7.1.1 | Remote idle and absolute lifetimes are explicitly 2 hours / 24 hours. |
| V7.4.1 | Logout/revoke semantics invalidate server-side sessions and clear remote cookies; re-authentication revokes the previously presented remote token before issuing a replacement. |
| V13.2.2 | The Web runtime remains under the existing least-privilege `omni-cio-runtime` account and PostgreSQL SSPI role. |

`Cross-Origin-Opener-Policy` is retained as additional defense-in-depth for the remote Web surface. It is not used here to claim satisfaction of a lower ASVS level than the applicable ASVS requirement actually defines.

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

The remote runtime also explicitly disables the earlier loopback-only WP17/WP15 OWNER acceptance modes before activating the WP22A factory. A Tailscale Serve request reaching the backend through loopback must never inherit those older test/acceptance authorities.

## 7. Windows runtime, runner and rollback boundary

The WP22A apply path reuses the accepted WP15 deployment root and runtime identity. It may rotate the runtime account password when registering the remote scheduled task, so rollback must never assume that a previously registered WP15 task still holds a valid stored credential.

The reviewed rollback/reconstruction path therefore:

1. resets the WP22A Tailscale Serve configuration using the current Serve reset operation and verifies that no Serve `*.ts.net` route remains;
2. confirms Funnel/public ingress is not active;
3. removes the WP22A remote scheduled task;
4. removes the WP22A runner-loopback firewall rule;
5. invokes accepted WP15 `Cleanup` **unconditionally**, even when the WP15 task/runtime root are already absent, so a partially completed cutover cannot leave `omni-cio-runtime` enabled or another accepted WP15 cleanup obligation pending;
6. invokes accepted WP15 `Apply` through `start_wp15_live_web_acceptance.ps1`, preserving its temporary `SeBatchLogonRight` grant/restore boundary for the non-admin runtime identity instead of calling the low-level Apply provisioner directly;
7. requires the reconstructed accepted WP15 task to be `Running`.

Before a new remote cutover, WP22A first executes the accepted WP15 `Verify` gate on the exact reviewed head. An already accepted, running exact-head local runtime may be reused instead of being destroyed and rebuilt a second time immediately after successful OWNER Cleanup. Any stale, partial or non-ready state fails Verify and is normalized through accepted WP15 Cleanup → Apply before cutover. Rollback still reconstructs through Cleanup → Apply and must never merely start a stale pre-cutover task.

The Apply transaction does not end when Serve is merely enabled. Post-cutover Serve state, loopback binding, runner firewall binding, runtime batch-logon binding, no-Funnel state and the local self-Serve anti-spoof 403 probe are part of the same transaction. Any failure or exception in those late checks must pass through the same rollback handler and report `LOCAL_ROLLBACK_PASS` or a sanitized rollback failure. Returning a plain FAIL while leaving remote mode active is forbidden.

A failed remote apply must retain a sanitized primary reason code and separately report either local rollback PASS or a sanitized rollback reason. Generic replacement of both failures with one opaque reason is forbidden. Raw nested process output, private URLs, Tailscale identities, runner identities/SIDs and secrets must not be exposed as diagnostic evidence.

The source-controlled `invoke_wp22a_owner_apply_safe.ps1` must establish a protected, non-reparse local result root and atomically persist a sanitized in-progress marker before starting Apply. It must replace that marker with a final allowlisted JSON result without persisting or emitting raw child output, private URL, Tailscale identity or secrets. A successful Apply proves only the private remote **infrastructure** contour plus the local self-Serve negative identity check; it must leave OWNER identity/session fields unproven until the separate device rehearsal. The durable apply result is operational recovery evidence only; it cannot satisfy the OWNER phone-rehearsal Exit Gate.

The source-controlled `diagnose_wp22a_local_state.ps1` is non-mutating and reports only sanitized state needed to classify a partial deployment: base/remote task states, runtime root and deployment-marker presence, runtime identity enabled state, loopback listener state, runner firewall presence, Serve/Funnel status availability and whether Serve points to the expected backend port. It must not emit the tailnet hostname, OWNER login, runner identity/SID or secrets.

## 8. Required deterministic checks

Before OWNER deployment evidence, CI must prove at minimum:

- invalid/non-tailnet host configuration rejected;
- malformed OWNER identity binding rejected;
- wrong Tailscale identity rejected;
- a valid copied remote session cookie, including a copied session+CSRF pair, is rejected when replayed through a wrong or missing Tailscale OWNER identity;
- repeated successful private authentication rotates the remote session token and the previously issued token becomes unusable;
- the remote-specific session policy remains exactly 2 hours idle / 24 hours absolute and the emitted session cookie is bounded by the current idle expiry;
- the same remote-specific policy governs both session issuance and every inner application session resolution, so the accepted local 12-hour idle policy cannot refresh a remote session;
- direct/non-loopback identity-header spoof path rejected;
- hostile Host rejected;
- hostile/missing Origin rejected for unsafe remote requests;
- missing/mismatched CSRF rejected;
- valid same-origin CSRF accepted;
- login rate limit enforced;
- remote session cookie is host-bound, Secure/HttpOnly/SameSite=Strict;
- remote CSRF cookie is host-bound, Secure/SameSite=Strict and not HttpOnly so same-origin frontend code can echo the token header;
- a valid legacy local session cookie presented to the remote host is ignored;
- remote logout clears host-bound cookies and revokes the server-side session;
- server-side session expiry remains effective;
- cross-origin responses do not gain permissive CORS;
- strict CSP is emitted without `unsafe-inline`/`unsafe-eval`, and frontend source does not require React inline style attributes;
- the existing local-only TrustedHost middleware still composes correctly behind the outer remote-access guard;
- frontend Web API sends the CSRF header only when the CSRF cookie exists;
- Windows provisioning, runtime-launcher, sanitized apply-result wrapper, sanitized diagnostic, runner-auditor and OWNER-evidence scripts parse under Windows PowerShell 5.1 without applying changes in CI;
- the source-controlled runtime launcher binds Uvicorn only to loopback and runs as the existing non-admin runtime account during OWNER apply;
- the provisioner creates an outbound Windows Firewall block bound to the exact non-LocalSystem GitHub runner service SID and WP22A backend port;
- the persistent WP22A startup/restart task holds `SeBatchLogonRight` only on the dedicated non-admin runtime identity while remote mode is active, rejects the deny right, records whether WP22A owns the assignment, and restores only a WP22A-owned assignment during Cleanup/rollback;
- the local machine's own Serve endpoint strips a forged OWNER identity and returns HTTP 403; this is a negative anti-spoof proof and is never counted as positive OWNER identity/session evidence;
- the runner audit proves both reviewed impersonation paths fail live: direct TCP access to the loopback backend is denied, and an OWNER-header spoof sent through the node's own no-proxy Serve endpoint returns HTTP 403;
- the running WP22A task remains bound to the current tailnet host and OWNER-login fingerprint before the runner audit can pass;
- Serve activation uses a bounded child process, never passes `--yes`, never emits/persists a consent URL, and converts consent/timeout into sanitized fail-closed rollback reasons;
- Serve cleanup uses the reviewed reset primitive and verifies that no Serve route remains;
- rollback executes accepted WP15 Cleanup → Apply unconditionally; pre-cutover reuse is allowed only after accepted exact-head WP15 Verify, and every failed verification is normalized through Cleanup → Apply so partial task/root absence cannot bypass runtime-identity normalization;
- a reconstructed local runtime must be running before rollback is accepted;
- **all post-cutover acceptance checks remain inside the Apply rollback boundary**; a late Serve/no-Funnel/loopback/firewall/batch-logon/self-Serve-negative failure cannot leave remote mode active without a rollback result;
- apply failures preserve sanitized primary and rollback reason classes without publishing raw subprocess output; a structured nonzero WP15 readiness result is reduced to its first failed boolean boundary before the generic base-Web fallback is allowed;
- the OWNER apply wrapper persists a protected attempt marker before mutation and atomically replaces it with the final sanitized result, so closing the initiating shell cannot erase the only available failure classification;
- the OWNER workflow reports the non-mutating sanitized local deployment state before it requires physical phone evidence;
- the OWNER finalizer requires explicit physical confirmations for separate-device HTTPS reachability, successful `OWNER private access` authentication and logout/session revocation before it may claim positive OWNER identity/session evidence;
- the OWNER finalizer rejects a reparse `C:\ProgramData\OmniCIO` parent or `wp22a` evidence root **before** deleting or replacing any evidence descendant, then creates a protected evidence directory with SYSTEM/Administrators write authority, exact runner read-only authority, no runner write/delete authority and no broad Everyone/Authenticated Users/Users allow rule;
- the source-controlled OWNER evidence validator requires the ACL/read-only booleans and rejects any evidence claiming runner write access;
- the source-controlled Windows boundary tests bind the firewall, recovery, diagnostic, evidence ACL and runner-negative-audit implementation into the focused WP22A gate;
- full repository quality/security/Regression Shield remains green.

## 9. OWNER and runner evidence boundary

CI cannot prove a real Lenovo is joined to the intended OWNER tailnet, that Tailscale Serve is configured privately rather than Funnel, or that a separate authorized OWNER device can reach the exact Web URL and authenticate as OWNER.

Before another OWNER attempt after any failed deployment, the exact replacement implementation must first pass non-OWNER CI and its self-hosted OWNER workflow must report the sanitized Lenovo deployment state. Engineering must use that state to decide whether the next physical action is recovery (`-Cleanup`) or normal apply; the OWNER must not be told to retry a failed implementation blindly.

After code, static checks, focused tests and authoritative CI are GREEN, WP22A requires one reviewed OWNER-local/private rehearsal for the selected private remote candidate. The source-controlled Apply gate first proves exact implementation binding, loopback-only backend, runner-specific loopback firewall binding, runtime batch-logon binding, private Serve state, no Funnel and the **negative** local self-Serve anti-spoof result. It does **not** claim positive OWNER identity or a successful remote session from the Lenovo itself.

The OWNER then proves the exact link from a separate authorized phone/browser device: HTTPS must load through the same tailnet, `OWNER private access` must authenticate successfully, protected Web pages must work through the server-side session, and logout must revoke that session. `finalize_wp22a_owner_evidence.ps1` requires separate explicit switches for HTTPS reachability, successful private OWNER login and logout/session revocation. Only these physical confirmations may turn the final sanitized evidence's OWNER identity/session booleans true.

After that physical observation, the finalizer re-runs the live non-mutating infrastructure verification, rejects a reparse `C:\ProgramData\OmniCIO` parent or `wp22a` evidence root before any evidence-file mutation, protects `C:\ProgramData\OmniCIO\wp22a` with an explicit ACL and writes one sanitized local evidence file. The directory is an OWNER/system boundary: SYSTEM and Administrators retain FullControl, the exact non-admin GitHub runner service SID receives ReadAndExecute only, broad identities receive no allow rule. The evidence records safety facts as booleans but contains no raw OWNER login, runner identity/SID, private tailnet URL, Tailscale authentication material, broker secret, full account identifier or private portfolio payload.

The dedicated OWNER audit **must not synthesize** phone or local-runtime evidence. Before the local evidence exists it first reports the sanitized local deployment state and then reports `OWNER_ACTION_REQUIRED`. After the real OWNER evidence exists, the authoritative workflow runs a second negative test as the actual self-hosted runner identity. The WP22A remote task and loopback listener must be live; the running task's host/fingerprint binding must match the current tailnet identity; the runner-bound firewall rule must match the runner SID; a TCP connection from the runner to the backend port must be denied; a forged OWNER header sent through the node's own no-proxy Serve endpoint must return HTTP 403; the OWNER evidence must remain readable to the validator; and opening that evidence file for write, creating a file beside it, or renaming it must all be denied. Only after those negative probes may CI validate exact SHA/fingerprints and upload a short-lived sanitized derivative.

A repository job that can manufacture, modify, replace or delete the OWNER evidence is an Exit-Gate failure even when every JSON field and implementation hash is otherwise correct. OWNER physical evidence is never synthesized in CI.

Until that evidence and the WP22A Exit Gate are accepted, the current accepted Web remains local/private and Block F stays locked.
