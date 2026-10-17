# Narrow S2245 review: deterministic historical resampling

## Current scope check — 2026-10-17

The reviewed `bootstrap_capital_floor` call and line-local `# NOSONAR(S2245)`
remain in [portfolio_risk.py](../backend/portfolio_risk.py), with the scope
regression in [test_statistical_random_scope.py](../backend/tests/test_statistical_random_scope.py).
The finding identifiers and job references below remain historical evidence
for PRs #832/#833; they are not the latest CI result or permission to suppress
new findings. Current risk implementation and outstanding validation are tracked
under F14/F21 in [PLAN_STATUS.md](PLAN_STATUS.md) and
[RISK_REBALANCING.md](RISK_REBALANCING.md).

## Historical review

Reviewed 2026-10-14 for PR #832 and the identical function in PR #833.
This is a source-context review by the implementation assistant, not an
independent security audit or a certification of the application's safety.

## Finding and scope

Exact-head annotations in Backend CI job 115818095775 and Android CI job
115818814415 identify S2245 on the bounded `rng.randrange` use in
`backend/portfolio_risk.py::bootstrap_capital_floor`. The earlier description
incorrectly located the finding at the constructor. Issue keys were
`AaE1IHb5hzcT_PGDhPgg` (#832) and `AaE2-GfNYfMchPqqZWYw` (#833).
No project rule, severity, quality gate or accepted-issue status is changed.

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
repairing a security boundary. One line-local `# NOSONAR(S2245)` annotation is
placed on the reviewed row-index call, not on the constructor. This valid,
rule-specific syntax replaces the earlier malformed generic suppression.
It does not suppress other rules, other lines, or other modules.
If the generator's scope or sinks change, remove the annotation and review again.
For secrets, use the security APIs already appropriate for that code, not this
statistical generator.

## Verification and limits

`backend/tests/test_statistical_random_scope.py` checks reproducibility,
isolation from module-global RNG state, bounded row-index sampling, finite
output schema, input/work-limit rejection before constructing the RNG, and the
reviewed single-call/non-escaping source boundary. It also checks the exact
rule-specific annotation and its placement. These tests are synthetic, offline,
and included in normal backend discovery. They do not prove resistance to every
attack, calibration of loss probabilities, or quality of market evidence.

Primary documentation:
- Python `secrets`: https://docs.python.org/3.12/library/secrets.html — explicitly
  distinguishes `random` for modelling/simulation from cryptographic secrets.
- Sonar Python rule-specific suppression syntax:
  https://community.sonarsource.com/t/python-issue-suppression-improvements-nosonar-and-new-rules/145017
- Sonar reviewing security-sensitive code:
  https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/issues/reviewing-security-hotspots
  (the project API classifies this particular finding as VULNERABILITY;
  the contextual review does not claim the finding never existed).
