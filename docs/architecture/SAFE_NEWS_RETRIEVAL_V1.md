# Safe News Retrieval V1

## Purpose

`retrieve_safe_news_chunks` builds a deterministic, citation-backed retrieval bundle from documents that have already passed the existing news sanitation and deduplication pipeline.

The module is deliberately local and lexical. It does not fetch the web, call an embedding service, execute document instructions, produce a market forecast or recommend a trade.

## Trust boundary

Only canonical documents with all of the following properties can enter retrieval:

- `disposition=accepted`;
- factual content;
- resolved instrument identity;
- exact requested instrument key;
- authority allowed by retrieval policy;
- no injection flags;
- event time inside the configured lookback;
- no material future timestamp.

`context_only` and `rejected` documents are counted and excluded. Their text is never returned as a retrieval chunk.

The layer operates only on `sanitized_text`. Raw HTML and raw content are not stored or returned.

## Event time

Freshness uses `event_at` when available and falls back to `published_at`. This prevents a recent repost from making an old underlying event appear current.

## Exact deduplication

The existing `deduplicate_news_documents` function runs before retrieval. Exact sanitized-content duplicates collapse to one canonical occurrence. Canonical selection retains the existing disposition, authority and content-kind ranking.

## Deterministic chunks

Text is split into bounded character ranges with configurable overlap. Every chunk includes:

- occurrence ID;
- source document ID;
- event cluster ID;
- publisher and authority;
- title;
- publication, event and retrieval timestamps;
- chunk index;
- exact start/end offsets;
- exact excerpt.

The citation contract verifies that offset length equals excerpt length.

## Lexical scoring

V1 uses an explicit weighted score:

`total = term coverage × 0.50 + authority × 0.30 + recency × 0.20`

Authority scores are:

- primary: `1.00`;
- official: `0.90`;
- regulated: `0.80`.

Recency declines linearly to zero across the configured lookback. Query terms are normalized and deduplicated by contract.

The result always warns that retrieval is lexical-only and that semantic reranking was not applied.

## Event diversity

A policy limit caps chunks returned from one `event_cluster_id`. This reduces the chance that one event or long article crowds out all other evidence.

## Audit counts

The result reports:

- input and canonical document counts;
- exact duplicates;
- eligible documents and matching chunks;
- returned chunks;
- unique publishers and event clusters;
- context-only, rejected, wrong-instrument, stricter-authority, future, stale and no-match exclusions.

Input, canonical and duplicate counts reconcile in the result contract. Publisher and event-cluster counts reconcile against returned citations.

## Security invariants

Every result retains:

- `accepted_documents_only=true`;
- `facts_only=true`;
- `source_text_treated_as_data=true`;
- `external_instructions_executed=false`;
- `raw_content_stored=false`;
- `no_price_forecast=true`;
- `no_investment_recommendation=true`;
- `execution_ready=false`;
- `trading_methods=false`.

## Limitations

V1 does not provide:

- semantic embeddings;
- vector search;
- cross-encoder reranking;
- contradiction resolution;
- near-duplicate clustering beyond existing event IDs;
- claim extraction;
- multi-source fact verification;
- automatic web ingestion;
- public API exposure.

A later stage may add semantic retrieval only behind the same accepted-document and citation boundaries.

## Compatibility

The module adds no broker call, order method, transfer/withdrawal method, FastAPI route, OpenAPI operation or GPT Action. Gateway version remains `3.9.1`; Render entrypoint remains `app:app`.

## Tests

Focused tests cover deterministic ranking, exact citations, prompt-injection exclusion, context-only exclusion, stricter authority policy, wrong instrument, future and stale events, exact deduplication, event-cluster caps, no-match results, result limits, query normalization, score/citation/result tampering and timezone safety.

## Rollback

Revert the PR merge commit. Existing sanitation, market, equity, fund, technical, bond, paper, public API and broker layers remain independent.
