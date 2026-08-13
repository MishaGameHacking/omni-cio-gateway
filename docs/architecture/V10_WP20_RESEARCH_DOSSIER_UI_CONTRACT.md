# Omni-CIO V10 — WP20 Research Dossier UI Contract

Status: WP20 implementation contract

## Product rule

The Research page has two permanently distinct information channels:

1. **SOURCE FACT / canonical evidence** — facts derived only from accepted `ResearchDossierV1` records with source identity, authority, timestamps, freshness and contradiction/coverage state.
2. **AI / INFERENCE / non-authoritative** — an optional narrative that may explain a dossier but cannot become a fact, source, coverage record, contradiction resolution or deterministic decision input.

The WP20 Exit Gate is violated if a reasonable user or assistive technology can confuse those channels.

## Canonical fact presentation

Each represented fact exposes:

- canonical fact key and typed value;
- material/context classification and evidence-use class;
- source provider, source class and authority;
- retrieved time, and published/effective time when available;
- deterministic freshness (`FRESH`, `STALE`, `UNKNOWN`) relative to matching dossier requirements;
- evidence confidence context (`SUPPORTED`, `CONTEXT_ONLY`, `STALE`, `CONTRADICTED`, `UNKNOWN`), never an invented model probability;
- safe source location text and an optional clickable `http`/`https` link only;
- deterministic record hash for correlation.

Rejected evidence records are not rendered as source facts.

## Uncertainty presentation

- material/critical coverage gaps remain visible under `unknowns`;
- unresolved contradictions remain visible with their source-record identities and distinct canonical values;
- stale evidence is never upgraded to fresh by the browser;
- unknown freshness remains `UNKNOWN`;
- a dossier is `PARTIAL` when canonical readiness/freshness/conflict state is incomplete.

## AI narrative presentation

The Web adapter accepts an optional narrative only when it is bound to the exact `dossier_sha256`. It is returned as:

- `kind = AI_GENERATED_NON_AUTHORITATIVE`;
- `authoritative = false`;
- a separate DOM authority region `data-authority="ai-non-authoritative"`;
- a visible text label `НЕ ИСТОЧНИК ФАКТА`.

The narrative has no source-authority styling and is never inserted into the facts/timeline arrays.

WP20 does not implement or select the model, prompt, SearchProvider, RAG, tool registry or generation runtime. Those remain Block G responsibilities.

## External-text and source-link safety

Research text is rendered through normal React text interpolation. `dangerouslySetInnerHTML`/raw HTML injection is prohibited. Source locations become links only when the backend validates an `http` or `https` URL with a network location and without embedded credentials. Unsupported schemes remain inert text.

## Related analysis links

Credit/Fund links are optional read-only internal application paths supplied by a future accepted producer. External URLs or paths outside the application are rejected. Absence is explicit and does not fabricate downstream analysis.

## Runtime state before Block G producer

The local/private runtime installs WP20 with an empty provider. Therefore `/api/v10/web/research-dossiers` returns an explicit `EMPTY` state until a later accepted Block G producer is wired. This is intentional: completing WP20 does not claim that autonomous research or AI generation is already running.

## Bounds

The Web projection rejects oversized dossier/fact/contradiction/gap/link/narrative collections rather than performing unbounded rendering or silent truncation. No raw source document is returned to the browser.

## Authority invariants

WP20 adds no secret access, broker write, research mutation, external retrieval, public ingress, AI tool authority or Real execution. `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and protected V9 rollback remain unchanged.
