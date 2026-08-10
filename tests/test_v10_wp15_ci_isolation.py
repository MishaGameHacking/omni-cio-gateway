from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_v10_wp15_ci_isolation import (
    classify_open,
    validate_report,
)


def test_ci_boundary_classifier_never_reads_file_content(tmp_path: Path) -> None:
    readable = tmp_path / "ciphertext.dpapi"
    readable.write_bytes(b"synthetic-not-a-secret")

    assert classify_open(readable) == "READABLE"
    assert classify_open(tmp_path / "missing.dpapi") == "NOT_VISIBLE"


def test_ci_boundary_validation_accepts_only_denied_or_not_visible() -> None:
    validate_report(
        {
            "schema_version": "1",
            "work_package": "WP15",
            "broker_read_ciphertext": "ACCESS_DENIED",
            "private_owner_binding": "NOT_VISIBLE",
            "secret_value_read": False,
            "private_payload_read": False,
        }
    )

    with pytest.raises(ValueError, match="WP15_CI_BOUNDARY_UNSAFE"):
        validate_report(
            {
                "schema_version": "1",
                "work_package": "WP15",
                "broker_read_ciphertext": "READABLE",
                "private_owner_binding": "NOT_VISIBLE",
                "secret_value_read": False,
                "private_payload_read": False,
            }
        )

    with pytest.raises(ValueError, match="WP15_CI_BOUNDARY_UNSAFE"):
        validate_report(
            {
                "schema_version": "1",
                "work_package": "WP15",
                "broker_read_ciphertext": "ERROR_TYPE:OSError",
                "private_owner_binding": "NOT_VISIBLE",
                "secret_value_read": False,
                "private_payload_read": False,
            }
        )
