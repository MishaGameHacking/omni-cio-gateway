from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts import bootstrap_v10_cloudflare_neon_hosted_egress as hosted


_EXPECTED_SHA = "a" * 40
_STAGING_ORIGIN = "https://omni-cio-v10-web-staging.example.workers.dev"
_BOOTSTRAP_ORIGIN = (
    "https://br-test1234-cfdprodbootstrap.compute.c-6."
    "eu-central-1.aws.neon.tech/"
)


class CloudflareNeonHostedEgressTests(unittest.TestCase):
    def test_staging_bootstrap_writes_cloudflare_secret_in_same_job(self) -> None:
        api = mock.Mock()
        with (
            mock.patch.object(hosted.runtime, "run") as runtime_run,
            mock.patch.object(hosted, "_cloudflare_api", return_value=api),
            mock.patch.object(hosted, "put_staging_runtime_secret") as put_secret,
        ):
            hosted.bootstrap_staging(_EXPECTED_SHA)
        runtime_run.assert_called_once_with(_EXPECTED_SHA, "staging")
        put_secret.assert_called_once_with(api)

    def test_production_custody_resync_uses_exact_staging_release(self) -> None:
        api = mock.Mock()
        token_context = mock.MagicMock()
        token_context.__enter__.return_value = "0" * 64
        token_context.__exit__.return_value = False
        with (
            mock.patch.object(
                hosted.builds,
                "_staging_url",
                return_value=_STAGING_ORIGIN,
            ),
            mock.patch.object(hosted, "assert_staging_exact_release") as exact_release,
            mock.patch.object(
                hosted,
                "bootstrap_origin_sync_token",
                return_value=token_context,
            ) as sync_token,
            mock.patch.object(
                hosted,
                "fetch_bootstrap_origin_custody",
                return_value=_BOOTSTRAP_ORIGIN,
            ) as fetch_custody,
            mock.patch.object(hosted, "write_bootstrap_origin_handoff") as write_handoff,
        ):
            hosted._resync_production_branch_custody(api, _EXPECTED_SHA)

        exact_release.assert_called_once_with(_STAGING_ORIGIN, _EXPECTED_SHA)
        sync_token.assert_called_once_with(api)
        fetch_custody.assert_called_once_with(
            staging_origin=_STAGING_ORIGIN,
            expected_sha=_EXPECTED_SHA,
            token="0" * 64,
        )
        write_handoff.assert_called_once_with(_BOOTSTRAP_ORIGIN)

    def test_production_bootstrap_resyncs_before_canonical_runtime(self) -> None:
        api = mock.Mock()
        order: list[str] = []

        def resync(*_args: object, **_kwargs: object) -> None:
            order.append("custody")

        def run(*_args: object, **_kwargs: object) -> None:
            order.append("runtime")

        def put_secret(*_args: object, **_kwargs: object) -> None:
            order.append("secret")

        with (
            mock.patch.object(hosted, "_cloudflare_api", return_value=api),
            mock.patch.object(
                hosted,
                "_resync_production_branch_custody",
                side_effect=resync,
            ),
            mock.patch.object(hosted.runtime, "run", side_effect=run),
            mock.patch.object(
                hosted.production,
                "put_runtime_secret",
                side_effect=put_secret,
            ),
        ):
            hosted.bootstrap_production(_EXPECTED_SHA)

        self.assertEqual(order, ["custody", "runtime", "secret"])

    def test_production_runtime_is_not_called_when_custody_resync_fails(self) -> None:
        api = mock.Mock()
        with (
            mock.patch.object(hosted, "_cloudflare_api", return_value=api),
            mock.patch.object(
                hosted,
                "_resync_production_branch_custody",
                side_effect=hosted.builds.BootstrapStopped(
                    "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAVAILABLE"
                ),
            ),
            mock.patch.object(hosted.runtime, "run") as runtime_run,
            mock.patch.object(hosted.production, "put_runtime_secret") as put_secret,
        ):
            with self.assertRaisesRegex(
                hosted.builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAVAILABLE",
            ):
                hosted.bootstrap_production(_EXPECTED_SHA)
        runtime_run.assert_not_called()
        put_secret.assert_not_called()

    def test_resync_does_not_log_raw_bootstrap_origin(self) -> None:
        api = mock.Mock()
        token_context = mock.MagicMock()
        token_context.__enter__.return_value = "0" * 64
        token_context.__exit__.return_value = False
        output = io.StringIO()
        with (
            mock.patch.object(
                hosted.builds,
                "_staging_url",
                return_value=_STAGING_ORIGIN,
            ),
            mock.patch.object(hosted, "assert_staging_exact_release"),
            mock.patch.object(
                hosted,
                "bootstrap_origin_sync_token",
                return_value=token_context,
            ),
            mock.patch.object(
                hosted,
                "fetch_bootstrap_origin_custody",
                return_value=_BOOTSTRAP_ORIGIN,
            ),
            mock.patch.object(hosted, "write_bootstrap_origin_handoff"),
            redirect_stdout(output),
        ):
            hosted._resync_production_branch_custody(api, _EXPECTED_SHA)
        self.assertNotIn(_BOOTSTRAP_ORIGIN, output.getvalue())
        self.assertNotIn("br-test1234", output.getvalue())
        self.assertIn(
            "CLOUDFLARE_NEON_HOSTED_PRODUCTION_BRANCH_CUSTODY=READY",
            output.getvalue(),
        )

    def test_hosted_control_plane_projection_uses_canonical_lock_only(self) -> None:
        from scripts import build_v10_cloudflare_hosted_control_plane_lock as lock

        source = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
            encoding="utf-8"
        )
        rendered = lock.render_hosted_control_plane_lock(source)
        expected = {
            "annotated-types": "0.8.0",
            "pydantic": "2.13.4",
            "pydantic-core": "2.46.4",
            "psycopg": "3.3.4",
            "psycopg-binary": "3.3.4",
            "typing-extensions": "4.16.0",
            "typing-inspection": "0.4.2",
        }
        self.assertEqual(lock.required_versions(), expected)
        for package, version in expected.items():
            self.assertIn(f"{package}=={version}", rendered)
        rendered_packages = {
            parsed[0]
            for line in rendered.splitlines()
            if (parsed := lock._parse_header(line)) is not None
        }
        self.assertEqual(rendered_packages, set(expected))
        for forbidden in ("fastapi", "httpx", "starlette", "tzdata", "uvicorn"):
            self.assertNotIn(f"{forbidden}==", rendered)
        self.assertIn("--hash=sha256:", rendered)

    def test_hosted_control_plane_projection_fails_closed_on_version_drift(
        self,
    ) -> None:
        from scripts import build_v10_cloudflare_hosted_control_plane_lock as lock

        source = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
            encoding="utf-8"
        )
        drifted = source.replace("pydantic==2.13.4", "pydantic==2.13.5", 1)
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_HOSTED_LOCK_VERSION_DRIFT:pydantic",
        ):
            lock.render_hosted_control_plane_lock(drifted)

    def test_hosted_control_plane_installed_verifier_covers_projection(self) -> None:
        from scripts import build_v10_cloudflare_hosted_control_plane_lock as lock

        expected = lock.required_versions()
        with mock.patch.object(
            lock.metadata,
            "version",
            side_effect=expected.__getitem__,
        ) as version:
            lock.verify_installed_control_plane_versions()
        self.assertEqual(
            [call.args[0] for call in version.call_args_list],
            list(expected),
        )

    def test_hosted_control_plane_lock_path_is_runner_temp_bounded(self) -> None:
        from scripts import build_v10_cloudflare_hosted_control_plane_lock as lock

        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {"RUNNER_TEMP": directory}, clear=False):
                self.assertEqual(
                    lock.hosted_lock_path(),
                    Path(directory).resolve()
                    / "omni-cio-v10-cloudflare-hosted-control-plane.txt",
                )

    def test_main_sanitizes_legacy_handoff_failure(self) -> None:
        output = io.StringIO()
        error = io.StringIO()
        with (
            mock.patch.object(
                hosted,
                "bootstrap_production",
                side_effect=hosted.LegacyBootstrapStopped("HANDOFF_INVALID"),
            ),
            mock.patch("sys.stdout", output),
            mock.patch("sys.stderr", error),
        ):
            rc = hosted.main(
                ["bootstrap-production", "--expected-sha", _EXPECTED_SHA]
            )
        self.assertEqual(rc, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("code=HANDOFF_INVALID", error.getvalue())


if __name__ == "__main__":
    unittest.main()
