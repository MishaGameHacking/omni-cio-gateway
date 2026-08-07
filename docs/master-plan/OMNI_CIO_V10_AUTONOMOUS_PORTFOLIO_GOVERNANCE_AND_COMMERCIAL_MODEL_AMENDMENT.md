# Omni-CIO V10 — Autonomous Portfolio Governance / Zero-Custody / Commercial Model Amendment

Status: **OWNER-APPROVED PLANNING AUTHORITY — IMPLEMENTATION NOT STARTED BY THIS AMENDMENT**  
Effective date: **2026-08-07**  
Scope: product mission, autonomous portfolio governance, Russian-market universe, sanctions/custody policy, Cortex role, user negotiation, confirmed execution, zero-custody, fixed-term paid access, automatic updates, Russian-law production gates.

## 1. Why this amendment exists

This amendment makes the product itself unambiguous before later V10 implementation work begins.

Omni-CIO V10 is **not** primarily a dashboard, chat bot, report viewer or trading robot. Those are product surfaces/tools around the central capability.

The central product is:

> **A personal autonomous portfolio-governance system for the Russian investment market that continuously monitors every held asset, detects deterioration/opportunity, gathers and verifies evidence, evaluates the whole allowed broker universe, constructs a concrete portfolio action proposal, explains the expected portfolio effect and risks, negotiates revisions with the OWNER, and may execute only the exact OWNER-approved immutable proposal through the protected deterministic money path.**

This is a V9 -> V10 productization/migration clarification. It does not authorize a greenfield rewrite of V9 Risk, Credit, Strategy, Optimizer, Watchtower, Plan, Journal or Real Execution engines.

## 2. Product promise and non-promise

V10 is sold as access to an actively maintained system that provides:

- continuous portfolio control;
- asset-health monitoring;
- risk/concentration/liquidity/currency/custody/sanctions observation;
- evidence-backed research;
- professional diversification logic;
- concrete portfolio restructuring proposals rather than an unranked list of ideas;
- continuous post-decision monitoring;
- clear OWNER communication through Web and Telegram;
- safe confirmed BUY/SELL execution where the optional trading credential is enabled and all gates pass.

V10 must never promise:

- guaranteed profit;
- guaranteed loss avoidance;
- guaranteed sanctions immunity/freeze immunity merely because an issuer is Russian;
- guaranteed prediction of future prices;
- autonomous discretionary Real trading without OWNER approval;
- margin, leverage, uncovered short positions or transfer/withdrawal functionality.

## 3. One autonomous system; Cortex is a bounded specialist tool

### 3.1 Autonomous system

The **system**, not the language model, operates 24/7.

Approved autonomous components include deterministic/event-driven jobs for:

- portfolio snapshot refresh;
- data freshness checks;
- asset-health refresh;
- corporate/fundamental/event change detection;
- risk/concentration/liquidity checks;
- sanctions/custody policy refresh;
- candidate-universe screening;
- materiality prioritization;
- Watchtower/incident lifecycle;
- proposal recomputation when an accepted trigger requires it;
- post-trade reconciliation and post-decision monitoring.

### 3.2 Cortex role

Cortex is invoked by the system or OWNER when language/research/interpretation is useful. Cortex may:

- interpret public disclosures and source text;
- search for missing public evidence through allowlisted research tools;
- explain deterministic Core results;
- summarize conflicting evidence;
- formulate the question the system needs to ask the OWNER;
- conduct the user-facing negotiation when a proposal is rejected/revised;
- convert OWNER natural-language intent into a typed non-authoritative intent for deterministic validation.

Cortex must **not**:

- continuously think without a trigger;
- become the portfolio source of truth;
- assign canonical financial numbers from memory;
- directly select/submit a Real order outside the deterministic Decision/Plan/Execution lifecycle;
- receive raw trading secrets;
- override a hard safety/policy block.

The system may call Cortex internally. Internal system<->Cortex tool traffic is not a user-facing chat transcript, but auditable tool/evidence events must remain reconstructable without exposing hidden model reasoning.

## 4. Portfolio scale and asset-level state

No arbitrary small position-count limit is part of the product contract. The architecture must remain capable of portfolios ranging from one position to hundreds or thousands, subject to measured hardware/runtime limits established by owning WPs.

Each position/instrument receives a versioned `AssetHealthState` containing, where applicable and evidence-supported:

- identity and instrument type;
- portfolio role;
- issuer/credit quality;
- profitability/cash-flow/debt trend;
- valuation inputs/status where the methodology is valid;
- liquidity/tradability;
- market/volatility risk;
- interest-rate/duration risk;
- commodity exposure;
- economic currency exposure;
- concentration contribution;
- corporate actions/events;
- sanctions state;
- custody/settlement/infrastructure risk;
- data completeness/freshness/conflicts;
- last deep-review time and reason;
- health state and materiality priority.

Canonical health states:

`HEALTHY | WATCH | DETERIORATING | REVIEW_REQUIRED | REPLACEMENT_CANDIDATE | CRITICAL | INSUFFICIENT_DATA`

The system must track **direction/trend**, not only the latest point-in-time score.

## 5. Risk-based monitoring intensity

Monitoring resources are allocated by materiality and uncertainty.

- `HEALTHY`: normal scheduled refresh.
- `WATCH`: higher-frequency targeted refresh.
- `DETERIORATING`: deeper financial/corporate/event review.
- `REVIEW_REQUIRED`: portfolio-impact calculation + replacement research if warranted.
- `REPLACEMENT_CANDIDATE`: candidate-universe scan + optimizer run + proposal preparation.
- `CRITICAL`: priority incident, evidence refresh and OWNER notification; unsafe actions remain blocked.
- `INSUFFICIENT_DATA`: no strong recommendation until required evidence is restored.

This avoids using the LLM or expensive deep research equally for every instrument at every cycle.

## 6. Russian-market-only investable universe

V10's commercial/product baseline is **Russian-market-only**.

The candidate universe is built dynamically from instruments available through the supported broker connector(s), then narrowed by policy. A broker exposing an instrument does not automatically make it eligible for Omni-CIO.

The universe pipeline is:

`BROKER_DISCOVERED -> IDENTITY_NORMALIZED -> RUSSIAN_MARKET_POLICY -> SANCTIONS/CUSTODY POLICY -> USER/BROKER ELIGIBILITY -> NO_MARGIN/NO_SHORT -> LIQUIDITY/DATA QUALITY -> ASSET-CLASS RULES -> V10_ALLOWED_UNIVERSE`

The owning implementation must define objective classification rules for "Russian-market" rather than relying on display name alone. At minimum it must consider issuer/jurisdiction, venue, instrument/custody chain and settlement characteristics where relevant.

No fixed whitelist of a few hand-picked tickers is sufficient. The system must be able to evaluate the available universe through staged screening.

## 7. Sanctions and custody hard gate

Sanctions/custody risk is a first-class hard policy, not a cosmetic score.

Canonical sanctions states:

`CLEAR | WATCH | AMBIGUOUS | RESTRICTED | BLOCKED | DATA_STALE`

Rules:

- `BLOCKED` instruments are excluded from new BUY proposals and optimizer candidates.
- `RESTRICTED`, `AMBIGUOUS` or stale status cannot silently become `CLEAR`.
- ownership/control relationships must be considered where source rules make them material; naive exact-name matching is insufficient.
- source identity, list version/date, retrieved time and matching rationale are evidence.
- a currently held instrument becoming `BLOCKED/RESTRICTED` creates an incident/review; it does not authorize blind forced selling if market/legal/settlement conditions make execution unsafe or impossible.

"Russian instrument" is not marketed as a guarantee against blocking/freeze. Custody chain, settlement, currency mechanics and external infrastructure dependency remain explicit risk dimensions.

## 8. Currency and bond exposure model

The system must distinguish nominal/display currency from economic exposure. Where applicable, canonical instrument data separates:

- settlement currency;
- nominal currency;
- coupon/payment currency;
- coupon/index/reference currency;
- FX-linked payout mechanism;
- economic FX exposure;
- custody/payment infrastructure.

This is required so an instrument settled in RUB can still be identified as carrying material USD/CNY/commodity-linked economic exposure when its legal/economic terms support that conclusion.

## 9. Diversification and optimizer mission

Diversification is multi-dimensional, not equal-weight ticker counting.

The optimizer/decision layer must be able to reason over versioned constraints including, as applicable:

- issuer concentration;
- sector concentration;
- asset class;
- credit quality;
- duration/rate sensitivity;
- economic currency exposure;
- liquidity;
- income/cash-flow profile;
- commodity factor exposure;
- correlation/diversification contribution;
- sanctions/custody/infrastructure risk;
- OWNER preferences;
- available own cash;
- lot/instrument trading constraints;
- taxes/fees/spread/turnover costs where reliable inputs exist.

The optimizer may choose:

- `NO_CHANGE`;
- reduce one position;
- fully exit one position;
- add to an existing position;
- replace one asset with one asset;
- split one exposure across two or more assets;
- rebalance multiple positions in one coherent proposal.

There is no requirement that a proposal contain only one replacement instrument.

## 10. Anti-churn / turnover discipline

The system must not trade merely because another candidate scores marginally better.

A restructuring proposal must pass a **material-improvement threshold** after accounting for known/reasonably estimated transaction friction and risk of change.

Required proposal considerations include where data is available:

- commissions;
- bid/ask spread / liquidity;
- tax implications as a constraint or explicit uncertainty;
- loss of desirable current exposure;
- execution uncertainty;
- concentration/correlation changes;
- expected improvement magnitude;
- confidence/data quality.

`NO_CHANGE` is a valid and often preferred output.

## 11. Decision pipeline

Canonical portfolio-governance state machine:

`NORMAL -> ANOMALY_DETECTED -> INVESTIGATING -> EVIDENCE_READY -> PORTFOLIO_IMPACT_CALCULATED -> CANDIDATES_SCREENED -> PORTFOLIO_OPTIMIZED -> PROPOSAL_READY -> OWNER_REVIEW`

OWNER_REVIEW branches:

- `APPROVED`;
- `REJECTED`;
- `REVISION_REQUESTED`;
- `EXPIRED`;
- `BLOCKED_BY_FRESHNESS_OR_POLICY`.

No Real execution occurs before `APPROVED` and a fresh preflight.

## 12. Concrete proposal, not an idea list

The user-facing default is one **system-selected primary proposal**, with exact rationale and portfolio effect.

A proposal must contain, where relevant:

- instruments and exact identities;
- BUY/SELL direction;
- quantities/lots or sizing methodology;
- target/max execution bounds as allowed by the owning execution contract;
- source snapshot IDs and timestamps;
- current vs proposed portfolio allocation;
- expected change in key risks/concentrations/exposures;
- cash impact;
- costs/uncertainties;
- why selected candidates beat rejected finalist candidates;
- conditions that invalidate the proposal;
- expiry;
- immutable plan ID/hash/version.

The system may expose runner-up evidence for transparency, but it must not shift the analytical burden to the user by presenting an unordered catalogue of possible assets as its normal result.

## 13. OWNER negotiation and preference learning

If the OWNER rejects or requests changes, the system must not repeatedly regenerate the same proposal blindly.

Cortex asks a concise question such as what specifically is unacceptable: issuer, sector, duration, volatility, income profile, currency exposure, concentration, timing, price, liquidity or another preference.

The response is converted into a versioned `PreferenceProfile` change or one-time proposal constraint.

Preference classes:

### Soft preferences — OWNER may change

Examples:

- desired income emphasis;
- preferred/avoided sectors;
- desired duration range;
- desired economic currency exposure;
- acceptable volatility/risk target within hard limits;
- preference for fewer/more holdings;
- minimum liquidity preference.

### Hard policy — OWNER cannot override in normal UI/chat

- no margin/leverage;
- no uncovered short;
- no transfers/withdrawals;
- insufficient own cash;
- instrument unavailable/unsupported;
- sanctions `BLOCKED`;
- broken identity/data integrity;
- stale critical data for a decision requiring freshness;
- invalid/expired immutable approval;
- broker/execution uncertainty requiring reconciliation.

The system explains when a requested change is harmful. If it is a soft-risk preference, the OWNER may knowingly accept the explained risk and request a revised proposal. Hard policy remains fail-closed.

## 14. Internal system<->Cortex and user communication

System/Cortex internal requests may include evidence gaps, issuer-event classification, source conflict resolution and user-question drafting.

They are stored as auditable structured events/tool calls, not exposed as hidden chain-of-thought.

When OWNER input is required while the site is closed:

- system opens/updates an incident/task;
- Telegram sends a privacy-safe concise notification;
- the shared Cortex explains what the system needs;
- deep link opens the exact Web context;
- the OWNER response is bound to the incident/proposal identity.

## 15. Notifications and value reporting

Telegram/Web should prioritize material events rather than constant noise.

Examples of valuable notifications:

- asset entered `DETERIORATING/REVIEW_REQUIRED/CRITICAL`;
- sanctions/custody state changed materially;
- material price move together with portfolio-impact context;
- corporate/fundamental evidence changed materially;
- proposal is ready;
- proposal requires OWNER clarification;
- approved order changed state or reconciliation completed;
- system health/data freshness affects analytical confidence;
- periodic portfolio-health summary.

The system may report performance/quality metrics, but must distinguish facts from counterfactual/modelled attribution.

Possible factual/system KPIs:

- portfolio return where valid inputs exist;
- benchmark comparison where methodology is fixed;
- volatility/drawdown;
- concentration and risk-budget utilization;
- income/fees/turnover;
- asset-health distribution/trend;
- material incidents detected/resolved;
- proposal acceptance/rejection/revision counts;
- data freshness and monitoring coverage.

A counterfactual such as "what if the old position had been kept" must be labelled as a modelled scenario, never as realized profit.

## 16. Broker credentials and cash-only execution

V10 supports at most two broker access secrets per Personal Node for this model:

1. **READ token** — monitoring/portfolio/market/account data.
2. **TRADE token** — optional, isolated, only for confirmed BUY/SELL execution.

Transfer/withdrawal token/support is outside V10.

Hard execution invariants:

- `NO_MARGIN`;
- `NO_LEVERAGE`;
- `NO_UNCOVERED_SHORT`;
- BUY only within own available cash after deterministic preflight;
- SELL only within owned/free quantity after deterministic preflight;
- any broker margin-confirmation flag remains false;
- exact OWNER-approved immutable plan;
- fresh preflight immediately before submit;
- one idempotent possible submit;
- ambiguous submit state requires reconciliation, not blind retry;
- submitted != filled without broker evidence.

Cortex never receives the raw TRADE token.

## 17. Zero-custody Personal Node data boundary

The commercial V10 target remains **Personal Node / zero-custody for investment-private state**.

Central Omni-CIO infrastructure must not require custody of:

- broker READ/TRADE secrets;
- portfolio positions/balances;
- broker reports;
- private trading history;
- private Cortex conversation history;
- full Decision Journal private payload;
- Telegram private binding if a local/direct architecture can satisfy the product requirement.

Broker/private-data connections are direct Personal Node -> provider wherever technically possible and contractually permitted. A central proxy that merely forwards private broker data is not treated as "no processing" and requires separate privacy/legal approval.

A `Privacy Firewall` must classify/redact outbound research/telemetry so public research never receives unnecessary private portfolio/account context.

## 18. Central commercial plane

A paid product necessarily requires a narrow central commercial plane. Its purpose is limited to:

- payment/order state;
- license entitlement;
- trial-used state;
- signed release/update metadata;
- anti-abuse/security state necessary for licensing;
- legally required receipt/refund records.

It must not become a shadow portfolio/account database.

The plan must explicitly inventory every central field and retention/legal basis before production.

## 19. Paid access model

Commercial access model:

- 7-day full-feature trial subject to all normal safety/legal gates;
- fixed-term 1-month access;
- fixed-term 3-month access;
- fixed-term 6-month access;
- fixed-term 12-month access.

Rules:

- no automatic renewal;
- no recurring charge;
- no saved payment method for future automatic debits as a V10 requirement;
- each renewal is a new explicit user-initiated payment;
- pricing may be decided later; architecture must not hard-code commercial prices into Core.

License entitlement is bound to a Personal Node cryptographic identity/recovery mechanism rather than requiring a central profile containing portfolio/private identity data.

Trial anti-abuse must resist simple uninstall/reinstall and local-clock rollback while acknowledging that no client-side DRM is mathematically unbreakable.

## 20. Expired subscription behavior

Expiry never deletes or takes custody of user-owned local data.

After expiry, premium/runtime capabilities may be disabled, including live monitoring, new research, Cortex, Watchtower automation, Telegram automation and Real execution.

Always-retained local/recovery functions include:

- license/renewal UI;
- export of user-owned data;
- removal/rotation of local broker secrets;
- data deletion controls;
- legal/privacy documents;
- recovery and Update Agent needed to return to a supported version after renewal.

## 21. Automatic stable updates and version convergence

Users purchase access to the maintained service, not a permanently pinned old build.

Production policy:

- supported active Personal Nodes automatically converge to the current approved `STABLE` version;
- manual installer download is not the normal update path;
- permanent user pinning to an obsolete unsupported production version is not supported;
- update rollout occurs only after repository gates, release provenance, internal/test-node validation and stable promotion;
- an offline node updates on next supported connection before regaining capabilities that require the newer minimum version;
- Update Agent remains available after subscription expiry so a renewed installation can become supported without manual reinstallation.

Security invariants:

- signed update metadata and artifact digest verification;
- rollback/freeze attack protection design;
- atomic/staged install;
- health-check before promotion;
- automatic rollback on failed health;
- updater has no access to broker secrets/private portfolio state;
- Real execution is paused during unsafe update windows;
- no arbitrary command execution from remote update metadata.

Exact technology (for example TUF-compatible implementation) is selected by the owning WP after security/runtime review; the security properties are mandatory even if implementation changes.

## 22. Russian-law design gates

The project must be designed for Russian-law deployment, but engineering documentation must not claim legal compliance solely because code follows this amendment.

Before public/commercial activation, the following gates are mandatory:

- `RU_LEGAL_ARCHITECTURE_REVIEW_COMPLETE`;
- `PD_OPERATOR_DETERMINATION_COMPLETE`;
- `PERSONAL_DATA_FLOW_AND_LOCALIZATION_REVIEW_COMPLETE`;
- `CONSUMER_TERMS_AND_FIXED_TERM_ACCESS_REVIEW_COMPLETE`;
- `PAYMENT_KKT_RECEIPT_REFUND_REVIEW_COMPLETE`;
- `BROKER_TERMS_COMPATIBILITY_COMPLETE`;
- `INVESTMENT_ADVISORY_MODEL_DETERMINED`;
- `AUTOCONSULTING_SOFTWARE_REGULATORY_PATH_DETERMINED`;
- `COMMERCIAL_PRODUCTION_LEGAL_SIGNOFF`.

These are fail-closed launch gates. A developer/AI may prepare technical/legal drafts but cannot self-certify the final legal conclusion.

### 22.1 Investment-advisory boundary

The desired product intentionally evaluates a specific user's portfolio and may select specific instruments/transactions as the system's preferred portfolio action. This can have characteristics of an individual investment recommendation under Russian securities law.

Therefore the plan does **not** rely on a cosmetic disclaimer such as "not an investment recommendation" to avoid the applicable legal regime.

Before commercial activation of personalized selected-asset recommendations, the project must obtain a qualified Russian legal/regulatory conclusion determining the lawful operating model, including whether the provider must be/partner with an investment adviser and whether the software requires accreditation under the applicable Bank of Russia regime.

The engineering target may still be built behind disabled/sandbox/legal gates so architecture is not thrown away later.

### 22.2 Personal-data boundary

Zero-custody minimizes central processing but does not create an assumption that the central commercial/license/update plane is outside 152-FZ. The exact central data inventory, whether data is personal, operator status, notification/localization duties and retention/security requirements are determined before production.

### 22.3 Consumer rights

User terms must not contain clauses that unlawfully waive consumer rights or permit arbitrary unilateral changes to paid period/price/material obligations. Security/compatibility updates may be mandatory under disclosed service terms, while new prices apply to future purchases/renewals rather than silently changing an already paid period.

## 23. Broker API contractual gate

A broker API may impose restrictions independent of code safety. The broker connector owning WP must verify current API/service terms before commercial use.

For T-Invest specifically, public documentation states that a public service based on T-Invest API is not permitted and data retransmission is not granted. Therefore commercial architecture may not assume a centralized T-Invest-data SaaS. Personal Node direct-user-token use requires a documented compatibility determination and, if ambiguity remains, written clarification/permission before production.

## 24. How this changes existing V10 blocks without renumbering them

The canonical A-J sequence and block weights remain unchanged.

### Block B / WP4

Add release/update provenance prerequisites only:

- update artifact identity/digest/signing fields;
- release channel and minimum-supported-version fields;
- rollback target;
- compatibility/schema/model/policy provenance.

Do not implement billing/updater/Portfolio Guardian in WP4.

### Block C — Personal Node

Owns:

- local node identity/recovery identity;
- local secret vault;
- privacy boundary;
- updater bootstrap/runtime safety;
- service supervision;
- durable local state.

### Block D — Core and data

Owns:

- canonical portfolio/instrument data;
- AssetHealthState schema/data inputs;
- broker-report truth;
- direct broker read connector boundary;
- currency/economic exposure model;
- sanctions/custody evidence schema;
- Privacy Firewall input classification.

### Block E — Web

Owns user-visible product surfaces for:

- portfolio health;
- asset-health details;
- system proposals and before/after portfolio impact;
- preferences/constraints;
- broker READ/TRADE secret connection screens;
- license/trial/expiry/renewal status;
- update status;
- local privacy/export/delete controls;
- legal document presentation/acceptance where required.

### Block F — Telegram

Remains a companion interface. Add notifications for portfolio-health incidents, proposal readiness, OWNER clarification, material evidence changes, system performance/health and execution/reconciliation status. Telegram still owns no financial logic.

### Block G — Cortex / Research

Owns:

- system-requested research/interpretation;
- public-source evidence retrieval;
- user explanation;
- rejection/revision dialogue;
- PreferenceProfile intent extraction;
- private-context redaction before outbound research;
- legal/advisory-safe response/eval contracts.

It does **not** own 24/7 scheduling or canonical portfolio decisions.

### Block H — Guardian / Watchtower

Becomes the primary 24/7 autonomous portfolio-governance loop:

- health monitoring;
- materiality prioritization;
- incident lifecycle;
- candidate-screen trigger;
- optimizer/Decision Engine orchestration;
- proposal lifecycle;
- monitoring-frequency escalation/de-escalation;
- OWNER-notification trigger.

### Block I — Personal Real Execution

Owns exact approved BUY/SELL execution only after immutable proposal approval and fresh preflight. Cash-only/no-short/no-transfer restrictions are hard Core policy.

### Block J — Integration / hardening / release

Owns the final commercial and production integration:

- fixed-term license service integration;
- 7-day trial/anti-abuse/recovery/transfer;
- payment/receipt/refund production integration;
- automatic update stable rollout and rollback rehearsal;
- legal production gates;
- broker terms compatibility evidence;
- end-to-end Personal Node zero-custody audit;
- final V9->V10 parity and commercial release acceptance.

## 25. Required machine-readable contracts

This amendment is accompanied by:

- `docs/architecture/V10_AUTONOMOUS_PORTFOLIO_GOVERNANCE_CONTRACT.json`;
- `docs/architecture/V10_RUSSIAN_MARKET_UNIVERSE_AND_SANCTIONS_POLICY.json`;
- `docs/architecture/V10_ZERO_CUSTODY_LICENSE_UPDATE_CONTRACT.json`;
- `docs/legal/V10_RU_COMMERCIAL_LEGAL_GATES.md`.

Future implementation must treat these as planning constraints and must not infer missing technical values from chat memory.

## 26. Definition of product success

A fully developed V10 is successful when an OWNER can leave the system running and receive evidence-backed, prioritized portfolio governance without manually doing the analyst's screening work:

1. every held asset is continuously covered by explicit freshness/health state;
2. material deterioration/opportunity creates a durable system event;
3. the system gathers sufficient evidence or explicitly reports insufficient data;
4. the allowed Russian-market universe is screened through policy;
5. sanctions/custody hard gates are applied;
6. deterministic risk/strategy/optimizer logic produces a concrete primary proposal or `NO_CHANGE`;
7. Cortex explains the reasoning and can negotiate OWNER revisions without becoming authority;
8. OWNER approves/rejects/revises;
9. only an exact valid approved plan may reach the isolated execution service;
10. post-trade/post-decision state is reconciled and monitored;
11. all private investment state remains on the Personal Node by default;
12. paid access, stable updates and commercial/legal gates operate without changing the financial authority model.

This amendment **does not start** Block C/D/E/F/G/H/I/J implementation and does not credit V10 progress. Current authorized next implementation package remains WP4 until the Current Program Status changes through accepted implementation evidence.