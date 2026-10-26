"""Render the reviewed theme46 union for the existing Windows development runner.

Administrative preparation only. This reads evidence/source bytes, computes
identities and writes a new context directory. It never applies a checkout,
imports application code, runs tests, compiles, dispatches or publishes.
"""
from __future__ import annotations

import argparse
import ast
import base64
import copy
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import zlib

import yaml

CONTEXT = Path(__file__).resolve().parent
ROOT = CONTEXT.parent
ADMIN45_SHA = "69bfb8dbefd2cb3ce7bbf03dbd3bbbaf90c66b8b6fb5d38873a6f27e878ecf9a"
NATIVE45_SHA = "6b9a7a7787cb295243e726db48c9fa90ccf41124c9e0db1c6f0a16a8397197ed"
PACKAGES = {
    "core": CONTEXT / "theme46-core-ime-viewport",
    "assets": CONTEXT / "theme46-assets",
    "lifecycle": CONTEXT / "theme46-lifecycle",
    "quotes": CONTEXT / "quote-reset46",
}
GRADLE = "app/build.gradle.kts"
ANDROID_TEST = ".github/scripts/tests/test_android17_live_spectrum.py"
BRAND_TEST = ".github/scripts/tests/test_spectrum_brand_identity.py"
VERSION_REPLACEMENTS = {
    GRADLE: ((b"versionCode = 45", b"versionCode = 46"),
             (b'versionName = "0.13.7"', b'versionName = "0.13.8"')),
    ANDROID_TEST: ((b"versionCode = 45", b"versionCode = 46"),
                   (b'versionName = "0.13.7"', b'versionName = "0.13.8"')),
    BRAND_TEST: ((b"self.assertEqual(int(version.group(1)), 44)",
                  b"self.assertEqual(int(version.group(1)), 46)"),
                 (b'versionName = "0.13.6"', b'versionName = "0.13.8"')),
}


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def json_bytes(value, *, compact=False):
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":")) if compact
            else json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode()


def read(path, expected=None, maximum=8 * 1024**2):
    path = Path(path).absolute()
    need(CONTEXT in path.parents and path.resolve(strict=True) == path and not path.is_symlink(),
         "Input must be a canonical context file")
    before = path.stat()
    need(path.is_file() and before.st_nlink == 1 and 0 < before.st_size <= maximum, "Invalid context file")
    raw = path.read_bytes()
    after = path.stat()
    need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "Input changed while reading")
    need(expected is None or digest(raw) == expected, "Input identity changed: " + str(path))
    return raw


def evidence(spec):
    need(isinstance(spec, dict) and set(spec) == {"path", "sha256"}
         and re.fullmatch(r"[a-f0-9]{64}", spec["sha256"]), "Invalid evidence descriptor")
    return json.loads(read(spec["path"], spec["sha256"]))


def administrative_module(name, path, expected):
    read(path, expected)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_path(name):
    p = PurePosixPath(name)
    need(p.as_posix() == name and not p.is_absolute() and ".." not in p.parts
         and not any(x in name for x in ("\\", ":", "\0", "\n", "\r"))
         and (name.startswith(("app/", "ci-ui-driver/", "backend/", ".github/scripts/"))),
         "Unreviewed source path: " + name)
    return name


def actual_base(name, inventory, prior_rows):
    identity = inventory["files"].get(name)
    if identity is None:
        return None
    if name in prior_rows:
        raw = prior_rows[name]["content"].encode()
    else:
        # The local reference is read-only and older; every byte is bound to
        # the actual Windows45 inventory before it can be used as a base.
        candidate = ROOT / "analyst-ai" / name
        need(candidate.resolve(strict=True) == candidate and not candidate.is_symlink()
             and candidate.stat().st_nlink == 1, "Base reference must be canonical")
        raw = candidate.read_bytes()
    need(identity == {"bytes": len(raw), "sha256": digest(raw)}, "Base45 bytes differ: " + name)
    return raw


def package_rows(kind, spec):
    manifest = evidence(spec)
    need(Path(spec["path"]).absolute() == PACKAGES[kind] / "manifest.json", "Unexpected package manifest path")
    if kind in {"core", "lifecycle"}:
        need(manifest.get("frozen") is True, "Theme package not frozen: " + kind)
    need(manifest.get("application_or_tests_executed", manifest.get("application_or_test_execution", False)) is False,
         "Package must describe preparation, not invented execution")
    entries = manifest.get("source_files", manifest.get("files"))
    need(isinstance(entries, list) and entries, "Missing source manifest: " + kind)
    result = {}
    for row in entries:
        name = source_path(row["path"])
        need(name not in result, "Duplicate package source")
        raw = read(PACKAGES[kind] / "source" / name, row["new_sha256"])
        size = row.get("new_bytes", row.get("bytes"))
        need(type(size) is int and size == len(raw), "Source byte count differs: " + name)
        if "content" in row:
            need(row["content"].encode() == raw, "Manifest content differs from source copy")
        if row.get("new_git_blob"):
            need(git_blob(raw) == row["new_git_blob"], "New Git identity differs")
        result[name] = (raw, row)
    return result


def prepare(request, destination):
    need(set(request) == {"schema", "verified45_request", "packages"} and request["schema"] == 1
         and set(request["packages"]) == set(PACKAGES), "Unexpected theme46 preparation request")
    native45 = administrative_module("reviewed_native45_for_theme46", CONTEXT / "prepare_native45_counter.py", NATIVE45_SHA)
    actual45_request = evidence(request["verified45_request"])
    _, _, prior_provenance, _, _ = native45.validate(actual45_request)
    base = actual45_request["source_backup_commit"]
    source = actual45_request["source_sha256"]
    inventory = evidence(actual45_request["source_inventory"])
    prior_rows = {row["path"]: row for row in evidence(actual45_request["reviewed_manifest"])["files"]}
    helper = administrative_module("reviewed_build45_for_theme46", CONTEXT / "prepare_candidate45.py", ADMIN45_SHA)
    helper.verify_transport_source()
    assembled, owners = {}, {}
    for kind in PACKAGES:
        for name, (raw, metadata) in package_rows(kind, request["packages"][kind]).items():
            need(name not in assembled, "Package overlap must be reviewed and merged before freeze: " + name)
            old = actual_base(name, inventory, prior_rows)
            if name != BRAND_TEST:
                need(metadata.get("old_sha256") == (digest(old) if old is not None else None),
                     "Prepared package is not based on actual45 source: " + name)
            else:
                # Asset review started at44, while strict versions were moved
                # to45 by the panel build. Only those assertions are managed here.
                need(kind == "assets" and old is not None, "Unexpected version-test owner")
                before44 = old.replace(b"self.assertEqual(int(version.group(1)), 45)",
                                       b"self.assertEqual(int(version.group(1)), 44)")
                before44 = before44.replace(b'versionName = "0.13.7"', b'versionName = "0.13.6"')
                need(digest(before44) == metadata["old_sha256"], "Asset test has changes beyond the prior version bump")
            assembled[name] = raw
            owners[name] = kind
    need(GRADLE not in assembled and ANDROID_TEST in assembled and BRAND_TEST in assembled,
         "Unexpected version-managed union")
    assembled[GRADLE] = actual_base(GRADLE, inventory, prior_rows)
    owners[GRADLE] = "version"
    for name, pairs in VERSION_REPLACEMENTS.items():
        raw = assembled[name]
        for old, new in pairs:
            need(raw.count(old) == 1 and new not in raw, "Strict version anchor changed: " + name)
            raw = raw.replace(old, new, 1)
        assembled[name] = raw
    need(60 <= len(assembled) <= 90, "Unexpected frozen theme46 scope")
    need(len({name.casefold() for name in assembled}) == len(assembled), "Case-folded source collision")
    rows, diff = [], []
    for name in sorted(assembled):
        raw, old = assembled[name], actual_base(name, inventory, prior_rows)
        need(raw != old and b"\0" not in raw, "Unchanged or invalid source")
        raw.decode("utf-8")
        if name.endswith(".py"):
            ast.parse(raw, filename=name)
        rows.append({"path": name, "old_git_blob": git_blob(old) if old is not None else None,
                     "old_sha256": digest(old) if old is not None else None,
                     "old_bytes": len(old) if old is not None else None,
                     "new_sha256": digest(raw), "new_bytes": len(raw), "content": raw.decode()})
        diff.extend(difflib.unified_diff((old or b"").decode().splitlines(keepends=True),
                    raw.decode().splitlines(keepends=True), fromfile="a/" + name, tofile="b/" + name))
    review = {"schema": 1, "kind": "reviewed_candidate46_themes_after_verified_windows45",
              "version_before": {"code": 45, "name": "0.13.7"},
              "version_after": {"code": 46, "name": "0.13.8"},
              "base_commit": base, "base_source_sha256": source,
              "actual45_request": request["verified45_request"], "package_manifests": request["packages"],
              "source_file_count": len(rows), "file_owners": owners,
              "application_or_tests_executed": False, "files": rows}
    review_raw = json_bytes(review)
    bundle = json_bytes({"reference_commit": base, "files": rows}, compact=True)
    transport = base64.b64encode(zlib.compress(bundle, 9))
    manifest = json_bytes({"schema": 1, "base_commit": base, "bundles": [{"name": "n00-native46",
        "transport_sha256": digest(transport), "decoded_sha256": digest(bundle)}]}, compact=True)
    bootstrap = helper.bootstrap(base, source)
    guest = helper.read_pinned(CONTEXT / "full-build-baseline/n00-linux-guest.py", helper.BASELINE_GUEST_SHA256)
    workflow = yaml.safe_load(helper.workflow(base, bootstrap, guest, transport, manifest))
    workflow["name"] = "Complete light and dark themes; verify candidate46"
    develop = workflow["jobs"]["develop"]
    develop["name"] = "Apply reviewed theme46 source on the laptop and perform the full build"
    staged = artifact = 0
    for step in develop["steps"]:
        if step.get("name") == "Stage verified administrative transport: n00-native45.b64":
            replacement = helper.stage("n00-native46.b64", transport)
            step.clear()
            step.update(replacement)
            staged += 1
        if step.get("uses", "").startswith("actions/upload-artifact@"):
            need(step["with"]["name"] == "n00-candidate45-build-checks", "Unexpected small artifact")
            step["with"]["name"] = "n00-candidate46-build-checks"
            # Preserve actual JVM XML in the bounded small artifact, in addition
            # to the unchanged complete private archive. No test command changes.
            step["with"]["path"] += ("\n${{ github.workspace }}/windows-development-${{ github.run_id }}-${{ github.run_attempt }}"
                                      "/app/build/test-results/testDebugUnitTest/*.xml")
            artifact += 1
    need(staged == artifact == 1, "Required stage/artifact is missing")
    workflow_raw = yaml.safe_dump(workflow, allow_unicode=True, sort_keys=False, width=120).encode()
    need(b"n00-native45" not in workflow_raw and b"n00-candidate45" not in workflow_raw,
         "Old transport name retained")
    summary = {"state": "prepared_only_no_application_or_test_execution", "base_commit": base,
               "base_source_sha256": source, "base45_inventory_sha256": actual45_request["source_inventory"]["sha256"],
               "base45_build_run": prior_provenance["build_run_id"], "source_paths": len(rows),
               "new_source_paths": sum(row["old_git_blob"] is None for row in rows),
               "reviewed_files_sha256": digest(review_raw), "bootstrap_sha256": digest(bootstrap),
               "patch_manifest_sha256": digest(manifest), "bundle_sha256": digest(bundle),
               "transport_sha256": digest(transport), "workflow_sha256": digest(workflow_raw),
               "package_manifests": request["packages"], "version": {"code": 46, "name": "0.13.8"},
               "bootstrap_changes": ["BASE_COMMIT", "BASE_SOURCE"],
               "extra_small_artifact": "app/build/test-results/testDebugUnitTest/*.xml",
               "source_applied_on_windows": False, "build_passed": False, "runtime_passed": False,
               "publication_performed": False, "phone_verified": False, "n00_complete": False,
               "native_additional_requirements": {"color_frames": 52, "lifecycle_cases": 4},
               "original_native_counts_changed": False}
    outputs = {"reviewed-files.json": review_raw, "bundle.json": bundle, "n00-native46.b64": transport,
               "patch-manifest.json": manifest, "windows-full-development.py": bootstrap,
               "n00-linux-guest.py": guest, "workflow.yml": workflow_raw,
               "manifest-summary.json": json_bytes(summary), "candidate.patch": "".join(diff).encode()}
    need(CONTEXT in destination.parents and not destination.exists()
         and destination.parent.resolve(strict=True) == destination.parent, "New context output required")
    destination.mkdir()
    for name, raw in outputs.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw)
    for row in rows:
        target = destination / "source" / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(row["content"].encode())
    print(json.dumps(summary))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(json.loads(read(args.request)), args.output.absolute())


if __name__ == "__main__":
    main()
