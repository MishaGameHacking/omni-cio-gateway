# V10 Identity and Broker Connection Security Notes

Status: current security companion under Amendment 18; historical multi-provider design below is superseded where it conflicts with Telegram-only authority.

## Authentication

- Ordinary human product login provider: Telegram Login only.
- VK ID is retired from current/future deployed composition and receives no new feature authority.
- Internal `user_id` is authoritative; Telegram identity is a unique external binding, never tenant authority by itself.
- Validate Telegram result server-side; reject stale/replayed/state/nonce/PKCE mismatches.
- Do not trust provider display name, username, avatar, phone or e-mail for authorization or account merge.
- No second ordinary human-login provider or provider-linking flow may be introduced without a new accepted authority change.

## Sessions

- Use revocable server-side sessions.
- Browser holds only an opaque high-entropy session cookie.
- Production cookie properties: `Secure`, `HttpOnly`, reviewed `SameSite`, narrow host/path scope.
- Rotate session on authentication and privilege-sensitive transitions.
- Support current-device logout and revoke-all-sessions.
- Never store auth/session/refresh credentials in browser Web Storage.

## Tenant authorization

- Resolve tenant from session on the server.
- Never authorize from a request-supplied `tenant_id` or `user_id` alone.
- Keep application authorization and database-enforced tenant isolation as independent controls.
- Carry tenant scope through jobs, cache keys, AI/RAG retrieval, exports, backups and notifications.
- Cross-tenant negative tests are mandatory before public activation.

## Broker credentials

- Normal provisioning is authenticated Web Settings only.
- Credentials are submitted once and are never readable again from the UI.
- READ and TRADE are separate roles.
- A broad token may discover several broker accounts; create verified per-account bindings.
- A TRADE token enables an account only when the same broker identity is already present in the tenant's verified READ set.
- Never use TRADE as a READ fallback.
- No transfer/withdrawal authority.
- Cortex, CI runner, updater and unrelated tenants cannot read raw broker credentials.

## Activation

Keep public multi-user registration disabled until external Web security, tenant isolation, abuse/rate-limit, broker-terms and Russian-law production gates are green.
