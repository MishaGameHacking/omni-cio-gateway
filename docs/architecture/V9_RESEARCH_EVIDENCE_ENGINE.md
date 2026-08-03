# Omni-CIO v9 — Research & Evidence Engine

Status: **WP5 implementation contract**  
Parent program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Protected production baseline: **Omni-CIO v8.6.1**

## 1. Purpose

WP5 turns the bounded WP4 research shortlist into reproducible research dossiers. It does not choose arbitrary tickers, size trades or execute orders.

Canonical flow:

`WP4 shortlist → exact target binding → structured/official evidence → sanitised context → coverage/contradiction gates → immutable dossier fingerprint`

Every material fact used by later decision engines must carry provenance and timestamps. Missing or contradictory critical evidence is represented explicitly; it is never silently filled by model inference.

## 2. Exact upstream binding

`bind_research_target()` accepts only a `CandidateFunnelResultV1` that is `decision_ready=true` and only a security actually present in `research_shortlist`.

The resulting target binds:

- exact `funnel_sha256`;
- exact WP4 `candidate_id`;
- verified instrument UID and type;
- optional T-Invest `asset_uid` only when accompanied by trusted broker provenance.

A caller cannot switch the researched instrument while keeping another funnel fingerprint.

## 3. Source hierarchy

Decision-grade evidence priority is deterministic:

1. broker;
2. exchange;
3. issuer;
4. official disclosure;
5. regulator;
6. rating agency for its domain;
7. reliable media only as context.

`PRIMARY`, `OFFICIAL` and `REGULATED` are the only authorities eligible for decision-grade records. `MEDIA_CONTEXT` is contractually restricted to `CONTEXT_ONLY`.

Source priority is used for deterministic ordering, not for silently overwriting contradictions. Two trusted sources that materially disagree remain an explicit contradiction until later resolution.

## 4. Current structured T-Invest inputs

WP5 initially normalizes the current read-only broker research surfaces:

- `GetAssetFundamentals`;
- `GetAssetReports`;
- `GetDividends`;
- `GetBondEvents` for bonds.

The adapter receives a token from its caller and does not read trading/Sandbox credentials. It contains no Orders, StopOrders, Sandbox mutation, transfer or withdrawal call.

T-Invest asset fundamentals are requested only when `asset_uid` is tied to trusted T-Invest broker provenance. Response rows must repeat the exact asset UID before they are normalized.

T-Invest documents zero-valued fundamental fields as unavailable data. WP5 therefore omits zero fundamentals instead of converting them into verified economic zeros.

## 5. Official/regulatory evidence

`official_evidence_record()` accepts only typed, already-extracted facts from trusted exchange, issuer, official-disclosure, regulator or rating-agency sources. It deliberately accepts no executable HTML, JavaScript or PDF payload.

This is the normalization path for facts sourced from, for example, official issuer disclosures and Bank of Russia registers. The raw source remains outside the dossier; only the normalized fact, source identity/location, record id and timestamps are retained.

## 6. External text threat model

WP5 reuses the existing safe-news sanitizer instead of building a second HTML/text parser.

External text may contain hostile strings such as:

- system/developer override attempts;
- tool-call instructions;
- credential requests;
- trading/transfer commands;
- hidden Unicode/HTML payloads.

Rejected sanitized documents never enter research. Safe external documents may become `MEDIA_CONTEXT` records only and remain `CONTEXT_ONLY`. External text is data, never an instruction or authorization source.

`raw_content_stored=false` is invariant for dossiers and source-load results.

## 7. Evidence records

Every normalized `EvidenceRecordV1` carries:

- instrument UID;
- fact type and canonical fact key;
- typed canonical value;
- source provider/class/authority/id/location;
- retrieval timestamp;
- optional publication/effective timestamp;
- optional source record id;
- materiality flag;
- canonical SHA-256.

Record SHA-256 excludes only the hash field itself and is mutation-sensitive.

## 8. Coverage requirements

A dossier receives explicit `EvidenceRequirementV1` rows. Each requirement declares:

- fact type and optional key prefix;
- acceptable decision-grade source classes;
- minimum record count;
- maximum age;
- importance: critical/material/context;
- whether a successful fresh zero-result probe may satisfy the requirement.

A successful zero-result probe is important for facts where “checked and none found” differs from “source not checked”. Failed or stale probes never satisfy coverage.

Critical or material coverage gaps set `decision_ready=false`.

## 9. Contradictions

Decision-grade records are compared by canonical fact key and comparison period. Distinct values from the same reporting/effective period produce an explicit `EvidenceContradictionV1`.

Different periods are not treated as contradictions merely because values changed over time.

Repeated retrieval of the same source record is treated as a revision: only the newest retrieval is retained, preventing stale revisions from creating false contradictions.

Contradiction severity follows the importance of the affected requirement. An unresolved critical contradiction sets `strong_recommendation_allowed=false` even when general coverage is otherwise complete.

## 10. Determinism

The engine canonicalizes:

- requirements;
- probes;
- evidence records;
- duplicate revisions;
- contradictions;
- coverage gaps.

`dossier_sha256` binds the target, exact WP4 funnel, assessment timestamp, requirements, probes, records, contradictions, gaps and duplicate count. Input ordering cannot change the dossier fingerprint.

## 11. Cache and rate boundary

`ResearchEvidenceCacheV1` is bounded by:

- validated TTL;
- minimum refresh interval;
- maximum entry count;
- deterministic oldest-entry eviction.

A complete source batch is cacheable only when every emitted source probe succeeded. A failed/degraded batch is never cached.

Normal reads reuse a fresh cache entry without broker calls. A forced refresh inside the minimum refresh window raises `ResearchRefreshRateLimited` rather than hammering the source.

The cache key includes instrument UID/type, asset UID and asset-identity source id. Cached source facts may be rebound to a newer WP4 funnel only through a newly validated Research Target.

## 12. Privacy and execution boundary

WP5 stores no account id, user id, token, raw HTML/PDF or raw free-text source document.

`ResearchDossierV1` and `ResearchSourceLoadV1` hard-code:

- `raw_content_stored=false`;
- `trading_methods=false`.

No public route, OpenAPI Action, Render/Upstash mutation surface or GPT Editor change is introduced by WP5.

## 13. Exit gate

WP5 is complete only when:

1. exact WP4 shortlist binding is enforced;
2. source hierarchy and typed provenance are contract-bound;
3. T-Invest structured research surfaces are fake-client tested;
4. asset UID provenance and zero-as-unavailable semantics are fail closed;
5. official/regulatory facts can be normalized without raw-document execution/storage;
6. external prompt-injection text remains inert/rejected or context-only;
7. material coverage gaps block `decision_ready`;
8. unresolved critical contradictions block strong recommendation;
9. same-period contradictions and cross-period changes are distinguished;
10. source revisions deduplicate deterministically;
11. dossier fingerprint is source-order invariant and mutation-sensitive;
12. bounded cache/refresh/failure behavior is tested;
13. repository guard and mypy cover the research package;
14. exact-head Regression Shield is fully green;
15. PR is squash-merged and epic #176 marks WP5 complete.
