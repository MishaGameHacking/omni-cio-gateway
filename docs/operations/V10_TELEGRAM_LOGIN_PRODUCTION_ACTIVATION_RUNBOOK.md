# V10 Telegram Login Production Activation Runbook

Scope: capability-specific activation for `telegram_login` under Amendment 13.

This runbook contains names and public callback/origin values only. Never paste the
Telegram Client Secret, provider tokens, identity-binding key, CSRF key or any other real
secret into GitHub, chat, CI logs, screenshots or artifacts.

## Canonical production registration

Official Telegram Login/OIDC reference:
`https://core.telegram.org/bots/telegram-login`

Register with BotFather Login Widget / OIDC:

- Allowed origin: `https://omnicio.ru`
- Redirect URI:
  `https://omnicio.ru/api/v10/web/auth/telegram/callback`

Telegram documents Authorization Code flow with PKCE and requires Allowed URLs to be
pre-registered before redirect/login processing.

## Cloudflare secret binding names

Provider/runtime values must exist only in approved Cloudflare secret custody:

- `OMNI_V10_TELEGRAM_OIDC_CLIENT_ID`
- `OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET`
- `OMNI_V10_IDENTITY_BINDING_KEY_HEX`
- `OMNI_V10_CSRF_BINDING_KEY_HEX`

The Worker passes only this reviewed allowlist to the production Container. Staging does
not receive these provider-auth bindings from the production path.

Do not store the values in `wrangler.jsonc`, repository files or GitHub Actions secrets
merely to relay them into Cloudflare. Worker Secrets / approved Cloudflare secret custody
is the runtime authority.

## Public activation flags

All source-controlled activation switches remain off in this preparation:

- `PUBLIC_MULTI_USER_ENABLED=false`;
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`;
- `OMNI_V10_VK_ID_LOGIN_ENABLED=false`.

Provider credentials alone must not activate login/registration. A later focused Telegram
activation may set only `PUBLIC_MULTI_USER_ENABLED=true` and
`OMNI_V10_TELEGRAM_LOGIN_ENABLED=true` after the owning gates close.
`OMNI_V10_VK_ID_LOGIN_ENABLED` remains `false` until the separate VK ID capability
has its own accepted provider/live evidence.

When public multi-user is false, configured providers report
`PUBLIC_MULTI_USER_DISABLED`. When public multi-user is true but a provider's own switch
is false, that provider reports `PROVIDER_ACTIVATION_DISABLED`.

## Acceptance sequence

1. source-preparation PR exact-head DRAFT/READY GREEN and squash merge;
2. exact-new-main Regression Shield + Engineering Governance SUCCESS;
3. non-delegable Telegram Allowed URL/callback registration;
4. Cloudflare secret provisioning without exposing values;
5. read-only/sanitized readiness check proving named bindings exist;
6. focused activation PR changing only the owning public-user activation state;
7. production release SUCCESS;
8. real canonical-Web USER login -> callback -> ordinary product account -> Tenant ->
   server-side Session;
9. logout/revoke and multi-user isolation negatives;
10. update capability state only from accepted real evidence.

At no point does login activation authorize broker write or Real-money execution.
