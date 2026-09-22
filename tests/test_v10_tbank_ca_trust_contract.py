from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_TBANK_CA_TRUST_CONTRACT.json"
PROVISIONER = ROOT / "infrastructure/windows/provision_v10_tbank_ca_trust.ps1"
CHECKER = ROOT / "scripts/check_v10_tbank_ca_trust.ps1"
AUTHORITATIVE = ROOT / ".github/workflows/self-hosted-windows-smoke.yml"


def test_tbank_ca_trust_contract_is_fail_closed() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert payload["package_index"] == (
        "https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple"
    )
    assert payload["official_certificate_source"] == "https://www.gosuslugi.ru/crt"
    assert payload["certificates"]["root"]["common_name"] == "Russian Trusted Root CA"
    assert payload["certificates"]["root"]["windows_store"] == r"Cert:\LocalMachine\Root"
    assert payload["certificates"]["intermediate"]["common_name"] == (
        "Russian Trusted Sub CA"
    )
    assert payload["certificates"]["intermediate"]["windows_store"] == (
        r"Cert:\LocalMachine\CA"
    )
    assert payload["mutation"]["ci_runner_may_modify_machine_trust"] is False
    assert payload["mutation"]["apply_requires_windows_administrator"] is True
    assert payload["mutation"]["network_download_by_provisioner"] is False
    assert payload["verification"]["tls_verification_may_be_disabled"] is False
    assert payload["verification"]["hostname_verification_may_be_disabled"] is False
    assert payload["protected_invariants"]["PUBLIC_MULTI_USER_ENABLED"] is False
    assert payload["protected_invariants"]["OMNI_V10_TELEGRAM_LOGIN_ENABLED"] is False
    assert payload["protected_invariants"]["broker_write"] is False
    assert payload["protected_invariants"]["trading_methods"] is False
    assert payload["protected_invariants"]["REAL_TRADING_ENABLED"] is False


def test_tbank_ca_provisioner_requires_explicit_admin_apply_and_local_files() -> None:
    source = PROVISIONER.read_text(encoding="utf-8")

    assert "Test-Administrator" in source
    assert "TBANK_CA_TRUST_ADMIN_REQUIRED" in source
    assert "TBANK_CA_TRUST_CERTIFICATE_PATHS_REQUIRED" in source
    assert "Import-Certificate" in source
    assert r'Cert:\LocalMachine\Root' in source
    assert r'Cert:\LocalMachine\CA' in source
    assert "Invoke-WebRequest" not in source
    assert "Start-BitsTransfer" not in source
    assert "System.Net.WebClient" not in source


def test_tbank_ca_checker_uses_read_only_pip_tls_probe() -> None:
    source = CHECKER.read_text(encoding="utf-8")

    assert "-Verify -AsJson" in source
    assert "pip --disable-pip-version-check index versions t-tech-investments" in source
    assert "--retries 0 --timeout 10" in source
    assert "mutations_attempted = $false" in source
    assert "Import-Certificate" not in source


def test_tbank_ca_boundary_contains_no_tls_bypass() -> None:
    sources = (
        PROVISIONER.read_text(encoding="utf-8"),
        CHECKER.read_text(encoding="utf-8"),
        AUTHORITATIVE.read_text(encoding="utf-8"),
    )
    forbidden = (
        "--trusted-host",
        "PIP_TRUSTED_HOST",
        "-SkipCertificateCheck",
        "NODE_TLS_REJECT_UNAUTHORIZED=0",
        "verify=False",
        "CERT_NONE",
        "curl -k",
        "--insecure",
    )
    for source in sources:
        for marker in forbidden:
            assert marker not in source


def test_authoritative_gate_checks_ca_before_dependency_install() -> None:
    workflow = AUTHORITATIVE.read_text(encoding="utf-8")
    check_marker = "scripts\\check_v10_tbank_ca_trust.ps1"
    install_marker = "Install hash-locked protected-runtime dependencies"

    assert workflow.count(check_marker) == 1
    assert workflow.index(check_marker) < workflow.index(install_marker)
