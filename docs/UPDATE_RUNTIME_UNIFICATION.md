# One update runtime: integration of #832 into Spectrum #833

This document records the integration contract. It is **not** evidence that an APK has been published, that the backend has been deployed, or that a physical phone has completed a self-update.

## Canonical runtime

- One `MandatoryUpdateHost` owns version policy, download, verification, permission handling, installer handoff and post-install version recovery. Spectrum supplies presentation only; it does not start a second updater.
- One transport contract is used: `/client/update-policy`, `/client/ready`, `/client/apk/...`, `X-Analyst-Version-Code` and `X-Analyst-Package`.
- The guarded native installer, typed release metadata, bounded checksummed stream and authenticated server pause/resume from #832 are retained.
- The former `AppRelease` / `AppUpdateClient` / `AppUpdateVerifier` / `AppUpdateInstaller` / `UpdateCheckStore` runtime is removed. `UpdateFlow` remains pure state-machine research and performs no network or install work.
- `BootstrapActivity` is a routing-only exported launcher. It forwards only the documented `analystai://auth` URI to private `MainActivity`; arbitrary external extras are not forwarded.
- Existing Telegram code exchange and encrypted session storage, five tabs, education entry, theme preference, package identity, signing certificate and version-code continuity are preserved.
- Spectrum update rendering respects safe drawing insets, scrolling, minimum touch targets and the persisted motion preference. Android installation consent is never bypassed or described as silent.

## Release tooling boundary

The canonical client and backend use the `/client` release channel. The deprecated `/releases/current.json` publisher is intentionally fail-closed: `legacy_release_guard.py` stops it before release creation, SSH access or production publication whenever the canonical runtime is present. It must not be used as an alternate release path.

The main-branch APK workflow builds and verifies the compact signed preview APK. A verified APK and its verification report are retained as a GitHub Actions artifact for the repository owner. A source merge alone does not publish a GitHub Release and does not activate the mandatory-update channel.

## Merge criteria

Before #833 is merged, the exact head must satisfy all of the following without accepted or suppressed findings:

1. Backend tests and compilation succeed.
2. Android lint and debug, release and preview builds succeed.
3. Clean installation, upgrade from the installed 0.5.1 preview, launcher/auth routing and profile/education UI checks succeed on the configured Android 16 emulators.
4. SonarQube Cloud reports no new issue, accepted issue, security hotspot or annotation.
5. The branch contains the real post-#832 history and no unresolved review thread.

After the merge, the same main-branch backend and APK workflows must pass again before the resulting APK is presented as the build from `main`.

## Operational boundaries

- `ANDROID_UPDATES_ENABLED` remains disabled until an updater-capable bootstrap APK is deliberately distributed and the server release channel is staged and verified end to end.
- The installed 0.5.1 preview has no updater and therefore needs one manual bootstrap upgrade.
- Android may require permission for the installation source, explicit installation consent, and a tap on **Open** after replacement.
- Emulator installation and upgrade checks do not reproduce every OEM behavior and do not prove installation on a physical Samsung or other phone.
- Version headers are compatibility claims, not authentication or cryptographic device attestation.
- Portfolio and risk outputs remain source-bound and read-only; no broker order, fabricated quote, rating, forecast or probability is introduced by this integration.
