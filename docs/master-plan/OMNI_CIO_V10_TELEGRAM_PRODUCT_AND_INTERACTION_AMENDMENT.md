# Omni-CIO V10 — Telegram Product and Interaction Amendment

Status: **OWNER-APPROVED PLANNING AMENDMENT / BLOCK F PRODUCT CONTRACT**  
Date recorded in GitHub: **2026-08-07**  
Applies to: **Block F / WP23–WP26 and later WP32C Telegram AI surface**  
Runtime effect: **none until the owning work packages are authorized**  
Base program: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Program Lock: `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`

## 0. Why this amendment exists

The canonical V10 plan already establishes Telegram as an OWNER-only alert/entry adapter to the same Core, Web and AI Orchestrator. This amendment removes the remaining product ambiguity before implementation so a future developer/AI session does not invent menus, commands, delivery semantics, authorization, AI behavior, Mini App routing or notification policy while coding.

This amendment is **planning only**. It does not start Block F, create a Telegram bot, request a token, install a runtime, publish an ingress, enable AI or alter broker authority. The next authorized implementation package remains WP4.

The synchronized Master Plan Markdown/PDF pair is not edited piecemeal. This amendment supplements Block F without changing block numbering or weights.

Official implementation references that must be re-checked at the owning WP include:

- Telegram Bot API: `https://core.telegram.org/bots/api`;
- Telegram Bot Features: `https://core.telegram.org/bots/features`;
- Telegram Mini Apps: `https://core.telegram.org/bots/webapps`;
- Telegram Bot API changelog: `https://core.telegram.org/bots/api-changelog`.

The product contract below intentionally uses stable capabilities rather than depending on optional/new Telegram features merely because they exist.

# 1. Product role — Telegram is a companion interface, not a second product

**Current identity overlay (Amendments 9/18 + OWNER clarification):** Telegram Login and the Telegram Bot are separate capabilities. Human registration/login is `Telegram user account OIDC -> OmniCIOUserAccount -> Tenant -> server-side Session`. The bot never registers users. The optional bot may be linked only after an Omni-CIO account already exists and an authenticated Web session proves control of that account. This planning clarification does not start WP23+ implementation.

Telegram V10 is a **fast USER companion interface** to the same Omni-CIO V10 platform.

Its three primary jobs are:

1. **See quickly** — current system/portfolio/incident state in compact form.
2. **Ask quickly** — short natural-language questions routed to the shared Omni-CIO Cortex when that later capability is enabled.
3. **React quickly** — receive material alerts and open the exact detailed Web/Mini App route.

Telegram is not:

- a second financial Core;
- a second portfolio database;
- a second independent AI brain;
- a second knowledge base;
- a second optimizer/risk engine;
- a full duplicate of the Web UI;
- a broker execution terminal;
- a public/community bot.

Canonical rule:

`Telegram -> typed V10 APIs / shared Cortex -> canonical Core DTO/evidence -> presentation`

No financial formula, sizing logic, risk policy or broker-write authority is owned by the Telegram adapter.

# 2. Access and scope lock

## 2.1 Account-linked companion scope

Current accepted direction:

- bot access is optional and user-scoped, never a prerequisite for Web registration/login;
- a USER must first exist through the canonical Telegram OIDC Web login path;
- bot connection is an explicit post-auth account-link operation bound server-side to that existing OmniCIOUserAccount/Tenant;
- private chat with the bot only unless a later amendment expands chat types;
- one canonical production bot identity may serve multiple isolated USER/Tenant bindings without becoming a tenant selector;
- Telegram Mini App/Web handoff uses the same V10 frontend and authenticated account authority;
- bot `/start`, chat identity, deep-link possession or bot-token possession can never create an Omni-CIO account, mint/select a Tenant, or replace Telegram Login.

## 2.2 Explicit non-goals without a later OWNER amendment

Do not implement by default:

- group/supergroup operation;
- channel administration/public broadcasts;
- inline mode in arbitrary chats;
- bot-to-bot automation;
- payments/Stars/monetization;
- managed bots/business bot features;
- social/community features;
- public portfolio sharing;
- photo/screenshot/OCR broker import;
- document upload as a substitute for the Web broker-report review flow;
- autonomous Real-money execution.

If Telegram receives an unsupported chat type or unknown user, it fails closed and returns no private portfolio/system data.

# 3. Transport contract

## 3.1 Initial transport = long polling

WP23 starts with Telegram Bot API long polling (`getUpdates`) from the approved Personal Node.

Reasons:

- no public Telegram webhook ingress is required;
- simpler V10 Personal attack surface;
- compatible with the replaceable Lenovo-first runtime;
- outbound connection from the node is sufficient.

A webhook may only replace long polling in a later reviewed package after an explicit ingress/security requirement exists. Long polling and webhook must never be active simultaneously.

## 3.2 Update cursor and restart safety

The Telegram adapter must persist or deterministically recover the processed update cursor so restart does not create an uncontrolled replay loop.

For each update:

`receive -> validate envelope -> authorize identity/chat -> classify -> create correlation id -> execute bounded handler -> persist outcome -> advance cursor`

The cursor is advanced only according to a documented at-least-once-safe handler policy. Side effects use their own idempotency key.

## 3.3 Allowed update surface

Use the narrowest required `allowed_updates` set. Block F should need only update types required for:

- private messages/commands;
- callback queries;
- Mini App-related flows where applicable.

Do not subscribe to unrelated update classes by default.

# 4. Bot identity and BotFather configuration

The repository stores configuration **schemas and safe metadata only**, never the real bot token.

OWNER participation at WP23 is limited to actions that cannot be delegated safely:

1. create/confirm the canonical bot in BotFather;
2. provide the resulting token once to the local V10 Secret Store;
3. confirm final human-facing bot username/name if Telegram requires it.

Everything that the Bot API can configure programmatically should be repository-controlled and applied by bootstrap/runtime where safe, including commands/menu metadata.

The token is:

- local secret only;
- redacted from logs/errors;
- separately rotatable/revocable;
- never stored in GitHub, CI artifacts, screenshots, browser URLs or AI context.

# 5. Navigation model

Telegram navigation must remain intentionally small.

## 5.1 Global commands

Accepted initial command contract:

- `/start` — OWNER authentication/status entry and concise introduction;
- `/help` — supported capabilities and safety boundaries;
- `/status` — compact V10 system/data status;
- `/portfolio` — compact current portfolio summary from canonical Core DTO;
- `/alerts` — active material incidents/alerts;
- `/system` — operational status relevant to OWNER;
- `/app` — open the canonical V10 Web/Mini App.

No command performs broker submit.

Additional commands require a later owning-WP justification; Telegram must not become a 40-command CLI.

## 5.2 Menu button

The preferred Telegram menu button opens **Omni-CIO V10 Web/Mini App** when Block E/F security and routing gates permit it.

Until that route is available safely, the menu may expose commands rather than a dead/unsafe Web App link.

## 5.3 Chat keyboards

Default interaction uses compact inline keyboards attached to bot messages. A persistent reply keyboard is not required by default because it adds chat clutter and duplicates the command/menu surface.

# 6. Message UX contract

Every Telegram message must answer, as applicable:

- **what happened / what is the state?**
- **how fresh is the information?**
- **what is the source class?**
- **what can the OWNER do next?**

Telegram shows only the minimum useful numbers. Detailed tables, charts, full broker reports, audit history and complex configuration remain in Web.

## 6.1 Presentation rules

- Russian is first-class product language.
- Exact financial values come only from canonical DTOs, never regenerated by message templates/LLM arithmetic.
- Material values show `as_of`/freshness when relevant.
- Stale/partial/unknown is explicit.
- Account identifiers remain masked.
- No raw secret/private payload in error text.
- User/source text is escaped before Telegram HTML/formatting parse mode.
- Message length limits are handled by concise summary + Web handoff rather than blind multi-message dumps.

## 6.2 Source/inference distinction

Where AI participates later, a message must make clear the distinction among:

- broker/accounting fact;
- deterministic Core calculation;
- external evidence/source;
- AI inference/explanation;
- unknown/missing data.

Telegram text similarity is never an acceptance oracle for Core correctness.

# 7. Versioned Telegram message registry

All material message families are versioned and schema-controlled. Initial registry:

- `TG_START_V1`;
- `TG_HELP_V1`;
- `TG_STATUS_V1`;
- `TG_PORTFOLIO_SUMMARY_V1`;
- `TG_ALERT_CRITICAL_V1`;
- `TG_ALERT_IMPORTANT_V1`;
- `TG_ALERT_INFO_V1`;
- `TG_INCIDENT_STATE_V1`;
- `TG_RESEARCH_READY_V1`;
- `TG_AI_ANSWER_V1`;
- `TG_SYSTEM_DEGRADED_V1`;
- `TG_SYSTEM_RECOVERED_V1`;
- `TG_WEB_HANDOFF_V1`;
- `TG_AUTH_DENIED_V1`.

Machine-readable details live in `docs/architecture/V10_TELEGRAM_MESSAGE_REGISTRY.json`.

Templates consume canonical values; they do not own business semantics.

# 8. Alert policy and anti-noise rules

## 8.1 Severity

Accepted product severities:

- **CRITICAL** — immediate OWNER attention; bypasses quiet hours;
- **IMPORTANT** — material change requiring timely review;
- **INFO** — useful but not urgent;
- **SILENT** — journal/system state only, no chat notification.

Severity is assigned by deterministic policy/incident state, not by LLM mood.

## 8.2 No-noise invariant

A clean Watchtower run is silent.

Do not send repeated messages merely because the same condition remains true.

Required behavior:

- semantic incident dedup;
- delivery-level idempotency;
- persisted Telegram `message_id` for material incidents;
- state update edits the existing incident message where practical;
- a new message is allowed when severity materially escalates, OWNER action newly becomes required, or a resolved incident reopens under defined semantics.

Quiet hours apply only to configured non-critical notifications.

# 9. Delivery reliability contract

Telegram delivery is a durable job, not a fire-and-forget HTTP call.

Recommended state model:

`PENDING -> SENDING -> DELIVERED`

with explicit exceptional states such as:

`RETRY_SCHEDULED | RATE_LIMITED | UNKNOWN_DELIVERY | FAILED_PERMANENT`.

Each delivery stores only minimum metadata needed for reliability/audit:

- delivery id;
- event/incident correlation id;
- message type/version;
- target OWNER chat identity reference;
- idempotency key;
- Telegram message id after confirmed send;
- attempts/timestamps;
- sanitized error class.

On network ambiguity, do not blindly create duplicates. Reconcile known local delivery state and apply bounded retry semantics.

Telegram API `retry_after`/flood signals are respected; concurrency/retry timing is measured and bounded rather than hardcoded from folklore.

# 10. Callback/query interaction contract

Inline callback actions are server-authoritative.

Rules:

- `callback_data` contains only a compact opaque action/reference token; no secret, full portfolio data or authority is encoded in it;
- callback payload must remain within Telegram API limits;
- every callback re-checks OWNER identity, current entity state and action validity server-side;
- stale/expired callbacks return a safe message and cannot mutate canonical financial state;
- callback query is acknowledged promptly so Telegram UI does not remain spinning;
- button text does not imply an action completed until server state confirms it.

Allowed Block F callback classes are read/navigation operations such as:

- refresh safe summary;
- show incident summary;
- open Web/Mini App route;
- show status/help.

Real-money confirmation/submission is **not** a generic Telegram callback capability.

# 11. OWNER authentication contract

## 11.1 Private bot chat

A Telegram user ID is necessary but not sufficient as a universal V10 identity primitive.

For the bot chat:

- only configured OWNER Telegram user ID is authorized;
- private chat type is required;
- chat/user consistency is checked;
- unauthorized identities receive `TG_AUTH_DENIED_V1` with no private data;
- authorization decisions are server-side and auditable.

## 11.2 Mini App authentication

The backend trusts Telegram Mini App identity only after server-side validation of `Telegram.WebApp.initData` according to current Telegram documentation.

`initDataUnsafe`, query-string fields or client JavaScript state are never authority.

Required controls:

- signature/hash validation;
- `auth_date` freshness policy;
- replay/staleness rejection;
- OWNER mapping;
- short-lived V10 server session after validation;
- explicit revoke/logout/expiry behavior;
- ordinary browser authentication remains independently designed under WP22A.

Mini App authentication never exposes broker secrets to Telegram/client code.

# 12. Deep-link / Web handoff contract

Telegram should hand off complex work to an exact Web route rather than forcing detailed analysis into chat.

Canonical route families may include:

- `/portfolio`;
- `/incidents/{opaque_ref}`;
- `/research/{opaque_ref}`;
- `/decisions/{opaque_ref}`;
- `/system`.

External/start parameters must be:

- opaque and non-secret;
- bounded in length;
- validated server-side;
- short-lived/signed where authority/freshness requires it;
- incapable of granting access by URL possession alone.

Do not put account ID, portfolio value, token or private payload in the URL/start parameter.

# 13. Mini App UX contract

The Mini App is the **same frontend codebase** as ordinary V10 Web, adapted responsively for Telegram context.

Requirements owned by WP26/Block E integration:

- Telegram/mobile theme compatibility;
- safe-area/mobile viewport support;
- exact route opened from alert/deep link;
- back/navigation behavior that does not lose canonical server state;
- no duplicate financial formulas in Mini App-specific JavaScript;
- no Telegram-only shadow database;
- deterministic page rendering from the same API DTOs as Web.

The Telegram menu should become a fast doorway to Web, not a second UI product.

# 14. AI/Cortex interaction contract

Block F must **prepare**, not prematurely implement, the Telegram AI surface.

The actual conversational AI integration remains owned by WP32C after Block G prerequisites.

When enabled later:

`Telegram free text -> shared Agent Orchestrator -> typed allowlisted tools -> Core/evidence -> compact Telegram answer`

Rules:

- one shared Cortex for Web and Telegram;
- no Telegram-specific model or second prompt authority;
- no independent Telegram knowledge base;
- no broker-write tool in AI registry;
- unsupported/unsafe request is rejected or handed off safely;
- long research becomes a durable Research Job rather than holding the chat request open indefinitely;
- completion can later produce `TG_RESEARCH_READY_V1`;
- complex result uses compact summary + exact Web link;
- provider outage produces explicit degraded behavior while deterministic commands continue working.

The bot must not pretend AI research has completed until the durable job/evidence state says it has.

# 15. System-status behavior

`/status` and `/system` are owner-operational views, not raw debug dumps.

They may show bounded facts such as:

- overall V10 state;
- Core readiness;
- last accepted portfolio/report timestamp;
- market-data freshness;
- active incidents count;
- Watchtower state;
- AI available/degraded/offline;
- Telegram delivery state;
- last backup status where approved;
- release/Git SHA identity where useful.

They must not expose:

- secrets;
- full environment variables;
- private file paths unnecessarily;
- stack traces containing private payloads;
- raw database rows;
- account identifiers beyond masking policy.

# 16. Degraded-mode matrix

Telegram uses the common V10 state vocabulary:

`READY | PARTIAL | STALE | DEGRADED | BLOCKED | ERROR | OFFLINE | RECOVERING | OWNER_ACTION_REQUIRED`.

Minimum behavior:

### AI/Cortex unavailable

- `/status`, `/portfolio`, `/alerts`, `/system`, `/app` continue if Core is available;
- AI request states that AI is unavailable;
- no fake fallback model/arithmetic.

### MOEX/current-market stale

- broker-period facts remain usable;
- current-market fields are explicitly `STALE/UNAVAILABLE`;
- message shows last known `as_of` where safe.

### Core/DB unavailable

- no portfolio/decision values are invented from cached chat text;
- bot returns controlled degraded state;
- notification/recovery jobs follow durable policy.

### Telegram API unavailable

- Core/Watchtower continue independently;
- deliveries remain queued/bounded according to retention/retry policy;
- recovery does not re-send all historical notifications blindly.

### Lenovo reboot/process restart

- long-poll cursor and delivery/job state recover;
- no manual terminal session is required after accepted Block C supervision work.

# 17. Privacy and retention contract

Telegram is not a long-term canonical portfolio store.

Persist only what is necessary for authorization, delivery reliability, correlation and audit.

Do not persist raw conversation text indefinitely by default.

Conversation memory, when later used by Cortex, is scoped/retained under the AI memory policy and never becomes financial truth.

Never send through Telegram unless explicitly necessary:

- broker HTML report file;
- raw transaction export;
- full account number;
- secret/token;
- database backup;
- unrestricted diagnostic bundle.

# 18. Observability contract

Block F must provide sanitized operational observability for at least:

- polling connected/disconnected;
- last successfully processed update id/time;
- authorized/denied update counts;
- delivery success/failure/rate-limit counts;
- queue depth/oldest pending delivery;
- callback failures/stale callbacks;
- Mini App auth failures/replay failures;
- message edit/send failures;
- Telegram API latency/error class;
- current bot capability/version metadata.

Logs carry correlation IDs and never log token/private payload values.

# 19. Threat model additions

Block F implementation must explicitly test/mitigate:

- stolen bot token;
- unauthorized Telegram user;
- group/channel accidental invocation;
- forged Mini App `initData`;
- stale/replayed `auth_date`;
- malicious deep-link/start parameter;
- callback tampering/replay;
- HTML/formatting injection from external source/AI text;
- repeated update replay;
- duplicate delivery after timeout;
- flood/rate limit;
- prompt injection through user/source text after AI integration;
- AI tool escalation;
- secret leakage in errors;
- stale incident button opening wrong/currently unauthorized state.

No Telegram feature can widen broker, OS, GitHub or Real-money authority.

# 20. Block F work-package concretization

## WP23 — Telegram Bot Foundation

### Purpose

Establish the minimal OWNER-only Telegram transport/adapter with no AI runtime and no financial business logic.

### Mandatory deliverables

- repository-controlled Telegram adapter module boundary;
- Bot API client behind a narrow adapter interface;
- long polling supervisor integration contract;
- update cursor/restart semantics;
- OWNER/private-chat authorization gate;
- `/start`, `/help`, `/status`, `/portfolio`, `/alerts`, `/system`, `/app` command routing;
- canonical Core DTO mapping only;
- BotFather/bootstrap metadata without token value;
- token read from Local Secret Store only;
- structured sanitized logs/health;
- fake/mocked Telegram API for deterministic tests.

### Mandatory non-goals

- webhook/public ingress;
- Mini App auth implementation beyond placeholders/contracts;
- AI/Cortex chat;
- Telegram-owned financial calculations;
- trade approval/submit;
- group/channel/inline mode.

### Exit Gate

On a test/fake transport and approved local integration path, OWNER receives correct canonical status/portfolio/alerts, unauthorized identity receives no private data, restart/replay does not duplicate side effects, and the adapter contains no broker-write/business-logic path.

## WP24 — Telegram Identity and Mini App Authentication

### Purpose

Cryptographically bind Telegram Mini App requests to OWNER without making client fields the authority.

### Mandatory deliverables

- current-spec `initData` validator;
- freshness/replay policy;
- OWNER mapping;
- V10 server session issue/expiry/revoke behavior;
- ordinary-browser auth boundary preserved;
- negative auth telemetry without secret leakage;
- signed/opaque handoff reference primitive where required.

### Mandatory tests

- valid OWNER session;
- tampered hash/signature;
- stale auth_date;
- wrong user;
- replay;
- modified route parameter;
- session expiry/revoke;
- direct API call without validated Telegram session.

### Exit Gate

No Mini App request receives OWNER capability solely from client-provided Telegram fields; validated session cannot widen Core/broker authority.

## WP25 — Alert Delivery Policy and Durable Messaging

### Purpose

Make Telegram a reliable, quiet incident-delivery channel rather than a noisy fire-and-forget notifier.

### Mandatory deliverables

- severity policy `CRITICAL/IMPORTANT/INFO/SILENT`;
- versioned message registry;
- durable TelegramDelivery job/state;
- semantic incident dedup + delivery idempotency;
- persisted message id for material incident update/edit;
- edit-in-place incident progression where practical;
- bounded retry/rate-limit handling;
- quiet-hours policy for non-critical only;
- delivery observability;
- message privacy/minimization rules.

### Mandatory tests

- clean run = no message;
- duplicate event;
- persistent condition;
- severity escalation;
- resolved/reopened incident;
- timeout before response;
- rate limit/retry_after;
- process crash after send-before-local-persist simulation;
- edit failure fallback;
- privacy/redaction.

### Exit Gate

One material incident creates one coherent Telegram notification lifecycle with no spam/duplicate storm, and delivery uncertainty is handled explicitly rather than by blind repeat sends.

## WP26 — Telegram to Web/Mini App Integration

### Purpose

Turn Telegram into the fastest route to the same detailed V10 Web application.

### Mandatory deliverables

- menu button/`/app` launch behavior;
- exact entity deep links for portfolio/incident/research/decision/system where available;
- opaque validated start/handoff refs;
- Telegram/mobile frontend mode in the same Web codebase;
- safe area/theme/navigation handling;
- long-content handoff policy;
- AI entry placeholder/capability flag only; actual shared Cortex chat remains WP32C;
- browser and Telegram Mini App use the same canonical APIs.

### Mandatory tests

- alert -> exact current incident;
- wrong/expired/forged handoff ref;
- Telegram theme/mobile safe area;
- ordinary browser remains functional;
- Mini App auth expiry;
- missing/deleted entity;
- long analysis opens Web instead of Telegram dump;
- AI-disabled capability state.

### Exit Gate

OWNER can move from a Telegram alert/summary to the exact authorized V10 Web context without manual searching, duplicate financial logic or client-side authority.

# 21. Later WP32C integration lock

WP32C may activate conversational Telegram AI only after:

- Block F transport/identity/handoff contracts are accepted;
- AI Provider/Knowledge/Tool Registry/Orchestrator prerequisites are accepted;
- shared Cortex passes required security/evals.

WP32C must prove the same question uses the same Core/evidence/tool authority in Web and Telegram. Telegram-specific presentation may differ, source of truth may not.

# 22. CI and acceptance strategy

Planning target for Block F CI:

### Hosted fast lane

- schema/message-registry validation;
- pure command/router/unit tests;
- Telegram payload parsing fixtures;
- formatting/escaping tests;
- auth validation unit tests with synthetic fixtures;
- static security/policy checks.

### Hosted clean-room lane when relevant

- packaging/runtime compatibility;
- frontend Mini App/mobile build when affected;
- no real Telegram token.

### Lenovo authoritative lane

- full Block F integration with local Core/test doubles;
- restart/recovery semantics;
- durable delivery/job integration;
- system resource/degraded-mode checks;
- later local Cortex integration in WP32C.

CI must never require the real bot token for ordinary PR validation. Live OWNER acceptance is a narrow final integration step only when required by the owning WP.

# 23. OWNER participation minimization

OWNER should not manually configure dozens of BotFather/UI options.

Preferred process at the owning WP:

`GitHub implementation -> tested bootstrap/config -> OWNER creates/confirms bot once -> token stored locally -> automated safe configuration -> live acceptance`

If local Windows action is needed, follow the project rule:

`PowerShell -> Administrator only if genuinely necessary -> one reviewed idempotent block -> PASS/FAIL evidence`.

# 24. Cost/subscription rule

Telegram Bot API/Mini App is used without adding a required paid bot/SaaS subscription.

Do not introduce a recurring paid Telegram middleware, notification SaaS, hosted bot framework or paid AI/search service unless the existing GitHub Pro + Lenovo + open-source/self-hosted architecture is proven insufficient and OWNER approves a separate amendment.

# 25. Definition of Done for Telegram V10

Block F is not complete because a bot responds to `/start`.

Telegram V10 is accepted only when:

1. OWNER-only/private access is fail-closed;
2. commands consume canonical Core DTOs;
3. no Telegram business logic duplicates Core calculations;
4. token/private data are local/redacted;
5. long polling survives restart/replay correctly;
6. alert delivery is durable, idempotent and non-noisy;
7. Mini App identity is cryptographically validated server-side;
8. deep links resolve exact authorized entities safely;
9. degraded states are explicit;
10. ordinary Web remains the detailed canonical UI;
11. Telegram contains no broker-write authority;
12. live AI surface is not enabled before WP32C prerequisites;
13. integration/recovery/security tests pass;
14. GitHub contains enough contracts/tests/runbooks for a future engineering session to reproduce the behavior without chat memory.

Final V10 acceptance additionally requires WP32C parity/evals so Telegram and Web share one accepted Cortex when AI is enabled.
