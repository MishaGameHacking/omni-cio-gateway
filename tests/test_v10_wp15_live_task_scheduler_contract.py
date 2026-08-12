from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_WP15_LIVE_WEB_ACCEPTANCE_CONTRACT.json"
PROVISIONER = (
    ROOT / "infrastructure" / "windows" / "provision_wp15_live_web_acceptance.ps1"
)
STARTER = ROOT / "infrastructure" / "windows" / "start_wp15_live_web_acceptance.ps1"
RUNTIME = ROOT / "infrastructure" / "windows" / "run_wp15_live_web_runtime.ps1"
SESSION_PROBE = (
    ROOT / "infrastructure" / "windows" / "probe_wp15_live_session_runtime.py"
)
FINALIZER = ROOT / "infrastructure" / "windows" / "finalize_wp15_live_web_evidence.ps1"
AUDITOR = ROOT / "infrastructure" / "windows" / "audit_wp15_live_web_runner.ps1"


def _provisioner_text() -> str:
    return PROVISIONER.read_text(encoding="utf-8")


def _starter_text() -> str:
    return STARTER.read_text(encoding="utf-8")


def test_live_acceptance_task_can_start_and_continue_on_battery() -> None:
    text = _provisioner_text()
    settings_block = text.split("$settings = New-ScheduledTaskSettingsSet", 1)[1].split(
        "Register-ScheduledTask", 1
    )[0]

    assert "-AllowStartIfOnBatteries" in settings_block
    assert "-DontStopIfGoingOnBatteries" in settings_block


def test_live_acceptance_timeout_reports_sanitized_task_scheduler_state() -> None:
    text = _provisioner_text()
    failure_block = text.split("if (-not $readyHttp) {", 1)[1].split("\n    }\n}", 1)[0]

    assert "Get-ScheduledTaskInfo -TaskName $taskName" in failure_block
    assert "$failedTask.State" in failure_block
    assert "$failedTaskInfo.LastTaskResult" in failure_block
    assert (
        "WP15_LIVE_LOOPBACK_RUNTIME_NOT_READY; task_state={0}; last_task_result={1}"
    ) in failure_block
    assert "Get-WinEvent" not in failure_block
    assert "Get-Content" not in failure_block


def test_live_runtime_probes_postgres_session_path_before_uvicorn() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    probe = SESSION_PROBE.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert contract["windows_runtime"]["runtime_session_probe_before_http"] is True
    assert contract["windows_runtime"]["session_probe_residue"] is False
    assert contract["postgresql"]["long_lived_web_connection_autocommit"] is True
    assert contract["postgresql"]["request_transaction_boundaries_explicit"] is True
    assert "probe_wp15_live_session_runtime.py" in runtime
    assert "WP15_LIVE_SESSION_PROBE_MISSING" in runtime
    assert runtime.index("& $python $sessionProbe") < runtime.index(
        "& $python -m uvicorn"
    )
    assert "PostgresWebSessionRegistryV1" in probe
    assert "connection.autocommit = True" in probe
    assert "registry.create(" in probe
    assert "registry.resolve(" in probe
    assert "registry.revoke(" in probe
    assert "DELETE FROM omni_cio_v10.web_sessions WHERE token_sha256 = %s" in probe
    assert "EXIT_BOOTSTRAP = 76" in probe
    assert probe.index("_bind_source_root()") < probe.index(
        "from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID"
    )
    assert "print(token" not in probe
    assert "print(digest" not in probe


def test_live_session_probe_imports_archived_source_from_arbitrary_cwd(
    tmp_path: Path,
) -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "PGHOST": "127.0.0.1",
            "PGPORT": "1",
            "PGDATABASE": "omni_cio_v10_probe_import_only",
            "PGUSER": "omni_cio_runtime",
            "PGCONNECT_TIMEOUT": "1",
        }
    )
    completed = subprocess.run(
        [sys.executable, str(SESSION_PROBE)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 71
    assert "ModuleNotFoundError" not in completed.stderr
    assert "No module named 'omni_cio'" not in completed.stderr


def test_live_acceptance_starter_uses_temporary_batch_logon_right_only() -> None:
    text = _starter_text()

    assert '"SeBatchLogonRight"' in text
    assert '"SeDenyBatchLogonRight"' in text
    assert "LsaEnumerateAccountRights" in text
    assert "LsaAddAccountRights" in text
    assert "LsaRemoveAccountRights" in text
    assert "WP15_LIVE_RUNTIME_DENY_BATCH_LOGON_RIGHT_PRESENT" in text
    assert "$batchRightAdded = $false" in text
    assert "finally {" in text
    assert "RemoveRight($runtimeSid, $batchRight)" in text
    assert "WP15_LIVE_RUNTIME_BATCH_LOGON_RIGHT_RESTORE_FAILED" in text
    assert "SeServiceLogonRight" not in text
    assert "SeInteractiveLogonRight" not in text


def test_live_acceptance_starter_has_non_mutating_helper_validation() -> None:
    text = _starter_text()

    assert "[switch]$ValidateOnly" in text
    assert 'evidence_type = "LIVE_RUNTIME_BATCH_LOGON_HELPER_VALIDATION"' in text
    assert "helper_compiled" in text
    assert "mutation_performed = $false" in text
    assert "real_secret_values_used = $false" in text
    validation_block = text.split("if ($ValidateOnly) {", 1)[1].split(
        "if ([bool]$runtimeUser.Enabled)", 1
    )[0]
    assert "GetRights(" not in validation_block
    assert "AddRight(" not in validation_block
    assert "RemoveRight(" not in validation_block


def test_live_acceptance_lsa_policy_attributes_follow_windows_contract() -> None:
    text = _starter_text()
    open_policy_block = text.split("private static IntPtr OpenPolicy", 1)[1].split(
        "private static IntPtr AllocSid", 1
    )[0]

    assert "var attributes = new LSA_OBJECT_ATTRIBUTES();" in open_policy_block
    assert "attributes.Length" not in open_policy_block
    assert "POLICY_LOOKUP_NAMES" in text
    assert "POLICY_CREATE_ACCOUNT" in text


def test_live_acceptance_starter_preserves_exact_head_and_existing_provisioner() -> (
    None
):
    text = _starter_text()

    assert "WP15_LIVE_GIT_HEAD_MISMATCH" in text
    assert "WP15_LIVE_WORKTREE_NOT_CLEAN" in text
    assert '"Omni-CIO V10 WP6 runtime role anchor"' in text
    assert "WP15_LIVE_RUNTIME_IS_ADMINISTRATOR" in text
    assert '"provision_wp15_live_web_acceptance.ps1"' in text
    assert '"-Apply"' in text
    assert '"-ExpectedImplementationSha"' in text
    assert '"-AsJson"' in text


def test_live_acceptance_final_evidence_binds_privilege_starter() -> None:
    finalizer = FINALIZER.read_text(encoding="utf-8")
    auditor = AUDITOR.read_text(encoding="utf-8")

    assert (
        '$starterPath = Join-Path $PSScriptRoot "start_wp15_live_web_acceptance.ps1"'
        in finalizer
    )
    assert "acceptance_starter_sha256 = $starterHash" in finalizer
    assert (
        '$starterPath = Join-Path $PSScriptRoot "start_wp15_live_web_acceptance.ps1"'
        in auditor
    )
    assert (
        "acceptance_starter_sha256 = if (Test-Path -LiteralPath $starterPath" in auditor
    )
