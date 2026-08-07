# Omni-CIO V10 — Russian Commercial / Legal Production Gates

Status: **PLANNING CHECKLIST — NOT LEGAL ADVICE / NOT PRODUCTION SIGN-OFF**  
Applies to: commercial/public activation of paid Omni-CIO V10.

## 1. Purpose

This document prevents engineering from assuming that a technically safe build is automatically lawful for commercial use in the Russian Federation.

Engineering may implement the approved architecture behind disabled/sandbox/non-commercial gates, but public paid activation remains fail-closed until the required legal determinations are completed by a qualified Russian specialist for the actual business model, operator/provider identity and production data flows.

## 2. Required launch gates

All must be resolved before commercial production activation:

- `RU_LEGAL_ARCHITECTURE_REVIEW_COMPLETE`
- `PD_OPERATOR_DETERMINATION_COMPLETE`
- `PERSONAL_DATA_FLOW_AND_LOCALIZATION_REVIEW_COMPLETE`
- `CONSUMER_TERMS_AND_FIXED_TERM_ACCESS_REVIEW_COMPLETE`
- `PAYMENT_KKT_RECEIPT_REFUND_REVIEW_COMPLETE`
- `BROKER_TERMS_COMPATIBILITY_COMPLETE`
- `INVESTMENT_ADVISORY_MODEL_DETERMINED`
- `AUTOCONSULTING_SOFTWARE_REGULATORY_PATH_DETERMINED`
- `AUTOMATIC_UPDATE_TERMS_REVIEW_COMPLETE`
- `COMMERCIAL_PRODUCTION_LEGAL_SIGNOFF`

A missing/ambiguous gate = commercial activation blocked.

## 3. Personal-data determination

Zero-custody is an engineering minimization rule, not an automatic legal exemption.

Before production, inventory the central Billing/License/Update plane field-by-field and determine:

- whether each field is personal data or can become personal data in combination;
- categories of subjects;
- purpose/legal basis;
- actions performed;
- storage and retention;
- locations/databases used;
- recipients/processors;
- cross-border flows, if any;
- operator/controller roles;
- whether notification to Roskomnadzor is required under the actual model;
- localization requirements for Russian citizens' personal data;
- information-security and incident-response obligations.

Do not claim that data is outside 152-FZ merely because it is pseudonymous, encrypted, not stored long-term, or transits a proxy.

## 4. Consumer-protection determination

The paid product uses fixed-term prepaid access:

- 7-day trial;
- 1 / 3 / 6 / 12 month paid access;
- no automatic renewal;
- no recurring charges;
- each renewal is a new explicit user-initiated payment.

User-facing commercial terms must clearly specify at least:

- provider/seller identity and contact details required by law;
- product/service scope;
- exact paid period;
- price at purchase time;
- what happens at expiry;
- update policy;
- technical requirements;
- cancellation/refund/claims procedure as applicable;
- what local user data remains accessible/exportable at expiry;
- limitations that are lawful and do not waive mandatory consumer rights.

Do not use terms that attempt to remove statutory liability or give the provider an unrestricted right to change an already-paid price/period/material obligation.

## 5. Payment / receipt gate

Before accepting real payments determine and implement the lawful seller/tax/payment model for the actual provider (for example legal entity, individual entrepreneur or another lawful status appropriate to the activity).

Verify for the selected payment provider and tax status:

- acquiring agreement;
- online payment flow;
- fiscal receipt / KKT obligations or lawful alternative for the chosen tax regime;
- receipt delivery fields;
- refund flow;
- payment reconciliation;
- required accounting/retention records.

Broker/portfolio secrets must not be included in payment metadata.

## 6. Broker API terms gate

Technical API availability does not grant a right to commercial retransmission or public SaaS use.

For every supported broker connector, record:

- current API/user agreement version;
- whether third-party commercial software is permitted;
- restrictions on retransmission/display/storage of broker/market data;
- token/user authorization model;
- rate/use limits;
- execution/algorithmic-trading conditions;
- any required written permission/partner agreement.

For T-Invest, current public FAQ explicitly states that a public service based on T-Invest API is not allowed and data retransmission is not granted. Therefore V10 must not activate a centralized T-Invest data SaaS based only on the public API. The Personal Node direct-token model still requires a documented legal/contractual compatibility determination before commercial production.

## 7. Investment-advisory / autocon-sulting gate

The intended V10 product may:

- analyze a specific user's actual portfolio;
- evaluate the user's risk/preferences;
- select specific financial instruments;
- propose exact BUY/SELL portfolio changes;
- explain that the selected action is preferable for that portfolio;
- convert an approved proposal into broker execution.

This feature set can have the characteristics of an individual investment recommendation / investment consulting model under Russian securities law.

Do not rely on a disclaimer such as "not an investment recommendation" if the factual product behavior meets regulated criteria.

Before commercial activation, obtain a qualified determination covering:

- whether the provider must have investment-adviser status or use a licensed/registered partner model;
- requirements for the customer's investment profile;
- form/content/evidence of recommendations;
- records and disclosures;
- conflicts of interest;
- whether the program is an automated consulting/autofollow program requiring accreditation by the Bank of Russia or another authorized body;
- whether the planned execution handoff changes the regulatory classification.

Until this gate is accepted, production may run analytical/sandbox functionality only to the extent specifically approved by legal review; Real personalized advisory/execution features remain disabled for commercial users.

## 8. Automatic updates gate

Commercial terms must explain that supported V10 is a maintained service and STABLE security/compatibility updates install automatically.

Legal review must confirm:

- updates do not silently change an already-paid period/price;
- material product/contract changes are handled through an appropriate notice/re-consent process where required;
- user-owned local data remains recoverable/exportable;
- rollback/security updates do not create misleading claims about availability or investment outcomes.

## 9. Legal document registry

Before production, final approved versions must be immutable/versioned and linked to release/license state where legally necessary.

Expected documents include, subject to legal review:

- user/license/service terms;
- fixed-term access/payment terms;
- privacy/personal-data policy for the central plane;
- separate personal-data consent where consent is the chosen legal basis and the law requires separate form;
- broker READ connection disclosure;
- broker TRADE connection / execution terms;
- investment/trading risk disclosure;
- AI/Cortex disclosure;
- automatic-update policy;
- license transfer/recovery rules;
- refund/claims process.

Store `document_type`, `version`, `sha256`, `effective_at`, and where applicable the minimum auditable acceptance record required by the final legal design. Do not centralize extra identity merely to create an acceptance record if a lawful minimized design is available.

## 10. Required authoritative review sources

The final legal review must use current primary/official or professional legal-text sources, including as applicable:

- Federal Law No. 152-FZ on Personal Data;
- Law of the Russian Federation No. 2300-1 on Consumer Rights Protection;
- Federal Law No. 39-FZ on the Securities Market;
- current Bank of Russia regulations/explanations/registers for investment advisers and software accreditation;
- current broker API/user agreements and written clarifications;
- tax/KKT rules and Federal Tax Service guidance;
- selected payment-provider agreements/documentation.

This checklist intentionally avoids freezing legal conclusions that can change between planning and launch. Final production sign-off must record the date and legal sources actually reviewed.