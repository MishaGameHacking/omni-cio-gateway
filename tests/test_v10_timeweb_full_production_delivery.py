from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_timeweb_full_production_delivery.py"
SPEC = importlib.util.spec_from_file_location(
    "check_v10_timeweb_full_production_delivery",
    SCRIPT,
)
assert SPEC is not None
assert SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

DEPENDENCIES = (
    "docs/master-plan/OMNI_CIO_V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_AMENDMENT.md",
    "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json",
    "docs/architecture/V10_TELEGRAM_PUBLIC_USER_ACTIVATION_READINESS_CONTRACT.json",
    "apps/api/hosted_runtime.py",
    "apps/api/telegram_auth.py",
    "Dockerfile",
)


def _copy(root: Path) -> None:
    for relative in DEPENDENCIES:
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


class TimewebFullProductionDeliveryGuardTests(unittest.TestCase):
    def test_repository_contract_passes(self) -> None:
        guard.validate(ROOT)

    def test_rejects_production_autodeploy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            contract_path = (
                root
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            )
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            payload["release"]["production_autodeploy_allowed"] = True
            contract_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_FULL_DELIVERY_RELEASE_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_canonical_domain_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            contract_path = (
                root
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            )
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            payload["canonical_origin"] = "https://example.invalid"
            contract_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_FULL_DELIVERY_CONTRACT_DRIFT:canonical_origin",
            ):
                guard.validate(root)

    def test_rejects_premature_public_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            readiness_path = (
                root
                / "docs/architecture/"
                "V10_TELEGRAM_PUBLIC_USER_ACTIVATION_READINESS_CONTRACT.json"
            )
            payload = json.loads(readiness_path.read_text(encoding="utf-8"))
            payload["activation_allowed"] = True
            readiness_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_FULL_DELIVERY_PREMATURE_PUBLIC_ACTIVATION",
            ):
                guard.validate(root)

    def test_rejects_broker_write_authority_widening(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            contract_path = (
                root
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            )
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            payload["protected_invariants"]["broker_write"] = True
            contract_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_FULL_DELIVERY_AUTHORITY_WIDENED:broker_write",
            ):
                guard.validate(root)

    def test_secret_allowlist_contains_names_not_values(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        names = payload["runtime"]["secret_env_names"]
        self.assertEqual(len(names), len(set(names)))
        self.assertNotIn("secret_values", payload["runtime"])
        self.assertFalse(payload["runtime"]["secret_values_in_repository_allowed"])


if __name__ == "__main__":
    unittest.main()
