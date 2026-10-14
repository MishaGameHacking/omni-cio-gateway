# Narrow S2245 review: deterministic historical resampling

Reviewed 2026-10-14 for PR #832 and the identical function in PR #833.
This is a source-context review by the implementation assistant, not an
independent security audit or a certification of the application's safety.

## Finding and scope

The read-only diagnostic job 115792715262 on run 38511244478 identified the
remaining SECURITY/MEDIUM finding as `python:S2245` at the `random.Random(seed)`
constructor in `backend/portfolio_risk.py::bootstrap_capital_floor`.
The issue keys were `AaE1IHb5hzcT_PGDhPgg` (#832) and
`AaE2-GfNYfMchPqqZWYw` (#833). Do not infer from other annotations that each is a
security vulnerability. No Sonar project rule, severity, quality gate or
accepted-issue status is changed by this review.

## Reviewed data flow

`seed` is an explicit, non-secret integer simulation parameter. The resulting
PRNG is a local variable. Its sole use is `randrange` to select a starting index
of a consecutive block of supplied historical return rows. Those rows are used
to simulate portfolio values. The returned record contains the seed, numerical
simulation statistics, supplied source identifier, and an explicit no-guarantee
warning. The generator object and its state are not returned or stored.

There are no authentication, authorization, password-reset, cryptographic key,
nonce, session-ID, unguessable URL, trading-order, filesystem or network sinks
for this generator. Its unpredictability is not a security boundary. Knowing
the seed and reconstructing the simulation is intentional, not an exploit.
Reviewed inputs and protection against cherry-picking remain a separate data
quality responsibility; this review does not make a simulation a forecast.

## Disposition

The security-vulnerability classification is not applicable to this call's
reviewed use. Keep the seeded generator: replacing it with a cryptographic
non-repeatable stream would change the reproducibility contract without
repairing a security boundary. The constructor has one line-local `NOSONAR`
annotation referencing this document. It does **not** cover other lines,
functions, modules or future uses. Such an annotation suppresses findings on
that single line; therefore no additional operation belongs on that line.
If the generator's scope/sinks change, remove the annotation and review again.
For secrets, use the security APIs already appropriate for that code, not this
statistical generator.

## Verification and limits

`backend/tests/test_statistical_random_scope.py` checks reproducibility,
isolation from module-global RNG state, bounded row-index sampling, finite
output schema, input/work-limit rejection before constructing the RNG, and the
reviewed single-call/non-escaping source boundary. These tests are synthetic,
offline, and included in normal backend test discovery. They do not prove
resistance to every possible attack, calibration of loss probabilities, or
quality of market evidence. Existing mathematical and application tests remain.

Primary documentation consulted:
- Python `secrets`: https://docs.python.org/3.12/library/secrets.html — explicitly
  distinguishes `random` for modelling/simulation from cryptographic secrets.
- Sonar reviewing security-sensitive code:
  https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/issues/reviewing-security-hotspots
  (the actual project API reports this finding as VULNERABILITY; the review
  above establishes its local context rather than claiming it is absent).
