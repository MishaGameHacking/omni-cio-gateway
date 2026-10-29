# Candidate 56: data, explanations and navigation

The owner reported empty data surfaces, a silent chat composer, missing contextual
explanations, and navigation/charts that did not follow the supplied references.

Changes prepared for the existing Android client and Timeweb runtime:

- Read the persistent public corpus in the application, with search, report/news
  filters, pagination, source timestamps and explicit partial/unavailable states.
- Retain original official PDF reports alongside extracted text in SQLite. Verify
  their SHA-256, deduplicate bytes, preserve referenced versions, cap original
  storage at 256 MiB and re-fetch legacy originals through the existing queue.
  Text retention remains separate: news 30 days, current reports five years,
  old revisions one year. Nothing is claimed to cover all issuers or all news.
- Show rejected estimates next to the composer; accept brief greetings; require
  valid evidence IDs only for concrete observations, permitting general answers
  with an empty claims array. Existing budget, settlement and idempotency guards
  still apply. Preserve legacy request hashes when no explanation was selected.
- Resolve risk, candidate, analysis, notification and document explanation targets
  server-side with ownership checks. Never trust UI prose as portfolio evidence.
  The selected question preserves an existing draft until the owner replaces it.
- Reconcile notification scheduling on foreground resume using stored settings.
- Keep a slim rounded icon rail and show vertically labelled destinations when
  expanded. Retain draft-exit guards, Back handling and touch targets.
- Add an interactive line/area view of stored portfolio balances. Missing calendar
  buckets break the line; exact observed values remain available. Deposits are
  not presented as investment returns. The column view remains selectable.

Verification is pending at this commit. The previous candidate failed two stale
version assertions (55 instead of 56); those expectations now match the candidate.
Backend regressions include target ownership, saved-document context, report type
filters, original retention/backfill, capacity limits, and chat settlement/replay.
Compose fixtures are synthetic and are not evidence of behavior on the owner's
physical device. All executable application verification runs on LAPTOP-NPSGA016.

Live diagnostics before this change confirmed a fresh snapshot and enabled
automation, 563 saved publications, two reports and 32 partial/failed targets.
The diagnostics found no accepted user chat messages or chat jobs. The corpus
previously had no client entry point. No claim is made that those source failures
or incomplete investment research can be resolved by showing a placeholder.

This release does not enable real trading. Discovery remains a research workflow;
cash availability alone is not proof that a candidate passed the required checks.
The existing broker connection, strategy, database and paid-model limits persist.
