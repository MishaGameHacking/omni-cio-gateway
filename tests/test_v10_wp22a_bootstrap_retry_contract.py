from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap_wp22a_terraform.ps1"


def test_opentofu_bootstrap_retries_only_transport_download_failures() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")

    assert "$maxDownloadAttempts = 3" in text
    assert "for ($attempt = 1; $attempt -le $maxDownloadAttempts; $attempt++)" in text
    assert "Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $tempArchive -TimeoutSec 90" in text
    assert "Start-Sleep -Seconds ($attempt * 2)" in text
    assert "WP22A_OPENTOFU_DOWNLOAD_FAILED_AFTER_RETRIES" in text

    loop_start = text.index("for ($attempt = 1; $attempt -le $maxDownloadAttempts; $attempt++)")
    first_download = text.index("Invoke-WebRequest", loop_start)
    partial_cleanup = text.index(
        "Remove-Item -LiteralPath $tempArchive -Force -ErrorAction SilentlyContinue",
        loop_start,
    )
    hash_check = text.index("Get-FileHash -Algorithm SHA256", first_download)

    assert partial_cleanup < first_download < hash_check
    assert text.count("Invoke-WebRequest") == 1
    assert "WP22A_OPENTOFU_ARCHIVE_HASH_MISMATCH" in text
    assert "https://github.com/opentofu/opentofu/releases/download/v$version/$archiveName" in text
