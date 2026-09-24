from __future__ import annotations

import json
from pathlib import Path
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
            with self.assertRaisesRegex(
                RuntimeError, "V9C_LEGACY_SOURCE_REINTRODUCED"
            ):
                guard.validate(root)

    def test_rejects_missing_canonical_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            (root / "omni_cio/portfolio/market_source_v1.py").unlink()
            with self.assertRaisesRegex(
                RuntimeError, "V9C_CANONICAL_TARGET_MISSING"
            ):
                guard.validate(root)

    def test_rejects_legacy_import_reintroduction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            consumer = root / "tests/legacy_consumer.py"
            consumer.parent.mkdir(parents=True, exist_ok=True)
            consumer.write_text("import portfolio_market\n", encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "V9C_LEGACY_IMPORT_REINTRODUCED"
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

    def test_rejects_premature_runtime_retirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _copy(root)
            path = root / guard.CONTRACT.relative_to(ROOT)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["runtime_retirement_plan"][0]["state"] = "RETIRED"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                RuntimeError, "V9C_RUNTIME_RETIREMENT_PREMATURE"
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
