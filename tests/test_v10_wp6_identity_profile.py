from __future__ import annotations

import copy

from scripts import assess_v10_wp6_identity_profile as identity
from scripts import check_v10_wp6_privilege_boundary as boundary


def passing_profile() -> dict:
    return {
        "schema_version": "1",
        "capture_mode": "PASSIVE",
        "runner": {
            "service_running": True,
            "service_start_mode": "Auto",
            "account_class": "NETWORK_SERVICE",
            "administrator": False,
            "service_identity_matches_current_process": True,
            "current_process_administrator": False,
            "distinct_from_interactive_owner": True,
        },
        "runtime": {
            "identity_present": True,
            "identity_enabled": False,
            "administrator": False,
            "execution_secret_direct_read_grant": False,
            "runner_config_direct_write_grant": False,
        },
        "execution": {
            "identity_present": True,
            "identity_enabled": False,
            "administrator": False,
            "execution_secret_direct_read_grant": True,
        },
        "boundaries": {
            "execution_secret_sentinel_present": True,
            "runner_execution_secret_read": "ACCESS_DENIED",
            "execution_secret_broad_read_exposure": False,
            "runner_config_present": True,
            "runner_config_broad_write_exposure": False,
        },
        "privacy": {
            "raw_usernames_collected": False,
            "sids_emitted": False,
            "hostnames_collected": False,
            "addresses_collected": False,
            "secret_values_collected": False,
            "process_lists_collected": False,
        },
    }


def contract() -> dict:
    return boundary.load_contract()


def test_complete_least_privilege_profile_passes() -> None:
    status, blockers = identity.assess(passing_profile(), contract())
    assert status == "PASS"
    assert blockers == []


def test_local_system_runner_fails_closed() -> None:
    profile = passing_profile()
    profile["runner"]["account_class"] = "LOCAL_SYSTEM"
    profile["runner"]["administrator"] = True

    status, blockers = identity.assess(profile, contract())

    assert status == "FAIL"
    assert "RUNNER_ACCOUNT_CLASS_NOT_ALLOWED" in blockers
    assert "RUNNER_USES_LOCAL_SYSTEM" in blockers


def test_runner_secret_read_fails_closed() -> None:
    profile = passing_profile()
    profile["boundaries"]["runner_execution_secret_read"] = "ACCESS_GRANTED"

    status, blockers = identity.assess(profile, contract())

    assert status == "FAIL"
    assert "RUNNER_EXECUTION_SECRET_READ_NOT_DENIED" in blockers


def test_runtime_admin_or_secret_read_fails_closed() -> None:
    profile = passing_profile()
    profile["runtime"]["administrator"] = True
    profile["runtime"]["execution_secret_direct_read_grant"] = True

    status, blockers = identity.assess(profile, contract())

    assert status == "FAIL"
    assert "RUNTIME_ADMINISTRATOR_NOT_FALSE" in blockers
    assert "RUNTIME_EXECUTION_SECRET_READ_NOT_DENIED" in blockers


def test_missing_execution_secret_grant_fails_closed() -> None:
    profile = passing_profile()
    profile["execution"]["execution_secret_direct_read_grant"] = False

    status, blockers = identity.assess(profile, contract())

    assert status == "FAIL"
    assert "EXECUTION_SECRET_READ_GRANT_NOT_PRESENT" in blockers


def test_privacy_leak_flag_fails_closed() -> None:
    profile = passing_profile()
    profile["privacy"]["sids_emitted"] = True

    status, blockers = identity.assess(profile, contract())

    assert status == "FAIL"
    assert "PRIVACY_FLAG_NOT_FALSE:sids_emitted" in blockers


def test_partial_profile_fails_closed() -> None:
    profile = copy.deepcopy(passing_profile())
    del profile["runner"]["administrator"]

    status, blockers = identity.assess(profile, contract())

    assert status == "FAIL"
    assert any("missing runner fields" in blocker for blocker in blockers)
