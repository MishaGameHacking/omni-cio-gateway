from __future__ import annotations

import importlib.util
from pathlib import Path
import re

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_ci_security_baseline.py"
)
SPEC = importlib.util.spec_from_file_location("check_ci_security_baseline", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)


def test_requirement_blocks_group_hash_continuations() -> None:
    blocks = baseline.requirement_blocks(
        "--index-url https://pypi.org/simple\n"
        "\n"
        "example-package==1.2.3 \\\n"
        "    --hash=sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \\\n"
        "    --hash=sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
    )

    assert len(blocks) == 1
    assert blocks[0].startswith("example-package==1.2.3")
    assert blocks[0].count("--hash=sha256:") == 2


def test_lock_validator_rejects_unpinned_or_unhashed_requirements(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "requirements.txt"
    lock_path.write_text(
        "unpinned-package>=1\nexact-package==2\n",
        encoding="utf-8",
    )
    failures: list[str] = []

    baseline.validate_lock_file(lock_path, failures)

    assert any("unpinned requirement" in failure for failure in failures)
    assert sum("without SHA-256 hash" in failure for failure in failures) == 2


def test_action_pin_validator_accepts_only_full_commit_sha() -> None:
    workflow = """
    - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
    - uses: actions/setup-python@v6
    - uses: ./local-action
    """
    failures: list[str] = []

    baseline.validate_action_pins(workflow, failures)

    assert len(failures) == 1
    assert "actions/setup-python@v6" in failures[0]


def test_workflow_validator_requires_self_hosted_isolation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_path = tmp_path / "regression-shield.yml"
    commands = "\n".join(baseline.REQUIRED_WORKFLOW_COMMANDS.values())
    workflow_path.write_text(
        f"permissions: contents: read\n{commands}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(baseline, "WORKFLOW_PATH", workflow_path)
    failures: list[str] = []

    baseline.validate_workflow(failures)

    assert any("dedicated self-hosted" in failure for failure in failures)
    assert any("persisted credentials" in failure for failure in failures)
    assert any("verified Python runtime" in failure for failure in failures)
    assert any("RUNNER_TEMP" in failure for failure in failures)
    assert any("external virtual environment" in failure for failure in failures)


def test_workflow_validator_rejects_pull_request_trigger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_path = tmp_path / "regression-shield.yml"
    commands = "\n".join(baseline.REQUIRED_WORKFLOW_COMMANDS.values())
    workflow_path.write_text(
        f"on:\n  pull_request:\npermissions: contents: read\n{commands}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(baseline, "WORKFLOW_PATH", workflow_path)
    failures: list[str] = []

    baseline.validate_workflow(failures)

    assert any("post-merge only" in failure for failure in failures)


def test_workflow_validator_rejects_checkout_local_virtualenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_path = tmp_path / "regression-shield.yml"
    commands = "\n".join(baseline.REQUIRED_WORKFLOW_COMMANDS.values())
    workflow_path.write_text(
        f"{commands}\npython -m venv .venv-ci\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(baseline, "WORKFLOW_PATH", workflow_path)
    failures: list[str] = []

    baseline.validate_workflow(failures)

    assert any("outside the repository checkout" in failure for failure in failures)


def test_soft_fail_policy_rejects_mandatory_gate() -> None:
    failures: list[str] = []
    baseline.validate_soft_fail_policy(
        "steps:\n"
        "  - name: Run Regression Shield with coverage\n"
        "    continue-on-error: true\n"
        "    run: python -m pytest\n",
        failures,
    )

    assert len(failures) == 1
    assert "only the post-merge diagnostics artifact" in failures[0]


def test_soft_fail_policy_allows_diagnostics_artifact_transport() -> None:
    failures: list[str] = []
    baseline.validate_soft_fail_policy(
        "steps:\n"
        "  - name: Upload test diagnostics\n"
        "    id: diagnostics_upload\n"
        "    if: always()\n"
        "    continue-on-error: true\n"
        "    uses: actions/upload-artifact@"
        "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a\n",
        failures,
    )

    assert failures == []


def test_secret_scan_exclude_pattern_is_cross_platform() -> None:
    pattern = re.compile(baseline.SECRET_SCAN_EXCLUDE_PATTERN)

    excluded = (
        ".venv/Lib/site-packages/example.py",
        r".venv-ci\Lib\site-packages\example.py",
        ".git/objects/aa/bb",
        r"build\.mypy_cache\3.12\cache.json",
        "requirements-dev.txt",
        r"artifacts\windows-compiled-requirements.txt",
    )
    for candidate in excluded:
        assert pattern.search(candidate), candidate

    assert pattern.search("tests/test_windows_ci_lock.py") is None


def test_detect_secrets_validator_reports_only_real_findings() -> None:
    failures: list[str] = []

    baseline.validate_detect_secrets_report(
        {
            "results": {
                "safe.py": [],
                "unsafe.py": [
                    {
                        "type": "Secret Keyword",
                        "line_number": 7,
                    }
                ],
            }
        },
        failures,
    )

    assert failures == ["potential secret: unsafe.py:7 (Secret Keyword)"]


def test_detect_secrets_validator_allows_only_exact_approved_wp6_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract_path = (
        tmp_path / "docs" / "architecture" / "V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json"
    )
    contract_path.parent.mkdir(parents=True)
    sensitive_word = "sec" + "ret"
    safe_line = f'  "execution_{sensitive_word}_access": "DENY",\n'
    contract_path.write_text(safe_line, encoding="utf-8")
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    report = {
        "results": {
            r"docs\architecture\V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json": [
                {"type": "Secret Keyword", "line_number": 1}
            ]
        }
    }

    failures: list[str] = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == []

    contract_path.write_text(
        f'  "execution_{sensitive_word}_access": "unexpected-value",\n',
        encoding="utf-8",
    )
    failures = []
    baseline.validate_detect_secrets_report(report, failures)

    assert failures == [
        "potential secret: "
        r"docs\architecture\V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json:1 "
        "(Secret Keyword)"
    ]


def test_detect_secrets_validator_does_not_allowlist_other_finding_types(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract_path = (
        tmp_path / "docs" / "architecture" / "V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json"
    )
    contract_path.parent.mkdir(parents=True)
    sensitive_word = "sec" + "ret"
    contract_path.write_text(
        f'  "execution_{sensitive_word}_access": "DENY",\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    failures: list[str] = []

    baseline.validate_detect_secrets_report(
        {
            "results": {
                "docs/architecture/V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json": [
                    {"type": "High Entropy String", "line_number": 1}
                ]
            }
        },
        failures,
    )

    assert failures == [
        "potential secret: "
        "docs/architecture/V10_WP6_IDENTITY_PRIVILEGE_CONTRACT.json:1 "
        "(High Entropy String)"
    ]


def test_detect_secrets_validator_allows_only_exact_wp7_public_checksum(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract_path = (
        tmp_path / "docs" / "architecture" / "V10_WP7_BOOTSTRAP_CONTRACT.json"
    )
    contract_path.parent.mkdir(parents=True)
    checksum = baseline._WP7_PUBLIC_PYTHON_SHA256
    contract_path.write_text(
        f'  "installer_sha256": "{checksum}",\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    report = {
        "results": {
            "docs/architecture/V10_WP7_BOOTSTRAP_CONTRACT.json": [
                {"type": "Hex High Entropy String", "line_number": 1}
            ]
        }
    }

    failures: list[str] = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == []

    contract_path.write_text(
        '  "installer_sha256": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",\n',
        encoding="utf-8",
    )
    failures = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == [
        "potential secret: docs/architecture/V10_WP7_BOOTSTRAP_CONTRACT.json:1 "
        "(Hex High Entropy String)"
    ]


def test_detect_secrets_validator_allows_only_exact_wp7_boundary_keyword(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract_path = (
        tmp_path / "docs" / "architecture" / "V10_WP7_BOOTSTRAP_CONTRACT.json"
    )
    contract_path.parent.mkdir(parents=True)
    sensitive_word = "sec" + "ret"
    contract_path.write_text(
        f'  "{sensitive_word}_root_owned_by_wp8": '
        f'"C:\\\\ProgramData\\\\OmniCIO\\\\{sensitive_word}s",\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    report = {
        "results": {
            "docs/architecture/V10_WP7_BOOTSTRAP_CONTRACT.json": [
                {"type": "Secret Keyword", "line_number": 1}
            ]
        }
    }

    failures: list[str] = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == []

    contract_path.write_text(
        f'  "{sensitive_word}_root_owned_by_wp8": "unexpected",\n',
        encoding="utf-8",
    )
    failures = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == [
        "potential secret: docs/architecture/V10_WP7_BOOTSTRAP_CONTRACT.json:1 "
        "(Secret Keyword)"
    ]


def test_detect_secrets_validator_allows_only_exact_wp22a_git_sha_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence_path = (
        tmp_path
        / "docs"
        / "architecture"
        / "V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.json"
    )
    transition_path = tmp_path / "tests" / "test_v10_wp22a_phase5_transition.py"
    evidence_path.parent.mkdir(parents=True)
    transition_path.parent.mkdir(parents=True)
    accepted_main = baseline._WP22A_PHASE5_ACCEPTED_MAIN_SHA
    implementation_head = baseline._WP22A_PHASE5_IMPLEMENTATION_HEAD_SHA
    evidence_path.write_text(
        f'  "accepted_main_sha": "{accepted_main}",\n',
        encoding="utf-8",
    )
    transition_path.write_text(
        f'        "{implementation_head}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    report = {
        "results": {
            r"docs\architecture\V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.json": [
                {"type": "Hex High Entropy String", "line_number": 1}
            ],
            "tests/test_v10_wp22a_phase5_transition.py": [
                {"type": "Hex High Entropy String", "line_number": 1}
            ],
        }
    }

    failures: list[str] = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == []

    evidence_path.write_text(
        f'  "accepted_main_sha": "{"a" * 40}",\n',
        encoding="utf-8",
    )
    failures = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == [
        "potential secret: "
        r"docs\architecture\V10_WP22A_PHASE5_TECHNICAL_ACCEPTANCE_EVIDENCE.json:1 "
        "(Hex High Entropy String)"
    ]
