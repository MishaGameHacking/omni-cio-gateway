# Legal publication source

Current user-facing legal documents are published directly from:

- `web/legal/privacy.html`;
- `web/legal/consent.html`;
- `web/legal/terms.html`.

Version: `2026-10-02-v3`.

The personal-data consent is intentionally separate from the terms and privacy
policy. Production registration must fail closed unless all of the following are
versioned and satisfied:

- current legal versions;
- a positive server-side `REGISTRATION_MAX_USERS`;
- reviewed multi-user legal approval;
- confirmed personal-data operator/regulatory readiness;
- complete operator name and contact email for the rendered legal pages;
- VK ID configuration and successful end-to-end deployment verification.

Operator identity/contact values are deployment configuration and must not be
guessed. The operator address required for a regulatory notification is handled
through that filing and is not duplicated on the public website unless there is
a separate legal reason to publish it. The public pages are rendered during deployment and the
deployer rejects unresolved placeholders.

Do not store passport details, scans, secret keys, API tokens or other sensitive
identity material in Git.
