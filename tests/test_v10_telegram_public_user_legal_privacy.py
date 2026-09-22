from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import check_v10_telegram_public_user_legal_privacy as guard


_REQUIRED = (
    guard.CONTRACT,
    guard.READINESS,
    guard.POLICY,
    guard.CONSENT,
    guard.RUNBOOK,
    guard.STATUS,
    guard.PLATFORM_AUTHORITY,
    guard.AUTH_RUNTIME,
)


def _copy_fixture(root: Path) -> None:
    for relative in _REQUIRED:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(guard.ROOT / relative, target)


class TelegramPublicUserLegalPrivacyTests(unittest.TestCase):
    def test_current_repository_contract_is_valid(self) -> None:
        guard.validate()

    def test_guard_rejects_retired_provider_reentry_as_current_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.PLATFORM_AUTHORITY
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["database"]["neon_current_rollback_available"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_LEGAL_PRIVACY_PLATFORM_AUTHORITY_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_foreign_database_as_localized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["current_data_residency"]["russian_localization_accepted"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_LEGAL_PRIVACY_LOCALIZATION_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_premature_public_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.AUTH_RUNTIME
            source = path.read_text(encoding="utf-8").replace(
                "if not value:\n        return False",
                "if not value:\n        return True",
                1,
            )
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_LEGAL_PRIVACY_ACTIVATION_DEFAULT_DRIFT",
            ):
                guard.validate(root)

    def test_guard_tolerates_policy_body_reflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.POLICY
            source = path.read_text(encoding="utf-8").replace(
                "публичная регистрация граждан Российской Федерации",
                "публичная регистрация граждан\nРоссийской Федерации",
                1,
            )
            path.write_text(source, encoding="utf-8")
            guard.validate(root)

    def test_guard_rejects_readiness_blocker_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.READINESS
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["legal_privacy_gate"]["blocking_conditions"].pop()
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_LEGAL_PRIVACY_READINESS_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_unproved_regulator_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["regulator_and_public_notice"][
                "roskomnadzor_processing_notification_accepted"
            ] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_LEGAL_PRIVACY_REGULATOR_INVALID",
            ):
                guard.validate(root)

    def test_guard_requires_timeweb_production_cutover_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["current_data_residency"]["required_before_activation"] = (
                "HISTORICAL_RU_PG_B_SYNTHETIC_PARITY"
            )
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_LEGAL_PRIVACY_LOCALIZATION_INVALID",
            ):
                guard.validate(root)

    def test_guard_rejects_missing_activation_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy_fixture(root)
            path = root / guard.CONTRACT
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["activation_gate"]["blocking_conditions"].pop()
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TELEGRAM_LEGAL_PRIVACY_GATE_INVALID",
            ):
                guard.validate(root)


if __name__ == "__main__":
    unittest.main()
