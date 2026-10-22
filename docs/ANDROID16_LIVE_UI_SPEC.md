# Analyst AI: native UI specification

## Current platform contract

The owner's clarification of 19–20 October 2026 supersedes the older platform
requirements below: the **0.11.0 / 35 candidate requires Android 17 / API 37**,
with `minSdk = compileSdk = targetSdk = 37`. Both measured **4096-byte and
16384-byte** API37 x86_64 profiles require installation, upgrade, launch and
full UI checks tied to the candidate's bytes. The authoritative contract is in
[AGENTS](../AGENTS.md#android); actual results remain in [PLAN_STATUS](PLAN_STATUS.md).
This specification does not establish a verified new APK release.

## Preserved specification — 17 October 2026

The body below retains the dated 3D100 specification, its historical API35/36
platform assumptions and the published **0.10.0 / 34** baseline. Those OS and
acceptance-matrix defaults are superseded by the current contract above;
historical evidence and implementation descriptions retain their original scope.

Current implementation contract for the **3D100 / 0.11.0 / 35 candidate**, updated 2026-10-17. The latest published baseline remains 0.10.0 / 34. [3D100](3D100.md) tracks source and verification for each requirement; this specification does not itself certify a release.

The owner's Android 15+ clarification supersedes the previous Android 16-only baseline. The filename is retained for existing links. Product scope and release evidence remain in [MASTER_PLAN](MASTER_PLAN.md) and [PLAN_STATUS](PLAN_STATUS.md); the current screen map is [WORKSPACE_UI](WORKSPACE_UI.md).

## Platform baseline

- `minSdk = 35`, `compileSdk = 36`, and `targetSdk = 36`. Android 14 / API 34 and older are unsupported.
- Use stable public Android 15+ APIs. Guard APIs introduced after API 35 by OS version when needed; increasing the target SDK must not silently raise the installation floor.
- Edge-to-edge cannot be opted out of on Android 16 when targeting API 36. Do not rely on the old opt-out attribute.
- Edge-to-edge is the default coordinate system. Screens consume `safeDrawing` and IME insets once and remain usable with gesture navigation, cutouts, and transparent system bars.
- Back navigation uses Activity/Compose predictive-back APIs. Do not intercept `KEYCODE_BACK` or restore legacy `onBackPressed()` handling.
- Layouts must remain usable on narrow phones, large fonts, split-screen, tablets, foldables, and large displays. Do not depend on orientation locks or a fixed aspect ratio.
- Motion state belongs to the shared Filament frame scheduler or `graphicsLayer`, so the full screen is not recomposed for each frame. Native text and input are composed independently of the meshes.

## Portfolio history and instrument candles in 3D100

- The **Портфель → Динамика** section, with an account selector, displays orthographic mesh columns derived from saved balance snapshots. This data is a date and portfolio value, not an instrument OHLC series.
- Each column uses the last observed balance in its interval. The interval is chosen from days, weeks, months or years according to the available history, using the Moscow timezone.
- Missing intervals remain empty; zero and very small balances have an explicit marker. The value scale includes zero and supports negative balances without decorative distortion.
- A tap, horizontal drag, or previous/next accessibility action selects an interval. The tooltip shows its dates and exact closing balance; reset returns to the full displayed period.
- Compact statistics show observed value change and minimum/maximum where multiple snapshots are available. One snapshot is usable immediately and explicitly lacks a comparison.
- Interval cash flows use the existing read-only analytics API after selection settles. Deposits, withdrawals, dividends and coupons are shown separately from other operations and retain their source currencies.
- Value change and cash flows are not labelled investment profit. Invalid or contradictory history and incomplete operations have explicit states; privacy mode hides the chart.
- Selection is keyed by the actual observation date, with linked table, range handles, exact-period requests, magnification and a clear gap state. A selected Z offset never changes bar height.
- Separate GetCandles data uses actual OHLC, completion and volume. Bond quotations are percentages of nominal and futures are points; they must not silently receive a money label. Calendar markers have source dates and do not assert causation.
- See [HistoryBars.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryBars.kt), [HistoryChart.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryChart.kt) and [AccountAnalytics.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AccountAnalytics.kt).

## Nine live visual families

The approved Spectrum reference defines these nine families:

1. Live charts.
2. Animated indicators.
3. Volumetric controls.
4. Materials and lighting.
5. Interactive AI assistant.
6. Smart notifications.
7. Personal recommendations.
8. Risk control.
9. World-market analysis.

They describe the visual vocabulary; completion of broader investment algorithms still needs its own evidence. Packaged, versioned GLB meshes render through Filament. Compose owns readable labels, accessibility nodes, hit targets, native selection and IME. In-app bitmaps, animated frame sequences or a WebView are not substitutes for these meshes.

Each family has a distinct motion language:

- charts update bars and points;
- indicators move a gauge or progress arc;
- spatial elements move actual geometry within bounded depth levels;
- RGB elements shift light across facets;
- the assistant changes pose only from real waiting, verification, ready or error state;
- notifications use a restrained bell/ripple response;
- recommendations converge on a target;
- risk control scans or pulses a shield;
- world markets rotate or orbit around a globe.

## Motion lifecycle and accessibility

### Home content — OWNER clarification, 2026-10-17

The Home screen must not render a showcase of implementation capabilities.
Remove the entire “Живые возможности” card, its technical subtitle, Android badge
and catalogue of animated tiles. The analyst card follows the two real shortcuts to assets and payments.
The nine native visual families remain available inside functional UI elements;
their existence does not require a separate user-facing catalogue. This replaces
the former catalogue-visibility requirement and its source test. Real navigation,
data integrity, lifecycle, accessibility, build and emulator gates still apply.

### Runtime behavior

- A decorative animation may run only while its composable is visible, its Activity is at least `STARTED`, the user has enabled **Оформление → Движение**, and Android animators are enabled.
- Selection and navigation effects are finite. A settled idle scene stops requesting frames; state-dependent loading can continue only while visible and in the foreground.
- Leaving a scene releases its nodes and cancels its frame demand. Backgrounding pauses rendering. Each native dialog has a SpatialWindow backed by the same Engine, and releases its surface on dismissal.
- Read animated values during draw or graphics-layer phases. Avoid recomposing a whole screen at frame rate.
- Limit simultaneous live elements within functional controls. A long scrolling list must not start dozens of independent loops; no separate capability showcase belongs on the dashboard.
- Every live icon keeps a visible text label and an accessibility description. Color or motion must never be the only carrier of financial meaning.
- Large-font layouts may stack content vertically instead of clipping or shrinking it below readable sizes.
- Field value, focus and UTF-16 selection are saved for recreation. Predictive-back cancellation restores the prior scene and state; completion performs exactly one navigation action.
- Motion settings are live/subdued/off, with system animator disable first. Public thermal and energy-save signals reduce frame rate, detail and lighting without changing source data or native interaction targets.

## Update journey

The mandatory update screen has its own native visual language:

- a restrained mesh background and status-specific lighting;
- a large volumetric warning mark when an update is required;
- readable installed/new version information;
- actual download/check progress only, never synthetic completion;
- explicit explanation of download, integrity verification, Android installation, and launch;
- unchanged server, signature, package, checksum, and system-installer security boundaries.

The animated background and warning symbol are presentation only. They must not download an APK, invoke PackageInstaller, unlock content, or bypass the shared update gate.

## Data integrity

Animation never invents portfolio values, ratings, returns, model activity, or recommendations. The Analyst AI avatar mood is derived only from real states such as waiting for a portfolio, verified data ready, or an actual warning/error.

## Verification

Every candidate must pass:

- source regressions forbidding bitmap/GIF/WebView substitutions;
- Android lint and all build variants;
- clean installation and launch of the exact preview APK on API 35 and API 36;
- UI checks in a separate debug fixture from the same candidate commit on API 35 and API 36;
- exact upgrade from the applicable currently published preview APK, preserving its package and signing identity;
- large-font and narrow-screen checks;
- actual frames showing shaded mesh silhouettes in dark and light themes, modal-window lifetime, idle stop and native controls;
- native input/caret restoration, real cancelled/completed predictive-back gestures, and observed system/thermal overrides;
- a measured long-scroll session reporting actions, wall time, frame statistics and process memory without claiming physical-device GPU/battery results;
- ELF LOAD/RELRO and ZIP alignment of the actual packaged JNI libraries;
- runtime API 35 on the official `google_apis_ps16k;x86_64` image with `getconf PAGE_SIZE = 16384`, plus API 36 with its observed kernel size recorded;
- Sonar/quality checks and backend tests applicable to the exact head.

The installation report for versionCode 35 and newer must contain the candidate
APK hash, exact emulator image, measured page size, installation/upgrade results
and UI evidence. A 16 KB linker flag, upstream compatibility claim or parser unit
test is insufficient runtime evidence. Upgrade uses the exact published 0.10.0 / 34
on both APIs. Test-only synthetic UI never enters the distributed preview.

Physical TalkBack experience, haptic feel, thermal comfort, all-day battery use and
frame timing on an actual phone remain separately labelled acceptance evidence.
Emulator observations must not be presented as those physical measurements.

For the published 0.10.0 APK, [run 39042091615](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39042091615) verified clean installation and launch of the preview on API 35 and API 36, plus upgrade from 0.9.0 / 33 and post-upgrade launch on API 36. UI was checked in a separate debug fixture from the same commit on both APIs; its test Activity and synthetic data are absent from the preview. The old APK's API 36 minimum makes it unsuitable for an API 35 upgrade test. Timeweb delivery and a physical phone remain distinct acceptance evidence in [PLAN_STATUS](PLAN_STATUS.md).

## Official platform references

Checked 2026-10-17:

- [Android SDK configuration](https://developer.android.com/build)
- [Android 15 behavior changes](https://developer.android.com/about/versions/15/behavior-changes-15)
- [Android 16 behavior changes](https://developer.android.com/about/versions/16/behavior-changes-16)
- [16 KB page-size compatibility](https://developer.android.com/guide/practices/page-sizes)
