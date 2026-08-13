# V10 WP20 — Research Dossier UI contract

Status: **IMPLEMENTATION / ACCEPTANCE PENDING**  
Authority: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` WP20 and `V10_WP20_EXECUTION_CONTRACT.md`

## Screen contract

Route: `/research` inside the accepted WP17 Application Shell.

The page answers, without hidden inference:

- what security/issuer the dossier is about;
- which structured facts exist;
- where every fact came from;
- when it was published/effective/retrieved;
- whether it is fresh under canonical requirement semantics;
- whether canonical evidence contains unresolved contradictions;
- what required evidence remains unknown/missing/stale;
- which event-like facts form the research timeline;
- where related Credit/Risk and Fund/Assets views live;
- whether an AI interpretation exists, while keeping it semantically non-authoritative.

## Origin zones

### Canonical structured evidence

DOM origin markers:

- `canonical-source-facts`
- `canonical-source-fact`
- `canonical-unknowns`
- `canonical-contradictions`
- `canonical-event-timeline`

A canonical fact card contains the value and its provenance together. Source links are optional; provenance labels/timestamps remain present even if the source location is rejected by the Web allowlist.

### AI / inference

DOM origin marker: `ai-inference`.

Required persistent labels:

- `AI / INFERENCE · NON-AUTHORITATIVE`
- `НЕ ИСТОЧНИК ФАКТОВ`

The AI section may never reuse the canonical fact card presentation without these semantic labels. It may not mutate or overwrite source-fact values.

## State model

Top-level state:

- `EMPTY`: no validated dossiers are available;
- `READY`: represented dossiers are fresh and have no visible gaps/conflicts;
- `PARTIAL`: invalid/truncated/gapped/contradictory evidence exists;
- `STALE`: at least one represented dossier is past cache expiry.

Dossier state:

- `READY`
- `PARTIAL`
- `STALE`

Fact freshness:

- `FRESH`
- `STALE`
- `UNKNOWN`

The Web layer does not upgrade a lower-confidence or stale state to success.

## Long-content behavior

Fact values, source labels, IDs and AI text use normal React text nodes plus CSS wrapping. They must not use raw HTML rendering. Long source lists remain bounded by the backend dossier/fact limits and remain scrollable as normal document content.

## Safe source-link behavior

`source.location` is exposed only when backend parsing accepts an `http` or `https` URL with a host and without embedded credentials. UI anchors use `target="_blank"` and `rel="noreferrer noopener"`.

A rejected location produces a visible metadata note, not a clickable arbitrary scheme.

## Accessibility / responsive baseline

WP20 reuses WP16/WP17 controls, headings, cards and state panels. The page keeps semantic headings, lists, definition lists and labels. At narrow widths, metric/identity/timeline grids collapse to one column. Refresh is an explicit user action and does not mutate canonical research data.

## Security boundary

The endpoint is same-origin, session-authenticated, tenant derived from server-side session, and `Cache-Control: no-store`. No tenant ID comes from a browser query/body selector. No T-Invest token, account fingerprint, secret reference, raw research blob, or private broker credential is returned.

The endpoint is GET-only; WP20 does not introduce research mutation, model execution, broker writes or Real execution.

## Acceptance evidence

Browser evidence must include:

1. a long multi-source canonical dossier;
2. literal markup-like text remaining text rather than injected DOM;
3. visibly separate canonical and AI origin zones;
4. stale + contradictory + unknown states;
5. a captured synthetic browser screenshot from the focused Lenovo workflow.
