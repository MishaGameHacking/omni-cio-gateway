from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any
from urllib.parse import parse_qs, urlsplit, urlunsplit

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "v10-phase4-free-preview-deploy.yml"
SCRIPT = ROOT / "scripts" / "provision_v10_render_neon_preview.py"
HOSTED_APP = ROOT / "apps" / "api" / "hosted_preview.py"


def _postgres_uri(
    user: str,
    marker: str,
    host: str,
    *,
    database: str = "neondb",
    sslmode: str = "require",
) -> str:
    return urlunsplit(
        (
            "postgresql",
            f"{user}:{marker}@{host}",
            f"/{database}",
            f"sslmode={sslmode}",
            "",
        )
    )


def _module() -> Any:
    spec = importlib.util.spec_from_file_location("phase4_preview", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("phase4 preview script cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_workflow_has_no_pull_request_secret_path() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_run:" not in text
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "secrets.RENDER_API_KEY" not in text
    assert "secrets.NEON_API_KEY" not in text
    assert "cancel-in-progress: false" in text
    assert "permissions:\n  contents: read\n" in text


def test_all_trigger_paths_reverify_exact_main_regression_before_mutation() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Amendment 14 retires this path from active V10 provider authority" in text
    assert "invocation fails\n# closed before any provider mutation" in text
    assert "exit /b 78" in text


def test_workflow_runs_only_zero_cost_preview_contracts_before_mutation() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Historical Render preview path is retired" in text
    assert "Refuse obsolete Render provider mutation" in text
    assert "LEGACY_RENDER_PHASE4_RETIRED_AMENDMENT_14" in text
    assert "not an active V10 deployment path" in text
    assert "do not refresh Render attestation or mutate Render" in text


def test_runtime_uri_replacement_drops_bootstrap_credentials() -> None:
    module = _module()
    bootstrap_marker = "bootstrap-test-marker"
    runtime_marker = "runtime-test-marker"
    value = module._replace_uri_credentials(
        _postgres_uri("bootstrap", bootstrap_marker, "host.example"),
        "omni_cio_hosted_api",
        runtime_marker,
    )

    assert "bootstrap" not in value
    assert bootstrap_marker not in value
    assert "omni_cio_hosted_api" in value
    assert runtime_marker in value
    assert value.endswith("/neondb?sslmode=require")


def test_render_environment_is_fail_closed_and_free_only() -> None:
    module = _module()
    rows = module._render_env(_postgres_uri("runtime", "test-marker", "host"))
    env = {row["key"]: row["value"] for row in rows}

    assert env["OMNI_V10_HOSTED_PREVIEW"] == "1"
    assert env["PUBLIC_MULTI_USER_ENABLED"] == "false"
    assert env["BILLING_ENABLED"] == "false"
    assert env["TRIAL_ENABLED"] == "false"
    assert env["SUBSCRIPTION_ENFORCEMENT"] == "false"
    assert env["PREMIUM_FEATURE_GATING"] == "false"
    assert env["REAL_TRADING_ENABLED"] == "false"
    assert env["TRADING_METHODS"] == "false"
    assert env["BROKER_WRITE_ENABLED"] == "false"
    assert env["PYTHON_VERSION"] == "3.12.10"
    assert env["NODE_VERSION"] == "24.18.0"


def test_neon_organization_requires_one_free_plan() -> None:
    module = _module()

    class Api:
        def __init__(self, organizations: list[dict[str, object]]) -> None:
            self.organizations = organizations

        def request(self, method: str, path: str) -> dict[str, object]:
            assert method == "GET"
            assert path == "/users/me/organizations"
            return {"organizations": self.organizations}

    assert module._neon_organization(
        Api([{"id": "org-free-preview", "plan": "free"}])
    ) == "org-free-preview"

    with pytest.raises(
        module.ProvisioningStopped,
        match="NEON_ORGANIZATION_NOT_UNIQUE",
    ):
        module._neon_organization(Api([]))

    with pytest.raises(module.ProvisioningStopped, match="NEON_FREE_PLAN_REQUIRED"):
        module._neon_organization(
            Api([{"id": "org-paid-preview", "plan": "launch"}])
        )


def test_existing_neon_project_lookup_is_explicitly_org_scoped() -> None:
    module = _module()

    class Api:
        def __init__(self) -> None:
            self.paths: list[str] = []

        def request(self, method: str, path: str) -> dict[str, object]:
            assert method == "GET"
            self.paths.append(path)
            query = parse_qs(urlsplit(path).query)
            assert query["org_id"] == ["org-free-preview"]
            assert query["search"] == [module.NEON_PROJECT_NAME]
            return {
                "projects": [
                    {
                        "id": "project-free-preview",
                        "name": module.NEON_PROJECT_NAME,
                        "org_id": "org-free-preview",
                        "pg_version": 18,
                        "region_id": module.NEON_REGION,
                    }
                ]
            }

    api = Api()
    project = module._ensure_neon_project(api, "org-free-preview")

    assert project["id"] == "project-free-preview"
    assert len(api.paths) == 1


def test_wrong_region_legacy_neon_project_is_preserved() -> None:
    module = _module()
    assert module.NEON_PROJECT_NAME == "omni-cio-v10-preview-frankfurt"
    assert module.LEGACY_NEON_PROJECT_NAME == "omni-cio-v10-preview"

    class Api:
        def __init__(self) -> None:
            self.methods: list[str] = []

        def request(
            self,
            method: str,
            path: str,
            *,
            body: object | None = None,
            expected: frozenset[int] = frozenset({200}),
        ) -> dict[str, object]:
            self.methods.append(method)
            if method == "GET" and path.startswith("/projects?"):
                query = parse_qs(urlsplit(path).query)
                assert query["search"] == [module.NEON_PROJECT_NAME]
                return {
                    "projects": [
                        {
                            "id": "project-legacy-preview",
                            "name": module.LEGACY_NEON_PROJECT_NAME,
                            "org_id": "org-free-preview",
                            "pg_version": 18,
                            "region_id": "aws-us-east-1",
                        }
                    ]
                }
            if method == "GET" and path.startswith("/regions?"):
                # Neon OpenAPI RegionResponse uses the `region_id` field.
                return {"regions": [{"region_id": module.NEON_REGION}]}
            assert method == "POST"
            assert path == "/projects"
            assert expected == frozenset({201})
            assert body == {
                "project": {
                    "name": module.NEON_PROJECT_NAME,
                    "region_id": module.NEON_REGION,
                    "pg_version": 18,
                    "org_id": "org-free-preview",
                }
            }
            return {
                "project": {
                    "id": "project-frankfurt-preview",
                    "name": module.NEON_PROJECT_NAME,
                    "org_id": "org-free-preview",
                    "pg_version": 18,
                    "region_id": module.NEON_REGION,
                },
                "operations": [],
            }

    api = Api()
    project = module._ensure_neon_project(api, "org-free-preview")

    assert project["id"] == "project-frankfurt-preview"
    assert api.methods == ["GET", "GET", "POST"]


def test_neon_create_and_region_paths_are_org_scoped() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'api.request("GET", "/users/me/organizations")' in source
    assert 'regions_query = urlencode({"org_id": safe_organization_id})' in source
    assert '"org_id": safe_organization_id' in source
    assert 'project.get("org_id") != safe_organization_id' in source
    assert "NEON_PROJECT_ORGANIZATION_DRIFT" in source


def test_existing_render_service_requires_exact_safe_shape() -> None:
    module = _module()
    service = {
        "id": "srv-preview",
        "slug": "omni-cio-v10-web-9x7k",
        "autoDeploy": "no",
        "name": module.RENDER_SERVICE_NAME,
        "type": "web_service",
        "repo": module.REPOSITORY_URL,
        "branch": "main",
        "serviceDetails": {
            "runtime": "python",
            "plan": "free",
            "region": "frankfurt",
            "healthCheckPath": "/healthz",
            "url": "https://omni-cio-v10-web-9x7k.onrender.com",
            "envSpecificDetails": {
                "buildCommand": module.BUILD_COMMAND,
                "startCommand": module.START_COMMAND,
            },
        },
    }
    module._validate_existing_render_service(service)

    service["autoDeploy"] = "yes"
    with pytest.raises(
        module.ProvisioningStopped,
        match="RENDER_AUTODEPLOY_FORBIDDEN",
    ):
        module._validate_existing_render_service(service)

    service["autoDeploy"] = "no"
    service["serviceDetails"]["plan"] = "starter"
    with pytest.raises(module.ProvisioningStopped, match="RENDER_FREE_PLAN_REQUIRED"):
        module._validate_existing_render_service(service)


def test_synthetic_record_hashes_are_real_and_stable() -> None:
    module = _module()
    tenant, user = module._preview_records()
    tenant_digest = module._canonical_sha256(tenant)
    user_digest = module._canonical_sha256(user)

    assert len(tenant_digest) == 64
    assert len(user_digest) == 64
    assert tenant_digest != "0" * 64
    assert user_digest != "0" * 64
    assert tenant_digest == module._canonical_sha256(tenant)
    assert user_digest == module._canonical_sha256(user)


def test_http_failures_never_include_provider_response_body() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "exc.read" not in source
    assert "response body" not in source.casefold()
    assert "PAYMENT_OR_CARD_REQUIRED" in source
    assert "API_KEY_INVALID_OR_INSUFFICIENT" in source
    assert "::add-mask::" in source


def test_provider_identifiers_reject_path_traversal() -> None:
    module = _module()

    assert module._provider_id("srv-safe_123", "INVALID") == "srv-safe_123"
    for value in ("../owners", "srv/value", "srv?x=1", "", "srv%2fvalue"):
        with pytest.raises(module.ProvisioningStopped, match="INVALID"):
            module._provider_id(value, "INVALID")


def test_provider_paths_reject_absolute_and_encoded_traversal() -> None:
    module = _module()

    assert module._safe_api_path("/services/srv-safe", "INVALID") == (
        "/services/srv-safe"
    )
    for value in (
        "https://attacker.example/steal",
        "//attacker.example/steal",
        "/services/../owners",
        "/services/%2e%2e/owners",
        "/services/%2Fowners",
        "/services\\owners",
    ):
        with pytest.raises(module.ProvisioningStopped, match="INVALID"):
            module._safe_api_path(value, "INVALID")


def test_render_health_probe_uses_provider_assigned_slug_and_url() -> None:
    module = _module()
    service = {
        "slug": "omni-cio-v10-web-9x7k",
        "serviceDetails": {
            "url": "https://omni-cio-v10-web-9x7k.onrender.com",
        },
    }

    assert module._render_service_url(service) == (
        "https://omni-cio-v10-web-9x7k.onrender.com"
    )

    invalid = (
        (
            "omni-cio-v10-web-9x7k",
            "https://attacker.example",
        ),
        (
            "omni-cio-v10-web-9x7k",
            "https://omni-cio-v10-web-9x7k.onrender.com.attacker.example",
        ),
        (
            "omni-cio-v10-web-9x7k",
            "http://omni-cio-v10-web-9x7k.onrender.com",
        ),
        (
            "omni-cio-v10-web-9x7k",
            "https://omni-cio-v10-web-9x7k.onrender.com/other",
        ),
        (
            "omni-cio-v10-web-other",
            "https://omni-cio-v10-web-9x7k.onrender.com",
        ),
        (
            "OMNI-CIO-V10-WEB",
            "https://omni-cio-v10-web.onrender.com",
        ),
    )
    for slug, url in invalid:
        service["slug"] = slug
        service["serviceDetails"]["url"] = url
        with pytest.raises(module.ProvisioningStopped):
            module._render_service_url(service)

    source = SCRIPT.read_text(encoding="utf-8")
    hosted_source = HOSTED_APP.read_text(encoding="utf-8")
    assert "RENDER_SERVICE_URL" not in source
    assert "def _external_probe(service_url: str, expected_sha: str)" in source
    assert 'health_url = f"{service_url}/healthz"' in source
    assert "_external_probe(render_target.service_url, expected_sha)" in source
    assert 'payload.get("database") == "READY"' in source
    assert '_required_env("RENDER_EXTERNAL_HOSTNAME")' in hosted_source
    assert "_NO_REDIRECT_OPENER.open" in source


def test_neon_connection_uri_requires_neon_tls_endpoint() -> None:
    module = _module()
    safe = _postgres_uri(
        "owner",
        "test-marker",
        "ep-preview.eu-central-1.aws.neon.tech",
    )
    assert module._neon_connection_uri(safe, "neondb", "INVALID") == safe

    for value in (
        _postgres_uri("owner", "test-marker", "127.0.0.1"),
        _postgres_uri(
            "owner",
            "test-marker",
            "ep-preview.neon.tech",
            database="other",
        ),
        _postgres_uri(
            "owner",
            "test-marker",
            "ep-preview.neon.tech",
            sslmode="disable",
        ),
    ):
        with pytest.raises(module.ProvisioningStopped, match="INVALID"):
            module._neon_connection_uri(value, "neondb", "INVALID")


def test_database_bootstrap_stage_evidence_is_fixed_sanitized_and_ordered() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    bootstrap = source[
        source.index("def _bootstrap_database(") : source.index("def _render_env(")
    ]
    markers = (
        'DATABASE_BOOTSTRAP_STAGE=CONNECT',
        'DATABASE_BOOTSTRAP_STAGE=MIGRATIONS',
        'DATABASE_BOOTSTRAP_STAGE=RUNTIME_ROLE',
        'DATABASE_BOOTSTRAP_STAGE=RUNTIME_GRANTS',
        'DATABASE_BOOTSTRAP_STAGE=SYNTHETIC_SEED',
        'DATABASE_BOOTSTRAP_STAGE=COMPLETE',
    )
    positions: list[int] = []
    for marker in markers:
        literal = f'_emit("{marker}")'
        assert bootstrap.count(literal) == 1
        positions.append(bootstrap.index(literal))

    assert positions == sorted(positions)
    assert '_emit(str(' not in bootstrap
    assert '_emit(repr(' not in bootstrap
    assert 'raise ProvisioningStopped("DATABASE_BOOTSTRAP_FAILED") from None' in bootstrap
