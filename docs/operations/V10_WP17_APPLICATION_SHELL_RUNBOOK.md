# Omni-CIO V10 WP17 — Application Shell / local broker provisioning runbook

Status: **accepted historical WP17 procedure / current Amendment 18 override applies**

> **Amendment 18 CURRENT-AUTHORITY OVERRIDE:** this runbook retains the accepted
> WP17 local/Windows security procedure because the READ-vault OWNER evidence is
> still an exact-head acceptance boundary. It is not current Timeweb product-login
> or deployment authority. Current deployed-product direction is Timeweb +
> Telegram Login only; VK ID and the local private-test login are historical
> acceptance surfaces and must not enter the Timeweb runtime composition.

## Scope

WP17 creates the authenticated local/private Web shell and the normal `Settings -> Broker Connections` READ-token flow. It does not expose Omni-CIO to the public Internet, enable public registration, accept TRADE credentials or authorize Real execution.

The protected production gateway remains `app:app`. The Web adapter is separate source-controlled code under `apps/web` + `apps/api` and is local/private until the owning external-ingress gate.

## Ordinary account UX

Current ordinary product login is exactly **Telegram Login**. VK ID is retired
from current/future deployed composition by Amendment 18. No Omni-CIO local
password, Google login, OWNER/admin/demo/preview product-session bypass, or
browser-selected tenant authority is introduced.

The remaining sections describing local/private WP17 acceptance are preserved
only because they own historical Windows security evidence and the current
READ-vault exact-head proof. They do not define the Timeweb product login path.

## Historical local/private test identity

The historical `POST /api/v10/web/private-test-login` acceptance endpoint is
not installed by `apps.api.hosted_runtime:create_app`. In its accepted local
WP17 contour it is:

- disabled by default;
- enabled only when `OMNI_V10_WEB_PRIVATE_ACCEPTANCE=1` is present in the local process environment;
- accepted only from a loopback client address;
- not presented as an ordinary login provider;
- not public-launch authority.

It issues the same opaque server-side session shape used by the shell. Browser cookies are HttpOnly + SameSite=Strict; public `Secure`/TLS enforcement is owned by WP22A.

## Web build / local launch

The frontend uses the exact accepted WP16 Node/npm lock.

From repository root on the Lenovo node, after WP17 code acceptance:

```powershell
Set-Location .\apps\web
& 'C:\Program Files\nodejs\npm.cmd' ci --ignore-scripts --no-audit --no-fund
& 'C:\Program Files\nodejs\npm.cmd' run build
Set-Location ..\..
```

The local API factory is:

`apps.api.app:create_local_private_app`

It must bind only to loopback during WP17 acceptance. A reviewed service/launcher must use `127.0.0.1`; `0.0.0.0`, router port forwarding, public tunnels and public hostnames are prohibited before WP22A.

Database authentication remains the accepted WP13 libpq/local runtime boundary. Do not place database passwords in source, workflow YAML, CLI arguments or evidence.

## Connection-scoped READ secret boundary

WP17 reuses WP8 DPAPI LocalMachine under:

`C:\ProgramData\OmniCIO\secrets\read-broker\connections`

The child does not exist as an accepted runtime write boundary until OWNER applies the reviewed ACL script:

`infrastructure/windows/provision_wp17_web_read_vault.ps1`

That OWNER step is intentionally deferred until all code/CI/security gates that do not need it are GREEN.

The script must:

- refuse to adopt an unmarked directory;
- require the existing WP8 read-broker ownership marker;
- grant `omni-cio-runtime` Modify only on the READ-connections child;
- preserve SYSTEM/Administrators recovery authority;
- deny the CI runner secret `ReadData`, write/delete and ACL-control capability;
- leave `broker_trading` ACL unchanged;
- use only synthetic/non-secret sentinel evidence.

No real T-Invest token is entered into PowerShell. The actual READ token is later entered only through the authenticated Web settings flow.

## OWNER READ-vault acceptance evidence

ACL application and acceptance are deliberately separate. A successful Administrator `-Apply` or `-Verify` is necessary but is not sufficient evidence for the WP17 Exit Gate.

After the exact reviewed WP17 head is otherwise GREEN, OWNER runs the reviewed evidence finalizer from a clean checkout of that exact head:

`infrastructure/windows/finalize_wp17_web_read_vault_evidence.ps1`

The finalizer must:

- refuse a dirty checkout or invalid Git HEAD;
- invoke the current READ-vault verifier without entering any real credential;
- bind sanitized evidence to the exact 40-character implementation Git SHA;
- bind evidence to SHA-256 hashes of the reviewed provisioner and evidence-finalizer scripts;
- protect `C:\ProgramData\OmniCIO\wp17` so SYSTEM/Administrators retain recovery authority and the ordinary CI runner receives read-only evidence access, not write/delete/ACL-control authority;
- record only booleans, source hashes and the reviewed implementation SHA; never SIDs, usernames, hostnames, raw ACLs, broker secrets or private portfolio data.

The dedicated `V10 WP17 OWNER Read Vault Audit` then runs under the ordinary non-admin Lenovo CI identity. It must fail closed unless the evidence is bound to its exact checked-out head and current script hashes. It also performs direct negative permission probes proving that the runner:

- cannot read the synthetic DPAPI sentinel payload in the READ-connections child;
- cannot create/write a file in the READ-connections child;
- cannot modify the OWNER evidence directory.

Only a GREEN OWNER read-vault audit may satisfy the runner-isolation portion of this boundary. A missing evidence file is `OWNER_ACTION_REQUIRED`, not a synthetic PASS. Do not weaken ACLs, make the runner Administrator or grant it secret `ReadData` merely to make the audit pass.

## Web provisioning protocol

1. Authenticated user opens `Settings -> Broker Connections`.
2. Candidate T-Invest READ token is POSTed once over same-origin API.
3. Server invokes accepted WP15 account discovery.
4. Any FULL/unknown authority rejects the credential before storage.
5. Server creates a short-lived memory-only challenge and returns only masked accounts plus opaque selection identity.
6. Browser clears the token field and selects one or more verified accounts.
7. Commit revalidates the token/account set.
8. Token is DPAPI-protected in the connection-scoped READ vault.
9. PostgreSQL stores only opaque connection metadata and canonical/masked account bindings.
10. Server zeroes short-lived provisioning bytes.

Replacement uses the same preview/commit flow and must prove exactly the same existing account set. Revocation removes the connection READ secret and marks the connection revoked. TRADE/transfer/withdrawal credentials are not accepted by WP17.

## Deferred WP15 live evidence

After the Web shell, migration and READ-vault boundary are accepted, OWNER will use this Web flow to enter a real T-Invest READ token. The reviewed live acceptance must then prove, for the authenticated tenant/BrokerConnection:

- READ_ONLY authority;
- intended masked broker account selection;
- portfolio summary parity;
- one sample-position quantity/value parity;
- acceptable freshness;
- sanitized evidence bound to the reviewed implementation.

Until that real evidence passes, Block D remains uncredited and WP18 cannot claim real broker-data acceptance.

## Evidence rules

Allowed CI/acceptance evidence:

- exact Git SHA/build version;
- booleans/status codes;
- masked account labels only where OWNER-local review requires them;
- counts;
- sanitized synthetic screenshots;
- migration/security hashes.

Forbidden:

- real T-Invest token or DPAPI ciphertext;
- provider login secrets;
- full broker account IDs;
- private portfolio payload;
- secret-root archives;
- Windows SID/username/hostname disclosure in durable artifacts.

## Rollback / failure

If Web/API downstream is degraded, the shell must remain readable and show explicit DEGRADED/OFFLINE state; it must not invent financial freshness.

If the READ-vault ACL cannot be proven, provisioning remains blocked. Do not fall back to PowerShell token entry, environment tokens, PostgreSQL token columns, TRADE credentials or elevated Web execution.

WP18 remains locked until WP17 Exit Gate and the deferred real broker evidence are both satisfied.
