from __future__ import annotations

import ast
import inspect
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import scripts.install_v10_cloudflare_delivery_toolchain as installer


class CloudflareDeliveryToolchainQualityTests(unittest.TestCase):
    @staticmethod
    def _tarball(member: tarfile.TarInfo, payload: bytes | None = None) -> bytes:
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            fileobj = io.BytesIO(payload) if payload is not None else None
            archive.addfile(member, fileobj=fileobj)
        return stream.getvalue()

    @classmethod
    def _regular_npm_tarball(cls, payload: bytes = b"cli") -> bytes:
        member = tarfile.TarInfo("package/bin/npm-cli.js")
        member.size = len(payload)
        return cls._tarball(member, payload)

    def test_download_normalizes_urllib_and_timeout_oserrors(self) -> None:
        failures = (
            URLError("offline"),
            HTTPError(installer._NPM_TARBALL_URL, 503, "unavailable", None, None),
            TimeoutError("timed out"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                with patch.object(installer._OPENER, "open", side_effect=failure):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "CLOUDFLARE_NPM_DOWNLOAD_FAILED",
                    ):
                        installer._download_npm_tarball()

    def test_extract_accepts_regular_cli_member(self) -> None:
        payload = self._regular_npm_tarball(b"console.log('npm')")
        with tempfile.TemporaryDirectory() as raw_temp:
            destination = Path(raw_temp) / "npm"
            cli = installer._extract_npm(payload, destination)
            self.assertEqual(cli.read_bytes(), b"console.log('npm')")
            self.assertFalse(cli.is_symlink())

    def test_extract_rejects_special_member(self) -> None:
        member = tarfile.TarInfo("package/bin/npm-cli.js")
        member.type = tarfile.SYMTYPE
        member.linkname = "../../escape"
        payload = self._tarball(member)
        with tempfile.TemporaryDirectory() as raw_temp:
            destination = Path(raw_temp) / "npm"
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_NPM_TARBALL_MEMBER_INVALID",
            ):
                installer._extract_npm(payload, destination)
            self.assertFalse((destination / "package/bin/npm-cli.js").exists())

    def test_extract_enforces_unpacked_limit_before_write(self) -> None:
        payload = self._regular_npm_tarball(b"12345")
        with tempfile.TemporaryDirectory() as raw_temp:
            destination = Path(raw_temp) / "npm"
            with patch.object(installer, "_MAX_UNPACKED_BYTES", 4):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_NPM_TARBALL_UNPACKED_SIZE_INVALID",
                ):
                    installer._extract_npm(payload, destination)
            self.assertFalse((destination / "package/bin/npm-cli.js").exists())

    def test_extract_orchestrator_remains_decomposed(self) -> None:
        tree = ast.parse(inspect.getsource(installer._extract_npm))
        function = tree.body[0]
        self.assertIsInstance(function, ast.FunctionDef)
        branch_nodes = (
            ast.If,
            ast.For,
            ast.While,
            ast.Try,
            ast.IfExp,
            ast.Match,
        )
        self.assertLessEqual(
            sum(isinstance(node, branch_nodes) for node in ast.walk(function)),
            3,
        )
        call_names = {
            node.func.id
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue(
            {
                "_prepare_extract_destination",
                "_open_npm_archive",
                "_bounded_archive_members",
                "_validate_archive_member",
                "_write_archive_member",
            }.issubset(call_names)
        )


if __name__ == "__main__":
    unittest.main()
