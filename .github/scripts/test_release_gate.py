"""Regress stale, failed, missing and wrongly attributed release evidence."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import pathlib
import re
import unittest
from unittest.mock import Mock, patch

import report_sonar_annotations as diagnostics
import verify_main_release as gate
from report_sonar_annotations import report_annotations

SHA = "a" * 40
PR_HEAD = "b" * 40
TREE = "c" * 40
PR_NUMBER = 765
BRANCH = {"commit": {"sha": SHA}}


def sonar(identifier: int = 10, **changes: object) -> dict:
    return {
        "id": identifier, "head_sha": PR_HEAD,
        "name": "SonarCloud Code Analysis",
        "app": {"id": 12526, "slug": "sonarqubecloud"},
        "details_url": f"https://sonarcloud.io/dashboard?id={gate.SONAR_PROJECT}&pullRequest={PR_NUMBER}",
        "status": "completed", "conclusion": "success",
        "completed_at": "2026-10-08T12:01:00Z",
        "output": {
            "annotations_count": 0,
            "summary": (
                "Issues\n[0 New issues](https://sonarcloud.io/new)\n"
                "[0 Accepted issues](https://sonarcloud.io/accepted)\n"
                "Measures\n[0 Security Hotspots](https://sonarcloud.io/hotspots)"
            ),
        },
        **changes,
    }


def foundation(**changes: object) -> dict:
    return {
        "id": 20, "head_sha": SHA, "head_branch": "main", "event": "push",
        "path": gate.FOUNDATION_PATH, "repository": {"full_name": gate.REPOSITORY},
        "run_attempt": 1, "status": "completed", "conclusion": "success", **changes,
    }


def application(**changes: object) -> dict:
    return foundation(**{"id": 30, "path": gate.APPLICATION_PATH, **changes})


def application_test(**changes: object) -> dict:
    return {
        "id": 40, "run_id": 30, "head_sha": SHA, "head_branch": "main",
        "name": gate.APPLICATION_TEST_JOB, "status": "completed", "conclusion": "success",
        **changes,
    }


def merged_pull(**changes: object) -> dict:
    return {
        "number": PR_NUMBER, "state": "closed", "merged": True,
        "merge_commit_sha": SHA, "merged_at": "2026-10-09T04:00:00Z",
        "base": {"ref": "main", "repo": {"full_name": gate.REPOSITORY}},
        "head": {"sha": PR_HEAD, "repo": {"full_name": gate.REPOSITORY}},
        **changes,
    }


def client_with_evidence(*, final_sonar: dict | None = None) -> Mock:
    client = Mock(spec=gate.GitHubClient)
    client.collect_list.return_value = [{"number": PR_NUMBER, "merge_commit_sha": SHA}]
    checks_read = 0

    def get(path: str) -> dict:
        if path == "/branches/main":
            return copy.deepcopy(BRANCH)
        if path == f"/pulls/{PR_NUMBER}":
            return merged_pull()
        if path in {f"/git/commits/{SHA}", f"/git/commits/{PR_HEAD}"}:
            return {"sha": path.rsplit("/", 1)[-1], "tree": {"sha": TREE}}
        raise AssertionError(f"Unexpected GitHub object request: {path}")

    def collect(path: str, key: str) -> list[dict]:
        nonlocal checks_read
        if path == f"/commits/{PR_HEAD}/check-runs?filter=all":
            checks_read += 1
            return [final_sonar if checks_read > 1 and final_sonar is not None else sonar()]
        if path == f"/actions/workflows/auth-foundation-ci.yml/runs?event=push&head_sha={SHA}":
            return [foundation()]
        if path == f"/actions/workflows/auth-app-deploy.yml/runs?event=push&head_sha={SHA}":
            return [application()]
        if path == f"/actions/workflows/auth-postgres.yml/runs?event=push&head_sha={SHA}":
            return [application(id=50, path=gate.POSTGRES_PATH)]
        if path == "/actions/runs/30/attempts/1/jobs":
            return [application_test()]
        if path == "/actions/runs/50/attempts/1/jobs":
            return [application_test(id=60, run_id=50, name=gate.POSTGRES_TEST_JOB)]
        raise AssertionError(f"Unexpected GitHub collection request: {path}, {key}")

    client.get.side_effect = get
    client.collect.side_effect = collect
    return client


class ReleaseEvidenceTests(unittest.TestCase):
    def test_previous_release_proof_does_not_authorize_new_deployment(self) -> None:
        with patch.dict(BRANCH, {"commit": {"sha": "f" * 40}}):
            gate.verify_accepted_release(client_with_evidence(), SHA)
            previous = client_with_evidence()
            with self.assertRaises(gate.ReleaseBlocked):
                gate.verify(previous, SHA)
            failed = client_with_evidence(final_sonar=sonar(conclusion="failure"))
            with self.assertRaises(gate.ReleaseBlocked):
                gate.verify_accepted_release(failed, SHA)

    def test_current_main_with_all_successful_checks_passes(self) -> None:
        client = client_with_evidence()
        gate.verify(client, SHA)
        self.assertEqual(client.get.call_count, 6)
        self.assertIn("filter=all", client.collect.call_args_list[0].args[0])
        self.assertEqual(client.collect.call_args_list[0], client.collect.call_args_list[-1])
        self.assertEqual(client.collect.call_args_list[3].args,
                         ("/actions/runs/30/attempts/1/jobs", "jobs"))

    def test_sonar_requires_zero_issue_summary_and_annotations(self) -> None:
        dirty_outputs = (
            {"annotations_count": 1, "summary": sonar()["output"]["summary"]},
            {
                "annotations_count": 0,
                "summary": sonar()["output"]["summary"].replace(
                    "[0 New issues]", "[2 New issues]"
                ),
            },
            {
                "annotations_count": 0,
                "summary": sonar()["output"]["summary"].replace(
                    "[0 Accepted issues]", "[1 Accepted issue]"
                ),
            },
            {
                "annotations_count": 0,
                "summary": sonar()["output"]["summary"].replace(
                    "[0 Security Hotspots]", "[1 Security Hotspot]"
                ),
            },
        )
        for output in dirty_outputs:
            check = sonar(output=output)
            with self.subTest(output=output), self.assertRaises(gate.ReleaseBlocked):
                gate.require_sonar([check], PR_HEAD, PR_NUMBER)

    def test_sonar_missing_or_malformed_output_blocks_release(self) -> None:
        malformed = (
            None,
            {},
            {"annotations_count": True, "summary": sonar()["output"]["summary"]},
            {"annotations_count": -1, "summary": sonar()["output"]["summary"]},
            {"annotations_count": 0, "summary": ""},
            {"annotations_count": 0, "summary": "Quality Gate passed"},
            {"annotations_count": 0,
             "summary": sonar()["output"]["summary"] + "\n[1 New issue](https://sonarcloud.io/new)"},
        )
        for output in malformed:
            check = sonar(output=output)
            with self.subTest(output=output), self.assertRaises(gate.ReleaseBlocked):
                gate.require_sonar([check], PR_HEAD, PR_NUMBER)

    def test_another_pr_success_cannot_hide_failed_merged_pr(self) -> None:
        pull_request = sonar(12, details_url=(
            f"https://sonarcloud.io/dashboard?id={gate.SONAR_PROJECT}&pullRequest=660"
        ))
        checks = [sonar(conclusion="failure"), pull_request]
        with self.assertRaises(gate.ReleaseBlocked):
            gate.require_sonar(checks, PR_HEAD, PR_NUMBER)
        with self.assertRaises(gate.PendingChecks):
            gate.require_sonar([pull_request], PR_HEAD, PR_NUMBER)

    def test_latest_merged_pr_attempt_controls_acceptance(self) -> None:
        for conclusion in ("failure", "cancelled", "timed_out", "neutral", "skipped", None):
            checks = [sonar(), sonar(11, conclusion=conclusion)]
            with self.subTest(conclusion=conclusion), self.assertRaises(gate.ReleaseBlocked):
                gate.require_sonar(checks, PR_HEAD, PR_NUMBER)
        gate.require_sonar([sonar(conclusion="failure"), sonar(11)], PR_HEAD, PR_NUMBER)

    def test_pending_or_unclassified_new_analysis_cannot_reuse_old_success(self) -> None:
        for change in ({"status": "in_progress"}, {"details_url": None}):
            checks = [sonar(), sonar(11, **change)]
            with self.subTest(change=change), self.assertRaises(gate.PendingChecks):
                gate.require_sonar(checks, PR_HEAD, PR_NUMBER)

    def test_untrusted_sonar_identity_cannot_pass(self) -> None:
        for change in (
            {"head_sha": "d" * 40}, {"name": "Fake Sonar"},
            {"app": {"id": 1, "slug": "sonarqubecloud"}},
            {"app": {"id": 12526, "slug": "another-app"}}, {"app": None},
        ):
            checks = [sonar(**change)]
            with self.subTest(change=change), self.assertRaises(gate.PendingChecks):
                gate.require_sonar(checks, PR_HEAD, PR_NUMBER)

    def test_ambiguous_project_or_branch_url_cannot_pass(self) -> None:
        valid = sonar()["details_url"]
        for url in (
            valid.replace("https:", "http:"), valid.replace("sonarcloud.io", "example.org"),
            valid.replace(gate.SONAR_PROJECT, "another-project"),
            valid.replace("pullRequest=765", "branch=feature"), valid + "&branch=main",
            valid + "&pullRequest=661", valid + "#fragment", "https://[invalid", 123,
        ):
            checks = [sonar(details_url=url)]
            with self.subTest(url=url), self.assertRaises(gate.PendingChecks):
                gate.require_sonar(checks, PR_HEAD, PR_NUMBER)

    def test_only_exact_push_foundation_workflow_can_certify_release(self) -> None:
        for change in (
            {"event": "pull_request"}, {"event": "workflow_dispatch"},
            {"head_branch": "feature"}, {"head_sha": "b" * 40},
            {"path": ".github/workflows/other.yml"},
            {"repository": {"full_name": "someone/else"}},
        ):
            runs = [foundation(**change)]
            with self.subTest(change=change), self.assertRaises(gate.PendingChecks):
                gate.require_foundation(runs, SHA)

    def test_foundation_failure_and_pending_rerun_block_old_success(self) -> None:
        failed = [foundation(), foundation(id=21, conclusion="failure")]
        pending = [foundation(status="queued", conclusion=None)]
        with self.assertRaises(gate.ReleaseBlocked):
            gate.require_foundation(failed, SHA)
        with self.assertRaises(gate.PendingChecks):
            gate.require_foundation(pending, SHA)

        for conclusion in ("failure", None):
            rerun = foundation(run_attempt=2, conclusion=conclusion,
                               status="completed" if conclusion else "queued")
            error = gate.ReleaseBlocked if conclusion else gate.PendingChecks
            runs = [rerun, foundation()]
            with self.subTest(conclusion=conclusion), self.assertRaises(error):
                gate.require_foundation(runs, SHA)

    def test_main_moving_before_or_during_verification_blocks_release(self) -> None:
        for moves_on_read in (1, 2):
            client = client_with_evidence()
            original = client.get.side_effect
            reads = 0

            def get(path: str, moves_on_read=moves_on_read, original=original) -> dict:
                nonlocal reads
                if path == "/branches/main":
                    reads += 1
                    if reads >= moves_on_read:
                        return {"commit": {"sha": "d" * 40}}
                return original(path)

            client.get.side_effect = get
            with self.subTest(moves_on_read=moves_on_read), self.assertRaises(gate.ReleaseBlocked):
                gate.verify(client, SHA)

    def test_malformed_check_identity_blocks_instead_of_selecting_a_result(self) -> None:
        for identifier in (None, "99", True, -1):
            checks = [sonar(id=identifier)]
            with self.subTest(identifier=identifier), self.assertRaises(gate.ReleaseBlocked):
                gate.require_sonar(checks, PR_HEAD, PR_NUMBER)

    def test_missing_checks_wait_then_success_returns(self) -> None:
        client = client_with_evidence()
        client.deadline = 100
        with patch.object(gate, "verify", side_effect=[gate.PendingChecks("Pending"), None]), \
                patch.object(gate.time, "monotonic", return_value=1), \
                patch.object(gate.time, "sleep") as sleep, \
                contextlib.redirect_stdout(io.StringIO()):
            gate.wait_for_release(client, SHA)
            sleep.assert_called_once_with(15)

    def test_missing_checks_have_bounded_wait_and_failure_is_not_retried(self) -> None:
        client = client_with_evidence()
        client.deadline = 1
        for error in (gate.PendingChecks("Pending"), gate.ReleaseBlocked("Failed")):
            with self.subTest(error=type(error)), \
                    patch.object(gate, "verify", side_effect=error), \
                    patch.object(gate.time, "monotonic", return_value=2), \
                    patch.object(gate.time, "sleep") as sleep, \
                    self.assertRaises(gate.ReleaseBlocked):
                gate.wait_for_release(client, SHA)
            sleep.assert_not_called()


class MergedPullRequestEvidenceTests(unittest.TestCase):
    def test_squash_commit_uses_the_exact_merged_pr_head_analysis(self) -> None:
        client = client_with_evidence()
        gate.verify(client, SHA)
        client.collect_list.assert_called_once_with(f"/commits/{SHA}/pulls")
        check_paths = [call.args[0] for call in client.collect.call_args_list
                       if call.args[1] == "check_runs"]
        self.assertEqual(check_paths, [f"/commits/{PR_HEAD}/check-runs?filter=all"] * 2)
        self.assertIn(f"/git/commits/{SHA}", [call.args[0] for call in client.get.call_args_list])
        self.assertIn(f"/git/commits/{PR_HEAD}",
                      [call.args[0] for call in client.get.call_args_list])

    def test_failed_main_sonar_does_not_override_successful_exact_pr_sonar(self) -> None:
        main = sonar(99, conclusion="cancelled", details_url=(
            f"https://sonarcloud.io/dashboard?id={gate.SONAR_PROJECT}&branch=main"
        ))
        self.assertEqual(gate.require_sonar([main, sonar()], PR_HEAD, PR_NUMBER)[0], 10)
        with self.assertRaises(gate.PendingChecks):
            gate.require_sonar([main], PR_HEAD, PR_NUMBER)

    def test_direct_push_or_another_merge_cannot_borrow_a_pr_result(self) -> None:
        for rows in ([], [{"number": PR_NUMBER, "merge_commit_sha": "d" * 40}]):
            client = client_with_evidence()
            client.collect_list.return_value = rows
            with self.subTest(rows=rows), self.assertRaises(gate.PendingChecks):
                gate.verify(client, SHA)
            client.collect.assert_not_called()

    def test_ambiguous_or_malformed_pr_association_blocks(self) -> None:
        for rows in (
            [{"number": PR_NUMBER, "merge_commit_sha": SHA}] * 2,
            [{"number": True, "merge_commit_sha": SHA}],
            [{"number": "765", "merge_commit_sha": SHA}],
            [{"number": -1, "merge_commit_sha": SHA}],
        ):
            client = client_with_evidence()
            client.collect_list.return_value = rows
            with self.subTest(rows=rows), self.assertRaises(gate.ReleaseBlocked):
                gate.verify(client, SHA)

    def test_only_closed_merged_same_repository_main_pr_is_accepted(self) -> None:
        for changes in (
            {"merged": False}, {"merged": 1}, {"state": "open"},
            {"number": PR_NUMBER + 1}, {"merge_commit_sha": "d" * 40},
            {"merged_at": None}, {"head": None}, {"base": {}},
            {"base": {"ref": "other", "repo": {"full_name": gate.REPOSITORY}}},
            {"head": {"sha": PR_HEAD, "repo": {"full_name": "untrusted/fork"}}},
            {"head": {"sha": "not-a-commit", "repo": {"full_name": gate.REPOSITORY}}},
        ):
            client = client_with_evidence()
            original = client.get.side_effect
            client.get.side_effect = lambda path, changes=changes, original=original: (
                merged_pull(**changes) if path == f"/pulls/{PR_NUMBER}" else original(path)
            )
            with self.subTest(changes=changes), self.assertRaises(gate.ReleaseBlocked):
                gate.verify(client, SHA)
            client.collect.assert_not_called()

    def test_unanalysed_merge_tree_changes_block_even_with_green_pr(self) -> None:
        client = client_with_evidence()
        original = client.get.side_effect
        client.get.side_effect = lambda path: (
            {"sha": SHA, "tree": {"sha": "d" * 40}}
            if path == f"/git/commits/{SHA}" else original(path)
        )
        with self.assertRaisesRegex(gate.ReleaseBlocked, "main tree differs.*PR head tree"):
            gate.verify(client, SHA)
        client.collect.assert_not_called()

    def test_missing_or_misattributed_tree_fails_closed(self) -> None:
        for commit in (
            {"sha": PR_HEAD, "tree": {"sha": TREE}}, {"sha": SHA},
            {"sha": SHA, "tree": {"sha": "invalid"}},
        ):
            client = client_with_evidence()
            original = client.get.side_effect
            client.get.side_effect = lambda path, commit=commit, original=original: (
                commit if path == f"/git/commits/{SHA}" else original(path)
            )
            with self.subTest(commit=commit), self.assertRaises(gate.ReleaseBlocked):
                gate.verify(client, SHA)

    def test_changed_pr_head_cannot_reuse_older_green_sha(self) -> None:
        client = client_with_evidence()
        original = client.collect.side_effect
        client.collect.side_effect = lambda path, key: (
            [sonar(head_sha="d" * 40)] if key == "check_runs" else original(path, key)
        )
        with self.assertRaises(gate.PendingChecks):
            gate.verify(client, SHA)

    def test_pr_head_changing_during_verification_blocks(self) -> None:
        client = client_with_evidence()
        original = client.get.side_effect
        reads = 0

        def get(path: str) -> dict:
            nonlocal reads
            if path == f"/pulls/{PR_NUMBER}":
                reads += 1
                if reads > 1:
                    return merged_pull(head={"sha": "d" * 40,
                                             "repo": {"full_name": gate.REPOSITORY}})
            return original(path)

        client.get.side_effect = get
        with self.assertRaisesRegex(gate.PendingChecks, "PR head changed"):
            gate.verify(client, SHA)

    def test_new_failed_pending_or_replaced_pr_analysis_blocks(self) -> None:
        for check, error in (
            (sonar(11, status="queued", conclusion=None), gate.PendingChecks),
            (sonar(11, conclusion="failure"), gate.ReleaseBlocked),
            (sonar(11, conclusion="cancelled"), gate.ReleaseBlocked),
            (sonar(11), gate.PendingChecks),
            (sonar(completed_at="2026-10-09T05:00:00Z"), gate.PendingChecks),
        ):
            client = client_with_evidence(final_sonar=check)
            with self.subTest(check=check), self.assertRaises(error):
                gate.verify(client, SHA)

    def test_foundation_rerun_after_initial_green_cannot_pass(self) -> None:
        for conclusion in ("failure", None, "success"):
            client = client_with_evidence()
            original = client.collect.side_effect
            reads = 0

            def collect(path: str, key: str, conclusion=conclusion,
                        original=original) -> list[dict]:
                nonlocal reads
                if "auth-foundation-ci.yml/runs" in path:
                    reads += 1
                    if reads > 1:
                        return [foundation(run_attempt=2, conclusion=conclusion,
                                           status="completed" if conclusion else "queued")]
                return original(path, key)

            client.collect.side_effect = collect
            error = gate.ReleaseBlocked if conclusion == "failure" else gate.PendingChecks
            with self.subTest(conclusion=conclusion), self.assertRaises(error):
                gate.verify(client, SHA)

    def test_postgres_job_must_pass_without_waiting_for_its_own_deployment(self) -> None:
        for conclusion in ("success", "failure", "cancelled", None):
            client = client_with_evidence()
            original = client.collect.side_effect

            def collect(path: str, key: str, conclusion=conclusion,
                        original=original) -> list[dict]:
                if "auth-postgres.yml/runs" in path:
                    return [application(id=50, path=gate.POSTGRES_PATH,
                                        status="in_progress", conclusion=None)]
                if path == "/actions/runs/50/attempts/1/jobs":
                    return [application_test(id=60, run_id=50, name=gate.POSTGRES_TEST_JOB,
                                             conclusion=conclusion,
                                             status="completed" if conclusion else "queued")]
                return original(path, key)

            client.collect.side_effect = collect
            with self.subTest(conclusion=conclusion):
                if conclusion == "success":
                    gate.verify(client, SHA)
                else:
                    error = gate.PendingChecks if conclusion is None else gate.ReleaseBlocked
                    with self.assertRaises(error):
                        gate.verify(client, SHA)

    def test_postgres_or_application_jobs_changing_after_initial_green_block(self) -> None:
        for run in (30, 50):
            client = client_with_evidence()
            original = client.collect.side_effect
            reads = 0

            def collect(path: str, key: str, run=run, original=original) -> list[dict]:
                nonlocal reads
                rows = original(path, key)
                if path == f"/actions/runs/{run}/attempts/1/jobs":
                    reads += 1
                    if reads > 1:
                        rows[0]["conclusion"] = "failure"
                return rows

            client.collect.side_effect = collect
            with self.subTest(run=run), self.assertRaises(gate.ReleaseBlocked):
                gate.verify(client, SHA)


class ApplicationPushEvidenceTests(unittest.TestCase):
    def test_downstream_success_cannot_hide_exact_push_test_failure(self) -> None:
        push = application(id=37499453831, conclusion="failure")
        downstream = application(id=37500030438, event="workflow_run")
        client = Mock(spec=gate.GitHubClient)
        client.collect.side_effect = [
            [push, downstream],
            [application_test(run_id=push["id"], conclusion="failure")],
        ]
        with self.assertRaises(gate.ReleaseBlocked):
            gate.require_application_tests(client, SHA)
        self.assertEqual(client.collect.call_args.args,
                         ("/actions/runs/37499453831/attempts/1/jobs", "jobs"))

    def test_only_the_exact_main_push_can_supply_application_tests(self) -> None:
        for change in (
            {"event": "workflow_run"}, {"event": "workflow_dispatch"},
            {"event": "pull_request"}, {"head_sha": "b" * 40},
            {"head_branch": "feature"}, {"repository": {"full_name": "someone/else"}},
            {"path": gate.FOUNDATION_PATH},
        ):
            client = Mock(spec=gate.GitHubClient)
            client.collect.return_value = [application(**change)]
            with self.subTest(change=change), self.assertRaises(gate.PendingChecks):
                gate.require_application_tests(client, SHA)
            self.assertEqual(client.collect.call_count, 1)

    def test_latest_same_run_attempt_prevents_reusing_previous_green_jobs(self) -> None:
        client = Mock(spec=gate.GitHubClient)
        client.collect.side_effect = [
            [application(run_attempt=2, conclusion="failure"), application()],
            [application_test(conclusion="failure", run_attempt=2)],
        ]
        with self.assertRaises(gate.ReleaseBlocked):
            gate.require_application_tests(client, SHA)
        self.assertEqual(client.collect.call_args.args,
                         ("/actions/runs/30/attempts/2/jobs", "jobs"))

    def test_latest_push_run_controls_even_when_an_older_run_has_more_attempts(self) -> None:
        client = Mock(spec=gate.GitHubClient)
        client.collect.side_effect = [
            [application(run_attempt=9), application(id=31, conclusion="failure")],
            [application_test(run_id=31, conclusion="failure")],
        ]
        with self.assertRaises(gate.ReleaseBlocked):
            gate.require_application_tests(client, SHA)
        self.assertEqual(client.collect.call_args.args,
                         ("/actions/runs/31/attempts/1/jobs", "jobs"))

    def test_tests_must_succeed_and_other_workflow_jobs_are_not_a_dependency(self) -> None:
        for state, conclusion in (("in_progress", None), ("completed", "failure")):
            push = application(status=state, conclusion=conclusion)
            client = Mock(spec=gate.GitHubClient)
            client.collect.side_effect = [[push], [application_test()], [push]]
            with self.subTest(state=state):
                gate.require_application_tests(client, SHA)

    def test_every_non_successful_terminal_test_outcome_blocks(self) -> None:
        for conclusion in ("failure", "cancelled", "timed_out", "skipped", "neutral", None):
            client = Mock(spec=gate.GitHubClient)
            client.collect.side_effect = [
                [application()], [application_test(conclusion=conclusion)],
            ]
            with self.subTest(conclusion=conclusion), self.assertRaises(gate.ReleaseBlocked):
                gate.require_application_tests(client, SHA)

    def test_pending_tests_or_missing_pending_jobs_wait_without_old_evidence(self) -> None:
        for jobs in ([], [application_test(status="in_progress", conclusion=None)]):
            client = Mock(spec=gate.GitHubClient)
            client.collect.side_effect = [[application(status="in_progress")], jobs]
            with self.subTest(jobs=jobs), self.assertRaises(gate.PendingChecks):
                gate.require_application_tests(client, SHA)

    def test_missing_misattributed_and_ambiguous_jobs_cannot_certify_tests(self) -> None:
        invalid = (
            [], [application_test(name="Deploy auth application")],
            [application_test(run_id=31)], [application_test(head_sha="b" * 40)],
            [application_test(head_branch="feature")], [application_test(run_attempt=2)],
            [application_test(id=True)], [application_test(), application_test(id=41)],
        )
        for jobs in invalid:
            client = Mock(spec=gate.GitHubClient)
            client.collect.side_effect = [[application()], jobs]
            with self.subTest(jobs=jobs), self.assertRaises(gate.ReleaseBlocked):
                gate.require_application_tests(client, SHA)

    def test_malformed_attempt_cannot_be_used_in_an_api_path(self) -> None:
        for attempt in (None, 0, -1, True, "2"):
            client = Mock(spec=gate.GitHubClient)
            client.collect.return_value = [application(run_attempt=attempt)]
            with self.subTest(attempt=attempt), self.assertRaises(gate.ReleaseBlocked):
                gate.require_application_tests(client, SHA)
            self.assertEqual(client.collect.call_count, 1)

    def test_attempt_changing_during_job_verification_requires_fresh_evidence(self) -> None:
        for current in (application(run_attempt=2), application(id=31)):
            client = Mock(spec=gate.GitHubClient)
            client.collect.side_effect = [[application()], [application_test()], [current]]
            with self.subTest(current=current), self.assertRaises(gate.PendingChecks):
                gate.require_application_tests(client, SHA)


class SelfHostedCiPolicyTests(unittest.TestCase):
    def test_sonar_diagnostics_cannot_block_main_on_provider_quota(self) -> None:
        workflow_dir = pathlib.Path(__file__).resolve().parent.parent / "workflows"
        conditions = {
            "auth-foundation-ci.yml": "matrix.name == 'Release gate tests'",
            "auth-app-deploy.yml": (
                "always() && steps.checkout.outcome == 'success' "
                "&& steps.python.outcome == 'success'"
            ),
        }
        for name, condition in conditions.items():
            workflow = (workflow_dir / name).read_text(encoding="utf-8")
            diagnostic_steps = [
                block for block in workflow.split("\n      - name: ")[1:]
                if "run:" in block and "report_sonar_annotations.py'" in block
            ]
            with self.subTest(workflow=name):
                self.assertEqual(len(diagnostic_steps), 1)
                step = diagnostic_steps[0]
                self.assertIn(
                    "        if: github.event_name == 'pull_request' && " + condition + "\n",
                    step,
                )
                self.assertIn("SOURCE_SHA: ${{ github.event.pull_request.head.sha }}", step)

    def test_workflow_environment_and_permission_blocks_are_not_empty(self) -> None:
        workflow_dir = pathlib.Path(__file__).resolve().parent.parent / "workflows"
        for path in workflow_dir.glob("*.yml"):
            lines = [line for line in path.read_text(encoding="utf-8").splitlines()
                     if line.strip() and not line.lstrip().startswith("#")]
            for index, line in enumerate(lines):
                mapping = re.fullmatch(r"( *)(env|permissions):", line)
                if mapping is None:
                    continue
                following = lines[index + 1] if index + 1 < len(lines) else ""
                with self.subTest(workflow=path.name, line=line):
                    self.assertGreater(
                        len(following) - len(following.lstrip()), len(mapping[1]),
                        "An empty workflow mapping is null, not an accepted Actions configuration",
                    )

    def test_infrastructure_pr_queues_are_isolated_from_production(self) -> None:
        workflow_dir = pathlib.Path(__file__).resolve().parent.parent / "workflows"
        for name in ("auth-postgres", "auth-private-network"):
            fallback = "github.run_id" if name == "auth-postgres" else "'production'"
            workflow = (workflow_dir / f"{name}.yml").read_text(encoding="utf-8")
            header, jobs = workflow.split("\njobs:\n", 1)
            concurrency = "\n".join(
                line for line in header.split("\nconcurrency:\n", 1)[1].splitlines()
                if not line.lstrip().startswith("#")
            ).strip()
            reconcile = jobs.split("\n  reconcile:\n", 1)[1].split(
                "\n  isolated-restore:\n", 1,
            )[0]
            with self.subTest(workflow=name):
                self.assertEqual(
                    concurrency,
                    f"group: {name}-"
                    "${{ github.event.pull_request.number || " + fallback + " }}\n"
                    "  cancel-in-progress: false",
                )
                self.assertIn(
                    "    concurrency:\n"
                    "      group: omnicio-production-ssh\n"
                    "      cancel-in-progress: false\n"
                    "      queue: max\n",
                    reconcile,
                )
                self.assertIn(
                    "github.event_name != 'pull_request' && github.ref == 'refs/heads/main'",
                    reconcile,
                )
                self.assertIn("    needs: tests\n", reconcile)
                self.assertIn("- name: Verify current main release checks\n", reconcile)

    def test_host_restore_uses_shared_gate_and_keeps_data_on_server(self) -> None:
        workflow = (
            pathlib.Path(__file__).resolve().parent.parent / "workflows" / "auth-postgres.yml"
        ).read_text(encoding="utf-8")
        restore = workflow.split("\n  isolated-restore:\n", 1)[1]
        self.assertIn("OMNICIO_RESTORE_DRILL_ALLOWED: \"true\"", restore)
        self.assertIn("github.event_name == 'workflow_dispatch'", restore)
        self.assertIn("github.ref == 'refs/heads/main' && inputs.restore_drill", restore)
        self.assertIn("run_recovery_drill.py --on-host", restore)
        self.assertNotIn("upload-artifact", restore)
        self.assertNotIn("OMNICIO_RESTORE_SOURCE_DSN", restore)
        self.assertIn("pull-requests: read", restore)
        self.assertNotIn("SONAR_TOKEN", workflow)

    def test_application_gate_targets_the_existing_tests_job_only(self) -> None:
        workflow = (pathlib.Path(__file__).resolve().parents[2] / gate.APPLICATION_PATH).read_text(
            encoding="utf-8",
        )
        tests = workflow.split("\n  tests:\n", 1)[1].split("\n  deploy:\n", 1)[0]
        self.assertIn("    name: " + gate.APPLICATION_TEST_JOB + "\n", tests)
        self.assertIn("    needs: tests\n", workflow)
        self.assertNotIn("    needs: deploy\n", tests)

    def test_owner_same_repo_prs_use_the_four_runner_pool(self) -> None:
        workflow = (
            pathlib.Path(__file__).resolve().parent.parent
            / "workflows"
            / "auth-foundation-ci.yml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository",
            workflow,
        )
        self.assertIn(
            "github.event.pull_request.author_association == 'OWNER'",
            workflow,
        )
        self.assertIn(
            "runs-on: [self-hosted, Windows, X64, omni-cio-ci]",
            workflow,
        )
        self.assertIn("max-parallel: 4", workflow)
        self.assertIn("Full tests (includes security)", workflow)
        self.assertIn(
            'command: \'"%OMNICIO_PYTHON%" .github/scripts/test_with_postgres.py\'',
            workflow,
        )
        self.assertNotIn("name: Security tests", workflow)
        self.assertIn(
            "github.event_name == 'push' && github.ref == 'refs/heads/main'",
            workflow,
        )

    def test_pull_request_workflows_are_owner_only_on_self_hosted(self) -> None:
        workflow_dir = pathlib.Path(__file__).resolve().parent.parent / "workflows"
        for workflow_path in workflow_dir.glob("*.yml"):
            content = workflow_path.read_text(encoding="utf-8")
            if "pull_request:" not in content:
                continue
            with self.subTest(workflow=workflow_path.name):
                self.assertIn(
                    "github.event.pull_request.head.repo.full_name == github.repository",
                    content,
                )
                self.assertIn(
                    "github.event.pull_request.author_association == 'OWNER'",
                    content,
                )

    def test_repository_workflows_do_not_depend_on_billed_hosted_runners(self) -> None:
        workflow_dir = pathlib.Path(__file__).resolve().parent.parent / "workflows"
        forbidden = ("runs-on: ubuntu-", "runs-on: windows-", "runs-on: macos-")
        for workflow_path in workflow_dir.glob("*.yml"):
            content = workflow_path.read_text(encoding="utf-8")
            with self.subTest(workflow=workflow_path.name):
                for marker in forbidden:
                    self.assertNotIn(marker, content)
                self.assertNotIn("services:", content)



class SonarScopePolicyTests(unittest.TestCase):
    def test_postgresql_migrations_only_are_excluded_from_incompatible_plsql_analysis(self) -> None:
        config = (
            pathlib.Path(__file__).resolve().parents[2]
            / ".sonarcloud.properties"
        ).read_text(encoding="utf-8")

        properties = {}
        for line in config.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            self.assertNotIn(key, properties, "Duplicate Sonar property")
            properties[key] = value

        # Exact scope prevents broad exclusions, hidden rule/coverage suppressions,
        # or classifying application/deployment sources as test code to fit a quota.
        self.assertEqual(properties, {
            "sonar.exclusions": "migrations/*.sql",
            "sonar.sources": ".",
            "sonar.tests": "tests,.github/scripts",
            "sonar.test.inclusions": "tests/**,.github/scripts/test_*.py",
        })


class GitHubTransportTests(unittest.TestCase):
    def test_pr_provenance_pagination_reaches_the_actual_merged_pr(self) -> None:
        client = gate.GitHubClient("synthetic-test-token", deadline=100)
        first = [{"number": 1, "merge_commit_sha": "d" * 40}] * 100
        accepted = {"number": PR_NUMBER, "merge_commit_sha": SHA}
        with patch.object(client, "get_list", side_effect=[first, [accepted]]) as get:
            rows = client.collect_list(f"/commits/{SHA}/pulls")
        self.assertEqual(rows[-1], accepted)
        self.assertEqual(get.call_args.args[0], f"/commits/{SHA}/pulls?per_page=100&page=2")

    def test_pr_provenance_pagination_is_bounded(self) -> None:
        client = gate.GitHubClient("synthetic-test-token", deadline=100)
        with patch.object(client, "get_list", return_value=[{}] * 100) as get, \
                self.assertRaises(gate.ReleaseBlocked):
            client.collect_list(f"/commits/{SHA}/pulls")
        self.assertEqual(get.call_count, 10)

    def test_attempt_jobs_pagination_adds_the_first_query_separator(self) -> None:
        client = gate.GitHubClient("synthetic-test-token", deadline=100)
        with patch.object(client, "get", return_value={"jobs": [application_test()]}) as get:
            self.assertEqual(client.collect("/actions/runs/30/attempts/1/jobs", "jobs"),
                             [application_test()])
        get.assert_called_once_with("/actions/runs/30/attempts/1/jobs?per_page=100&page=1")

    def test_sonar_annotation_transport_retry_is_bounded_and_fail_closed(self) -> None:
        for error, recover in (
            (gate.PendingChecks("temporary annotation timeout"), True),
            (gate.PendingChecks("temporary annotation timeout"), False),
            (gate.ReleaseBlocked("permission denied"), False),
        ):
            with (
                self.subTest(error=type(error), recover=recover),
                patch.dict(os.environ, {"SOURCE_SHA": SHA, "GH_TOKEN": "synthetic-test-token"}),
                patch.object(diagnostics, "GitHubClient"),
                patch.object(diagnostics, "completed_sonar", return_value=sonar()),
                patch.object(
                    diagnostics, "report_annotations", side_effect=[error, None],
                ) as report,
                patch.object(
                    diagnostics.time, "monotonic", side_effect=[0, 1, 2 if recover else 241],
                ),
                patch.object(diagnostics.time, "sleep") as sleep,
            ):
                if recover:
                    diagnostics.main()
                    self.assertEqual(report.call_count, 2)
                    sleep.assert_called_once_with(10)
                else:
                    with self.assertRaises(gate.ReleaseBlocked):
                        diagnostics.main()
                    self.assertEqual(report.call_count, 1)
                    if isinstance(error, gate.ReleaseBlocked):
                        sleep.assert_not_called()

    def test_sonar_summary_and_annotations_survive_windows_console_encoding(self) -> None:
        client = Mock(spec=gate.GitHubClient)
        client.get_list.return_value = [{"message": "Исправить ≤ 3%"}]
        summary = "3.4% duplication (required ≤ 3%)"
        buffer = io.BytesIO()
        with io.TextIOWrapper(buffer, encoding="ascii", write_through=True) as output:
            with contextlib.redirect_stdout(output):
                report_annotations(client, sonar(output={"summary": summary}))
            rows = buffer.getvalue().decode("ascii").splitlines()
        self.assertEqual(json.loads(rows[0]), summary)
        self.assertEqual(json.loads(rows[1])["message"], "Исправить ≤ 3%")
        client.get_list.assert_called_once_with("/check-runs/10/annotations?per_page=100&page=1")

    def test_annotation_reader_rejects_malformed_lists(self) -> None:
        client = gate.GitHubClient("synthetic-test-token", deadline=100)
        for data in ({}, ["invalid"], None):
            with patch.object(client, "_request", return_value=data), \
                    self.subTest(data=data), self.assertRaises(gate.ReleaseBlocked):
                client.get_list("/check-runs/1/annotations")
        with patch.object(client, "_request", return_value=[{"path": "web/app.js"}]):
            self.assertEqual(client.get_list("/check-runs/1/annotations"), [{"path": "web/app.js"}])

    def test_uses_fixed_https_host_get_and_closes_connection(self) -> None:
        response = Mock(status=200)
        response.read.return_value = json.dumps(BRANCH).encode()
        connection = Mock()
        connection.getresponse.return_value = response
        with patch.object(gate.http.client, "HTTPSConnection", return_value=connection) as https, \
                patch.object(gate.time, "monotonic", return_value=0):
            client = gate.GitHubClient("synthetic-test-token", deadline=100)
            self.assertEqual(client.get("/branches/main"), BRANCH)
        https.assert_called_once_with("api.github.com", timeout=15)
        self.assertEqual(connection.request.call_args.args, (
            "GET", f"/repos/{gate.REPOSITORY}/branches/main",
        ))
        connection.close.assert_called_once()

    def test_redirect_auth_failure_and_invalid_data_fail_closed(self) -> None:
        for status, body in (
            (302, b"redirect"), (401, b"unauthorized"), (403, b"forbidden"),
            (404, b"missing"), (200, b"invalid json"),
            (200, b"[]"), (200, b"x" * (gate.MAX_RESPONSE_BYTES + 1)),
        ):
            response = Mock(status=status)
            response.read.return_value = body
            connection = Mock()
            connection.getresponse.return_value = response
            client = gate.GitHubClient("synthetic-test-token", deadline=100)
            with self.subTest(status=status, size=len(body)), \
                    patch.object(gate.http.client, "HTTPSConnection", return_value=connection), \
                    patch.object(gate.time, "monotonic", return_value=0), \
                    self.assertRaises(gate.ReleaseBlocked):
                client.get("/branches/main")

    def test_transient_github_failures_are_retryable_but_bounded(self) -> None:
        for status in (408, 429, 500, 502, 503, 599):
            response = Mock(status=status)
            response.read.return_value = b"temporary"
            connection = Mock()
            connection.getresponse.return_value = response
            client = gate.GitHubClient("synthetic-test-token", deadline=100)
            with self.subTest(status=status), \
                    patch.object(gate.http.client, "HTTPSConnection", return_value=connection), \
                    patch.object(gate.time, "monotonic", return_value=0), \
                    self.assertRaises(gate.PendingChecks):
                client.get("/branches/main")

        client = gate.GitHubClient("synthetic-test-token", deadline=100)
        with patch.object(
            gate.http.client,
            "HTTPSConnection",
            side_effect=OSError("temporary network failure"),
        ), patch.object(gate.time, "monotonic", return_value=0), \
                self.assertRaises(gate.PendingChecks):
            client.get("/branches/main")

    def test_pagination_reaches_main_failure_after_a_full_first_page(self) -> None:
        client = gate.GitHubClient("synthetic-test-token", deadline=100)
        with patch.object(client, "get", side_effect=[
            {"check_runs": [sonar(details_url=None)] * 100},
            {"check_runs": [sonar(999, conclusion="failure")]},
        ]) as get:
            rows = client.collect("/commits/example/check-runs?filter=all", "check_runs")
        self.assertIn("page=2", get.call_args.args[0])
        with self.assertRaises(gate.ReleaseBlocked):
            gate.require_sonar(rows, PR_HEAD, PR_NUMBER)

    def test_malformed_lists_and_pagination_overflow_block(self) -> None:
        client = gate.GitHubClient("synthetic-test-token", deadline=100)
        for response in ({}, {"check_runs": None}, {"check_runs": ["bad"]}):
            with patch.object(client, "get", return_value=response), \
                    self.subTest(response=response), self.assertRaises(gate.ReleaseBlocked):
                client.collect("/checks?filter=all", "check_runs")
        with patch.object(client, "get", return_value={"check_runs": [sonar()] * 100}) as get, \
                self.assertRaises(gate.ReleaseBlocked):
            client.collect("/checks?filter=all", "check_runs")
        self.assertEqual(get.call_count, 10)

    def test_expired_deadline_never_opens_a_connection(self) -> None:
        client = gate.GitHubClient("synthetic-test-token", deadline=1)
        with patch.object(gate.time, "monotonic", return_value=2), \
                patch.object(gate.http.client, "HTTPSConnection") as https, \
                self.assertRaises(gate.ReleaseBlocked):
            client.get("/branches/main")
        https.assert_not_called()


class ReleaseContextTests(unittest.TestCase):
    def test_shared_entrypoint_only_needs_github_and_a_bounded_deadline(self) -> None:
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(gate.time, "monotonic", return_value=100), \
                patch.object(gate, "GitHubClient") as github, \
                patch.object(gate, "wait_for_release") as wait:
            gate.wait_for_main_release(SHA, "synthetic-github-token", timeout=600)
        github.assert_called_once_with("synthetic-github-token", deadline=700)
        wait.assert_called_once_with(github.return_value, SHA)

    def test_cli_needs_no_sonar_api_or_credential(self) -> None:
        valid = {
            "GITHUB_REPOSITORY": gate.REPOSITORY, "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "push", "GITHUB_SHA": SHA,
            "GITHUB_TOKEN": "synthetic-github-token",
        }
        with patch.dict(os.environ, valid, clear=True), \
                patch.object(gate, "require_checkout"), \
                patch.object(gate, "GitHubClient") as github, \
                patch.object(gate, "wait_for_release") as wait, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main(), 0)
        self.assertEqual(github.call_args.args, ("synthetic-github-token",))
        wait.assert_called_once_with(github.return_value, SHA)

    def test_release_gate_uses_a_trusted_git_executable(self) -> None:
        executable = pathlib.Path(gate.git_executable())
        self.assertTrue(executable.is_file())
        self.assertEqual(executable.name.casefold(), "git.exe" if os.name == "nt" else "git")

    def test_checkout_must_match_release_identity(self) -> None:
        for actual in (SHA, "b" * 40):
            result = Mock(stdout=actual + "\n")
            with patch.object(gate.subprocess, "run", return_value=result), \
                    self.subTest(sha=actual):
                if actual == SHA:
                    gate.require_checkout(SHA)
                else:
                    with self.assertRaises(gate.ReleaseBlocked):
                        gate.require_checkout(SHA)

    def test_checkout_verification_error_fails_closed(self) -> None:
        with patch.object(gate.subprocess, "run", side_effect=OSError), \
                self.assertRaises(gate.ReleaseBlocked):
            gate.require_checkout(SHA)

    def test_wrong_context_stops_before_any_api_call(self) -> None:
        valid = {
            "GITHUB_REPOSITORY": gate.REPOSITORY, "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "push", "GITHUB_SHA": SHA,
            "GITHUB_TOKEN": "synthetic-test-token",
        }
        for changes in (
            {"GITHUB_REPOSITORY": "someone/else"}, {"GITHUB_REF": "refs/pull/1/merge"},
            {"GITHUB_EVENT_NAME": "pull_request"}, {"GITHUB_SHA": "not-a-commit"},
            {"GITHUB_TOKEN": ""},
        ):
            output = io.StringIO()
            with self.subTest(changes=changes), \
                    patch.dict(os.environ, valid | changes, clear=True), \
                    patch.object(gate, "GitHubClient") as api, contextlib.redirect_stderr(output):
                self.assertEqual(gate.main(), 1)
            api.assert_not_called()
            self.assertNotIn("synthetic-test-token", output.getvalue())
        with patch.dict(os.environ, valid, clear=True):
            self.assertEqual(gate.release_context(), (SHA, "synthetic-test-token"))


if __name__ == "__main__":
    unittest.main()
