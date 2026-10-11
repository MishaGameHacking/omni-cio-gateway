"""Publish a verified main debug APK through free GitHub Release assets."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.parse import quote

import verify_main_release as gate

API_PREFIX = f"/repos/{gate.REPOSITORY}"
MAX_RESPONSE = 2_000_000


class ReleaseAPI:
    def __init__(self, token: str) -> None:
        self.token = token

    def request(
        self, method: str, path: str, *, body: bytes | None = None,
        upload: bool = False, expected: int = 200,
    ) -> dict[str, Any]:
        host = "uploads.github.com" if upload else "api.github.com"
        headers = {
            "Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "omnicio-android-publisher/1.0",
            "Content-Type": "application/octet-stream" if upload else "application/json",
        }
        with closing(http.client.HTTPSConnection(host, timeout=120)) as connection:
            connection.request(method, API_PREFIX + path, body=body, headers=headers)
            response = connection.getresponse()
            # Never follow redirects with the write token; never print response bodies.
            if response.status != expected:
                raise gate.ReleaseBlocked(f"Release API failed (HTTP {response.status})")
            payload = response.read(MAX_RESPONSE + 1)
        if len(payload) > MAX_RESPONSE:
            raise gate.ReleaseBlocked("Release API response exceeds the size limit")
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise gate.ReleaseBlocked("Release API response is not an object")
        return data


def build_assets(root: Path, sha: str, run_id: str, attempt: str) -> tuple[str, dict[str, bytes]]:
    directory = root / "app/build/outputs/apk/debug"
    metadata = json.loads((directory / "output-metadata.json").read_text(encoding="utf-8"))
    elements = metadata.get("elements", [])
    if (metadata.get("applicationId") != "ru.omnicio.app.debug"
            or metadata.get("variantName") != "debug" or len(elements) != 1):
        raise gate.ReleaseBlocked("Expected exactly one debug application output")
    output = elements[0]
    version = output.get("versionName", "")
    if (output.get("outputFile") != "app-debug.apk"
            or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-debug", version)
            or type(output.get("versionCode")) is not int or output["versionCode"] < 1):
        raise gate.ReleaseBlocked("Invalid Android build metadata")
    apk = directory / "app-debug.apk"
    if apk.is_symlink() or not 0 < apk.stat().st_size < 100 * 1024 * 1024:
        raise gate.ReleaseBlocked("APK is not a bounded regular build output")
    signing = (root / "artifacts/android/apksigner.txt").read_text(encoding="utf-8")
    certificates = re.findall(r"Signer #1 certificate SHA-256 digest: ([0-9a-fA-F]{64})", signing)
    if len(certificates) != 1:
        raise gate.ReleaseBlocked("Missing verified APK certificate digest")
    apk_bytes = apk.read_bytes()
    name = f"omnicio-{version}-{sha}.apk"
    manifest = {
        "schema": 1, "package": "ru.omnicio.app.debug", "version": version,
        "version_code": output["versionCode"], "commit": sha, "file": name,
        "sha256": hashlib.sha256(apk_bytes).hexdigest(),
        "certificate_sha256": certificates[0].lower(), "build_type": "debug",
        "run": f"https://github.com/{gate.REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}",
    }
    assets = {
        name: apk_bytes, "android-build.json": (json.dumps(manifest, indent=2) + "\n").encode(),
    }
    checksums = "".join(f"{hashlib.sha256(data).hexdigest()}  {filename}\n"
                        for filename, data in assets.items())
    assets["SHA256SUMS.txt"] = checksums.encode()
    return version, assets


def verify_asset(asset: dict[str, Any], name: str, data: bytes) -> None:
    if (asset.get("name") != name or asset.get("state") != "uploaded"
            or asset.get("size") != len(data)
            or asset.get("digest") != "sha256:" + hashlib.sha256(data).hexdigest()):
        raise gate.ReleaseBlocked("Uploaded release asset does not match the local build")


def publish(
    api: ReleaseAPI, sha: str, run_id: str, attempt: str, version: str, assets: dict[str, bytes],
) -> str:
    tag = f"android-debug-{sha}-{run_id}-{attempt}"
    body = (
        f"Установочный debug APK OmniCIO {version}, Android 8.0+.\n\n"
        f"Исходники: `{sha}` из принятого main. Пакет: `ru.omnicio.app.debug`.\n"
        "Сборка прошла Android lint, unit tests, проверку подписи и защиту release signing.\n"
        "Это debug-сборка для установки и проверки владельцем, не подписанный магазинный выпуск. "
        "Она не подтверждает работоспособность входа, брокерского счёта "
        "или новых функций на устройстве.\n\n"
        "Скачайте APK; SHA256SUMS.txt и android-build.json содержат контрольные суммы, "
        "версию, сертификат и ссылку на сборку. При несовпадении сертификата со старым debug APK "
        "Android не разрешит обновление поверх него.\n"
    )
    release = api.request("POST", "/releases", body=json.dumps({
        "tag_name": tag, "target_commitish": sha, "name": f"OmniCIO {version} ({sha[:12]})",
        "body": body, "draft": True, "prerelease": True, "make_latest": "false",
    }).encode(), expected=201)
    identifier = release.get("id")
    if (type(identifier) is not int or identifier < 1 or release.get("tag_name") != tag
            or release.get("target_commitish") != sha or release.get("draft") is not True):
        raise gate.ReleaseBlocked("Draft release identity does not match the accepted build")
    # Keep an incomplete upload as a draft; never replace or delete an existing release or asset.
    for name, data in assets.items():
        uploaded = api.request(
            "POST", f"/releases/{identifier}/assets?name={quote(name, safe='')}",
            body=data, upload=True, expected=201,
        )
        verify_asset(uploaded, name, data)
    saved = api.request("GET", f"/releases/{identifier}")
    rows = saved.get("assets", [])
    if len(rows) != len(assets):
        raise gate.ReleaseBlocked("Draft release asset set is incomplete")
    by_name = {row["name"]: row for row in rows}
    for name, data in assets.items():
        verify_asset(by_name.get(name, {}), name, data)
    # Re-check main immediately before making the validated draft visible.
    if api.request("GET", "/branches/main").get("commit", {}).get("sha") != sha:
        raise gate.ReleaseBlocked("Main changed during APK publication")
    result = api.request("PATCH", f"/releases/{identifier}", body=json.dumps({
        "draft": False, "prerelease": True, "make_latest": "false",
    }).encode())
    url = f"https://github.com/{gate.REPOSITORY}/releases/tag/{tag}"
    if (result.get("draft") is not False or result.get("prerelease") is not True
            or result.get("html_url") != url):
        raise gate.ReleaseBlocked("Published release did not match the requested result")
    reference = api.request("GET", f"/git/ref/tags/{tag}")
    if reference.get("object", {}).get("sha") != sha:
        raise gate.ReleaseBlocked("Published release tag does not match the build commit")
    return url


def main() -> int:
    try:
        if os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
            raise gate.ReleaseBlocked("Only an explicit main dispatch can publish APKs")
        sha, token = gate.release_context()
        gate.require_checkout(sha)
        run_id, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
        if not all(re.fullmatch(r"[1-9][0-9]*", value) for value in (run_id, attempt)):
            raise gate.ReleaseBlocked("Invalid build run identity")
        version, assets = build_assets(Path(__file__).resolve().parents[2], sha, run_id, attempt)
        gate.wait_for_main_release(sha, token)
        url = publish(ReleaseAPI(token), sha, run_id, attempt, version, assets)
        print(f"Verified debug APK release: {url}")
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
            output.write(
                f"### Installable debug APK\n\n[Download {version}]({url})\n\nCommit: `{sha}`\n",
            )
    except (gate.ReleaseBlocked, OSError, ValueError, KeyError, http.client.HTTPException) as exc:
        # No raw transport error or API body may expose the write credential.
        message = str(exc) if isinstance(exc, gate.ReleaseBlocked) else type(exc).__name__
        print(f"::error::Android publication stopped: {message}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
