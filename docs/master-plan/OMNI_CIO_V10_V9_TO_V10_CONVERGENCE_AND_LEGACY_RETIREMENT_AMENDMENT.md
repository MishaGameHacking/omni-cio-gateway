# Omni-CIO V10 — V9-to-V10 Convergence and Legacy Working-Tree Retirement Amendment

Status: **OWNER-APPROVED / ACTIVE FOR PR #584 BRANCH-LOCAL IMPLEMENTATION**  
Decision date: **2026-09-24**  
Owning System Update: **TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED**  
Owning branch: `system/timeweb-platform-consolidation-tw-b` / PR #584

## 1. OWNER decision

Omni-CIO is one product and one forward runtime line. The accepted V9 capability set is
now a **migration source** for V10, not a separately evolving future runtime.

The accepted V9 repository target is
`b9e4fabcb54f8f6e0ba206f030c35f2fafa2ce62`. That commit is already an ancestor
of the accepted V10/main lineage, so this amendment explicitly forbids merging a stale
`v9/*` branch head into PR #584 merely to claim convergence. Such branch heads may
contain squash-history divergence, superseded provider assumptions or already-migrated
code.

Convergence is performed from the V9 source that already exists in the current
repository lineage:

`accepted V9 behavior -> canonical V10 packages/contracts -> Timeweb runtime -> parity proof -> legacy working-tree retirement`.

Git history is retained. Working-tree deletion is not history rewriting.

## 2. Final product/runtime boundary

After the convergence milestones finish and PR #584 is separately accepted by the
OWNER, the supported forward runtime is V10 only:

`GitHub source/CI -> Timeweb App Platform -> V10 Web/API -> Timeweb PostgreSQL 18`

Human product identity remains Telegram Login only.

The target application entrypoint is the current provider-neutral hosted composition
`apps.api.hosted_runtime:create_app` as invoked by the Timeweb Docker runtime.
`app:app`, `app_v360.py`, `app_v371.py` and `main.py` are migration inputs,
not permanent parallel product runtimes.

This amendment changes source/runtime convergence authority only. It does not itself
deploy Timeweb, cut over production PostgreSQL, mutate DNS/TLS, activate public users,
or authorize broker writes or Real money.

## 3. Reuse before movement

Most accepted V9 deterministic engines have already been extracted under
`omni_cio/`. They remain canonical and must not be duplicated or rewritten merely
because their origin was V9.

The migration preference remains:

`REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

The remaining root-level portfolio/accounting/pre-trade compatibility modules are
relocated into canonical `omni_cio/` packages with behavior-preserving imports and
parity tests before the old paths are removed.

Money-critical semantics may change only through their existing versioned owning
contracts and authority gates.

## 4. Ordered V9 convergence milestones inside PR #584

The branch uses these internal checkpoints:

1. **V9C-A / AUTHORITY_AND_INVENTORY** — establish this amendment, exact source
   inventory, migration map and machine guard.
2. **V9C-B / DETERMINISTIC_SOURCE_RELOCATION** — relocate remaining root-level
   deterministic V9 source into canonical V10 packages, update producers/consumers and
   prove parity before deleting old source paths.
3. **V9C-C / RUNTIME_ENTRYPOINT_CONVERGENCE** — move all supported runtime/API
   behavior to the V10 Timeweb composition, eliminate current consumers of
   `app.py`, `app_v360.py`, `app_v371.py` and `main.py`, then retire those
   working-tree files.
4. **V9C-D / GPT_AND_RETIRED_PROVIDER_WORKTREE_RETIREMENT** — extract any still-needed
   V9 GPT policy/knowledge and historical provider logic into current V10 authority or
   Git history, then remove obsolete V9/Render/Cloudflare/Neon/Cloud.ru/VK working-tree
   artifacts that have zero current consumers.
5. **V9C-E / CI_RECOVERY_CONVERGENCE** — replace checks that require retired
   entrypoints/providers with equal-or-stronger V10/Timeweb checks; recovery must stand
   on current Timeweb source, PostgreSQL backup/restore and Git provenance.
6. **V9C-F / WHOLE_TREE_LEGACY_ABSENCE_PROOF** — prove no current runtime, deploy,
   required CI or current documentation authority depends on retired V9/provider
   working-tree paths.

Each checkpoint must be `CERTIFIED_GREEN` before the next functional checkpoint.

## 5. Deletion gate

A legacy working-tree path may be removed only after all applicable conditions are
proved:

- canonical replacement source exists;
- direct and transitive current producers/consumers have been migrated;
- deterministic or contract parity tests pass;
- no required runtime/deploy/CI import or command still needs the path;
- recovery/provenance remains available through current V10 recovery artifacts and Git
  history;
- tenant isolation, least privilege, secret custody and broker/Real-money boundaries
  are unchanged or stronger;
- no regression guard is weakened merely to permit deletion.

Historical documentation may be compacted or removed from the working tree after its
current authority has been migrated, because the Git commit graph remains the immutable
historical archive.

## 6. Protected authority

Throughout V9C-A through V9C-F:

- `PUBLIC_MULTI_USER_ENABLED` remains false until TW-F;
- Telegram Login activation remains fail-closed until its owning gate;
- broker write remains OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- transfer/withdrawal, margin/leverage and uncovered-short authority remain forbidden;
- tenant identity is server-side and RLS/FORCE-RLS remains mandatory;
- no real secret is moved into GitHub, chat, fixtures or CI output.

## 7. PR #584 landing authority

PR #584 remains one integrated branch for this global source/runtime convergence.
Internal checkpoints do not require separate feature branches or merges.

**PR #584 must not be merged into `main` without a new explicit OWNER instruction.**

A branch-local GREEN checkpoint is implementation evidence only. Accepted-main
authority changes only after an OWNER-authorized merge and exact-new-main
post-merge verification.
