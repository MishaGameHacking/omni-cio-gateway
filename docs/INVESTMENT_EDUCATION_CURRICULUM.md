# Analyst AI — investment education curriculum

Date: 2026-10-13. This is a product/content specification, not personal investment advice.
The two owner-provided `share.google` redirects could not be fetched, so their text was not
copied, summarized or silently reconstructed. The curriculum below is original and was checked
against official educational material linked at the end.

## Learning outcome

A beginner should be able to answer five questions before pressing a broker button:

1. What am I buying and where does its result come from?
2. What can make me lose money, need cash early or be unable to sell?
3. How does this position change the risks already present in my portfolio?
4. Which facts and expectations support the decision, and how current are they?
5. What would make me do nothing, wait, reduce the amount or review the decision?

## Course sequence

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

## Product improvements derived from the research

1. **Education hub:** implemented first native version with filters and expandable lessons.
2. **Contextual lesson:** a risk/recommendation card can link to the exact lesson explaining its term.
3. **News impact map:** Pulse should show the mechanism and portfolio exposure, not a sentiment badge alone.
4. **Source quality:** official issuer/regulator/exchange source first; secondary analysis explicitly labelled.
5. **Plain-language mode:** lead with ruble impact and one sentence; math, assumptions and sources expand below.
6. **Knowledge checks:** future non-graded questions after lessons; no gamified pressure to trade.
7. **Progress storage:** future local/account progress must not affect portfolio analysis or model risk score.
8. **Safety separation:** learning completion never unlocks trading permissions or implies suitability.

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
