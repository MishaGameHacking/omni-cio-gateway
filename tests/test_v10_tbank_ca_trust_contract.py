from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts import check_ci_security_baseline as ci_security_baseline


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/architecture/V10_TBANK_CA_TRUST_CONTRACT.json"
PROVISIONER = ROOT / "infrastructure/windows/provision_v10_tbank_ca_trust.ps1"
CHECKER = ROOT / "scripts/check_v10_tbank_ca_trust.ps1"
PREPARER = ROOT / "scripts/prepare_v10_tbank_pip_ca_bundle.py"
ROOT_CA = ROOT / "infrastructure/certificates/russian_trusted_root_ca_2022.der"
SYNTAX_CHECKER = ROOT / "scripts/check_v10_tbank_ca_trust_syntax.ps1"
AUTHORITATIVE = ROOT / ".github/workflows/self-hosted-windows-smoke.yml"
FAST_PR = ROOT / ".github/workflows/v10-pr-fast-checks.yml"
TIMEWEB_DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"


def test_tbank_ca_trust_contract_is_fail_closed() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert payload["package_index"] == (
        "https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple"
    )
    assert payload["official_certificate_source"] == "https://www.gosuslugi.ru/crt"
    assert payload["certificates"]["root"]["common_name"] == "Russian Trusted Root CA"
    root_sha256 = payload["certificates"]["root"]["sha256_der"]
    assert isinstance(root_sha256, str)
    assert len(root_sha256) == 64
    assert root_sha256 == root_sha256.upper()
    assert all(character in "0123456789ABCDEF" for character in root_sha256)
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
    verification = payload["verification"]
    assert verification["package_index_tls_probe_retries"] == 2
    assert verification["package_index_tls_probe_timeout_seconds"] == 10
    assert verification["package_index_tls_probe_retry_scope"] == (
        "NEW_HTTP_CONNECTION_ONLY"
    )
    assert (
        verification["package_index_tls_probe_retry_may_disable_tls_verification"]
        is False
    )
    assert verification["tls_verification_may_be_disabled"] is False
    assert verification["hostname_verification_may_be_disabled"] is False
    assert payload["verification"]["ci_pip_trust"] == {
        "mode": "ephemeral_pip_cert_bundle",
        "root_der": "infrastructure/certificates/russian_trusted_root_ca_2022.der",
        "base_bundle": "pip_vendored_certifi",
        "environment_variable": "PIP_CERT",
        "caller_supplied_bundle_paths": False,
        "bundle_output_scope": "RUNNER_TEMP_DIRECT_CHILD",
        "github_env_writer": "READ_ONLY_CA_CHECKER",
        "github_env_must_be_runner_temp_descendant": True,
        "machine_trust_store_required": False,
        "persistent_machine_mutation": False,
        "certificate_verification_enabled": True,
        "hostname_verification_enabled": True,
    }
    assert payload["protected_invariants"]["PUBLIC_MULTI_USER_ENABLED"] is False
    assert payload["protected_invariants"]["OMNI_V10_TELEGRAM_LOGIN_ENABLED"] is False
    assert payload["protected_invariants"]["broker_write"] is False
    assert payload["protected_invariants"]["trading_methods"] is False
    assert payload["protected_invariants"]["REAL_TRADING_ENABLED"] is False


def test_timeweb_docker_build_reuses_scoped_pinned_pip_ca_bundle() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    trust = payload["verification"]["timeweb_docker_pip_trust"]
    dockerfile = TIMEWEB_DOCKERFILE.read_text(encoding="utf-8")
    dockerignore = DOCKERIGNORE.read_text(encoding="utf-8")

    assert trust == {
        "dockerfile": "Dockerfile",
        "requirements_lock": "requirements.txt",
        "bundle_preparer": "scripts/prepare_v10_tbank_pip_ca_bundle.py",
        "root_der": "infrastructure/certificates/russian_trusted_root_ca_2022.der",
        "base_bundle": "pip_vendored_certifi",
        "environment_variable": "PIP_CERT",
        "bundle_scope": "DOCKER_BUILD_TEMP_ONLY",
        "persistent_bundle": False,
        "machine_trust_store_required": False,
        "certificate_verification_enabled": True,
        "hostname_verification_enabled": True,
        "runtime_tinvest_sdk_verify_env": "SSL_TBANK_VERIFY",
        "runtime_tinvest_sdk_verify_value": "True",
    }
    assert "prepare_v10_tbank_pip_ca_bundle.py" in dockerfile
    assert "V10_TBANK_CA_TRUST_CONTRACT.json" in dockerfile
    assert "russian_trusted_root_ca_2022.der" in dockerfile
    assert 'PIP_CERT="$PIP_CERT_PATH" python -m pip install' in dockerfile
    assert 'rm -f "$PIP_CERT_PATH" /tmp/tbank-pip-ca.json' in dockerfile
    assert "SSL_TBANK_VERIFY=True" in dockerfile
    assert "!docs/architecture/V10_TBANK_CA_TRUST_CONTRACT.json" in dockerignore
    for marker in (
        "--trusted-host",
        "PIP_TRUSTED_HOST",
        "verify=False",
        "CERT_NONE",
        "--insecure",
    ):
        assert marker not in dockerfile


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
    assert "$rootStore = [string]$contract.certificates.root.windows_store" in source
    assert (
        "$subStore = [string]$contract.certificates.intermediate.windows_store"
        in source
    )
    assert "Invoke-WebRequest" not in source
    assert "Start-BitsTransfer" not in source
    assert "System.Net.WebClient" not in source


def test_checked_in_tbank_root_certificate_matches_contract_pin() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    der = ROOT_CA.read_bytes()

    assert der
    assert b"-----BEGIN CERTIFICATE-----" not in der
    assert (
        hashlib.sha256(der).hexdigest().upper()
        == payload["certificates"]["root"]["sha256_der"]
    )


def test_tbank_pip_ca_preparer_extends_pip_certifi_without_network() -> None:
    source = PREPARER.read_text(encoding="utf-8")

    assert '"_vendor"' in source
    assert '"certifi"' in source
    assert '"cacert.pem"' in source
    assert "RUNNER_TEMP" in source
    assert "secrets.token_hex(16)" in source
    assert "os.O_EXCL" in source
    assert '"--verify-only"' in source
    assert 'parser.add_argument("--output"' not in source
    assert 'parser.add_argument("--github-env"' not in source
    assert "DER_cert_to_PEM_cert" in source
    assert "TBANK_PIP_CA_ROOT_FINGERPRINT_MISMATCH" in source
    assert "Invoke-WebRequest" not in source
    assert "urllib" not in source
    assert "requests" not in source
    assert "subprocess" not in source


def test_tbank_ca_checker_uses_ephemeral_pinned_pip_bundle() -> None:
    source = CHECKER.read_text(encoding="utf-8")

    assert "prepare_v10_tbank_pip_ca_bundle.py" in source
    assert '"bundle_path"' in source
    assert "Resolve-RunnerTempBundlePath" in source
    assert "Test-RunnerTempDescendant" in source
    assert "[System.IO.File]::AppendAllText" in source
    assert '"--github-env"' not in source
    assert '"--cert"' in source
    assert '"t-tech-investments"' in source
    assert '"--retries"' in source
    assert '"--timeout"' in source
    assert (
        "$probeRetries = "
        "[int]$contract.verification.package_index_tls_probe_retries"
    ) in source
    assert (
        "$probeTimeoutSeconds = "
        "[int]$contract.verification.package_index_tls_probe_timeout_seconds"
    ) in source
    assert '"TBANK_PACKAGE_INDEX_SECURE_PROBE_NOT_READY"' in source
    assert '"--retries",\n        "0"' not in source
    assert "TBANK_CA_TRUST_PROBE_POLICY_INVALID" in source
    assert "Start-Process" in source
    assert "RedirectStandardOutput" in source
    assert "RedirectStandardError" in source
    assert "TBANK_PIP_CA_BUNDLE_FAILED" in source
    assert "bundle_preparer_exit_code" in source
    assert "machine_trust_store_required = $false" in source
    assert "mutations_attempted = $false" in source
    assert "Import-Certificate" not in source


def test_tbank_ca_boundary_contains_no_tls_bypass() -> None:
    sources = (
        PROVISIONER.read_text(encoding="utf-8"),
        PREPARER.read_text(encoding="utf-8"),
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


def test_fast_pr_verifies_pinned_pip_ca_bundle_assembly() -> None:
    workflow = FAST_PR.read_text(encoding="utf-8")
    marker = "      - name: Verify pinned T-Bank pip CA bundle assembly"
    block = workflow.split(marker, 1)[1].split("      - name:", 1)[0]

    assert "prepare_v10_tbank_pip_ca_bundle.py --verify-only" in block
    assert "--output" not in block
    assert "--github-env" not in block
    assert "--trusted-host" not in block
    assert "Set-ExecutionPolicy" not in block


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


def test_every_self_hosted_windows_dependency_install_job_fails_fast_on_ca_trust() -> (
    None
):
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    verification = payload["verification"]
    configured_workflows = {
        ROOT / path for path in verification["windows_dependency_consumers"]
    }
    configured_jobs = {
        (ROOT / record["workflow"], record["job"])
        for record in verification["windows_dependency_install_jobs"]
    }

    install_marker = "--require-hashes -r windows-requirements-dev.txt"
    check_marker = "scripts\\check_v10_tbank_ca_trust.ps1"
    process_marker = (
        "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "
        "scripts\\check_v10_tbank_ca_trust.ps1 -AsJson"
    )
    discovered_jobs: set[tuple[Path, str]] = set()
    blocks_by_job: dict[tuple[Path, str], str] = {}

    for pattern in ("*.yml", "*.yaml"):
        for path in (ROOT / ".github/workflows").glob(pattern):
            source = path.read_text(encoding="utf-8")
            for job_name, block in ci_security_baseline.workflow_job_blocks(
                source
            ).items():
                if "omni-cio-ci" in block and install_marker in block:
                    key = (path, job_name)
                    discovered_jobs.add(key)
                    blocks_by_job[key] = block

    assert verification["dependency_install_boundary"] == "JOB_LOCAL"
    assert verification["every_windows_dependency_consumer_requires_preflight"] is True
    assert (
        verification["every_windows_dependency_install_job_requires_preflight"] is True
    )
    assert configured_jobs == discovered_jobs
    assert {path for path, _ in configured_jobs} == configured_workflows

    for key in sorted(discovered_jobs, key=lambda item: (str(item[0]), item[1])):
        block = blocks_by_job[key]
        assert block.count(check_marker) == 1, key
        assert process_marker in block, key
        assert block.index(process_marker) < block.index(install_marker), key
        assert "Set-ExecutionPolicy" not in block, key
