from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISIONER = (
    ROOT / "infrastructure" / "windows" / "provision_wp22a_private_remote_access.ps1"
)


def test_remote_acceptance_requires_exact_live_task_binding() -> None:
    source = PROVISIONER.read_text(encoding="utf-8")
    binding = source[
        source.index("function Test-RemoteTaskExactBinding") : source.index(
            "function Get-RemoteTaskFailureReason"
        )
    ]
    acceptance = source[
        source.index("function Get-RemoteAcceptanceState") : source.index(
            "function Get-RemoteAcceptanceFailureReason"
        )
    ]
    result = source[source.rindex("$result = [ordered]@{") :]

    assert 'Get-ScheduledTask -TaskName $remoteTaskName -ErrorAction Stop' in binding
    assert '[string]$task.State -ne "Running"' in binding
    assert "task.Principal.UserId" in binding
    assert "Get-LocalUser -Name $runtimeName" in binding
    assert "-ImplementationSha" in binding
    assert "-ExternalHost" in binding
    assert "-OwnerLoginSha256" in binding
    assert "-Port" in binding
    assert "$deploymentMarker" in binding
    assert "$markerSha -ne $Sha" in binding
    assert "Test-RemoteTaskExactBinding" in acceptance
    assert "remote_task_exact_binding" in acceptance
    assert "WP22A_REMOTE_TASK_BINDING_MISMATCH" in source
    assert (
        "exact_implementation_binding = [bool]$acceptance.remote_task_exact_binding"
        in result
    )
    assert "exact_implementation_binding = $true" not in result
