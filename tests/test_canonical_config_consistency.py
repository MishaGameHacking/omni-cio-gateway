from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_canonical_config_consistency.py"
)
SPEC = importlib.util.spec_from_file_location("check_canonical_config_consistency", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
consistency = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(consistency)


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_stale_phase4_claim_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(consistency, "ROOT", tmp_path)
    _write(
        tmp_path,
        "knowledge/00_PROJECT_MASTER_CONTEXT.md",
        "**Only remaining release gate:** Phase 4",
    )
    failures: list[str] = []

    consistency.validate_no_stale_claims(failures)

    assert any("stale production claim" in failure for failure in failures)


def test_old_v84_manifest_claim_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(consistency, "ROOT", tmp_path)
    _write(
        tmp_path,
        "gpt/BOT_ONLY_FILE_MANIFEST.md",
        "CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` | Единственные production Instructions",
    )
    failures: list[str] = []

    consistency.validate_no_stale_claims(failures)

    assert any("V8_4_1" in failure for failure in failures)


def test_program_lock_requires_all_markers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(consistency, "ROOT", tmp_path)
    _write(
        tmp_path,
        "AGENTS.md",
        "ACTIVE PROGRAM LOCK\nprotected production/recovery baseline",
    )
    _write(
        tmp_path,
        consistency.V9_PROGRAM,
        "OWNER-APPROVED / PROGRAM LOCKED\nDefinition of Done\n"
        "stable v8.6.1 production contour",
    )
    _write(
        tmp_path,
        "knowledge/16_CURRENT_PROGRAM_STATUS.md",
        "Active development program — LOCKED\nWP0 — Baseline freeze and recovery correctness",
    )
    failures: list[str] = []

    consistency.validate_program_lock(failures)

    assert failures == [
        "AGENTS.md does not enforce v9 program lock: earliest incomplete v9 work package"
    ]


def test_unfinished_v9_must_not_replace_recovery_baseline(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(consistency, "ROOT", tmp_path)
    _write(tmp_path, "gpt/SETUP_INDEX.md", "v9 is under development")
    failures: list[str] = []

    consistency.validate_unfinished_v9_not_promoted(failures)

    assert failures == [
        "gpt/SETUP_INDEX.md must preserve v8.6.1 as the recovery baseline"
    ]
