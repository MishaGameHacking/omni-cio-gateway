from __future__ import annotations

from typing import Any
import unittest
from unittest.mock import patch

import scripts.check_v10_cloudflare_postmerge_release_gate as release_gate
import scripts.check_v10_sonar_equivalent_tree_provenance as provenance


_MAIN = "a" * 40
_HEAD = "b" * 40
_TREE = "c" * 40
_NAME = "SonarCloud Code Analysis"
_APP = "sonarqubecloud"
_REPOSITORY = "owner/repo"
_TOKEN = "token"


def _sonar_check(
    *,
    status: str = "completed",
    conclusion: str = "success",
) -> dict[str, Any]:
    return {
        "id": 1,
        "name": _NAME,
        "head_sha": _HEAD,
        "status": status,
        "conclusion": conclusion,
        "started_at": "2026-09-17T19:47:00Z",
        "completed_at": "2026-09-17T19:47:20Z" if status == "completed" else None,
        "app": {"slug": _APP},
        "output": {
            "annotations_count": 0,
            "summary": "[0 New issues]\n[0 Security Hotspots]",
        },
    }


def _authoritative_gate(
    *,
    status: str = "completed",
    conclusion: str = "success",
    annotations: int = 0,
) -> dict[str, Any]:
    return {
        "id": 2,
        "name": "V10 authoritative merge gate",
        "head_sha": _HEAD,
        "status": status,
        "conclusion": conclusion,
        "started_at": "2026-09-17T20:00:00Z",
        "completed_at": "2026-09-17T20:10:00Z" if status == "completed" else None,
        "app": {"slug": "github-actions"},
        "output": {
            "annotations_count": annotations,
            "summary": "repository-owned exact-head acceptance",
        },
    }


def _certify_with_head_checks(head_checks: list[dict[str, Any]]) -> str:
    pull_request = {
        "number": 540,
        "merged_at": "2026-09-17T21:00:00Z",
        "merge_commit_sha": _MAIN,
        "base": {"ref": "main"},
        "head": {"sha": _HEAD},
    }
    with (
        patch.object(provenance, "_associated_pull_request", return_value={"number": 540}),
        patch.object(provenance, "_pull_request_number", return_value=540),
        patch.object(provenance, "_canonical_pull_request", return_value=pull_request),
        patch.object(provenance, "_pull_request_head", return_value=_HEAD),
        patch.object(provenance, "_require_merge_identity"),
        patch.object(provenance, "_tree_sha", side_effect=(_TREE, _TREE)),
        patch.object(release_gate, "_check_runs", return_value=head_checks),
        patch.object(release_gate, "_require_current_main"),
    ):
        return provenance._certify_equivalent_tree_pr_sonar(
            repository=_REPOSITORY,
            token=_TOKEN,
            expected_sha=_MAIN,
            required_name=_NAME,
            required_app_slug=_APP,
            evidence_mode="test",
            emit_certification=False,
        )


class SonarEquivalentTreePrHeadFallbackTests(unittest.TestCase):
    def test_authoritative_gate_certifies_when_direct_sonar_check_is_absent(self) -> None:
        checks = [_authoritative_gate()]
        self.assertEqual(_certify_with_head_checks(checks), _HEAD)

    def test_no_direct_sonar_and_no_authoritative_gate_fails_closed(self) -> None:
        checks: list[dict[str, Any]] = []
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_PROVENANCE_HEAD_CHECK_MISSING",
        ):
            _certify_with_head_checks(checks)

    def test_direct_in_progress_sonar_remains_authoritative(self) -> None:
        checks = [
            _sonar_check(status="in_progress", conclusion="success"),
            _authoritative_gate(),
        ]
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_PROVENANCE_HEAD_CHECK_PENDING",
        ):
            _certify_with_head_checks(checks)

    def test_direct_failed_sonar_is_not_masked_by_authoritative_gate(self) -> None:
        checks = [_sonar_check(conclusion="failure"), _authoritative_gate()]
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_NOT_SUCCESS",
        ):
            _certify_with_head_checks(checks)

    def test_failed_authoritative_gate_is_not_accepted(self) -> None:
        checks = [_authoritative_gate(conclusion="failure")]
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_PROVENANCE_HEAD_AUTHORITATIVE_GATE_NOT_SUCCESS",
        ):
            _certify_with_head_checks(checks)

    def test_authoritative_gate_with_annotations_is_not_accepted(self) -> None:
        checks = [_authoritative_gate(annotations=1)]
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_PROVENANCE_HEAD_AUTHORITATIVE_GATE_ANNOTATIONS_PRESENT",
        ):
            _certify_with_head_checks(checks)


if __name__ == "__main__":
    unittest.main()
