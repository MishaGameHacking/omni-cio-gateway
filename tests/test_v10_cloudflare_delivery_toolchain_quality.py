from __future__ import annotations

import ast
import errno
from http.client import IncompleteRead
import inspect
import io
from pathlib import Path
import ssl
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock, patch
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

    @staticmethod
    def _response(payload: bytes = b"npm") -> MagicMock:
        response = MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.geturl.return_value = installer._NPM_TARBALL_URL
        response.read.return_value = payload
        return response

    def test_download_retries_transient_connection_then_succeeds(self) -> None:
        response = self._response(b"payload")
        with (
            patch.object(
                installer._OPENER,
                "open",
                side_effect=[ConnectionResetError(errno.ECONNRESET, "reset"), response],
            ) as open_request,
            patch.object(installer.time, "sleep") as sleep,
        ):
            payload = installer._download_npm_tarball()

        self.assertEqual(payload, b"payload")
        self.assertEqual(open_request.call_count, 2)
        sleep.assert_called_once_with(15.0)

    def test_download_retries_retryable_http_then_succeeds(self) -> None:
        response = self._response(b"payload")
        transient = HTTPError(
            installer._NPM_TARBALL_URL,
            503,
            "unavailable",
            None,
            None,
        )
        with (
            patch.object(installer._OPENER, "open", side_effect=[transient, response]),
            patch.object(installer.time, "sleep") as sleep,
        ):
            payload = installer._download_npm_tarball()

        self.assertEqual(payload, b"payload")
        sleep.assert_called_once_with(15.0)

    def test_download_exhausts_transient_failures_with_bounded_backoff(self) -> None:
        failures = [
            HTTPError(
                installer._NPM_TARBALL_URL,
                503,
                "unavailable",
                None,
                None,
            )
            for _ in range(installer._DOWNLOAD_ATTEMPTS)
        ]
        with (
            patch.object(
                installer._OPENER,
                "open",
                side_effect=failures,
            ) as open_request,
            patch.object(installer.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"CLOUDFLARE_NPM_DOWNLOAD_RETRY_EXHAUSTED HTTP status=503 attempts=5",
            ):
                installer._download_npm_tarball()

        self.assertEqual(open_request.call_count, 5)
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            [15.0, 30.0, 45.0, 60.0],
        )

    def test_download_retry_log_does_not_expose_exception_details(self) -> None:
        response = self._response(b"payload")
        stderr = io.StringIO()
        failure = ConnectionResetError(errno.ECONNRESET, "sensitive-route-detail")
        with (
            patch.object(
                installer._OPENER,
                "open",
                side_effect=[failure, response],
            ),
            patch.object(installer.time, "sleep"),
            patch.object(installer.sys, "stderr", stderr),
        ):
            payload = installer._download_npm_tarball()

        self.assertEqual(payload, b"payload")
        log = stderr.getvalue()
        self.assertIn("TRANSPORT class=CONNECTION", log)
        self.assertNotIn("sensitive-route-detail", log)
        self.assertNotIn(installer._NPM_TARBALL_URL, log)

    def test_download_http_retry_policy_is_explicit_and_bounded(self) -> None:
        for status in (408, 429, 500, 503, 599):
            with self.subTest(status=status):
                self.assertTrue(installer._retryable_http_status(status))
        for status in (400, 401, 403, 404, 499, 600):
            with self.subTest(status=status):
                self.assertFalse(installer._retryable_http_status(status))

    def test_download_does_not_retry_permanent_http_failure(self) -> None:
        failure = HTTPError(
            installer._NPM_TARBALL_URL,
            403,
            "forbidden",
            None,
            None,
        )
        with (
            patch.object(
                installer._OPENER,
                "open",
                side_effect=failure,
            ) as open_request,
            patch.object(installer.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"CLOUDFLARE_NPM_HTTP_STATUS_PERMANENT status=403",
            ):
                installer._download_npm_tarball()

        open_request.assert_called_once()
        sleep.assert_not_called()

    def test_download_does_not_retry_redirect(self) -> None:
        failure = HTTPError(
            installer._NPM_TARBALL_URL,
            302,
            "redirect",
            None,
            None,
        )
        with (
            patch.object(
                installer._OPENER,
                "open",
                side_effect=failure,
            ) as open_request,
            patch.object(installer.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_NPM_REDIRECT_FORBIDDEN",
            ):
                installer._download_npm_tarball()

        open_request.assert_called_once()
        sleep.assert_not_called()

    def test_download_does_not_retry_tls_certificate_failure(self) -> None:
        certificate_failure = ssl.SSLCertVerificationError(
            1, "certificate verify failed"
        )
        failure = URLError(certificate_failure)
        with (
            patch.object(
                installer._OPENER,
                "open",
                side_effect=failure,
            ) as open_request,
            patch.object(installer.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"CLOUDFLARE_NPM_TRANSPORT_NON_RETRYABLE class=TLS_CERTIFICATE",
            ):
                installer._download_npm_tarball()

        open_request.assert_called_once()
        sleep.assert_not_called()

    def test_download_retries_abrupt_tls_eof_then_succeeds(self) -> None:
        response = self._response(b"payload")
        failure = URLError(ssl.SSLEOFError(8, "abrupt TLS EOF"))
        with (
            patch.object(
                installer._OPENER,
                "open",
                side_effect=[failure, response],
            ) as open_request,
            patch.object(installer.time, "sleep") as sleep,
        ):
            payload = installer._download_npm_tarball()

        self.assertEqual(payload, b"payload")
        self.assertEqual(open_request.call_count, 2)
        sleep.assert_called_once_with(15.0)

    def test_download_does_not_retry_generic_tls_failure(self) -> None:
        failure = URLError(ssl.SSLError(1, "TLS protocol failure"))
        with (
            patch.object(
                installer._OPENER,
                "open",
                side_effect=failure,
            ) as open_request,
            patch.object(installer.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"CLOUDFLARE_NPM_TRANSPORT_NON_RETRYABLE class=TLS",
            ):
                installer._download_npm_tarball()

        open_request.assert_called_once()
        sleep.assert_not_called()

    def test_download_retries_incomplete_read(self) -> None:
        response = self._response(b"payload")
        with (
            patch.object(
                installer._OPENER,
                "open",
                side_effect=[IncompleteRead(b"partial", 100), response],
            ),
            patch.object(installer.time, "sleep") as sleep,
        ):
            payload = installer._download_npm_tarball()

        self.assertEqual(payload, b"payload")
        sleep.assert_called_once_with(15.0)

    def test_download_unknown_url_failure_is_non_retryable(self) -> None:
        failure = URLError("offline")
        with (
            patch.object(
                installer._OPENER,
                "open",
                side_effect=failure,
            ) as open_request,
            patch.object(installer.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"CLOUDFLARE_NPM_TRANSPORT_NON_RETRYABLE class=URL_ERROR",
            ):
                installer._download_npm_tarball()

        open_request.assert_called_once()
        sleep.assert_not_called()

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

    def test_capture_version_fails_closed_on_empty_success_output(self) -> None:
        completed = subprocess.CompletedProcess(
            args=("tool", installer._VERSION_FLAG),
            returncode=0,
            stdout=" \r\n",
            stderr="",
        )
        with patch.object(installer.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_TEST_VERSION_INVALID",
            ):
                installer._capture_version(
                    ("tool", installer._VERSION_FLAG),
                    "CLOUDFLARE_TEST_VERSION_INVALID",
                )


if __name__ == "__main__":
    unittest.main()
