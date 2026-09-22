from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_TBANK_CA_TRUST_CONTRACT.json"
PROVISIONER = ROOT / "infrastructure/windows/provision_v10_tbank_ca_trust.ps1"
CHECKER = ROOT / "scripts/check_v10_tbank_ca_trust.ps1"
SYNTAX_CHECKER = ROOT / "scripts/check_v10_tbank_ca_trust_syntax.ps1"
AUTHORITATIVE = ROOT / ".github/workflows/self-hosted-windows-smoke.yml"
FAST_PR = ROOT / ".github/workflows/v10-pr-fast-checks.yml"


def test_tbank_ca_trust_contract_is_fail_closed() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert payload["package_index"] == (
        "https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple"
    )
    assert payload["official_certificate_source"] == "https://www.gosuslugi.ru/crt"
    assert payload["certificates"]["root"]["common_name"] == "Russian Trusted Root CA"
    assert payload["certificates"]["root"]["sha256_der"] == (
        "D26D2D0231B7C39F92CC738512BA54103519E4405D68B5BD703E9788CA8ECF31"
    )
    assert payload["certificates"]["root"]["fingerprint_pin_required"] is True
    assert (
        payload["certificates"]["intermediate"]["chain_to_pinned_root_required"] is True
    )
    assert (
        payload["certificates"]["root"]["windows_store"] == r"Cert:\LocalMachine\Root"
    )
    assert payload["certificates"]["intermediate"]["common_name"] == (
        "Russian Trusted Sub CA"
    )
    assert payload["certificates"]["intermediate"]["windows_store"] == (
        r"Cert:\LocalMachine\CA"
    )
    assert payload["mutation"]["ci_runner_may_modify_machine_trust"] is False
    assert payload["mutation"]["apply_requires_windows_administrator"] is True
    assert payload["mutation"]["network_download_by_provisioner"] is False
    assert (
        payload["mutation"]["validate_all_inputs_before_first_store_mutation"] is True
    )
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
    assert "TBANK_CA_TRUST_ROOT_FINGERPRINT_MISMATCH" in source
    assert "TBANK_CA_TRUST_INTERMEDIATE_CHAIN_INVALID" in source
    assert "Get-CertificateSha256" in source
    assert "Test-SubordinateChain" in source
    assert source.count("function Test-Administrator") == 1
    assert source.count("if ($Apply) {") == 1
    assert source.count("$roots = @(") == 1
    assert source.count("$subs = @(") == 1
    assert "AllowUnknownCertificateAuthority" in source
    assert source.index("TBANK_CA_TRUST_INTERMEDIATE_CHAIN_INVALID") < source.index(
        "$mutationsAttempted = $true"
    )
    assert "Import-Certificate" in source
    assert r"Cert:\LocalMachine\Root" in source
    assert r"Cert:\LocalMachine\CA" in source
    assert "Invoke-WebRequest" not in source
    assert "Start-BitsTransfer" not in source
    assert "System.Net.WebClient" not in source


def test_tbank_ca_checker_uses_captured_read_only_tls_probes() -> None:
    source = CHECKER.read_text(encoding="utf-8")

    assert '"-Verify"' in source
    assert '"-AsJson"' in source
    assert '"t-tech-investments"' in source
    assert '"--retries"' in source
    assert '"--timeout"' in source
    assert "Start-Process" in source
    assert "RedirectStandardOutput" in source
    assert "RedirectStandardError" in source
    assert "TBANK_CA_TRUST_VERIFIER_FAILED" in source
    assert "[AllowNull()]$Value" in source
    assert "$stdoutPath = $null" in source
    assert "$stderrPath = $null" in source
    assert "verifier_exit_code" in source
    assert "mutations_attempted = $false" in source
    assert "& powershell.exe" not in source
    assert "2>$null" not in source
    assert "Import-Certificate" not in source


def test_tbank_ca_boundary_contains_no_tls_bypass() -> None:
    sources = (
        PROVISIONER.read_text(encoding="utf-8"),
        CHECKER.read_text(encoding="utf-8"),
        SYNTAX_CHECKER.read_text(encoding="utf-8"),
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


def test_fast_pr_parses_tbank_ca_trust_powershell_boundary() -> None:
    workflow = FAST_PR.read_text(encoding="utf-8")
    marker = "      - name: Parse T-Bank CA trust PowerShell boundary"
    block = workflow.split(marker, 1)[1].split("      - name:", 1)[0]

    assert "        shell: cmd" in block
    assert "shell: powershell" not in block
    assert "-ExecutionPolicy Bypass -File" in block
    assert "scripts\\check_v10_tbank_ca_trust_syntax.ps1 -AsJson" in block
    assert "-Command" not in block


def test_tbank_ca_syntax_checker_has_bounded_targets_and_no_mutation() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = SYNTAX_CHECKER.read_text(encoding="utf-8")

    assert payload["verification"]["syntax_checker"] == (
        "scripts/check_v10_tbank_ca_trust_syntax.ps1"
    )
    assert payload["verification"]["syntax_checker_targets"] == [
        "scripts/check_v10_tbank_ca_trust.ps1",
        "infrastructure/windows/provision_v10_tbank_ca_trust.ps1",
    ]
    assert "System.Management.Automation.Language.Parser" in source
    assert "TBANK_CA_TRUST_POWERSHELL_SYNTAX_INVALID" in source
    assert "scripts\\check_v10_tbank_ca_trust.ps1" in source
    assert "infrastructure\\windows\\provision_v10_tbank_ca_trust.ps1" in source
    assert "Set-ExecutionPolicy" not in source
    assert "Import-Certificate" not in source
    assert "Invoke-Expression" not in source
    assert "Invoke-WebRequest" not in source


def test_every_self_hosted_windows_dependency_consumer_fails_fast_on_ca_trust() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    configured = {
        ROOT / path for path in payload["verification"]["windows_dependency_consumers"]
    }
    discovered = set()
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        source = path.read_text(encoding="utf-8")
        if "omni-cio-ci" in source and "windows-requirements-dev.txt" in source:
            discovered.add(path)

    assert configured == discovered
    assert (
        payload["verification"]["every_windows_dependency_consumer_requires_preflight"]
        is True
    )

    check_marker = "scripts\\check_v10_tbank_ca_trust.ps1"
    install_marker = "--require-hashes -r windows-requirements-dev.txt"
    process_marker = (
        "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "
        "scripts\\check_v10_tbank_ca_trust.ps1 -AsJson"
    )
    for path in sorted(discovered):
        source = path.read_text(encoding="utf-8")
        assert source.count(check_marker) == 1, path
        check_index = source.index(check_marker)
        assert check_index < source.index(install_marker), path

        step_start = source.rfind("      - name:", 0, check_index)
        step_end = source.find("      - name:", check_index)
        if step_end == -1:
            step_end = len(source)
        step = source[step_start:step_end]
        assert "        shell: cmd" in step, path
        assert process_marker in step, path
        assert "Set-ExecutionPolicy" not in step, path
