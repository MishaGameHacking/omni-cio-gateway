from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FULL_SHA = re.compile(r"[0-9a-f]{40}")


def test_live_acceptance_assets_are_tracked() -> None:
    required_paths = (
        ".github/workflows/live-read-only-acceptance.yml",
        "docs/operations/LIVE_READ_ONLY_ACCEPTANCE.md",
        "omni_cio/release/live_acceptance_v1.py",
        "scripts/check_live_read_only_release.py",
        "tests/test_live_read_only_acceptance_v1.py",
    )
    for relative_path in required_paths:
        assert (ROOT / relative_path).is_file(), relative_path


def test_live_acceptance_workflow_is_read_only_and_pinned() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "live-read-only-acceptance.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" in workflow
    assert "contents: read" in workflow
    assert "check_live_read_only_release.py" in workflow
    assert "GATEWAY_API_KEY" not in workflow
    assert "TINVEST_TOKEN" not in workflow
    assert "continue-on-error: true" not in workflow

    for raw_line in workflow.splitlines():
        if "uses:" not in raw_line:
            continue
        value = raw_line.split("uses:", maxsplit=1)[1].split("#", maxsplit=1)[0]
        reference = value.strip().strip("\"'").rsplit("@", maxsplit=1)[-1]
        assert FULL_SHA.fullmatch(reference), value
