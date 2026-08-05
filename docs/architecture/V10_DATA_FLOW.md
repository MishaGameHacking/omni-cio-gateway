# Omni-CIO V10 — Data Flow

Status: **WP0 architecture freeze**  
Runtime effect: **none until later work-package acceptance**

## 1. Purpose

Define where V10 data originates, how it is normalized, where it is allowed to persist, and which component may turn information into a decision or execution request.

The main design rule is:

**raw input -> normalized canonical record -> validation/evidence -> deterministic Core decision -> optional explanation -> explicit approval -> isolated execution**.

## 2. Portfolio / broker read flow

```text
T-Invest READ credential
        |
        v
Broker adapter / streams / snapshots
        |
        v
Canonical instrument/account identity
        |
        v
PortfolioSnapshot / Position / Cash / Operations
        |
        +----> Durable DB
        |
        v
Risk / Credit / Policy / Optimizer / Watchtower
        |
        v
Decision / Plan candidate / Journal
```

Rules:

- READ credential never falls back to Real trading credential;
- broker UID/FIGI/ISIN/class-code identity precedes ticker/name matching;
- money/quantity values use exact decimal semantics;
- timestamps preserve source time and receive time;
- stale/partial/contradictory broker data blocks unjustified strong conclusions.

## 3. External research flow

```text
Approved public/official source
        |
        v
Research Collector
 fetch / cache / content hash / parser version
        |
        v
Normalized document
        |
        v
Evidence / Claim Engine
 provenance / identity / published_at / retrieved_at
 freshness / supporting / contradicting
        |
        +----> Durable evidence store
        |
        +----> deterministic Credit/Risk/Watchtower
        |
        `----> optional AI Researcher for synthesis
```

Rules:

- unapproved scraping shortcut is not an accepted source method;
- active HTML/script content is never executed as trusted code;
- duplicate documents are deduplicated by canonical identity/content hash;
- AI output is not evidence without source references;
- contradiction/unknown state is persisted instead of silently averaged away.

## 4. AI Copilot flow

```text
OWNER Web/Telegram request
        |
        v
Conversation Orchestrator
        |
        +----> System Policy
        +----> Knowledge/RAG
        +----> allowlisted Tool Registry
        |
        v
Structured AI response
 facts cited / inference labeled / unknowns explicit
        |
        v
Web/Telegram presentation
```

When AI needs financial facts, it calls read-only/analytical Core tools. It does not read broker secrets and cannot call the broker-write primitive.

Untrusted retrieved text never modifies System Policy or tool permissions.

## 5. Watchtower / Guardian flow

```text
Portfolio state + market state + policy + evidence
        |
        v
Deterministic Watchtower triggers
        |
  no material event ----------------> stop / journal if needed
        |
  material event
        v
Incident
        |
        v
Research / evidence validation
        |
        v
Credit / Risk / Strategy / Optimizer
        |
        v
MAIN_DECISION
NO_ACTION | HOLD | REDUCE | EXIT | REALLOCATE
        |
        v
Plan candidate + explanation
        |
        v
Telegram alert / Web incident
```

AI can improve research/explanation but cannot bypass the deterministic decision/plan authority path.

## 6. Real execution flow

```text
Validated decision
      |
      v
Immutable Plan
 exact instruments / sides / lots / limits / constraints / expiry
      |
      v
OWNER approval bound to plan hash
      |
      v
Repeat preflight
 market / account / cash / position / price-step / drift / durable state
      |
      v
Execution service using isolated Real credential
      |
      v
One idempotent possible submit per request identity
      |
      +---- ambiguous --------> UNKNOWN / reconciliation only
      |
      v
Broker state / fills
      |
      v
Reconciliation
      |
      v
Execution record + Decision Journal + portfolio refresh
```

No execution leg may infer `filled` from local submit success alone.

## 7. GitHub / deployment flow

```text
Developer or AI agent
      |
      v
focused branch
      |
      v
PR + CI/security/review
      |
      v
accepted commit/release
      |
      v
Deploy Controller
      |
      v
Approved V10 runtime node
```

GitHub transports engineering artifacts, not broker secret values or private portfolio state.

## 8. Secret flow

```text
OWNER one-time local provisioning
       |
       v
Local Secret Store
       |
       +--> read-only broker adapter (read secret only)
       +--> Telegram adapter (Telegram secret only)
       +--> execution service (Real trading secret only when enabled)
       `--> other approved service-scoped credentials
```

CI runner, AI worker and frontend never receive the Real trading secret by default.

## 9. Backup/recovery flow

```text
GitHub -----------------------> source/config/migrations/runbooks
Local durable DB -------------> encrypted backup
Runtime private metadata -----> encrypted backup where required
Secret values ----------------> separate owner-controlled recovery procedure
                                      |
                                      v
                               replacement approved node
```

Recovery must not require chat history or the original ChatGPT account.

## 10. Time semantics

Canonical persistent timestamps use UTC. Presentation may use MSK or owner-selected UI timezone.

Where relevant, records distinguish:

- source `published_at`;
- source/broker event time;
- `retrieved_at`;
- local receive time;
- decision time;
- approval time/expiry;
- submit/reconciliation timestamps.

Unsafe clock drift is a later Real-execution blocker.

## 11. Data-retention rule

V10 stores the minimum raw/private data required for reproducibility, evidence, reconciliation and recovery. Retention/rotation values are defined by the relevant later WP and cannot be extended merely for convenience.

## 12. Flow-change rule

Any future path that bypasses normalization, evidence, deterministic plan authority or explicit Real approval requires an ADR/program amendment and is fail-closed by default.
