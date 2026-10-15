# Analyst AI Spectrum — canonical product design

Status: owner-approved visual direction from 2026-10-13, clarified by the owner on 2026-10-15. This document turns the reference collage into repeatable implementation rules. It does not make synthetic balances, ratings, charts or recommendations valid production data.

## Product impression

Analyst AI should feel like a calm personal analytical instrument, not a game, casino or imitation of a broker application:

- black/deep-navy environment with controlled cyan, blue, violet, rose and emerald light;
- compact glass-like cards with thin spectral borders;
- original 2D icons with a small amount of depth and glow;
- one clear conclusion first, detail and sources after expansion;
- movement communicates selection, progress or fresh information, never urgency to trade;
- plain Russian text that explains the portfolio effect without unexplained jargon;
- T‑Invest remains a verified data source, not the visual identity of the product.

The five primary destinations are: **Главная, Портфель, Риски, Обучение, Профиль**.

- **Главная** is the Analyst AI dashboard: real balance, core metrics, shortcuts, a deterministic explanation and portfolio structure.
- **Портфель** contains verified accounts, positions, operations, payments and analytics.
- **Риски** contains structured server signals, morning/evening checks and uncertainty labels.
- **Обучение** is a first-class destination rather than a hidden profile page.
- **Профиль** contains appearance, account, T‑API, risk profile and application information.
- **Рекомендации** and **Сообщения** are internal destinations opened from Главная. They do not replace the five primary tabs.

## Color system

Dark foundation:

| Token | Value | Use |
|---|---:|---|
| Spectrum top | `#020A16` | application background |
| Spectrum bottom | `#07192B` | application background |
| Spectrum card | `#071A2A` | normal glass surfaces |
| Spectrum strong card | `#0B2940` | hero/recommendation surfaces |
| Text | `#F4F7FF` | primary text |
| Supporting text | `#B8C2D2` | explanations and metadata |
| Cyan | `#36E0FF` | navigation/action accent |
| Blue | `#4C8DFF` | charts and neutral analytics |
| Violet | `#8A5CFF` | brand/AI accent |
| Rose | `#FF4FA3` | news/attention decoration, not loss |
| Emerald | `#19E6A2` | positive action and verified completion |
| Amber | `#FFC857` | warning/attention with text |

Light foundation remains quiet rather than neon-white: `#F5F8FF` background, white cards, dark text, saturated but accessible accent variants.

Semantic financial colors are separate from RGB branding. Profit/loss/warning/rating must include words and values. A violet glow must never mean “safe”; an emerald glow must never silently mean “guaranteed profit”.

## Layout and component rules

- 4dp base grid; screen horizontal padding 20dp.
- Main card radius 24dp; pills fully rounded; thin 1dp spectral border on Spectrum cards.
- Body text at least 16sp where it carries meaning; supporting metadata may use 12–14sp.
- Minimum touch target 48dp.
- Bottom navigation uses original Spectrum symbols and finite selection motion.
- Use 2D charts with labels and accessible text/table alternatives. Decorative depth belongs behind data, not in perspective-distorted wedges or axes.
- Preserve content while a new currency/period loads. Never blank a page just because a different view is requested.
- Real data comes from the user’s APIs and verified server sources. Preview/demo data must be visibly labelled.
- Every screen uses theme-aware foreground and surface colors; hard-coded black text on dark cards is not permitted.

Reusable implementation lives in:

- `ui/spectrum/SpectrumDesignSystem.kt` — palette, backgrounds, glass cards, branded buttons, metrics, progress and the Analyst AI brand orb;
- `ui/spectrum/SpectrumIcon.kt` — original finite-motion icons;
- `ui/theme/AnalystTheme.kt` — system/light/dark mode, typography and saved motion preference;
- `ui/AnalystBottomBar.kt` — five production destinations;
- `ui/home/HomeScreen.kt` — production dashboard based on real portfolio data.

## Motion

- Selection animation: one short 180ms rise and 420ms settle; no automatic infinite loop.
- App setting “Живые RGB-эффекты” controls decorative motion.
- Platform animator-disabled state and Activity lifecycle are mandatory gates.
- GIF/WebP is allowed for a small hero or onboarding scene, but not for every row in a portfolio list. Static vector alternatives are required.
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

The collage establishes these production patterns without authorizing fake data:

- branded loading/login scene with a spectral brain/orbit and honest progress state;
- home dashboard with real balance, metrics, five compact destinations and an Analyst AI explanation card;
- portfolio with verified accounts, structure, positions and broker-source timestamps;
- recommendations with rationale, current/target role, risk limits and source status;
- risk screen with signal breakdown, validity and uncertainty;
- education cards with bright original 2D lesson symbols;
- profile/settings hub using the same glass system;
- full-screen mandatory update gate only after the updater pipeline is genuinely safe.

## Implementation order

1. Apply Spectrum tokens, theme-aware text and the exact product navigation.
2. Implement the real-data Home dashboard.
3. Convert recommendations, risks, education, profile and login to shared Spectrum components.
4. Convert deeper portfolio/account/detail screens without changing verified financial logic.
5. Integrate richer recommendation/risk data only after collectors and validation exist.
6. Release a new APK only after exact-head Android CI, installation/update tests, backend tests and quality checks succeed.
