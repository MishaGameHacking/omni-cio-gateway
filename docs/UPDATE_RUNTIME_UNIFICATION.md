# One update runtime

Source review: **2026-10-17**. The unified runtime introduced by #832/#833 is
integrated in the current app. This document describes that implementation and
preserves its historical merge criteria below. Current APK publication, Moscow
delivery and open physical-device checks are recorded in
[PLAN_STATUS.md](PLAN_STATUS.md); the old source-merge note is not a current
release status.

## Canonical runtime

- One `MandatoryUpdateHost` owns version policy, download, verification, permission handling, installer handoff and post-install version recovery. Spectrum supplies presentation only; it does not start a second updater.
- One transport contract is used: `/client/update-policy`, `/client/ready`, `/client/apk/...`, `X-Analyst-Version-Code` and `X-Analyst-Package`.
- The guarded native installer, typed release metadata, bounded checksummed stream and authenticated client compatibility checks from #832 are retained. As of F11.1, server portfolio monitoring is independent of Android sessions and APK versions; it is bound to the broker connection instead.
- The former `AppRelease` / `AppUpdateClient` / `AppUpdateVerifier` / `AppUpdateInstaller` / `UpdateCheckStore` runtime is removed. `UpdateFlow` remains pure state-machine research and performs no network or install work.
- `BootstrapActivity` is a routing-only exported launcher. It forwards only the documented `analystai://auth` URI to private `MainActivity`; arbitrary external extras are not forwarded.
- Existing Telegram code exchange and encrypted session storage, the five Workspace tabs (**«Капитал», «Портфель», «Действия», «Риски», «Профиль»**), education entry, appearance preferences, package identity, signing certificate and version-code continuity are preserved.
- Spectrum update rendering respects safe drawing insets, scrolling, minimum touch targets and the persisted motion preference. Android installation consent is never bypassed or described as silent.

## Release tooling boundary

The canonical client and backend use the `/client` release channel. The deprecated `/releases/current.json` publisher is intentionally fail-closed: `legacy_release_guard.py` stops it before release creation, SSH access or production publication whenever the canonical runtime is present. It must not be used as an alternate release path.

The main-branch [Android APK workflow](../.github/workflows/android-apk.yml)
builds and verifies the signed preview APK. GitHub Release publication is an
explicit main operation: manual workflow dispatch or the `[publish-apk]` commit
marker with matching path filters. Actions artifact retention is separate from
Release publication; a source merge alone does not activate the Timeweb channel.

The current release line supports Android 15+ (minSdk 35, compile/target 36).
For 0.10.0 / 34, CI verifies clean installation and launch of the published
preview on API 35 and 36, plus upgrade from the published 0.9.0 / 33 and
post-upgrade launch on API 36. UI is checked in a separate debug fixture from
the same commit on both APIs; its test Activity is absent from the preview.
The previous APK requires API 36, so the API 35 preview check is a clean install. Use
[APK_INSTALLATION.md](APK_INSTALLATION.md) for the complete verification contract.

The [Moscow channel workflow](../.github/workflows/repair-moscow-update-channel.yml)
delivers the pinned, already published APK and report. Use it to deliver the
same 0.10.0 / 34 bytes; do not rebuild changed bytes under that versionCode.
It also replaces backend code from the checked-out commit. Its backup and
rollback cover backend/environment, not automatic restoration of `current.json`;
public read-back runs after the remote rollback trap has ended. The precise
operational boundary is documented in
[UPDATES_AND_PORTFOLIO_RESEARCH.md](UPDATES_AND_PORTFOLIO_RESEARCH.md#штатная-доставка-уже-опубликованного-apk-на-timeweb).

## Historical merge criteria for #833

These are the recorded criteria for the original integration, including its
0.5.1 baseline. They do not replace the current matrix above or the current
[repository rules](../AGENTS.md). The original requirement read:

Before #833 is merged, the exact head must satisfy all of the following without accepted or suppressed findings:

1. Backend tests and compilation succeed.
2. Android lint and debug, release and preview builds succeed.
3. Clean installation, upgrade from the installed 0.5.1 preview, launcher/auth routing and profile/education UI checks succeed on the configured Android 16 emulators.
4. SonarQube Cloud reports no new issue, accepted issue, security hotspot or annotation.
5. The branch contains the real post-#832 history and no unresolved review thread.

The original integration also required the same main-branch backend and APK
workflows to pass again after merge before presenting the resulting APK as a
build from `main`. Later release evidence belongs in the progress register.

## Operational boundaries

- `ANDROID_UPDATES_ENABLED` controls protected backend API compatibility. Its disabled state does not disable Android's `MandatoryUpdateHost`, which still requires a usable public policy. Server enforcement has its own verified rollout conditions; publishing an APK requires a matching usable channel regardless of that flag.
- Historical 0.5.1 and older clients have no updater and need one manual bootstrap upgrade. This is a legacy compatibility limitation, not the current release baseline.
- Android may require permission for the installation source, explicit installation consent, and a tap on **Open** after replacement.
- Emulator installation and upgrade checks do not reproduce every OEM behavior and do not prove installation on a physical Samsung or other phone.
- Version headers are compatibility claims, not authentication or cryptographic device attestation.
- Portfolio and risk outputs remain source-bound and read-only; no broker order, fabricated quote, rating, forecast or probability is introduced by this integration.
- The ordinary `timeweb-backend.yml` remains paused after the Moscow cutover. Success in a dedicated Moscow workflow does not re-enable that old deployment path.

Implementation: [MandatoryUpdateHost](../app/src/main/java/ru/omnicio/app/ui/updates/MandatoryUpdateHost.kt),
[client policy](../backend/client_updates.py), [publication library](../backend/release_publication.py),
[CI installation evidence](../backend/installation_evidence.py).
