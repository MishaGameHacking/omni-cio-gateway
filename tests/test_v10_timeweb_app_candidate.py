from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_timeweb_app_candidate.py"
SPEC = importlib.util.spec_from_file_location("check_v10_timeweb_app_candidate", SCRIPT)
assert SPEC is not None
assert SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)
CONTRACT_RELATIVE = (
    "docs/architecture/V10_TIMEWEB_APP_EXACT_SHA_CANDIDATE_CONTRACT.json"
)


class TimewebAppCandidateGuardTests(unittest.TestCase):
    def _fixture(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for relative in (
            CONTRACT_RELATIVE,
            "scripts/timeweb_app_release.py",
            ".github/workflows/v10-timeweb-app-candidate.yml",
        ):
            source = ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        runtime = root / "apps/api/hosted_runtime.py"
        runtime.parent.mkdir(parents=True, exist_ok=True)
        runtime.write_text(
            'X = "OMNI_V10_CANDIDATE_HOSTNAME"\n'
            'Y = "OMNI_V10_POSTGRES_PRIVATE_HOSTADDR"\n'
            'Z = "OMNI_V10_POSTGRES_PRIVATE_NETWORK_CIDR"\n'
            "def prepare_timeweb_postgres_private_target(): pass\n"
            "def _optional_candidate_hostname(): pass\n"
            'additional_hosts=("localhost", *candidate_hosts)\n',
            encoding="utf-8",
        )
        return root

    def test_contract_and_sources_pass(self) -> None:
        guard.validate(self._fixture())

    def test_rejects_autodeploy_authority(self) -> None:
        root = self._fixture()
        path = root / CONTRACT_RELATIVE
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["target"]["auto_deploy_allowed"] = True
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(
            RuntimeError, "TIMEWEB_APP_CANDIDATE_TARGET_INVALID"
        ):
            guard.validate(root)

    def test_rejects_unsafe_initial_create_api_authority(self) -> None:
        root = self._fixture()
        path = root / CONTRACT_RELATIVE
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["target"]["initial_create_via_documented_api_allowed"] = True
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_APP_CANDIDATE_TARGET_INVALID",
        ):
            guard.validate(root)

    def test_requires_creation_time_private_network_binding(self) -> None:
        root = self._fixture()
        path = root / CONTRACT_RELATIVE
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["target"]["immutable_private_network_required_at_creation"] = False
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_APP_CANDIDATE_TARGET_INVALID",
        ):
            guard.validate(root)

    def test_rejects_automatic_workflow_trigger(self) -> None:
        root = self._fixture()
        path = root / ".github/workflows/v10-timeweb-app-candidate.yml"
        source = path.read_text(encoding="utf-8")
        path.write_text(
            source.replace(
                "on:\n  workflow_dispatch:",
                "on:\n  push:\n    branches: [main]\n  workflow_dispatch:",
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_APP_CANDIDATE_WORKFLOW_AUTHORITY_WIDENED",
        ):
            guard.validate(root)

    def test_rejects_repository_clone_url_identity_downgrade(self) -> None:
        root = self._fixture()
        path = root / CONTRACT_RELATIVE
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["target"]["repository_clone_url_identity_required"] = False
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_APP_CANDIDATE_TARGET_INVALID",
        ):
            guard.validate(root)

    def test_rejects_live_mode_without_p5_evidence_contract(self) -> None:
        root = self._fixture()
        path = root / CONTRACT_RELATIVE
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["runtime"]["activation_modes"]["live-operable"][
            "p5_live_evidence_sha256_required"
        ] = False
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_APP_CANDIDATE_RUNTIME_ENV_INVALID",
        ):
            guard.validate(root)

    def test_runtime_contract_rejects_integer_for_boolean_invariant(self) -> None:
        root = self._fixture()
        path = root / CONTRACT_RELATIVE
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["runtime"]["postgres_private_route_rfc1918_required"] = 1
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_APP_CANDIDATE_RUNTIME_ENV_INVALID",
        ):
            guard.validate(root)

    def test_rejects_liveness_database_startup_dependency(self) -> None:
        root = self._fixture()
        path = root / CONTRACT_RELATIVE
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["acceptance"]["liveness_startup_database_connection_required"] = True
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_APP_CANDIDATE_ACCEPTANCE_INVALID",
        ):
            guard.validate(root)

    def test_rejects_missing_private_database_readiness_contract(self) -> None:
        root = self._fixture()
        path = root / CONTRACT_RELATIVE
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["acceptance"]["database_readiness_path"] = "/livez"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_APP_CANDIDATE_ACCEPTANCE_INVALID",
        ):
            guard.validate(root)

    def test_rejects_candidate_before_p3_prepare_ordering(self) -> None:
        root = self._fixture()
        path = root / CONTRACT_RELATIVE
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["orchestration"]["p3_prepare_before_physical_candidate_required"] = (
            False
        )
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_APP_CANDIDATE_ORCHESTRATION_INVALID",
        ):
            guard.validate(root)

    def test_rejects_p3_accept_before_current_candidate_proof(self) -> None:
        root = self._fixture()
        path = root / CONTRACT_RELATIVE
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["orchestration"]["p3_accept_before_physical_candidate_allowed"] = True
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_APP_CANDIDATE_ORCHESTRATION_INVALID",
        ):
            guard.validate(root)

    def test_rejects_public_activation_contract_drift(self) -> None:
        root = self._fixture()
        path = root / CONTRACT_RELATIVE
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["protected_invariants"][
            "public_activation_without_p5_live_evidence_allowed"
        ] = True
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(
            RuntimeError,
            "TIMEWEB_APP_CANDIDATE_INVARIANTS_INVALID",
        ):
            guard.validate(root)


if __name__ == "__main__":
    unittest.main()
