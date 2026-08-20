from __future__ import annotations

import json
from pathlib import Path

import pytest

from omni_cio.web.hosted_secret_custody_v1 import (
    HostedReadSecretCustodyError,
    HostedReadSecretDescriptorV1,
    new_hosted_read_secret_ref,
    validate_hosted_read_secret_scope,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "infrastructure" / "cloudru" / "wp22a" / "hosted-runtime-contract.json"


def test_hosted_runtime_contract_preserves_phase3_locks() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    authority = payload["authority"]

    assert authority["provider"] == "Cloud.ru Evolution"
    assert authority["source_only"] is True
    assert authority["provider_apply_authorized"] is False
    assert authority["public_ingress_enabled"] is False
    assert authority["authorized_recurring_rub"] == 0
    assert authority["public_multi_user_enabled"] is False
    assert authority["trading_methods_enabled"] is False
    assert authority["real_trading_enabled"] is False
    assert authority["protected_v9_entrypoint"] == "app:app"
    assert authority["wp23_unlocked"] is False


def test_hosted_private_state_and_secret_custody_fail_closed() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    private_state = payload["private_state"]
    custody = payload["broker_secret_custody"]

    assert private_state["database"] == "postgresql"
    assert private_state["tenant_context_required"] is True
    assert private_state["rls_required"] is True
    assert private_state["least_privilege_runtime_role_required"] is True
    assert private_state["public_database_ingress_allowed"] is False

    assert custody["scope"] == "tenant"
    assert custody["credential_role"] == "read"
    assert custody["plaintext_at_rest_allowed"] is False
    assert custody["plaintext_in_github_ci_artifacts_allowed"] is False
    assert custody["browser_readback_allowed"] is False
    assert custody["provider_backed_encryption_required"] is True
    assert custody["runtime_decrypt_role"] == "api"
    assert custody["cross_tenant_access_allowed"] is False


def test_hosted_recovery_contract_requires_integrity_and_tenant_preservation() -> None:
    recovery = json.loads(CONTRACT.read_text(encoding="utf-8"))["recovery"]

    for field in (
        "encrypted_backup_required",
        "off_runtime_copy_required",
        "sha256_integrity_required",
        "corrupt_backup_rejection_required",
        "tenant_isolation_after_restore_required",
        "replacement_runtime_recovery_required",
        "rollback_to_last_accepted_release_required",
    ):
        assert recovery[field] is True


def test_hosted_secret_reference_is_opaque_and_scope_validated() -> None:
    secret_ref = new_hosted_read_secret_ref()
    assert secret_ref.startswith("hosted-read:v1:")
    validate_hosted_read_secret_scope(
        tenant_id="tenant:v1:alpha_001",
        secret_ref=secret_ref,
    )
    descriptor = HostedReadSecretDescriptorV1(
        tenant_id="tenant:v1:alpha_001",
        secret_ref=secret_ref,
    )
    assert descriptor.purpose == "broker_read"


@pytest.mark.parametrize(
    ("tenant_id", "secret_ref", "expected"),
    [
        ("tenant:bad", "hosted-read:v1:" + "a" * 64, "HOSTED_SECRET_TENANT_INVALID"),
        ("tenant:v1:alpha_001", "read-connection:v1:" + "a" * 64, "HOSTED_SECRET_REF_INVALID"),
    ],
)
def test_hosted_secret_scope_rejects_invalid_identity(
    tenant_id: str,
    secret_ref: str,
    expected: str,
) -> None:
    with pytest.raises(HostedReadSecretCustodyError, match=expected):
        validate_hosted_read_secret_scope(tenant_id=tenant_id, secret_ref=secret_ref)
