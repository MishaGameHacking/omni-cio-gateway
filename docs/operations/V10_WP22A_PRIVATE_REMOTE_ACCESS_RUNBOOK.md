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

Because a second local process could otherwise attempt to forge proxy identity headers against the same loopback listener, WP22A also installs an OWNER-admin Windows Firewall outbound block for the exact GitHub Actions runner service identity to the WP22A loopback backend port. This is an extension of the accepted WP6 runner/runtime privilege separation, not a new authentication provider.

## Pre-application requirements

Do not perform the OWNER-local step until the reviewed WP22A PR has passed its code/static/security gates.

The Lenovo must have:

- the reviewed exact WP22A Git head;
- the accepted PostgreSQL/Web runtime baseline;
- the accepted non-admin GitHub self-hosted runner identity from WP6;
- Tailscale installed and already joined to the intended OWNER-controlled tailnet;
- HTTPS/Serve support available in the installed Tailscale version;
- no active Funnel/public configuration on the Personal node;
- no unrelated existing Serve configuration that would be overwritten by the Omni-CIO root route;
- an untagged Tailscale node identity for this Personal OWNER gate. Tailscale Serve does not populate user identity headers for tagged devices, so the reviewed provisioner rejects a tagged Lenovo rather than weakening OWNER authentication.

The phone or other OWNER browser device must join the same authorized tailnet before the separate-device rehearsal.

Never send Tailscale authentication keys, provider credentials, OWNER login, runner identity/SID, broker credentials or private portfolio values to GitHub/CI/chat.

### HTTPS certificate privacy / OWNER consent

Tailscale Serve HTTPS requires HTTPS certificates to be enabled for the tailnet. If that capability has never been enabled, the `tailscale serve` CLI may require an interactive Tailscale web-consent step instead of completing immediately.

Enabling Tailscale HTTPS has a privacy consequence that requires OWNER awareness: the device name and tailnet DNS suffix used in the certificate become visible through the public Certificate Transparency ecosystem even though network access to Serve remains restricted to the tailnet. Before enabling HTTPS, the OWNER must therefore verify that the Lenovo Tailscale machine name itself contains no sensitive/private information.

This is a real external-account/privacy consent boundary. Engineering does not silently accept it on the OWNER's behalf and does not replace it with public Funnel exposure. If HTTPS is already enabled and the node name is acceptable, no additional certificate-file provisioning is required for the Serve path; Tailscale manages the Serve certificate lifecycle.

## Source-controlled deployment, recovery and evidence boundary

WP22A adds five reviewed Windows scripts:

```text
infrastructure/windows/run_wp22a_private_remote_runtime.ps1
infrastructure/windows/provision_wp22a_private_remote_access.ps1
infrastructure/windows/diagnose_wp22a_local_state.ps1
infrastructure/windows/audit_wp22a_runner_loopback.ps1
infrastructure/windows/finalize_wp22a_owner_evidence.ps1
```

The runtime launcher:

- runs only as the existing non-admin `omni-cio-runtime` identity;
- requires an exact source-controlled deployment SHA marker;
- binds Uvicorn only to `127.0.0.1`;
- uses PostgreSQL SSPI under the existing runtime role;
- explicitly disables inherited WP17/WP15 loopback-only acceptance modes before enabling the WP22A remote factory;
- activates only `apps.api.wp22a_remote:create_private_remote_app`.

The provisioning gate:

- requires an exact clean reviewed Git head;
- reuses the accepted WP15/WP17 Web deployment and broker READ-vault boundary instead of creating a second Web stack;
- derives the local `*.ts.net` DNS name and OWNER Tailscale login fingerprint from local Tailscale status without writing the raw login to GitHub;
- rejects tagged nodes, active Funnel/public ingress and unrelated existing Serve configuration;
- discovers the exact GitHub Actions runner service identity locally and rejects a LocalSystem runner;
- installs an outbound Windows Firewall block for that exact runner SID to `127.0.0.1:<web-port>` and verifies the rule's user/address/port binding;
- installs a limited remote scheduled task with restart-on-failure and startup trigger;
- verifies that the Web listener is loopback-only;
- configures Tailscale Serve in background mode to the loopback Web port;
- performs a real HTTPS OWNER identity/session/login/logout probe through Serve;
- still leaves a separate phone/browser reachability rehearsal as OWNER evidence.

The recovery behavior is deliberately fail-closed and idempotent:

- Tailscale Serve cleanup uses `tailscale serve reset`, then verifies that no Serve `*.ts.net` route remains;
- cleanup never enables Funnel as a fallback;
- before both remote cutover and local-runtime reconstruction, the accepted WP15 Cleanup then WP15 Apply path is executed unconditionally. WP15 Cleanup is the authority that removes a stale task/runtime deployment and disables `omni-cio-runtime`, including partial states where the task/root are already absent but the runtime identity remained enabled;
- local reconstruction must end with the accepted WP15 task actually `Running`; merely finding a task object is not recovery evidence;
- a failed apply preserves a sanitized primary reason code and separately reports whether local rollback passed or the sanitized rollback reason. Raw nested command output, credentials, identities and private URLs are not promoted into the reason code;
- a failed apply with a failed rollback leaves WP22A blocked. It must not be retried blindly on the same implementation head.

The sanitized local-state diagnostic is non-mutating. It is designed for self-hosted CI to report only task states and safety booleans needed to classify a partial deployment: runtime root/marker presence, runtime identity enabled state, loopback listener state, runner firewall presence, Serve/Funnel status availability and whether Serve points at the expected backend port. It does not emit the tailnet hostname, OWNER login, runner identity/SID or secret values.

The runner auditor:

- is intended to execute later as the actual non-admin self-hosted GitHub runner identity;
- requires the remote WP22A task and loopback listener to be live;
- verifies the runner-bound firewall rule without emitting the raw runner identity or SID;
- makes a real TCP connection attempt from the runner to `127.0.0.1:<web-port>` and requires that connection to be denied;
- requires the sanitized OWNER evidence to be readable for validation but not writable by the runner;
- attempts to open the evidence file for write, create a new file in the evidence directory and rename the OWNER evidence, and requires every mutation attempt to be denied;
- fails WP22A if the ordinary CI runner can reach the backend directly or manufacture/replace OWNER evidence.

The finalizer:

- can run only after the OWNER has physically opened the HTTPS link from a separate authorized phone/browser and confirmed logout/session revocation;
- re-runs the non-mutating live `-Verify` gate on the exact clean reviewed head;
- requires the runner-loopback firewall binding to remain present;
- rejects a reparse-point evidence root;
- protects `C:\ProgramData\OmniCIO\wp22a` with inheritance disabled: SYSTEM and Administrators retain FullControl, the exact GitHub runner SID receives ReadAndExecute only, and broad Everyone/Authenticated Users/Users allows are absent;
- writes only `C:\ProgramData\OmniCIO\wp22a\owner-rehearsal.sanitized.local.json`;
- binds the evidence to the exact Git SHA and SHA-256 fingerprints of the reviewed security/runtime/runner-audit/evidence implementation;
- records the protected/read-only evidence state as booleans;
- stores no raw OWNER login, runner identity/SID, private `*.ts.net` URL, Tailscale authentication material, broker secret, full account ID or private portfolio payload.

CI cannot synthesize this OWNER evidence. The dedicated OWNER audit first reports the sanitized local deployment state, then requires the real local OWNER evidence. Only after the local evidence exists does it independently prove runner loopback denial and runner evidence-mutation denial, validate the exact implementation binding and upload a short-lived sanitized derivative.

## Private runtime configuration

The runtime receives three non-source-controlled values through the local scheduled-task boundary:

```text
OMNI_V10_WEB_PRIVATE_REMOTE=1
OMNI_V10_WEB_EXTERNAL_HOST=<exact *.ts.net node hostname>
OMNI_V10_TAILSCALE_OWNER_LOGIN_SHA256=<sha256 fingerprint>
```

The fingerprint is derived locally from the normalized OWNER Tailscale login. The raw login is not a repository setting or output field. The private remote middleware rechecks this OWNER fingerprint on every remote request except the non-sensitive readiness/status probe, so possession of a copied Web session cookie or copied session+CSRF pair is not sufficient when the request arrives with a wrong or missing Tailscale user identity.

WP22A uses a remote-only server-session lifetime of **2 hours idle / 24 hours absolute**. A successful private OWNER authentication revokes any previously presented remote session token before creating the replacement token, so re-authentication rotates the session identifier instead of extending an old bearer indefinitely. The accepted local Web session baseline is not changed by this remote policy.

The application factory is:

```text
apps.api.wp22a_remote:create_private_remote_app
```

The Web process remains bound to `127.0.0.1` only.

## Tailscale Serve and local-process boundary

The reviewed target is Tailscale **Serve**, not Funnel. Serve proxies the local loopback Web service into the private tailnet HTTPS endpoint. The installed Tailscale client remains the runtime source of truth for exact CLI behavior.

The provisioning gate fails closed rather than enabling Funnel. Before acceptance it verifies all of the following locally:

- the service target is the loopback Web port;
- the reported URL is the intended `https://<node>.<tailnet>.ts.net` host;
- the Serve route is present only after the backend is ready;
- dedicated Funnel status does not report public exposure;
- the application Web process itself is not listening on a non-loopback address;
- the ordinary GitHub runner has an exact outbound user-scoped deny rule to the backend port;
- a real HTTPS request through Serve receives the expected OWNER identity and can create/revoke a server-side session.

The later self-hosted OWNER audit provides the second half of this boundary: while the WP22A runtime is still live, the actual runner identity must fail a direct TCP connection attempt to the loopback backend. A configured firewall rule without a successful negative runner probe is not Exit-Gate evidence.

## Recovery after a failed OWNER apply

A previous reviewed implementation may have changed local deployment state before returning a failure. Do not infer from the absence of a task or runtime directory that the machine is already clean, and do not manually delete Omni-CIO runtime state.

Engineering must first review the sanitized diagnostic from the exact replacement head. After the replacement head has passed all non-OWNER CI, recovery is performed with that exact reviewed head using `-Cleanup`. The corrected Cleanup path resets Serve, removes the remote task/firewall, unconditionally normalizes the accepted WP15 local Web state through Cleanup → Apply and verifies that the reconstructed local Web task is running.

Only after the corrected Cleanup returns PASS may a new `-Apply` be attempted. If Cleanup fails, stop and preserve its sanitized reason code; do not continue to Apply or finalization.

## OWNER-local commands — only after exact-head non-OWNER CI GREEN

From an elevated PowerShell in the exact clean reviewed checkout, the normal reviewed apply command is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_wp22a_private_remote_access.ps1" -ExpectedImplementationSha "<EXACT_REVIEWED_HEAD>" -Apply -AsJson
```

The script returns the private HTTPS URL locally after a successful remote deployment. Do not paste the raw Tailscale login, private URL or credentials into GitHub/chat.

If Tailscale requires external HTTPS consent, stop at that OWNER decision boundary. Review the Tailscale machine name first; enable HTTPS only if its publication in certificate transparency is acceptable. Then rerun the same exact-head `-Apply` command.

A non-mutating verification after apply is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_wp22a_private_remote_access.ps1" -ExpectedImplementationSha "<EXACT_REVIEWED_HEAD>" -Verify -AsJson
```

Rollback/recovery is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\provision_wp22a_private_remote_access.ps1" -ExpectedImplementationSha "<EXACT_REVIEWED_HEAD>" -Cleanup -AsJson
```

Cleanup does **not** merely restart the pre-cutover WP15 scheduled task, because WP22A rotates the runtime-account password when registering its own task and the older task credential may therefore be stale. Cleanup resets Serve, removes the WP22A task and runner firewall rule, invokes accepted WP15 Cleanup unconditionally, then recreates/starts the accepted local Web runtime through WP15 Apply with a fresh runtime credential and readiness checks. It never enables Funnel as a fallback.

The same reconstruction is attempted automatically if `-Apply` fails after cutover. Expected sanitized failure shapes distinguish the two outcomes:

```text
WP22A_APPLY_FAILED:<PRIMARY_REASON>;LOCAL_ROLLBACK_PASS
WP22A_APPLY_FAILED:<PRIMARY_REASON>;LOCAL_ROLLBACK_FAILED:<ROLLBACK_REASON>
```

Both are failures. `LOCAL_ROLLBACK_PASS` only means the accepted local Web was reconstructed after the failed remote attempt; it does not satisfy WP22A.

## Expected phone/browser behavior

From an authorized OWNER device inside the intended tailnet:

1. Open the exact HTTPS tailnet URL printed locally by the provisioning gate.
2. The application shows `OWNER private access` only when the request reached the backend through the reviewed private remote path.
3. Select the private access action. The backend binds the Tailscale identity to the configured OWNER fingerprint.
4. A successful authentication creates a rotated server-side session and host-bound Secure/HttpOnly/SameSite session cookie bounded by the 2-hour idle / 24-hour absolute remote policy; subsequent remote data/API requests continue to require the matching Tailscale OWNER identity in addition to the session.
5. Navigate through Portfolio, Watchtower, Research, Decisions/Risk/Plans and System to prove the existing single Web App is reachable remotely.
6. Logout, reopen the URL and verify the server-side session state changes as expected.

A wrong tailnet identity, a copied session or session+CSRF replayed under a wrong/missing tailnet identity, a previously rotated-away session token, direct non-loopback request, hostile Host/Origin, missing CSRF token or excessive login attempts must fail closed. Those negative browser paths are deterministic CI obligations. The runner-local spoof path is separately proven by the source-controlled runner auditor; the OWNER is not asked to imitate it manually.

Only after steps 1–6 have genuinely passed, finalize the local sanitized evidence:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\finalize_wp22a_owner_evidence.ps1" -ExpectedImplementationSha "<EXACT_REVIEWED_HEAD>" -PhoneHttpsReachabilityConfirmed -LogoutSessionRevocationConfirmed
```

The confirmation switches are OWNER assertions about physical observations and must never be used unless the separate-device rehearsal was actually performed.

After the finalizer succeeds, the dedicated GitHub OWNER audit must be run on that exact implementation head while the remote runtime remains live. That workflow independently proves that the actual CI runner cannot connect directly to the loopback backend, cannot open the OWNER evidence for write, cannot create a replacement file and cannot rename the OWNER evidence before it validates the OWNER file.

## Sanitized acceptance evidence

Return only facts similar to:

```text
WP22A OWNER private remote gate: PASS
Exact implementation binding: True
Backend loopback-only: True
CI runner loopback firewall: True
OWNER evidence ACL protected: True
CI runner evidence write allowed: False
Tailscale Serve private: True
Funnel/public ingress: False
OWNER identity binding: True
Secure session: True
Phone HTTPS reachability: True
Logout/session revoke: True
```

Do not include the actual tailnet login, runner name/SID, authentication keys, broker token, full account ID, portfolio totals or private position details. The private `*.ts.net` URL does not need to be sent back to engineering if the sanitized booleans are sufficient.

## Rollback

If the private remote path is unsafe or unavailable:

- run the reviewed exact-head `-Cleanup` mode;
- require the accepted WP15 local Web reconstruction to pass instead of assuming a stale task is usable;
- keep `REAL_TRADING_ENABLED=false`;
- keep `trading_methods=false`;
- do not substitute Funnel/public exposure as a workaround;
- preserve the protected V9 rollback and current accepted `main` until WP22A is accepted.
