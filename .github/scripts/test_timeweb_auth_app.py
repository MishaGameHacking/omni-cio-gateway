#!/usr/bin/env python3
"""Regression tests for the auth application deployer."""

from __future__ import annotations

import base64
import importlib.util
import io
import pathlib
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SCRIPT_DIR = pathlib.Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

MODULE_PATH = SCRIPT_DIR / "timeweb_auth_app.py"
SPEC = importlib.util.spec_from_file_location("timeweb_auth_app", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load timeweb_auth_app.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeSsh:
    def __init__(self, succeeds: bool) -> None:
        self.succeeds = succeeds
        self.commands: list[str] = []

    def run(self, command: str, *, input_text: str | None = None) -> str:
        self.commands.append(command)
        if not self.succeeds:
            raise MODULE.InfraError("not ready")
        return ""


class FakeClient:
    def get_servers(self) -> list[dict[str, object]]:
        return [
            {
                "id": 9235089,
                "name": "omni-cio-white-site",
                "comment": "Managed by GitHub Actions: timeweb-white-site",
            }
        ]

    def get_server(self, server_id: int) -> dict[str, object]:
        self.server_id = server_id
        return {
            "id": server_id,
            "networks": [
                {
                    "type": "public",
                    "ips": [{"ip": "194.87.151.244"}],
                }
            ],
        }

    def get_database_clusters(self) -> list[dict[str, object]]:
        raise AssertionError("app deploy must not require database API access")


class FakeEphemeralSsh:
    def __init__(self, **_: object) -> None:
        self.ssh = FakeSsh(False)

    def __enter__(self) -> FakeSsh:
        return self.ssh

    def __exit__(self, *args: object) -> None:
        return None


class AuthAppDeployTests(unittest.TestCase):
    def test_release_sha_requires_full_lowercase_commit(self) -> None:
        self.assertIsNotNone(MODULE.RELEASE_RE.fullmatch("a" * 40))
        self.assertIsNone(MODULE.RELEASE_RE.fullmatch("A" * 40))
        self.assertIsNone(MODULE.RELEASE_RE.fullmatch("a" * 39))

    def test_runtime_gate_requires_remote_environment(self) -> None:
        ready = FakeSsh(True)
        missing = FakeSsh(False)

        self.assertTrue(MODULE.runtime_is_ready(ready))
        self.assertFalse(MODULE.runtime_is_ready(missing))
        self.assertIn("REGISTRATION_ENABLED=false", ready.commands[0])

    def test_pending_database_gate_does_not_require_database_api_scope(self) -> None:
        with (
            patch.object(MODULE, "EphemeralSsh", FakeEphemeralSsh),
            patch.object(MODULE, "build_release_archive", return_value="archive"),
        ):
            result = MODULE.reconcile(
                FakeClient(),
                server_name="omni-cio-white-site",
                server_comment="Managed by GitHub Actions: timeweb-white-site",
                release_sha="a" * 40,
                repository_root=pathlib.Path("."),
            )

        self.assertEqual(result, 0)

    def test_release_archive_contains_only_runtime_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = pathlib.Path(tempdir)
            (root / "src" / "omnicio").mkdir(parents=True)
            (root / "web").mkdir()
            (root / "tests").mkdir()
            (root / "pyproject.toml").write_text("[project]\nname='x'\n")
            (root / "src" / "omnicio" / "__init__.py").write_text("")
            (root / "web" / "index.html").write_text("<html></html>")
            (root / "tests" / "secret-test.txt").write_text("not shipped")

            encoded = MODULE.build_release_archive(root)
            raw = base64.b64decode(encoded)
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
                names = set(archive.getnames())

        self.assertIn("pyproject.toml", names)
        self.assertIn("src/omnicio/__init__.py", names)
        self.assertIn("web/index.html", names)
        self.assertNotIn("tests/secret-test.txt", names)

    def test_remote_service_is_loopback_only_and_registration_is_gated(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        self.assertIn("--host 127.0.0.1 --port 8001", script)
        self.assertIn("EnvironmentFile=/etc/omnicio/runtime.env", script)
        self.assertIn("NoNewPrivileges=true", script)
        self.assertIn("proxy_pass http://127.0.0.1:8001", script)


if __name__ == "__main__":
    unittest.main()
