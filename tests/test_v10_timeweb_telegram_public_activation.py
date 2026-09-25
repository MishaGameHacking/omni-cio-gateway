from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from urllib.request import Request


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "scripts/timeweb_telegram_public_activation.py"
GUARD = ROOT / "scripts/check_v10_timeweb_telegram_public_activation.py"

CONTROLLER_SPEC = importlib.util.spec_from_file_location(
    "timeweb_telegram_public_activation",
    CONTROLLER,
)
assert CONTROLLER_SPEC is not None
assert CONTROLLER_SPEC.loader is not None
activation = importlib.util.module_from_spec(CONTROLLER_SPEC)
CONTROLLER_SPEC.loader.exec_module(activation)

GUARD_SPEC = importlib.util.spec_from_file_location(
    "check_v10_timeweb_telegram_public_activation",
    GUARD,
)
assert GUARD_SPEC is not None
assert GUARD_SPEC.loader is not None
guard = importlib.util.module_from_spec(GUARD_SPEC)
GUARD_SPEC.loader.exec_module(guard)

EXPECTED_SHA = "a" * 40
ROLLBACK_SHA = "b" * 40
DIGEST = "c" * 64
LIVE_DIGEST = "d" * 64


class _Response:
    status = 200

    def __init__(self, payload: object) -> None:
        self._raw = json.dumps(payload).encode("utf-8")
        self.headers = {"Content-Type": "application/json; charset=utf-8"}

    def read(self, limit: int) -> bytes:
        return self._raw[:limit]

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        del args


class _Opener:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = list(responses)
        self.requests: list[Request] = []

    def open(self, request: Request, *, timeout: float) -> _Response:
        del timeout
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.pop(0)


def _opener(*, enabled: bool, sha: str = EXPECTED_SHA) -> _Opener:
    provider: dict[str, object] = {"provider": "telegram", "enabled": enabled}
    if not enabled:
        provider["reason"] = "PUBLIC_MULTI_USER_DISABLED"
    return _Opener(
        [
            _Response({"status": "ok", "release_sha": sha}),
            _Response(
                {
                    "status": "ok",
                    "release_sha": sha,
                    "database": "READY",
                    "synthetic_preview": False,
                }
            ),
            _Response([provider]),
        ]
    )


def _prerequisites() -> dict[str, str]:
    return {
        "p3_acceptance_evidence_sha256": DIGEST,
        "p4_acceptance_evidence_sha256": DIGEST,
        "external_readiness_evidence_sha256": DIGEST,
        "rollback_release_sha": ROLLBACK_SHA,
        "rollback_evidence_sha256": DIGEST,
    }


def _seal() -> str:
    return activation.readiness_seal(
        EXPECTED_SHA,
        {
            "p3_acceptance_evidence_sha256": DIGEST,
            "p4_acceptance_evidence_sha256": DIGEST,
            "external_readiness_evidence_sha256": DIGEST,
            "rollback_release_sha": ROLLBACK_SHA,
            "rollback_evidence_sha256": DIGEST,
        },
    )


class TimewebTelegramPublicActivationTests(unittest.TestCase):
    def test_repository_guard_passes(self) -> None:
        guard.validate(ROOT)

    def test_ready_requires_configured_runtime_while_flags_remain_off(self) -> None:
        opener = _opener(enabled=False)
        activation.run(
            operation="ready",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            confirmation=activation.READY_CONFIRMATION,
            opener=opener,
            **_prerequisites(),
        )
        self.assertEqual(
            [request.full_url for request in opener.requests],
            [
                "https://omnicio.ru/livez",
                "https://omnicio.ru/healthz",
                "https://omnicio.ru/api/v10/web/auth/providers",
            ],
        )

    def test_accept_requires_same_readiness_seal_and_live_provider(self) -> None:
        activation.run(
            operation="accept",
            expected_sha=EXPECTED_SHA,
            observed_main_sha=EXPECTED_SHA,
            confirmation=activation.ACCEPT_CONFIRMATION,
            readiness_sha256=_seal(),
            live_acceptance_evidence_sha256=LIVE_DIGEST,
            opener=_opener(enabled=True),
            **_prerequisites(),
        )

    def test_accept_rejects_readiness_seal_from_different_evidence(self) -> None:
        with self.assertRaisesRegex(
            activation.TelegramActivationStopped,
            "TIMEWEB_TELEGRAM_ACTIVATION_READINESS_SEAL_DRIFT",
        ):
            activation.run(
                operation="accept",
                expected_sha=EXPECTED_SHA,
                observed_main_sha=EXPECTED_SHA,
                confirmation=activation.ACCEPT_CONFIRMATION,
                readiness_sha256="e" * 64,
                live_acceptance_evidence_sha256=LIVE_DIGEST,
                opener=_opener(enabled=True),
                **_prerequisites(),
            )

    def test_ready_rejects_missing_runtime_credentials(self) -> None:
        opener = _opener(enabled=False)
        opener.responses[-1] = _Response(
            [{"provider": "telegram", "enabled": False, "reason": "NOT_CONFIGURED"}]
        )
        with self.assertRaisesRegex(
            activation.TelegramActivationStopped,
            "TIMEWEB_TELEGRAM_ACTIVATION_STATE_MISMATCH",
        ):
            activation.run(
                operation="ready",
                expected_sha=EXPECTED_SHA,
                observed_main_sha=EXPECTED_SHA,
                confirmation=activation.READY_CONFIRMATION,
                opener=opener,
                **_prerequisites(),
            )

    def test_accept_rejects_release_sha_drift(self) -> None:
        with self.assertRaisesRegex(
            activation.TelegramActivationStopped,
            "TIMEWEB_TELEGRAM_ACTIVATION_RELEASE_SHA_DRIFT",
        ):
            activation.run(
                operation="accept",
                expected_sha=EXPECTED_SHA,
                observed_main_sha=EXPECTED_SHA,
                confirmation=activation.ACCEPT_CONFIRMATION,
                readiness_sha256=_seal(),
                live_acceptance_evidence_sha256=LIVE_DIGEST,
                opener=_opener(enabled=True, sha="f" * 40),
                **_prerequisites(),
            )

    def test_accept_rejects_rollback_collision(self) -> None:
        evidence = _prerequisites()
        evidence["rollback_release_sha"] = EXPECTED_SHA
        with self.assertRaisesRegex(
            activation.TelegramActivationStopped,
            "TIMEWEB_TELEGRAM_ACTIVATION_ROLLBACK_SHA_COLLISION",
        ):
            activation.run(
                operation="ready",
                expected_sha=EXPECTED_SHA,
                observed_main_sha=EXPECTED_SHA,
                confirmation=activation.READY_CONFIRMATION,
                opener=_opener(enabled=False),
                **evidence,
            )

    def test_guard_rejects_write_all_workflow_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in (
                guard.CONTRACT_RELATIVE,
                guard.CONTROLLER_RELATIVE,
                guard.WORKFLOW_RELATIVE,
                guard.RUNBOOK_RELATIVE,
                guard.READINESS_RELATIVE,
                guard.AUTH_RUNTIME_RELATIVE,
                guard.FULL_DELIVERY_RELATIVE,
            ):
                source = ROOT / relative
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            workflow = root / guard.WORKFLOW_RELATIVE
            workflow.write_text(
                workflow.read_text(encoding="utf-8") + "\npermissions: write-all\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_TELEGRAM_ACTIVATION_WORKFLOW_UNSAFE",
            ):
                guard.validate(root)


if __name__ == "__main__":
    unittest.main()
