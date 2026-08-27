from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import provision_v10_render_neon_preview_org_scope as provisioner


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP22A_PHASE4_FREE_PREVIEW_CONTRACT.json"
_ORG_ID = "org-safe-preview"
_PROJECT = {
    "id": "blue-lake-123",
    "name": provisioner.NEON_PROJECT_NAME,
    "org_id": _ORG_ID,
    "pg_version": 18,
    "region_id": provisioner.NEON_REGION,
}
SCRIPT = Path(provisioner.__file__).resolve()


class _Api:
    def __init__(
        self,
        *,
        organization: dict[str, object] | None = None,
        projects: list[dict[str, object]] | None = None,
    ) -> None:
        self.organization = organization or {"id": _ORG_ID, "plan": "free"}
        self.projects = [] if projects is None else projects
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def request(self, method: str, path: str, **kwargs: object) -> object:
        self.calls.append((method, path, dict(kwargs)))
        if method == "GET" and path == f"/organizations/{_ORG_ID}":
            return {"organization": self.organization}
        if method == "GET" and path.startswith("/projects?"):
            return {"projects": self.projects}
        if method == "POST" and path == "/projects":
            return {"project": _PROJECT, "operations": []}
        raise AssertionError((method, path))


def test_org_scoped_lookup_uses_direct_organization_endpoint() -> None:
    api = _Api()

    assert provisioner._neon_organization(api, _ORG_ID) == _ORG_ID
    assert api.calls == [("GET", f"/organizations/{_ORG_ID}", {})]


def test_org_scoped_lookup_rejects_identity_drift_and_paid_plan() -> None:
    mismatch_api = _Api(organization={"id": "org-other", "plan": "free"})
    with pytest.raises(
        provisioner.ProvisioningStopped,
        match="NEON_ORGANIZATION_ID_MISMATCH",
    ):
        provisioner._neon_organization(mismatch_api, _ORG_ID)

    paid_api = _Api(organization={"id": _ORG_ID, "plan": "launch"})
    with pytest.raises(
        provisioner.ProvisioningStopped,
        match="NEON_FREE_PLAN_REQUIRED",
    ):
        provisioner._neon_organization(paid_api, _ORG_ID)


def test_project_create_path_does_not_use_regions_discovery() -> None:
    api = _Api(projects=[])

    assert provisioner._ensure_neon_project(api, _ORG_ID) == _PROJECT
    paths = [path for _method, path, _kwargs in api.calls]
    assert all("/regions" not in path for path in paths)
    assert any(
        method == "POST" and path == "/projects"
        for method, path, _kwargs in api.calls
    )


def test_invalid_org_id_fails_before_provider_call() -> None:
    api = _Api()

    with pytest.raises(provisioner.ProvisioningStopped, match="NEON_ORG_ID_INVALID"):
        provisioner._neon_organization(api, "../other")

    assert api.calls == []


def test_org_scoped_adapter_forbids_user_and_region_discovery() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "/users/me/organizations" not in source
    assert "/regions?" not in source
    assert "NEON_ORG_ID" in source
    assert "from scripts import provision_v10_render_neon_preview as _base" in source


def test_phase4_contract_pins_non_secret_org_identity() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    github = payload["github_boundary"]
    database = payload["preview_database"]

    assert github["required_variable_names"] == [
        "NEON_ORG_ID",
        "RENDER_ZERO_CHARGE_ATTESTATION",
    ]
    assert database["organization_id_source"] == "GITHUB_ACTIONS_VARIABLE_NEON_ORG_ID"
    assert database["organization_scoped_api_key_supported"] is True
