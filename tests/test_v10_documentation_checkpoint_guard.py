from __future__ import annotations

from pathlib import Path

import scripts.check_v10_documentation_consistency as guard


def _install_live_guidance(
    tmp_path: Path,
    monkeypatch,
    source: str,
) -> Path:
    path = tmp_path / "guidance.md"
    path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(guard, "ROOT", tmp_path)
    monkeypatch.setattr(guard, "LIVE_GUIDANCE", (path,))
    return path


def test_transient_checkpoint_guard_rejects_live_checkpoint_copy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_live_guidance(
        tmp_path,
        monkeypatch,
        "The current integrated checkpoint is P4 public ingress.\n",
    )
    failures: list[str] = []

    guard._validate_transient_checkpoint_delegation(failures)

    assert failures == [
        "live guidance freezes transient branch checkpoint: guidance.md:1"
    ]


def test_transient_checkpoint_guard_allows_accepted_amendment_marker(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_live_guidance(
        tmp_path,
        monkeypatch,
        "> **CURRENT AMENDMENT-21 TIMEWEB DELIVERY OVERRIDE (2026-09-24):**\n",
    )
    failures: list[str] = []

    guard._validate_transient_checkpoint_delegation(failures)

    assert failures == []
