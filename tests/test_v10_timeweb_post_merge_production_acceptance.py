from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
from urllib.parse import urlsplit

from scripts import check_v10_timeweb_post_merge_production_acceptance as guard
from scripts import timeweb_production_acceptance as acceptance


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
ROLLBACK_SHA = "b" * 40
DIGESTS = tuple(character * 64 for character in "123456")
CONTRACT = (
    "docs/architecture/V10_TIMEWEB_POST_MERGE_PRODUCTION_ACCEPTANCE_CONTRACT.json"
)
DEPENDENCIES = (
    CONTRACT,
    "scripts/timeweb_production_acceptance.py",
    ".github/workflows/v10-timeweb-post-merge-production-acceptance.yml",
)


def _copy_guard_dependencies(root: Path) -> None:
    for relative in DEPENDENCIES:
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


class _Response:
    def __init__(self, payload: object) -> None:
        self.status = 200
        self.headers = {"Content-Type": "application/json"}
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        del exc_type, exc, traceback

    def read(self, limit: int) -> bytes:
        return self._raw[:limit]


class _Opener:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def open(self, request: object, timeout: float) -> _Response:
        del timeout
        path = urlsplit(str(request.full_url)).path
        if path == "/livez":
            return _Response({"status": "ok", "release_sha": SHA})
        if path == "/healthz":
            return _Response(
                {
                    "status": "ok",
                    "database": "READY",
                    "synthetic_preview": False,
                    "release_sha": SHA,
                }
            )
        if path == "/api/v10/web/auth/providers":
            if self.enabled:
                return _Response([{"provider": "telegram", "enabled": True}])
            return _Response(
                [
                    {
                        "provider": "telegram",
                        "enabled": False,
                        "reason": "PUBLIC_MULTI_USER_DISABLED",
                    }
                ]
            )
        raise AssertionError(path)


class _TransientOpener(_Opener):
    def __init__(self) -> None:
        super().__init__()
        self.failed_once = False
        self.paths: list[str] = []

    def open(self, request: object, timeout: float) -> _Response:
        path = urlsplit(str(request.full_url)).path
        self.paths.append(path)
        if path == "/livez" and not self.failed_once:
            self.failed_once = True
            raise OSError("transient route propagation")
        return super().open(request, timeout)


def _accepted_kwargs() -> dict[str, str]:
    return {
        "p2_candidate_evidence_sha256": DIGESTS[0],
        "p3_cutover_evidence_sha256": DIGESTS[1],
        "p4_ingress_evidence_sha256": DIGESTS[2],
        "p5_readiness_sha256": DIGESTS[3],
        "p5_live_evidence_sha256": DIGESTS[4],
        "rollback_release_sha": ROLLBACK_SHA,
        "rollback_evidence_sha256": DIGESTS[5],
    }


class TimewebPostMergeProductionAcceptanceTests(unittest.TestCase):
    def test_repository_contract_passes(self) -> None:
        guard.validate(ROOT)

    def test_premerge_readiness_cannot_claim_production_acceptance(self) -> None:
        payload = json.loads((ROOT / CONTRACT).read_text(encoding="utf-8"))
        readiness = payload["premerge_readiness"]
        self.assertTrue(readiness["source_contract_complete"])
        self.assertTrue(readiness["exact_head_ci_required_before_merge"])
        self.assertFalse(readiness["production_accepted"])
        self.assertTrue(readiness["post_merge_execution_required"])
        self.assertTrue(readiness["merge_does_not_imply_live"])

    def test_guard_rejects_premature_production_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_guard_dependencies(root)
            contract_path = root / CONTRACT
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            payload["premerge_readiness"]["production_accepted"] = True
            contract_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_P6_PREMERGE_READINESS_DRIFT",
            ):
                guard.validate(root)

    def test_execution_access_policy_is_fail_closed(self) -> None:
        payload = json.loads((ROOT / CONTRACT).read_text(encoding="utf-8"))
        execution = payload["execution"]
        access_keys = [key for key in execution if key.endswith("_access_allowed")]
        self.assertEqual(len(access_keys), 1)
        self.assertFalse(execution[access_keys[0]])

    def test_guard_rejects_execution_access_widening(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_guard_dependencies(root)
            contract_path = root / CONTRACT
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            execution = payload["execution"]
            access_keys = [key for key in execution if key.endswith("_access_allowed")]
            self.assertEqual(len(access_keys), 1)
            execution[access_keys[0]] = True
            contract_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_P6_EXECUTION_ACCESS_POLICY_DRIFT",
            ):
                guard.validate(root)

    def test_acceptance_seal_is_deterministic_and_source_bound(self) -> None:
        evidence = acceptance._validated_evidence(**_accepted_kwargs())
        first = acceptance.production_acceptance_seal(SHA, evidence)
        second = acceptance.production_acceptance_seal(SHA, evidence)
        other = acceptance.production_acceptance_seal("c" * 40, evidence)
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_accept_requires_live_telegram_and_emits_seal(self) -> None:
        output = StringIO()
        kwargs = _accepted_kwargs()
        with redirect_stdout(output):
            seal = acceptance.run(
                operation="accept",
                expected_sha=SHA,
                observed_main_sha=SHA,
                confirmation=acceptance.ACCEPT_CONFIRMATION,
                opener=_Opener(),
                **kwargs,
            )
        self.assertIsNotNone(seal)
        self.assertIn("TIMEWEB_PRODUCTION_ACCEPTANCE=ACCEPTED", output.getvalue())

    def test_accept_retries_transient_public_transport(self) -> None:
        output = StringIO()
        opener = _TransientOpener()
        with (
            mock.patch.object(acceptance.time, "sleep") as sleeper,
            redirect_stdout(output),
        ):
            seal = acceptance.run(
                operation="accept",
                expected_sha=SHA,
                observed_main_sha=SHA,
                confirmation=acceptance.ACCEPT_CONFIRMATION,
                opener=opener,
                **_accepted_kwargs(),
            )
        self.assertIsNotNone(seal)
        sleeper.assert_called_once_with(acceptance._PUBLIC_PROBE_RETRY_DELAYS[0])
        self.assertEqual(opener.paths[:2], ["/livez", "/livez"])

    def test_accept_rejects_disabled_telegram(self) -> None:
        kwargs = _accepted_kwargs()
        opener = _Opener(enabled=False)
        with self.assertRaisesRegex(
            acceptance.ProductionAcceptanceStopped,
            "TIMEWEB_PRODUCTION_ACCEPTANCE_PROVIDER_SURFACE_INVALID",
        ):
            acceptance.run(
                operation="accept",
                expected_sha=SHA,
                observed_main_sha=SHA,
                confirmation=acceptance.ACCEPT_CONFIRMATION,
                opener=opener,
                **kwargs,
            )

    def test_accept_rejects_main_drift(self) -> None:
        opener = _Opener()
        with self.assertRaisesRegex(
            acceptance.ProductionAcceptanceStopped,
            "TIMEWEB_PRODUCTION_ACCEPTANCE_MAIN_SHA_DRIFT",
        ):
            acceptance.run(
                operation="observe",
                expected_sha=SHA,
                observed_main_sha="c" * 40,
                opener=opener,
            )

    def test_accept_rejects_rollback_collision(self) -> None:
        kwargs = _accepted_kwargs()
        kwargs["rollback_release_sha"] = SHA
        opener = _Opener()
        with self.assertRaisesRegex(
            acceptance.ProductionAcceptanceStopped,
            "TIMEWEB_PRODUCTION_ACCEPTANCE_ROLLBACK_SHA_COLLISION",
        ):
            acceptance.run(
                operation="accept",
                expected_sha=SHA,
                observed_main_sha=SHA,
                confirmation=acceptance.ACCEPT_CONFIRMATION,
                opener=opener,
                **kwargs,
            )


if __name__ == "__main__":
    unittest.main()
