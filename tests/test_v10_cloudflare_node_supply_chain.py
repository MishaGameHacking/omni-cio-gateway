from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import scripts.check_v10_cloudflare_node_supply_chain as guard


class CloudflareNodeSupplyChainTests(unittest.TestCase):
    def test_repository_contract_is_valid(self) -> None:
        guard.validate()

    def test_guard_rejects_provider_npm_mismatch(self) -> None:
        payload = json.loads(guard.PACKAGE.read_text(encoding="utf-8"))
        payload["engines"]["npm"] = "11.16.0"
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "package.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "PACKAGE", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_NODE_SUPPLY_CHAIN_TOOLCHAIN_INVALID",
                ):
                    guard.validate()

    def test_guard_rejects_package_manager_mismatch(self) -> None:
        payload = json.loads(guard.PACKAGE.read_text(encoding="utf-8"))
        payload["packageManager"] = "npm@11.16.0"
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "package.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "PACKAGE", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_NODE_SUPPLY_CHAIN_PACKAGE_MANAGER_INVALID",
                ):
                    guard.validate()

    def test_guard_rejects_unsafe_npmrc(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / ".npmrc"
            candidate.write_text("ignore-scripts=false\n", encoding="utf-8")
            with mock.patch.object(guard, "NPMRC", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_NODE_SUPPLY_CHAIN_NPMRC_INVALID",
                ):
                    guard.validate()

    def test_guard_rejects_root_lock_dependency_drift(self) -> None:
        payload = json.loads(guard.PACKAGE_LOCK.read_text(encoding="utf-8"))
        payload["packages"][""]["devDependencies"]["wrangler"] = "4.127.0"
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "package-lock.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "PACKAGE_LOCK", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_NODE_SUPPLY_CHAIN_LOCK_ROOT_DEVDEPENDENCIES_INVALID",
                ):
                    guard.validate()

    def test_guard_rejects_root_lifecycle_scripts(self) -> None:
        payload = json.loads(guard.PACKAGE.read_text(encoding="utf-8"))
        payload["scripts"]["postinstall"] = "node scripts/unreviewed.js"
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "package.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(guard, "PACKAGE", candidate):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_NODE_SUPPLY_CHAIN_LIFECYCLE_SCRIPTS_FORBIDDEN",
                ):
                    guard.validate()


if __name__ == "__main__":
    unittest.main()
