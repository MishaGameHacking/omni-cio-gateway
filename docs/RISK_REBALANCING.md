# Evidence-backed portfolio research

Source review: **2026-10-17**. This is the current implementation contract for
F04/F06/F08–F14/F17/F21, not a completion claim for the investment plan.
See [MASTER_PLAN.md](MASTER_PLAN.md) for the approved target and
[PLAN_STATUS.md](PLAN_STATUS.md) for code, release, delivery and device evidence.

## Product contract

Personalized understandable assistance is not autonomous order execution or a
promise that bankruptcy/losses are impossible. Calculations are deterministic and
consume no LLM tokens. Production figures come from the authenticated user's
broker or reviewed evidence. Synthetic prices and ratings exist ONLY in tests.

## Implemented paths and limits

- GET /analysis/research: authenticated, identity/token-scoped five-minute cache,
  also bound to profile digest, evidence revision and freshness boundaries. A
  concurrent profile/evidence change or crossed time boundary rejects the stale
  result. Uses the existing read-only portfolio reader, bounded GetAssetFundamentals
  (at most 100 asset IDs) and News (100 latest items). News matches instrument UID,
  not ambiguous names. Only short headlines/source/time, not full articles.
  This is not a complete global-news feed: pagination/backfill/provider contracts
  and macro/sector propagation are not implemented.
- The native **«Действия → Анализ»** section shows security facts, missing
  coverage, explanations and broker-view/search buttons. Per-instrument research
  is also reachable from portfolio instrument details. Collection runs on a
  client request; it is not yet a separate background research job. F11.1's
  independent portfolio-monitoring scheduler does not make this research
  collector autonomous.
- `collect_research` still selects the first 100 aggregated positions. Responses
  expose examined/total counts; incomplete valuation prevents a whole-portfolio
  historical risk result. This limit remains open under F11/F21 and must not be
  presented as a full pass over 2000 positions.
- Configured user limits only. Default profiles are not user agreement. assetUid,
  instrument name and brand are NOT treated as verified issuer/group identifiers.
- Append-only, content-addressed imports of issuer identity, agency ratings,
  statements and adjusted total returns. No public write endpoint. A real provider
  audit reference and publication/check/expiry dates are required. The importer
  validates metadata, NOT document truth. Agency feeds/report parsers are separate.
- Empty evidence produces missing-data states, not invented ratings, safe scores,
  default probabilities or a personal buy list.

## Ratings and statements

`credit_evidence.py` currently supports ACRA (RU) and Expert RA ru... national
long-term scales, retaining agency and scope. NKR and NRA remain missing; the
approved four-agency AAA–BBB- product rule is tracked separately in F04/F09.
A displayed rating is not proof that the complete purchase-admission policy is
implemented.
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

The live research path calls `risk_math.py` when verified inputs are complete.
`portfolio_risk.py` and `risk_preview.py` also contain separate calculation and
preview helpers; their presence does not expose a complete planner through the API.

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

`portfolio_risk.py` contains `reduction_plan` and `preview_one_lot_buy` helpers.
They are not a production portfolio optimizer and are not wired as an executable
plan in `/analysis/research`. There is no `backend/rebalance.py` in the current
tree. Earlier notes about an isolated draft and its 20 local tests are historical
work-session evidence, not tests or a delivered module in this repository.

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

The research-card action in `PortfolioResearchPanel.kt` attempts ACTION_VIEW
targeted to ru.tinkoff.investing, the package in the
bank's official RuStore listing. When absent or the version cannot handle that
URL, show an explanation and offer the official page and copyable ticker/ISIN/name.
No private scheme, order quantity, access token, account ID or trading action is
sent to the broker. No permission to enumerate all packages is required.
Successful intent dispatch does not prove the correct security opened in a
particular broker version; real-phone verification remains necessary. The app
never presses Buy/Sell or confirms a trade.

## Validation / rollout

Normal backend, Android and quality checks must pass before merge. The ordinary
Timeweb deployment workflow remains paused; verified Moscow updates use the
separate workflows recorded in [PLAN_STATUS.md](PLAN_STATUS.md). Documentation
review does not prove paid inference, a provider subscription or live evidence
coverage. A client connected to a server without this endpoint gets an explicit
unavailable message.

Implementation sources: [research route](../backend/portfolio_research.py),
[evidence store](../backend/research_store.py),
[credit evidence](../backend/credit_evidence.py), [risk math](../backend/risk_math.py),
[planning helpers](../backend/portfolio_risk.py),
[Android research panel](../app/src/main/java/ru/omnicio/app/ui/research/PortfolioResearchPanel.kt).

Current Android support is Android 15+ (`minSdk=35`, compile/target 36); the
installation and upgrade evidence requirements are in
[APK_INSTALLATION.md](APK_INSTALLATION.md). Emulator verification does not prove
the broker-card handoff or a self-update on the owner's phone.

Remaining: real licensed agency/report imports, issuer/group identity and fund
look-through, full adjusted histories, global/macro/sector evidence, walk-forward
validation and stress coverage, a reviewed candidate strategy and rebalance plan,
verified live-source operation and device/broker-app tests. The approved product
is limited to five invited accounts; applicability of the rules for personal
investment instructions and data processing is an open F23 requirement before
expanding access. A disclaimer is not a compliance implementation.

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
