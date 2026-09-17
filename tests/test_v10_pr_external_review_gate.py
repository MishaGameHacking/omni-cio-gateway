from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

import scripts.check_v10_pr_external_review_gate as MODULE


_HEAD = "a" * 40
_REPOSITORY = "owner/repo"
_TOKEN = "token"
_PR_NUMBER = 540
_SUITE_ID = 101


class V10ExternalReviewGateTests(unittest.TestCase):
    def _run(
        self,
        *,
        sha: str = _HEAD,
        status: str = "completed",
        conclusion: str = "success",
        issues: int = 0,
        hotspots: int = 0,
        annotations: int = 0,
    ) -> dict[str, object]:
        return {
            "id": 1,
            "name": MODULE.SONAR_CHECK_NAME,
            "head_sha": sha,
            "status": status,
            "conclusion": conclusion,
            "started_at": "2026-09-17T19:47:00Z",
            "completed_at": "2026-09-17T19:47:20Z" if status == "completed" else None,
            "app": {"slug": MODULE.SONAR_APP_SLUG},
            "output": {
                "summary": (
                    f"[Quality Gate](https://sonarcloud.io/)  "
                    f"[{issues} New issues](https://sonarcloud.io/)  "
                    f"[{hotspots} Security Hotspots](https://sonarcloud.io/)"
                ),
                "annotations_count": annotations,
            },
        }

    def _pull(self) -> dict[str, object]:
        return {
            "number": _PR_NUMBER,
            "state": "open",
            "head": {"sha": _HEAD},
            "base": {"ref": "main"},
        }

    def _suite(
        self,
        *,
        status: str = "queued",
        conclusion: str | None = None,
        check_runs_count: int = 0,
        suite_id: int = _SUITE_ID,
    ) -> dict[str, object]:
        return {
            "id": suite_id,
            "head_sha": _HEAD,
            "status": status,
            "conclusion": conclusion,
            "latest_check_runs_count": check_runs_count,
            "created_at": "2026-09-17T19:46:54Z",
            "updated_at": "2026-09-17T19:46:54Z",
            "app": {"slug": MODULE.SONAR_APP_SLUG},
            "pull_requests": [
                {
                    "number": _PR_NUMBER,
                    "head": {"sha": _HEAD},
                }
            ],
        }

    def _comment(
        self,
        *,
        issues: int = 0,
        accepted: int = 0,
        hotspots: int = 0,
        updated_at: str = "2026-09-17T19:47:14Z",
    ) -> dict[str, object]:
        return {
            "id": 5720254281,
            "created_at": updated_at,
            "updated_at": updated_at,
            "user": {"login": MODULE.SONAR_BOT_LOGIN},
            "body": (
                "**Quality Gate passed**\n"
                f"[{issues} New issues](https://sonarcloud.io/project/issues?pullRequest={_PR_NUMBER})\n"
                f"[{accepted} Accepted issues](https://sonarcloud.io/project/issues?pullRequest={_PR_NUMBER})\n"
                f"[{hotspots} Security Hotspots](https://sonarcloud.io/project/security_hotspots?pullRequest={_PR_NUMBER})\n"
            ),
        }

    def _commit(self) -> dict[str, object]:
        return {
            "sha": _HEAD,
            "commit": {"committer": {"date": "2026-09-17T19:46:53Z"}},
        }

    def test_exact_clean_sonar_run_passes(self) -> None:
        self.assertEqual(MODULE._validate_sonar_run(self._run()), [])

    def test_nonzero_new_issues_fail_closed(self) -> None:
        failures = MODULE._validate_sonar_run(self._run(issues=5, annotations=5))
        self.assertTrue(any("new issues must be 0" in item for item in failures))
        self.assertTrue(any("annotations/new findings must be 0" in item for item in failures))

    def test_nonzero_hotspots_fail_closed(self) -> None:
        failures = MODULE._validate_sonar_run(self._run(hotspots=1))
        self.assertTrue(any("Security Hotspots must be 0" in item for item in failures))

    def test_incomplete_or_failed_quality_gate_fails_closed(self) -> None:
        incomplete = MODULE._validate_sonar_run(
            self._run(status="in_progress", conclusion="success")
        )
        failed = MODULE._validate_sonar_run(self._run(conclusion="failure"))
        self.assertTrue(any("not completed" in item for item in incomplete))
        self.assertTrue(any("Quality Gate is not success" in item for item in failed))

    def test_missing_summary_metrics_fail_closed(self) -> None:
        run = self._run()
        output = run["output"]
        assert isinstance(output, dict)
        output["summary"] = "Quality Gate passed"
        failures = MODULE._validate_sonar_run(run)
        self.assertTrue(any("new-issues metric" in item for item in failures))
        self.assertTrue(any("Security-Hotspots metric" in item for item in failures))

    def test_only_exact_head_sonar_run_is_selected(self) -> None:
        exact_sha = "b" * 40
        payload = {"check_runs": [self._run(sha=_HEAD), self._run(sha=exact_sha)]}
        selected = MODULE._find_exact_sonar_run(payload, exact_sha)
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected["head_sha"], exact_sha)

    def test_wrong_provider_or_head_does_not_satisfy_gate(self) -> None:
        wrong_provider = self._run()
        app = wrong_provider["app"]
        assert isinstance(app, dict)
        app["slug"] = "other"
        self.assertIsNone(MODULE._find_exact_sonar_run({"check_runs": [wrong_provider]}, _HEAD))
        self.assertIsNone(MODULE._find_exact_sonar_run({"check_runs": [self._run()]}, "b" * 40))

    def test_stalled_suite_requires_zero_runs_and_null_conclusion(self) -> None:
        self.assertEqual(
            MODULE._stalled_suite_fingerprint(self._suite()),
            (_SUITE_ID, "queued", None, 0),
        )
        invalid_suites = (
            self._suite(status="completed", conclusion="failure"),
            self._suite(check_runs_count=1),
        )
        for suite in invalid_suites:
            with self.subTest(suite=suite):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "not an eligible stalled zero-run suite",
                ):
                    MODULE._stalled_suite_fingerprint(suite)

    def test_sonar_decoration_requires_zero_metrics_and_exact_pr(self) -> None:
        self.assertEqual(MODULE._validate_sonar_comment(self._comment(), _PR_NUMBER), [])
        cases = (
            (self._comment(issues=1), "New issues must be 0"),
            (self._comment(accepted=1), "Accepted issues must be 0"),
            (self._comment(hotspots=1), "Security Hotspots must be 0"),
        )
        for comment, marker in cases:
            with self.subTest(marker=marker):
                failures = MODULE._validate_sonar_comment(comment, _PR_NUMBER)
                self.assertTrue(any(marker in failure for failure in failures))

    def test_stale_sonar_decoration_fails_closed(self) -> None:
        comments = [self._comment(updated_at="2026-09-17T19:46:52Z")]
        not_before = datetime(2026, 9, 17, 19, 46, 54, tzinfo=timezone.utc)
        with patch.object(MODULE, "_github_json", return_value=comments):
            with self.assertRaisesRegex(RuntimeError, "decoration is missing"):
                MODULE._latest_sonar_comment(
                    _REPOSITORY,
                    _TOKEN,
                    _PR_NUMBER,
                    not_before=not_before,
                )

    def test_stalled_suite_decoration_certifies_with_toctou_rechecks(self) -> None:
        payloads = [
            [self._pull()],
            self._commit(),
            {"total_count": 1, "check_suites": [self._suite()]},
            [self._comment()],
            {"check_runs": []},
            [self._pull()],
            {"total_count": 1, "check_suites": [self._suite()]},
            [self._comment()],
        ]
        with patch.object(MODULE, "_github_json", side_effect=payloads):
            mode = MODULE._certify_stalled_suite_decoration(_REPOSITORY, _HEAD, _TOKEN)
        self.assertEqual(mode, "stalled_suite_pr_decoration")

    def test_direct_run_appearing_during_fallback_becomes_authoritative(self) -> None:
        payloads = [
            [self._pull()],
            self._commit(),
            {"total_count": 1, "check_suites": [self._suite()]},
            [self._comment()],
            {"check_runs": [self._run()]},
        ]
        with patch.object(MODULE, "_github_json", side_effect=payloads):
            mode = MODULE._certify_stalled_suite_decoration(_REPOSITORY, _HEAD, _TOKEN)
        self.assertEqual(mode, "direct_check_run_after_stalled_suite")

    def test_changed_suite_during_fallback_fails_closed(self) -> None:
        payloads = [
            [self._pull()],
            self._commit(),
            {"total_count": 1, "check_suites": [self._suite()]},
            [self._comment()],
            {"check_runs": []},
            [self._pull()],
            {"total_count": 1, "check_suites": [self._suite(suite_id=102)]},
        ]
        with patch.object(MODULE, "_github_json", side_effect=payloads):
            with self.assertRaisesRegex(RuntimeError, "suite changed"):
                MODULE._certify_stalled_suite_decoration(_REPOSITORY, _HEAD, _TOKEN)

    def test_wait_prefers_direct_completed_check(self) -> None:
        payload = {"check_runs": [self._run()]}
        with patch.object(MODULE, "_github_json", return_value=payload):
            run, mode = MODULE._wait_for_sonar(_REPOSITORY, _HEAD, _TOKEN)
        self.assertIsNotNone(run)
        self.assertEqual(mode, "direct_check_run")

    def test_wait_never_uses_decoration_when_direct_check_is_in_progress(self) -> None:
        in_progress = self._run(status="in_progress", conclusion="success")
        payload = {"check_runs": [in_progress]}
        settings = {"V10_SONAR_GATE_ATTEMPTS": "1", "V10_SONAR_GATE_DELAY_SECONDS": "1"}
        with (
            patch.object(MODULE, "_github_json", return_value=payload),
            patch.object(MODULE, "_certify_stalled_suite_decoration") as fallback,
            patch.dict(MODULE.os.environ, settings, clear=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "did not complete"):
                MODULE._wait_for_sonar(_REPOSITORY, _HEAD, _TOKEN)
        fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
