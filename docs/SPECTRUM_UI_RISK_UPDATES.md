# Analyst AI / Spectrum — staged integration, not a release

Date: 2026-10-13. Baseline: e99007a24f015617d904248aac3e5eddf4efa4d1.

## Exact status

This draft branch now contains both reusable components and the first native integration:

- primary bottom navigation uses original Spectrum vector icons and finite selection motion;
- theme persists a user-controlled “Живые RGB-эффекты” setting and provides the canonical palette;
- Profile uses Spectrum icons and opens a native beginner Education screen;
- Education contains original Russian lessons on market mechanics, assets, diversification,
  credit ratings, financial statements, news transmission and fraud, with official source links;
- canonical design rules are recorded in AGENTS.md and `docs/SPECTRUM_DESIGN_CANON.md`.

The portfolio, ideas and pulse bodies have NOT all been visually converted. Mandatory update,
broker-card actions and quantitative risk preview are still components/libraries rather than a
complete production path. No deployment, release APK, paid inference, cloud purchase or trade
was performed by this branch. Keep it draft until exact-head Android/backend/quality checks and
installation/update tests complete.

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
Spectrum immersive background: #020A16 → #07192B; card #071A2A / #0B2940.
RGB accents: cyan #36E0FF, blue #4C8DFF, violet #8A5CFF, rose #FF4FA3,
emerald #19E6A2 and amber #FFC857.
Light base: #F5F6F8; card #FFFFFF; text #191A1D; supporting text #626974.
RGB means brand/action decoration, NOT gains, investment safety or model confidence.
Loss/warning/gain always have explicit text and a numeric value in addition to semantic color.

4dp grid; page padding 20dp; cards radius 24dp; icons 24/40/64dp;
interactive targets at least 48dp; body text 16sp; navigation labels remain compact.
Show understandable conclusion first, details/math/sources on expansion.

SpectrumIcon performs one 180ms rise plus 420ms settle when selected. The saved Profile switch,
Activity lifecycle and platform-disabled animation state gate decorative motion. GIF assets are
128x128, 48 frames and one 3.61-second pass, then static. Do not run dozens of decoders in a
scrolling portfolio list. Static vector/PNG alternatives remain required.

## Education research and product corrections

The owner-provided share.google redirects were not readable in the earlier session, so their
article text was not copied or silently replaced. The native curriculum is original and links to
official material from Moscow Exchange School, Bank of Russia / Financial Culture and
Investor.gov.

Implemented learning sequence:

1. goal, horizon and emergency reserve before buying;
2. broker/exchange/depository mechanics and costs;
3. stocks, bonds, funds and cash instruments;
4. issuer-group/sector/class/currency diversification and rebalancing with new cash;
5. credit-rating agency, scale, object, date, outlook and limitations;
6. news as a change in expectations transmitted through profit, rates, FX, commodities and risk;
7. statements: revenue, margins, debt, cash flow and one-off effects;
8. hype, fraud, license/source/date checks.

The screen is deliberately education, not a trade recommendation. It does not fetch user data,
call models or claim that reading a lesson removes investment risk. Official links open through
the platform URI handler.

## Quantitative risk library

`risk_preview.py` implements equal-probability empirical VaR and expected shortfall with
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

`BrokerInstrumentLink` validates a trusted canonical HTTPS instrument-card URL and tries a
non-browser Android handler. It does NOT guess private deep-link schemes or package IDs,
request broad package visibility, pre-fill trades or execute an order. The caller must show
an explicit browser option plus copy ticker/ISIN if no app handles the URL. An installed app
does not necessarily handle every card URL; actual device verification is still required.
Canonical-link retrieval and production button wiring are unfinished.

## Mandatory APK update

`release_contract.py` validates immutable same-host HTTPS release metadata, expected package,
certificate, SHA256, version bounds, size and publication date. It only makes pure decisions.
`UpdateFlow` models progress/verification/installer/confirmation/recheck; installer completion
never unlocks an obsolete code by itself. `RequiredUpdateScreen` is a component, not an active
root gate. No downloader, PackageInstaller session, authenticated device registry, serving
route or production policy was enabled.

Implementation order remains:

1. publish a tested same-certificate APK under immutable Moscow HTTPS;
2. verify size/hash/package/minSdk/signature and installation/update tests;
3. atomically activate release metadata;
4. bootstrap one updater-capable version before enforcing minimum versions;
5. download boundedly to app-private storage and reject redirects/mismatches;
6. hand the verified file to the Android installer and handle user confirmation/failure;
7. re-read the actual installed version before unlocking;
8. pause only affected personal jobs, not shared public-data collection.

Android does not guarantee silent installation and automatic reopening for this distribution
model. Do not bypass Play Protect, unknown-source controls or installer confirmation.

## Verification and remaining integration

Earlier local component verification: 31 Python risk/release regressions, 20 pure Kotlin update
checks, Chromium prototype groups, decoded finite GIFs and selected contrast checks. These are
not a full Android accessibility audit, live broker-link verification or a production investment
recommendation.

After the owner approved the visual direction, native integration added theme motion preference,
Spectrum navigation, Spectrum Profile actions and Education. Exact final SHA Android/backend CI,
Sonar, installation/update and real-device visual checks remain mandatory before merge/release.

Remaining major work:

- convert Portfolio, Ideas, Pulse and Chat bodies to the canonical components screen by screen;
- connect verified live rating/statement/news collectors and calibration;
- implement constrained recommendation optimization and broker-card source retrieval;
- complete the updater service/pipeline and safe legacy bootstrap;
- add tests for education navigation, large fonts, reduced motion and narrow screens;
- ship media assets only when their size, decoding and lifecycle behaviour are acceptable.

No external reference or design example establishes a real instrument rating, return, price or
portfolio fact. Data acquisition/licensing, model validation and the applicable legal regime for
personal recommendations require separate verification.
