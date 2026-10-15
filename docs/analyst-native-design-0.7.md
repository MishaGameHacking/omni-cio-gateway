# Analyst AI 0.7 — native reference implementation

The 15 October owner reference replaces the old brokerage-style app shell.

## Application structure
- Primary destinations: Главная, Портфель, Рынок, Обучение, Профиль.
- Рекомендации, Риски, События and Сообщения are secondary screens, not extra bottom tabs.
- The dashboard is separate from the portfolio. Portfolio views are Структура, Активы and Динамика.
- Broker operations, account analytics, instrument details, education links, encrypted session recovery and the update gate retain their existing data paths.

## Visual system
Original native vector brain, robot, globe and filled neon glyphs; midnight blue glass surfaces; cyan edges; violet-blue action buttons; consistent typography, 20dp screen margins and compact 20dp cards. Light and system modes remain supported. Existing explicit preferences are preserved; a new installation starts in the reference midnight theme.

Every custom card and root now supplies an explicit on-colour. Normal text is checked against a 4.5:1 contrast target. Actions have at least 48dp targets; primary actions are at least 52dp. Selection animation is finite, respects the saved preference, system animation enablement and lifecycle. No animated GIF collection or continuous shader loop is introduced.

## Data integrity
The reference's balances, gains, suggested stock returns and 28/100 score are not product data. The release does not fabricate them. The chart uses validated, saved observations and retains an accessible value table; zeroes do not replace missing observations. Read-only access and broker source attribution remain intact. The market list is explicitly limited to the connected portfolio and is not falsely presented as a full exchange catalogue.

## Acceptance
Android lint and all APK variants must pass; signed upgrade compatibility and Android 13/16 installation must pass. Theme persistence, 200% fonts, educational navigation and existing mathematical/authentication/update tests remain required. A passing build alone is not a claim that every physical handset has been tested.

Primary references: https://developer.android.com/guide/topics/ui/accessibility/apps and https://developer.android.com/reference/kotlin/androidx/compose/material3/package-summary#LocalContentColor()
