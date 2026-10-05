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
        "status": "completed", "conclusion": "success", **changes,
    }


def client_with_evidence() -> Mock:
    client = Mock(spec=gate.GitHubClient)
    client.get.return_value = copy.deepcopy(BRANCH)
    client.collect.side_effect = [[sonar()], [foundation()]]
    return client


class ReleaseEvidenceTests(unittest.TestCase):
    def test_current_main_with_both_successful_checks_passes(self) -> None:
        client = client_with_evidence()
        gate.verify(client, SHA)
        self.assertEqual(client.get.call_count, 2)
        self.assertIn("filter=all", client.collect.call_args_list[0].args[0])

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

    def test_main_moving_before_or_during_verification_blocks_release(self) -> None:
        for responses in ([{"commit": {"sha": "b" * 40}}], [BRANCH, {"commit": {}}]):
            client = client_with_evidence()
            client.get.side_effect = responses
            with self.subTest(responses=responses), self.assertRaises(gate.ReleaseBlocked):
                gate.verify(client, SHA)

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


class SelfHostedCiPolicyTests(unittest.TestCase):
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
