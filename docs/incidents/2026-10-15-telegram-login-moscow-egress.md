# Telegram login incident — Moscow backend egress

Date: 2026-10-15

## User-visible symptom

Android successfully opened the Telegram confirmation flow, but the callback returned
`analystai://auth?error=telegram_unavailable`. The application displayed
“Telegram временно недоступен. Попробуйте позже.”

The Android phone and its internet connection were not the failing link. The callback
reached the Analyst AI backend and failed only when the backend tried to contact
Telegram from the Moscow server.

## Exact production evidence

Read-only diagnostics ran against the already verified Timeweb server:

- server ID: `9334503`;
- public IPv4: `176.98.178.81`;
- public host: `176.98.178.81.sslip.io`;
- systemd service: `analyst-ai-backend` (active);
- configured callback: `https://176.98.178.81.sslip.io/auth/telegram/callback`;
- Android deep link: `analystai://auth`.

The server resolved `oauth.telegram.org`, but could not establish a connection:

- Telegram IPv4 `149.154.167.99:443`: connection timeout;
- Telegram IPv6 `2001:67c:4e8:f004::9:443`: `ENETUNREACH` (`errno 101`);
- control destination `api.github.com:443`: IPv4 and IPv6 connected successfully and
  negotiated TLS 1.3.

The production journal recorded the matching callback failure as
`httpx.ConnectError: [Errno 113] No route to host` while posting the authorization
code to `https://oauth.telegram.org/token`.

This isolates the incident to destination-specific egress from the Moscow host to
Telegram OIDC. It is not a general DNS failure, a general HTTPS outage, an Android
network problem, or an invalid local session.

## Repair design

The repair uses Telegram’s official browser Login library on the user’s browser,
where Telegram is reachable. The library returns a signed OIDC `id_token` to the
Analyst AI origin. The backend then validates that token locally against a
release-pinned Telegram RS256 public key and checks:

- signature and signing-key ID;
- issuer `https://oauth.telegram.org`;
- audience equal to the BotFather Client ID;
- expiration and issued-at time;
- the server-generated one-time nonce;
- the one-use Analyst AI login transaction.

The browser’s decoded `user` object is never trusted. Unknown or rotated signing
keys fail closed. After validation, the existing one-time `analystai://auth` code and
Android `/auth/session` exchange remain unchanged, so the installed APK does not need
a protocol change.

## Deployment and rollback boundary

Production must load `telegram_browser_app:app` instead of the legacy `app:app` entry
point. Deployment is restricted to the exact existing Moscow server, preserves the
backend environment, SQLite database and release artifacts, and must pass local and
public health/login-page checks. Any failed check restores the previous backend and
systemd unit before the job exits.

## Remaining external configuration check

BotFather Login Widget settings must include both the Analyst AI website origin
`https://176.98.178.81.sslip.io` and the callback URL
`https://176.98.178.81.sslip.io/auth/telegram/callback`. Telegram only processes
logins from pre-registered allowed URLs.
