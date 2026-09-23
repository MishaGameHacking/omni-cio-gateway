from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

import scripts.check_v10_timeweb_no_owner_laptop_dependency as guard


ROOT = Path(__file__).resolve().parents[1]


def _copy(root: Path) -> None:
    paths = (
        guard.CONTRACT,
        guard.HOSTED_CUSTODY,
        guard.HOSTED_APP,
        guard.HOSTED_RUNTIME,
        guard.TELEGRAM_AUTH,
        guard.WP17_CONTRACT,
        guard.WP17_SECURITY_GUARD,
        guard.CURRENT_WORKFLOW,
        guard.HISTORICAL_WORKFLOW,
        guard.PUBLIC_RUNTIME,
    )
    for source in paths:
        relative = source.relative_to(ROOT)
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


class TimewebNoOwnerLaptopGuardTests(unittest.TestCase):
    def test_current_repository_passes(self) -> None:
        guard.validate()

    def test_rejects_current_windows_vault_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard.HOSTED_RUNTIME.relative_to(ROOT)
            path.write_text(
                path.read_text(encoding="utf-8")
                + "\nimport omni_cio.web.broker_vault_v1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_NO_LAPTOP_CURRENT_LOCAL_VAULT_DEPENDENCY",
            ):
                guard.validate(root)

    def test_rejects_required_workflow_return_to_self_hosted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard.CURRENT_WORKFLOW.relative_to(ROOT)
            source = path.read_text(encoding="utf-8").replace(
                "runs-on: ubuntu-latest",
                "runs-on: [self-hosted, Windows, X64, omni-cio-ci]",
                1,
            )
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_NO_LAPTOP_REQUIRED_WORKFLOW",
            ):
                guard.validate(root)

    def test_runtime_metadata_uses_custody_contract_reference(self) -> None:
        payload = json.loads(guard.CONTRACT.read_text(encoding="utf-8"))
        runtime = payload["current_timeweb_runtime"]
        self.assertEqual(
            set(runtime),
            {
                "provider",
                "local_windows_vault_dependency_allowed",
                "windows_dpapi_dependency_allowed",
                "broker_mutation_enabled",
                "global_shared_broker_token_allowed",
                "hosted_custody_contract",
            },
        )
        self.assertEqual(
            runtime["hosted_custody_contract"],
            "omni_cio/web/hosted_secret_custody_v1.py",
        )

    def test_rejects_broker_mutation_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard.CONTRACT.relative_to(ROOT)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["current_timeweb_runtime"]["broker_mutation_enabled"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_NO_LAPTOP_RUNTIME_BOUNDARY_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_wp17_contract_requiring_owner_acl_for_timeweb_pr(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard.WP17_CONTRACT.relative_to(ROOT)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["timeweb_broker_custody"][
                "owner_admin_acl_evidence_required_for_timeweb_pr"
            ] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_NO_LAPTOP_WP17_CUSTODY_DRIFT",
            ):
                guard.validate(root)

    def test_historical_local_vault_remains_non_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard.WP17_CONTRACT.relative_to(ROOT)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                payload["read_vault_acceptance"]["authority"],
                "HISTORICAL_LOCAL_ONLY",
            )
            self.assertFalse(payload["read_vault_acceptance"]["blocks_timeweb_pr"])
            guard.validate(root)


if __name__ == "__main__":
    unittest.main()
