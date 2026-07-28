# Secure News Ingestion v1

## Purpose

PR-11 adds an offline sanitization and exact-deduplication boundary for news and
external text supplied by a future ingestion adapter.

External HTML and text are always treated as untrusted data. They cannot change
system rules, call tools, reveal secrets, create a trade, transfer assets or
become an instruction to the model.

PR-11 does not fetch URLs, call a broker, publish an Action, generate a
recommendation or execute any operation.

## Input contract

`NewsDocumentInputV1` requires:

- article-level document ID;
- publisher and source-authority class;
- publication and retrieval timestamps;
- optional event timestamp, kept separately from publication time;
- title and raw input content;
- explicit `plain_text` or `html` format;
- explicit `fact`, `opinion`, `forecast` or `mixed` content kind;
- entity-resolution status;
- instrument key only when an external resolver already marked the entity as
  resolved.

The pipeline never guesses a ticker or instrument identity from article text.
An unresolved or ambiguous document remains context-only.

## Output contract

`SanitizedNewsDocumentV1` contains:

- sanitized visible text only;
- source and event timestamps;
- explicit disposition;
- security flags;
- deterministic occurrence, content and event-cluster identifiers;
- `raw_content_stored=false`;
- `trading_methods=false`.

Raw HTML is not copied into the normalized output.

## HTML sanitization

The pipeline uses Python's standard `HTMLParser` only as a tokenizer for
provided content. A conservative stack tracks nested suppressed elements.

Removed or suppressed content includes:

- script and style;
- iframe, object and embed;
- forms and controls;
- template, SVG, MathML and canvas;
- elements with `hidden`;
- `aria-hidden=true`;
- inline `display:none`, `visibility:hidden` or `opacity:0`;
- common hidden utility classes.

Hidden content is still scanned for prompt-injection patterns before it is
excluded from visible output. This prevents a malicious instruction in a
script or hidden element from disappearing without a security signal.

`HTMLParser` is intentionally not treated as an HTML validator. Malformed
markup is processed fail-closed through the suppression stack and bounded
input/output sizes.

## Unicode normalization

Input and title are normalized with Unicode NFKC. Zero-width, bidi and other
formatting controls used to split or reorder suspicious phrases are removed
before pattern matching and visible-text output.

The original presence of those code points produces
`SUSPICIOUS_UNICODE`, even when the normalized text itself looks ordinary.

## Prompt-injection indicators

The bounded title, raw input and sanitized text are checked in English and
Russian for attempts to:

- override previous or system instructions;
- invoke a tool, API, function or Action;
- reveal an API key, token, password or secret;
- execute code, shell commands or scripts;
- create or submit an order or trade;
- withdraw or transfer money, funds or securities.

Severe indicators produce `rejected`. Hidden content, suspicious Unicode or an
oversized document without a severe instruction produces `context_only`.

Pattern matching is a security signal, not a guarantee that every possible
attack is detected. Later orchestration must still keep tools allowlisted,
arguments validated and external content separated from instructions.

## Dispositions

### accepted

Requires all of the following:

- non-empty sanitized text;
- no security flags;
- trusted primary, official or regulated authority;
- resolved entity supplied by an external resolver;
- content classified as fact.

`accepted` means safe enough to enter structured analysis. It does not prove
that the claim is true, complete or material.

### context_only

Used for:

- secondary sources;
- opinion, forecast or mixed content;
- unresolved or ambiguous entity;
- hidden content;
- suspicious Unicode;
- oversized/truncated content without a severe injection.

Context-only content cannot become the sole basis for a recommendation.

### rejected

Used when a severe prompt-injection indicator is found or visible content is
empty after sanitization.

## Size limits

- input contract maximum: 1,000,000 characters;
- parser boundary: 200,000 characters;
- normalized visible output: 50,000 characters.

Crossing the parser boundary produces `OVERSIZED_CONTENT`, sets
`truncated=true` and prevents acceptance.

## Deduplication

Exact duplicates use SHA-256 over normalized title and sanitized body.
Canonical selection prefers:

1. accepted over context-only over rejected;
2. primary over official over regulated over secondary over untrusted;
3. fact over mixed over opinion over forecast;
4. earlier publication when prior dimensions are equal.

Occurrence IDs remain article-specific. Repeated identical occurrences receive
unique duplicate IDs so audit records are unambiguous.

`event_cluster_id` uses resolved entity, event date and normalized title. It is
an exact deterministic cluster aid, not fuzzy semantic deduplication.

## Network and SSRF boundary

The PR-11 pipeline imports no HTTP or socket client. It accepts already supplied
content only. URL fetching, redirect policy, DNS/IP validation, MIME controls,
response-size enforcement and SSRF protection require a separate reviewed
adapter before any live ingestion is enabled.

## Compatibility and safety

PR-11 does not change:

- FastAPI routes or HTTP methods;
- GPT Action operation IDs or OpenAPI schemas;
- broker SDK calls or permissions;
- `trading_methods=false`;
- Gateway version `3.9.1`;
- Render entrypoint `app:app`.

## Rollback

Revert the PR merge commit. No runtime, OpenAPI, database, Render, secret or
broker-side migration is required.
