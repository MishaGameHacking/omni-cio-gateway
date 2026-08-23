# Omni-CIO V10 — Premium Spatial Financial OS Web Visual Refresh

**Status:** OWNER-APPROVED VISUAL DIRECTION / IMPLEMENTATION BRIEF / NOT CURRENT-WP AUTHORITY BY ITSELF  
**Recorded:** 2026-08-23  
**Drafting baseline:** protected `main` `235ebfd386d46b74fb2428085ac233aa4494d696`  
**Product:** the existing source-controlled `apps/web` Omni-CIO Web application only  
**Dynamic current-WP authority:** `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`

## 0. Lifecycle and execution lock

This document records the OWNER-approved direction for the next material Omni-CIO Web visual modernization. It is deliberately detailed so a future AI/developer session can execute the design without reconstructing intent from chat history.

This document does **not** override the V10 Program Lock, current-WP sequence, `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`, active amendments, protected V9 boundaries, or exact-head GREEN merge law.

At the time this brief was authored, `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` still identifies **WP22A Phase 4 — Protected provider bootstrap/apply** as the authorized current increment. Therefore:

- do not begin runtime/CSS/TSX implementation from this brief while the current status still forbids that work;
- first restore accepted `main`, current status, amendments, current WP contracts, open PR/issues and CI;
- when the canonical status explicitly authorizes this Web visual-refresh increment, execute it through focused branch/PR increments;
- if program sequencing requires an amendment or a named design-refresh Work Package before implementation, create/accept that authority first;
- never silently treat this file as a competing `NEXT` ledger.

The intended implementation preserves one product and one frontend. It **must not** create a second Web App, second design system, website-builder copy, parallel API, parallel Core, new product identity system, or competing broker/execution stack.

## 1. Canonical implementation prompt

Use the following as the implementation prompt once the canonical V10 status authorizes this work.

---

### ROLE

You are the primary AI engineer and product-design implementer for Omni-CIO V10 in `MishaGameHacking/omni-cio-gateway`.

Your job is to modernize the existing `apps/web` visual system into a premium, spatial, high-trust financial interface while preserving all accepted product semantics, security boundaries, accessibility, performance, responsive behavior and source-controlled architecture.

Do not perform a greenfield rewrite. Reuse the accepted React/Vite application, existing route contracts, design-system ownership and deterministic product/API semantics.

### FIRST: RESTORE AUTHORITY

Before changing code, re-read at minimum:

1. `README.md`;
2. `AGENTS.md`;
3. `CONTRIBUTING.md`;
4. `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`;
5. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
6. `knowledge/16_CURRENT_PROGRAM_STATUS.md`;
7. `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
8. `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
9. `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` and applicable active amendments;
10. `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
11. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
12. current Web architecture/contracts/tests;
13. exact current `main`, latest commits, open PRs/issues and GitHub Actions.

If the current status does not authorize this visual-refresh implementation, **STOP implementation** and leave this brief as planning evidence only.

### NON-NEGOTIABLE PRODUCT/SECURITY BOUNDARIES

Preserve all of the following unless a later accepted authority explicitly changes them:

- protected V9 entrypoint `app:app` and V9 rollback;
- one existing V10 Web App in `apps/web`;
- `PUBLIC_MULTI_USER_ENABLED=false` until its owning gate;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker write remains OFF;
- no transfer/withdrawal/margin/uncovered-short authority;
- no real broker/provider/Telegram/VK secrets in source, browser storage, logs, CI or artifacts;
- PROJECT OWNER is an ordinary product USER when using Omni-CIO;
- `/system` is USER-facing diagnostics, not a hidden cross-tenant admin console;
- financial truth, permissions and money-path semantics stay in deterministic Core/API contracts, not in the presentation layer;
- do not invent financial fields, aggregate currencies without an authorized FX basis, manufacture freshness, or visually imply data confidence the API does not provide.

### DESIGN NORTH STAR

Transform Omni-CIO from a conventional bordered admin dashboard into a **Premium Spatial Financial OS**.

The experience should feel:

- calm rather than noisy;
- premium rather than decorative;
- spatial rather than flat;
- information-dense but highly scannable;
- trustworthy rather than speculative;
- modern on both phone and desktop;
- distinctly Omni-CIO, not a clone of another product.

Reference principles, not pixel copies:

- Linear: calm information hierarchy, dimmer navigation chrome, consistency, reduced visual noise;
- Apple modern material guidance: navigation/controls may form a separate translucent functional layer while content remains legible and comparatively solid;
- Material 3 Expressive: token-driven color, typography, shape and motion with purposeful emphasis;
- modern Framer/Webflow work: restrained interactive gradients, shaders and spring motion as optional atmospheric enhancements, never as financial-data distortion.

Do **not** make the product look like a crypto casino, gaming HUD, neon cyberpunk dashboard, generic glassmorphism template, or marketing landing page pretending to be a financial operating system.

## 2. Visual architecture

### 2.1 Three-layer spatial hierarchy

Build the entire interface around three explicit visual planes:

1. **Canvas** — the atmospheric application background.
2. **Content surfaces** — readable, mostly opaque financial/data panels.
3. **Functional layer** — navigation, top-level controls, sheets, menus and transient UI that may use restrained translucent material.

The hierarchy must be obvious even in screenshots with no motion.

Never use strong glass/transparency for dense financial tables, long text, forms, warning blocks or primary data cards. Glass is reserved mainly for navigation and compact controls.

### 2.2 Canvas

Dark identity should use graphite/navy rather than pure black. Light identity should use cool off-white rather than pure white across every surface.

Initial target dark tokens (tune only when contrast/perceptual testing proves necessary):

```css
--canvas: oklch(0.145 0.020 255);
--canvas-raised: oklch(0.175 0.024 255);
--surface-1: oklch(0.205 0.026 255);
--surface-2: oklch(0.245 0.030 255);
--surface-3: oklch(0.285 0.033 255);
--text-primary: oklch(0.955 0.010 255);
--text-secondary: oklch(0.740 0.024 255);
--text-tertiary: oklch(0.610 0.025 255);
--accent-blue: oklch(0.690 0.190 255);
--accent-cyan: oklch(0.790 0.130 205);
--accent-violet: oklch(0.690 0.160 300);
--semantic-success: oklch(0.750 0.155 150);
--semantic-warning: oklch(0.820 0.155 85);
--semantic-error: oklch(0.690 0.195 28);
```

Initial target light tokens:

```css
--canvas: oklch(0.975 0.008 255);
--canvas-raised: oklch(0.995 0.004 255);
--surface-1: oklch(0.995 0.004 255);
--surface-2: oklch(0.960 0.010 255);
--surface-3: oklch(0.925 0.014 255);
--text-primary: oklch(0.220 0.025 255);
--text-secondary: oklch(0.450 0.030 255);
--text-tertiary: oklch(0.560 0.028 255);
--accent-blue: oklch(0.560 0.205 255);
--accent-cyan: oklch(0.620 0.140 205);
--accent-violet: oklch(0.560 0.175 300);
```

These are foundation candidates, not permission to scatter hard-coded colors across components. Map them into canonical semantic design tokens in `tokens.css`; all pages consume aliases/tokens.

### 2.3 Ambient light

The canvas may contain at most 2–3 very soft atmospheric gradient sources:

- electric-blue glow near primary content focus;
- cyan secondary glow;
- restrained violet tertiary accent.

Target opacity: approximately **4–12%**, never saturated blobs behind text.

For ambient animation:

- cycle length: **12–24 seconds**;
- translation amplitude: at most **2–4% of viewport**;
- scale change: at most **1.03–1.07**;
- no rapid hue cycling;
- no continuous animation when `prefers-reduced-motion: reduce`;
- no animation that changes financial meaning or attention priority.

## 3. Typography

### 3.1 Font strategy

Replace the current visually dated Arial-first presentation with a modern, neutral financial-product typography system.

Do not add a remote Google Fonts/CDN dependency. Existing CSP/self-hosting rules must remain valid.

Preferred decision order:

1. review a self-hosted open-source variable sans such as **Inter Variable** or **Geist Sans** for license, binary size, CSP, reproducibility and browser support;
2. if a new font asset is not justified/authorized, use a modern system stack without external network fetches;
3. do not add a typography framework merely for appearance.

Suggested fallback stack:

```css
font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
```

A bundled font must be added only through the repository’s dependency/license/reproducibility process.

### 3.2 Type scale

Use a restrained fluid scale:

- display/major portfolio value: `clamp(2.5rem, 6vw, 5.25rem)`, weight 600–700, line-height 0.95–1.0;
- page H1: `clamp(2rem, 4vw, 3.5rem)`, weight 600–700, line-height 1.0–1.08;
- H2: `clamp(1.35rem, 2.2vw, 2rem)`, weight 600–650;
- card heading: 1.0–1.125rem, weight 600;
- body: 0.9375–1rem, line-height 1.5–1.65;
- metadata/captions: 0.75–0.8125rem, line-height >= 1.4;
- eyebrow/technical label: 0.70–0.78rem, tracking 0.08–0.12em, use sparingly.

Financial numbers must use:

```css
font-variant-numeric: tabular-nums lining-nums;
```

Do not use ultralight fonts for monetary values or status-critical text.

## 4. Spacing, grid and geometry

Use a **4 px base grid** with canonical spacing steps:

`4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 px`.

Do not create one-off 13px/19px/27px spacing unless a measured component constraint justifies it.

### 4.1 Desktop

For >= 1200 px:

- application content max width: **1440–1600 px**;
- outer content gutter: **32 px** (24 px minimum near 1200);
- desktop navigation width: **272 px** target; acceptable range 264–288 px;
- top functional bar height: **64–72 px**;
- major panel gap: **24 px**;
- compact grid gap: **16 px**.

### 4.2 Tablet

For 768–1199 px:

- outer gutter: **20–24 px**;
- content gaps: **16–20 px**;
- navigation may collapse into a narrower rail or sheet only if route discoverability remains strong;
- do not squeeze financial tables below readable widths: use internal horizontal scroll for tables rather than whole-page overflow.

### 4.3 Mobile

Canonical minimum viewport remains **360 px**.

For <= 767 px:

- content edge padding: **16 px**;
- compact control gap: **8–12 px**;
- card gap: **12–16 px**;
- topbar target: **56–64 px**;
- touch targets: at least **44 × 44 px**;
- safe-area aware bottom/top padding using `env(safe-area-inset-*)` where relevant;
- no horizontal document overflow at 360 px;
- tables may scroll inside dedicated containers;
- long IDs, codes and financial strings must wrap or truncate with an accessible full-value affordance where appropriate.

### 4.4 Radius system

Use a small consistent set:

- compact controls: 10 px;
- fields/small cards: 12–14 px;
- standard cards: 16–18 px;
- hero/floating shell panels: 20–24 px;
- pills/badges: 999 px.

Avoid making every rectangle excessively rounded.

## 5. Material, borders and elevation

Reduce the current dependence on visible 1 px borders.

Use borders only when they clarify interaction, containment or dense table structure. Prefer hierarchy from luminance, spacing, subtle elevation and edge highlights.

Define three elevation levels:

- **Elevation 0:** canvas / flat page background;
- **Elevation 1:** content card; very subtle shadow or edge separation;
- **Elevation 2:** floating navigation, popover, drawer, dialog;
- **Elevation 3:** transient critical overlay only.

Dark-mode shadows should not become large black blobs. Combine low-opacity shadow with a subtle top/inner edge highlight.

Example direction (tune via visual test):

```css
--shadow-1: 0 8px 24px rgb(0 0 0 / 14%);
--shadow-2: 0 18px 50px rgb(0 0 0 / 22%);
--edge-highlight: inset 0 1px 0 rgb(255 255 255 / 7%);
```

## 6. Functional glass layer

Use translucent material only for top-level functional chrome such as:

- desktop sidebar/dock;
- topbar;
- mobile navigation dock/sheet;
- compact popovers;
- transient command/selection surfaces.

Target values for a regular functional material:

- background opacity roughly **72–88%** depending on theme/content;
- `backdrop-filter: blur(18px) saturate(120%)` as progressive enhancement;
- subtle 1 px translucent edge;
- sufficient opaque fallback when `backdrop-filter` is unsupported;
- text contrast must remain AA even over worst-case background.

Never stack multiple highly translucent glass cards over each other.

## 7. Shell and navigation redesign

### 7.1 Desktop shell

Convert the shell from a flat admin-layout feeling into a quiet spatial operating environment:

- sidebar/dock visually recedes from the main work area;
- main content is brighter/clearer than navigation chrome;
- active route gets a restrained accent fill/edge, not a giant bright rectangle;
- inactive routes use lower contrast but remain readable;
- global `READY/PARTIAL/STALE/DEGRADED/...` state remains visible in the functional layer;
- freshness stays adjacent to health/status where space allows;
- do not hide critical degraded state for aesthetic reasons.

Target sidebar geometry:

- width 272 px;
- 12–16 px inset from viewport edges on large screens if the chosen shell composition supports it;
- 18–22 px radius for floating shell material;
- nav row height 44–48 px;
- icon/label gap 10–12 px;
- group spacing 20–28 px.

If icons are introduced, use one coherent open-source SVG icon set only after license/source review; do not mix icon styles. Text labels remain present on desktop.

### 7.2 Mobile navigation

Do not return to a transparent fullscreen sidebar.

Preferred pattern for the 12 current routes:

- persistent compact topbar with brand, global status and `Меню`/navigation trigger;
- 4 primary destinations may be exposed in an optional bottom dock (`Обзор`, `Портфель`, `Watchtower`, `Research`) plus `Ещё`;
- all routes remain accessible through a solid/regular-material navigation sheet;
- sheet max width on side-sheet implementation: **min(360px, 92vw)**;
- bottom-sheet implementation: radius 24 px 24 px 0 0, max-height about 82dvh, internal scroll;
- open/close must trap/restore focus correctly if implemented as modal navigation;
- background content must not visually compete with the sheet;
- body/document must not horizontally scroll while navigation is open.

Do not change route semantics merely to fit a visual pattern.

## 8. Motion system

Motion must communicate hierarchy and state, not decorate every element.

Create canonical motion tokens:

```css
--motion-fast: 120ms;
--motion-standard: 180ms;
--motion-emphasis: 240ms;
--motion-layout: 320ms;
--ease-standard: cubic-bezier(0.2, 0.8, 0.2, 1);
--ease-enter: cubic-bezier(0.16, 1, 0.3, 1);
--ease-exit: cubic-bezier(0.4, 0, 1, 1);
```

Use primarily `transform`, `opacity`, `filter` and composited properties.

Recommended behaviors:

- card hover: max `translateY(-1px)` plus slight elevation increase;
- press: scale no lower than `0.985` and return immediately;
- nav selection: 180–240 ms material/indicator transition;
- sheet/drawer: 240–320 ms with modest spring-like ease;
- route content: subtle 4–8 px translate + opacity, never dramatic zoom;
- status changes: short color/opacity transition; never pulse forever;
- counters may animate only when values actually change and must finish quickly.

Use the View Transition API only as progressive enhancement with deterministic fallback; do not make routing correctness depend on it.

For `prefers-reduced-motion: reduce`:

- disable ambient drift, parallax, elastic/spring movement and nonessential transitions;
- retain immediate state clarity;
- keep the existing project principle of effectively zero-duration decorative animation.

## 9. 3D / shader / spatial enhancement policy

3D is allowed only where it improves brand atmosphere without obscuring financial truth.

### Allowed locations

- unauthenticated/login screen;
- synthetic preview landing/empty state;
- global background brand atmosphere;
- rare non-data decorative identity element.

### Forbidden locations

- bars, lines or areas representing money/quantities/risk where perspective changes perceived magnitude;
- dense portfolio tables;
- warnings/errors;
- execution authorization surfaces;
- security/settings forms;
- any state where decoration could hide `BLOCKED`, `ERROR`, `STALE` or `DEGRADED` meaning.

Start with CSS-native pseudo-3D and gradients. Do **not** add Three.js, Spline runtime, GSAP or another animation/3D dependency merely because modern reference products use such tools.

Only introduce a dedicated WebGL/motion dependency after a focused decision proves:

- measurable visual value;
- acceptable license/security/maintenance status;
- reproducible locked dependency;
- route-level lazy loading;
- acceptable bundle/performance impact;
- graceful no-WebGL fallback;
- reduced-motion and low-power fallback;
- no CSP/network widening.

If pointer-responsive brand depth is used:

- maximum perceived tilt: about **3–5 degrees**;
- maximum translation: **8–12 px**;
- spring response should be soft, not twitchy;
- disable pointer parallax on touch-only devices and reduced-motion mode.

## 10. Product surfaces

All existing routes stay part of one coherent visual system:

`/`, `/portfolio`, `/assets`, `/watchtower`, `/research`, `/risks`, `/decisions`, `/plans`, `/execution`, `/journal`, `/system`, `/settings`.

### 10.1 Login / synthetic preview

Make this the most expressive surface because it has the least dense financial content.

Composition:

- centered or asymmetric two-column hero on desktop;
- one clear Omni-CIO brand object / spatial orb / data-mesh illustration;
- concise product message and authentication card;
- Telegram/VK controls remain fail-closed according to provider state;
- synthetic-preview action remains explicit and visibly different from real product auth;
- warning that real tokens/private data are disabled remains prominent;
- on 360 px collapse to one column; decorative object moves behind/above content without reducing text contrast.

Do not imply providers are enabled when API says `NOT_CONFIGURED`.

### 10.2 Overview `/`

Create a command-center overview, not a wall of equally weighted cards.

Prioritize:

1. product/global state;
2. portfolio/account freshness and high-level data that actually exists;
3. active Watchtower severity;
4. important decisions/plans;
5. recent research/system state.

If an API field does not exist, do not invent it for visual symmetry. Use truthful empty/degraded states.

### 10.3 Portfolio `/portfolio`

Build a premium financial hierarchy:

- hero region for the most authoritative available portfolio/account value;
- nearby freshness/source/completeness metadata;
- P&L or performance metrics only if authoritative data exists in accepted contracts;
- compact KPI surfaces;
- holdings table below the hero;
- semantic grouping by account/currency without illegal cross-currency aggregation;
- distinguish broker-reported period/current account facts from current-market quote enrichment visually and textually;
- show stale/partial/unknown prominently, never as normal READY styling.

If accounts contain different currencies and no approved FX basis exists, **do not display one summed total**. Show currency-separated totals or an explicit `not available without FX` state.

### 10.4 Assets `/assets`

Use the Portfolio visual language but optimize for scanning instruments:

- instrument identity/ticker hierarchy;
- quantity and blocked quantity;
- broker value vs current-market value clearly separated;
- freshness/source visible on demand or in a consistent secondary row;
- risk/state chips accessible and not color-only;
- table remains 2D and numerically precise.

### 10.5 Watchtower `/watchtower`

Make severity and recency immediately scannable:

- strong but restrained critical/error indicators;
- severity rail/timeline or structured incident cards;
- `active/resolved/reopened` differentiated by shape/icon/text, not color alone;
- timestamps/freshness visible;
- incident detail expands without causing route-wide layout jumps.

### 10.6 Research `/research`

Research should feel editorial and evidence-driven rather than like generic cards:

- dossier title + state + freshness;
- provenance/source identity prominent;
- published/retrieved times where available;
- evidence density with clean typography;
- compact tags/chips;
- invalid/duplicate/truncated state must remain visible;
- no decorative animation should distract from evidence reading.

### 10.7 Risks `/risks`

Use an analytical hierarchy:

- top risk summary only from existing deterministic data;
- risk states use semantic tokens plus text/icon;
- risk details should be visually quieter than truly blocking/critical conditions;
- use flat 2D charts/heatmaps when data supports them;
- no perspective/3D charts.

### 10.8 Decisions `/decisions` and Plans `/plans`

Design as a decision stack:

- primary decision at top;
- evidence/rationale layer;
- before/after or plan structure if existing contract supplies it;
- explicit execution authorization state;
- version/freshness/status metadata;
- `NO_CHANGE`, `BLOCKED`, incomplete data and missing plan must have intentionally designed states, not blank screens.

### 10.9 Execution `/execution`

This surface must visually reinforce authority boundaries.

While execution is disabled/locked:

- make the lock state unmistakable;
- never render a realistic enabled trade-submit button as decorative mock UI;
- do not imply real-money authority exists;
- use calm locked-state explanation rather than alarm-red unless an actual error exists.

Future real execution UI must be owned by its later authorized WP; this visual refresh cannot unlock it.

### 10.10 Journal `/journal`

Use a chronological, readable structure:

- time/decision/state hierarchy;
- compact metadata;
- expandable evidence/details;
- avoid giant card repetition;
- keep history trustworthy and calm.

### 10.11 System `/system`

This is USER diagnostics, not engineering admin authority.

Use:

- grouped service state;
- database/application/recovery/freshness indicators;
- release/version metadata where available;
- clear degraded/offline messages;
- no hidden cross-tenant controls;
- no provider-secret surfaces.

### 10.12 Settings `/settings`

Settings must be the least decorative surface.

Prioritize:

- strong form hierarchy;
- Broker Connections security explanation;
- clear READ credential semantics;
- explicit success/error/disabled states;
- field labels always visible;
- destructive/session-revoke controls visually separated;
- raw credentials never displayed after submission and never written to Web Storage;
- synthetic preview must keep real broker-credential submission disabled.

## 11. Components and design-system migration

Do not style pages independently.

Implement in this order:

1. **Tokens** — palette, typography, spacing, radius, elevation, material, motion, semantic states.
2. **Primitives** — buttons, inputs, badges, cards, state blocks, tables, skeletons, dialogs/sheets.
3. **Shell** — topbar, desktop nav, mobile navigation, content frame, global status/degraded banners.
4. **High-value product surfaces** — Overview/Portfolio/Assets.
5. **Operational surfaces** — Watchtower/Research/Risks/Decisions/Plans.
6. **Safety/utility surfaces** — Execution/Journal/System/Settings.
7. **Atmospheric enhancement** — ambient gradients / optional CSS spatial identity.
8. **Hardening** — accessibility, responsive, performance, visual regression.

Do not create a second `tokens.css`, parallel component library or page-local mini design system.

Do not introduce Tailwind, MUI, shadcn, Chakra, Bootstrap or another UI framework unless a separate approved dependency/architecture decision proves why the existing accepted CSS/React design system cannot support the requirement.

## 12. Canonical operational-state styling

Preserve the exact vocabulary:

`READY | PARTIAL | STALE | DEGRADED | BLOCKED | ERROR | OFFLINE | RECOVERING | OWNER_ACTION_REQUIRED`

Status must never rely on color alone.

Each state needs:

- semantic color;
- readable label;
- optional icon/shape;
- appropriate background/edge treatment;
- dark/light contrast validation.

Suggested emotional hierarchy:

- READY: calm green, low visual noise;
- PARTIAL / STALE / DEGRADED / RECOVERING / OWNER_ACTION_REQUIRED: amber/yellow family with distinct labels/icons;
- BLOCKED / ERROR: red family, stronger containment;
- OFFLINE: neutral/slate, not necessarily danger red unless loss creates a dangerous condition.

## 13. Accessibility requirements

Target **WCAG 2.2 AA** minimum.

Required:

- normal text contrast >= 4.5:1;
- large text / essential UI graphical boundaries >= 3:1 where applicable;
- visible `:focus-visible` state on every interactive element;
- keyboard navigation and logical focus order;
- touch target >= 44 × 44 px for primary mobile controls;
- labels not replaced by placeholder-only text;
- semantic HTML/landmarks preserved;
- status not communicated by color alone;
- motion reduced under `prefers-reduced-motion`;
- material/transparency has an opaque legible fallback;
- test forced-colors/high-contrast behavior for critical controls;
- no focus hidden behind sticky/floating bars;
- error text must be associated with the relevant field/control.

Add support for `prefers-contrast` / `prefers-reduced-transparency` only as progressive enhancement where browser support permits; never depend on them for baseline readability.

## 14. Performance requirements

The redesign must feel premium because it is fast, not despite being heavy.

Targets for real hosted routes:

- LCP <= **2.5 s** at p75 target conditions;
- INP <= **200 ms**;
- CLS <= **0.1**;
- no obvious scroll jank on mid-range mobile hardware;
- animations target 60 fps when the display/browser supports it;
- no continuously running heavy WebGL loop on core authenticated pages;
- optional visual effect code must be lazy-loaded and non-blocking;
- avoid layout-thrashing animation properties;
- preserve responsive usability if blur/shader features are unavailable.

For each design increment, record bundle-size change. A purely visual foundation/shell increment should not casually add a large runtime dependency. Any material JS increase requires justification and a rollback path.

## 15. Responsive acceptance matrix

Preserve the repository’s canonical required viewports:

- **360 px** mobile;
- **768 px** tablet;
- **1440 px** desktop.

Supplemental checks may include 390/430, 1024 and 1920 px, but must not replace the canonical matrix.

At every canonical viewport verify:

- no horizontal document overflow;
- no overlapping header/nav/page content;
- no transparent nav over unreadable content;
- all routes reachable;
- card/table text remains legible;
- controls remain within viewport;
- drawers/sheets scroll internally when needed;
- sticky/fixed elements do not cover focused controls;
- synthetic preview warning remains visible and readable;
- degraded/error banners do not collapse layout;
- touch targets are usable on 360 px.

## 16. Testing and regression strategy

Preserve and extend the existing CSS-token regression guard that ensures every no-fallback `var(--token)` resolves to the canonical default `:root` token set.

Minimum focused tests for an authorized design refresh:

1. token contract test for all new palette/material/motion aliases;
2. light/dark theme token completeness;
3. no unresolved CSS custom properties;
4. canonical operational states unchanged;
5. canonical viewport matrix unchanged;
6. `prefers-reduced-motion` behavior;
7. mobile nav hidden/closed by default and correctly isolated when open;
8. nontransparent/legible navigation material computed style;
9. no document horizontal overflow at 360/768/1440;
10. keyboard/focus smoke across navigation and forms;
11. representative visual screenshot assertions with animations disabled;
12. no browser console errors in core route smoke;
13. CSS/JS build/type/lint/test success;
14. CSP-safe asset loading — no accidental remote font/shader/analytics fetches.

Representative screenshot set should include at minimum:

- login/synthetic preview;
- overview;
- portfolio;
- watchtower;
- research;
- decisions/plans;
- settings;
- mobile nav open and closed;
- dark and light theme for high-value surfaces;
- one reduced-motion run.

Use deterministic fixture data; visual regression must not depend on volatile timestamps or random shader seeds.

## 17. Implementation increments

When authorized, do not land the entire redesign as one giant PR. Use coherent reviewable increments while remaining inside the owning authorized package.

Recommended sequence:

### Increment A — Design-system foundation

Allowed focus:

- `tokens.css`;
- `base.css`;
- design-system contracts/tests;
- no product-semantic changes.

Exit evidence:

- token completeness;
- light/dark accessibility;
- build/type/lint/tests;
- visual gallery evidence;
- no route behavior changed.

### Increment B — Spatial shell and navigation

Allowed focus:

- `app-shell.css`;
- minimal shell TSX only where required for navigation/accessibility;
- mobile sheet/dock behavior;
- global status/degraded presentation.

Exit evidence:

- 360/768/1440 shell screenshots;
- keyboard/focus navigation;
- no overlap/overflow;
- degraded mode remains usable.

### Increment C — Portfolio and Assets

Allowed focus:

- portfolio/assets presentation only;
- no new financial calculation semantics.

Exit evidence:

- complete/partial/empty/stale fixtures;
- multi-currency no-illegal-aggregation proof;
- 360/768/1440 visual evidence.

### Increment D — Watchtower / Research / Risk / Decisions / Plans

Modernize high-density analytical surfaces while preserving exact data contracts and state semantics.

### Increment E — Execution / Journal / System / Settings

Modernize safety and utility surfaces with especially conservative motion/material use.

### Increment F — Atmosphere and optional spatial brand layer

Only after core UI is already excellent without it.

Prefer CSS-native ambient gradients/pseudo-3D. Add no WebGL dependency unless separately justified.

### Increment G — Visual/performance/accessibility hardening

Cross-route regression, reduced motion, high contrast, bundle/performance review and final visual consistency pass.

Every increment follows exact repository branch/PR/CI/READY/squash/post-merge rules. A new commit invalidates prior exact-head final evidence.

## 18. Preflight and CI

Before expensive exact-head CI for each implementation increment, run all applicable repository baselines plus Web-specific checks.

Permanent project baseline includes, where applicable:

```text
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python scripts/check_v10_repository_boundaries.py
python scripts/check_v10_engineering_governance.py
python scripts/check_v10_documentation_consistency.py
python scripts/check_gpt_recovery_consistency.py
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest -q --cov --cov-branch --cov-fail-under=60
```

Web preflight must include the repository’s accepted commands for:

```text
npm ci
npm run typecheck
npm run lint
npm test
npm run build
```

Run Playwright/browser evidence where the increment changes rendered behavior.

Do not weaken a gate, coverage, secret scan, type check, CSP/security control or responsive test to land appearance changes.

## 19. Rollback strategy

Visual refresh increments should avoid database/API migrations whenever possible.

Rollback must remain simple:

- previous accepted `main` remains the source rollback point;
- no design increment may require migration of financial state merely to render correctly;
- new assets must be source-controlled/reproducible and removable;
- optional spatial effects must fail independently without taking down the shell;
- if a visual increment degrades mobile accessibility/performance, revert that focused increment without reverting unrelated Core/security work.

## 20. Definition of Done for the complete visual refresh

The refresh is complete only when all of the following are true on accepted `main` after required post-merge verification:

- one coherent Premium Spatial Financial OS visual language is visible across all existing routes;
- dark and light themes are both intentional, not inversions;
- navigation is a distinct quiet functional layer while content remains highly legible;
- financial surfaces are mostly opaque and exact data remains visually unambiguous;
- 360/768/1440 responsive acceptance passes with no overlap or horizontal document overflow;
- mobile navigation is stable, accessible and visually isolated;
- typography is modern, readable and tabular for financial values;
- motion is tokenized, subtle and reduced-motion safe;
- optional spatial/3D effects are atmospheric only and have no effect on financial truth;
- all operational states remain exact and accessible;
- no real execution, broker authority, identity, tenant or security semantics changed merely for design;
- Web typecheck/lint/test/build and applicable browser tests all succeed;
- repository-wide applicable exact-head checks all conclude `success`;
- zero unresolved blocking review threads;
- full diff review confirms no parallel frontend/design stack was introduced;
- post-merge Regression Shield and any owning Web/deployment acceptance gates succeed;
- real hosted browser evidence confirms the accepted release looks correct on modern phone and desktop without relying on OWNER home infrastructure.

### Final visual quality bar

The site should look unmistakably more modern than the pre-refresh UI without becoming harder to use.

A successful result should communicate, within seconds:

> “This is a serious financial operating system: precise, calm, alive, spatial, modern and trustworthy.”

The interface should still be excellent when every ambient animation and transparency effect is disabled. That is the quality test: **structure, typography, spacing and hierarchy carry the product; effects only amplify them.**

---

## 21. Current implementation baseline to reuse

At drafting baseline `235ebfd386d46b74fb2428085ac233aa4494d696`:

- Web runtime is React/Vite/TypeScript and already has Playwright coverage;
- canonical styles live under `apps/web/src/design-system` and `apps/web/src/app-shell`;
- the design-system contract already requires responsive viewports `[360, 768, 1440]`;
- the design-system contract already guards canonical operational vocabulary;
- the post-#379 guard requires no-fallback Web CSS custom properties to resolve from the canonical default `:root` token set;
- the shared shell uses the accepted route list and must remain the single application shell.

Treat those as reusable foundations, not reasons to rewrite the frontend.

## 22. Official external design references reviewed for this brief

These references are inspiration/engineering context only; they do not override repository authority and their visual assets/code must not be copied.

- Linear, UI refresh (2026-03-12): `https://linear.app/changelog/2026-03-12-ui-refresh`
- Linear, design process: `https://linear.app/now/behind-the-latest-design-refresh`
- Apple Human Interface Guidelines — Materials: `https://developer.apple.com/design/human-interface-guidelines/materials`
- Apple — Adopting Liquid Glass: `https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass`
- Material Design 3 / M3 Expressive: `https://m3.material.io/`
- Framer — Shaders (2026-03-24): `https://www.framer.com/updates/shaders`
- Framer — Interactive Liquid/Logo Gradient (2026-07-16): `https://www.framer.com/updates/interactive-shaders-liquid-logo`
- Webflow — Interactions with GSAP: `https://help.webflow.com/hc/en-us/articles/42832301823635-Intro-to-Interactions-with-GSAP`
- Webflow — design variables in interactions: `https://webflow.com/updates/animate-variables-gsap`

At implementation time, re-check current official browser/framework/accessibility support before introducing any material new technology. `latest` is not automatically better than the accepted stack.

## 23. Explicitly approved design-direction checklist

This brief records the OWNER’s approval of the following eight design directions:

1. modernize the complete color system;
2. introduce real surface depth/elevation;
3. redesign shell/navigation as a distinct spatial functional layer;
4. modernize typography and financial-number hierarchy;
5. introduce a coherent restrained motion system;
6. use 3D/shader effects sparingly and never distort financial data;
7. redesign every key product surface coherently;
8. evolve the existing design system first, rather than add page-local effects.

Implementation remains subject to canonical V10 sequence and acceptance gates.