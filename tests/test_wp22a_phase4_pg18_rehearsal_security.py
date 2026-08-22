from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REHEARSAL = ROOT / "scripts" / "rehearse_v10_wp22a_phase4_runtime_role.py"
CIRCLECI = ROOT / ".circleci" / "config.yml"


def test_phase4_pg18_rehearsal_generates_ephemeral_credentials() -> None:
    source = REHEARSAL.read_text(encoding="utf-8")

    assert "import secrets" in source
    assert source.count("secrets.token_urlsafe(32)") == 1
    assert source.count("_ephemeral_password()") == 5
    assert "first_password = _ephemeral_password()" in source
    assert "second_password = _ephemeral_password()" in source
    assert "SYNTHETIC_PASSWORD" not in source
    assert "BOOTSTRAP_PASSWORD" not in source


def test_phase4_pg18_circleci_reuses_isolated_parameterized_job() -> None:
    source = CIRCLECI.read_text(encoding="utf-8")

    assert source.count("\n  supplemental_linux_postgres18:\n") == 1
    assert source.count("\n      - supplemental_linux_postgres18:\n") == 2
    assert "  supplemental_linux_phase4_pg18_creator_edge:\n" not in source
    assert "  supplemental_linux_phase4_pg18_bootstrap:\n" not in source
    assert "name: supplemental_linux_phase4_pg18_creator_edge" in source
    assert "name: supplemental_linux_phase4_pg18_bootstrap" in source
    assert "rehearsal: phase4-creator-edge" in source
    assert "rehearsal: phase4-bootstrap" in source
