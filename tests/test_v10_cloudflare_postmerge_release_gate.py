from __future__ import annotations

import unittest
from unittest.mock import patch

import scripts.check_v10_cloudflare_postmerge_release_gate as gate


_SHA = "a" * 40
_REQUIRED = frozenset({"Regression Shield", "V10 Engineering Governance"})


def _run(
    name: str,
    *,
    status: str = "completed",
    conclusion: str | None = "success",
    attempt: int = 1,
    run_id: int = 1,
):
    return {
        "name": name,
        "head_sha": _SHA,
        "head_branch": "main",
        "event": "push",
        "status": status,
        "conclusion": conclusion,
        "run_attempt": attempt,
        "id": run_id,
    }


def _eleven_successful_runs():
    rows = [
        _run("Regression Shield", run_id=1),
        _run("V10 Engineering Governance", run_id=2),
    ]
    rows.extend(_run(f"workflow-{index}", run_id=10 + index) for index in range(9))
    return rows


class CloudflarePostMergeReleaseGateTests(unittest.TestCase):
    def test_gate_requires_core_and_success_only_for_all_observed_latest_runs(
        self,
    ) -> None:
        rows = _eleven_successful_runs()
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
            _run(
                "V10 Engineering Governance",
                status="in_progress",
                conclusion=None,
            ),
        ]
        ready, observed = gate._gate_state(rows, _REQUIRED, 11)
        self.assertFalse(ready)
        self.assertEqual(observed, 2)

    def test_completed_without_conclusion_is_pending_until_materialized(self) -> None:
        rows = _eleven_successful_runs()
        rows[-1]["conclusion"] = None

        ready, observed = gate._gate_state(rows, _REQUIRED, 11)
        self.assertFalse(ready)
        self.assertEqual(observed, 11)

        rows[-1]["conclusion"] = "success"
        ready, observed = gate._gate_state(rows, _REQUIRED, 11)
        self.assertTrue(ready)
        self.assertEqual(observed, 11)

    def test_completed_without_conclusion_times_out_as_pending(self) -> None:
        rows = _eleven_successful_runs()
        rows[-1]["conclusion"] = None
        environment = {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "token"}

        with (
            patch.object(gate, "_contract", return_value=(_REQUIRED, 11)),
            patch.object(gate, "_current_main_sha", return_value=_SHA),
            patch.object(gate, "_workflow_runs", return_value=rows),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_PUSH_WORKFLOWS_PENDING",
            ):
                gate.wait_for_release_gate(
                    _SHA,
                    environ=environment,
                    wait_seconds=0,
                    poll_seconds=1,
                )

    def test_malformed_status_or_completed_conclusion_fails_closed(self) -> None:
        rows = _eleven_successful_runs()
        rows[-1]["status"] = None
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_RUN_INVALID",
        ):
            gate._gate_state(rows, _REQUIRED, 11)

        rows = _eleven_successful_runs()
        rows[-1]["conclusion"] = 7
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_POSTMERGE_RUN_INVALID",
        ):
            gate._gate_state(rows, _REQUIRED, 11)

    def test_workflow_runs_paginates_complete_exact_sha_evidence(self) -> None:
        first_page = [_run(f"workflow-{index}", run_id=index + 1) for index in range(100)]
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

    def test_workflow_runs_fail_closed_if_snapshot_changes_between_pages(self) -> None:
        first_page = [_run(f"workflow-{index}", run_id=index + 1) for index in range(100)]
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

    def test_wait_rejects_superseded_main_before_observing_workflows(self) -> None:
        environment = {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "token"}
        with (
            patch.object(gate, "_contract", return_value=(_REQUIRED, 11)),
            patch.object(gate, "_current_main_sha", return_value="b" * 40),
            patch.object(gate, "_workflow_runs") as workflow_runs,
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

    def test_wait_rechecks_main_after_all_workflows_are_green(self) -> None:
        rows = _eleven_successful_runs()
        environment = {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "token"}
        with (
            patch.object(gate, "_contract", return_value=(_REQUIRED, 11)),
            patch.object(gate, "_workflow_runs", return_value=rows),
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


if __name__ == "__main__":
    unittest.main()
