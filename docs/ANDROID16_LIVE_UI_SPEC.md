# Analyst AI: Android 16 live UI specification

This document records the OWNER-approved implementation contract for Analyst AI 0.7.3 and later Android 16+ releases.

## Platform baseline

- `minSdk`, `compileSdk`, and `targetSdk` are API 36 or newer.
- Do not add fallback branches, polyfills, deprecated APIs, non-SDK APIs, or compatibility code solely for Android 15 and older.
- Edge-to-edge is the default coordinate system. Screens consume `safeDrawing` and IME insets once and remain usable with gesture navigation, cutouts, and transparent system bars.
- Back navigation uses Activity/Compose predictive-back APIs. Do not intercept `KEYCODE_BACK` or restore legacy `onBackPressed()` handling.
- Layouts must remain usable on narrow phones, large fonts, split-screen, tablets, foldables, and large displays. Do not depend on orientation locks or a fixed aspect ratio.
- Motion state should be read in Canvas or `graphicsLayer` whenever possible so the full screen is not recomposed for each frame.

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

They are native program elements rendered with Jetpack Compose Canvas/graphics APIs. They are not PNG sequences, animated GIF files, remote images, WebViews, or copied broker artwork.

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

- A repeating animation may run only while its composable is visible, its Activity is at least `STARTED`, the user has enabled Spectrum motion, and Android animators are enabled.
- Leaving the screen must cancel the animation coroutine. Do not leave hidden timers, decoders, or render loops running.
- Read animated values during draw or graphics-layer phases. Avoid recomposing a whole screen at frame rate.
- Limit simultaneous live elements. A compact dashboard strip is acceptable; a long scrolling list must not start dozens of independent loops.
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
- exact upgrade from the currently published preview APK;
- launch and UI checks on API 36;
- large-font and narrow-screen checks;
- Sonar/quality checks and backend tests applicable to the exact head.
