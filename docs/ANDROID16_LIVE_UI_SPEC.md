# Analyst AI: Android 15+ native UI specification

Current contract for **0.10.0-preview / 34**, F01.4 / F22, following the Workspace interface stages F01.2 and F01.3. Updated 2026-10-17.

The owner's Android 15+ clarification supersedes the previous Android 16-only baseline. The filename is retained for existing links. Product scope and release evidence remain in [MASTER_PLAN](MASTER_PLAN.md) and [PLAN_STATUS](PLAN_STATUS.md); the current screen map is [WORKSPACE_UI](WORKSPACE_UI.md).

## Platform baseline

- `minSdk = 35`, `compileSdk = 36`, and `targetSdk = 36`. Android 14 / API 34 and older are unsupported.
- Use stable public Android 15+ APIs. Guard APIs introduced after API 35 by OS version when needed; increasing the target SDK must not silently raise the installation floor.
- Edge-to-edge cannot be opted out of on Android 16 when targeting API 36. Do not rely on the old opt-out attribute.
- Edge-to-edge is the default coordinate system. Screens consume `safeDrawing` and IME insets once and remain usable with gesture navigation, cutouts, and transparent system bars.
- Back navigation uses Activity/Compose predictive-back APIs. Do not intercept `KEYCODE_BACK` or restore legacy `onBackPressed()` handling.
- Layouts must remain usable on narrow phones, large fonts, split-screen, tablets, foldables, and large displays. Do not depend on orientation locks or a fixed aspect ratio.
- Motion state should be read in Canvas or `graphicsLayer` whenever possible so the full screen is not recomposed for each frame.

## Portfolio history in 0.10.0

- The **Портфель → Динамика** section, with an account selector, displays native Spectrum columns derived from saved balance snapshots. This data is a date and portfolio value, not an instrument OHLC series.
- Each column uses the last observed balance in its interval. The interval is chosen from days, weeks, months or years according to the available history, using the Moscow timezone.
- Missing intervals remain empty; zero and very small balances have an explicit marker. The value scale includes zero and supports negative balances without decorative distortion.
- A tap, horizontal drag, or previous/next accessibility action selects an interval. The tooltip shows its dates and exact closing balance; reset returns to the full displayed period.
- Compact statistics show observed value change and minimum/maximum where multiple snapshots are available. One snapshot is usable immediately and explicitly lacks a comparison.
- Interval cash flows use the existing read-only analytics API after selection settles. Deposits, withdrawals, dividends and coupons are shown separately from other operations and retain their source currencies.
- Value change and cash flows are not labelled investment profit. Invalid or contradictory history and incomplete operations have explicit states; privacy mode hides the chart.
- See [HistoryBars.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryBars.kt), [HistoryChart.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/HistoryChart.kt) and [AccountAnalytics.kt](../app/src/main/java/ru/omnicio/app/ui/portfolio/AccountAnalytics.kt).

## Nine live visual families

The approved Spectrum reference defines these nine families:

1. Live charts.
2. Animated indicators.
3. 2D/spatial elements.
4. RGB icon effects.
5. Interactive AI assistant.
6. Smart notifications.
7. Personal recommendations.
8. Risk control.
9. World-market analysis.

They describe the visual vocabulary, not completion of the investment algorithms, chat or delivery systems in the master plan. They are native program elements rendered with Jetpack Compose Canvas/graphics APIs. They are not PNG sequences, animated GIF files, remote images, WebViews, or copied broker artwork.

Each family has a distinct motion language:

- charts update bars and points;
- indicators move a gauge or progress arc;
- spatial elements change apparent depth;
- RGB elements shift light across facets;
- the assistant blinks, breathes, and changes mood only from real client state;
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
- The current shared live-motion helper runs two finite cycles. Selection effects are finite; the primary navigation icons are static. Do not reintroduce unbounded loops.
- Leaving the screen must cancel the animation coroutine. Do not leave hidden timers, decoders, or render loops running.
- Read animated values during draw or graphics-layer phases. Avoid recomposing a whole screen at frame rate.
- Limit simultaneous live elements within functional controls. A long scrolling list must not start dozens of independent loops; no separate capability showcase belongs on the dashboard.
- Every live icon keeps a visible text label and an accessibility description. Color or motion must never be the only carrier of financial meaning.
- Large-font layouts may stack content vertically instead of clipping or shrinking it below readable sizes.

## Update journey

The mandatory update screen has its own native visual language:

- a slow animated aurora/star-field background;
- a large animated warning mark when an update is required;
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
- Sonar/quality checks and backend tests applicable to the exact head.

For the published 0.10.0 APK, [run 39042091615](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39042091615) verified clean installation and launch of the preview on API 35 and API 36, plus upgrade from 0.9.0 / 33 and post-upgrade launch on API 36. UI was checked in a separate debug fixture from the same commit on both APIs; its test Activity and synthetic data are absent from the preview. The old APK's API 36 minimum makes it unsuitable for an API 35 upgrade test. Timeweb delivery and a physical phone remain distinct acceptance evidence in [PLAN_STATUS](PLAN_STATUS.md).

## Official platform references

Checked 2026-10-17:

- [Android SDK configuration](https://developer.android.com/build)
- [Android 15 behavior changes](https://developer.android.com/about/versions/15/behavior-changes-15)
- [Android 16 behavior changes](https://developer.android.com/about/versions/16/behavior-changes-16)
- [16 KB page-size compatibility](https://developer.android.com/guide/practices/page-sizes)
