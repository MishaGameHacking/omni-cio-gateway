# Omni-CIO V10 — WP20 Research Dossier UI Execution Contract

## 1. WP identity

- Block: E — Omni-CIO Web Platform
- WP: WP20
- Title: Research Dossier UI
- Authorized by current program status: YES
- Prior Exit Gate proven by: WP19 PR #308 squash-merged to `058e53a76e6f6aeabe32eb6711cb5168417d5093`; status PR #309 squash-merged to `7251d68fff381a2cb263a0e9d565b002d1bbebe3`; post-status Regression Shield #1489 / run `31732149041` SUCCESS on exact accepted main.

## 2. Accepted baseline

- Accepted `main` SHA: `7251d68fff381a2cb263a0e9d565b002d1bbebe3`.
- Protected baseline: V9 remains the controlled-maintenance/recovery baseline; V10 Web remains one local/private source-controlled app with server-side session scope.
- Relevant Master Plan: Block E / WP20; dependency `WP19, Block G contracts`; Exit Gate that a source fact must never be visually confusable with AI/inference.
- Relevant accepted contracts: `V10_AI_CORTEX_CONTRACT.json`, `V10_SYSTEM_ARCHITECTURE.md`, `V10_THREAT_MODEL.md`, `V10_V9_TO_V10_PARITY_LEDGER.json`, `V10_COMPONENT_REUSE_MATRIX.json`, WP16–WP19 Web contracts, and canonical `omni_cio.contracts.v1.research_evidence`.

## 3. Purpose

Make research provenance and uncertainty understandable in the existing OWNER Web cabinet without starting Block G runtime work. WP20 presents canonical source facts, timestamps, freshness, contradictions, unknown/coverage gaps and confidence context; it may also present a separately supplied AI-generated narrative only as explicitly non-authoritative presentation.

## 4. Inputs and prerequisites

- accepted WP19 local/private authenticated Web shell and read-only presentation boundary;
- accepted `ResearchDossierV1`, `EvidenceRecordV1`, coverage-gap and contradiction contracts;
- accepted V9 Research & Evidence semantics and protected tests;
- accepted Block G planning/interface contracts from the active Concrete Execution Plan amendment and `V10_AI_CORTEX_CONTRACT.json`;
- WP16 design system and WP17 session scope;
- deterministic synthetic dossier fixtures for Web acceptance.

The Master Plan dependency on **Block G contracts is satisfied as an interface dependency only**. It does not authorize SearchProvider/SearXNG, fetch/browser research, Ollama, LangGraph, RAG, tool-registry runtime or AI generation implementation in WP20.

## 5. Existing implementation to reuse

### Canonical research/evidence contract

- path: `omni_cio/contracts/v1/research_evidence.py`;
- behavior: versioned typed evidence, source identity/class/authority, UTC timestamps, decision-grade/context separation, explicit coverage gaps and contradictions, deterministic dossier hash, `raw_content_stored=false`, `trading_methods=false`;
- parity ledger: `PARITY-RESEARCH-EVIDENCE` (`CONTRACT_DEFINED`);
- reuse decision: use the accepted canonical contract through the existing `COMP-V10-CANONICAL-DOMAIN-IDENTITY` WRAP_ADAPTER boundary; do not rewrite research semantics.

### Protected V9 Research & Evidence Engine

- paths: `omni_cio/research/*`, `docs/architecture/V9_RESEARCH_EVIDENCE_ENGINE.md`, protecting V9 tests;
- behavior: deterministic source hierarchy, exact target binding, explicit missing/contradictory evidence, hostile external text treated as data, source-order-invariant dossier identity;
- reuse: REUSE SEMANTICS / READ-ONLY PRESENTATION; do not migrate or extend the collector/runtime in WP20.

### Existing Web platform

- paths: `apps/web`, `apps/api/app.py`, `omni_cio/web`;
- behavior: one Web app, WP16 design system, WP17 server-side sessions, WP18/WP19 fail-closed read surfaces;
- reuse: EXTEND EXISTING WEB APP ONLY.

## 6. Allowed changes

- add a WP20 read-only Web projection module under `omni_cio/web`;
- add a GET-only research dossier route to the existing local/private API;
- add Research page/types/styles/tests inside the existing `apps/web` tree;
- add deterministic sanitized WP20 fixtures, browser evidence and focused CI;
- add WP20 architecture/product documentation required for acceptance.

## 7. Explicit non-goals

- no Block G SearchProvider/SearXNG, HTTP fetcher, Playwright research collector, RAG, Ollama, LangGraph, model runtime, prompt policy or tool-registry implementation;
- no research source mutation, refresh button that performs outbound research, AI generation endpoint or arbitrary URL fetch;
- no new persistence/migration or second evidence store;
- no Credit/Fund analytical-engine rewrite;
- no WP21 Decision/Risk/Plan implementation;
- no public Internet ingress or public multi-user activation;
- no broker-write, trading-secret or Real-execution authority.

## 8. Interfaces/contracts

### `GET /api/v10/web/research-dossiers`

- producer: local/private FastAPI Web runtime;
- consumer: existing React Application Shell `/research` route;
- version: WP20 Web view schema `1.0.0`;
- compatibility: additive Web view; canonical research contracts are not mutated;
- auth/scope: server-side session supplies tenant scope; client cannot choose tenant;
- default runtime before Block G producer exists: explicit `EMPTY`/`UNAVAILABLE`, never fabricated dossier data.

### Canonical fact projection

Every represented fact retains:

- typed fact key/value and material/context semantics;
- source class/authority and safe source label/location;
- retrieved timestamp and optional published/effective timestamp;
- freshness state derived from dossier requirement age when deterministically resolvable, otherwise explicit `UNKNOWN`;
- record hash for deterministic correlation;
- instrument binding from the canonical dossier target.

Unsafe source locations are displayed as text only; only bounded `http`/`https` locations may become links. No `dangerouslySetInnerHTML` or raw active document content is permitted.

### AI narrative projection

A future Block G producer may supply an optional narrative to the WP20 adapter only if it is bound to the exact `dossier_sha256`. The Web view labels it `AI_GENERATED_NON_AUTHORITATIVE`; it is never inserted into the canonical facts array, never satisfies coverage, never resolves contradictions and never becomes a source link. WP20 does not define the future canonical Block G AI-output model; it defines only this presentation envelope.

## 9. Data/persistence effects

- migration required: NO;
- persistent writes: NONE;
- rollback: remove/revert the WP20 Web/API projection; canonical research/evidence data remains untouched;
- private data: tenant scope resolved server-side; deterministic acceptance fixtures contain no private OWNER portfolio data;
- raw external documents are never returned or stored by WP20.

## 10. Security/authority effects

- secret access: NO;
- broker authority: NO;
- OS/runtime privileges: NO;
- GitHub permissions: NO;
- new external ingress: NO;
- AI tool authority: NO;
- Real execution path: NO.

Threat controls: prompt-injection-shaped text remains inert escaped text; unsafe URLs are non-clickable; model narrative is visually/semantically non-authoritative; source/inference separation fails closed.

## 11. Normal-path acceptance tests

- authenticated Research route renders dossier identity and event/fact timeline;
- source facts show source class/authority, safe label/link, published/retrieved/effective time as available, freshness, material/context state and confidence/provenance context;
- coverage gaps/unknowns are visible;
- unresolved contradictions identify affected fact and conflicting source records;
- issuer/security identity and Credit/Fund navigation links remain read-only navigation metadata;
- optional AI narrative renders in a separately labeled non-authoritative region bound to the dossier hash;
- long fact text and long source lists remain readable/responsive.

## 12. Negative/failure tests

- unauthenticated API request returns 401;
- missing producer/dossier returns explicit EMPTY/UNAVAILABLE rather than fake success;
- malformed/incompatible projection fails closed;
- stale evidence is labelled stale/unknown and cannot be visually presented as fresh;
- contradictory records remain contradictory rather than silently merged;
- `javascript:`, `data:` and other unsafe source locations are never clickable;
- HTML/script/prompt-injection-shaped source text renders inertly and never as active markup;
- AI narrative cannot appear inside canonical fact/source components and cannot carry decision-grade/source-authority styling;
- oversized dossier/source/fact collections are bounded and fail explicitly;
- browser/source contract contains no broker secret, full provider account ID, private portfolio payload or broker-write surface.

## 13. Observability

- response includes generated timestamp, state and bounded counts;
- UI has loading/empty/unavailable/partial states;
- no raw source document logging;
- canonical dossier/record hashes provide safe correlation;
- acceptance retains only deterministic synthetic browser/test evidence.

## 14. CI routing

- Fast hosted checks: existing path-aware lane; report billing startup failure truthfully if it cannot start;
- hosted clean-room compatibility: existing repository lane only; no new dependency;
- Lenovo authoritative: focused WP20 Web/Python gate plus existing authoritative Self-Hosted Windows CI and Regression Shield;
- GPU AI eval: NO, because WP20 does not implement AI behavior/runtime;
- release/recovery matrix: NO new durable state or authority; existing Regression Shield is sufficient.

## 15. Rollback/recovery

Revert the WP20 Web/API files. There is no migration, source refresh or research mutation to undo. Accepted WP19 and earlier Web pages remain functional, canonical dossier/evidence contracts remain unchanged, and V9 rollback is unaffected.

## 16. Exit Gate

PASS only if, on the exact reviewed PR head, deterministic Python/Web/browser tests and focused WP20 audit are GREEN, authoritative Self-Hosted Windows CI is GREEN, review has zero unresolved blocking threads, full diff is reviewed, and **a fact from a source can never be visually or semantically confused with AI/inference**. Missing/stale/contradictory evidence must remain explicit.

## 17. Required acceptance evidence

- exact PR head SHA;
- focused WP20 audit run ID/result;
- exact-head authoritative Self-Hosted Windows CI result;
- Web typecheck/lint/unit/build plus browser evidence;
- Python projection tests for auth/bounds/source safety/freshness/contradiction/AI separation;
- malicious-markup and unsafe-link tests;
- zero unresolved blocking review threads;
- squash merge SHA and required post-merge Regression Shield before WP20 is COMPLETE.

## 18. Documentation/status updates in the same PR

- `docs/architecture/V10_WP20_EXECUTION_CONTRACT.md`;
- WP20 Research Dossier Web-view contract;
- focused tests/fixtures/workflow.

Program status does not advance to WP21 merely because implementation tests pass.

## 19. Next WP unlock

WP21 remains LOCKED until WP20 is squash-merged, exact post-merge required gates are GREEN, and the required status transition records WP20 acceptance according to the Master Plan.

## 20. Scope-discovery rule

Anything requiring actual Research Collector, outbound Web retrieval, RAG, model generation, AI tool execution, new persistence or later Credit/Fund/Decision semantics is a Block G/later-WP dependency or explicit blocker. It is never silently implemented inside WP20. OWNER physical/secret action is not expected for this WP.
