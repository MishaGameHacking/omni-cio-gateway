"""Regress stale, failed, missing and wrongly attributed release evidence."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import pathlib
import unittest
from unittest.mock import Mock, patch

import report_sonar_annotations as diagnostics
import verify_main_release as gate
from report_sonar_annotations import report_annotations

SHA = "a" * 40
BRANCH = {"commit": {"sha": SHA}}


def sonar(identifier: int = 10, **changes: object) -> dict:
    return {
        "id": identifier, "head_sha": SHA,
        "name": "SonarCloud Code Analysis",
        "app": {"id": 12526, "slug": "sonarqubecloud"},
        "details_url": f"https://sonarcloud.io/dashboard?id={gate.SONAR_PROJECT}&branch=main",
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


def client_with_evidence(*, final_sonar: dict | None = None) -> Mock:
    client = Mock(spec=gate.GitHubClient)
    client.get.return_value = copy.deepcopy(BRANCH)
    client.collect.side_effect = [
        [sonar()], [foundation()], [application()], [application_test()], [application()],
        [sonar() if final_sonar is None else final_sonar],
    ]
    return client


def analysis_page(**changes: object) -> dict:
    return {
        "paging": {"pageIndex": 1, "pageSize": 1, "total": 3},
        "analyses": [{
            "key": "analysis-a", "revision": SHA, "date": "2026-10-08T12:00:00+0000",
            **changes,
        }],
    }


def issues_page(total: int = 0, **changes: object) -> dict:
    return {
        "paging": {"pageIndex": 1, "pageSize": 1, "total": total},
        "issues": ([{
            "key": "old-issue", "project": gate.SONAR_PROJECT,
            "issueStatus": "OPEN", "creationDate": "2025-01-01T00:00:00+0000",
        }] if total else []),
        **changes,
    }


def sonar_client_with_evidence() -> Mock:
    client = Mock(spec=gate.SonarClient)
    client.get.side_effect = [analysis_page(), issues_page(), analysis_page()]
    return client


class ReleaseEvidenceTests(unittest.TestCase):
    def test_current_main_with_all_successful_checks_passes(self) -> None:
        client = client_with_evidence()
        gate.verify(client, SHA, sonar_client_with_evidence())
        self.assertEqual(client.get.call_count, 2)
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
                gate.require_sonar([check], SHA)

    def test_sonar_missing_or_malformed_output_blocks_release(self) -> None:
        malformed = (
            None,
            {},
            {"annotations_count": True, "summary": sonar()["output"]["summary"]},
            {"annotations_count": -1, "summary": sonar()["output"]["summary"]},
            {"annotations_count": 0, "summary": ""},
            {"annotations_count": 0, "summary": "Quality Gate passed"},
        )
        for output in malformed:
            check = sonar(output=output)
            with self.subTest(output=output), self.assertRaises(gate.ReleaseBlocked):
                gate.require_sonar([check], SHA)

    def test_same_sha_pr_success_cannot_hide_failed_main(self) -> None:
        pull_request = sonar(12, details_url=(
            f"https://sonarcloud.io/dashboard?id={gate.SONAR_PROJECT}&pullRequest=660"
        ))
        checks = [sonar(conclusion="failure"), pull_request]
        with self.assertRaises(gate.ReleaseBlocked):
            gate.require_sonar(checks, SHA)
        with self.assertRaises(gate.PendingChecks):
            gate.require_sonar([pull_request], SHA)

    def test_latest_main_attempt_controls_acceptance(self) -> None:
        for conclusion in ("failure", "cancelled", "timed_out", "neutral", "skipped", None):
            checks = [sonar(), sonar(11, conclusion=conclusion)]
            with self.subTest(conclusion=conclusion), self.assertRaises(gate.ReleaseBlocked):
                gate.require_sonar(checks, SHA)
        gate.require_sonar([sonar(conclusion="failure"), sonar(11)], SHA)

    def test_pending_or_unclassified_new_analysis_cannot_reuse_old_success(self) -> None:
        for change in ({"status": "in_progress"}, {"details_url": None}):
            checks = [sonar(), sonar(11, **change)]
            with self.subTest(change=change), self.assertRaises(gate.PendingChecks):
                gate.require_sonar(checks, SHA)

    def test_untrusted_sonar_identity_cannot_pass(self) -> None:
        for change in (
            {"head_sha": "b" * 40}, {"name": "Fake Sonar"},
            {"app": {"id": 1, "slug": "sonarqubecloud"}},
            {"app": {"id": 12526, "slug": "another-app"}}, {"app": None},
        ):
            checks = [sonar(**change)]
            with self.subTest(change=change), self.assertRaises(gate.PendingChecks):
                gate.require_sonar(checks, SHA)

    def test_ambiguous_project_or_branch_url_cannot_pass(self) -> None:
        valid = sonar()["details_url"]
        for url in (
            valid.replace("https:", "http:"), valid.replace("sonarcloud.io", "example.org"),
            valid.replace(gate.SONAR_PROJECT, "another-project"),
            valid.replace("branch=main", "branch=feature"), valid + "&branch=main",
            valid + "&pullRequest=661", valid + "#fragment", "https://[invalid", 123,
        ):
            checks = [sonar(details_url=url)]
            with self.subTest(url=url), self.assertRaises(gate.PendingChecks):
                gate.require_sonar(checks, SHA)

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
        for responses in ([{"commit": {"sha": "b" * 40}}], [BRANCH, {"commit": {}}]):
            client = client_with_evidence()
            client.get.side_effect = responses
            with self.subTest(responses=responses), self.assertRaises(gate.ReleaseBlocked):
                gate.verify(client, SHA, sonar_client_with_evidence())

    def test_malformed_check_identity_blocks_instead_of_selecting_a_result(self) -> None:
        for identifier in (None, "99", True, -1):
            checks = [sonar(id=identifier)]
            with self.subTest(identifier=identifier), self.assertRaises(gate.ReleaseBlocked):
                gate.require_sonar(checks, SHA)

    def test_missing_checks_wait_then_success_returns(self) -> None:
        client = client_with_evidence()
        client.deadline = 100
        with patch.object(gate, "verify", side_effect=[gate.PendingChecks("Pending"), None]), \
                patch.object(gate.time, "monotonic", return_value=1), \
                patch.object(gate.time, "sleep") as sleep, \
                contextlib.redirect_stdout(io.StringIO()):
            gate.wait_for_release(client, SHA, sonar_client_with_evidence())
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
                gate.wait_for_release(client, SHA, sonar_client_with_evidence())
            sleep.assert_not_called()


class OverallSonarEvidenceTests(unittest.TestCase):
    def test_new_pending_or_failed_main_check_during_inventory_blocks_release(self) -> None:
        for check, error in (
            (sonar(11, status="queued", conclusion=None), gate.PendingChecks),
            (sonar(11, conclusion="failure"), gate.ReleaseBlocked),
            (sonar(status="in_progress", conclusion=None), gate.PendingChecks),
            (sonar(conclusion="cancelled"), gate.ReleaseBlocked),
        ):
            with self.subTest(check=check), self.assertRaises(error):
                gate.verify(client_with_evidence(final_sonar=check), SHA,
                            sonar_client_with_evidence())

    def test_replaced_success_or_new_completion_requires_fresh_inventory(self) -> None:
        for check in (sonar(11), sonar(completed_at="2026-10-08T12:02:00Z")):
            with self.subTest(check=check), self.assertRaisesRegex(
                gate.PendingChecks, "check changed",
            ):
                gate.verify(client_with_evidence(final_sonar=check), SHA,
                            sonar_client_with_evidence())

    def test_sonar_check_missing_completion_identity_cannot_certify_inventory(self) -> None:
        for completed_at in (None, "", True):
            with self.subTest(completed_at=completed_at), self.assertRaises(gate.ReleaseBlocked):
                gate.require_sonar([sonar(completed_at=completed_at)], SHA)

    def test_green_new_code_check_cannot_hide_older_main_issue(self) -> None:
        for status in ("OPEN", "CONFIRMED", "ACCEPTED"):
            inventory = issues_page(1)
            inventory["issues"][0]["issueStatus"] = status
            sonar_client = Mock(spec=gate.SonarClient)
            sonar_client.get.side_effect = [analysis_page(), inventory]
            with self.subTest(status=status), self.assertRaisesRegex(
                gate.ReleaseBlocked, "overall main has",
            ):
                gate.verify(client_with_evidence(), SHA, sonar_client)

    def test_zero_inventory_requires_stable_exact_analysis_around_the_read(self) -> None:
        client = sonar_client_with_evidence()
        gate.require_overall_sonar(client, SHA)
        self.assertEqual([call.args[0] for call in client.get.call_args_list], [
            gate.SONAR_ANALYSES_PATH, gate.SONAR_ISSUES_PATH, gate.SONAR_ANALYSES_PATH,
        ])
        self.assertEqual(gate.SONAR_ISSUES_PATH, (
            f"/api/issues/search?componentKeys={gate.SONAR_PROJECT}&branch=main"
            "&issueStatuses=OPEN,CONFIRMED,ACCEPTED&p=1&ps=1"
        ))
        self.assertEqual(gate.SONAR_ANALYSES_PATH, (
            f"/api/project_analyses/search?project={gate.SONAR_PROJECT}&branch=main&p=1&ps=1"
        ))

    def test_previous_revision_never_certifies_even_an_empty_inventory(self) -> None:
        client = Mock(spec=gate.SonarClient)
        client.get.return_value = analysis_page(revision="b" * 40)
        with self.assertRaises(gate.PendingChecks):
            gate.require_overall_sonar(client, SHA)
        client.get.assert_called_once_with(gate.SONAR_ANALYSES_PATH)

    def test_no_analysis_waits_instead_of_treating_missing_inventory_as_clean(self) -> None:
        client = Mock(spec=gate.SonarClient)
        client.get.return_value = {
            "paging": {"pageIndex": 1, "pageSize": 1, "total": 0}, "analyses": [],
        }
        with self.assertRaises(gate.PendingChecks):
            gate.require_overall_sonar(client, SHA)

    def test_reanalysis_during_inventory_read_requires_fresh_verification(self) -> None:
        for changes in (
            {"key": "analysis-b"}, {"revision": "b" * 40},
            {"date": "2026-10-08T12:01:00+0000"},
        ):
            client = Mock(spec=gate.SonarClient)
            client.get.side_effect = [analysis_page(), issues_page(), analysis_page(**changes)]
            with self.subTest(changes=changes), self.assertRaises(gate.PendingChecks):
                gate.require_overall_sonar(client, SHA)

    def test_missing_or_malformed_analysis_identity_fails_closed(self) -> None:
        for changes in (
            {"key": None}, {"key": ""}, {"key": "invalid\nkey"},
            {"revision": None}, {"revision": True}, {"revision": "not-a-sha"},
            {"date": None}, {"date": "invalid"}, {"date": "2026-10-08T12:00:00"},
        ):
            client = Mock(spec=gate.SonarClient)
            client.get.return_value = analysis_page(**changes)
            with self.subTest(changes=changes), self.assertRaises(gate.ReleaseBlocked):
                gate.require_overall_sonar(client, SHA)

    def test_malformed_or_incomplete_zero_issue_response_cannot_pass(self) -> None:
        invalid = (
            {}, {"issues": []}, issues_page(paging=None), issues_page(issues=None),
            issues_page(issues=["invalid"]), issues_page(issues=[{"key": "hidden"}]),
            issues_page(paging={"pageIndex": 1, "pageSize": 1, "total": False}),
            issues_page(paging={"pageIndex": True, "pageSize": 1, "total": 0}),
            issues_page(paging={"pageIndex": 1, "pageSize": 0, "total": 0}),
            issues_page(paging={"pageIndex": 2, "pageSize": 1, "total": 0}),
            issues_page(paging={"pageIndex": 1, "pageSize": 1, "total": -1}),
            issues_page(paging={"pageIndex": 1, "pageSize": 1, "total": "0"}),
            issues_page(total=0, p=2), issues_page(total=0, ps=100),
            {**issues_page(), "total": 1}, {**issues_page(), "total": False},
            issues_page(2, issues=[]),
        )
        for response in invalid:
            client = Mock(spec=gate.SonarClient)
            client.get.side_effect = [analysis_page(), response]
            with self.subTest(response=response), self.assertRaises(gate.ReleaseBlocked):
                gate.require_overall_sonar(client, SHA)

    def test_deprecated_matching_paging_fields_remain_compatible(self) -> None:
        client = Mock(spec=gate.SonarClient)
        client.get.side_effect = [
            analysis_page(), {**issues_page(), "p": 1, "ps": 1, "total": 0}, analysis_page(),
        ]
        gate.require_overall_sonar(client, SHA)

    def test_nonzero_total_cannot_be_hidden_on_later_pages(self) -> None:
        client = Mock(spec=gate.SonarClient)
        client.get.side_effect = [analysis_page(), issues_page(501)]
        with self.assertRaises(gate.ReleaseBlocked):
            gate.require_overall_sonar(client, SHA)
        self.assertEqual(client.get.call_count, 2)

    def test_unavailable_overall_inventory_blocks_successful_github_evidence(self) -> None:
        client = Mock(spec=gate.SonarClient)
        client.get.side_effect = gate.ReleaseBlocked("SonarCloud unavailable")
        with self.assertRaisesRegex(gate.ReleaseBlocked, "SonarCloud unavailable"):
            gate.verify(client_with_evidence(), SHA, client)


class SonarTransportTests(unittest.TestCase):
    def test_public_read_uses_fixed_tls_host_without_github_credentials(self) -> None:
        response = Mock(status=200)
        response.read.return_value = json.dumps(issues_page()).encode()
        connection = Mock()
        connection.getresponse.return_value = response
        with patch.object(gate.http.client, "HTTPSConnection", return_value=connection) as https, \
                patch.object(gate.time, "monotonic", return_value=0), \
                patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-github-token"}):
            client = gate.SonarClient("", deadline=100)
            self.assertEqual(client.get(gate.SONAR_ISSUES_PATH), issues_page())
        https.assert_called_once_with("sonarcloud.io", timeout=15)
        self.assertEqual(connection.request.call_args.args, ("GET", gate.SONAR_ISSUES_PATH))
        headers = connection.request.call_args.kwargs["headers"]
        self.assertNotIn("Authorization", headers)
        self.assertNotIn("synthetic-github-token", str(connection.mock_calls))
        self.assertEqual(headers["Cache-Control"], "no-cache")
        response.read.assert_called_once_with(gate.MAX_RESPONSE_BYTES + 1)
        connection.close.assert_called_once()

    def test_only_dedicated_sonar_token_can_authenticate_the_read(self) -> None:
        with patch.object(gate, "request_json", return_value=analysis_page()) as request:
            client = gate.SonarClient("synthetic-sonar-token", deadline=100)
            client.get(gate.SONAR_ANALYSES_PATH)
        self.assertEqual(request.call_args.args[0], "sonarcloud.io")
        self.assertEqual(request.call_args.args[2]["Authorization"],
                         "Bearer synthetic-sonar-token")

    def test_wrong_host_project_branch_and_narrowed_inventory_are_rejected(self) -> None:
        for path in (
            "https://example.org/api/issues/search", "//example.org/anything",
            gate.SONAR_ISSUES_PATH.replace(gate.SONAR_PROJECT, "another-project"),
            gate.SONAR_ISSUES_PATH.replace("branch=main", "pullRequest=765"),
            gate.SONAR_ISSUES_PATH.replace("branch=main", "branch=feature"),
            gate.SONAR_ISSUES_PATH + "&sinceLeakPeriod=true",
            gate.SONAR_ISSUES_PATH + "&assignees=someone",
            gate.SONAR_ISSUES_PATH + "&createdAfter=2026-01-01",
        ):
            with self.subTest(path=path), patch.object(gate, "request_json") as request, \
                    self.assertRaises(gate.ReleaseBlocked):
                gate.SonarClient("", deadline=100).get(path)
            request.assert_not_called()

    def test_redirect_private_project_and_invalid_responses_fail_closed(self) -> None:
        for status, body in (
            (301, b"redirect"), (302, b"redirect"), (401, b"unauthorized"),
            (403, b"forbidden"), (404, b"missing project"),
            (200, b"<html>login required</html>"), (200, b"[]"), (200, b"null"),
            (200, b"x" * (gate.MAX_RESPONSE_BYTES + 1)),
        ):
            response = Mock(status=status)
            response.read.return_value = body
            connection = Mock()
            connection.getresponse.return_value = response
            with self.subTest(status=status, size=len(body)), \
                    patch.object(gate.http.client, "HTTPSConnection", return_value=connection), \
                    patch.object(gate.time, "monotonic", return_value=0), \
                    self.assertRaises(gate.ReleaseBlocked) as raised:
                gate.SonarClient("", deadline=100).get(gate.SONAR_ISSUES_PATH)
            self.assertNotIn(body.decode(), str(raised.exception))
            connection.close.assert_called_once()
            self.assertEqual(connection.request.call_count, 1)

    def test_transient_errors_share_the_existing_bounded_release_retry(self) -> None:
        for status in (408, 429, 500, 502, 503, 599):
            response = Mock(status=status)
            connection = Mock()
            connection.getresponse.return_value = response
            with self.subTest(status=status), \
                    patch.object(gate.http.client, "HTTPSConnection", return_value=connection), \
                    patch.object(gate.time, "monotonic", return_value=0), \
                    self.assertRaises(gate.PendingChecks):
                gate.SonarClient("", deadline=100).get(gate.SONAR_ISSUES_PATH)
        with patch.object(gate.http.client, "HTTPSConnection", side_effect=OSError), \
                patch.object(gate.time, "monotonic", return_value=0), \
                self.assertRaises(gate.PendingChecks):
            gate.SonarClient("", deadline=100).get(gate.SONAR_ISSUES_PATH)

    def test_deadline_expired_before_or_during_request_cannot_pass(self) -> None:
        response = Mock(status=200)
        response.read.return_value = json.dumps(issues_page()).encode()
        connection = Mock()
        connection.getresponse.return_value = response
        with patch.object(gate.http.client, "HTTPSConnection", return_value=connection), \
                patch.object(gate.time, "monotonic", side_effect=[0, 101]), \
                self.assertRaises(gate.ReleaseBlocked):
            gate.SonarClient("", deadline=100).get(gate.SONAR_ISSUES_PATH)
        with patch.object(gate.http.client, "HTTPSConnection") as https, \
                patch.object(gate.time, "monotonic", return_value=101), \
                self.assertRaises(gate.ReleaseBlocked):
            gate.SonarClient("", deadline=100).get(gate.SONAR_ISSUES_PATH)
        https.assert_not_called()

    def test_malformed_sonar_token_never_reaches_http_headers(self) -> None:
        for token in ("bad\r\nheader", "bad token", "a" * 513):
            with self.subTest(length=len(token)), self.assertRaises(gate.ReleaseBlocked):
                gate.SonarClient(token, deadline=100)


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
            gate.require_sonar(rows, SHA)

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
    def test_cli_keeps_github_and_optional_sonar_credentials_separate(self) -> None:
        valid = {
            "GITHUB_REPOSITORY": gate.REPOSITORY, "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "push", "GITHUB_SHA": SHA,
            "GITHUB_TOKEN": "synthetic-github-token",
        }
        for sonar_token in ("", "synthetic-sonar-token"):
            with self.subTest(authenticated=bool(sonar_token)), \
                    patch.dict(os.environ, valid | {"SONAR_TOKEN": sonar_token}, clear=True), \
                    patch.object(gate, "require_checkout"), \
                    patch.object(gate, "GitHubClient") as github_client, \
                    patch.object(gate, "SonarClient") as sonar_client, \
                    patch.object(gate, "wait_for_release") as wait, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gate.main(), 0)
            self.assertEqual(github_client.call_args.args, ("synthetic-github-token",))
            self.assertEqual(sonar_client.call_args.args, (sonar_token,))
            self.assertEqual(sonar_client.call_args.kwargs["deadline"],
                             github_client.return_value.deadline)
            wait.assert_called_once_with(github_client.return_value, SHA,
                                         sonar_client.return_value)

    def test_cli_rejects_github_token_reused_as_sonar_auth(self) -> None:
        valid = {
            "GITHUB_REPOSITORY": gate.REPOSITORY, "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "push", "GITHUB_SHA": SHA,
            "GITHUB_TOKEN": "synthetic-github-token", "SONAR_TOKEN": "synthetic-github-token",
        }
        output = io.StringIO()
        with patch.dict(os.environ, valid, clear=True), patch.object(gate, "require_checkout"), \
                patch.object(gate, "GitHubClient"), patch.object(gate, "SonarClient") as sonar, \
                patch.object(gate, "wait_for_release") as wait, contextlib.redirect_stderr(output):
            self.assertEqual(gate.main(), 1)
        sonar.assert_not_called()
        wait.assert_not_called()
        self.assertNotIn("synthetic-github-token", output.getvalue())

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
