from __future__ import annotations

from scripts.check_watchtower_boundary import main


def test_watchtower_repository_boundary() -> None:
    assert main() == 0
