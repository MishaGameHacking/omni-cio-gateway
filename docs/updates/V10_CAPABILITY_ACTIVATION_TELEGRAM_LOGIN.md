# Omni-CIO V10 — Telegram Login Capability Activation Ledger

`WORKING CAPABILITY ACTIVATION STATE — NOT ACCEPTED MAIN AUTHORITY`

This ledger tracks the material `telegram_login` activation transition under Amendment
13. Accepted current state remains only in `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## Identity

- Capability ID: `telegram_login`
- User-facing name: Telegram Login
- Owning WP/System Update: WP22A authentication architecture / Amendment 13 activation
- Accepted base `main` SHA: `8e057112817277b8f4ba0da31d125c0cb91bc21e`
- Branch: `activation/telegram-login-production-plumbing`
- Dashboard: issue #549
- Canonical Web/runtime target: `https://omnicio.ru` / Cloudflare Worker + Container
- Current accepted capability state: `BLOCKED_EXTERNAL`
- Proposed capability state: `LIVE_OPERABLE`

## Implementation / technical evidence

- [x] Telegram OIDC Authorization Code + PKCE implementation is accepted.
- [x] Browser-bound state/proof, callback validation and session lifecycle are accepted.
- [x] Verified identity -> ordinary product account -> Tenant -> server-side Session is accepted.
- [x] Database-enforced tenant isolation and reserved historical OWNER-scope rejection are accepted.
- [x] Canonical Cloudflare production ingress/release is accepted through Release #79.
- [ ] Production runtime-only Telegram provider bindings are present and proven.
- [ ] Real browser login/logout/revocation is proven on canonical Web.

Repository preparation in this branch:

- explicit Worker -> production Container allowlist for provider-auth binding names;
- staging isolation from provider-auth secret propagation;
- public browser Origin authority decoupled from the internal Container Host;
- registration bound to the existing `PUBLIC_MULTI_USER_ENABLED` fail-closed gate;
- Telegram activation additionally requires `OMNI_V10_TELEGRAM_LOGIN_ENABLED=true`;
- VK ID remains independently gated by `OMNI_V10_VK_ID_LOGIN_ENABLED=false`;
- truthful UI/API reason while provider configuration exists but public or
  capability-specific activation is off.

## External blocker inventory

- [ ] Telegram Allowed URL/origin registration for `https://omnicio.ru`.
- [ ] Telegram OIDC callback registration for
      `https://omnicio.ru/api/v10/web/auth/telegram/callback`.
- [ ] Runtime-only Telegram Client ID / Client Secret in Cloudflare secret custody.
- [ ] Runtime-only identity-binding and CSRF keys in Cloudflare secret custody.
- [ ] Public-user privacy/legal/capacity/monitoring/incident gates accepted.
- [ ] `PUBLIC_MULTI_USER_ENABLED=true` accepted only after all owning gates close.
- [ ] `OMNI_V10_TELEGRAM_LOGIN_ENABLED=true` accepted only for the Telegram capability.
- [x] `OMNI_V10_VK_ID_LOGIN_ENABLED=false` remains fail-closed in this activation.

No secret value belongs in this file, issue #549, PR comments, CI logs or chat.

## Real-user operability evidence

Not yet accepted. Required later evidence:

- canonical `https://omnicio.ru` login button redirects to Telegram;
- callback verifies real provider identity and establishes only a server-side USER session;
- logout and revoke-all invalidate the correct user sessions;
- provider outage/misconfiguration produces a bounded fail-closed user-visible state;
- no OWNER/admin/demo/auth bypass is used.

## Multi-user / tenant isolation

Accepted structural implementation exists, but the real-user activation step still needs
sanitized live negatives before `LIVE_OPERABLE`:

- USER A cannot read USER B state;
- USER A cannot mutate USER B state;
- guessed object IDs do not widen tenant scope;
- revoke/logout is user-scoped;
- one user's provider/broker credentials cannot cross tenant scope.

## Kill switch / runtime availability

- Accepted capability state: `BLOCKED_EXTERNAL`
- Current runtime availability: provider login unavailable
- Kill switch / temporary suspension active: YES
- Reason: `PUBLIC_MULTI_USER_ENABLED=false` plus missing real provider registration/secrets
- Recovery criteria: all blocker inventory items accepted with real sanitized evidence

## Monitoring / recovery

- [x] Provider misconfiguration fails closed.
- [x] Session revoke/logout paths exist.
- [x] Cloudflare release rollback/recovery exists.
- [ ] Provider-specific production availability/incident evidence accepted.

## State transition decision

```text
FROM: BLOCKED_EXTERNAL
TO: LIVE_OPERABLE
DECISION: BLOCKED
EXTERNAL GATES CLOSED: canonical Cloudflare ingress/release
REMAINING BLOCKERS: provider registration, runtime secret custody, public-user
privacy/legal/capacity/monitoring, real-user evidence
EXACT EVIDENCE: issue #549 + current activation branch/PR
```

## GitHub acceptance lifecycle

- [ ] Exact-head DRAFT applicable checks all `success`.
- [ ] Independent review complete.
- [ ] Unresolved blocking review threads = 0.
- [ ] Fresh READY exact-head applicable checks all `success`.
- [ ] Squash merge complete.
- [ ] Exact-new-main Regression Shield `success`.
- [ ] Exact-new-main V10 Engineering Governance `success`.

This source-preparation PR must not change the accepted capability state or flip
`PUBLIC_MULTI_USER_ENABLED` to `true`.
