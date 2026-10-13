# Evidence-backed portfolio research

## Product contract

Personalized understandable assistance is not autonomous order execution or a
promise that bankruptcy/losses are impossible. Calculations are deterministic and
consume no LLM tokens. Production figures come from the authenticated user's
broker or reviewed evidence. Synthetic prices and ratings exist ONLY in tests.

## Implemented paths and limits

- GET /analysis/research: authenticated, identity/token-scoped five-minute cache.
  Uses the existing read-only portfolio reader, bounded GetAssetFundamentals
  (at most 100 asset IDs) and News (100 latest items). News matches instrument UID,
  not ambiguous names. Only short headlines/source/time, not full articles.
  This is not a complete global-news feed: pagination/backfill/provider contracts
  and macro/sector propagation are not implemented.
- The Ideas panel shows security facts, missing coverage, ordinary-language
  explanations and broker-view/search buttons. Collection refreshes in foreground;
  it is not yet a separate background research job. Existing AI scheduler unchanged.
- Configured user limits only. Default profiles are not user agreement. assetUid,
  instrument name and brand are NOT treated as verified issuer/group identifiers.
- Append-only, content-addressed imports of issuer identity, agency ratings,
  statements and adjusted total returns. No public write endpoint. A real provider
  audit reference and publication/check/expiry dates are required. The importer
  validates metadata, NOT document truth. Agency feeds/report parsers are separate.
- Empty evidence produces missing-data states, not invented ratings, safe scores,
  default probabilities or a personal buy list.

## Ratings and statements

ACRA (RU) and Expert RA ru... national long-term scales retain agency and scope.
International scales and structured-finance ratings are not coerced into them.
Latest action wins, including withdrawal. Issuer rating does not become a bond
rating, particularly for subordinated debt. Different agency opinions are not
averaged into a fabricated numerical rating. Buying low-rated debt merely to
fill a diversification bucket is not a safety strategy.

A rating is not a calibrated default probability. EAD * PD * LGD requires a sourced
PD on the same horizon; no PD table is invented. Expected losses add even with
dependence. One-or-more-default risk uses union bounds, not independence. Bonds
of the same issuer share its default event.

Statements use one accounting period/standard/currency: net debt / positive EBITDA,
EBIT / positive interest, operating cash flow / positive net income. Negative or
missing denominators are not reassuring ratios. Banks/insurers require their own
capital/reserve model, not generic corporate leverage. Broker fundamentals are
labelled broker metrics, not audited statements. GetAssetReports supplies a
publication calendar, not a report's contents.

## Mathematics actually implemented

- Same-date adjusted simple total returns, minimum 120 common sessions. Reject
  missing dates, NaN, unadjusted close series or different currencies. No fabricated
  zero returns/holiday filling.
- Sample covariance shrunk to its diagonal, explicitly chosen alpha 0.2. This is
  NOT automatically fitted Ledoit-Wolf shrinkage.
- Empirical VaR and Expected Shortfall with fractional boundary probability mass;
  thin-tail warning. These are historical conditional estimates.
- Joint moving-block bootstrap: defaults 5-session blocks, 20-session horizon,
  500 paths, seed 0; cross-asset co-movement and buy-and-hold weight drift preserved.
  Residual cash has zero simulated return. Floor-breach frequency and a Wilson
  simulation-count interval are not real-world bankruptcy probabilities. Fees,
  future withdrawals, unprecedented defaults and model uncertainty are omitted.
  The 80% capital floor is a documented scenario, not a user-selected loss limit.
- Inverse Herfindahl concentration and actual peak-to-trough drawdown. More tickers
  do not imply independent risks. No investor return forecast is manufactured.

## Rebalancing plan: NOT integrated

A separate local whole-lot cash-first planning draft was written and tested, but
writing backend/rebalance.py was blocked by the tool. That file is NOT part of this
repository change; no substitute or alternate upload was used. Its 20 isolated
tests are not counted as CI tests of this branch.

New-security catalog, user target-policy review, real transaction-cost/tax checks,
settlement rules and the production recommendation planner remain unfinished.
The read API reports candidate_selection_state=verified_universe_required and
analysis_is_complete=false. A reminder to review a position already over the
user's configured limit is NOT a complete trade plan. No new buy quantities are
served and no orders are created.

## T-Invest handoff

Only official HTTPS instrument-page patterns: /invest/stocks/{ticker}/,
/invest/bonds/{ticker}/, /invest/etfs/{ticker}/. OFZ tickers can differ from ISIN;
both are shown. Funds can have a trailing @. ISIN may be a bond fallback, but
existence of every generated individual URL is not guaranteed.

Android attempts ACTION_VIEW targeted to ru.tinkoff.investing, the package in the
bank's official RuStore listing. When absent or the version cannot handle that
URL, show an explanation and offer the official page and copyable ticker/ISIN/name.
No private scheme, order quantity, access token, account ID or trading action is
sent to the broker. No permission to enumerate all packages is required.
Successful intent dispatch does not prove the correct security opened in a
particular broker version; real-phone verification remains necessary. The app
never presses Buy/Sell or confirms a trade.

## Validation / rollout

Normal backend, Android and quality checks must pass before merge. Existing
Moscow server, authentication, keys and paused deployment remain unchanged. No
new servers, model calls, trading writes or agency subscriptions were ordered.
A client connected to an old server gets an explicit unavailable message for this
endpoint. Source integration is not deployment or proof of live broker inference.

Remaining: real licensed agency/report imports, issuer/group identity and fund
look-through, full adjusted histories, global/macro/sector evidence, walk-forward
validation and stress coverage, a reviewed candidate strategy and rebalance plan,
production rollout, device/broker-app tests and compliance review before public
personalized advice. A disclaimer is not a compliance implementation.

## Primary references checked 2026-10-13

- https://developer.tbank.ru/invest/services/instruments/methods
- https://acra-ratings.ru/about-ratings/scales/
- https://acra-ratings.ru/compliance/2685/
- https://web.stanford.edu/~boyd/papers/cvx_portfolio.html
- https://www.risk.net/journal-risk/2161159/optimization-conditional-value-risk
- https://www.tbank.ru/invest/stocks/SBER/
- https://www.tbank.ru/invest/bonds/SU26232RMFS7/
- https://www.tbank.ru/invest/etfs/TPAY/
- https://www.rustore.ru/catalog/app/ru.tinkoff.investing
- https://developer.android.com/training/package-visibility/use-cases

The bank pages are references for URL conventions, not asset recommendations or
current price sources in this change.
