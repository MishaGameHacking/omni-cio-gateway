# APK installation incident — 2026-10-12

## Observed report

The user could not install `Analyst-AI-debug-0cbb7ee.apk` (0.4.1), even after
uninstalling the previous app. The Samsung package installer displayed only
"Application not installed", without an INSTALL_FAILED code.

## Verified original artifacts

We downloaded the original GitHub release bytes, not locally rebuilt substitutes:

- 0.3.0 / versionCode 17: SHA-256
  `187778fc95b7ecceacb82ee7c5ec5fb48b62a7d7e925c565bb7d09acb0be4b7e`.
- 0.4.1 / versionCode 19: SHA-256
  `9c45e7600edb8c9044b933ada9ba896595eff5c44fdf93382684456c99b4c009`.
- Both have application ID `ru.omnicio.app.debug`, minSdk 33, targetSdk 36,
  valid APK v2 signatures and the SAME signing certificate SHA-256:
  `bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1`.
- ZIP CRC, absence of duplicate entries, uncompressed/aligned resources and
  `zipalign -c -P 16 4` checks passed. Both include arm64-v8a, armeabi-v7a,
  x86 and x86_64 native libraries. Neither has testOnly=true or requires split APKs.
- Static audit: Actions run 38298187227, job 114974293122.

On a disposable Android 13/API 33 x86_64 emulator, the EXACT original artifacts
passed all of the following without `adb install -t`, downgrade or protection bypass:

1. Clean installation of 0.3.0.
2. Upgrade from 0.3.0 to 0.4.1.
3. Uninstall inside that disposable emulator, then clean installation of 0.4.1.
4. Launch of MainActivity (`Status: ok`) and a running process after eight seconds.

Installation audit: Actions run 38298412827, job 114975059482,
completed successfully at 2026-10-12 19:38 UTC.

This does NOT identify the user's Samsung-specific root cause. Do not claim that
signature mismatch, malformed APK, missing v3 signature, or debug mode was proven
to cause the reported failure. Installation through a physical phone's file manager
and firmware protections is not equivalent to an emulator ADB installation.

## Distribution changes in 0.4.2

A compact, non-debuggable `preview` variant is built from release settings and
signed with the EXISTING test key. It preserves `ru.omnicio.app.debug` and minSdk 33,
uses versionCode 20, excludes debug-only Compose tooling, and enables R8 shrinking.
It is still a test-key preview, not a production-store release.

Publication now requires:

- archive, DEX checksums/header compatibility and 64-bit ELF 16 KB checks;
- the pinned existing signing certificate, valid v2 signature and ZIP alignment;
- correct application ID, versionCode, minSdk/targetSdk, no testOnly/debuggable flag;
- actual clean installation and launch on disposable Android 13 and 16 emulators;
- PR validation also checks upgrade from the known 0.4.1 artifact;
- SHA-256 read-back comparison after upload and before publishing the release.

The published `apk-verification.json` contains actual results for the specific APK.
No fabricated checks, forced installation flags, key rotation or package-ID change
are used. A failed check stops publication. Sonar rules and quality gate are unchanged.

## Still needed when a phone refuses installation

Obtain the exact device model, Android/One UI version, and ideally the package
manager's INSTALL_FAILED code. Check whether the downloaded APK hash matches the
published hash. A message about Auto Blocker or source permission is a separate
policy issue; do not recommend disabling Play Protect or resetting user data blindly.

Official references:
- https://developer.android.com/tools/apksigner
- https://developer.android.com/tools/zipalign
- https://developer.android.com/tools/adb
- https://developer.android.com/guide/practices/page-sizes
- https://source.android.com/docs/core/runtime/dex-format
- https://developer.android.com/tools/agents/android-cli#known-issues

Android CLI currently documents its Windows emulator command as disabled; the
Windows CI harness therefore uses the SDK avdmanager/emulator tools directly.
