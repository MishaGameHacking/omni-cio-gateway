# Omni-CIO V10 — Telegram Implementation Checklist

Status: **OWNER-APPROVED PLANNING CHECKLIST / DO NOT IMPLEMENT OUT OF SEQUENCE**  
Owning block: **Block F — WP23–WP26**  
Later integration: **WP32C — shared Cortex Telegram surface**  
Product authority: `OMNI_CIO_V10_TELEGRAM_PRODUCT_AND_INTERACTION_AMENDMENT.md`

This checklist converts the Block F product contract into an implementation-ready sequence. It does not authorize Block F before all preceding Exit Gates are accepted.

# A. Preconditions before WP23

- [ ] Current program status explicitly authorizes WP23.
- [ ] Block E contracts required by Telegram navigation are accepted to the degree required by WP23.
- [ ] Block C supervision/secret-store/runtime prerequisites are accepted.
- [ ] Canonical Core APIs/DTOs used by `/status`, `/portfolio`, `/alerts`, `/system` exist and are versioned.
- [ ] Telegram product contract and message registry validate in CI.
- [ ] No implementation assumes paid bot middleware/SaaS.
- [ ] No implementation requires broker trading credentials.
- [ ] Canonical Web login already authenticates the Telegram USER account independently of the bot; bot chat/`/start`/`telegram:bot_access` are not login prerequisites.
- [ ] Define an explicit post-auth account-link contract: existing OmniCIOUserAccount + authenticated server-side Session -> one-time/short-lived link challenge -> server-bound bot chat identity.
- [ ] Bot linking cannot create accounts, mint/select tenants or bypass the canonical Telegram OIDC login/session boundary.

# B. WP23 — Telegram Bot Foundation

## B1. Before coding

- [ ] Fill `OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`.
- [ ] Record exact accepted `main` SHA.
- [ ] Inventory any existing Telegram-related code before creating new modules.
- [ ] Choose reuse decision (`REUSE_AS_IS`, `WRAP_ADAPTER`, `EXTRACT_TO_CORE`, `REWRITE_REQUIRED`, `RETIRE`) for any existing material code.
- [ ] Define package/module ownership so Telegram presentation cannot import broker execution internals directly.
- [ ] Define typed interface from Telegram adapter to Core API/client.

## B2. Transport

- [ ] Implement Bot API client behind an adapter/protocol suitable for a fake test transport.
- [ ] Implement long polling only.
- [ ] Ensure webhook is not silently active when polling starts.
- [ ] Use narrow `allowed_updates`.
- [ ] Persist/recover update cursor according to documented semantics.
- [ ] Add bounded network timeout/backoff/cancellation.
- [ ] Respect Telegram flood/rate-limit response metadata.
- [ ] Add supervisor health/readiness status.

## B3. Authorization

- [ ] Require private chat.
- [ ] Require a server-side bot-link record that belongs to an already existing authenticated OmniCIOUserAccount/Tenant.
- [ ] Link creation requires proof of the authenticated Web session plus a bounded one-time/short-lived server challenge; chat identity alone is never account authority.
- [ ] Reject unlinked, group/supergroup/channel or tenant-mismatched identities before any Core private query.
- [ ] Bot `/start` must not create an Omni-CIO account or select a tenant.
- [ ] Log denial class only; no sensitive identity/payload dump.
- [ ] Add synthetic unlinked/cross-tenant/unauthorized-user fixtures.

## B4. Commands

- [ ] `/start`.
- [ ] `/help`.
- [ ] `/status`.
- [ ] `/portfolio`.
- [ ] `/alerts`.
- [ ] `/system`.
- [ ] `/app`.
- [ ] Unknown command produces compact help, not stack trace.
- [ ] Commands are repository-controlled/configurable without manually re-entering every value in BotFather when API configuration is available.

## B5. Canonical data rule

- [ ] `/portfolio` consumes canonical DTO/API.
- [ ] `/status` consumes canonical health/data DTO/API.
- [ ] `/alerts` consumes canonical Incident/Watchtower DTO/API.
- [ ] No Telegram-specific financial arithmetic.
- [ ] Decimal/freshness/source semantics preserved.
- [ ] `unknown`, `stale`, `partial` render explicitly.

## B6. Token handling

- [ ] Real token never in GitHub.
- [ ] Token loaded only from accepted Local Secret Store/runtime secret interface.
- [ ] Redaction tests cover logs/exceptions/config dumps.
- [ ] Rotation/revocation runbook exists before live acceptance.

## B7. WP23 tests

- [ ] Pure command-router unit tests.
- [ ] Fake Telegram API send/edit/callback tests.
- [ ] Long-poll reconnect test.
- [ ] Update replay/offset test.
- [ ] Unauthorized user/chat negative tests.
- [ ] Core timeout/degraded test.
- [ ] Telegram timeout/rate-limit test.
- [ ] Secret redaction test.
- [ ] No broker-write import/authority test.
- [ ] Process restart test.

## B8. WP23 Exit Gate

PASS only if account-linked deterministic commands work through test/local integration, an unlinked or cross-tenant Telegram identity receives no private data, bot linking cannot create/select product identity, restart/replay is safe, token handling is redacted/approved, and Telegram contains no financial/broker-write business logic.

# C. WP24 — Telegram Identity and Mini App Authentication

## C1. Preconditions

- [ ] WP23 accepted.
- [ ] WP22A/Web auth boundary available to integrate without replacing ordinary-browser auth.
- [ ] Current Telegram Mini App validation specification re-checked against official docs/changelog.

## C2. `initData` validator

- [ ] Parse only bounded expected input.
- [ ] Validate current Telegram signature/hash algorithm server-side.
- [ ] Treat `initDataUnsafe` as display convenience only, never authority.
- [ ] Validate `auth_date` freshness.
- [ ] Reject stale/replayed session material.
- [ ] Resolve validated Telegram user to OWNER identity.
- [ ] Reject wrong user even if hash is otherwise valid.

## C3. V10 session

- [ ] Issue short-lived server session after Telegram validation.
- [ ] Explicit expiry.
- [ ] Explicit revoke/logout.
- [ ] Rotation/fixation defenses.
- [ ] Session cannot widen Core/broker authority beyond OWNER Web policy.
- [ ] Telegram token/broker token never reaches browser JavaScript.

## C4. Handoff references

- [ ] Opaque reference format defined.
- [ ] No private values encoded directly.
- [ ] Expiry/signature where material.
- [ ] Server-side entity authorization on every open.
- [ ] Missing/deleted/stale entity safe behavior.

## C5. WP24 tests

- [ ] Valid OWNER fixture.
- [ ] Tampered hash/signature.
- [ ] Wrong OWNER user ID.
- [ ] Old `auth_date`.
- [ ] Replay.
- [ ] Modified/forged deep link.
- [ ] Expired/revoked session.
- [ ] Direct backend call without Telegram/Web authorization.
- [ ] CSRF/origin/session controls as required by WP22A.
- [ ] Secret/private-data leak tests.

## C6. WP24 Exit Gate

PASS only if Telegram Mini App obtains OWNER session solely after server-side cryptographic validation and freshness checks, and the resulting session does not bypass ordinary Core/security/Real-money authority.

# D. WP25 — Alerts and Durable Delivery

## D1. Severity policy

- [ ] CRITICAL.
- [ ] IMPORTANT.
- [ ] INFO.
- [ ] SILENT.
- [ ] Critical bypasses quiet hours.
- [ ] Non-critical quiet-hours policy documented.
- [ ] Severity comes from deterministic policy/Incident state, not LLM free text.

## D2. Message registry

- [ ] Implement/validate all message IDs in `V10_TELEGRAM_MESSAGE_REGISTRY.json` owned by Block F.
- [ ] Version included in rendering/tests.
- [ ] Untrusted text escaped.
- [ ] Privacy level enforced.
- [ ] Long response handoff rather than uncontrolled chat split.

## D3. Durable delivery state

- [ ] Durable `TelegramDelivery` model/job.
- [ ] Delivery ID.
- [ ] Correlation/incident ID.
- [ ] Idempotency key.
- [ ] Message type/version.
- [ ] Target OWNER identity reference.
- [ ] Attempts/time state.
- [ ] Telegram message ID after confirmed delivery.
- [ ] Sanitized error class.

## D4. Anti-spam lifecycle

- [ ] Clean Watchtower run sends nothing.
- [ ] Duplicate event dedup.
- [ ] Persistent condition does not repeatedly notify.
- [ ] Incident progression edits same message where practical.
- [ ] New message on defined severity escalation.
- [ ] New message on defined reopen.
- [ ] Owner-action-required transition handled explicitly.

## D5. Ambiguous delivery/retry

- [ ] Network timeout before response has explicit `UNKNOWN_DELIVERY` behavior.
- [ ] Blind duplicate send is forbidden.
- [ ] `retry_after` handled.
- [ ] Retry attempts bounded.
- [ ] Permanent validation/auth failures do not loop forever.

## D6. WP25 tests

- [ ] Clean/no-alert.
- [ ] Duplicate incident.
- [ ] Persistent incident.
- [ ] Escalation.
- [ ] Resolved/reopened.
- [ ] Send success.
- [ ] Send timeout ambiguity.
- [ ] Rate limit.
- [ ] Edit success/failure fallback.
- [ ] Crash before send.
- [ ] Crash after send before local state persistence.
- [ ] Queue recovery after restart.
- [ ] Redaction/privacy.

## D7. WP25 Exit Gate

PASS only if a material incident produces one coherent, auditable Telegram notification lifecycle without duplicate storms and clean/no-change operation is silent.

# E. WP26 — Web / Mini App Integration

## E1. Menu/App launch

- [ ] `/app` uses canonical V10 Web URL/configuration.
- [ ] Menu button opens Mini App only after auth/ingress prerequisites are green.
- [ ] No dead/publicly unsafe link before gate.

## E2. Exact route handoff

Where owning Web routes exist:

- [ ] Portfolio route.
- [ ] Incident route.
- [ ] Research route.
- [ ] Decision route.
- [ ] System route.
- [ ] Missing/deleted entity behavior.
- [ ] Opaque validated reference.

## E3. Same frontend rule

- [ ] Telegram Mini App uses same V10 frontend codebase.
- [ ] Same canonical APIs.
- [ ] No duplicate financial formula.
- [ ] No Telegram-only shadow state/database.
- [ ] Mobile/responsive/safe-area behavior.
- [ ] Telegram theme mapping.
- [ ] Navigation/back behavior.

## E4. AI boundary

- [ ] Block F may expose capability flag/placeholder only.
- [ ] No live Telegram Cortex chat before WP32C.
- [ ] AI-disabled state is explicit and not an error for deterministic Telegram functions.

## E5. WP26 tests

- [ ] Alert -> exact incident.
- [ ] Portfolio -> exact portfolio route.
- [ ] Forged/expired handoff.
- [ ] Wrong user/session.
- [ ] Mobile safe area/theme.
- [ ] Ordinary Web browser still works.
- [ ] Missing entity.
- [ ] Long analysis handoff.
- [ ] AI disabled/degraded capability state.

## E6. WP26 Exit Gate

PASS only if Telegram reliably opens the exact authorized detailed V10 Web context, using the same frontend/Core contracts and no client-side/private-link authority.

# F. WP32C — Later shared Cortex activation

This section is planning only and must not be pulled into Block F early.

## F1. Preconditions

- [ ] WP23–WP26 accepted.
- [ ] AI Provider abstraction accepted.
- [ ] Knowledge/RAG accepted.
- [ ] Tool Registry/authority firewall accepted.
- [ ] shared Agent Orchestrator accepted.
- [ ] required AI security/evals green.

## F2. Activation

- [ ] Telegram free text routes to same Orchestrator as Web.
- [ ] No Telegram-specific model.
- [ ] No Telegram-specific prompt authority.
- [ ] No Telegram-specific knowledge store.
- [ ] Same Core/evidence for same request.
- [ ] Compact response renderer only.
- [ ] Long research creates durable job and later `TG_RESEARCH_READY_V1`.
- [ ] AI provider offline leaves deterministic Telegram functions operational.

## F3. WP32C Telegram acceptance

- [ ] Same intent Web vs Telegram -> equivalent canonical evidence/tool outputs.
- [ ] Prompt injection.
- [ ] unsupported request.
- [ ] tool loop.
- [ ] stale session.
- [ ] long response handoff.
- [ ] provider failure.
- [ ] zero broker-write authority leakage.
- [ ] zero invented exact financial facts in critical fixture set.

# G. Security checklist across Block F

- [ ] No token in repository/history/artifact/log.
- [ ] OWNER-only private chat fail-closed.
- [ ] No group/channel private data.
- [ ] `initData` server validation.
- [ ] replay/freshness controls.
- [ ] callback data opaque and reauthorized.
- [ ] external/AI text escaped.
- [ ] URL/start parameters contain no authority/private payload.
- [ ] no generic destructive/admin tool.
- [ ] no broker-write tool.
- [ ] no Real-money approval implied by Telegram message/button.
- [ ] account identifiers masked.
- [ ] diagnostic bundle safe.

# H. Observability checklist

- [ ] polling health.
- [ ] last processed update/time.
- [ ] auth denial counts.
- [ ] delivery queue depth/age.
- [ ] send/edit success/failure.
- [ ] rate-limit counters.
- [ ] callback stale/failure.
- [ ] Mini App auth failure/replay.
- [ ] current Telegram contract/message-registry version.
- [ ] correlation IDs from incident/job to Telegram delivery.

# I. Documentation required before Block F completion

- [ ] Telegram architecture/runbook.
- [ ] BotFather/bootstrap runbook with no token value.
- [ ] token rotation/revocation procedure.
- [ ] long-poll restart/recovery procedure.
- [ ] Mini App auth flow.
- [ ] message registry docs/examples.
- [ ] alert delivery state model.
- [ ] degraded-mode matrix.
- [ ] OWNER acceptance checklist.
- [ ] update current status/architecture/evidence in same PRs.

# J. Block F completion statement

Block F reaches its planned 8% only after WP23–WP26 Exit Gates are accepted. A responding Telegram bot, a successful `/start`, a screenshot or a BotFather-created token is not Block F completion.

Conversational AI parity is a later Block G/WP32C responsibility and does not retroactively permit Block F to implement AI early.
