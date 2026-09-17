from __future__ import annotations

import unittest
from unittest.mock import patch

import scripts.check_v10_pr_external_review_gate as MODULE


_HEAD = "a" * 40
_REPOSITORY = "owner/repo"
_TOKEN = "token"
_SETTINGS = {"V10_SONAR_GATE_ATTEMPTS": "1", "V10_SONAR_GATE_DELAY_SECONDS": "1"}


def _governance(
    *,
    status: str = "completed",
    conclusion: str = "success",
    annotations: int = 0,
) -> dict[str, object]:
    return {
        "id": 2,
        "name": "Engineering quality and green-merge contract",
        "head_sha": _HEAD,
        "status": status,
        "conclusion": conclusion,
        "started_at": "2026-09-17T20:00:00Z",
        "completed_at": "2026-09-17T20:05:00Z" if status == "completed" else None,
        "app": {"slug": "github-actions"},
        "output": {"annotations_count": annotations, "summary": "governance"},
    }


def _sonar(
    *,
    status: str = "completed",
    conclusion: str = "success",
) -> dict[str, object]:
    return {
        "id": 3,
        "name": MODULE.SONAR_CHECK_NAME,
        "head_sha": _HEAD,
        "status": status,
        "conclusion": conclusion,
        "started_at": "2026-09-17T20:01:00Z",
        "completed_at": "2026-09-17T20:02:00Z" if status == "completed" else None,
        "app": {"slug": MODULE.SONAR_APP_SLUG},
        "output": {
            "annotations_count": 0,
            "summary": "[0 New issues]\n[0 Security Hotspots]",
        },
    }


class V10ExternalReviewGateProxyTests(unittest.TestCase):
    def test_permission_limited_consumer_can_use_successful_governance_proxy(self) -> None:
        payloads = [
            {"check_runs": []},
            MODULE.ReviewGateHttpError(403),
            {"check_runs": [_governance()]},
        ]
        with (
            patch.object(MODULE, "_github_json", side_effect=payloads),
            patch.dict(MODULE.os.environ, _SETTINGS, clear=False),
        ):
            run, mode = MODULE._wait_for_sonar(_REPOSITORY, _HEAD, _TOKEN)
        self.assertIsNone(run)
        self.assertEqual(mode, "repository_governance_proxy")

    def test_non_permission_http_error_never_uses_governance_proxy(self) -> None:
        payloads = [{"check_runs": []}, MODULE.ReviewGateHttpError(500)]
        with (
            patch.object(MODULE, "_github_json", side_effect=payloads),
            patch.dict(MODULE.os.environ, _SETTINGS, clear=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTP 500"):
                MODULE._wait_for_sonar(_REPOSITORY, _HEAD, _TOKEN)

    def test_direct_in_progress_sonar_blocks_governance_proxy(self) -> None:
        check_runs = [_sonar(status="in_progress"), _governance()]
        payload = {"check_runs": check_runs}
        with (
            patch.object(MODULE, "_github_json", return_value=payload),
            patch.dict(MODULE.os.environ, _SETTINGS, clear=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "did not become successful"):
                MODULE._repository_governance_proxy(_REPOSITORY, _HEAD, _TOKEN)

    def test_direct_failed_sonar_blocks_governance_proxy(self) -> None:
        check_runs = [_sonar(conclusion="failure"), _governance()]
        payload = {"check_runs": check_runs}
        with (
            patch.object(MODULE, "_github_json", return_value=payload),
            patch.dict(MODULE.os.environ, _SETTINGS, clear=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "Quality Gate is not success"):
                MODULE._repository_governance_proxy(_REPOSITORY, _HEAD, _TOKEN)

    def test_failed_governance_proxy_is_not_accepted(self) -> None:
        payload = {"check_runs": [_governance(conclusion="failure")]}
        with (
            patch.object(MODULE, "_github_json", return_value=payload),
            patch.dict(MODULE.os.environ, _SETTINGS, clear=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "proxy is not success"):
                MODULE._repository_governance_proxy(_REPOSITORY, _HEAD, _TOKEN)


if __name__ == "__main__":
    unittest.main()
