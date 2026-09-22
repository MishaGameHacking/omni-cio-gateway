# V10 Engineering Failure Learning Ledger — FL166

## Scope

Reusable defect class: protected Windows CI cannot establish TLS trust to the
official T-Bank Python package index.

The defect was reproduced on TW-B PR #584 exact head
`ecaab689f872d2547af1f26e43e744fd53e575f6` in WP20 Research Dossier Audit
#2288 / run `35770674981`, job `106891291518`.

This focused repair is a dependency/security machine-boundary split from TW-B.
It does not authorize TW-C, Timeweb provider mutation, Telegram public
activation, broker write or Real-money execution.

## Failure evidence

The dependency install repeatedly reached
`https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple/` and
failed with Windows `SSLCertVerificationError` reporting an untrusted root.
After the TLS failures pip emitted `No matching distribution found for
t-tech-investments==1.49.3`.

The selected dependency version and hashes were unchanged. The same failure
class appeared across multiple Windows jobs because the canonical lock carries
the official T-Bank package index as an additional resolver source.

## Root cause

The persistent self-hosted Windows runner did not have a usable Russian Trusted
Root CA + Russian Trusted Sub CA trust chain for the package-index TLS path.

T-Bank documents that its affected TLS endpoints require these two MinDigital
certificates and that Windows services use the LocalMachine Root and
Intermediate CA stores. The repository previously assumed this machine
precondition but did not model, verify or recover it.

The global extra-index configuration amplifies the visible blast radius because
pip can query the additional index while resolving unrelated public packages.
That is not a reason to disable certificate validation or substitute an
unrelated public SDK package.

## Blast radius

Without a permanent machine-trust boundary:

- authoritative Self-Hosted Windows CI can stop before static quality/tests;
- WP13–WP22A audits that install the canonical lock can fail at the same
  dependency step;
- repeated pip retries obscure one common trust failure as many package lookup
  failures;
- blind reruns cannot repair persistent machine trust;
- disabling TLS or changing package source would create a supply-chain security
  regression.

## Correction

1. Add a machine-readable T-Bank CA trust contract.
2. Add an OWNER/Admin-only, local-file provisioner that never downloads
   certificates and never disables TLS. Pin the long-lived root by DER SHA-256,
   and require every supplied/current intermediate to cryptographically chain
   to that pinned root.
3. Add a read-only verifier that first proves the LocalMachine CA presence and
   then uses pip itself for a bounded package-index TLS probe.
4. Run that verifier before the authoritative dependency installation so the
   failure is immediate and classified.
5. Add regression tests forbidding TLS bypasses and proving the verifier remains
   before dependency installation.
6. Document exact OWNER recovery and same-SHA CI rerun semantics.

## Security and authority invariants preserved

- no real credential, broker token, GitHub token or machine identifier is
  written to source/evidence;
- CI runner receives no certificate-store mutation authority;
- OWNER/Admin mutation is explicit and idempotent;
- matching certificate names alone are insufficient mutation authority: the
  root fingerprint is pinned and the intermediate chain is verified;
- dependency versions/hashes and T-Bank package-source authority are unchanged;
- certificate and hostname verification remain enabled;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`;
- broker write remains OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`.

## Acceptance

This repair is not GREEN merely because the source exists. The exact repair head
must pass source/governance checks, OWNER must establish the required machine
trust through the reviewed boundary, the same exact head must then pass every
applicable GitHub-native check, and the squash-merged exact new main must pass
post-merge Regression Shield.
