"""Private, bounded S3 handoff for signed CI files; never publishes an APK."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import zipfile

from timeweb_actions_probe import (
    BASE_URL, MAX_BYTES, NoRedirect, ProbeError, decode_response, read_catalog,
    read_resource, summarize, transport_error_code, validated_token, verified_ssl_context,
)
from timeweb_ci_catalog import storage_offers

PROJECT_ID = 2941515
MAX_MONTHLY_RUB = 1
OBJECT_KEY = "ci-handoff.zip"
MAX_ARCHIVE_BYTES = 512 * 1024**2
OWNER_MARKER = "Analyst AI temporary private CI transfer "
FILES = (
    "app/build/outputs/apk/preview/app-preview.apk",
    "app/build/outputs/apk/debug/app-debug.apk",
    "ci-ui-driver/build/outputs/apk/debug/ci-ui-driver-debug.apk",
    "previous.apk",
)


def identity() -> tuple[str, str]:
    run, attempt, head = (os.environ.get(key, "") for key in
                          ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA"))
    if (not re.fullmatch(r"\d{1,20}", run, re.ASCII)
            or not re.fullmatch(r"\d{1,5}", attempt, re.ASCII)
            or not re.fullmatch(r"[a-f0-9]{40}", head)):
        raise ProbeError("transfer_identity_required")
    return "analyst-ci-" + run + "-" + attempt, OWNER_MARKER + head


def storage_request(token: str, method: str, path: str, body=None) -> dict:
    if not ((method == "POST" and path == "/api/v1/storages/buckets") or
            (method in {"GET", "DELETE"} and re.fullmatch(
                r"/api/v1/storages/buckets/[1-9]\d{0,15}", path, re.ASCII))):
        raise ProbeError("unapproved_transfer_request")
    request = urllib.request.Request(
        BASE_URL + path, method=method,
        data=None if body is None else json.dumps(body).encode(), headers={
            "Authorization": "Bearer " + validated_token(token),
            "Content-Type": "application/json", "Accept-Encoding": "identity",
        })
    try:
        opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPSHandler(context=verified_ssl_context()))
        with opener.open(request, timeout=30) as response:
            if response.status not in {200, 201, 204}:
                raise ProbeError("unexpected_storage_http_status")
            if response.headers.get("Content-Encoding", "identity").lower() not in {"identity", ""}:
                raise ProbeError("encoded_response_refused")
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        code = error.code
        error.close()
        raise ProbeError("storage_http_" + str(code)) from None
    except OSError as error:
        raise ProbeError(transport_error_code(error)) from None
    return decode_response(raw) if raw else {}


def owned_bucket(bucket: dict) -> dict:
    name, description = identity()
    if (type(bucket) is not dict or type(bucket.get("id")) is not int or bucket["id"] <= 0
            or bucket.get("name") != name or bucket.get("description") != description
            or bucket.get("project_id") != PROJECT_ID or bucket.get("type") != "private"):
        raise ProbeError("transfer_bucket_ownership_mismatch")
    return bucket


def find_bucket(token: str) -> dict | None:
    document = read_resource(token, "buckets")
    if not summarize("buckets", document)["complete"]:
        raise ProbeError("transfer_inventory_incomplete")
    name, _ = identity()
    matches = [item for item in document["buckets"] if item.get("name") == name]
    if len(matches) > 1:
        raise ProbeError("transfer_ambiguous_bucket")
    return owned_bucket(matches[0]) if matches else None


def select_offer(document: dict) -> dict:
    offers = [item for item in storage_offers(document)
              if item["disk"] == 1024 and item["price"] <= MAX_MONTHLY_RUB
              and item.get("storage_class") == "standard"]
    if not offers:
        raise ProbeError("transfer_no_small_offer_within_budget")
    return offers[0]


def create_bucket(token: str) -> dict:
    if find_bucket(token) is not None:
        raise ProbeError("transfer_bucket_already_exists")
    projects = summarize("projects", read_resource(token, "projects"))
    if PROJECT_ID not in projects["ids"]:
        raise ProbeError("transfer_project_not_visible")
    offer = select_offer(read_catalog(token, "storage"))
    name, description = identity()
    print("TIMEWEB_TRANSFER_OFFER=" + json.dumps(offer, sort_keys=True), flush=True)
    document = storage_request(token, "POST", "/api/v1/storages/buckets", {
        "name": name, "description": description, "type": "private",
        "preset_id": offer["id"], "project_id": PROJECT_ID,
    })
    bucket = owned_bucket(document.get("bucket"))
    if bucket.get("preset_id") != offer["id"]:
        raise ProbeError("transfer_bucket_offer_mismatch")
    print("TIMEWEB_TRANSFER_BUCKET_ID=" + str(bucket["id"]), flush=True)
    return bucket


def endpoint(hostname: str) -> str:
    if not isinstance(hostname, str):
        raise ProbeError("transfer_endpoint_invalid")
    value = hostname if hostname.startswith("https://") else "https://" + hostname
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or not re.fullmatch(r"[a-z\d.-]+\.twcstorage\.ru", parsed.hostname or "", re.ASCII)):
        raise ProbeError("transfer_endpoint_invalid")
    return "https://" + parsed.hostname


def client(bucket: dict):
    import boto3
    from botocore.config import Config

    if os.name == "nt":
        import truststore
        truststore.inject_into_ssl()
    url = endpoint(bucket.get("hostname"))
    access = validated_token(bucket.get("access_key", ""))
    secret = validated_token(bucket.get("secret_key", ""))
    return boto3.client("s3", endpoint_url=url, region_name="ru-1",
                        aws_access_key_id=access, aws_secret_access_key=secret,
                        config=Config(signature_version="s3v4", connect_timeout=10,
                                      read_timeout=120, retries={"max_attempts": 2},
                                      s3={"addressing_style": "path"},
                                      request_checksum_calculation="when_required",
                                      response_checksum_validation="when_required"))


def read_bytes(s3, bucket: dict, *, expected_hash: str) -> bytes:
    response = s3.get_object(Bucket=bucket["name"], Key=OBJECT_KEY)
    stream = response["Body"]
    try:
        data = stream.read(MAX_ARCHIVE_BYTES + 1)
    finally:
        stream.close()
    if len(data) > MAX_ARCHIVE_BYTES or hashlib.sha256(data).hexdigest() != expected_hash:
        raise ProbeError("transfer_integrity_mismatch")
    return data


def require_private(s3, bucket: dict) -> None:
    acl = s3.get_bucket_acl(Bucket=bucket["name"])
    if any(grant.get("Grantee", {}).get("Type") == "Group" for grant in acl.get("Grants", [])):
        raise ProbeError("transfer_public_bucket_acl")


def probe(token: str) -> None:
    bucket = create_bucket(token)
    s3 = client(bucket)
    require_private(s3, bucket)
    payload = b"Analyst AI private CI transport probe\n"
    s3.put_object(Bucket=bucket["name"], Key=OBJECT_KEY, Body=payload, ACL="private")
    digest = hashlib.sha256(payload).hexdigest()
    if read_bytes(s3, bucket, expected_hash=digest) != payload:
        raise ProbeError("transfer_readback_mismatch")
    print("TIMEWEB_TRANSFER_PROBE=private_readback_passed", flush=True)


def regular_file(root: Path, relative: str) -> Path:
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ProbeError("transfer_file_escapes_checkout")
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise ProbeError("transfer_link_refused")
    return path


def pack(root: Path, previous: Path) -> bytes:
    identity()
    buffer = io.BytesIO()
    manifest = {"head": os.environ["GITHUB_SHA"], "files": {}}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        total = 0
        for name in FILES:
            source = previous if name == "previous.apk" else regular_file(root, name)
            if source.is_symlink() or not source.is_file():
                raise ProbeError("transfer_source_missing_or_link")
            size = source.stat().st_size
            total += size
            if size <= 0 or total > MAX_ARCHIVE_BYTES - MAX_BYTES:
                raise ProbeError("transfer_payload_size_invalid")
            data = source.read_bytes()
            if len(data) != size:
                raise ProbeError("transfer_source_changed")
            manifest["files"][name] = {"bytes": size, "sha256": hashlib.sha256(data).hexdigest()}
            archive.writestr(name, data)
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
    return buffer.getvalue()


def unpack(data: bytes, root: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if (len(entries) != len(FILES) + 1 or {entry.filename for entry in entries} != {*FILES, "manifest.json"}
                or sum(entry.file_size for entry in entries) > MAX_ARCHIVE_BYTES
                or archive.getinfo("manifest.json").file_size > MAX_BYTES):
            raise ProbeError("transfer_archive_members_invalid")
        manifest = decode_response(archive.read("manifest.json"))
        if manifest.get("head") != os.environ.get("GITHUB_SHA") or set(manifest.get("files", {})) != set(FILES):
            raise ProbeError("transfer_manifest_identity_mismatch")
        payload = {}
        for name in FILES:
            content = archive.read(name)
            record = manifest["files"][name]
            if record != {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}:
                raise ProbeError("transfer_manifest_digest_mismatch")
            payload[name] = content
        # Validate all content before creating any output. No archive paths are extracted.
        for name, content in payload.items():
            destination = regular_file(root, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)


def upload(token: str) -> None:
    root = Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True)
    data = pack(root, Path(os.environ["PREVIOUS_APK"]).resolve(strict=True))
    digest = hashlib.sha256(data).hexdigest()
    bucket = create_bucket(token)
    s3 = client(bucket)
    require_private(s3, bucket)
    s3.put_object(Bucket=bucket["name"], Key=OBJECT_KEY, Body=data, ACL="private")
    read_bytes(s3, bucket, expected_hash=digest)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write("archive_sha256=" + digest + "\n")
    print("TIMEWEB_TRANSFER_UPLOAD=" + json.dumps({"sha256": digest, "bytes": len(data)}), flush=True)


def download(token: str) -> None:
    digest = os.environ.get("TRANSFER_SHA256", "")
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ProbeError("transfer_expected_digest_required")
    bucket = find_bucket(token)
    if bucket is None:
        raise ProbeError("transfer_bucket_missing")
    s3 = client(bucket)
    require_private(s3, bucket)
    data = read_bytes(s3, bucket, expected_hash=digest)
    root = Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True)
    unpack(data, root)
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as output:
        output.write("PREVIOUS_APK=" + str(root / "previous.apk") + "\n")
    print("TIMEWEB_TRANSFER_DOWNLOAD=exact_head_and_file_hashes_verified", flush=True)


def delete_bucket(token: str, bucket: dict) -> None:
    path = "/api/v1/storages/buckets/" + str(bucket["id"])
    storage_request(token, "DELETE", path)
    for _ in range(6):
        try:
            storage_request(token, "GET", path)
        except ProbeError as error:
            if str(error) == "storage_http_404":
                print("TIMEWEB_TRANSFER_CLEANUP=verified_absent", flush=True)
                return
            raise
        time.sleep(5)
    raise ProbeError("transfer_deletion_not_confirmed")


def cleanup_empty(token: str) -> None:
    """Recover only an owned bucket with control-plane confirmation of zero objects."""
    bucket = find_bucket(token)
    if bucket is None:
        print("TIMEWEB_TRANSFER_CLEANUP=verified_absent", flush=True)
        return
    if type(bucket.get("object_amount")) is not int or bucket["object_amount"] != 0:
        raise ProbeError("transfer_cleanup_bucket_not_empty")
    delete_bucket(token, bucket)


def diagnose(token: str) -> None:
    bucket = find_bucket(token)
    if bucket is None:
        raise ProbeError("transfer_bucket_missing")
    print("TIMEWEB_TRANSFER_METADATA=" + json.dumps({
        "id": bucket["id"], "endpoint": endpoint(bucket.get("hostname")),
        "object_amount": bucket.get("object_amount") if type(bucket.get("object_amount")) is int else None,
    }), flush=True)
    require_private(client(bucket), bucket)
    print("TIMEWEB_TRANSFER_PRIVATE_ACL=passed", flush=True)


def cleanup(token: str) -> None:
    bucket = find_bucket(token)
    if bucket is None:
        print("TIMEWEB_TRANSFER_CLEANUP=verified_absent", flush=True)
        return
    s3 = client(bucket)
    listing = s3.list_objects_v2(Bucket=bucket["name"], MaxKeys=2)
    if listing.get("IsTruncated") or any(item.get("Key") != OBJECT_KEY for item in listing.get("Contents", [])):
        raise ProbeError("transfer_cleanup_unexpected_objects")
    s3.delete_object(Bucket=bucket["name"], Key=OBJECT_KEY)
    delete_bucket(token, bucket)


def error_summary(error: Exception) -> dict:
    result = {"code": str(error) if isinstance(error, ProbeError) else type(error).__name__}
    response = getattr(error, "response", {})
    if type(response) is dict:
        code = response.get("Error", {}).get("Code")
        if isinstance(code, str) and re.fullmatch(r"[A-Za-z\d]{1,64}", code, re.ASCII):
            result["s3_code"] = code
    operation = getattr(error, "operation_name", None)
    if isinstance(operation, str) and re.fullmatch(r"[A-Za-z]{1,64}", operation):
        result["operation"] = operation
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = {"probe": probe, "cleanup": cleanup, "upload": upload, "download": download,
                "cleanup-empty": cleanup_empty, "diagnose": diagnose}
    parser.add_argument("command", choices=commands)
    args = parser.parse_args()
    try:
        token = validated_token(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
        commands[args.command](token)
    except Exception as error:
        # SDK exceptions can contain request URLs and credentials. Never echo them.
        print("TIMEWEB_TRANSFER_ERROR=" + json.dumps(error_summary(error), sort_keys=True), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
