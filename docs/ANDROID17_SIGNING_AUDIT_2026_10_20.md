# Android 17 APK signing audit — 20 October 2026

Work continues only in existing `codex/spectrum-3d-100` / PR #880.
Starting head: e8e4a939ac9cec10d447440fcf3a0f2539fcb813.
No new branch, production deployment, key replacement or APK publication.
The intended physical device is Samsung Galaxy S25 Ultra / Android17.

## Observations, not assumptions about the key

Android CI #661, run 39396139876, job 118539579705 passed SDK37,
unit tests, lint, all app assemblies and exact-head Sonar, then stopped before
emulator startup with `Signing certificate changed`. The old regular expression
recognized only `Signer #N`. The actual public fingerprint was not logged.
The official CLI source also has SDK-range labels, so an empty parse was not
proof that the installed signing key changed.

Commit 641ecdf added a bounded parser for both documented CLI forms and 21
regressions. Those tests passed in Android CI #662. However the full run
39400568706 / job 118553947238 still failed at 09:36:57 UTC:
`Missing or excessive signer certificate records`. Its report did confirm
successful verification, one signer and v2, but neither certificate text form
was found. Actual output was redirected and not retained. Consequently the
specific format/cause and the actual key identity are still UNPROVEN.

#662 passed 678 script test methods with 3 skips, build/lint (154 tasks),
canonical 3D asset and native alignment checks. It did NOT run emulators.
Backend #429 / 39400568733 passed 1441 tests, 2 skips, 1382 subtests,
284-source syntax audit, health/OpenAPI and exact-head zero-issue Sonar.
One existing Starlette/AnyIO warning remains. This was not a green Android run.

## Replacement: verify bytes through the official public library

The CLI text parser and its prose-format tests are now replaced rather than
extended with guessed formats. `VerifyApkSigning.java` uses public
`com.android.apksig.ApkVerifier` from the same pinned Build Tools 37.0.0 JAR.
It requires isVerified(), a single X509 signer and the UNCHANGED certificate
pin for every verified signer and any signing lineage. It verifies the actual
APK bytes and binds the result to their SHA-256 and size before/after inspection.
No reflection, private Android API, trust in a source stamp, or key lookup.

The API37 verification runs independently of v2 format verification: current
platform verification can intentionally skip a v2 block in a v3-signed APK.
A separate public verifier checks that existing v2 requirement using its
signature-format interval. This is NOT an old-OS installation test and does not
lower manifest min/target37 or restore any runtime support below Android17.

`apk_signing_identity.py` invokes this fixed helper with the SDK JAR/JDK using
an argument list, no shell, no network, no automatic retry. Its bounded JSON
contract rejects duplicate fields, coercion, mismatched APK/hash/key, absent
fields and additional data. Failures expose at most fixed diagnostics and a
PUBLIC certificate fingerprint, never a DN, keystore, password or key.
The original CLI crypto verification, zipalign, native checks and BOTH actual
API37 4KB/16KB emulator acceptance profiles are still mandatory. No gate is
skipped or replaced by a unit test.

## Validation scope of this follow-up

Nine machine-protocol unittest methods passed locally. The helper compiles
with `javac --release 17` against a local API-shape stub; that ONLY checks Java
syntax, not the real SDK API nor cryptographic validity.

An additional mandatory Android-CI smoke creates a temporary no-code API37 APK
and ephemeral test-only key using official aapt2/keytool/apksigner. It exercises
the REAL helper/JAR for correct identity, wrong key, unsigned APK and changed
signed bytes. It runs before the expensive app build, fails (not skips) when
GitHub Actions lacks its configured SDK/JDK, and never uses the installed
application's key. It is skipped locally because the SDK is absent. The stub
is NOT committed and cannot substitute for this real CI smoke.

Final-head CI and emulator outcome must be recorded separately. This change
alone does not prove that the app certificate matches, that all workflows are
green, or that an APK has passed mobile acceptance.

## Primary contracts

- ApkVerifier Result, public Builder and signature selection:
  https://android.googlesource.com/platform/tools/apksig/+/refs/heads/main/src/main/java/com/android/apksig/ApkVerifier.java
- Public certificate lineage:
  https://android.googlesource.com/platform/tools/apksig/+/refs/heads/main/src/main/java/com/android/apksig/SigningCertificateLineage.java
- Official CLI, for comparison only (no parsing dependency):
  https://developer.android.com/tools/apksigner
