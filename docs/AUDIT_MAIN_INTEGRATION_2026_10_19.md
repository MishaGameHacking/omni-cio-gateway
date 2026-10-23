# Main integration into 0.11.0 — 19 October 2026

F01 / F02 / F20 / F22 / F23. This records the source-resolution decision for
integrating main `97149a309361aa0db0da3c07d2e7342f23d3cc8b` into development
`8ee4d2078680b2a00f55aba8085fc502201315be`. It does not approve merging PR #880
or releasing/deploying 0.11.0. Main's verified PR #881 was separately squash-merged
under the owner's express 19 October authorization.

## Complete main delta

GitHub comparison `12b5b1f...97149a3` contains exactly 19 changed paths: four
modified files and fifteen additions. No other main files changed. The resolved
development tree keeps its existing version-specific implementation; it is not
an unconditional replacement with the older main application.

Fourteen additions already have identical Git blob identities in both lines:

| Path | Shared blob |
| --- | --- |
| .github/scripts/require_clean_sonar.cjs | 584866aa05df9cc6e44cda2d8ccc7a0a0f93a146 |
| .github/scripts/require_clean_sonar.test.cjs | 1d65dc324dd200d0843b3e8856fc2360771169df |
| backend/bounded_ai_response.py | f4c7c4dd79fe49f9ed0d9549750a5d1ddb9ce619 |
| backend/broker_connections.py | fd7367f0c4e8a6fccca9c73f22fa9c31c16ed361 |
| backend/model_json_limits.py | 8ca718100438d87b7eda02bb04af25a1b7f42c5e |
| backend/tests/test_ai_accounting_audit.py | eebb60185c45a2d4fc4c7157f2bb0e31d6e1318e |
| backend/tests/test_ai_json_audit.py | 1bfdb5f157f5e28392f5326d33c7e4d378d6231e |
| backend/tests/test_ai_response_streaming.py | 58402f33e2fe56456f610ec7b0b262dc468e3923 |
| backend/tests/test_bounded_ai_response.py | adbab6283223402b149d2abe557d4451e0fcdfaf |
| backend/tests/test_broker_connection_versions.py | 79ae20c58592883bb360864a56502416c10683c9 |
| backend/tests/test_model_json_limits.py | f2d548afaaedcd5a698cab65fba8ae4f9f5f5fd5 |
| backend/tests/test_tinvest_connection_races.py | 27d36fffe2b8c6206fdbfbda37e33e075b96bd39 |
| docs/AUDIT_BROKER_CONNECTION_2026_10_19.md | 682cc5b878da62fe2d4f986d1f9fee9f64cf6d2f |
| docs/AUDIT_HTTP_RESPONSE_2026_10_19.md | 6924c98c04fd3d4436b5cb8f03ce792562fe9df7 |

The fifteenth addition, `docs/AUDIT_MAIN_AI_BACKPORT_2026_10_19.md`, is copied
unchanged from main blob `97e51bfc6647df1442e1e9852026c80d12664377`. It is a
historical initial backport report, not the latest deployment/merge status.
Its former native-crash attribution was superseded by the correction in the
broker audit; this integration does not reinstate that diagnosis.

## Resolution of modified files

- `backend/ai_budget.py`: retain development blob
  `059209f5423a229b86576335bd916368843333bd`. All main fixes to independent
  micro-RUB quantization, bounded reservation labels, monotonic observed charges
  and exact summaries are present. Preserve development's additional transaction
  guard, job user binding and cancellation check.
- `backend/ai_guarded_client.py`: retain development blob
  `458be5c8e9a2ea765c4688e0f0285388bb67e7f9`. Main's duplicate/nonfinite/underflow
  JSON rejection, explicit preflight, accounting and bounded raw/gzip HTTP
  response changes are already present. Preserve route catalogue admission,
  per-request guards and the distinction between pre-dispatch cancellation and
  possibly charged responses; no paid replay is introduced.
- `backend/app.py`: retain development blob
  `4074fde8731cc48ea02fcab42336a9fa1b1dc448`. Main's broker module imports,
  initialization, no-store error handler and all save/disconnect ticket guards
  are already present. Preserve development's device migration and route wiring.
- `.github/workflows/backend-ci.yml`: retain development blob
  `2c15f587ec7558e5bbb3dd2ffc40b1913eb5456b`. Its existing Sonar path glob covers
  main's narrower .cjs glob, and its strict exact-head algorithm is the same.
  Preserve the broader Python syntax audit, pytest collection, disabled live
  processing/scheduler in tests and existing step/time budgets. Do not regress
  development to main's smaller unittest-only collection.

The integration commit records both parent histories without force-updating
main or rewriting development history. The additional session-rotation repair
and its nine regression methods are described in
`AUDIT_SESSION_ROTATION_2026_10_19.md`; neither production renderer nor session
state is modified by that UI-driver repair.

## Evidence boundaries

The mapping above was checked from the complete changed-path list, Git tree/blob
identities and the four main source patches against the development source.
It is a source-resolution record, not a fabricated full local git checkout.
The new combined head/base must pass complete backend, Sonar and Android CI.
Historical green PR #881 or Backend #422 results cannot certify this integration.
No 0.11.0 acceptance item is closed solely by resolving a Git conflict.
