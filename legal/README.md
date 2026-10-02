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
- complete operator name, address and contact email for the rendered legal pages;
- VK ID configuration and successful end-to-end deployment verification.

Operator identity/contact values are deployment configuration because they may
contain personal contact data that must not be guessed or committed without an
explicit decision. The public pages are rendered during deployment and the
deployer rejects unresolved placeholders.

Do not store passport details, scans, secret keys, API tokens or other sensitive
identity material in Git.
