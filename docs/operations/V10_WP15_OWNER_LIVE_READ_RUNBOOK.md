# Omni-CIO V10 — WP15 Deferred Live Read-Only Acceptance Runbook

Status: **DEFERRED TO AUTHENTICATED WEB BROKER PROVISIONING**

## 1. Authority change

The OWNER-approved identity/multi-tenant amendment supersedes the pre-amendment normal PowerShell token-provisioning workflow.

Normal users must enter, replace and revoke broker credentials only through authenticated Omni-CIO Web Settings. The raw credential is never returned to the browser and is stored only by the approved tenant-scoped secret backend.

Therefore **do not provision a real T-Invest READ token for WP15 through this runbook**.

## 2. Current WP15 acceptance state

WP15 code/security acceptance uses only:

- deterministic synthetic broker fixtures;
- exact-head focused tests;
- authoritative repository/security/Regression Shield CI;
- secret/private-binding isolation tests;
- source-controlled deferred-live evidence.

Expected marker:

`LIVE_EVIDENCE_STATUS=DEFERRED_TO_WEB_PROVISIONING`

The marker means only that real live evidence is intentionally pending the owning Web flow. It is not a PASS for real portfolio correctness.

Until deferred live evidence is completed:

- no real portfolio/account is claimed as accepted;
- Block D remains uncredited;
- WP18 real-data acceptance remains blocked;
- broker credentials remain absent from GitHub/CI/chat.

## 3. Future Web acceptance procedure

WP17 will own the authenticated account/session and `Settings -> Broker Connections` provisioning surface. The reviewed flow must:

1. resolve `user_id` and `tenant_id` from the server-side authenticated session;
2. accept the READ credential over the reviewed secure Web transport;
3. query T-Invest account discovery without returning the raw credential to the client;
4. reject the credential if any accessible OPEN account has broader/unknown authority instead of READ_ONLY;
5. present only masked broker-account identities to the user;
6. allow the user to bind one or more accounts discovered by a broad READ token;
7. persist only tenant-scoped BrokerConnection metadata plus a protected secret reference;
8. run the controlled live snapshot verification for the selected broker account;
9. produce sanitized implementation-bound acceptance evidence.

The future OWNER/user confirmation proves:

- intended broker account selection;
- portfolio-summary parity;
- one sample-position quantity/value parity;
- acceptable freshness;
- no secret/full account/private portfolio payload in uploaded evidence.

## 4. Broad READ token behavior

A token may expose one or multiple broker accounts. Omni-CIO creates separate verified account bindings under the authenticated tenant. The selected account for each read adapter instance is resolved by exact fingerprint from that credential's discovered set.

A second optional TRADE credential is not part of WP15. Later execution may enable only broker accounts independently proven to exist in both the verified READ and verified TRADE account sets.

## 5. PowerShell status

WP8 PowerShell secret tooling remains valid for bootstrap, recovery and privileged maintenance, but it is not the normal product provisioning UX and is not required to complete amended WP15 code/security acceptance.

If `broker_read` is currently `UNPROVISIONED`, leave it unprovisioned until the reviewed Web broker-provisioning flow exists.

## 6. OWNER action now

**None.**

Do not send broker tokens, full account IDs, fingerprints, portfolio values, position data or screenshots to GitHub/ChatGPT for this gate.
