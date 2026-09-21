# PR575: allocation revision provenance / secret-scan repair

Failure-learning evidence for the existing RU-PG-B repair, not an activation,
allocation approval, current-program ledger or completed live integration.

## Observed failure and source classification

Windows CI #2975, run 35532651003, job 106135904411, rejected three
`Hex High Entropy String` findings on reviewed head
`85b8e1d7aade36da72b439f4de9a21f113ae2ed6`:

- allocation contract line 6: historical source-base revision;
- allocation protocol tests lines 13 and 14: MAIN / OTHER revision fixtures.

Both revisions were verified as Git commit identities, not provider credentials.
The original base is the accepted PR574 squash commit; the other fixture copied
an earlier accepted main. This classification does not make a failed scan GREEN.

The same Windows run passed Ruff, mypy, 3574 tests / 737 subtests, the configured
protected-runtime coverage threshold, dependency audit and SAST before stopping
at the scan. Those results are historical and do not certify replacement bytes.

## Root cause and blast radius

The new tests need valid distinct source revisions, not live repository values.
Copying real high-entropy revision literals into fixtures unnecessarily couples
unit tests to repository history and collides with the entropy detector. The
contract does need exact historical provenance, but did not validate that field.

Inspect the contract producer and validator, fixture consumers, private plan
checksums, approval/source-drift negatives, journal/approval adapter test imports,
and the unchanged security-baseline report consumer. The earlier preflight did
not run the pinned detector; runtime tests and syntax checks did not cover this
source-representation constraint.

## Coherent correction

Keep the original base in five ordered eight-hex `source_base_sha_parts`, following
the existing known-revision representation. The source guard reconstructs it,
requires the exact known revision, rejects malformed/missing/dual encodings, and
does not reinterpret historical provenance as mutable current-main authority.

Use explicitly synthetic, valid and distinct revisions in MAIN / OTHER fixtures.
The source-drift, wrong-approval, private-digest and replay tests remain unchanged.
No existing test body or production allocation function is removed or weakened.

Add regression coverage for exact reconstruction; missing/legacy/dual/malformed
parts; case, whitespace, Unicode, ordering and valid-but-wrong revision drift;
fixture independence; and unchanged live-authority refusal. Direct tests using
the existing pinned HexHighEntropyString detector keep its default limit, require
clean corrected source, and require a full revision plus generated high-entropy
negative sample to remain detectable. Generated samples are not credentials.

No change is made to detect-secrets settings, thresholds, exclusions, baseline,
allowlists, report handling, dependency locks or workflow permissions. This is
not a generic technique for concealing credentials: only a verified, non-secret
Git revision is represented as structured provenance. Actual private values still
belong outside source and are never made acceptable by splitting them.

## Executed preflight and limits

The local copies of the three original changed files and the reused allocation
protocol/custody modules were verified against their exact Git blob identities.
All 63 selected protocol and provenance tests pass on Python 3.13.5; Python 3.12
grammar/compilation passes. Fixture replacement leaves the rest of the test AST
unchanged, and the reconstructed contract base equals the original scalar value.

Local pinned Ruff, mypy and detect-secrets are unavailable. DNS/download attempts
failed; no alternate version or home-made scanner is certified equivalent. The
two added detector tests, full native Windows execution, full repository baseline
and exact-head security scan require the existing authoritative CI. Their result
must be recorded against the replacement head before M1 certification or M2 work.

## Remaining boundary

This batch addresses the source/native-custody checkpoint only. The actual legacy
IPv4 remains unallocated. Do not merge the unfinished integration, rerun the paid
transport workflow, create/delete an address or invent OWNER approval. The same
PR must still implement and certify the real Timeweb adapter and protected
PLAN / APPLY / RECONCILE workflow after M1 passes all applicable gates.

Primary detector reference:
https://github.com/Yelp/detect-secrets/blob/v1.5.0/detect_secrets/plugins/high_entropy_strings.py

## M2 pre-publication integration findings

The M2 full-diff review found two adjacent defect classes before any live
allocation was authorized.

First, canonical cluster-shape validation compared the provider CPU field with
the integer target using ordinary Python equality. A boolean true or integral
numeric lookalike can compare equal to integer 1, so the live adapter now uses an
exact positive-integer validator for CPU and RAM. Regression coverage exercises
boolean and fractional CPU values. This strengthens provider-shape evidence and
does not broaden accepted provider state.

Second, the first operational workflow draft placed workflow_dispatch plan,
approval-comment and confirmation expressions directly inside Windows command
lines. Those values are authority inputs and must not become shell syntax on the
trusted self-hosted runner. The workflow now transfers them only as process
environment values; the Python parser reads and validates them without shell
expansion. The contract and source guard explicitly require environment-only
dispatch transport and reject direct shell interpolation.

The initial M2 source guard checked mode separation, permissions, secret scope,
provider methods and safe summaries but did not encode this shell-input boundary.
That gap is now a regression property. The blast radius is limited to the new M2
workflow source; M1 protocol/journal/OWNER evidence, the existing Timeweb
network/TLS workflow, production DSN and provider resources were not changed by
the review.

These findings were corrected before any M2 workflow could be run from protected
main. They are not live provider evidence and do not authorize allocation.
Exact-head canonical CI, secret scan, Sonar and review still decide whether the
replacement M2 source can advance.

