"""Synthetic delivery fixtures; not Android signing or installation evidence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend import public_updates_app

PACKAGE = "ru.omnicio.app.debug"
FIXTURE_BYTES = b"\x00Analyst AI public-update fixture\xff\n"
CERTIFICATE = hashlib.sha256(b"synthetic test certificate identity").hexdigest()


def write_release_fixture(root: Path, *, code=36, payload=FIXTURE_BYTES):
    digest = hashlib.sha256(payload).hexdigest()
    filename = f"Analyst-AI-{code}-{digest}.apk"
    manifest = {
        "schema_version": 1, "package_name": PACKAGE, "version_code": code,
        "version_name": f"fixture-{code}", "apk_sha256": digest,
        "apk_bytes": len(payload), "certificate_sha256": CERTIFICATE,
        "min_sdk": 37, "published_at": 1_700_000_000,
        "notes": "Synthetic delivery fixture; no runtime certification.",
    }
    directory = root / PACKAGE
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_bytes(payload)
    encoded = json.dumps(manifest, sort_keys=True).encode("utf-8")
    (directory / f"{filename[:-4]}.json").write_bytes(encoded)
    (directory / "current.json").write_bytes(encoded)
    return manifest, filename


def assert_unavailable(response):
    assert response.status_code == 503
    assert response.json() == {"detail": "update_channel_unavailable"}
    assert response.headers["cache-control"] == "no-store"


@pytest.fixture
def public_client(tmp_path, monkeypatch):
    root = tmp_path / "public-releases"
    monkeypatch.setenv("ANDROID_RELEASE_DIR", str(root))
    monkeypatch.setenv("ANDROID_UPDATES_ENABLED", "true")
    forbidden = Mock(side_effect=AssertionError("public service accessed a database"))
    monkeypatch.setattr(public_updates_app, "_private_database_unavailable", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    with TestClient(public_updates_app.create_app()) as client:
        yield client, root
    forbidden.assert_not_called()


def test_policy_and_apk_follow_existing_contract(public_client):
    client, root = public_client
    manifest, filename = write_release_fixture(root)
    response = client.get("/client/update-policy")
    assert response.status_code == 200
    assert response.json() == {
        **manifest, "minimum_version_code": manifest["version_code"],
        "apk_path": f"/client/apk/{filename}", "version_is_not_attestation": True,
    }
    assert response.headers["cache-control"] == "no-store"
    assert {v.strip().lower() for v in response.headers["vary"].split(",")} == {
        "x-analyst-package", "x-analyst-version-code",
    }
    download = client.get(f"/client/apk/{filename}", params={"package_name": PACKAGE})
    assert download.status_code == 200
    assert download.content == FIXTURE_BYTES
    assert len(download.content) == manifest["apk_bytes"]
    assert hashlib.sha256(download.content).hexdigest() == manifest["apk_sha256"]
    assert download.headers["content-type"] == "application/vnd.android.package-archive"
    assert download.headers["content-length"] == str(len(FIXTURE_BYTES))
    assert download.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert filename in download.headers["content-disposition"]
    ready = client.post("/client/ready", headers={"Authorization": "Bearer synthetic-token"})
    assert ready.status_code == 401
    assert ready.json() == {"detail": "authentication_required"}


@pytest.mark.parametrize("enabled", ["false", "true"])
@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer synthetic-token"},
    {"Authorization": "Bearer synthetic-token", "X-Analyst-Package": PACKAGE,
     "X-Analyst-Version-Code": "999"},
    {"Authorization": "Basic synthetic-credentials"},
])
def test_ready_rejects_before_database(public_client, monkeypatch, enabled, headers):
    client, root = public_client
    monkeypatch.setenv("ANDROID_UPDATES_ENABLED", enabled)
    response = client.post("/client/ready", headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "authentication_required"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["www-authenticate"] == "Bearer"
    assert not root.exists()


def test_only_update_contract_routes_are_exposed(public_client):
    client, _ = public_client
    assert {route.path: frozenset(route.methods) for route in client.app.routes} == {
        "/client/update-policy": frozenset({"GET"}),
        "/client/ready": frozenset({"POST"}),
        "/client/apk/{filename}": frozenset({"GET"}),
    }
    for path in ("/docs", "/redoc", "/openapi.json", "/health", "/me", "/workspace",
                 "/auth/telegram/start", "/auth/telegram/owner-enrollment/callback"):
        assert client.get(path).status_code == 404


def test_no_publication_or_write_routes(public_client):
    client, root = public_client
    _, filename = write_release_fixture(root)
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    for method, path, status in (
        ("POST", "/client/update-policy", 405), ("PUT", "/client/update-policy", 405),
        ("DELETE", "/client/update-policy", 405), ("POST", f"/client/apk/{filename}", 405),
        ("PUT", f"/client/apk/{filename}", 405), ("DELETE", f"/client/apk/{filename}", 405),
        ("POST", "/client/publish", 404), ("POST", "/client/releases", 404),
    ):
        assert client.request(method, path, json={"version_code": 999}).status_code == status
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


def test_missing_channel_does_not_create_storage(public_client):
    client, root = public_client
    assert_unavailable(client.get("/client/update-policy"))
    assert_unavailable(client.get(f"/client/apk/Analyst-AI-36-{'a' * 64}.apk"))
    assert not root.exists()


@pytest.mark.parametrize("corruption", ["invalid_json", "unsupported_schema", "package_mismatch"])
def test_corrupt_manifests_are_unavailable(public_client, corruption):
    client, root = public_client
    manifest, filename = write_release_fixture(root)
    if corruption == "invalid_json":
        encoded = b'{"schema_version":'
    else:
        changed = dict(manifest)
        if corruption == "unsupported_schema":
            changed["schema_version"] = 999
        else:
            changed["package_name"] = "ru.omnicio.app"
        encoded = json.dumps(changed).encode()
    directory = root / PACKAGE
    (directory / "current.json").write_bytes(encoded)
    (directory / f"{filename[:-4]}.json").write_bytes(encoded)
    assert_unavailable(client.get("/client/update-policy"))
    assert_unavailable(client.get(f"/client/apk/{filename}"))


@pytest.mark.parametrize("corruption", ["missing", "wrong_size", "same_size"])
def test_missing_or_tampered_apk_is_unavailable(public_client, corruption):
    client, root = public_client
    _, filename = write_release_fixture(root)
    apk = root / PACKAGE / filename
    assert client.get("/client/update-policy").status_code == 200
    assert client.get(f"/client/apk/{filename}").status_code == 200
    old_stat = apk.stat()
    if corruption == "missing":
        apk.unlink()
    elif corruption == "wrong_size":
        apk.write_bytes(FIXTURE_BYTES + b"changed")
    else:
        changed = bytes([FIXTURE_BYTES[0] ^ 1]) + FIXTURE_BYTES[1:]
        assert len(changed) == len(FIXTURE_BYTES)
        apk.write_bytes(changed)
        os.utime(apk, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
    assert_unavailable(client.get("/client/update-policy"))
    assert_unavailable(client.get(f"/client/apk/{filename}"))


def test_retained_url_remains_immutable(public_client):
    client, root = public_client
    old_bytes = b"\x00synthetic older APK fixture\xff"
    old_manifest, old_name = write_release_fixture(root, code=35, payload=old_bytes)
    old_url = f"/client/apk/{old_name}"
    assert client.get(old_url).content == old_bytes
    new_manifest, new_name = write_release_fixture(root)
    policy = client.get("/client/update-policy")
    assert policy.status_code == 200
    assert policy.json()["version_code"] == new_manifest["version_code"]
    assert policy.json()["minimum_version_code"] == new_manifest["version_code"]
    assert policy.json()["apk_path"] == f"/client/apk/{new_name}"
    retained = client.get(old_url)
    assert retained.status_code == 200
    assert retained.content == old_bytes
    assert hashlib.sha256(retained.content).hexdigest() == old_manifest["apk_sha256"]
    assert "immutable" in retained.headers["cache-control"]
    (root / PACKAGE / "current.json").write_bytes(b"invalid current manifest")
    assert_unavailable(client.get("/client/update-policy"))
    assert client.get(old_url).content == old_bytes


def test_unknown_filenames_keep_existing_status_contract(public_client):
    client, root = public_client
    write_release_fixture(root)
    malformed = client.get("/client/apk/not-a-release.apk")
    assert malformed.status_code == 404
    assert malformed.json() == {"detail": "release_not_found"}
    assert_unavailable(client.get(f"/client/apk/Analyst-AI-999-{'a' * 64}.apk"))


def test_unknown_package_is_unavailable(public_client):
    client, root = public_client
    _, filename = write_release_fixture(root)
    parameters = {"package_name": "invalid.synthetic.package"}
    assert_unavailable(client.get("/client/update-policy", params=parameters))
    assert_unavailable(client.get(f"/client/apk/{filename}", params=parameters))
