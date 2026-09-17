from __future__ import annotations

import unittest
from unittest.mock import patch

import scripts.check_v10_cloudflare_postmerge_release_gate as gate
import scripts.check_v10_sonar_equivalent_tree_provenance as provenance


_SHA = "a" * 40
_NAME = "SonarCloud Code Analysis"
_APP = "sonarqubecloud"
_REPOSITORY = "owner/repo"
_TOKEN = "token"


class _ForeignReleaseGateStopped(RuntimeError):
    def __init__(self, code: str, *, status: int | None = None) -> None:
        self.code = code
        self.status = status
        super().__init__(code)


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


def _evidence_state() -> bool:
    return gate._external_evidence_state(
        _REPOSITORY,
        _TOKEN,
        _SHA,
        _NAME,
        _APP,
    )


def _deadline_state() -> bool:
    return gate._deadline_external_evidence_state(
        _REPOSITORY,
        _TOKEN,
        _SHA,
        _NAME,
        _APP,
    )


class CloudflarePostMergeSonarFallbackTests(unittest.TestCase):
    def test_cancelled_exact_main_uses_provenance_certifier(self) -> None:
        cancelled = _check("cancelled")
        with (
            patch.object(gate, "_check_runs", return_value=[cancelled]),
            patch.object(
                provenance,
                "certify_cancelled_exact_main_sonar",
                return_value="b" * 40,
            ) as certify,
        ):
            self.assertTrue(_evidence_state())
        certify.assert_called_once()

    def test_valid_merge_sha_convergence_signal_stays_pending(self) -> None:
        cancelled = _check("cancelled")
        pending = _ForeignReleaseGateStopped(
            provenance.MERGE_SHA_CONVERGENCE_PENDING
        )
        with (
            patch.object(gate, "_check_runs", return_value=[cancelled]),
            patch.object(
                provenance,
                "certify_cancelled_exact_main_sonar",
                side_effect=pending,
            ),
        ):
            self.assertFalse(_evidence_state())

    def test_other_foreign_provenance_stop_is_normalized_and_terminal(self) -> None:
        cancelled = _check("cancelled")
        terminal_code = "CLOUDFLARE_POSTMERGE_PROVENANCE_TREE_MISMATCH"
        with (
            patch.object(gate, "_check_runs", return_value=[cancelled]),
            patch.object(
                provenance,
                "certify_cancelled_exact_main_sonar",
                side_effect=_ForeignReleaseGateStopped(terminal_code),
            ),
        ):
            with self.assertRaises(gate.ReleaseGateStopped) as caught:
                _evidence_state()
        self.assertEqual(caught.exception.code, terminal_code)

    def test_unclassified_runtime_error_is_never_reclassified_as_pending(self) -> None:
        cancelled = _check("cancelled")
        with (
            patch.object(gate, "_check_runs", return_value=[cancelled]),
            patch.object(
                provenance,
                "certify_cancelled_exact_main_sonar",
                side_effect=RuntimeError("unexpected"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "unexpected"):
                _evidence_state()

    def test_each_release_snapshot_rechecks_current_main(self) -> None:
        with (
            patch.object(gate, "_require_current_main") as current_main,
            patch.object(gate, "_workflow_runs", return_value=[]),
            patch.object(gate, "_gate_state", return_value=(True, 11)),
            patch.object(gate, "_external_evidence_state", return_value=False),
        ):
            for _ in range(2):
                ready, observed, external_ready = gate._release_gate_snapshot(
                    _REPOSITORY,
                    _TOKEN,
                    _SHA,
                    frozenset({"Regression Shield"}),
                    11,
                    _NAME,
                    _APP,
                )
                self.assertTrue(ready)
                self.assertEqual(observed, 11)
                self.assertFalse(external_ready)
        self.assertEqual(current_main.call_count, 2)

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
                _evidence_state()
        certify.assert_not_called()

    def test_pending_or_missing_exact_main_sonar_stays_pending(self) -> None:
        for rows in ([], [_check(None)]):
            with self.subTest(rows=rows):
                with patch.object(gate, "_check_runs", return_value=rows):
                    self.assertFalse(_evidence_state())

    def test_deadline_missing_exact_main_uses_provenance_certifier(self) -> None:
        with (
            patch.object(gate, "_check_runs", return_value=[]),
            patch.object(
                provenance,
                "certify_missing_exact_main_sonar",
                return_value="b" * 40,
            ) as certify,
        ):
            self.assertTrue(_deadline_state())
        certify.assert_called_once_with(
            repository=_REPOSITORY,
            token=_TOKEN,
            expected_sha=_SHA,
            required_name=_NAME,
            required_app_slug=_APP,
        )

    def test_deadline_in_progress_exact_main_never_uses_missing_fallback(self) -> None:
        pending = _check(None)
        with (
            patch.object(gate, "_check_runs", return_value=[pending]),
            patch.object(gate, "_external_evidence_state", return_value=False) as normal,
            patch.object(
                provenance,
                "certify_missing_exact_main_sonar",
            ) as certify_missing,
        ):
            self.assertFalse(_deadline_state())
        normal.assert_called_once_with(
            _REPOSITORY,
            _TOKEN,
            _SHA,
            _NAME,
            _APP,
        )
        certify_missing.assert_not_called()


if __name__ == "__main__":
    unittest.main()
