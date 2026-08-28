from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
from urllib.parse import urlunsplit

import pytest

from scripts import provision_v10_render_neon_preview_org_scope as provisioner


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP22A_PHASE4_FREE_PREVIEW_CONTRACT.json"
_ORG_ID = "org-safe-preview"
_PROJECT = {
    "id": "blue-lake-123",
    "name": "omni-cio-v10-preview-frankfurt",
    "org_id": _ORG_ID,
    "pg_version": 18,
    "region_id": provisioner.NEON_REGION,
}
SCRIPT = Path(provisioner.__file__).resolve()
_TEST_TOKEN = "test-neon-token"
ProviderCall = Callable[..., object]


def _no_sleep(_delay: float) -> None:
    return None


def _api(*, sleeper: Callable[[float], None] = _no_sleep) -> provisioner.OrgScopedNeonApi:
    return provisioner.OrgScopedNeonApi(
        _TEST_TOKEN,
        _ORG_ID,
        sleeper=sleeper,
    )


def _organization_response(org_id: str, plan: str) -> dict[str, object]:
    return {"organization": {"id": org_id, "plan": plan}}


def _postgres_uri(user: str, marker: str, host: str) -> str:
    return urlunsplit(
        (
            "postgresql",
            f"{user}:{marker}@{host}",
            "/neondb",
            "sslmode=require",
            "",
        )
    )


def _rejecting_call(status: int) -> ProviderCall:
    def reject(
        _method: str,
        _path: str,
        **_kwargs: object,
    ) -> object:
        raise provisioner.ProvisioningStopped(
            "NEON_API_KEY_INVALID_OR_INSUFFICIENT",
            status=status,
        )

    return reject


def test_org_scoped_lookup_uses_direct_organization_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _api()
    calls: list[tuple[str, str]] = []

    def provider_call(
        method: str,
        path: str,
        **_kwargs: object,
    ) -> object:
        calls.append((method, path))
        return _organization_response(_ORG_ID, "free")

    monkeypatch.setattr(api, "_call_provider", provider_call)

    assert provisioner._neon_organization(api, _ORG_ID) == _ORG_ID
    assert calls == [("GET", f"/organizations/{_ORG_ID}")]


def test_org_scoped_lookup_rejects_identity_drift_and_paid_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mismatch_api = _api()
    paid_api = _api()
    monkeypatch.setattr(
        mismatch_api,
        "_call_provider",
        lambda *_args, **_kwargs: _organization_response("org-other", "free"),
    )
    monkeypatch.setattr(
        paid_api,
        "_call_provider",
        lambda *_args, **_kwargs: _organization_response(_ORG_ID, "launch"),
    )

    with pytest.raises(
        provisioner.ProvisioningStopped,
        match="NEON_ORGANIZATION_ID_MISMATCH",
    ):
        provisioner._neon_organization(mismatch_api, _ORG_ID)

    with pytest.raises(
        provisioner.ProvisioningStopped,
        match="NEON_FREE_PLAN_REQUIRED",
    ):
        provisioner._neon_organization(paid_api, _ORG_ID)


def test_clean_room_project_create_reuses_base_target_without_provider_regions_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _api()
    calls: list[tuple[str, str]] = []
    intercepted_region_paths: list[str] = []
    original_region_response = api._static_region_response
    connection_uri = _postgres_uri(
        "neondb_owner",
        "synthetic-marker",
        "ep-test.neon.tech",
    )

    def provider_call(
        method: str,
        path: str,
        **_kwargs: object,
    ) -> object:
        calls.append((method, path))
        if method == "GET" and path.startswith("/projects?"):
            return {"projects": []}
        if method == "POST" and path == "/projects":
            return {"project": _PROJECT, "operations": []}
        if method == "GET" and path.endswith("/branches?limit=100"):
            return {"branches": [{"id": "br-main", "name": "main", "default": True}]}
        if method == "GET" and path.endswith("/databases"):
            return {"databases": [{"name": "neondb", "owner_name": "neondb_owner"}]}
        if method == "GET" and "/connection_uri?" in path:
            return {"uri": connection_uri}
        raise AssertionError((method, path))

    def region_response(path: str) -> dict[str, object] | None:
        if path.startswith("/regions"):
            intercepted_region_paths.append(path)
        return original_region_response(path)

    monkeypatch.setattr(api, "_call_provider", provider_call)
    monkeypatch.setattr(api, "_static_region_response", region_response)

    target = provisioner._neon_target(api, _ORG_ID)

    assert target.project_id == _PROJECT["id"]
    assert intercepted_region_paths == [f"/regions?org_id={_ORG_ID}"]
    assert all("/regions" not in path for _method, path in calls)
    assert ("POST", "/projects") in calls


def test_static_region_shim_rejects_wrong_organization_before_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _api()
    called = False

    def provider_call(*_args: object, **_kwargs: object) -> object:
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(api, "_call_provider", provider_call)
    wrong_path = "/regions?org_id=org-other"

    with pytest.raises(
        provisioner.ProvisioningStopped,
        match="NEON_REGION_ORGANIZATION_DRIFT",
    ):
        api.request("GET", wrong_path)

    assert called is False


def test_static_region_shim_still_enforces_safe_api_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _api()
    called = False

    def provider_call(*_args: object, **_kwargs: object) -> object:
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(api, "_call_provider", provider_call)
    unsafe_path = f"/regions?org_id={_ORG_ID}#fragment"

    with pytest.raises(provisioner.ProvisioningStopped, match="NEON_API_PATH_INVALID"):
        api.request("GET", unsafe_path)

    assert called is False


def test_invalid_org_id_fails_before_provider_call() -> None:
    with pytest.raises(provisioner.ProvisioningStopped, match="NEON_ORG_ID_INVALID"):
        provisioner.OrgScopedNeonApi(_TEST_TOKEN, "../other")


def test_org_scoped_adapter_retries_423_and_preserves_precise_auth_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    api = _api(sleeper=sleeps.append)
    attempts = 0

    def locked_then_ready(
        method: str,
        path: str,
        **_kwargs: object,
    ) -> object:
        nonlocal attempts
        del method, path
        attempts += 1
        if attempts == 1:
            raise provisioner.ProvisioningStopped("NEON_API_HTTP_ERROR", status=423)
        return _organization_response(_ORG_ID, "free")

    monkeypatch.setattr(api, "_call_provider", locked_then_ready)
    assert api.request("GET", f"/organizations/{_ORG_ID}") == _organization_response(
        _ORG_ID,
        "free",
    )
    assert attempts == 2
    assert sleeps == [1.0]

    for status, code in (
        (401, "NEON_API_KEY_INVALID"),
        (403, "NEON_API_KEY_INSUFFICIENT"),
    ):
        rejecting_api = _api()
        monkeypatch.setattr(rejecting_api, "_call_provider", _rejecting_call(status))
        with pytest.raises(provisioner.ProvisioningStopped) as stopped:
            rejecting_api.request("GET", f"/organizations/{_ORG_ID}")
        assert stopped.value.code == code
        assert stopped.value.status == status


def test_org_scoped_adapter_reuses_base_target_and_forbids_user_discovery() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "/users/me/organizations" not in source
    assert "_base._neon_target" in source
    assert "def _ensure_neon_project(" not in source
    assert "def _neon_target(api:" in source
    assert "NEON_ORG_ID" in source


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
