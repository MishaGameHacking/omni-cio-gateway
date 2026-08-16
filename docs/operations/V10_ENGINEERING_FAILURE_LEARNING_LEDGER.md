# Omni-CIO V10 — Engineering Failure Learning Ledger

Status: **ACTIVE ENGINEERING MEMORY AFTER GOVERNANCE AMENDMENT ACCEPTANCE**  
Purpose: retain reusable non-secret lessons from failed or misleading engineering cycles so future chats, agents and developers do not repeat the same failure classes.

This is not a blame log and it is not a replacement for current status, issue tracking, tests or CI evidence.

## Rules

Create/update an entry when a material failure occurs **after** the branch was considered ready for an expensive validation cycle, or when a check was misleading enough to expose a process weakness.

Every reusable entry should contain:

- Date / WP / PR or accepted change reference;
- Symptom / failing gate;
- Root cause;
- Blast radius searched;
- Why preflight missed it;
- Corrective change;
- Permanent regression/guard;
- Future prevention rule;
- Dependency/tooling knowledge change, if any.

Never record:

- broker/Telegram/provider tokens;
- Authorization headers;
- private portfolio/account payloads;
- raw OWNER identities;
- BitLocker/recovery keys;
- sensitive machine identifiers.

A short SHA may be used for navigation when useful. Full random-looking secret material must not be copied here.

---

## FL-001 — Infrastructure RED must not be merged around

**Date:** 2026-08-16  
**Scope:** V10-wide policy correction  
**Symptom:** GitHub-hosted Fast/Toolchain checks could fail before substantive job execution because of account billing/spending-limit state while authoritative Lenovo checks were GREEN. Earlier engineering treatment correctly classified those checks as infrastructure failures rather than code failures, but that classification was allowed to coexist with merge acceptance.

**Root cause:** the merge policy distinguished code failure from infrastructure failure for diagnosis, but did not separately enforce the OWNER requirement that the PR status surface itself be completely GREEN before merge.

**Blast radius searched:** all future V10 PR/maintenance/status/dependency merges and workflow routing semantics.

**Why preflight missed it:** this was a governance gap rather than an application-code defect.

**Corrective change:** the Engineering Quality / Green-Merge Amendment now states that any applicable RED check blocks merge regardless of whether the cause is code, billing, provider startup or infrastructure.

**Permanent guard:** machine-readable quality contract + PR template + agent instructions + governance CI check. Irrelevant workflows must be routed so they do not trigger; `skipped`/`neutral` are not GREEN evidence for applicable V10 gates.

**Future prevention rule:** classification explains the failure; it never grants a bypass.

---

## FL-002 — PowerShell native stderr is not equivalent to process failure

**Date:** 2026-08-12  
**Reference:** accepted WP15 correction PR #287  
**Symptom:** a Windows PowerShell 5.1 path treated native `npm` stderr as fatal despite the command's exit status being authoritative.

**Root cause:** PowerShell error-stream behavior and native process exit semantics were conflated.

**Blast radius searched:** the reviewed Web build commands that invoke npm under Windows PowerShell 5.1.

**Why preflight missed it:** the failure depended on the exact shell/runtime behavior rather than only application logic.

**Corrective change:** preserve global fail-closed behavior while handling non-fatal native stderr only inside the reviewed npm commands; keep npm exit codes authoritative.

**Permanent guard:** Windows PowerShell 5.1 regression probe in the accepted correction.

**Future prevention rule:** when wrapping native tools, test both exit-code and stderr behavior under the exact production/CI shell before declaring the wrapper portable.

**Dependency/tooling knowledge change:** shell semantics are part of the toolchain contract, not incidental implementation detail.

---

## FL-003 — Runtime probes must bind their source root explicitly

**Date:** 2026-08-12  
**Reference:** accepted WP15 correction PR #295  
**Symptom:** an archived runtime session probe could resolve/import the wrong application source when started from an arbitrary current working directory.

**Root cause:** implicit CWD/module-resolution assumptions leaked into a recovery/acceptance probe.

**Blast radius searched:** archived application source binding, bootstrap exit behavior and arbitrary-CWD execution.

**Why preflight missed it:** the happy path used the expected repository working directory and did not initially exercise an arbitrary CWD.

**Corrective change:** bind the probe to the archived application source root before importing Omni-CIO modules and use a bounded bootstrap exit code.

**Permanent guard:** arbitrary-CWD regression test added by the accepted correction.

**Future prevention rule:** recovery/deployment/evidence scripts must never rely on caller CWD for authoritative source selection; source identity/path must be explicit and testable.

---

## Entry template

```text
## FL-NNN — Short failure-class title

Date:
WP / PR / reference:
Symptom / failing gate:
Root cause:
Blast radius searched:
Why preflight missed it:
Corrective change:
Permanent regression/guard:
Future prevention rule:
Dependency/tooling knowledge change:
```
