from __future__ import annotations

import unittest
from unittest.mock import patch

import scripts.check_v10_cloudflare_postmerge_release_gate as gate
import scripts.check_v10_sonar_equivalent_tree_provenance as provenance


_SHA = "a" * 40
_NAME = "SonarCloud Code Analysis"
_APP = "sonarqubecloud"


def _check(conclusion: str | None) -> dict[str, object]:
    return {
        "id": 1,
        "name": _NAME,
        "head_sha": _SHA,
        "status": "completed" if conclusion is not None else "in_progress",
        "conclusion": conclusion,
        "started_at": "2026-09-15T22:09:20Z",
        "completed_at": "2026-09-15T22:10:00Z" if conclusion is not None else None,
        "app": {"slug": _APP},
        "output": {
            "annotations_count": 0,
            "summary": "[0 New issues]\n[0 Security Hotspots]",
        },
    }


class CloudflarePostMergeSonarFallbackTests(unittest.TestCase):
    def test_cancelled_exact_main_uses_bounded_provenance_certifier(self) -> None:
        cancelled = _check("cancelled")
        with (
            patch.object(gate, "_check_runs", return_value=[cancelled]),
            patch.object(
                provenance,
                "certify_cancelled_exact_main_sonar",
                return_value="b" * 40,
            ) as certify,
        ):
            self.assertTrue(
                gate._external_evidence_state(
                    "owner/repo",
                    "token",
                    _SHA,
                    _NAME,
                    _APP,
                )
            )
        certify.assert_called_once()

    def test_terminal_failure_never_uses_provenance_fallback(self) -> None:
        failed = _check("failure")
        with (
            patch.object(gate, "_check_runs", return_value=[failed]),
            patch.object(
                provenance,
                "certify_cancelled_exact_main_sonar",
            ) as certify,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_NOT_SUCCESS",
            ):
                gate._external_evidence_state(
                    "owner/repo",
                    "token",
                    _SHA,
                    _NAME,
                    _APP,
                )
        certify.assert_not_called()

    def test_pending_or_missing_exact_main_sonar_stays_pending(self) -> None:
        for rows in ([], [_check(None)]):
            with self.subTest(rows=rows):
                with patch.object(gate, "_check_runs", return_value=rows):
                    self.assertFalse(
                        gate._external_evidence_state(
                            "owner/repo",
                            "token",
                            _SHA,
                            _NAME,
                            _APP,
                        )
                    )


if __name__ == "__main__":
    unittest.main()
