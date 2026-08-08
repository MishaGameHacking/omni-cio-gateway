from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISION = ROOT / "infrastructure" / "windows" / "provision_wp6_privilege_boundary.ps1"
ROLLBACK = ROOT / "infrastructure" / "windows" / "rollback_wp6_privilege_boundary.ps1"
MARKER_RE = re.compile(r'^\$(runtimeMarker|executionMarker) = "([^"]+)"$', re.MULTILINE)


def _markers(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    return {name: value for name, value in MARKER_RE.findall(text)}


def test_wp6_local_user_ownership_markers_fit_windows_description_limit() -> None:
    provision = _markers(PROVISION)
    rollback = _markers(ROLLBACK)

    assert set(provision) == {"runtimeMarker", "executionMarker"}
    assert rollback == provision
    for marker in provision.values():
        assert 1 <= len(marker) <= 48


def test_wp6_marker_guard_remains_bound_to_local_user_description() -> None:
    provision = PROVISION.read_text(encoding="utf-8")
    rollback = ROLLBACK.read_text(encoding="utf-8")

    assert "-Description $Marker" in provision
    assert "$existing.Description -ne $Marker" in provision
    assert "$user.Description -ne $Marker" in rollback
