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
_PR_NUMBER = 517
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
    number: int = _PR_NUMBER,
    base_ref: str = "main",
    merge_sha: str | None = _MAIN,
    head_sha: str = _HEAD,
) -> dict[str, Any]:
    return {
        "number": number,
        "merged_at": "2026-09-15T22:09:17Z",
        "merge_commit_sha": merge_sha,
        "base": {"ref": base_ref},
        "head": {"sha": head_sha},
    }


def _pull_with_unavailable_merge_sha(*, missing: bool) -> dict[str, Any]:
    pull = _pull(merge_sha=None)
    if missing:
        del pull["merge_commit_sha"]
    return pull


def _merge_event(commit_id: object = _MAIN) -> dict[str, object]:
    return {"event": "merged", "commit_id": commit_id}


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


def _suite(
    *,
    suite_id: int = 101,
    status: str = "queued",
    conclusion: str | None = None,
    check_runs_count: int = 0,
    head_sha: str = _MAIN,
) -> dict[str, Any]:
    return {
        "id": suite_id,
        "head_sha": head_sha,
        "status": status,
        "conclusion": conclusion,
        "latest_check_runs_count": check_runs_count,
        "created_at": "2026-09-17T18:03:22Z",
        "updated_at": "2026-09-17T18:03:22Z",
        "app": {"slug": _APP},
    }


def _tree_payload(tree_sha: str = _TREE) -> dict[str, dict[str, str]]:
    return {"tree": {"sha": tree_sha}}


def _api_rows(
    *,
    associated: dict[str, Any] | None = None,
    canonical: dict[str, Any] | None = None,
    head_tree: str = _TREE,
) -> list[Any]:
    association = _pull() if associated is None else associated
    detail = _pull() if canonical is None else canonical
    return [[association], detail, _tree_payload(), _tree_payload(head_tree)]


def _certify(main_check: dict[str, Any] | None = None) -> str:
    return provenance.certify_cancelled_exact_main_sonar(
        repository=_REPOSITORY,
        token=_TOKEN,
        expected_sha=_MAIN,
        main_check=_main_check() if main_check is None else main_check,
        required_name=_NAME,
        required_app_slug=_APP,
    )


def _certify_missing() -> str:
    return provenance.certify_missing_exact_main_sonar(
        repository=_REPOSITORY,
        token=_TOKEN,
        expected_sha=_MAIN,
        required_name=_NAME,
        required_app_slug=_APP,
    )


def _require_merge_identity(pull_request: dict[str, Any]) -> None:
    provenance._require_merge_identity(
        _REPOSITORY,
        _TOKEN,
        _PR_NUMBER,
        pull_request,
        _MAIN,
    )


class SonarEquivalentTreeProvenanceTests(unittest.TestCase):
    def test_certification_requires_unique_canonical_pr_tree_and_green_head(
        self,
    ) -> None:
        with (
            patch.object(release_gate, "_require_current_main") as current_main,
            patch.object(release_gate, "_api_get", side_effect=_api_rows()) as api_get,
            patch.object(
                release_gate, "_check_runs", return_value=[_green_head_check()]
            ),
        ):
            certified = _certify()

        self.assertEqual(certified, _HEAD)
        self.assertEqual(current_main.call_count, 2)
        self.assertFalse(
            any("/issues/" in call.args[0] for call in api_get.call_args_list)
        )

    def test_missing_exact_main_uses_same_unique_tree_and_green_head_chain(
        self,
    ) -> None:
        with (
            patch.object(release_gate, "_require_current_main") as current_main,
            patch.object(release_gate, "_api_get", side_effect=_api_rows()),
            patch.object(
                release_gate,
                "_check_runs",
                side_effect=([_green_head_check()], []),
            ),
            patch.object(provenance, "_check_suites", side_effect=([], [])),
        ):
            certified = _certify_missing()

        self.assertEqual(certified, _HEAD)
        self.assertEqual(current_main.call_count, 3)

    def test_stalled_exact_main_suite_uses_same_provenance_after_deadline(self) -> None:
        stalled = _suite()
        with (
            patch.object(release_gate, "_require_current_main") as current_main,
            patch.object(release_gate, "_api_get", side_effect=_api_rows()),
            patch.object(
                release_gate,
                "_check_runs",
                side_effect=([_green_head_check()], []),
            ),
            patch.object(
                provenance,
                "_check_suites",
                side_effect=([stalled], [stalled]),
            ),
        ):
            certified = _certify_missing()

        self.assertEqual(certified, _HEAD)
        self.assertEqual(current_main.call_count, 3)

    def test_terminal_or_nonzero_suite_is_not_eligible_for_stalled_fallback(
        self,
    ) -> None:
        cases = (
            _suite(status="completed", conclusion="failure"),
            _suite(check_runs_count=1),
        )
        for suite in cases:
            with self.subTest(suite=suite):
                with (
                    patch.object(release_gate, "_require_current_main"),
                    patch.object(provenance, "_check_suites", return_value=[suite]),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_SUITE_NOT_STALLED",
                    ):
                        _certify_missing()

    def test_missing_exact_main_fails_closed_if_provider_check_appears_during_provenance(
        self,
    ) -> None:
        appeared = _green_head_check()
        appeared["head_sha"] = _MAIN
        with (
            patch.object(release_gate, "_require_current_main"),
            patch.object(release_gate, "_api_get", side_effect=_api_rows()),
            patch.object(
                release_gate,
                "_check_runs",
                side_effect=([_green_head_check()], [appeared]),
            ),
            patch.object(provenance, "_check_suites", return_value=[]),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_CHECK_APPEARED",
            ):
                _certify_missing()

    def test_missing_suite_appearance_during_provenance_fails_closed(self) -> None:
        appeared = _suite()
        with (
            patch.object(release_gate, "_require_current_main"),
            patch.object(release_gate, "_api_get", side_effect=_api_rows()),
            patch.object(
                release_gate,
                "_check_runs",
                side_effect=([_green_head_check()], []),
            ),
            patch.object(
                provenance,
                "_check_suites",
                side_effect=([], [appeared]),
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_SUITE_APPEARED",
            ):
                _certify_missing()

    def test_stalled_suite_change_during_provenance_fails_closed(self) -> None:
        initial = _suite(suite_id=101)
        replacement = _suite(suite_id=102)
        with (
            patch.object(release_gate, "_require_current_main"),
            patch.object(release_gate, "_api_get", side_effect=_api_rows()),
            patch.object(
                release_gate,
                "_check_runs",
                side_effect=([_green_head_check()], []),
            ),
            patch.object(
                provenance,
                "_check_suites",
                side_effect=([initial], [replacement]),
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_SUITE_CHANGED",
            ):
                _certify_missing()

    def test_check_suites_paginates_and_requires_exact_sha(self) -> None:
        first = [_suite(suite_id=index + 1) for index in range(100)]
        second = [_suite(suite_id=101)]
        with (
            patch.object(provenance, "_MAX_FILTERED_CHECK_SUITES", 101),
            patch.object(
                release_gate,
                "_api_get",
                side_effect=(
                    {"total_count": 101, "check_suites": first},
                    {"total_count": 101, "check_suites": second},
                ),
            ) as api_get,
        ):
            suites = provenance._check_suites(_REPOSITORY, _TOKEN, _MAIN)

        self.assertEqual(len(suites), 101)
        self.assertEqual(api_get.call_count, 2)

    def test_check_suites_rejects_exact_sha_filter_drift(self) -> None:
        drifted = _suite(head_sha=_HEAD)
        with patch.object(
            release_gate,
            "_api_get",
            return_value={"total_count": 1, "check_suites": [drifted]},
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_PROVENANCE_SUITE_FILTER_DRIFT",
            ):
                provenance._check_suites(_REPOSITORY, _TOKEN, _MAIN)

    def test_association_projection_merge_sha_is_not_used_as_canonical_metadata(
        self,
    ) -> None:
        stale_association = _pull(merge_sha=_OTHER_TREE)
        api_rows = _api_rows(associated=stale_association)
        with (
            patch.object(release_gate, "_require_current_main"),
            patch.object(release_gate, "_api_get", side_effect=api_rows),
            patch.object(
                release_gate, "_check_runs", return_value=[_green_head_check()]
            ),
        ):
            certified = _certify()

        self.assertEqual(certified, _HEAD)

    def test_valid_canonical_merge_sha_mismatch_is_pending(self) -> None:
        pull = _pull(merge_sha=_OTHER_TREE)
        with self.assertRaisesRegex(
            RuntimeError,
            provenance.MERGE_SHA_CONVERGENCE_PENDING,
        ):
            _require_merge_identity(pull)

    def test_malformed_non_null_canonical_merge_sha_is_terminal_red(self) -> None:
        pull = _pull(merge_sha="not-a-sha")
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_SHA_INVALID",
        ):
            _require_merge_identity(pull)

    def test_unavailable_merge_sha_uses_unique_exact_merged_event_then_continues(
        self,
    ) -> None:
        for missing in (False, True):
            with self.subTest(missing=missing):
                canonical = _pull_with_unavailable_merge_sha(missing=missing)
                api_rows: list[Any] = [
                    [_pull()],
                    canonical,
                    [_merge_event()],
                    _tree_payload(),
                    _tree_payload(),
                ]
                with (
                    patch.object(release_gate, "_require_current_main") as current_main,
                    patch.object(
                        release_gate, "_api_get", side_effect=api_rows
                    ) as api_get,
                    patch.object(
                        release_gate,
                        "_check_runs",
                        return_value=[_green_head_check()],
                    ),
                ):
                    certified = _certify()

                self.assertEqual(certified, _HEAD)
                self.assertEqual(current_main.call_count, 2)
                issue_calls = [
                    call.args[0]
                    for call in api_get.call_args_list
                    if "/issues/" in call.args[0]
                ]
                self.assertEqual(len(issue_calls), 1)
                self.assertIn(f"/issues/{_PR_NUMBER}/events", issue_calls[0])

    def test_unavailable_merge_sha_requires_exactly_one_merged_event(self) -> None:
        cases = (
            ([], "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_NOT_UNIQUE"),
            (
                [_merge_event(), _merge_event()],
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_NOT_UNIQUE",
            ),
        )
        for missing in (False, True):
            for events, code in cases:
                with self.subTest(missing=missing, events=events):
                    pull = _pull_with_unavailable_merge_sha(missing=missing)
                    with patch.object(release_gate, "_api_get", return_value=events):
                        with self.assertRaisesRegex(RuntimeError, code):
                            _require_merge_identity(pull)

    def test_unavailable_merge_sha_rejects_invalid_or_mismatched_event_commit(
        self,
    ) -> None:
        cases = (
            (
                [_merge_event(None)],
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_COMMIT_INVALID",
            ),
            (
                [{"event": "merged"}],
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_COMMIT_INVALID",
            ),
            (
                [_merge_event("not-a-sha")],
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_COMMIT_INVALID",
            ),
            (
                [_merge_event(_OTHER_TREE)],
                "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_COMMIT_MISMATCH",
            ),
        )
        for missing in (False, True):
            for events, code in cases:
                with self.subTest(missing=missing, code=code):
                    pull = _pull_with_unavailable_merge_sha(missing=missing)
                    with patch.object(release_gate, "_api_get", return_value=events):
                        with self.assertRaisesRegex(RuntimeError, code):
                            _require_merge_identity(pull)

    def test_unavailable_merge_sha_event_pagination_is_bounded_fail_closed(
        self,
    ) -> None:
        page = [
            {"event": "closed", "commit_id": None},
            {"event": "ready_for_review", "commit_id": None},
        ]
        overflow = [{"event": "head_ref_deleted", "commit_id": None}]
        for missing in (False, True):
            with self.subTest(missing=missing):
                pull = _pull_with_unavailable_merge_sha(missing=missing)
                with (
                    patch.object(provenance, "_ISSUE_EVENTS_PER_PAGE", 2),
                    patch.object(provenance, "_MAX_ISSUE_EVENT_PAGES", 2),
                    patch.object(
                        release_gate,
                        "_api_get",
                        side_effect=[page, page, overflow],
                    ),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_LIST_TRUNCATED",
                    ):
                        _require_merge_identity(pull)

    def test_unavailable_merge_sha_invalid_event_response_is_terminal_red(self) -> None:
        for missing in (False, True):
            with self.subTest(missing=missing):
                pull = _pull_with_unavailable_merge_sha(missing=missing)
                with patch.object(release_gate, "_api_get", return_value={}):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "CLOUDFLARE_POSTMERGE_PROVENANCE_MERGE_EVENT_RESPONSE_INVALID",
                    ):
                        _require_merge_identity(pull)

    def test_multiple_associated_prs_fail_closed(self) -> None:
        associated = [_pull(), _pull(number=_PR_NUMBER + 1)]
        with patch.object(release_gate, "_api_get", return_value=associated):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_PROVENANCE_PULL_NOT_UNIQUE",
            ):
                provenance._associated_pull_request(_REPOSITORY, _TOKEN, _MAIN)

    def test_invalid_associated_pr_number_fails_closed(self) -> None:
        associated = _pull(number=0)
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_PROVENANCE_PULL_NUMBER_INVALID",
        ):
            provenance._canonical_pull_request(_REPOSITORY, _TOKEN, associated)

    def test_invalid_canonical_pr_response_fails_closed(self) -> None:
        associated = _pull()
        with patch.object(release_gate, "_api_get", return_value=[]):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_PROVENANCE_PULL_DETAIL_RESPONSE_INVALID",
            ):
                provenance._canonical_pull_request(_REPOSITORY, _TOKEN, associated)

    def test_canonical_pr_number_mismatch_fails_closed(self) -> None:
        associated = _pull()
        canonical = _pull(number=_PR_NUMBER + 1)
        with patch.object(release_gate, "_api_get", return_value=canonical):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_PROVENANCE_PULL_DETAIL_NUMBER_MISMATCH",
            ):
                provenance._canonical_pull_request(_REPOSITORY, _TOKEN, associated)

    def test_non_main_canonical_base_fails_closed(self) -> None:
        pull = _pull(base_ref="release")
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_PROVENANCE_BASE_NOT_MAIN",
        ):
            provenance._pull_request_head(pull)

    def test_source_tree_mismatch_fails_closed(self) -> None:
        with (
            patch.object(release_gate, "_require_current_main"),
            patch.object(
                release_gate,
                "_api_get",
                side_effect=_api_rows(head_tree=_OTHER_TREE),
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_PROVENANCE_TREE_MISMATCH",
            ):
                _certify()

    def test_main_cancellation_must_have_zero_annotations(self) -> None:
        main_check = _main_check(annotations=1)
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_CHECK_ANNOTATIONS_PRESENT",
        ):
            provenance._require_cancelled_main_check(main_check)

    def test_main_failure_is_not_eligible_for_cancelled_provenance(self) -> None:
        main_check = _main_check(conclusion="failure")
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_PROVENANCE_MAIN_CHECK_NOT_CANCELLED",
        ):
            provenance._require_cancelled_main_check(main_check)

    def test_pr_head_sonar_must_be_normal_success(self) -> None:
        bad_head = _green_head_check()
        bad_head[_CONCLUSION] = "cancelled"
        with (
            patch.object(release_gate, "_require_current_main"),
            patch.object(release_gate, "_api_get", side_effect=_api_rows()),
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
        with (
            patch.object(release_gate, "_require_current_main"),
            patch.object(release_gate, "_api_get", side_effect=_api_rows()),
            patch.object(release_gate, "_check_runs", return_value=[finding]),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_NEW_ISSUES_PRESENT",
            ):
                _certify()


if __name__ == "__main__":
    unittest.main()
