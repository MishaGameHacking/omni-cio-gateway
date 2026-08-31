from __future__ import annotations

import unittest
from unittest.mock import patch

import scripts.check_v10_cloudflare_postmerge_release_gate as gate


_SHA = "a" * 40
_REQUIRED = frozenset({"Regression Shield", "V10 Engineering Governance"})


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
        rows = [_run("Regression Shield"), _run("V10 Engineering Governance")]
        rows.extend(_run(f"workflow-{index}") for index in range(9))
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
