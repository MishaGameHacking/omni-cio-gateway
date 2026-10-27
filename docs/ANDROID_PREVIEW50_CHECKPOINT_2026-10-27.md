# Preview50 — exact laptop checks, remaining build failure and quality remediation

The owner requires an actual new APK delivered to Timeweb, not source-only work.
No APK50 has been published. This checkpoint records failures without turning
them into success and keeps the existing release gates intact.

## Actual run32da

Source HEAD32da000b0d92cba6b94b1828842f706c162e596b was tested as merge
e6471439cb7004311178a770e73f85e6fe65445f against mainf54912165127bfab42673743cd141d635e20881f.
Android40557208934/job122376464724 on LAPTOP-NPSGA016 advanced past exact-source
inventory, acquired the shared lease, and started its owned build worker.
The worker failed with exit1; the controller preserved owned_processes_after=0
and final source-integrity verification. The generic exported error
owned_worker_failed does not identify the underlying build phase. No claim is
made that Gradle, JVM tests, signing or installation completed in that run.

Backend40557208858/job122376413303 completed its actual test step successfully
and retained its reports, but its overall result failed the exact-head Sonar
gate. Sonar122377498376 failed and exposed50 annotations. Original failures and
reports remain retained; they are not replaced or ignored.

## Corrections in this batch

- Failed-worker diagnostics now expose only bounded synthetic logs already in
  this run's validated state directory after worker cleanup. Paths recorded in
  step JSON are never followed; filenames are reconstructed from validated labels.
  Diagnostic errors cannot turn a failure into a pass or trigger execution.
- The WSL guest run root is reconstructed beneath fixed /opt/analyst-ci/runs
  from bounded ASCII integer run/attempt identifiers, never directly from a
  command-line Path. Existing canonical-parent, absence and no-symlink checks
  remain. This addresses the concrete Sonar path-traversal finding at the old
  root.mkdir call without weakening source or execution identity.
- Paper scenario callbacks capture their intended order/journal/lease and clock.
- Component-registry validation is separated from topological sorting without
  changing components, dependency order, errors or false acceptance declarations.
- Provenance assertions are split and exception tests isolate their target call;
  no assertions or scenarios are removed.

New source and tests require the next ordinary owner-laptop CI. Neither this
checkpoint nor written regression code is evidence of a pass. No workflow,
permission, signing key, secret, cloud transport, production DB/runtime setting,
main branch or APK channel is changed. Full N00–N11 remains unfinished.
