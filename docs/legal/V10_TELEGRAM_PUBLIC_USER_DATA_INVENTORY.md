# V10 Telegram Public-User Data Inventory — Pre-Activation Evidence

Status: **ENGINEERING DATA-MINIMIZATION EVIDENCE / NOT LEGAL SIGN-OFF**

This document supports issue #549 and the Telegram Login activation runbook. It describes the current accepted source behavior on exact base `66ef57dedd07ad68d472cb205da6bb8e87528e94`. It deliberately does not invent the PROJECT OWNER's legal/operator identity, legal basis, jurisdictional conclusions or regulator notification status.

## Authentication data path

The deployed Telegram flow uses OIDC Authorization Code + PKCE and requests only the mandatory `openid` scope. It does not request Telegram `profile`, `phone` or bot-access scopes.

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

Cloudflare receives ordinary Internet request metadata as the public edge. The Worker validates `CF-Connecting-IP`, replaces any client-supplied forwarding headers and passes the validated address only into the internal request scope used by server-side request handling and abuse controls.

The current Omni-CIO application source does not intentionally write that client address into product identity/session tables. This statement is a source-behavior claim, not a claim about every infrastructure/provider log or legal classification.

## Current processors / infrastructure surfaces

Engineering topology relevant to initial Telegram login:

- Telegram — external authentication provider;
- Cloudflare Workers/Containers — public edge/runtime and release platform;
- Neon PostgreSQL 18 — relational account/tenant/session/auth-transaction data plane, constrained to the accepted Frankfurt region contract;
- GitHub — source/review/release-provenance authority, not a product identity provider and not a store for provider secret values.

No provider secret value, raw Telegram subject, raw browser proof, raw OAuth state or private portfolio payload belongs in GitHub source, PR comments, CI output or artifacts.

## Retention boundaries currently enforced by source

- pre-auth transaction lifetime: at most 15 minutes;
- server-side session idle/absolute expiry and revoke/logout are enforced by accepted session code;
- raw Telegram subject: not persisted;
- raw OAuth state/browser proof: not persisted;
- provider secrets: Cloudflare secret custody only, not repository values.

A final public privacy notice still needs the real operator/controller identity and contact, applicable legal basis, final retention/deletion policy, processor/transfer determination and user rights/contact wording. Those are deliberately left fail-closed.

## Legal/privacy gate

No source code, encryption or pseudonymization automatically proves that data is outside personal-data law.

For EU users where GDPR applies, the European Commission summarizes required principles including lawfulness/transparency, purpose limitation, data minimization and storage limitation:
https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/principles-gdpr_en

For the Russian/public-product contour, the repository's `docs/legal/V10_RU_COMMERCIAL_LEGAL_GATES.md` remains a planning checklist, not legal advice or sign-off. It requires a real field-by-field determination for the actual operator and production data flows.

Therefore the machine contract intentionally keeps:

`legal_privacy_gate.accepted = false`

until the OWNER supplies or obtains the required real-world determination. This readiness change must not flip production login flags.
