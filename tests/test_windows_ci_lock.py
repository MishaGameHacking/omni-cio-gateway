from __future__ import annotations

from pathlib import Path

import pytest

from scripts.windows_ci_lock import parse_lock, project_lock, verify_projection


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
COLORAMA_SOURCE_HASH = "08695f5cb7ed6e0531a20572697297273c47b8cae5a63ffc6d6ed5c201be6e44"  # pragma: allowlist secret
COLORAMA_WHEEL_HASH = "4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6"  # pragma: allowlist secret
TZDATA_SOURCE_HASH = "4a1518b8993086a7982523e071643f3c0e5f213e75b21318e78bcabfff9d1415"  # pragma: allowlist secret
TZDATA_WHEEL_HASH = "dc096730c87af6cab1b171c9d532be840741ff5d459015e7f6947bd7d7e54931"  # pragma: allowlist secret


def _lock(*, uvloop_via_uvicorn: bool = True, extra: str = "") -> str:
    uvloop_owner = "# via uvicorn" if uvloop_via_uvicorn else "# via direct"
    return (
        "# generated lock\n"
        "--extra-index-url https://example.invalid/simple\n\n"
        "fastapi==1.0.0 \\\n"
        f"    --hash=sha256:{HASH_A}\n"
        "    # via input\n"
        "uvloop==0.22.1 \\\n"
        f"    --hash=sha256:{HASH_B}\n"
        f"    {uvloop_owner}\n"
        "uvicorn==0.51.0 \\\n"
        f"    --hash=sha256:{HASH_C}\n"
        "    # via input\n"
        f"{extra}"
    )


def _windows_projection() -> str:
    return _lock().replace(
        f"uvloop==0.22.1 \\\n    --hash=sha256:{HASH_B}\n    # via uvicorn\n",
        "",
    ) + (
        "colorama==0.4.6 \\\n"
        f"    --hash=sha256:{COLORAMA_SOURCE_HASH} \\\n"
        f"    --hash=sha256:{COLORAMA_WHEEL_HASH}\n"
        "    # via bandit\n"
        'tzdata==2026.3 ; sys_platform == "win32" \\\n'
        f"    --hash=sha256:{TZDATA_SOURCE_HASH} \\\n"
        f"    --hash=sha256:{TZDATA_WHEEL_HASH}\n"
        "    # via -r requirements.in\n"
    )


def test_project_lock_applies_exact_platform_delta(tmp_path: Path) -> None:
    source = tmp_path / "requirements.txt"
    destination = tmp_path / "windows-requirements.txt"
    source.write_text(_lock(), encoding="utf-8")

    project_lock(source, destination)

    projected = destination.read_text(encoding="utf-8")
    assert "uvloop==" not in projected
    assert "colorama==0.4.6" in projected
    assert COLORAMA_SOURCE_HASH in projected
    assert COLORAMA_WHEEL_HASH in projected
    assert 'tzdata==2026.3 ; sys_platform == "win32"' in projected
    assert TZDATA_SOURCE_HASH in projected
    assert TZDATA_WHEEL_HASH in projected
    assert set(parse_lock(destination)) == {
        "colorama",
        "fastapi",
        "tzdata",
        "uvicorn",
    }


def test_project_lock_rejects_unowned_uvloop(tmp_path: Path) -> None:
    source = tmp_path / "requirements.txt"
    source.write_text(_lock(uvloop_via_uvicorn=False), encoding="utf-8")

    with pytest.raises(ValueError, match="not owned by uvicorn"):
        project_lock(source, tmp_path / "windows-requirements.txt")


def test_verify_projection_requires_same_versions_and_hashes(tmp_path: Path) -> None:
    linux = tmp_path / "linux.txt"
    windows = tmp_path / "windows.txt"
    linux.write_text(_lock(), encoding="utf-8")
    windows.write_text(_windows_projection(), encoding="utf-8")

    verify_projection(linux, windows)

    windows.write_text(
        windows.read_text(encoding="utf-8").replace("uvicorn==0.51.0", "uvicorn==0.50.0"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="requirement"):
        verify_projection(linux, windows)


def test_verify_projection_rejects_additional_package(tmp_path: Path) -> None:
    linux = tmp_path / "linux.txt"
    windows = tmp_path / "windows.txt"
    linux.write_text(_lock(), encoding="utf-8")
    extra = f"watchfiles==1.0.0 \\\n    --hash=sha256:{HASH_A}\n    # via input\n"
    windows.write_text(_windows_projection() + extra, encoding="utf-8")

    with pytest.raises(ValueError, match="package set differs"):
        verify_projection(linux, windows)
