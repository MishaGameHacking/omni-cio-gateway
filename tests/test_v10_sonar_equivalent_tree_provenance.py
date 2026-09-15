from __future__ import annotations

from typing import Any
import unittest
from unittest.mock import patch

import scripts.check_v10_cloudflare_postmerge_release_gate as release_gate
import scripts.check_v10_sonar_equivalent_tree_provenance as provenance


_MAIN = "a" * 40
_HEAD = "b" * 40
_TREE = "c" * 40
_OTHER_TREE = "d" * 40
_NAME = "SonarCloud Code Analysis"
_APP = "sonarqubecloud"
_REPOSITORY = "owner/repo"
_TOKEN = "token"
_CONCLUSION = "conclusion"
_OUTPUT = "output"


def _main_check(
    *,
    annotations: int = 0,
    conclusion: str = "cancelled",
) -> dict[str, Any]:
    return {
        "status": "completed",
        _CONCLUSION: conclusion,
        _OUTPUT: {"annotations_count": annotations, "summary": "analysis failed"},
    }


def _pull(
    *,
    base_ref: str = "main",
    merge_sha: str = _MAIN,
    head_sha: str = _HEAD,
) -> dict[str, Any]:
    return {
        "merged_at": "2026-09-15T22:09:17Z",
        "merge_commit_sha": merge_sha,
        "base": {"ref": base_ref},
        "head": {"sha": head_sha},
    }


def _green_head_check() -> dict[str, Any]:
    return {
        "id": 7,
        "name": _NAME,
        "head_sha": _HEAD,
        "status": "completed",
        _CONCLUSION: "success",
        "started_at": "2026-09-15T21:57:32Z",
        "completed_at": "2026-09-15T21:58:04Z",
        "app": {"slug": _APP},
        _OUTPUT: {
            "annotations_count": 0,
            "summary": "[0 New issues]\n[0 Security Hotspots]",
        },
    }


def _tree_payload(tree_sha: str = _TREE) -> dict[str, dict[str, str]]:
    return {"tree": {"sha": tree_sha}}


def _certify(main_check: dict[str, Any] | None = None) -> str:
    return provenance.certify_cancelled_exact_main_sonar(
        repository=_REPOSITORY,
        token=_TOKEN,
        expected_sha=_MAIN,
        main_check=_main_check() if main_check is None else main_check,
        required_name=_NAME,
        required_app_slug=_APP,
    )


class SonarEquivalentTreeProvenanceTests(unittest.TestCase):
    def test_certification_requires_unique_merged_main_pr_identical_tree_and_green_head(
        self,
    ) -> None:
        api_rows = [[_pull()], _tree_payload(), _tree_payload()]
        with (
            patch.object(release_gate, "_require_current_main") as current_main,
            patch.object(release_gate, "_api_get", side_effect=api_rows),
            patch.object(release_gate, "_check_runs", return_value=[_green_head_check()]),
        ):
            certified = _certify()

        self.assertEqual(certified, _HEAD)
        self.assertEqual(current_main.call_count, 2)

    def test_multiple_associated_prs_fail_closed(self) -> None:
        with patch.object(release_gate, "_api_get", return_value=[_pull(), _pull()]):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_PROVENANCE_PULL_NOT_UNIQUE",
            ):
                provenance._associated_pull_request(_REPOSITORY, _TOKEN, _MAIN)

    def test_non_main_or_wrong_merge_sha_fail_closed(self) -> None:
        cases = (
            (_pull(base_ref="release"), "CLOUDFLARE_POSTMERGE_PROVENANCE_BASE_NOT_MAIN"),
            (
                _pull(merge_sha=_OTHER_TREE),
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_SHA_MISMATCH",
            ),
        )
        for pull, code in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(RuntimeError, code):
                    provenance._pull_request_head(pull, _MAIN)

    def test_source_tree_mismatch_fails_closed(self) -> None:
        api_rows = [[_pull()], _tree_payload(), _tree_payload(_OTHER_TREE)]
        with (
            patch.object(release_gate, "_require_current_main"),
            patch.object(release_gate, "_api_get", side_effect=api_rows),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_PROVENANCE_TREE_MISMATCH",
            ):
                _certify()

    def test_main_cancellation_must_have_zero_annotations(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_CHECK_ANNOTATIONS_PRESENT",
        ):
            provenance._require_cancelled_main_check(_main_check(annotations=1))

    def test_main_failure_is_not_eligible_for_cancelled_provenance(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_CHECK_NOT_CANCELLED",
        ):
            provenance._require_cancelled_main_check(_main_check(conclusion="failure"))

    def test_pr_head_sonar_must_be_normal_success(self) -> None:
        bad_head = _green_head_check()
        bad_head[_CONCLUSION] = "cancelled"
        api_rows = [[_pull()], _tree_payload(), _tree_payload()]
        with (
            patch.object(release_gate, "_require_current_main"),
            patch.object(release_gate, "_api_get", side_effect=api_rows),
            patch.object(release_gate, "_check_runs", return_value=[bad_head]),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_NOT_SUCCESS",
            ):
                _certify()

    def test_pr_head_sonar_findings_remain_red(self) -> None:
        finding = _green_head_check()
        finding[_OUTPUT]["summary"] = "[1 New issues]\n[0 Security Hotspots]"
        api_rows = [[_pull()], _tree_payload(), _tree_payload()]
        with (
            patch.object(release_gate, "_require_current_main"),
            patch.object(release_gate, "_api_get", side_effect=api_rows),
            patch.object(release_gate, "_check_runs", return_value=[finding]),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_NEW_ISSUES_PRESENT",
            ):
                _certify()


if __name__ == "__main__":
    unittest.main()
