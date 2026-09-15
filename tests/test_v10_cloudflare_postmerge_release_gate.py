from __future__ import annotations

import unittest
from unittest.mock import patch

import scripts.check_v10_cloudflare_postmerge_release_gate as gate


_SHA = "a" * 40
_REQUIRED = frozenset({"Regression Shield", "V10 Engineering Governance"})
_EXTERNAL_NAME = "SonarCloud Code Analysis"
_EXTERNAL_APP = "sonarqubecloud"


def _run(
    name: str,
    *,
    conclusion: str | None = "success",
    attempt: int = 1,
    run_id: int = 1,
):
    return {
        "name": name,
        "head_sha": _SHA,
        "head_branch": "main",
        "event": "push",
        "status": "completed" if conclusion is not None else "in_progress",
        "conclusion": conclusion,
        "run_attempt": attempt,
        "id": run_id,
    }


def _check(
    *,
    name: str = _EXTERNAL_NAME,
    app_slug: str = _EXTERNAL_APP,
    conclusion: str | None = "success",
    check_id: int = 1,
    annotations_count: int = 0,
    new_issues: int = 0,
    hotspots: int = 0,
    started_at: str = "2026-09-15T20:00:00Z",
    completed_at: str | None = "2026-09-15T20:01:00Z",
    head_sha: str = _SHA,
):
    return {
        "id": check_id,
        "name": name,
        "head_sha": head_sha,
        "status": "completed" if conclusion is not None else "in_progress",
        "conclusion": conclusion,
        "started_at": started_at,
        "completed_at": completed_at if conclusion is not None else None,
        "app": {"slug": app_slug},
        "output": {
            "annotations_count": annotations_count,
            "summary": f"[{new_issues} New issues]\n[{hotspots} Security Hotspots]",
        },
    }


class CloudflarePostMergeReleaseGateTests(unittest.TestCase):
    def test_gate_requires_core_and_success_only_for_all_observed_latest_runs(
        self,
    ) -> None:
        rows = [
            _run("Regression Shield", run_id=1),
            _run("V10 Engineering Governance", run_id=2),
        ]
        rows.extend(_run(f"workflow-{index}", run_id=10 + index) for index in range(9))
        ready, observed = gate._gate_state(rows, _REQUIRED, 11)
        self.assertTrue(ready)
        self.assertEqual(observed, 11)

        rows.append(_run("workflow-3", conclusion="failure", attempt=2, run_id=99))
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_PUSH_WORKFLOW_NOT_SUCCESS",
        ):
            gate._gate_state(rows, _REQUIRED, 11)

    def test_latest_successful_rerun_supersedes_earlier_failed_attempt(self) -> None:
        rows = [
            _run("Regression Shield", conclusion="failure", attempt=1, run_id=1),
            _run("Regression Shield", conclusion="success", attempt=2, run_id=2),
            _run("V10 Engineering Governance", run_id=3),
        ]
        rows.extend(_run(f"workflow-{index}", run_id=10 + index) for index in range(9))
        ready, observed = gate._gate_state(rows, _REQUIRED, 11)
        self.assertTrue(ready)
        self.assertEqual(observed, 11)

    def test_pending_or_missing_workflows_never_count_as_ready(self) -> None:
        rows = [
            _run("Regression Shield"),
            _run("V10 Engineering Governance", conclusion=None),
        ]
        ready, observed = gate._gate_state(rows, _REQUIRED, 11)
        self.assertFalse(ready)
        self.assertEqual(observed, 2)

    def test_external_check_requires_exact_provider_identity_and_success(self) -> None:
        self.assertFalse(
            gate._external_check_state(
                [_check(app_slug="github-actions")],
                _EXTERNAL_NAME,
                _EXTERNAL_APP,
            )
        )
        self.assertTrue(
            gate._external_check_state(
                [_check()],
                _EXTERNAL_NAME,
                _EXTERNAL_APP,
            )
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_NOT_SUCCESS",
        ):
            gate._external_check_state(
                [_check(conclusion="cancelled")],
                _EXTERNAL_NAME,
                _EXTERNAL_APP,
            )

    def test_external_check_latest_same_provider_run_is_authoritative(self) -> None:
        rows = [
            _check(
                conclusion="success",
                check_id=20,
                started_at="2026-09-15T20:00:00Z",
                completed_at="2026-09-15T20:01:00Z",
            ),
            _check(
                conclusion="cancelled",
                check_id=2,
                started_at="2026-09-15T20:02:00Z",
                completed_at="2026-09-15T20:03:00Z",
            ),
        ]
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_NOT_SUCCESS",
        ):
            gate._external_check_state(rows, _EXTERNAL_NAME, _EXTERNAL_APP)

    def test_external_check_requires_zero_sonar_new_code_metrics(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_NEW_ISSUES_PRESENT",
        ):
            gate._external_check_state(
                [_check(new_issues=1)],
                _EXTERNAL_NAME,
                _EXTERNAL_APP,
            )
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_SECURITY_HOTSPOTS_PRESENT",
        ):
            gate._external_check_state(
                [_check(hotspots=1)],
                _EXTERNAL_NAME,
                _EXTERNAL_APP,
            )

    def test_external_check_requires_zero_annotations(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_ANNOTATIONS_PRESENT",
        ):
            gate._external_check_state(
                [_check(annotations_count=1)],
                _EXTERNAL_NAME,
                _EXTERNAL_APP,
            )

    def test_workflow_runs_paginates_complete_exact_sha_evidence(self) -> None:
        first_page = [
            _run(f"workflow-{index}", run_id=index + 1) for index in range(100)
        ]
        second_page = [_run("workflow-100", run_id=101)]
        with patch.object(
            gate,
            "_api_get",
            side_effect=(
                {"total_count": 101, "workflow_runs": first_page},
                {"total_count": 101, "workflow_runs": second_page},
            ),
        ) as api_get:
            rows = gate._workflow_runs("owner/repo", "token", _SHA)

        self.assertEqual(len(rows), 101)
        self.assertEqual(api_get.call_count, 2)
        paths = [entry.args[0] for entry in api_get.call_args_list]
        self.assertIn("per_page=100", paths[0])
        self.assertIn("page=1", paths[0])
        self.assertIn("page=2", paths[1])

    def test_check_runs_paginates_complete_exact_sha_evidence(self) -> None:
        first_page = [
            _check(name=f"check-{index}", check_id=index + 1) for index in range(100)
        ]
        second_page = [_check(name="check-100", check_id=101)]
        with patch.object(
            gate,
            "_api_get",
            side_effect=(
                {"total_count": 101, "check_runs": first_page},
                {"total_count": 101, "check_runs": second_page},
            ),
        ) as api_get:
            rows = gate._check_runs("owner/repo", "token", _SHA)

        self.assertEqual(len(rows), 101)
        self.assertEqual(api_get.call_count, 2)
        paths = [entry.args[0] for entry in api_get.call_args_list]
        self.assertIn("filter=latest", paths[0])
        self.assertIn("page=1", paths[0])
        self.assertIn("page=2", paths[1])

    def test_workflow_runs_fail_closed_above_github_filtered_search_cap(self) -> None:
        with patch.object(
            gate,
            "_api_get",
            return_value={"total_count": 1001, "workflow_runs": []},
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_RUNS_TRUNCATED",
            ):
                gate._workflow_runs("owner/repo", "token", _SHA)

    def test_check_runs_fail_closed_if_exact_sha_filter_drifts(self) -> None:
        with patch.object(
            gate,
            "_api_get",
            return_value={
                "total_count": 1,
                "check_runs": [_check(head_sha="b" * 40)],
            },
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_CHECK_FILTER_DRIFT",
            ):
                gate._check_runs("owner/repo", "token", _SHA)

    def test_workflow_runs_fail_closed_if_snapshot_changes_between_pages(self) -> None:
        first_page = [
            _run(f"workflow-{index}", run_id=index + 1) for index in range(100)
        ]
        with patch.object(
            gate,
            "_api_get",
            side_effect=(
                {"total_count": 101, "workflow_runs": first_page},
                {"total_count": 102, "workflow_runs": [_run("late", run_id=102)]},
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_RUNS_CHANGED_DURING_READ",
            ):
                gate._workflow_runs("owner/repo", "token", _SHA)

    def test_api_get_retries_transient_http_without_weakening_terminal_errors(
        self,
    ) -> None:
        transient = gate.HTTPError(
            "https://api.github.com/repos/owner/repo",
            503,
            "unavailable",
            hdrs=None,
            fp=None,
        )
        with (
            patch.object(
                gate,
                "_open_api_request",
                side_effect=(transient, (200, b'{"ok": true}')),
            ) as open_api,
            patch.object(gate.time, "sleep") as sleep,
        ):
            self.assertEqual(gate._api_get("/repos/owner/repo", "token"), {"ok": True})
        self.assertEqual(open_api.call_count, 2)
        sleep.assert_called_once_with(1.0)

    def test_api_get_rejects_invalid_json_with_classified_error(self) -> None:
        with patch.object(gate, "_open_api_request", return_value=(200, b"not-json")):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_GITHUB_JSON_INVALID",
            ):
                gate._api_get("/repos/owner/repo", "token")

    def test_wait_rejects_superseded_main_before_observing_evidence(self) -> None:
        environment = {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "token"}
        with (
            patch.object(
                gate,
                "_contract",
                return_value=(_REQUIRED, 11, _EXTERNAL_NAME, _EXTERNAL_APP),
            ),
            patch.object(gate, "_current_main_sha", return_value="b" * 40),
            patch.object(gate, "_workflow_runs") as workflow_runs,
            patch.object(gate, "_check_runs") as check_runs,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_MAIN_SUPERSEDED",
            ):
                gate.wait_for_release_gate(
                    _SHA,
                    environ=environment,
                    wait_seconds=0,
                    poll_seconds=1,
                )
        workflow_runs.assert_not_called()
        check_runs.assert_not_called()

    def test_wait_rechecks_main_after_all_evidence_is_green(self) -> None:
        rows = [_run("Regression Shield"), _run("V10 Engineering Governance")]
        rows.extend(_run(f"workflow-{index}") for index in range(9))
        environment = {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "token"}
        with (
            patch.object(
                gate,
                "_contract",
                return_value=(_REQUIRED, 11, _EXTERNAL_NAME, _EXTERNAL_APP),
            ),
            patch.object(gate, "_workflow_runs", return_value=rows),
            patch.object(gate, "_check_runs", return_value=[_check()]),
            patch.object(gate, "_current_main_sha", side_effect=[_SHA, "b" * 40]),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_MAIN_SUPERSEDED",
            ):
                gate.wait_for_release_gate(
                    _SHA,
                    environ=environment,
                    wait_seconds=0,
                    poll_seconds=1,
                )

    def test_wait_reports_external_check_pending_after_workflows_are_green(
        self,
    ) -> None:
        rows = [_run("Regression Shield"), _run("V10 Engineering Governance")]
        rows.extend(_run(f"workflow-{index}") for index in range(9))
        environment = {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "token"}
        with (
            patch.object(
                gate,
                "_contract",
                return_value=(_REQUIRED, 11, _EXTERNAL_NAME, _EXTERNAL_APP),
            ),
            patch.object(gate, "_workflow_runs", return_value=rows),
            patch.object(gate, "_check_runs", return_value=[]),
            patch.object(gate, "_current_main_sha", return_value=_SHA),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_PENDING",
            ):
                gate.wait_for_release_gate(
                    _SHA,
                    environ=environment,
                    wait_seconds=0,
                    poll_seconds=1,
                )


if __name__ == "__main__":
    unittest.main()
