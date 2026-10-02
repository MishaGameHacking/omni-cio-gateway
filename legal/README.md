# Legal publication source

Current user-facing legal documents are published directly from:

- `web/legal/privacy.html`;
- `web/legal/consent.html`;
- `web/legal/terms.html`.

Version: `2026-10-02-v5`.

The personal-data consent is intentionally separate from the terms and privacy
policy. Production registration must fail closed unless current legal versions,
a positive server-side `REGISTRATION_MAX_USERS`, reviewed multi-user legal
approval, operator identity/contact values, VK ID configuration and end-to-end
deployment verification are all present. Ordinary production also requires
confirmed personal-data operator/regulatory readiness. The temporary
owner-approved `CONTROLLED_LIVE_TEST_MODE` is the only exception: it must keep
`RKN_NOTIFICATION_CONFIRMED=false` and is hard-capped at two user accounts.

Operator identity/contact values are deployment configuration and must not be
guessed. The operator address required for a regulatory notification is handled
through that filing and is not duplicated on the public website unless there is
a separate legal reason to publish it. The public pages are rendered during deployment and the
deployer rejects unresolved placeholders.

Do not store passport details, scans, secret keys, API tokens or other sensitive
identity material in Git.
