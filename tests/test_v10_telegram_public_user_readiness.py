from __future__ import annotations

import json
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
    guard.WRANGLER,
)


def _copy_fixture(root: Path) -> None:
    for relative in _REQUIRED:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(guard.ROOT / relative, target)


class TelegramPublicUserReadinessTests(unittest.TestCase):
    def test_current_repository_contract_is_valid(self) -> None:
        guard.validate()

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

    def test_guard_rejects_provider_readiness_marker_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["provider_secret_readiness"]["marker"] = "READY_BUT_UNREVIEWED"
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
            payload["operations"]["exact_main_release_evidence"]["conclusion"] = "failure"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_RELEASE_EVIDENCE_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_extra_telegram_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.TELEGRAM
            source = path.read_text(encoding="utf-8").replace(
                '"scope": "openid"',
                '"scope": "openid profile"',
                1,
            )
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_SCOPE_DRIFT",
            ):
                guard.validate(root)

    def test_guard_rejects_missing_production_vars(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.WRANGLER
            source = path.read_text(encoding="utf-8")
            start = source.index('  "vars": {')
            end = source.index('  "secrets": {', start)
            path.write_text(source[:start] + source[end:], encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_PRODUCTION_FLAG_DRIFT",
            ):
                guard.validate(root)

    def test_guard_rejects_activation_flag_flip_in_readiness_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.WRANGLER
            source = path.read_text(encoding="utf-8").replace(
                '"PUBLIC_MULTI_USER_ENABLED": "false"',
                '"PUBLIC_MULTI_USER_ENABLED": "true"',
                1,
            )
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_PRODUCTION_FLAG_DRIFT",
            ):
                guard.validate(root)

    def test_guard_rejects_capacity_widening(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.WRANGLER
            source = path.read_text(encoding="utf-8").replace(
                '"max_instances": 1',
                '"max_instances": 2',
                1,
            )
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_PUBLIC_USER_READINESS_CONTAINER_ENVELOPE_DRIFT",
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
