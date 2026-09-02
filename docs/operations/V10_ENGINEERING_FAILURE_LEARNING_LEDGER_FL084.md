# V10 Engineering Failure Learning Ledger — FL084

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D exact-main
production release ordering after accepted GitHub post-merge verification.

This entry records a false-RED release-gate failure discovered after PR #435 was
accepted on protected `main`.

## Failure observed

PR #435 was squash-merged as exact accepted main
`e131112491418e26ee5a64267d5f0d2c006519fb`.

Its exact-main push batch ultimately contained 11 applicable workflows, all terminal
`success`, including Regression Shield run `33689611114`, V10 Engineering Governance
run `33689611172`, and the owning WP16–WP22A audits.

Automatic `V10 Cloudflare Production Release` run `33690155899`, job
`100446810370`, invoked the post-merge gate with a bounded 900-second wait. At
`2026-09-02T22:27:46Z` the gate stopped with:

```text
CLOUDFLARE_POSTMERGE_GATE=STOPPED
code=CLOUDFLARE_POSTMERGE_PUSH_WORKFLOW_NOT_SUCCESS
```

The WP21 push workflow run `33689611296` finalized `completed / success` at
`2026-09-02T22:28:11Z`, 25 seconds later. No second workflow attempt or source-changing
rerun converted a real terminal failure into success.

All provider-facing production-release steps were skipped. No Neon authority probe or
mutation, staging deployment, production Worker mutation, Custom Domain attachment, or
public cutover occurred.

## Root cause class

`GITHUB_WORKFLOW_CONCLUSION_FINALIZATION_RACE`

The release gate already treated non-completed workflow rows as pending. It treated every
row whose `status == "completed"` but whose `conclusion != "success"` as immediate
terminal RED.

The exact-SHA timing and later all-success evidence are consistent with an incomplete
GitHub Actions API snapshot at the completion boundary before the final conclusion was
materialized. The previous deterministic fixture could not represent that combination
because it derived `status` directly from whether `conclusion` was `None`.

GitHub's documented model states that incomplete runs/checks use non-completed statuses
and completed checks have a conclusion. A provider/API finalization anomaly must not be
accepted as GREEN, but it also must not bypass the gate's existing bounded wait window.

## Corrective invariant

For every latest exact-SHA push workflow observed by the CF-D post-merge gate:

- missing required workflows remain pending and never count as GREEN;
- non-completed workflow states remain pending;
- `status == "completed"` with no materialized conclusion remains pending/indeterminate;
- pending/indeterminate evidence may wait only inside the existing bounded deadline;
- persistent indeterminate evidence times out as
  `CLOUDFLARE_POSTMERGE_PUSH_WORKFLOWS_PENDING`;
- an explicit completed conclusion other than `success` remains immediate terminal RED;
- malformed status/conclusion types fail closed as
  `CLOUDFLARE_POSTMERGE_RUN_INVALID`;
- current `main` is rechecked before and after the exact-SHA workflow gate;
- provider mutation remains unreachable until the gate returns READY.

## Regression coverage

The deterministic test fixture now models `status` and `conclusion` independently and
covers:

- ordinary non-completed pending state;
- `completed + null conclusion -> pending`;
- later materialized `success -> READY`;
- persistent missing conclusion -> bounded pending timeout;
- malformed status/conclusion -> fail closed;
- explicit terminal failure -> immediate fail closed;
- existing rerun, pagination, exact-main drift and GitHub API failure semantics.

## Permanent learning

- Polling code must distinguish terminal negative evidence from incomplete metadata.
- Success-only policy does not require converting an indeterminate provider snapshot into
  a synthetic failure before the configured deadline.
- Status and conclusion must be modeled as independent external fields in regression
  fixtures even when provider documentation describes an invariant between them.
- A release gate should tolerate bounded metadata finalization without weakening exact-SHA,
  exact-main, terminal-success, security, or provider-mutation boundaries.
- Provider-facing work must stay downstream of post-merge evidence convergence.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No real credential, token, password, provider identifier, database secret, private
  portfolio payload, or private runtime URL is recorded here.
- No Cloudflare or Neon mutation is authorized by this correction alone.
