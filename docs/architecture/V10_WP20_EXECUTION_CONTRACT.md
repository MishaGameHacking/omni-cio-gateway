# V10 WP20 — Research Dossier UI execution contract

Status: **WP20 IMPLEMENTATION CONTRACT / EXIT GATE EVIDENCE REQUIRED**  
Block: **E — Web Platform**  
Program authority: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Accepted baseline: `7251d68fff381a2cb263a0e9d565b002d1bbebe3` (WP19 COMPLETE / WP20 AUTHORIZED NEXT)

## 1. Purpose

Implement WP20 as a read-only Research Dossier projection inside the one accepted V10 Web App. The page makes canonical structured evidence understandable without allowing UI text, external content, or AI/inference to become financial truth.

## 2. Dependency/interface check

WP20 consumes accepted contracts; it does not start Block G runtime work out of order.

- `omni_cio.contracts.v1.research_evidence.ResearchDossierV1` is the canonical dossier/evidence schema.
- `docs/architecture/V9_RESEARCH_EVIDENCE_ENGINE.md` defines source provenance, freshness, coverage gaps, contradiction and decision-grade semantics.
- `docs/architecture/V10_AI_CORTEX_CONTRACT.json` is sufficient for the presentation boundary: AI may interpret/explain/research, but deterministic Core owns canonical truth and AI has no broker-write or ledger authority.
- `docs/architecture/V10_V9_TO_V10_PARITY_LEDGER.json` keeps Research Collector/Evidence Store runtime ownership in Block G.
- WP13 `research_cache` + `content_blobs` are reused as the bounded local durable projection source. No second research database, queue, vector store, or evidence store is added.

Result: **dependency check PASS for WP20 UI implementation**. Block G runtime remains locked.

## 3. Allowed changes

WP20 may add:

- tenant-scoped read projection in `omni_cio/web/`;
- one authenticated `GET /api/v10/web/research-dossiers` endpoint;
- Research Dossier React/CSS inside the accepted application shell;
- focused Python/Web/browser tests and a Lenovo audit workflow;
- WP20 architecture documentation.

## 4. Explicit non-goals

WP20 must not:

- implement Research Collector, SearXNG/HTTP/Playwright collection, AI/Cortex model calls, embeddings, vector search, or new RAG persistence;
- create/modify canonical evidence facts in Web;
- infer missing facts, silently resolve contradictions, or relabel stale evidence as fresh;
- add public ingress, multi-user production activation, Telegram runtime, broker-write authority, transfer/withdraw authority, or Real execution;
- change `app:app`, `trading_methods=false`, or `REAL_TRADING_ENABLED=false`.

## 5. Read model

The production reader is fail-closed:

1. resolve tenant only from the accepted server-side Web session;
2. select only that tenant's bounded `research_cache` rows;
3. join the accepted `content_blobs` identity referenced by `content_sha256`;
4. require the explicit `ResearchDossierV1` `schema_ref`;
5. validate the full payload with `ResearchDossierV1.model_validate`;
6. when a cache row binds an instrument, require exact `dossier.target.instrument_uid == instruments.broker_uid`;
7. ignore invalid/mismatched dossiers while returning explicit invalid/truncated state;
8. never return raw blob bytes to the browser.

WP13 already computes SHA-256 from blob bytes at `put_content_blob()` and rejects hash-identity conflicts, so WP20 reuses that accepted durability invariant rather than inventing a second integrity implementation.

## 6. Presentation semantics

Canonical source fact view includes:

- fact type/key/value;
- source provider/class/authority/source ID;
- safe source link when the location passes the Web `http/https` allowlist;
- published/effective/retrieved timestamps;
- freshness derived from accepted requirement `max_age_seconds` semantics;
- deterministic evidence-use/conflict presentation labels;
- contradiction metadata and evidence hash identity.

The UI's `DECISION_GRADE`, `LIMITED`, `CONTEXT_ONLY`, and `REJECTED` labels are deterministic presentation categories derived from canonical evidence use/coverage/contradiction state. They are **not** probabilistic model confidence.

Coverage gaps remain explicit as `Unknowns / coverage gaps`. Contradictions remain explicit and unresolved unless the canonical dossier says otherwise. Cache expiry is shown as STALE rather than converted to success.

## 7. AI/inference separation

WP20 reserves a dedicated presentation envelope for future AI summaries. It is intentionally separate from canonical facts:

- canonical facts use `data-origin="canonical-*"` zones;
- AI/inference uses `data-origin="ai-inference"`;
- AI region is explicitly labeled `NON-AUTHORITATIVE` and `НЕ ИСТОЧНИК ФАКТОВ`;
- production WP20 returns `ai_summary.state=NOT_AVAILABLE` because Block G runtime is not started;
- browser contract tests additionally exercise a synthetic `AVAILABLE` envelope to prove that even present AI text remains visually/semantically separate and is rendered as inert text.

The future Block G implementation may populate the envelope only through a reviewed adapter; WP20 does not grant AI any canonical state mutation or broker authority.

## 8. External text and links

All labels/values are rendered by React as strings. `dangerouslySetInnerHTML` is prohibited. Source locations become anchors only when parsed as bounded `http`/`https` URLs with a host and without embedded user credentials. Rejected locations remain metadata-only and are not emitted as clickable links.

## 9. Tests / exit evidence

WP20 acceptance must prove at minimum:

- long fact text and long source lists remain renderable and bounded;
- stale research is visibly stale;
- unresolved contradiction and unknown/coverage-gap states remain visible;
- markup-looking external strings are displayed as text and do not create injected DOM nodes;
- canonical source facts and AI/inference occupy distinct origin zones;
- source provenance/timestamps/freshness/confidence are visible;
- event timeline and Security/Credit/Fund links render from the read model;
- session/tenant boundary and no-store response behavior hold;
- reader is bounded and read-only;
- no broker-write/Real/secret/browser-storage surface is introduced;
- accepted repository/Web/regression guards stay green.

**Exit Gate:** a fact from a source must never be visually confusable with AI/inference.

## 10. Authority invariants

Unchanged:

- `app:app`
- `trading_methods=false`
- `REAL_TRADING_ENABLED=false`
- broker write authority: none added
- transfer/withdraw authority: none added
- V9 rollback: protected
