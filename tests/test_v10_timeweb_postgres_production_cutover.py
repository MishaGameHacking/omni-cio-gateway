from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_timeweb_postgres_production_cutover.py"
SPEC = importlib.util.spec_from_file_location(
    "check_v10_timeweb_postgres_production_cutover",
    SCRIPT,
)
assert SPEC is not None
assert SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

WORKFLOW_RELATIVE = Path(
    ".github/workflows/v10-timeweb-postgres-production-cutover.yml"
)

DEPENDENCIES = (
    "docs/architecture/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_CONTRACT.json",
    "docs/operations/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_RUNBOOK.md",
    "scripts/timeweb_postgres_production_cutover.py",
    WORKFLOW_RELATIVE.as_posix(),
    "infrastructure/postgres/hosted-postgres-runtime-contract.json",
    "infrastructure/postgres/hosted-recovery-contract.json",
)


def _copy(root: Path) -> None:
    for relative in DEPENDENCIES:
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _contract_path(root: Path) -> Path:
    return root / (
        "docs/architecture/V10_TIMEWEB_POSTGRES_PRODUCTION_CUTOVER_CONTRACT.json"
    )


class TimewebPostgresProductionCutoverGuardTests(unittest.TestCase):
    def test_repository_contract_passes(self) -> None:
        guard.validate(ROOT)

    def test_rejects_synthetic_fixture_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["target"]["synthetic_fixture_promotion_allowed"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_TARGET_INVALID",
            ):
                guard.validate(root)

    def test_rejects_controller_login_creation_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["runtime_role"]["controller_creates_login"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_RUNTIME_ROLE_WIDENED",
            ):
                guard.validate(root)

    def test_rejects_automatic_workflow_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / WORKFLOW_RELATIVE
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source.replace(
                    "on:\n  workflow_dispatch:",
                    "on:\n  push:\n    branches: [main]\n  workflow_dispatch:",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_WORKFLOW_AUTO_TRIGGER_FORBIDDEN",
            ):
                guard.validate(root)

    def test_rejects_public_activation_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["protected_invariants"]["PUBLIC_MULTI_USER_ENABLED"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_AUTHORITY_WIDENED",
            ):
                guard.validate(root)

    def test_rejects_recovery_attestation_as_actions_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / WORKFLOW_RELATIVE
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source
                + "\n# ${{ secrets.OMNI_V10_TIMEWEB_PG_RECOVERY_ATTESTATION }}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_RECOVERY_ATTESTATION_SECRET_FORBIDDEN",
            ):
                guard.validate(root)

    def test_rejects_provider_token_outside_accept_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / WORKFLOW_RELATIVE
            source = path.read_text(encoding="utf-8")
            marker = (
                "      - name: Observe verified production database\n"
                "        if: ${{ inputs.operation == 'observe' }}\n"
                "        shell: bash\n"
                "        env:\n"
            )
            self.assertIn(marker, source)
            path.write_text(
                source.replace(
                    marker,
                    marker
                    + "          TIMEWEB_CLOUD_API_TOKEN: "
                    + "${{ secrets.TIMEWEB_CLOUD_API_TOKEN }}\n",
                    1,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_WORKFLOW_SECRET_SCOPE_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_missing_recovery_evidence_digest_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = _contract_path(root)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["recovery"]["recovery_evidence_sha256_required"] = False
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                guard.CutoverContractError,
                "TIMEWEB_PG_CUTOVER_RECOVERY_DRIFT",
            ):
                guard.validate(root)

    def test_contract_keeps_recovery_and_app_promotion_external(self) -> None:
        payload = json.loads(_contract_path(ROOT).read_text(encoding="utf-8"))
        self.assertTrue(payload["recovery"]["timeweb_physical_backup_required"])
        self.assertTrue(payload["recovery"]["separate_restore_rehearsal_required"])
        self.assertTrue(payload["recovery"]["recovery_evidence_sha256_required"])
        self.assertFalse(
            payload["recovery"]["actions_secret_for_recovery_attestation_allowed"]
        )
        self.assertFalse(
            payload["app_binding"]["runtime_dsn_promotion_by_controller_allowed"]
        )
        self.assertFalse(
            payload["app_binding"]["undocumented_timeweb_app_settings_api_allowed"]
        )


if __name__ == "__main__":
    unittest.main()
