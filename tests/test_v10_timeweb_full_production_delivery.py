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
                root / "docs/architecture/"
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

    def test_branch_milestones_track_p4_green_and_p5_implementation(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        states = {row["id"]: row["state"] for row in payload["branch_milestones"]}
        self.assertEqual(
            states["P2_TIMEWEB_EXACT_SHA_CANDIDATE"],
            "CERTIFIED_GREEN_BRANCH_LOCAL",
        )
        self.assertEqual(
            states["P3_POSTGRES18_PRODUCTION_CUTOVER"],
            "CERTIFIED_GREEN_BRANCH_LOCAL",
        )
        self.assertEqual(
            states["P4_OMNICIO_RU_DNS_TLS"],
            "CERTIFIED_GREEN_BRANCH_LOCAL",
        )
        self.assertEqual(
            states["P5_TELEGRAM_PUBLIC_ACTIVATION"],
            "IMPLEMENTED_VERIFICATION_PENDING",
        )

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
        names = payload["runtime"]["runtime_credential_env_names"]
        self.assertEqual(len(names), len(set(names)))
        self.assertNotIn("secret_values", payload["runtime"])
        self.assertFalse(payload["runtime"]["credential_values_in_repository_allowed"])

    def test_public_ingress_is_read_only_and_evidence_bound(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        ingress = payload["public_ingress"]
        self.assertEqual(ingress["provider_api_mode"], "READ_ONLY")
        self.assertFalse(ingress["provider_domain_mutation_by_controller_allowed"])
        self.assertTrue(ingress["p3_recovery_evidence_digest_required"])
        self.assertTrue(ingress["russian_no_vpn_evidence_digest_required"])
        self.assertTrue(ingress["rollback_release_sha_required"])
        self.assertTrue(ingress["rollback_evidence_digest_required"])
        self.assertTrue(ingress["public_activation_must_remain_false"])

    def test_contract_metadata_keys_are_detector_safe(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_FULL_PRODUCTION_DELIVERY_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )

        def assert_keys_are_safe(value: object) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    self.assertNotIn("secret", key.casefold())
                    assert_keys_are_safe(child)
            elif isinstance(value, list):
                for child in value:
                    assert_keys_are_safe(child)

        assert_keys_are_safe(payload)


if __name__ == "__main__":
    unittest.main()
