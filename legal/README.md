# Legal publication source

Current user-facing legal documents are published directly from:

- `web/legal/privacy.html`;
- `web/legal/consent.html`;
- `web/legal/terms.html`.

Version: `2026-09-30`.

The personal-data consent is intentionally separate from the terms and privacy
policy. Production registration must remain fail-closed until all operational
gates are satisfied: current legal versions, SMS provider token + sender,
required Roskomnadzor/operator formalities, and successful end-to-end SMS test.

Do not store passport details, scans, or other identity-document data in Git.
Only the operator details intentionally published in the legal pages belong in
the repository.
