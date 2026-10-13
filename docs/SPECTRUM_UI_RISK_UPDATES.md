# Analyst AI / Spectrum — staged components, not a release

Date: 2026-10-13. Baseline: e99007a24f015617d904248aac3e5eddf4efa4d1.

## Exact status

This branch adds reusable Kotlin components and pure Python risk/release-policy libraries.
They are NOT wired into the app root, paid inference, portfolio recommendations or production
API. Do not enable a mandatory-version gate or advertise a new APK from this branch yet.
The existing working Android package, signing, authentication, UI and deployment are unchanged.

An accompanying conversation artifact contains a self-contained interactive HTML prototype,
20 original GIFs (10 symbols in light/dark), 20 SVGs, 20 PNGs, source generators and test logs.
Those design-media files are delivered in that artifact; they are not all committed here.
All balances, charts, instruments and rating examples in the prototype are explicitly synthetic.
No prototype button trades, calls a model or downloads/installs an actual APK.

## Visual contract

Keep the five destinations: Портфель, Что купить, Пульс, Чат, Профиль.
Portfolio first shows money, then one important explanation, allocations and accounts.
Use 2D charts with labels, common scales and an accessible table alternative. Depth belongs
in decorative icons/cards, not distorted 3D chart sectors. Do not invent missing history.

Dark base: #111111; card #1E1E1E; text #F4F4F5; supporting text #A4A7AE.
Dark RGB accents: cyan #57DDE6, blue #76A9FA, violet #AF99FF, rose #F190C5.
Light base: #F5F6F8; card #FFFFFF; text #191A1D; supporting text #626974.
Light accents: #006C78 / #326FC8 / #6E4EAD / #A6367A.
RGB means brand/action decoration, NOT gains, investment safety or model confidence.
Loss/warning/gain always have explicit text in addition to semantic color.

4dp grid; page padding 20dp; cards radius 24dp; icons 24/40/64dp;
interactive targets at least 48dp; body text 16sp; navigation labels 12sp.
Show understandable conclusion first, details/math/sources on expansion.

SpectrumIcon: finite 180+420ms selection movement; static by default until a persisted
motion setting is connected. Lifecycle and platform disabled-animation settings are respected.
GIF assets: 128x128, 48 frames, one 3.61-second pass, then static; no infinite loop.
SVG and transparent PNG alternatives are supplied. GIF backgrounds are theme-specific.
Do not run dozens of animated GIF decoders in a scrolling portfolio list.
Battery-saver behavior and the root motion preference still require integration.

## Quantitative risk library

risk_preview.py implements equal-probability empirical VaR and expected shortfall with
fractional tail-boundary mass, explicitly aligned joint scenarios, supplied PD*LGD*EAD,
and exposure aggregation across accounts by economic issuer group, sector, class, quoted
currency and separate agency/scale/grade rating buckets. Inputs require freshness, sources,
common base valuations, valid decimals and explicit limits. Inadequate tail observations,
stale/missing/incompatible inputs or unsupported short positions stop the result.

ES is average loss in a specified worst tail, NOT maximum possible loss or a bankruptcy
avoidance probability. Never derive PD from a letter rating without a separately validated
model/horizon. Do not average national and global scales or mix different agencies.
Withdrawn/stale/missing/mismatched ratings remain UNVERIFIED, never implicitly safest.
Do not add low-rated debt solely to create rating diversity. Quoted currency exposure is
not a complete look-through economic currency-risk model.

The library evaluates a supplied portfolio. It does NOT yet optimize, rank live securities,
load corporate statements/news, estimate correlations/PDs or generate personal buy/sell orders.
Future optimization should compare doing nothing, deploying new cash and rebalancing existing
positions, including transaction/tax/liquidity/lot constraints and out-of-sample validation.
Data needed first: investor limits; broker eligibility; validated issuer groups; current prices;
source/time/units/standard of statements; debt, coverage, cash flows and maturities; rating
agency, scale, rated subject, date, outlook/watch/withdrawal; dated official events/news.
Do not use the same industrial leverage ratios blindly for banks and insurers.

Plain-language example, not live advice: «32 из каждых 100 ₽ связаны с одной группой.
Если эта часть потеряет половину стоимости, весь портфель уменьшится на 16% при
неизменности остального. Сравним уменьшение доли и направление новых денег в другие
компании». This is conditional arithmetic, not a forecast or probability.

Each actual recommendation must identify current/target weight, actionable lots, costs,
why relevant to this portfolio, alternative/no-action choice, sources/date, uncertainties,
ticker/ISIN/UID and a verified instrument-card link. No risk-free/bankruptcy-proof promises.

## Opening T-Investments

BrokerInstrumentLink validates a trusted canonical HTTPS instrument-card URL and tries a
non-browser Android handler. It does NOT guess private deep-link schemes or package IDs,
request broad package visibility, pre-fill trades or execute an order. The caller must show
an explicit browser option plus copy ticker/ISIN if no app handles the URL. An installed app
does not necessarily handle every card URL; actual device verification is still required.
Canonical-link retrieval and production button wiring are unfinished.

## Mandatory APK update

release_contract.py validates immutable same-host HTTPS release metadata, expected package,
certificate, SHA256, version bounds, size and publication date. It only makes pure decisions.
UpdateFlow models progress/verification/installer/confirmation/recheck; installer completion
never unlocks an obsolete code by itself. RequiredUpdateScreen is a component, not an active
root gate. No downloader, PackageInstaller session, authenticated device registry, serving
route or production policy was enabled.

Order for implementation:
1. Publish tested same-certificate APK under /releases/{code}/{sha256}.apk on Moscow HTTPS.
2. Verify a download, size/hash/package/minSdk/signature and installation/update tests.
3. Atomically activate release metadata. For owner's mandatory policy minimum=latest.
4. Check on launch/resume, report per-install/session version, show full-screen gate;
   keep download/manifest/help/sign-out accessible, preserve tokens and local data.
5. Download boundedly to app-private temporary storage; reject redirects/hash/package/
   signer/version mismatch; hand verified APK to the platform installer.
6. Handle STATUS_PENDING_USER_ACTION, cancellation, failed installation and application
   process replacement. Re-read actual installed version after successful installation.
7. Pause only affected personal jobs after an authenticated server compatibility decision;
   preserve shared public-data collection; resume after a confirmed compatible session.

Version headers are client claims, not tamper-resistant attestation. Per-user/per-device
semantics and stale-heartbeat ordering must be designed before enforcement. Connectivity
errors must not be reported as proven obsolete versions. A missing APK must never leave
all users without an upgrade path. Self-update without extra confirmation requires Android
conditions; never promise silent installation/automatic reopening on every phone or bypass
Play Protect/unknown-source controls.

Legacy 0.5.1 and earlier contain no updater. A server cannot add local UI/code to already
installed binaries. One bootstrap installation of an updater-capable build is required;
«any APK upgrades itself» is only attainable for compatible builds from that point onward.

## Verification and remaining integration

Locally: 31 Python regressions, 20 pure Kotlin update-state checks, 8 groups of Chromium
prototype tests including 20 tab/width combinations (320/360/390/430), all 20 GIFs decoded
(48 frames/3610ms/no loop), 24 selected text palette contrast pairs >=4.5:1.
These are NOT an Android install test, full accessibility audit, broker-link verification,
live investment recommendation or proof of deployed services. Native compilation and all
applicable exact-head CI must pass. Keep this PR draft until product wiring and relevant
integration/installation tests are complete. No main merge/deploy/APK release from a mockup.

## Source scope

The two owner-provided share.google links could not be resolved in this session:
https://share.google/RLfZSVS59yHsiTBsP
https://share.google/CgouC96rAVvH8YKgc
Their article text was NOT read, summarized or replaced by similar search-result titles.
Prototype educational copy is original, not excerpts from those articles.

Primary external references checked:
- https://developer.android.com/reference/android/content/pm/PackageInstaller.SessionParams
- https://developer.android.com/training/package-visibility/use-cases
- https://developer.android.com/reference/kotlin/androidx/compose/ui/MotionDurationScale
- https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html
- https://www.w3.org/WAI/WCAG22/Techniques/general/G152.html
- https://doi.org/10.1007/978-1-4419-1153-7_1232

No external reference above establishes any real instrument rating or financial figure in
the prototype. Data acquisition/licensing, model validation and the applicable legal regime
for personal investment recommendations require separate verification.
