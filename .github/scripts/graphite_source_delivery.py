"""Temporary fixed-manifest source transport; never mutates a branch or production."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request
import zlib

BASE = "89ed9342a63512b22b4d84a01a0274bc415d9516"
API = "https://api.github.com/repos/MishaGameHacking/omni-cio-gateway"
PARTS = (
    "ccc56a78e528a2d7901e0e0e386c4de891bcc769",
    "fbe9200759727f632b3f569612b0569f4e383b92",
    "8c1b305086d6af2982ec1d3dbbaa3b0052a201a6",
    "a0249e3b4088facc5798e94f01ac443c7d0541fc",
    "813093eb4bfa6f939092c86beb999c0612d92532",
    "82210bed06f9f73c1d7ad08481cc564c2d3ce709",
    "6ce157bdd447131fb08cef58c6660ded9fae8f52",
    "fd20fd00cc5c6e566b44237fba1c3e8bb614e206",
)
DIGEST = "84eb23143f18ecacb85de22fd35d8cee969d095c27eb11eb769b54f70cb64a91"
ALLOWED = frozenset((
    ".github/scripts/test_timeweb_auth_app.py", "pyproject.toml",
    "src/omnicio/cbr.py", "src/omnicio/main.py", "src/omnicio/market.py",
    "tests/frontend-smoke.cjs", "tests/test_market.py", "tests/test_portfolio.py",
    "uv.lock", "web/app.css", "web/app.js", "web/index.html",
    "web/manifest.webmanifest", "web/workspace.js",
))


def blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def request(path: str, payload: object = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(API + path, data=data, headers={
        "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
        "User-Agent": "OmniCIO-reviewed-source-transport",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    })
    # Both GET and identical content-addressed blob creation are safe to retry.
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("source_response_too_large")
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 502, 503, 504) or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 2:
                raise
        time.sleep(attempt + 1)
    raise RuntimeError("source_transport_failed")


def verify_refs() -> None:
    if request("/git/ref/heads/main")["object"]["sha"] != BASE:
        raise ValueError("accepted_main_changed")
    if request("/git/ref/heads/feature/graphite-market-workspace")["object"]["sha"] != os.environ["GITHUB_SHA"]:
        raise ValueError("working_head_changed")


def main() -> None:
    verify_refs()
    parts = []
    for sha in PARTS:
        raw = base64.b64decode(request("/git/blobs/" + sha)["content"])
        if len(raw) > 4000 or blob_sha(raw) != sha:
            raise ValueError("source_part_mismatch")
        parts.append(raw)
    packed = base64.b64decode(b"".join(parts), validate=True)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(packed, 200_001)
    if len(raw) > 200_000 or not decoder.eof or decoder.unused_data:
        raise ValueError("source_archive_invalid")
    if hashlib.sha256(raw).hexdigest() != DIGEST:
        raise ValueError("source_manifest_mismatch")
    entries = json.loads(raw)
    if len(entries) != len(ALLOWED) or {entry["path"] for entry in entries} != ALLOWED:
        raise ValueError("source_path_mismatch")
    verified = []
    for entry in entries:
        original = subprocess.check_output(["git", "show", BASE + ":" + entry["path"]])
        if blob_sha(original) != entry["before"]:
            raise ValueError("baseline_blob_mismatch")
        lines = original.decode("utf-8").splitlines(keepends=True)
        previous = len(lines)
        for start, end, replacement in reversed(entry["edits"]):
            if not 0 <= start <= end <= previous:
                raise ValueError("source_edit_bounds")
            lines[start:end] = replacement
            previous = start
        content = "".join(lines)
        if blob_sha(content.encode("utf-8")) != entry["after"]:
            raise ValueError("candidate_blob_mismatch")
        verified.append((entry["path"], entry["after"], content))
    verify_refs()
    records = []
    for path, expected, content in verified:
        result = request("/git/blobs", {"content": content, "encoding": "utf-8"})
        if result["sha"] != expected:
            raise ValueError("published_blob_mismatch")
        records.append({"path": path, "sha": expected})
        print("Verified source:", path, expected)
    verify_refs()
    Path("graphite-candidate-blobs.json").write_text(json.dumps({
        "baseline": BASE, "delivery_head": os.environ["GITHUB_SHA"], "files": records,
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
