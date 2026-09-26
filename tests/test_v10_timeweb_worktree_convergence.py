from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import check_v10_timeweb_worktree_convergence as guard


ROOT = Path(__file__).resolve().parents[1]


class TimewebWorktreeConvergenceTests(unittest.TestCase):
    def test_current_repository_passes(self) -> None:
        guard.validate(ROOT)

    def _fixture_root(self, temporary: str) -> Path:
        root = Path(temporary)
        contract = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_WORKTREE_CONVERGENCE_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        contract_path = (
            root / "docs/architecture/V10_TIMEWEB_WORKTREE_CONVERGENCE_CONTRACT.json"
        )
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        for relative in contract["protected_present_paths"]:
            source = ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True, exist_ok=True)
        (workflows / "current.yml").write_text(
            "name: current\non:\n  workflow_dispatch:\n",
            encoding="utf-8",
        )
        return root

    def test_contract_records_all_completed_internal_phases(self) -> None:
        payload = json.loads(
            (
                ROOT
                / "docs/architecture/V10_TIMEWEB_WORKTREE_CONVERGENCE_CONTRACT.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(payload["phase"], "ALL_INTERNAL_PHASES_COMPLETE")
        self.assertEqual(
            payload["completed_internal_phases"],
            [
                "CLIENTLESS_CLOUDFLARE_REMOVAL",
                "RENDER_NEON_CLOUDFLARE_RUNTIME_REMOVAL",
                "WP22A_AUTH_TELEGRAM_ONLY_CONVERGENCE",
                "LEGACY_DOCUMENTATION_PRUNE_AND_CANONICALIZATION",
            ],
        )

    def test_partial_internal_phase_set_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._fixture_root(temporary)
            contract_path = (
                root
                / "docs/architecture/V10_TIMEWEB_WORKTREE_CONVERGENCE_CONTRACT.json"
            )
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
            payload["completed_internal_phases"].pop()
            contract_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_WORKTREE_COMPLETED_PHASES_DRIFT",
            ):
                guard.validate(root)

    def test_reintroduced_retired_path_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._fixture_root(temporary)
            retired = root / "omni_cio/web/external_access_v1.py"
            retired.parent.mkdir(parents=True, exist_ok=True)
            retired.write_text("legacy = True\n", encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_WORKTREE_RETIRED_PATH_PRESENT",
            ):
                guard.validate(root)

    def test_reintroduced_retired_prefix_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._fixture_root(temporary)
            retired = root / "infrastructure/cloudflare/wp22a/new.tf"
            retired.parent.mkdir(parents=True, exist_ok=True)
            retired.write_text("legacy = true\n", encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_WORKTREE_RETIRED_PREFIX_PRESENT",
            ):
                guard.validate(root)

    def test_reintroduced_workflow_reference_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._fixture_root(temporary)
            workflow = root / ".github/workflows/current.yml"
            workflow.write_text(
                "name: current\n"
                "on:\n  workflow_dispatch:\n"
                "jobs:\n  check:\n"
                "    steps:\n"
                "      - run: python apps/api/wp22a_remote.py\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_WORKTREE_RETIRED_WORKFLOW_REFERENCE",
            ):
                guard.validate(root)

    def test_protected_v9_entrypoint_cannot_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._fixture_root(temporary)
            (root / "render.yaml").write_text(
                "startCommand: uvicorn apps.api.hosted_runtime:create_app\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "TIMEWEB_WORKTREE_V9_ENTRYPOINT_DRIFT",
            ):
                guard.validate(root)


if __name__ == "__main__":
    unittest.main()
