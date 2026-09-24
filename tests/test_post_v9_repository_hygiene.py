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

CURRENT_STATE_DOCS = (
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "docs/README.md",
    "docs/master-plan/README.md",
    "knowledge/00_PROJECT_MASTER_CONTEXT.md",
    "knowledge/16_CURRENT_PROGRAM_STATUS.md",
    "gpt/README.md",
    "gpt/SETUP_INDEX.md",
    "gpt/CONFIGURATION.md",
    "gpt/NEW_CHAT_PROMPT.md",
    "gpt/PROJECT_INSTRUCTIONS.md",
    ".github/copilot-instructions.md",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
)

STALE_CURRENT_STATE_MARKERS = (
    "Applied external GPT remains **v8.6.1**",
    "Applied Custom GPT remains v8.6.1 until WP15",
    "Applied GPT remains v8.6.1 until WP15",
    "WP15 repository target: in progress",
    "WP15 is the final active package",
    "WP12 remains **IN PROGRESS**",
    "Next dependency after WP12 merge",
    "Current GPT Editor behavior is v8.6.1 Compact",
    "CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt",
    "strict read-only architecture",
    "User-facing endpoints остаются только `GET`",
    "Предложения, связанные с автоматической торговлей, созданием или отправкой заявок, не соответствуют архитектуре проекта",
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


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
    status = _read("knowledge/16_CURRENT_PROGRAM_STATUS.md")
    master = _read("knowledge/00_PROJECT_MASTER_CONTEXT.md")
    config = _read("gpt/CONFIGURATION.md")

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


def test_current_operational_docs_do_not_reintroduce_pre_v9_status() -> None:
    for relative in CURRENT_STATE_DOCS:
        text = _read(relative)
        for marker in STALE_CURRENT_STATE_MARKERS:
            assert marker not in text, f"{relative}: stale current-state marker {marker!r}"


def test_current_navigation_describes_v9_as_migration_source() -> None:
    changelog = _read("CHANGELOG.md")
    contributing = _read("CONTRIBUTING.md")
    copilot = _read(".github/copilot-instructions.md")
    master_plan_index = _read("docs/master-plan/README.md")

    assert "V9 migration source" in changelog
    assert "V9 migration source" in contributing
    assert "V9 migration source" in copilot
    assert "V9 migration source" in master_plan_index

    assert "Amendment 20" in changelog
    assert "PR #584" in contributing
    assert "PR #584" in copilot
    assert "Amendment 20" in master_plan_index

    assert "protected effective production/recovery V9 baseline" not in copilot
    assert "Do not mass-delete historical provider files" not in copilot
    assert "historical" in changelog.casefold()
    assert "completed" in master_plan_index.casefold()
