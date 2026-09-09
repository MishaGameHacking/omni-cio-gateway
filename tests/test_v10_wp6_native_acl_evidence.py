from __future__ import annotations

import json

from scripts import augment_v10_wp6_native_acl_evidence as native_acl


def identities() -> native_acl.IdentitySids:
    return native_acl.IdentitySids(
        runner="S-1-5-21-1-1-1-1001",
        runtime="S-1-5-21-1-1-1-1002",
        execution="S-1-5-21-1-1-1-1003",
    )


def allow(sid: str, mask: int) -> native_acl.Ace:
    return native_acl.Ace(
        ace_type=native_acl.ACCESS_ALLOWED_ACE_TYPE,
        sid=sid,
        mask=mask,
    )


def deny(sid: str, mask: int) -> native_acl.Ace:
    return native_acl.Ace(
        ace_type=native_acl.ACCESS_DENIED_ACE_TYPE,
        sid=sid,
        mask=mask,
    )


def test_native_acl_classification_accepts_execution_only_data_read() -> None:
    ids = identities()
    evidence = native_acl.classify_aces(
        [
            allow(ids.execution, native_acl.FILE_READ_DATA | 0x00020000),
            allow(ids.runner, 0x00020000),
        ],
        ids,
    )

    assert evidence.execution_read_data is True
    assert evidence.runtime_read_data is False
    assert evidence.runner_read_data is False
    assert evidence.broad_read_data is False


def test_native_acl_classification_detects_forbidden_runner_and_broad_read() -> None:
    ids = identities()
    evidence = native_acl.classify_aces(
        [
            allow(ids.execution, native_acl.FILE_READ_DATA),
            allow(ids.runner, native_acl.FILE_READ_DATA),
            allow("S-1-1-0", native_acl.FILE_READ_DATA),
        ],
        ids,
    )

    assert evidence.execution_read_data is True
    assert evidence.runner_read_data is True
    assert evidence.broad_read_data is True


def test_native_acl_classification_honors_direct_deny() -> None:
    ids = identities()
    evidence = native_acl.classify_aces(
        [
            allow(ids.execution, native_acl.FILE_READ_DATA),
            deny(ids.execution, native_acl.FILE_READ_DATA),
        ],
        ids,
    )

    assert evidence.execution_read_data is False


def test_profile_augmentation_replaces_only_acl_derived_fields(tmp_path) -> None:
    profile_path = tmp_path / "profile.json"
    profile = {
        "schema_version": "1",
        "capture_mode": "PASSIVE",
        "runner": {"service_running": True},
        "runtime": {"execution_secret_direct_read_grant": True, "keep": "runtime"},
        "execution": {"execution_secret_direct_read_grant": False, "keep": "execution"},
        "boundaries": {"execution_secret_broad_read_exposure": True, "keep": "boundary"},
        "privacy": {"raw_usernames_collected": False},
    }
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    native_acl.augment_profile(
        profile_path,
        native_acl.AclEvidence(
            execution_read_data=True,
            runtime_read_data=False,
            runner_read_data=False,
            broad_read_data=False,
        ),
    )

    updated = json.loads(profile_path.read_text(encoding="utf-8"))
    assert updated["runtime"]["execution_secret_direct_read_grant"] is False
    assert updated["execution"]["execution_secret_direct_read_grant"] is True
    assert updated["boundaries"]["execution_secret_broad_read_exposure"] is False
    assert updated["runtime"]["keep"] == "runtime"
    assert updated["execution"]["keep"] == "execution"
    assert updated["boundaries"]["keep"] == "boundary"


def test_native_probe_binds_runner_identity_to_reviewed_root_service_marker() -> None:
    text = native_acl.Path(native_acl.__file__).read_text(encoding="utf-8")
    assert "RUNNER_SERVICE_MARKER = RUNNER_ROOT / \".service\"" in text
    assert "$marker='C:\\\\actions-runner\\\\.service'" in text
    assert "Get-Content -LiteralPath $marker -Raw" in text
    assert "Where-Object { $_.Name -eq $serviceName }" in text
    assert "Where-Object { $_.Name -like 'actions.runner.*' }" not in text


def test_native_probe_has_no_identity_value_logging() -> None:
    text = native_acl.Path(native_acl.__file__).read_text(encoding="utf-8")
    assert "print(identities" not in text
    assert "print(aces" not in text
    assert "completed.stdout" not in text.split("print(")[-1]
    assert "ConvertTo-Json -Compress" in text
