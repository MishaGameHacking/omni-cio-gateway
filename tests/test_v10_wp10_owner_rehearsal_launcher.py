from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "infrastructure" / "windows" / "run_wp10_owner_rehearsal.ps1"


def test_owner_rehearsal_launcher_pins_machine_python_and_preserves_bypass() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")

    assert '"C:\\Program Files\\Python314\\python.exe"' in text
    assert 'Get-Command "py.exe"' in text
    assert 'WP10_PYTHON_VERSION_MISMATCH' in text
    assert '$env:PATH = "$pythonDirectory;$env:PATH"' in text
    assert "-ExecutionPolicy Bypass" in text
    assert "-UsePreparedOffdeviceTarget" in text
    assert "-AsJson" in text


def test_owner_rehearsal_launcher_does_not_handle_recovery_key_material() -> None:
    text = LAUNCHER.read_text(encoding="utf-8").lower()

    assert "recoverypassword" not in text
    assert "recoverykey" not in text
    assert "token" not in text
