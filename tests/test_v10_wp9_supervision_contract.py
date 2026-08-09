from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP9_SUPERVISION_CONTRACT.json"
CHECKER = ROOT / "scripts" / "check_v10_wp9_supervision_contract.py"
ASSESSOR = ROOT / "scripts" / "assess_v10_wp9_supervision_profile.py"
PROVISIONER = ROOT / "infrastructure" / "windows" / "provision_wp9_supervision.ps1"
ROLLBACK = ROOT / "infrastructure" / "windows" / "rollback_wp9_supervision.ps1"
HEALTH = ROOT / "infrastructure" / "windows" / "wp9_health_supervisor.ps1"


def load_contract() -> dict[str, object]:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def load_assessor():
    spec = importlib.util.spec_from_file_location("wp9_assessor", ASSESSOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_static_checker_passes() -> None:
    completed = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_wp9_uses_windows_native_bounded_supervision() -> None:
    payload = load_contract()
    supervision = payload["supervision"]
    assert isinstance(supervision, dict)
    assert supervision["mechanism"] == "WINDOWS_TASK_SCHEDULER_PLUS_EXISTING_WINDOWS_SERVICES"
    assert supervision["third_party_service_wrapper_allowed"] is False
    assert supervision["health_principal"] == r"NT AUTHORITY\LOCAL SERVICE"
    assert supervision["health_logon_type"] == "ServiceAccount"
    assert supervision["health_run_level"] == "Limited"
    assert supervision["startup_trigger_required"] is True
    assert supervision["periodic_health_interval_minutes"] == 1440
    assert supervision["component_restart_count"] == 3
    assert supervision["component_restart_interval_seconds"] == 60
    assert supervision["infinite_restart_loop_allowed"] is False


def test_later_product_slots_remain_sealed() -> None:
    payload = load_contract()
    components = payload["components"]
    assert isinstance(components, list)
    by_id = {row["id"]: row for row in components if isinstance(row, dict)}
    slots = {"core_api", "web", "telegram", "watchtower", "ai_worker"}
    for slot_id in slots:
        assert by_id[slot_id]["activation"] == "SEALED_UNTIL_OWNING_WP"
        assert by_id[slot_id]["expected_current_state"] == "NOT_READY"
        assert by_id[slot_id]["intended_runtime_role"] == "omni-cio-runtime"
    sealed = payload["sealed_boundaries"]
    assert isinstance(sealed, dict)
    assert sealed["execution_task_created"] is False
    assert sealed["execution_role_enabled"] is False
    assert sealed["broker_write_enabled"] is False
    assert sealed["real_money_authority_changed"] is False
    assert sealed["wp8_payload_access_for_health_principal"] is False


def test_rehearsals_are_synthetic_and_do_not_stop_postgresql() -> None:
    payload = load_contract()
    restart = payload["restart_rehearsal"]
    dependency = payload["dependency_rehearsal"]
    assert isinstance(restart, dict) and isinstance(dependency, dict)
    assert restart["uses_synthetic_non_product_workers"] is True
    assert set(restart["slots"]) == {"core_api", "web", "telegram", "watchtower", "ai_worker"}
    assert restart["kill_then_recover_required"] is True
    assert restart["bounded_restart_required"] is True
    assert restart["real_runtime_retest_required_in_owning_future_wp"] is True
    assert dependency["uses_synthetic_non_product_dependency"] is True
    assert dependency["production_database_stop_required"] is False


def test_reboot_gate_requires_fresh_post_boot_evidence() -> None:
    payload = load_contract()
    reboot = payload["reboot_rehearsal"]
    exit_gate = payload["exit_gate"]
    assert isinstance(reboot, dict) and isinstance(exit_gate, dict)
    assert reboot["owner_initiated_full_reboot_required"] is True
    assert reboot["manual_application_terminal_launch_allowed"] is False
    assert reboot["self_hosted_runner_must_return_automatically"] is True
    assert reboot["health_status_must_be_written_after_new_boot"] is True
    assert reboot["stale_pre_reboot_status_may_not_pass"] is True
    assert exit_gate["post_reboot_fresh_status"] is True
    assert set(exit_gate["post_reboot_status_allowed"]) == {"HEALTHY", "DEGRADED"}
    assert exit_gate["app_entrypoint"] == "app:app"
    assert exit_gate["trading_methods"] is False


def test_provisioner_has_idempotence_and_guarded_reboot() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    assert "WP9_APPLY_REQUIRES_OWNER_ADMINISTRATOR" in text
    assert "WP9_IDEMPOTENCE_NOT_PROVEN" in text
    assert "-RunRehearsals" in text
    assert "-ArmReboot" in text
    assert "-RestartComputer" in text
    assert "Stop-Process" in text
    assert "shutdown.exe /r /t 10" in text
    assert '"OmniCIO.V10.Execution"' not in text


def test_sealed_slot_idempotence_tolerates_provider_trigger_metadata() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    assert "provider-specific serialization detail" in text
    assert "elseif ($triggers.Count -ne 0)" not in text
    assert "if ($enabled -ne $ExpectedEnabled)" in text


def test_runner_task_scheduler_visibility_is_read_only() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")
    assert "Ensure-Wp9SchedulerReadBoundary" in text
    assert "GetSecurityDescriptor" in text
    assert "SetSecurityDescriptor" in text
    assert "$fileGenericRead = 0x00120089" in text
    assert "AceQualifier]::AccessAllowed" in text
    assert "Ensure-SchedulerObjectReadAccess" in text


def test_rollback_is_marker_guarded_and_preserves_prior_boundaries() -> None:
    text = ROLLBACK.read_text(encoding="utf-8")
    assert "OMNI-CIO-V10-WP9-OWNED-v1" in text
    assert "WP9_ROLLBACK_REFUSED" in text
    assert "Unregister-ScheduledTask" in text
    assert "postgresql_preserved = $true" in text
    assert "runner_preserved = $true" in text
    assert "wp6_wp7_wp8_preserved = $true" in text


def test_health_supervisor_is_truthful_before_later_wps() -> None:
    text = HEALTH.read_text(encoding="utf-8")
    assert "pg_isready.exe" in text
    assert "SEALED_PRODUCT_SLOTS_NOT_READY" in text
    assert '"NOT_READY"' in text
    assert '"DEGRADED"' in text
    assert '"HEALTHY"' in text
    assert "post_boot_observed" in text


def valid_profile() -> dict[str, object]:
    task = {
        "present": True,
        "enabled": True,
        "expected_enabled": True,
        "principal_is_local_service": True,
        "bounded_restart": True,
        "valid": True,
    }
    sealed = {
        "present": True,
        "enabled": False,
        "expected_enabled": False,
        "principal_is_local_service": True,
        "bounded_restart": True,
        "valid": True,
    }
    return {
        "schema_version": "1",
        "work_package": "WP9",
        "mode": "AUDIT",
        "status": "PASS",
        "reasons": [],
        "runner_process": True,
        "health_task": task,
        "sealed_slots": [
            {"id": slot, "task": sealed.copy()}
            for slot in ("core_api", "web", "telegram", "watchtower", "ai_worker")
        ],
        "execution_task_present": False,
        "runtime_role": {"present": True, "enabled": False, "administrator": False},
        "execution_role": {"present": True, "enabled": False, "administrator": False},
        "local_service_wp8_payload_read_grant": False,
        "provision": {
            "present": True,
            "idempotence_verified": True,
            "future_product_slots_sealed": True,
            "real_secret_values_used": False,
            "real_money_authority_changed": False,
        },
        "restart_rehearsal_pass": True,
        "dependency_rehearsal_pass": True,
        "post_reboot_fresh_status": True,
        "health_status": "DEGRADED",
        "privacy": {
            "raw_usernames_collected": False,
            "sids_emitted": False,
            "hostnames_collected": False,
            "addresses_collected": False,
            "credential_values_collected": False,
            "ciphertext_collected": False,
            "credential_hashes_collected": False,
            "account_ids_collected": False,
            "private_data_collected": False,
            "process_command_lines_collected": False,
            "process_dumps_collected": False,
        },
    }


def test_assessor_accepts_truthful_degraded_post_reboot_profile() -> None:
    module = load_assessor()
    assert module.assess(valid_profile()) == []


def test_assessor_fails_closed_on_authority_or_reboot_regression() -> None:
    module = load_assessor()
    profile = valid_profile()
    profile["execution_task_present"] = True
    profile["post_reboot_fresh_status"] = False
    profile["local_service_wp8_payload_read_grant"] = True
    blockers = module.assess(profile)
    assert "EXECUTION_TASK_PRESENT" in blockers
    assert "POST_REBOOT_FRESH_STATUS_NOT_PROVEN" in blockers
    assert "LOCAL_SERVICE_WP8_PAYLOAD_GRANT_PRESENT" in blockers
