"""Publish a verified one-time shell through the existing immutable update channel."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import zipfile

PACKAGE = "ru.omnicio.app.debug"
CERT = "bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"
OLD_SHA = "9940c994d3e6695708fe65d64e378c6d998c8891ae69bbaa1c20df17008dbb6e"
OLD_BYTES = 29937843
ROOT = Path("/srv/analyst-ai-ota/releases")


def need(value, code):
    if not value:
        raise RuntimeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path, limit):
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit
         and path.resolve(strict=True) == path and not info.st_mode & 0o022, "untrusted_file")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        raw = stream.read(limit + 1)
    need(len(raw) <= limit, "file_too_large")
    return raw


def save_new(path, raw):
    if path.exists() or path.is_symlink():
        need(regular(path, len(raw)) == raw, "existing_file_conflict")
        return
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def verify_runtime(meta):
    run_id = meta["runtime_deploy_run_id"]
    need(re.fullmatch("[0-9]{8,20}", run_id), "invalid_runtime_run")
    path = Path("/var/lib/analyst-ai-build/development") / ("server-runtime-" + run_id) / "deployment.json"
    receipt = json.loads(regular(path, 16384))
    need(receipt["status"] == "deployed" and receipt["source_commit"] == meta["source_commit"]
         and receipt["test_run_id"] == meta["test_run_id"]
         and receipt["unauthenticated_presentation"] == 401, "required_runtime_not_deployed")
    for name, expected in receipt["installed_sha256"].items():
        need(re.fullmatch("[a-z_]+\\.py", name), "invalid_runtime_module")
        need(sha(regular(Path("/opt/analyst-ai/backend") / name, 512 * 1024)) == expected, "runtime_changed")


def unpack(meta, payload):
    need(len(payload) == meta["payload_bytes"] and sha(payload) == meta["payload_sha256"], "payload_changed")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        need(set(archive.namelist()) == set(meta["members"]) == {"app-preview.apk", "apk-verification.json", "build-result.json"}
             and len(archive.namelist()) == len(meta["members"]) == 3, "unexpected_payload_members")
        members = {}
        for name, identity in meta["members"].items():
            need(archive.getinfo(name).file_size == identity["bytes"], "member_size_changed")
            raw = archive.read(name)
            need(len(raw) == identity["bytes"] and sha(raw) == identity["sha256"], "member_changed")
            members[name] = raw
    return members


def publish(meta, folder, members):
    sys.path.insert(0, "/opt/analyst-ai")
    from backend.client_updates import AndroidRelease, ReleaseChannel
    from backend.release_lock import publication_lock
    from backend.release_publication import _require_apk_evidence, _require_android_floor, _existing_current, _resume_prepared, _stage_candidate
    apk = members["app-preview.apk"]
    report = json.loads(members["apk-verification.json"])
    build = json.loads(members["build-result.json"])
    need(build["source_commit"] == meta["source_commit"] and build["status"] == "passed"
         and build["owned_processes_after"] == 0 and build["apk"] == report, "build_receipt_changed")
    need(report["package"] == PACKAGE and report["version_code"] == 50
         and report["version_name"] == "0.14.3-preview" and sha(apk) == meta["apk_sha256"]
         and len(apk) == meta["apk_bytes"], "apk_identity_changed")
    _require_apk_evidence(report, sha256=meta["apk_sha256"], size=meta["apk_bytes"], certificate=CERT)
    _require_android_floor(report)
    notes = ("Переходная оболочка: версия работающей системы поступает с Timeweb. "
             "Оформление и защита экрана сохраняются на сервере. Дальнейшие совместимые "
             "обновления серверных алгоритмов и данных не требуют нового APK.")
    candidate = AndroidRelease.parse({"schema_version": 1, "package_name": PACKAGE,
        "version_code": 50, "version_name": "0.14.3-preview", "apk_sha256": meta["apk_sha256"],
        "apk_bytes": meta["apk_bytes"], "certificate_sha256": CERT, "min_sdk": 37,
        "published_at": int(time.time()), "notes": notes})
    directory = ROOT / PACKAGE
    channel = ReleaseChannel(ROOT)
    with publication_lock(directory):
        old = channel.current(PACKAGE)
        need(old.certificate_sha256 == CERT, "previous_certificate_changed")
        previous = old.version_code == 49 and old.apk_sha256 == OLD_SHA and old.apk_bytes == OLD_BYTES
        resumed = old.version_code == 50 and old.apk_sha256 == meta["apk_sha256"] and old.apk_bytes == len(apk)
        need(previous or resumed, "unexpected_current_release")
        if previous:
            save_new(folder / "previous-current.json", regular(directory / "current.json", 16384))
        else:
            baseline = AndroidRelease.parse(json.loads(regular(folder / "previous-current.json", 16384)))
            need(baseline.version_code == 49 and baseline.apk_sha256 == OLD_SHA
                 and baseline.certificate_sha256 == CERT, "previous_release_receipt_changed")
        existing = _existing_current(channel, directory, candidate)
        if existing is not None:
            candidate = existing
        else:
            candidate = _resume_prepared(channel, directory, candidate)
            with tempfile.TemporaryDirectory(prefix="shell50-", dir=folder) as temporary:
                path = Path(temporary) / "candidate.apk"
                save_new(path, apk)
                _stage_candidate(channel, directory, candidate, path)
        current = channel.current(PACKAGE)
        need(current == candidate and sha(regular(channel.verified_file(current), len(apk))) == meta["apk_sha256"],
             "channel_activation_failed")
    return {**meta, "status": "published", "version_code": 50, "version_name": current.version_name,
            "certificate_sha256": CERT, "published_at": current.published_at,
            "url": "https://analyst-ai-2941515.twc1.net/client/apk/" + current.filename,
            "previous_version_code": 49, "physical_phone_verified": False,
            "full_native_matrix_passed": False, "backend_deployment_performed": False}


def main():
    need(os.getuid() == 0, "root_required")
    meta = ENVELOPE["meta"]
    need(re.fullmatch("[a-f0-9]{40}", meta["source_commit"]), "invalid_source_commit")
    need(re.fullmatch("[0-9]{8,20}", meta["delivery_run_id"]), "invalid_delivery_run")
    verify_runtime(meta)
    payload = sys.stdin.buffer.read(128 * 1024**2 + 1)
    need(len(payload) <= 128 * 1024**2, "payload_too_large")
    members = unpack(meta, payload)
    parent = Path("/var/lib/analyst-ai-build/incoming")
    need(parent.resolve(strict=True) == parent and parent.is_dir()
         and parent.stat().st_uid == 0 and not parent.stat().st_mode & 0o022, "untrusted_incoming")
    folder = parent / ("server-shell-" + meta["delivery_run_id"])
    folder.mkdir(mode=0o700, exist_ok=True)
    need(folder.resolve(strict=True) == folder and folder.stat().st_uid == 0
         and not folder.stat().st_mode & 0o077, "untrusted_archive")
    save_new(folder / "payload.zip", payload)
    save_new(folder / "source-build.json", encoded(meta))
    receipt = publish(meta, folder, members)
    save_new(folder / "publication.json", encoded(receipt))
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
