# FL-172 — Published source must be re-read after escaped-literal generation

Date: 2026-09-27  
WP / PR / reference: TIMEWEB-PLATFORM-CONSOLIDATION / P3 production network-scope repair / PR #593 head `11cf23e5d4b9bd59e37dac0c14a814d83e1d097a`

## Symptom / failing gate

Fast PR formatting and the repository policy/security guards passed, but the authoritative
Windows Regression Shield failed all 20 tests in the new production network-scope suite.
Every path stopped at `TIMEWEB_PG_PRODUCTION_NETWORK_HOST_INVALID`, including the
positive `prod-db.twc1.net` fixture.

## Root cause

The new hostname validator used a Python raw-string regular expression for dotted FQDNs.
While publishing the file through generated connector content, the intended raw-string
separator `\.` became `\\.` in the exact GitHub blob. The compiled expression therefore
required a literal backslash before each DNS label separator. This is the same defect
class already documented in FL-039, reintroduced at the source-publication boundary
rather than authored in the intended local draft.

## Blast radius searched

The defect is confined to the new read-only production network-scope verifier and its
new tests. It fails closed before Timeweb provider observation, PostgreSQL authentication,
database mutation, public-user activation, Telegram activation, broker write or Real
Trading. Existing accepted P3 TLS code is unchanged.

## Why preflight missed it

The focused preflight exercised the intended draft, while the exact published GitHub
blob was not re-read and executed before the checkpoint was treated as ready for remote
verification. Nested JavaScript-to-Python string escaping changed the validator after the
local proof.

## Corrective change

Remove the dotted-host raw regex entirely. Validate the hostname by splitting DNS labels
on `.` and applying an ASCII label regex that contains no escaped label separator.
Add an explicit positive regression for an ordinary dotted FQDN plus negative
backslash/empty-label/edge-hyphen cases.

## Permanent regression / guard

The focused hostname test must pass on the exact published source, and the full positive
network-scope path continues to exercise the same validator. After connector-generated
source publication, re-read the exact GitHub blob before accepting local-preflight
evidence as representative of the published head.

## Future prevention rule

Do not let nested transport/string escaping silently become application syntax. Prefer
representations that avoid escape-sensitive regexes when a simple structural parser is
clearer, and bind preflight to the exact bytes that are actually published.

## Dependency / tooling knowledge change

None.
