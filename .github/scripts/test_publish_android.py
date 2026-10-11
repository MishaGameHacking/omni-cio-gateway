"""Publishing must fail closed without uploading a broken or unaccepted build."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import publish_android as publisher

SHA = "a" * 40
TAG = f"android-debug-{SHA}-123-1"
URL = f"https://github.com/{publisher.gate.REPOSITORY}/releases/tag/{TAG}"


def asset(name: str, data: bytes) -> dict[str, object]:
    return {"name": name, "size": len(data), "state": "uploaded",
            "digest": "sha256:" + hashlib.sha256(data).hexdigest()}


def release_api() -> Mock:
    api = Mock(spec=publisher.ReleaseAPI)
    api.request.side_effect = [
        {"id": 55, "tag_name": TAG, "target_commitish": SHA, "draft": True},
        asset("app.apk", b"apk"), {"assets": [asset("app.apk", b"apk")]},
        {"commit": {"sha": SHA}}, {"draft": False, "prerelease": True, "html_url": URL},
        {"object": {"sha": SHA}},
    ]
    return api


class PublishTests(unittest.TestCase):
    def test_publish_only_after_upload_readback_and_current_main(self) -> None:
        api = release_api()
        self.assertEqual(
            publisher.publish(api, SHA, "123", "1", "2.7.0-debug", {"app.apk": b"apk"}), URL,
        )
        calls = api.request.call_args_list
        create = json.loads(calls[0].kwargs["body"])
        self.assertTrue(create["draft"])
        self.assertTrue(create["prerelease"])
        self.assertEqual(create["target_commitish"], SHA)
        self.assertEqual(calls[3].args, ("GET", "/branches/main"))
        self.assertEqual(calls[4].args, ("PATCH", "/releases/55"))

    def test_corrupt_or_missing_upload_never_publishes_the_draft(self) -> None:
        changesets = ({"digest": "wrong"}, {"size": 999}, {"state": "starter"}, {"name": "other"})
        for changes in changesets:
            api = release_api()
            api.request.side_effect = [
                {"id": 55, "tag_name": TAG, "target_commitish": SHA, "draft": True},
                asset("app.apk", b"apk") | changes,
            ]
            with self.subTest(changes=changes), self.assertRaises(publisher.gate.ReleaseBlocked):
                publisher.publish(api, SHA, "123", "1", "2.7.0-debug", {"app.apk": b"apk"})
            self.assertEqual(api.request.call_count, 2)

    def test_main_movement_keeps_uploaded_release_private_as_draft(self) -> None:
        api = release_api()
        api.request.side_effect = [
            {"id": 55, "tag_name": TAG, "target_commitish": SHA, "draft": True},
            asset("app.apk", b"apk"), {"assets": [asset("app.apk", b"apk")]},
            {"commit": {"sha": "b" * 40}},
        ]
        with self.assertRaisesRegex(publisher.gate.ReleaseBlocked, "Main changed"):
            publisher.publish(api, SHA, "123", "1", "2.7.0-debug", {"app.apk": b"apk"})
        self.assertEqual(api.request.call_count, 4)

    def test_non_main_or_non_manual_context_has_no_write_side_effects(self) -> None:
        valid = {"GITHUB_REPOSITORY": publisher.gate.REPOSITORY, "GITHUB_SHA": SHA,
                 "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch",
                 "GITHUB_TOKEN": "synthetic-token"}
        for changes in ({"GITHUB_EVENT_NAME": "pull_request"}, {"GITHUB_EVENT_NAME": "push"},
                        {"GITHUB_REF": "refs/heads/feature"}, {"GITHUB_REPOSITORY": "other/repo"}):
            with patch.dict(os.environ, valid | changes, clear=True), \
                    patch.object(publisher, "ReleaseAPI") as api, \
                    contextlib.redirect_stdout(io.StringIO()), self.subTest(changes=changes):
                self.assertEqual(publisher.main(), 1)
                api.assert_not_called()

    def test_failed_acceptance_gate_stops_before_release_api_is_created(self) -> None:
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_dispatch",
                                     "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}), \
                patch.object(publisher.gate, "release_context", return_value=(SHA, "token")), \
                patch.object(publisher.gate, "require_checkout"), \
                patch.object(publisher, "build_assets", return_value=("2.7.0-debug", {})), \
                patch.object(publisher.gate, "wait_for_main_release",
                             side_effect=publisher.gate.ReleaseBlocked("tests failed")), \
                patch.object(publisher, "ReleaseAPI") as api, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(publisher.main(), 1)
            api.assert_not_called()

    def test_transport_redirects_never_receive_the_write_token(self) -> None:
        connection = Mock()
        connection.getresponse.return_value = Mock(status=302)
        api = publisher.ReleaseAPI("test-token")
        with (
            patch.object(
                publisher.http.client, "HTTPSConnection", return_value=connection,
            ) as https,
            self.assertRaises(publisher.gate.ReleaseBlocked),
        ):
            api.request("POST", "/releases")
        https.assert_called_once_with("api.github.com", timeout=120)
        connection.close.assert_called_once()


class BuildAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directory = self.root / "app/build/outputs/apk/debug"
        self.directory.mkdir(parents=True)
        self.metadata = {"applicationId": "ru.omnicio.app.debug", "variantName": "debug",
                         "elements": [{"versionName": "2.7.0-debug", "versionCode": 10,
                                       "outputFile": "app-debug.apk"}]}
        (self.directory / "app-debug.apk").write_bytes(b"synthetic APK test fixture")
        signing = self.root / "artifacts/android/apksigner.txt"
        signing.parent.mkdir(parents=True)
        signing.write_text("Signer #1 certificate SHA-256 digest: " + "c" * 64, encoding="utf-8")
        self.save_metadata()

    def save_metadata(self) -> None:
        (self.directory / "output-metadata.json").write_text(
            json.dumps(self.metadata), encoding="utf-8",
        )

    def test_manifest_and_checksums_bind_all_downloads_to_exact_build(self) -> None:
        version, assets = publisher.build_assets(self.root, SHA, "123", "1")
        self.assertEqual(version, "2.7.0-debug")
        manifest = json.loads(assets["android-build.json"])
        self.assertEqual(manifest["commit"], SHA)
        self.assertEqual(manifest["certificate_sha256"], "c" * 64)
        for line in assets["SHA256SUMS.txt"].decode().splitlines():
            digest, name = line.split("  ")
            self.assertEqual(digest, hashlib.sha256(assets[name]).hexdigest())

    def test_wrong_package_and_split_build_cannot_be_published(self) -> None:
        for changes in ({"applicationId": "ru.omnicio.app"}, {"variantName": "release"},
                        {"elements": []}):
            with self.subTest(changes=changes):
                original = self.metadata
                self.metadata = self.metadata | changes
                self.save_metadata()
                with self.assertRaises(publisher.gate.ReleaseBlocked):
                    publisher.build_assets(self.root, SHA, "123", "1")
                self.metadata = original

    def test_missing_signature_proof_cannot_be_published(self) -> None:
        (self.root / "artifacts/android/apksigner.txt").write_text(
            "verification failed", encoding="utf-8",
        )
        with self.assertRaisesRegex(publisher.gate.ReleaseBlocked, "certificate"):
            publisher.build_assets(self.root, SHA, "123", "1")


if __name__ == "__main__":
    unittest.main()
