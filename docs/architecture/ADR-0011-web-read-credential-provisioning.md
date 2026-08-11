# ADR-0011 — Authenticated Web provisioning of tenant-owned broker READ credentials

Status: **WP17 implementation candidate**

## Context

The OWNER-approved Identity / Multi-Tenant Account / Authentication Amendment requires the normal T-Invest READ credential flow to live under authenticated `Settings -> Broker Connections`, not PowerShell. WP8 already accepted Windows DPAPI `LocalMachine` plus protected NTFS ACLs as the local secret-storage architecture. WP15 already accepts only READ-only T-Invest authority and returns masked/canonical account bindings.

Creating a second vault, storing raw tokens in PostgreSQL, or granting the Web/runtime contour access to `broker_trading` would violate V10 boundaries.

## Decision

WP17 extends only the existing WP8 **read-broker** boundary with a connection-scoped child:

`C:\ProgramData\OmniCIO\secrets\read-broker\connections`

Properties:

- every stored secret is a DPAPI `LocalMachine` ciphertext using the accepted WP8 protection primitive;
- filenames are derived only from opaque random `read-connection:v1:<sha256>` references, never broker account IDs;
- `omni-cio-runtime` receives create/read/replace/delete authority only inside this READ child;
- SYSTEM/Administrators retain recovery authority;
- the ordinary CI runner may inspect ACL metadata/traverse but receives no secret `ReadData`, write, delete or permission-control authority;
- the existing legacy `broker_read` blob and its lifecycle remain untouched for compatibility/recovery;
- `broker_trading`, Telegram, encryption and external-source classes remain outside the runtime write boundary;
- the browser sends a candidate READ token once over the authenticated same-origin API, receives only an opaque short-lived provisioning challenge plus masked account bindings, and never receives the raw token again;
- the server revalidates the credential as READ-only through the accepted WP15 connection adapter before durable storage;
- short-lived plaintext provisioning material is memory-only, tenant/session scoped and zeroed on commit/cancel/expiry;
- PostgreSQL stores only connection state, opaque secret reference and verified masked/canonical account bindings; no token or DPAPI ciphertext is stored in PostgreSQL;
- public ingress/public multi-user activation remains disabled in WP17.

## Why not database ciphertext

WP8 explicitly treats DPAPI `LocalMachine` as encryption rather than principal authorization and relies on the protected DACL as the same-machine authorization boundary. Putting connection ciphertext in a database readable by broader runtime/database principals would weaken that accepted boundary. Keeping ciphertext in the reviewed secret subtree preserves the WP8 authorization model.

## Why runtime write is acceptable for READ only

A user-facing provisioning flow cannot function if the runtime can only read a pre-provisioned singleton. The added capability is deliberately bounded to READ credentials that are independently verified before storage. It does not create broker write/trade/transfer authority. A compromised Web/runtime process could alter/revoke READ credentials and therefore affect confidentiality/availability of read data; it still cannot acquire `broker_trading` from this boundary or submit orders through the WP15 adapter.

## Rejected alternatives

- new cloud/third-party vault in WP17 — competing secret stack and unnecessary external custody;
- plaintext or reversible token column in PostgreSQL — violates secret boundary;
- one global `broker_read` token — incompatible with tenant-owned multiple BrokerConnections;
- running Web as OWNER/Administrator — excessive privilege;
- using TRADE token as READ fallback — explicitly prohibited;
- public OAuth/broker provisioning before WP22A — prohibited external surface.

## Required evidence

Before WP17 acceptance:

- static and unit tests prove no browser Web Storage credential persistence and no raw token in API response models;
- broad/incorrect broker authority is rejected before durable storage;
- connection challenge is scoped to the authenticated tenant/session and expires;
- filesystem vault tests prove path traversal is impossible and replacement/revocation are connection-scoped;
- reviewed Lenovo OWNER apply creates the child ACL and an ordinary CI identity proves secret data read/write is denied;
- `broker_trading` ACL/content remains unchanged;
- full repository Regression Shield/security/secret scan stays green.

Any future central/public multi-user secret custody requires a new explicit security/legal architecture decision; this ADR authorizes only the private-node V10 runtime boundary.