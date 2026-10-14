# Analyst AI Spectrum — canonical product design

Status: owner-approved visual direction from 2026-10-13. This document turns the reference collage into repeatable implementation rules. It does not make synthetic balances, ratings, charts or recommendations valid production data.

## Product impression

Analyst AI should feel like a calm personal analytical instrument, not a game or casino:

- black/deep-navy environment with controlled cyan, blue, violet, rose and emerald light;
- compact glass-like cards with thin spectral borders;
- original 2D icons with a small amount of depth and glow;
- one clear conclusion first, detail and sources after expansion;
- movement communicates selection, progress or fresh information, never urgency to trade;
- plain Russian text that explains the portfolio effect without unexplained jargon.

The current five primary destinations remain: **Портфель, Что купить, Пульс, Чат, Профиль**. Education is currently an internal destination opened from Profile/Info. A later navigation change requires an explicit product decision; visual similarity to a concept is not enough to change behavior silently.

## Color system

Dark foundation:

| Token | Value | Use |
|---|---:|---|
| App base | `#111111` with deep-navy Spectrum background glows | regular existing screens |
| Spectrum top | `#020A16` | immersive education/AI sections |
| Spectrum bottom | `#07192B` | immersive education/AI sections |
| Spectrum card | `#071A2A` | emphasized Spectrum surfaces |
| Spectrum strong card | `#0B2940` | hero/recommendation surfaces |
| Text | `#F4F4F5` | primary text |
| Supporting text | `#A4A7AE` | explanations and metadata |
| Cyan | `#36E0FF` | navigation/action accent |
| Blue | `#4C8DFF` | charts and neutral analytics |
| Violet | `#8A5CFF` | brand/AI accent |
| Rose | `#FF4FA3` | news/attention decoration, not loss |
| Emerald | `#19E6A2` | positive action and verified completion |
| Amber | `#FFC857` | warning/attention with text |

Light foundation remains quiet rather than neon-white: `#F5F6F8` background, white cards, dark text, saturated but accessible accent variants.

Semantic financial colors are separate from RGB branding. Profit/loss/warning/rating must include words and values. A violet glow must never mean “safe”; an emerald glow must never silently mean “guaranteed profit”.

## Layout and component rules

- 4dp base grid; screen horizontal padding 20dp; compact pages may use 16dp only for compatibility with existing screens.
- Main card radius 24dp; pills fully rounded; thin 1dp spectral border on Spectrum cards.
- Body text at least 16sp where it carries meaning; supporting metadata may use 12–14sp.
- Minimum touch target 48dp.
- Bottom navigation uses original Spectrum symbols and finite selection motion.
- Use 2D charts with labels and accessible text/table alternatives. Decorative depth belongs behind data, not in perspective-distorted wedges or axes.
- Preserve content while a new currency/period loads. Never blank a page just because a different view is requested.
- Real data comes from the user’s APIs and verified server sources. Preview/demo data must be visibly labelled.

Reusable implementation lives in:

- `ui/spectrum/SpectrumDesignSystem.kt` — palette, background, cards and badges;
- `ui/spectrum/SpectrumIcon.kt` — original finite-motion icons;
- `ui/theme/AnalystTheme.kt` — system/light/dark mode and saved motion preference;
- `ui/AnalystBottomBar.kt` — first production integration of Spectrum navigation.

## Motion

- Selection animation: one short 180ms rise and 420ms settle; no automatic infinite loop.
- App setting “Живые RGB-эффекты” controls decorative motion.
- Platform animator-disabled state and Activity lifecycle are mandatory gates.
- GIF/WebP is allowed for a small hero or onboarding scene, but not for every row in a portfolio list. Static SVG/PNG/vector alternatives are required.
- Motion must stop when the app is backgrounded. Reduced-motion mode keeps all information available.

## Education architecture

The built-in beginner curriculum is original copy with links to official material. It is organised around decisions a user actually faces:

1. goal, horizon and emergency reserve;
2. broker/exchange/depository mechanics;
3. stocks, bonds, funds and cash instruments;
4. diversification across economic groups, sectors, asset classes and currencies;
5. credit ratings, scale/agency/date/object limitations;
6. how news changes expectations and reaches a portfolio;
7. financial statements and cash flow;
8. fraud, hype and source checking.

The “news impact” explanation follows a repeatable map:

`official fact → difference from expectations → revenue/cost/rate/currency/commodity channel → issuer/sector → actual portfolio exposure → time horizon → uncertainty`.

Education must not become a sales funnel. It should teach the user to identify source, date, mechanism, scale and uncertainty before acting.

Official reading map used for curriculum design:

- Moscow Exchange School: beginner courses and step-by-step investment basics;
- Bank of Russia / Financial Culture: financial literacy and fraud prevention;
- Investor.gov: asset allocation/diversification and credit-rating limitations;
- Bank of Russia rating decisions: agencies, national scales and regulatory thresholds.

## Screens from the reference direction

The collage establishes these future visual patterns, but does not authorize fake production data:

- branded loading/splash scene with a spectral brain/globe and honest progress state;
- portfolio home with balance, real chart, five compact action cards and an Analyst AI explanation card;
- personalized ideas with source date, rationale, risk, target role, ticker/ISIN and explicit broker-card action;
- risk screen with a score breakdown and plain-language explanation;
- education cards with bright 2D lesson symbols;
- instrument details with real price/history/identity fields and no order execution by Analyst AI;
- full-screen mandatory update gate once the updater pipeline is genuinely safe.

## Implementation order

1. Apply Spectrum tokens and navigation without changing financial logic.
2. Add education and source-aware explanations.
3. Convert portfolio/ideas/pulse cards screen by screen; preserve existing tested flows.
4. Integrate verified recommendation/risk data only after collectors and validation exist.
5. Add updater gate only after same-signer download, verification, installation and rollback tests pass.
6. Release a new APK only after exact-head Android CI, installation/update tests, backend tests and quality checks succeed.
