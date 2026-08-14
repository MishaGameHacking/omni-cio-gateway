from __future__ import annotations

from datetime import datetime, timezone
import hashlib

import pytest

from scripts.assess_v10_wp22a_owner_evidence import _SOURCE_HASHES, assess


SHA = "a" * 40


def _source_hashes() -> dict[str, str]:
    return {
        key: hashlib.sha256(path.read_bytes()).hexdigest()
        for key, path in _SOURCE_HASHES.items()
    }


def valid_evidence() -> dict[str, object]:
    return {
        "schema_version": "1",
        "work_package": "WP22A",
        "evidence_type": "OWNER_PRIVATE_REMOTE_SANITIZED",
        "implementation_sha": SHA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        **_source_hashes(),
        "tailscale_private_serve_observed": True,
        "funnel_disabled_during_rehearsal": True,
        "backend_loopback_only": True,
        "private_config_acl_ok": True,
        "owner_identity_fingerprint_present": True,
        "runtime_exact_deployment": True,
        "runtime_non_admin": True,
        "runtime_task_principal_exact": True,
        "runtime_task_action_exact": True,
        "runner_runtime_data_access": False,
        "tailnet_policy_narrow_owner_only_confirmed": True,
        "owner_remote_https_cabinet_confirmed": True,
        "non_owner_identity_denied_confirmed": True,
        "local_loopback_fallback_confirmed": True,
        "serve_disabled_after_rehearsal": True,
        "funnel_disabled_after_rehearsal": True,
        "temporary_runtime_cleaned": True,
        "postgres_config_restored": True,
        "raw_owner_identity_recorded": False,
        "raw_tailnet_hostname_recorded": False,
        "session_cookie_recorded": False,
        "tailscale_auth_key_recorded": False,
        "broker_secret_recorded": False,
        "private_portfolio_payload_recorded": False,
        "public_ingress": False,
        "public_multi_user_enabled": False,
        "broker_write_authority_added": False,
        "trading_methods": False,
        "real_trading_enabled": False,
        "gateway_entrypoint": "app:app",
        "ready": True,
    }


def valid_runner_probe() -> dict[str, object]:
    return {
        "schema_version": "1",
        "work_package": "WP22A",
        "evidence_type": "RUNNER_PRIVATE_REMOTE_ISOLATION",
        "runner_is_administrator": False,
        "sanitized_evidence_present": True,
        "runner_evidence_read_allowed": True,
        "runner_evidence_write_allowed": False,
        "private_config_present": True,
        "runner_private_config_read_allowed": False,
        "runner_private_config_write_allowed": False,
        "real_secret_values_used": False,
        "raw_owner_identity_recorded": False,
        "raw_tailnet_hostname_recorded": False,
        "broker_write_authority_added": False,
        "trading_methods": False,
        "real_trading_enabled": False,
        "gateway_entrypoint": "app:app",
        "ready": True,
    }


def test_valid_sanitized_owner_evidence_is_accepted() -> None:
    assess(valid_evidence(), valid_runner_probe(), SHA)


def test_wrong_implementation_binding_is_rejected() -> None:
    evidence = valid_evidence()
    evidence["implementation_sha"] = "b" * 40
    with pytest.raises(ValueError, match="exact implementation SHA"):
        assess(evidence, valid_runner_probe(), SHA)


def test_private_field_is_rejected_even_if_other_booleans_are_safe() -> None:
    evidence = valid_evidence()
    evidence["owner_login"] = "synthetic-private-identity"
    with pytest.raises(ValueError, match="forbidden private evidence key"):
        assess(evidence, valid_runner_probe(), SHA)


def test_runner_private_config_read_or_evidence_write_is_rejected() -> None:
    runner = valid_runner_probe()
    runner["runner_private_config_read_allowed"] = True
    with pytest.raises(ValueError, match="runner_private_config_read_allowed"):
        assess(valid_evidence(), runner, SHA)

    runner = valid_runner_probe()
    runner["runner_evidence_write_allowed"] = True
    with pytest.raises(ValueError, match="runner_evidence_write_allowed"):
        assess(valid_evidence(), runner, SHA)


def test_source_hash_drift_is_rejected() -> None:
    evidence = valid_evidence()
    evidence["remote_security_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="source hash mismatch"):
        assess(evidence, valid_runner_probe(), SHA)
