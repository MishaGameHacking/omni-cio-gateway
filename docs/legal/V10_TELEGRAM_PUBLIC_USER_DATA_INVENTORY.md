# V10 Telegram Public-User Data Inventory — Pre-Activation Evidence

Status: **ENGINEERING DATA-MINIMIZATION EVIDENCE / NOT LEGAL SIGN-OFF**

This document supports issue #549 and the Telegram Login activation runbook. It describes accepted source-level data-minimization behavior and the Amendment-18 Timeweb target. Exact accepted-main/current-next authority is always resolved from GitHub and `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`, not frozen in this file. It deliberately does not invent the PROJECT OWNER's legal/operator identity, legal basis, jurisdictional conclusions or regulator notification status.

## Authentication data path

The accepted Telegram code path uses OIDC Authorization Code + PKCE and requests only the mandatory `openid` scope. It does not request Telegram `profile`, `phone` or bot-access scopes.

Telegram's current first-party Login documentation states that:

- Authorization Code Flow with PKCE is supported;
- `openid` is required;
- `profile` and `phone` are optional;
- Allowed website origins and OIDC redirect URIs must be pre-registered in BotFather.

Reference: https://core.telegram.org/bots/telegram-login

Current source behavior:

1. Telegram returns a signed ID token.
2. Omni-CIO verifies issuer, audience, nonce, time bounds, signature and the stable `sub`.
3. The raw Telegram subject exists only long enough to derive a keyed HMAC-SHA256 binding.
4. PostgreSQL stores the provider name plus keyed HMAC binding and opaque internal USER/Tenant identifiers. It does not store the raw Telegram subject.
5. Pre-auth transactions store SHA-256 of state and browser proof, PKCE verifier, nonce, exact redirect URI and bounded timestamps; raw state/browser proof are not persisted and lifetime is at most 15 minutes.
6. Product sessions remain server-side. Browser session authority is an opaque cookie; PostgreSQL stores only the token SHA-256 plus USER/Tenant scope, expiry/revocation metadata.

## Public request metadata

Amendment 18 retired the former Cloudflare edge/runtime. The current Timeweb public
ingress/proxy contract is not yet accepted, so this document does not assume a trusted
forwarded-client-IP header until TW-C/TW-E prove the exact provider behavior.

The Omni-CIO application must treat browser-supplied forwarding headers as untrusted
unless the accepted Timeweb ingress contract authenticates that boundary. The application
must not intentionally write client addresses into product identity/session tables unless
a separately reviewed security/legal purpose requires it.

## Current processors / infrastructure surfaces

Current/future topology selected by accepted Amendment 18:

- Telegram — the only human authentication provider;
- Timeweb Cloud App Platform — selected future public Web/API runtime;
- Timeweb Cloud Managed PostgreSQL 18 — selected future relational account/tenant/session/auth-transaction authority;
- GitHub — source/review/CI/release-provenance authority, not a product identity provider and not a store for provider secret values.

The Timeweb production app/database/DNS cutovers are not yet accepted. Former
Cloudflare/Neon evidence is archive-in-place historical evidence and is not current
activation authority.

No provider secret value, raw Telegram subject, raw browser proof, raw OAuth state or private portfolio payload belongs in GitHub source, PR comments, CI output or artifacts.

## Retention boundaries currently enforced by source

- pre-auth transaction lifetime: at most 15 minutes;
- server-side session idle/absolute expiry and revoke/logout are enforced by accepted session code;
- raw Telegram subject: not persisted;
- raw OAuth state/browser proof: not persisted;
- provider secrets: future Timeweb runtime custody only after its owning gate; never repository values.

A final public privacy notice still needs the real operator/controller identity and contact, applicable legal basis, final retention/deletion policy, processor/transfer determination and user rights/contact wording. Those are deliberately left fail-closed.

## Legal/privacy gate

No source code, encryption or pseudonymization automatically proves that data is outside personal-data law.

For EU users where GDPR applies, the European Commission summarizes required principles including lawfulness/transparency, purpose limitation, data minimization and storage limitation:
https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/principles-gdpr_en

For the Russian/public-product contour, the repository's `docs/legal/V10_RU_COMMERCIAL_LEGAL_GATES.md` remains a planning checklist, not legal advice or sign-off. It requires a real field-by-field determination for the actual operator and production data flows.

Therefore the machine contract intentionally keeps:

`legal_privacy_gate.accepted = false`

until the OWNER supplies or obtains the required real-world determination. This readiness change must not flip production login flags.
