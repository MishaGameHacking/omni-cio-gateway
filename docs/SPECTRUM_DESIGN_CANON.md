# Analyst AI Spectrum — canonical product design

Status: Spectrum direction approved 2026-10-13, refined by the owner on 2026-10-15 and superseded where needed by the **Workspace redesign and Android 15+ clarification of 2026-10-17**. Updated against **0.10.0-preview / 34**, F01.4 / F22.

This document records the current shared visual language. [WORKSPACE_UI](WORKSPACE_UI.md) defines the current screen map; [MASTER_PLAN](MASTER_PLAN.md) and [PLAN_STATUS](PLAN_STATUS.md) define product scope and completion evidence. Synthetic balances, ratings, charts or recommendations are not valid production data.

## Product impression

Analyst AI should feel like a calm personal analytical instrument, not a game, casino or imitation of a broker application:

- black/deep-navy environment with controlled cyan, blue, violet, rose and emerald light;
- compact glass-like cards with thin spectral borders;
- original 2D icons with a small amount of depth and glow;
- one clear conclusion first, detail and sources after expansion;
- movement communicates selection, progress or fresh information, never urgency to trade;
- plain Russian text that explains the portfolio effect without unexplained jargon;
- T‑Invest remains a verified data source, not the visual identity of the product.

The five primary destinations are: **Капитал, Портфель, Действия, Риски, Профиль**.

- **Капитал** is the Analyst AI dashboard: real balance, broker result and freshness, two shortcuts to assets/payments, a deterministic explanation and optional portfolio structure.
- **Портфель** contains accounts, positions, structure, balance history, operations, payments and read-only analytics.
- **Действия** opens the available analysis, with a separate plan view. The concrete trade-plan calculation remains unconnected and is labelled accordingly.
- **Риски** shows actual observation signals, data completeness, detail and uncertainty. Its visual presentation does not complete the risk model.
- **Профиль** groups settings, account and application information, with access to appearance, T‑API, strategies, notifications and other secondary tools.
- **Обучение**, **Ассистент**, **Уведомления**, **Моя стратегия** and **Отрасли и классы** are separately accessible internal destinations. Education is no longer a primary bottom tab.
- Do not restore the “Живые возможности” capability showcase, its technical catalogue or Android badge on the capital screen.

## Color system

Default dark Aurora foundation in 0.10.0:

| Token | Value | Use |
|---|---:|---|
| Spectrum top | `#090E18` | application background |
| Spectrum bottom | `#111827` | application background |
| Spectrum card | `#121D2B` | normal glass surfaces |
| Spectrum strong card | `#192A3B` | hero/recommendation surfaces |
| Text | `#F4F7FF` | primary text |
| Supporting text | `#B8C2D2` | explanations and metadata |
| Cyan / mint | `#70E0D2` | navigation/action accent |
| Blue | `#4C8DFF` | charts and neutral analytics |
| Violet | `#8A5CFF` | brand/AI accent |
| Rose | `#FF4FA3` | news/attention decoration, not loss |
| Emerald | `#19E6A2` | positive action and verified completion |
| Amber | `#FFC857` | warning/attention with text |

Light mode uses a `#F5F8FF` foundation, white cards, dark text and accessible accent variants. **Аврора**, **Океан** and **Ирис** change the accent palette through the shared theme; screens consume theme tokens instead of copying a local palette.

Semantic financial colors are separate from RGB branding. Profit/loss/warning/rating must include words and values. A violet glow must never mean “safe”; an emerald glow must never silently mean “guaranteed profit”.

## Layout and component rules

- 4dp base grid; screen horizontal padding 20dp.
- Main card radius is 24dp in the default density and 18dp in compact density; pills remain rounded and Spectrum cards use the shared border treatment.
- Body text is at least 16sp where it carries meaning. Supporting labels use the shared typography; compact chart-axis labels have exact-value text and accessibility alternatives.
- Minimum touch target 48dp.
- Bottom navigation uses original Spectrum symbols, persistent text labels and a clear selected surface. The current primary-navigation icons are static.
- Use 2D charts with labels and accessible text/table alternatives. Decorative depth belongs behind data, not in perspective-distorted wedges or axes.
- Preserve content while a new currency/period loads. Never blank a page just because a different view is requested.
- Real data comes from the user’s APIs and verified server sources. Preview/demo data must be visibly labelled.
- Every screen uses theme-aware foreground and surface colors; hard-coded black text on dark cards is not permitted.

Reusable implementation lives in:

- `ui/spectrum/SpectrumDesignSystem.kt` — palette, backgrounds, glass cards, branded buttons, metrics, progress and the Analyst AI brand orb;
- `ui/spectrum/SpectrumIcon.kt` — original icons with optional finite selection motion;
- `ui/spectrum/SpectrumLiveMotion.kt` — lifecycle-gated finite motion for native visual families;
- `ui/theme/AnalystTheme.kt` — system/light/dark mode, typography, accent variants and saved motion preference;
- `ui/workspace` — screen composition, appearance controls and local draft/preferences;
- `ui/AnalystBottomBar.kt` — five production destinations;
- `ui/home/HomeScreen.kt` — production dashboard based on real portfolio data;
- `ui/portfolio/HistoryBars.kt` and `HistoryChart.kt` — saved-balance grouping, columns, selection and exact values.

These paths are relative to `app/src/main/java/ru/omnicio/app/`.

## Financial charts

The F01.4 history is available at **Портфель → Динамика** with a choice of account, and inside **счёт → Аналитика**.

- Draw native 2D columns from real saved account balances. Each interval uses its last snapshot, preserving the exact original amount; it is not a sum of snapshots.
- Group in the Moscow timezone by day, week, month or year according to the history span. Leave missing intervals empty and include the most recent real snapshot.
- Keep the zero baseline and negative values truthful. Small/zero-value markers must not inflate the money scale.
- A tap, horizontal drag or previous/next action exposes dates and exact balance. Reset restores whole-period statistics; exact source values remain available in a disclosure.
- Label balance movement as **Изменение стоимости**. Cash flows are obtained separately from the existing read-only endpoint and retain source currencies; neither is labelled investment profit.
- Show single-snapshot, empty, incomplete or invalid-history states explicitly. Respect the user's hidden-balance setting.
- Do not describe these saved-balance columns as instrument OHLC candles or imply that unavailable quote history has been implemented.

## Motion

- An icon may use a short 180ms rise and 420ms settle when its caller enables selection motion. The shared live-motion helper performs two finite cycles.
- **Оформление → Движение** controls decorative motion; **Глубина** controls shadows and spatial accents.
- Platform animator-disabled state, visibility and an Activity lifecycle of at least `STARTED` are mandatory gates.
- Native icons, the assistant and update visuals use Compose Canvas/graphics APIs. Do not substitute GIF/WebP sequences, PNG artwork, remote images or WebViews for these program elements.
- Read motion state during drawing or graphics-layer work. Do not give each portfolio row its own timer or repeatedly recompose an entire screen.
- Motion stops when the app is backgrounded or the element leaves composition. Reduced-motion mode keeps all information available.

## Education architecture

The existing beginner curriculum is original copy with links to official material. This UI stage preserves its content; expansion remains outside the current instruction. It is organised around decisions a user actually faces:

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
- capital dashboard with real balance, metrics, two useful shortcuts and an Analyst AI explanation card;
- portfolio with verified accounts, structure, positions and broker-source timestamps;
- actions and analysis with real source status; concrete quantities and portfolio-effect calculations appear only when their plan dependencies are implemented;
- risk screen with signal breakdown, validity and uncertainty;
- education cards with bright original 2D lesson symbols;
- profile/settings hub using the same glass system;
- full-screen mandatory update gate only after the updater pipeline is genuinely safe.

## Current platform and maintenance contract

- Android baseline: `minSdk = 35`, `compileSdk = 36`, `targetSdk = 36`. Follow the [native UI specification](ANDROID16_LIVE_UI_SPEC.md) for edge-to-edge, predictive back, adaptive layouts and motion.
- Workspace screens and the F01.4 saved-balance columns are part of the published 0.10.0 preview. Release, server delivery and physical-device acceptance remain separate entries in [PLAN_STATUS](PLAN_STATUS.md).
- Build further screen changes from the shared components, preserving real read-only functions and user state.
- Connect recommendations, risk, strategy effects, chat and delivery only when the corresponding collectors, calculations and validation from the master plan are ready. Local drafts remain explicitly inactive.
- Release a new functional APK only after all applicable checks for the candidate commit pass, including Android installation/UI on API 35 and API 36 and the applicable upgrade path. Preserve the preview package, signing identity and user data.
- Documentation-only maintenance records the already published behavior and does not imply a new application version.
