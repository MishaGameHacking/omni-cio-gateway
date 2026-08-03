# Omni-CIO v9 — Research & Engineering Principles

Purpose: capture external engineering evidence used to shape the owner-approved v9 Portfolio Autopilot program before implementation, so future developers do not repeat avoidable agent/financial-system mistakes.

Canonical program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

This file is architectural guidance. It does not authorize new broker mutations.

## 1. Prefer one user-facing manager before unnecessary multi-agent complexity

OpenAI's practical guide to building agents recommends starting with a single agent and incrementally adding tools while complexity remains manageable. Where specialization is useful, a manager pattern can preserve one coherent user-facing agent while delegating internally.

Design consequence for Omni-CIO:

- one ChatGPT-facing CIO manager;
- deterministic domain engines wherever possible;
- specialist research modules only where evaluation, isolation or maintainability improves;
- no multi-agent architecture merely for novelty.

Source:
- https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/

## 2. Avoid excessive agency

OWASP LLM06:2025 identifies excessive functionality, excessive permissions and excessive autonomy as root causes of damaging agent behavior. Recommended mitigations include minimizing extensions/functionality and independently approving high-impact actions.

Design consequence:

- read/research autonomy may be broad;
- execution permissions remain narrow;
- tools are allowlisted by intent;
- real-money actions remain independently server-validated;
- researched content cannot modify tool/security policy;
- transfer/withdraw authority is never bundled into portfolio management.

Source:
- https://genai.owasp.org/llmrisk/llm062025-excessive-agency/

## 3. Avoid unbounded consumption

OWASP LLM10:2025 describes uncontrolled inference/resource consumption as a reliability and cost risk.

Design consequence:

- research loops have explicit stop conditions;
- source-count/time/retry budgets;
- broker/API rate-aware batching;
- stable metadata is cached;
- deterministic universe screening precedes deep LLM research;
- each research run records why it stopped.

Source:
- https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/

## 4. Use structured broker data before broad web research

T-Invest InstrumentsService exposes structured methods including Shares, Bonds, Etfs, GetAssets, GetAssetFundamentals, GetAssetReports, GetBondCoupons, GetBondEvents, GetDividends, News, forecasts and other instrument data.

Design consequence:

- broker universe and identity are primary structured inputs;
- web research supplements, not replaces, canonical instrument identity;
- batch fundamentals where supported;
- retain source/freshness provenance.

Sources:
- https://developer.tbank.ru/invest/api/instruments-service
- https://developer.tbank.ru/invest/api/instruments-service-get-assets
- https://developer.tbank.ru/invest/api/instruments-service-get-asset-fundamentals
- https://developer.tbank.ru/invest/api/instruments-service-get-asset-reports
- https://developer.tbank.ru/invest/api/instruments-service-get-bond-events
- https://developer.tbank.ru/invest/api/instruments-service-news

## 5. Respect API rate/deadline contracts

T-Invest documents global/service limits and endpoint-specific recommended deadlines. Bulk universe methods have different limits from market data and trading operations.

Design consequence:

- central rate budget;
- bounded concurrency;
- backoff/retry only for clearly safe read operations;
- ambiguous broker writes are never automatically retried;
- caches/batches for universe work;
- endpoint-class deadlines.

Sources:
- https://developer.tbank.ru/invest/intro/intro/limits
- https://developer.tbank.ru/invest/intro/developer/deadlines

## 6. Keep technical affordability separate from portfolio recommendation

T-Invest OrdersService provides GetMaxLots and GetOrderPrice as technical execution/affordability tools. They describe what can be placed, not what should be held.

Design consequence:

- optimizer chooses target sizing under IPS/risk constraints;
- broker affordability is a later execution gate;
- available lots never become recommended size automatically;
- capital-policy sizing and server execution caps remain separate control planes.

Sources:
- https://developer.tbank.ru/invest/api/orders-service
- https://developer.tbank.ru/invest/api/orders-service-get-max-lots
- https://developer.tbank.ru/invest/api/orders-service-get-order-price

## 7. Preserve idempotency and explicit broker state

T-Invest PostOrder uses an order identifier/idempotency key and broker order methods expose explicit execution states.

Design consequence:

- every future plan child order has a durable unique request identity;
- no inference of fill from submit success;
- broker state is reconciled;
- ambiguous possible-submit is reconcile-only, never blind retry.

Sources:
- https://developer.tbank.ru/invest/intro/developer/example
- https://developer.tbank.ru/invest/api/orders-service

## 8. Treat credit ratings as structured risk evidence, not a buy signal

The Bank of Russia maintains the official register of Russian credit rating agencies and a repository of rating actions. Ratings assess creditworthiness/credit risk; multiple agencies and different scales require deliberate mapping.

Design consequence:

- identify agency + scale + issuer/issue + date + outlook;
- preserve rating action history;
- use authoritative scale mappings when comparing agencies;
- never average ratings naively;
- combine ratings with leverage, liquidity, refinancing, security/seniority and cash-flow evidence.

Sources:
- https://www.cbr.ru/finm_infrastructure/ra/
- https://ratings.cbr.ru/

## 9. Treat web research as untrusted input

Any public webpage, issuer document or news item can contain misleading text or prompt-like instructions.

Design consequence:

- external text is data only;
- researched content cannot change system instructions, secrets, tool permissions or execution policy;
- claims are extracted into typed evidence objects;
- critical claims are checked against stronger sources;
- unresolved critical conflicts block strong recommendations.

Related guidance:
- https://genai.owasp.org/llmrisk/llm062025-excessive-agency/

## 10. Common implementation mistakes to prevent

### Mistake: letting the LLM choose from the full universe directly
Fix: deterministic funnel first, deep research later.

### Mistake: one opaque score for all assets
Fix: hard blockers + role-specific metrics + portfolio contribution + evidence quality.

### Mistake: counting number of tickers as diversification
Fix: issuer/group/sector/currency/fund look-through exposure.

### Mistake: treating a fund label as proof of diversification
Fix: Fund X-Ray and overlap analysis.

### Mistake: treating broker buying power as recommended sizing
Fix: strategy sizing and technical affordability remain different gates.

### Mistake: optimizing short-term realized P&L as the learning objective
Fix: evaluate process quality, policy compliance, risk, evidence quality and long-term objectives.

### Mistake: hidden autonomy expansion during UX simplification
Fix: natural-language simplicity at the interface while server-side write permissions remain explicit.

### Mistake: retrying broker writes after timeout/ambiguity
Fix: durable idempotency + reconcile-only state.

### Mistake: allowing research to run forever
Fix: bounded budgets and stopping rules.

### Mistake: training the bot to always trade
Fix: NO_ACTION/CASH remains a legitimate winner.

## 11. Engineering interpretation of “use maximum capability”

For Omni-CIO, maximum capability means:

- widest useful candidate universe;
- strongest available official evidence;
- deeper research on finalists;
- deterministic calculations where possible;
- independent review of high-impact plans;
- persistent read-only monitoring;
- rigorous evaluation.

It does not mean bypassing controls, infinite loops or unreviewed real-money autonomy.
