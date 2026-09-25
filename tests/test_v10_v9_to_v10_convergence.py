from __future__ import annotations

import ast
import json
from pathlib import Path, PureWindowsPath
import shutil
import tempfile
import unittest

import scripts.check_v10_v9_to_v10_convergence as guard


ROOT = Path(__file__).resolve().parents[1]


def _copy(root: Path) -> None:
    paths = (
        guard.CONTRACT,
        guard.PARITY_LEDGER,
        guard.AMENDMENT,
        guard.INDEX,
        guard.STATUS,
        guard.LEDGER,
        guard.AGENTS,
        guard.README,
        guard.CONTRIBUTING,
        guard.WORKFLOW,
        guard.PYPROJECT,
        guard.DOCKERFILE,
        ROOT / guard._CURRENT_RUNTIME_ENTRYPOINT,
        ROOT / "apps/api/hosted_app.py",
        *(ROOT / relative for relative in guard._CURRENT_GPT_AUTHORITY_PATHS),
        *(ROOT / relative for relative in guard._PROTECTED_V9_GPT_RECOVERY_PATHS),
        *(ROOT / relative for relative in guard._RETIRED_PROVIDER_WORKFLOW_PATHS),
        *(ROOT / relative for relative in guard._VERIFIER_WORKFLOW_RELATIVE_PATHS),
    )
    for source in paths:
        relative = source.relative_to(ROOT)
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    for target_name in guard._EXPECTED_TARGETS:
        target = root / target_name
        if target_name.endswith(".py"):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# canonical fixture\n", encoding="utf-8")
        else:
            target.mkdir(parents=True, exist_ok=True)
            (target / "__init__.py").write_text(
                "# canonical reconciliation fixture\n",
                encoding="utf-8",
            )

    for source in guard._EXPECTED_RUNTIME_ROOTS:
        target = root / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# runtime fixture\n", encoding="utf-8")


class V9ToV10ConvergenceGuardTests(unittest.TestCase):
    def test_current_repository_passes(self) -> None:
        guard.validate()

    def test_repository_contract_paths_are_runner_os_independent(self) -> None:
        windows_path = PureWindowsPath(r"gpt\PROJECT_INSTRUCTIONS.md")
        self.assertEqual(
            guard._repository_contract_path(windows_path),
            "gpt/PROJECT_INSTRUCTIONS.md",
        )

    def test_runtime_import_candidates_use_homogeneous_list(self) -> None:
        tree = ast.parse("import json, pathlib\n")
        modules = guard._runtime_import_candidates(
            Path("apps/api/example.py"),
            tree.body[0],
        )
        self.assertIsInstance(modules, list)
        self.assertEqual(modules, ["json", "pathlib"])

    def test_rejects_invalid_segmented_sha_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard.CONTRACT.relative_to(ROOT)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["accepted_v9_repository_target_segments"][0] = "not-sha!"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "V9C_ACCEPTED_V9_SHA_SEGMENTS_INVALID"
            ):
                guard.validate(root)

    def test_rejects_stale_v9_branch_merge_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard.CONTRACT.relative_to(ROOT)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["history_policy"]["stale_v9_branch_direct_merge_allowed"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "V9C_HISTORY_POLICY_DRIFT"):
                guard.validate(root)

    def test_rejects_reintroduced_legacy_root_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            (root / "portfolio_market.py").write_text(
                "# forbidden legacy source\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "V9C_LEGACY_SOURCE_REINTRODUCED"):
                guard.validate(root)

    def test_rejects_missing_canonical_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            (root / "omni_cio/portfolio/market_source_v1.py").unlink()
            with self.assertRaisesRegex(RuntimeError, "V9C_CANONICAL_TARGET_MISSING"):
                guard.validate(root)

    def test_rejects_legacy_import_reintroduction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            consumer = root / "tests/legacy_consumer.py"
            consumer.parent.mkdir(parents=True, exist_ok=True)
            consumer.write_text("import portfolio_market\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "V9C_LEGACY_IMPORT_REINTRODUCED"):
                guard.validate(root)

    def test_rejects_legacy_import_among_multiple_imports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            consumer = root / "tests/multi_legacy_consumer.py"
            consumer.parent.mkdir(parents=True, exist_ok=True)
            consumer.write_text(
                "import json, portfolio_market\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "V9C_LEGACY_IMPORT_REINTRODUCED"):
                guard.validate(root)

    def test_rejects_dynamic_legacy_import_reintroduction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            consumer = root / "tests/dynamic_legacy_consumer.py"
            consumer.parent.mkdir(parents=True, exist_ok=True)
            consumer.write_text(
                'import importlib\nimportlib.import_module("portfolio_market")\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError, "V9C_LEGACY_DYNAMIC_IMPORT_REINTRODUCED"
            ):
                guard.validate(root)

    def test_rejects_stale_legacy_path_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            consumer = root / "tests/stale_path_consumer.py"
            consumer.parent.mkdir(parents=True, exist_ok=True)
            consumer.write_text(
                'LEGACY_SOURCE = "sdk_order_compat.py"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError, "V9C_LEGACY_PATH_CONSUMER_REINTRODUCED"
            ):
                guard.validate(root)

    def test_rejects_noncanonical_reconciliation_subpath_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            consumer = root / "tests/noncanonical_reconciliation_consumer.py"
            consumer.parent.mkdir(parents=True, exist_ok=True)
            consumer.write_text(
                'PATH = "omni_cio/reconciliation/broker_report/__init__.py"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "V9C_NONCANONICAL_RECONCILIATION_PATH_CONSUMER",
            ):
                guard.validate(root)

    def test_rejects_unproven_relocation_parity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard.PARITY_LEDGER.relative_to(ROOT)
            payload = json.loads(path.read_text(encoding="utf-8"))
            for row in payload["capabilities"]:
                if row.get("id") == "PARITY-PRETRADE-CAPACITY":
                    row["status"] = "CONTRACT_DEFINED"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "V9C_PARITY_STATE_DRIFT"):
                guard.validate(root)

    def test_rejects_current_runtime_transitive_legacy_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            hosted_app = root / "apps/api/hosted_app.py"
            hosted_app.write_text("import app\n", encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "V9C_CURRENT_RUNTIME_LEGACY_IMPORT",
            ):
                guard.validate(root)

    def test_rejects_retired_provider_import_in_current_runtime_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            hosted_app = root / "apps/api/hosted_app.py"
            source = hosted_app.read_text(encoding="utf-8")
            hosted_app.write_text(
                "import cloudflare.runtime\n" + source,
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "V9C_CURRENT_RUNTIME_RETIRED_PROVIDER_IMPORT",
            ):
                guard.validate(root)

    def test_rejects_current_gpt_authority_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard._CURRENT_GPT_AUTHORITY_PATHS[0]
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source.replace("CURRENT AMENDMENT-21", "STALE AMENDMENT"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "V9C_CURRENT_GPT_AUTHORITY_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_unmarked_v9_gpt_recovery_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard._PROTECTED_V9_GPT_RECOVERY_PATHS[0]
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source.replace(guard._PROTECTED_V9_GPT_MARKER, "stale recovery"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "V9C_V9_GPT_RECOVERY_MARKER_MISSING",
            ):
                guard.validate(root)

    def test_rejects_retired_provider_workflow_auto_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard._RETIRED_PROVIDER_WORKFLOW_PATHS[0]
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source.replace(
                    "on:\n  workflow_dispatch:",
                    "on:\n  workflow_dispatch:\n  push:",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "V9C_RETIRED_WORKFLOW_TRIGGER_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_reactivated_retired_provider_workflow_job(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard._RETIRED_PROVIDER_WORKFLOW_PATHS[0]
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source.replace("    if: ${{ false }}\n", "", 1),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "V9C_RETIRED_WORKFLOW_NOT_HARD_DISABLED",
            ):
                guard.validate(root)

    def test_rejects_v10_runtime_authority_on_protected_v9_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard.CONTRACT.relative_to(ROOT)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["runtime_retirement_plan"][0][
                "v10_supported_runtime_consumer_allowed"
            ] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError,
                "V9C_RUNTIME_COMPATIBILITY_AUTHORITY_DRIFT",
            ):
                guard.validate(root)

    def test_rejects_premature_runtime_retirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard.CONTRACT.relative_to(ROOT)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["runtime_retirement_plan"][0]["state"] = "RETIRED"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "V9C_RUNTIME_COMPATIBILITY_STATE_DRIFT"
            ):
                guard.validate(root)

    def test_rejects_merge_without_new_owner_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard.CONTRACT.relative_to(ROOT)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["merge_authority"][
                "pr_584_merge_without_new_explicit_owner_instruction_allowed"
            ] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "V9C_UNAUTHORIZED_MAIN_MERGE"):
                guard.validate(root)


if __name__ == "__main__":
    unittest.main()
