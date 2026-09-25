from __future__ import annotations

import json
import re
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import check_v10_telegram_public_user_readiness as guard


_REQUIRED = (
    guard.CONTRACT,
    guard.LEDGER,
    guard.RUNBOOK,
    guard.TELEGRAM,
    guard.IDENTITY,
    guard.TRANSACTION_MIGRATION,
    guard.LIMITS,
    guard.AUTH_RUNTIME,
)


def _copy_fixture(root: Path) -> None:
    for relative in _REQUIRED:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(guard.ROOT / relative, target)


class TelegramPublicUserReadinessTests(unittest.TestCase):
    def test_current_repository_contract_is_valid(self) -> None:
        guard.validate()

    def test_guard_rejects_base_evidence_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["accepted_base_main_evidence"] = "UNREVIEWED_BASE"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_BASE_SHA_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_base_main_sha_segment_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["accepted_base_main_sha_segments"][0] = "00000000"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_BASE_SHA_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_release_source_binding_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["operations"]["historical_cloudflare_release_evidence"][
                "current_release_authority"
            ] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_RELEASE_EVIDENCE_INVALID",
            ):
                guard.validate(root)

    def test_machine_surfaces_avoid_contiguous_hex_sha_literals(self) -> None:
        pattern = re.compile(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])")
        contract = (guard.ROOT / guard.CONTRACT).read_text(encoding="utf-8")
        checker = Path(guard.__file__).read_text(encoding="utf-8")
        self.assertIsNone(pattern.search(contract))
        self.assertIsNone(pattern.search(checker))

    def test_guard_rejects_premature_legal_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["legal_privacy_gate"]["accepted"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_LEGAL_GATE_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_missing_legal_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["legal_privacy_gate"]["blocking_conditions"].pop()
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_LEGAL_GATE_INVALID",
            ):
                guard.validate(root)

    def test_guard_tolerates_human_ledger_prose_reflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.LEDGER
            source = path.read_text(encoding="utf-8").replace(
                "Timeweb PostgreSQL 18 production cutover is accepted",
                "Accepted Russian Timeweb production database cutover is recorded",
                1,
            )
            path.write_text(source, encoding="utf-8")
            guard.validate(root)

    def test_guard_rejects_provider_readiness_marker_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["provider_secret_readiness"][
                "timeweb_runtime_secret_custody_accepted"
            ] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_BINDINGS_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_release_evidence_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["operations"]["historical_cloudflare_release_evidence"][
                "conclusion"
            ] = "failure"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_RELEASE_EVIDENCE_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_bot_linking_as_login_prerequisite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["identity_and_bot_separation"]["bot_chat_required_for_login"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_IDENTITY_BOT_SEPARATION_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_telegram_bot_access_scope_in_login(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.TELEGRAM
            source = path.read_text(encoding="utf-8").replace(
                'TELEGRAM_OIDC_LOGIN_SCOPE = "openid"',
                'TELEGRAM_OIDC_LOGIN_SCOPE = "openid"\nTELEGRAM_BOT_SCOPE = "telegram:bot_access"',
                1,
            )
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_BOT_ACCESS_SCOPE_FORBIDDEN",
            ):
                guard.validate(root)

    def test_guard_rejects_extra_telegram_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.TELEGRAM
            source = path.read_text(encoding="utf-8").replace(
                'TELEGRAM_OIDC_LOGIN_SCOPE = "openid"',
                'TELEGRAM_OIDC_LOGIN_SCOPE = "openid profile"',
                1,
            )
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_SCOPE_DRIFT",
            ):
                guard.validate(root)

    def test_guard_is_bound_to_current_timeweb_telegram_runtime(self) -> None:
        self.assertEqual(guard.AUTH_RUNTIME, Path("apps/api/telegram_auth.py"))

    def test_guard_rejects_partial_activation_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["activation_switch"]["partial_activation_allowed"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_ACTIVATION_SWITCH_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_provider_neutral_activation_default_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.AUTH_RUNTIME
            source = path.read_text(encoding="utf-8").replace(
                'if raw in {"", "0", "false"}:\n        return False',
                'if raw in {"", "0", "false"}:\n        return True',
                1,
            )
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_ACTIVATION_DEFAULT_DRIFT",
            ):
                guard.validate(root)

    def test_guard_rejects_premature_timeweb_runtime_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["capacity_and_abuse"]["timeweb_runtime_capacity_accepted"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_CAPACITY_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_horizontal_scaling_before_distributed_limits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["capacity_and_abuse"]["current_horizontal_app_scaling_allowed"] = (
                True
            )
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_CAPACITY_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_request_rate_policy_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.LIMITS
            source = path.read_text(encoding="utf-8").replace(
                "anonymous_requests: int = 300",
                "anonymous_requests: int = 3000",
                1,
            )
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_RATE_POLICY_DRIFT",
            ):
                guard.validate(root)


if __name__ == "__main__":
    unittest.main()
