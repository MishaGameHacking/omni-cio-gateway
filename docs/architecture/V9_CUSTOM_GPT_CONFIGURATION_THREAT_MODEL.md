# Omni-CIO v9.0.0 — Custom GPT Configuration Threat Model

Target config release: **v9.0.0**.  
Protected rollback Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.

## Protected assets

- identity of the single existing Omni-CIO GPT;
- canonical v9.0.0 Instructions and Knowledge manifest;
- production OpenAPI/Action authentication boundary;
- Gateway, broker, Upstash and QStash secret values held only in their external systems;
- protected v8.6.1 rollback configuration;
- existing owner-confirmed real execution lifecycle;
- correctness of statements about which v9 capabilities actually ran.

## Threats and controls

### Duplicate bot / split source of truth

Threat: WP15 creates a new GPT instead of upgrading the existing one, leaving two independently configured investment assistants.

Controls: upgrade-in-place is a hard release invariant; setup/runbook says Edit existing GPT and Update, never Create; version-consistency checks require one canonical target identity and one Gateway.

### Instruction / Knowledge version drift

Threat: v9.0.0 name is applied with old v8 Instructions or stale/duplicate Knowledge.

Controls: one target Instructions path, one exact Knowledge manifest, machine-checked file set and consistent target release markers across recovery docs.

### Behavior hidden in Knowledge

Threat: critical safety behavior is placed only in retrieved Knowledge and can be missed.

Control: execution, routing and safety invariants stay in compact Instructions; Knowledge is reference material only.

### Invented Action capability

Threat: GPT assumes internal WP1–WP14 Python modules are callable Actions even though effective OpenAPI does not expose them.

Controls: Instructions explicitly distinguish effective Actions from internal deterministic engines; operationIds are documented against production `/openapi.json`; nonexistent operations must never be claimed or called.

### OpenAPI authority expansion

Threat: importing a schema silently broadens real-money authority.

Controls: WP15 adds no broker-write routes; effective surface remains governed by existing server feature flags/readiness; consequential Real operations remain exact-owner-confirmed, immutable, idempotent and broker-reconciled.

### Secret leakage into GPT configuration

Threat: external authentication/storage/scheduler values are pasted into Instructions, Knowledge, examples or GitHub.

Controls: only secret names/roles are documented; the Gateway authentication value is entered only in GPT Action authentication UI; broker/Upstash/QStash values remain external server secrets; repository secret scan remains required.

### Account/privacy leakage

Threat: full account identifier, private portfolio data or broker reports are uploaded as reusable GPT Knowledge.

Controls: Knowledge manifest excludes account-specific/private raw data; broker facts come through authenticated Gateway Actions; user-facing account identity remains masked.

### Stale model-name dependency

Threat: recovery fails because a hard-coded ChatGPT model label is renamed or retired.

Control: choose a currently available non-Pro model that supports Actions and validate in Preview; model marketing name is not part of config identity.

### Apps/Actions conflict

Threat: Apps are enabled alongside custom Actions and alter tool routing or make the configured Action unavailable.

Control: canonical WP15 capability policy uses Actions ON and Apps OFF.

### Confirmation bypass through instructions

Threat: v9 autonomy language is interpreted as permission to submit real trades without a new exact owner confirmation.

Controls: Instructions preserve REAL READ-ONLY / REAL EXECUTION / SANDBOX separation and prohibit autonomous recurring real execution, retries after ambiguous possible-submit, margin/short and transfers. Server enforcement remains authoritative.

### False v9 evidence

Threat: GPT says policy/risk/optimizer/plan/Watchtower/journal engine ran merely because its rules are described in Knowledge.

Control: distinguish observed Gateway results, public-web context, internal reference semantics and calculations. Claims of server execution require returned Action/evidence. Otherwise present reasoning as advisory analysis, not server-produced v9 evidence.

### Recovery from screenshots/chats

Threat: stale conversational instructions overwrite repository configuration.

Control: current `main` recovery docs are authoritative. Old chats/screenshots are informational only.

## External/manual boundary

GitHub cannot press Update in GPT Editor, upload files to the user's existing GPT, or know external secret values. Repository gates therefore prove **configuration readiness**, not applied production acceptance.

Owner Preview acceptance is required after merge. Until recorded, the applied GPT remains v8.6.1 and must be described that way.
