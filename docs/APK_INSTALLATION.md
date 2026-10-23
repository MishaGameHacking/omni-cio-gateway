# Analyst AI — APK installation and verification

## Current candidate: 0.11.0-preview / 35

The owner's clarification of 19–20 October 2026 sets the current development
contract to **Android 17 / API 37**, with `minSdk = compileSdk = targetSdk = 37`.
Both measured **4096-byte and 16384-byte** API37 x86_64 profiles require their own
installation, upgrade, launch and full UI checks tied to the candidate's bytes.
See [AGENTS](../AGENTS.md#android) and [PLAN_STATUS](PLAN_STATUS.md).
A verified new APK release is not established by this document.

The preserved instructions, API35/36 matrices and release gates below describe
the historical **0.10.0 / 34 baseline as of 17 October 2026**. They do not set
the current candidate's supported OS or replace its API37 acceptance checks.

## Historical published release: 0.10.0-preview / 34

Updated 2026-10-17 for F01.4 / F22. The published preview supports **Android 15 / API 35 and newer**. Android 14 / API 34 and older are outside the current device baseline.

| Property | Published value |
| --- | --- |
| Version | `0.10.0-preview` / `versionCode 34` |
| Application ID | `ru.omnicio.app.debug` |
| SDK configuration | `minSdk = 35`, `compileSdk = 36`, `targetSdk = 36` |
| APK size | `4347764` bytes |
| APK SHA-256 | `3a31c602ec885a0d8cac8d76f43369cfb6ed3bdaa928f1cd7429582b0d5a40a3` |
| Signing | Existing preview certificate pinned in [the repository](../.github/apk-signing-certificate.sha256) |
| Build type | Signed, non-debuggable preview with release shrinking; existing test signing key |

Download the APK from the [published GitHub Release](https://github.com/MishaGameHacking/omni-cio-gateway/releases/tag/android-preview-0a894dddfa858efe6c7be60aea78935adec84c1b), or use the in-app update channel after its delivery is confirmed in [PLAN_STATUS](PLAN_STATUS.md). The release includes `apk-verification.json` for the exact published bytes. See [the release notes](releases/0.10.0.md) for the user-facing changes.

For a routine update, install over the existing `ru.omnicio.app.debug` preview and complete Android's installation confirmation. Preserve the installed app and its data; removing the app is not a prerequisite for updating. The preview remains a test-key build for the approved private installation, not a production-store release.

### Verified installation matrix for 0.10.0

The [Android APK run 39042091615](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39042091615) completed the release checks:

| Environment | Verified scenario |
| --- | --- |
| Android 15 / API 35 emulator | Published preview: clean installation and launch |
| Android 16 / API 36 emulator | Published preview: clean installation and launch; upgrade from the published `0.9.0-preview / 33` and post-upgrade launch |
| Android 15 / API 35 and Android 16 / API 36 emulators | Separate debug fixture: UI checks |
| Physical phone | Separate acceptance; the emulator results do not confirm installation on the owner's phone |

The debug fixture is built from the same candidate commit. Its UI test Activity and synthetic data are not included in the published preview. The preview APK hash binds the installation and launch evidence; the UI fixture is recorded separately.

The 0.9.0 APK required API 36. It cannot be used as an installed upgrade baseline on API 35; the Android 15 result for this release is a clean installation. Future functional releases must use the currently published preview as their upgrade reference.

### Current release gates

- Check the exact preview APK: package, version, SDK levels, non-debuggable/non-testOnly state, pinned signature, archive/DEX integrity, ZIP alignment and any bundled 64-bit native ELF libraries.
- Run lint, builds and the applicable source/backend/quality checks for the candidate commit.
- Verify installation and launch of the exact preview on API 35 and API 36; verify upgrade from the applicable published reference without downgrade or forced test-install flags.
- Verify UI in the separate debug fixture from the same candidate commit on API 35 and API 36.
- Read the APK back after uploading and compare SHA-256 and size before publishing.
- Deliver the **same published bytes** to Timeweb, then verify the public manifest, package, version, HTTPS download, size and SHA-256. GitHub publication and update-channel delivery are separate evidence.
- Record release, channel and physical-device evidence separately in [PLAN_STATUS](PLAN_STATUS.md). A documentation-only update does not create a new APK version.

These gates are implemented by [Android APK](../.github/workflows/android-apk.yml), [Android CI](../.github/workflows/android-ci.yml) and the [APK verification action](../.github/actions/check-apk/action.yml). The workflow's reference APK must be deliberately advanced when preparing the next functional release.

The platform baseline follows the owner's 2026-10-17 decision. `minSdk` sets the installation floor; `targetSdk` selects platform behavior. The latter does not remove API 35 support. Official references: [SDK configuration](https://developer.android.com/build), [Android 15 behavior](https://developer.android.com/about/versions/15/behavior-changes-15), [Android 16 behavior](https://developer.android.com/about/versions/16/behavior-changes-16), [16 KB pages](https://developer.android.com/guide/practices/page-sizes).

## Historical incident — 2026-10-12

The archived investigation below describes APKs 0.3.0–0.4.2 and the checks used then. Its API 33 results are historical evidence; the current support and verification matrix is above.

### Observed report

The user could not install `Analyst-AI-debug-0cbb7ee.apk` (0.4.1), even after
uninstalling the previous app. The Samsung package installer displayed only
"Application not installed", without an INSTALL_FAILED code.

### Verified original artifacts

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

### Distribution changes in 0.4.2

A compact, non-debuggable `preview` variant is built from release settings and
signed with the EXISTING test key. It preserves `ru.omnicio.app.debug` and minSdk 33,
uses versionCode 20, excludes debug-only Compose tooling, and enables R8 shrinking.
It is still a test-key preview, not a production-store release.

Publication of 0.4.2 required:

- archive, DEX checksums/header compatibility and 64-bit ELF 16 KB checks;
- the pinned existing signing certificate, valid v2 signature and ZIP alignment;
- correct application ID, versionCode, minSdk/targetSdk, no testOnly/debuggable flag;
- actual clean installation and launch on disposable Android 13 and 16 emulators;
- PR validation also checks upgrade from the known 0.4.1 artifact;
- SHA-256 read-back comparison after upload and before publishing the release.

The published `apk-verification.json` contains actual results for the specific APK.
No fabricated checks, forced installation flags, key rotation or package-ID change
are used. A failed check stops publication. Sonar rules and quality gate are unchanged.

## When a phone refuses installation

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

During the historical investigation, Android CLI documented its Windows emulator
command as disabled; the Windows CI harness used SDK avdmanager/emulator tools directly.
