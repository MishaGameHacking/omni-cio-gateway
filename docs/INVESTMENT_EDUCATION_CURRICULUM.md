# Analyst AI — investment education curriculum

Content specification created **2026-10-13**; implementation and navigation
reviewed **2026-10-17**. This is original educational content, not personal
investment advice. The two owner-provided `share.google` redirects were unreadable
in the original research session, so their text was not copied, summarized or
reconstructed. The source map below preserves that research provenance.

The approved [MASTER_PLAN.md](MASTER_PLAN.md) keeps the existing Education
section but pauses its expansion. Updating this document does not authorize
new lessons, quizzes, progress tracking or model-backed teaching. Current
release and device evidence belongs in [PLAN_STATUS.md](PLAN_STATUS.md).

## Current native catalogue

Open **«Профиль → О приложении → Обучение»**. The screen uses category filters,
expandable lessons, a fixed accessible Back action and official source links.
Selected category and expanded lesson use `rememberSaveable`; there is no
learning-completion record, account progress or knowledge-check engine.

The current [EducationCatalog.kt](../app/src/main/java/ru/omnicio/app/ui/education/EducationCatalog.kt)
contains nine lessons:

| ID | Lesson |
| --- | --- |
| `start-plan` | Сначала цель, срок и резерв |
| `market-mechanics` | Как устроена сделка на бирже |
| `asset-types` | Акции, облигации, фонды и деньги |
| `diversification` | Диверсификация без иллюзий |
| `credit-ratings` | Кредитный рейтинг: полезный сигнал, не гарантия |
| `news-impact` | Как новости двигают рынок |
| `statements` | Финансовая отчётность простыми словами |
| `behavior` | Психология инвестора и пауза перед решением |
| `fraud-and-hype` | Мошенничество, хайп и обещания без риска |

[EducationScreen.kt](../app/src/main/java/ru/omnicio/app/ui/education/EducationScreen.kt)
is native Compose content. It does not fetch a user's portfolio, call a model,
place an order or treat lesson completion as proof of suitability.

## Learning outcome

A beginner should be able to answer five questions before pressing a broker button:

1. What am I buying and where does its result come from?
2. What can make me lose money, need cash early or be unable to sell?
3. How does this position change the risks already present in my portfolio?
4. Which facts and expectations support the decision, and how current are they?
5. What would make me do nothing, wait, reduce the amount or review the decision?

## Content topics

### 1. Personal foundation

- goal, horizon, regular contribution and emergency reserve;
- difference between saving, investing and speculation;
- loss in rubles as well as percent;
- why forced selling can be more dangerous than ordinary price fluctuation.

### 2. Market mechanics

- investor, broker, exchange, clearing and depository roles;
- market and limit orders; liquidity and spread;
- price, dividend/coupon, commission and tax as separate parts of result;
- settlement date, ownership record and corporate-action dates.

### 3. Instrument families

- shares: ownership, business result, valuation and dividends;
- bonds: debt, coupon, maturity, rate/duration, liquidity and credit risk;
- funds: pooled holdings, costs, benchmark and hidden overlap;
- cash/money-market instruments: reserve and liquidity role;
- derivatives only after the user understands leverage and nonlinear losses.

### 4. Portfolio construction

- asset allocation tied to goal and horizon;
- diversification both across and inside asset classes;
- economic issuer group, sector, currency, country, rate and commodity dependencies;
- why many tickers can still mean one risk;
- rebalancing with new cash before unnecessary selling, while considering lots, tax and costs.

### 5. Credit quality

- rating agency, rating scale and rated object are mandatory fields;
- rating date, outlook/watch and withdrawal status matter;
- a rating estimates one aspect — credit risk — and is not a buy/sell signal or repayment guarantee;
- national and international scales and different agencies are not averaged as ordinary numbers;
- missing/stale/withdrawn ratings remain unverified rather than “safe”.

### 6. Company statements

- revenue and its drivers;
- operating margin and one-off items;
- operating cash flow, capital expenditure and free cash flow;
- debt, interest coverage and maturity schedule;
- dilution, dividends/buybacks and governance;
- banks and insurers require sector-specific metrics rather than industrial-company ratios.

### 7. News and the market

A news card must explain a mechanism, not merely repeat a headline:

`primary-source fact → difference from expectations → affected cash flow/rate/FX/commodity/
funding channel → issuer/sector → actual portfolio exposure → time horizon → uncertainty`.

Required card fields:

- **What happened:** one verified sentence;
- **What the market expected:** only when supported, otherwise “expectation not verified”;
- **Why it can matter:** revenue, cost, discount rate, credit, FX, commodity or regulation;
- **Who is exposed:** companies/sectors and the user’s actual positions;
- **When:** intraday, next report, debt maturity or multi-year effect;
- **What can invalidate the conclusion:** explicit alternatives;
- **Source and time:** primary link, publication time and retrieval time.

The app should distinguish:

- official fact from commentary or rumor;
- company-specific event from sector/macro event;
- price movement from a demonstrated causal explanation;
- short-term volatility from a change in long-term business value.

### 8. Fraud and decision hygiene

- verify the organization independently from an advertisement;
- guaranteed high return, artificial urgency and requests for secrets are danger signs;
- screenshots, influencer profit claims and closed chats are not evidence;
- never send passwords, one-time codes, seed phrases or API tokens;
- show a short “pause checklist” before high-risk/complex-instrument actions.

## Implementation boundaries and deferred ideas

The topics above are content-design guidance, not a claim that all described
news-card fields or interactions are implemented in production. Psychology is
represented by the separate `behavior` lesson in the current nine-lesson catalogue.

| Area | Current status |
| --- | --- |
| Education hub | Native filters, expandable lessons and source links exist. |
| Contextual lesson from a risk/action card | A general deep-link mechanism to an exact lesson is not implemented. |
| News impact map | The full source-to-portfolio causal map remains F13. The old «Пульс» navigation name is historical; current routes are documented in WORKSPACE_UI. |
| Source quality and plain language | Content and presentation requirements; they do not prove live-source validation or completion of every research-card field. |
| Knowledge checks and learning progress | Not implemented; expansion remains paused by the approved plan. Saving the selected filter is not a completion record. |
| Learning versus investment permissions | Lessons grant no trading rights and provide no automated suitability determination. |

Current navigation: [WORKSPACE_UI.md](WORKSPACE_UI.md). Current portfolio-research
limits: [RISK_REBALANCING.md](RISK_REBALANCING.md).

## Source map

- Moscow Exchange School — beginner catalogue and “С чего начать инвестиции”:
  https://school.moex.com/courses/level/beginner
  https://school.moex.com/articles/s-chego-nachat-investicii-poshagovaya-instrukciya
- Moscow Exchange School — share mechanics, result and risks:
  https://school.moex.com/articles/investicii-v-akcii-dlya-nachinayushchih-mekhanika-raschet-riski
- Investor.gov — asset allocation and diversification:
  https://www.investor.gov/introduction-investing/getting-started/asset-allocation
- Investor.gov — credit-rating meaning and limitations:
  https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/updated-8
- Bank of Russia / Financial Culture:
  https://fincult.info/
- Bank of Russia — current credit-rating decisions and national-agency context:
  https://cbr.ru/finm_infrastructure/ra/rsd/

These links are references for deeper study. Analyst AI must not copy protected courses or
represent third-party material as its own. Regulations, tax rules and available instruments are
time-sensitive and require current verification before being shown as facts.
