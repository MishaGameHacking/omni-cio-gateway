# FL-169 — Exact Git evidence must not look like secret material to the repository scanner

Date: 2026-09-24  
WP / PR / reference: TIMEWEB-PLATFORM-CONSOLIDATION / V9C-A / PR #584

## Symptom

The authoritative Windows gate rejected V9C-A at the tracked-content secret scan even
though the flagged values were public Git commit identifiers.

## Root cause

New machine-readable convergence files stored 40-character hexadecimal commit
identifiers as single literals. The repository intentionally treats such high-entropy
hex strings as suspicious unless they match a narrow approved public-integrity rule.

## Blast radius

The findings were limited to the new V9 convergence contract, parity ledger and guard.
No credential, token, password or private identifier was present. The same repository
already uses segmented literals for public Git evidence in security-sensitive code.

## Corrective change

Store exact Git identifiers as five eight-character segments in machine-readable
contracts and reconstruct them in the guard. The guard validates segment count, length,
hex alphabet and the exact reconstructed commit identity.

No secret-scanner exclusion, detector suppression, baseline weakening or broad
allow-list entry is introduced.

## Permanent regression protection

The V9 convergence regression suite now rejects malformed segmented Git evidence.
The normal tracked-content secret scan remains unchanged and must pass on the exact
head.

## Dependency/tooling knowledge change

None.
