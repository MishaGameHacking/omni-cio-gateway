from __future__ import annotations

from scripts.check_decision_journal_boundary import main


def test_decision_journal_repository_boundary() -> None:
    assert main() == 0
