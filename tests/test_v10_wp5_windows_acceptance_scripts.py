from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "infrastructure" / "windows" / "run_wp5_owner_acceptance.ps1"
GPU_SAMPLER = ROOT / "infrastructure" / "windows" / "measure_wp5_gpu_load.ps1"


def test_wp5_owner_launcher_has_no_manual_enter_timing_dependency() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert "Wait-ForCombinedLoadStart" in launcher
    assert "Press ENTER only AFTER AIDA64 has already started" not in launcher
    assert "Do not press ENTER" in launcher


def test_wp5_owner_launcher_uses_inline_file_backed_gpu_evidence() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert "Running a 5-second GPU telemetry preflight before AIDA64" in launcher
    assert "GPU telemetry preflight: PASS" in launcher
    assert "& $gpuSampler -DurationSeconds $durationSeconds" in launcher
    assert "$sampler = Start-Process" not in launcher
    assert "Read-ValidatedGpuEvidence" in launcher
    assert "observed_duration_seconds" in launcher
    assert "GPU telemetry sampler did not produce the required evidence file" in launcher
    assert "GPU telemetry evidence violates the WP5 privacy contract" in launcher


def test_wp5_owner_launcher_stops_aida64_on_launcher_failure() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert "Stop-Aida64FailSafe" in launcher
    assert 'Get-Process -Name "aida64"' in launcher
    assert "Stop-Process -Force" in launcher


def test_wp5_gpu_sampler_records_observed_duration_and_privacy_contract() -> None:
    sampler = GPU_SAMPLER.read_text(encoding="utf-8")

    assert "observed_duration_seconds" in sampler
    assert "$observedDurationSeconds -lt $DurationSeconds" in sampler
    assert "model_or_uuid_collected = $false" in sampler
    assert "serial_collected = $false" in sampler
    assert "address_collected = $false" in sampler
    assert "process_list_collected = $false" in sampler
