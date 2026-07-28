from __future__ import annotations

import importlib.util
from pathlib import Path


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
