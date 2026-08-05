from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FULL_SHA = re.compile(r"[0-9a-f]{40}")


def test_live_authority_assets_are_tracked() -> None:
    required_paths = (
        ".github/workflows/live-gateway-authority.yml",
        "docs/operations/LIVE_GATEWAY_AUTHORITY_ACCEPTANCE.md",
        "omni_cio/release/live_authority_v1.py",
        "scripts/check_live_gateway_authority.py",
        "tests/test_live_gateway_authority_v1.py",
    )
    for relative_path in required_paths:
        assert (ROOT / relative_path).is_file(), relative_path

    retired_paths = (
        ".github/workflows/live-read-only-acceptance.yml",
        "docs/operations/LIVE_READ_ONLY_ACCEPTANCE.md",
    )
    for relative_path in retired_paths:
        assert not (ROOT / relative_path).exists(), relative_path


def test_live_authority_workflow_is_read_only_and_pinned() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "live-gateway-authority.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" in workflow
    assert "pull_request:" in workflow
    assert '"omni_cio/release/live_authority_v1.py"' in workflow
    assert '"scripts/check_live_gateway_authority.py"' in workflow
    assert "contents: read" in workflow
    assert "check_live_gateway_authority.py" in workflow
    assert "GATEWAY_API_KEY" not in workflow
    assert "TINVEST_TOKEN" not in workflow
    assert "continue-on-error: true" not in workflow

    for raw_line in workflow.splitlines():
        if "uses:" not in raw_line:
            continue
        value = raw_line.split("uses:", maxsplit=1)[1].split("#", maxsplit=1)[0]
        reference = value.strip().strip("\"'").rsplit("@", maxsplit=1)[-1]
        assert FULL_SHA.fullmatch(reference), value
