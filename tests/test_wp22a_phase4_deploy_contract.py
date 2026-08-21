from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "v10-phase4-free-preview-deploy.yml"
SCRIPT = ROOT / "scripts" / "provision_v10_render_neon_preview.py"


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

    assert "workflow_run:" in text
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.event == 'push'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text
    assert "refs/remotes/origin/main" in text
    assert (
        'test "$(git rev-parse refs/remotes/origin/main)" = '
        '"$EXPECTED_MAIN_SHA"'
    ) in text
    assert "secrets.RENDER_API_KEY" in text
    assert "secrets.NEON_API_KEY" in text
    assert "cancel-in-progress: false" in text


def test_workflow_runs_only_zero_cost_preview_contracts_before_mutation() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    verify = text.index("Verify deployment source contracts before provider mutation")
    provision = text.index("Provision and deploy zero-cost synthetic preview")

    assert verify < provision
    assert "tests/test_wp22a_phase4_free_preview_authorization.py" in text
    assert "tests/test_wp22a_phase4_hosted_preview_app.py" in text
    assert "tests/test_wp22a_phase4_deploy_contract.py" in text
    assert "paid resources: forbidden" in text
    assert "real registration/private data/broker credentials: disabled" in text


def test_runtime_uri_replacement_drops_bootstrap_credentials() -> None:
    module = _module()
    value = module._replace_uri_credentials(
        "postgresql://bootstrap:bootstrap-secret@host.example/neondb?sslmode=require",
        "omni_cio_hosted_api",
        "runtime-secret",
    )

    assert "bootstrap" not in value
    assert "bootstrap-secret" not in value
    assert "omni_cio_hosted_api" in value
    assert "runtime-secret" in value
    assert value.endswith("/neondb?sslmode=require")


def test_render_environment_is_fail_closed_and_free_only() -> None:
    module = _module()
    rows = module._render_env("postgresql://runtime:secret@host/neondb")
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


def test_existing_render_service_requires_exact_safe_shape() -> None:
    module = _module()
    service = {
        "id": "srv-preview",
        "name": module.RENDER_SERVICE_NAME,
        "type": "web_service",
        "repo": module.REPOSITORY_URL,
        "branch": "main",
        "serviceDetails": {
            "runtime": "python",
            "plan": "free",
            "region": "frankfurt",
            "healthCheckPath": "/healthz",
            "envSpecificDetails": {
                "buildCommand": module.BUILD_COMMAND,
                "startCommand": module.START_COMMAND,
            },
        },
    }
    module._validate_existing_render_service(service)

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
