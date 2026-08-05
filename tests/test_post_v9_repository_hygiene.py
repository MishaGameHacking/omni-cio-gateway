from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED_DEPENDENCY_PROJECTIONS = (
    "windows-requirements.txt",
    "windows-requirements-dev.txt",
    "windows-compiled-requirements.txt",
    "windows-compiled-requirements-dev.txt",
    "compiled-requirements.txt",
    "compiled-requirements-dev.txt",
)


def test_one_time_v390_bootstrap_artifacts_are_retired() -> None:
    assert not (ROOT / ".v390").exists()


def test_dependency_sources_and_locks_stay_canonical_at_root() -> None:
    for name in (
        "requirements.in",
        "requirements.txt",
        "requirements-dev.in",
        "requirements-dev.txt",
    ):
        assert (ROOT / name).is_file(), name

    tracked = subprocess.run(
        ["git", "ls-files", "--cached", "--", *GENERATED_DEPENDENCY_PROJECTIONS],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert not tracked, f"generated dependency projections are tracked: {tracked}"

    for generated_name in GENERATED_DEPENDENCY_PROJECTIONS:
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", generated_name],
            cwd=ROOT,
            check=False,
        )
        assert ignored.returncode == 0, f"{generated_name} must stay gitignored"


def test_applied_gpt_state_is_v9_not_pending_wp15() -> None:
    status = (ROOT / "knowledge" / "16_CURRENT_PROGRAM_STATUS.md").read_text(
        encoding="utf-8"
    )
    master = (ROOT / "knowledge" / "00_PROJECT_MASTER_CONTEXT.md").read_text(
        encoding="utf-8"
    )
    config = (ROOT / "gpt" / "CONFIGURATION.md").read_text(encoding="utf-8")

    assert "Applied external GPT: **v9.0.0**" in status
    assert "Applied external GPT: **v9.0.0**" in config
    assert "WP0–WP15" in master
    assert "controlled maintenance" in master

    stale_markers = (
        "Applied external GPT remains **v8.6.1**",
        "WP15 repository target: in progress",
        "WP15 is the final active package",
    )
    for marker in stale_markers:
        assert marker not in status
        assert marker not in master
        assert marker not in config
