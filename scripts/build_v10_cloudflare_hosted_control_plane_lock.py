from __future__ import annotations

import os
import re
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_CANONICAL_LOCK = _ROOT / "requirements.txt"
_FILENAME = "omni-cio-v10-cloudflare-hosted-control-plane.txt"
_REQUIRED = {
    "psycopg": "3.3.4",
    "psycopg-binary": "3.3.4",
    "typing-extensions": "4.16.0",
}
_HEADER = re.compile(r"^([A-Za-z0-9_.-]+)==([^ ;\\]+)(?:\s*;[^\\]+)?\s*\\?$", re.I)
_HASH = re.compile(r"^\s+--hash=sha256:[0-9a-f]{64}(?:\s*\\)?$")


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def hosted_lock_path() -> Path:
    value = os.environ.get("RUNNER_TEMP", "").strip()
    if not value:
        raise RuntimeError("CLOUDFLARE_RUNNER_TEMP_REQUIRED")
    root = Path(value).resolve()
    if not root.is_dir():
        raise RuntimeError("CLOUDFLARE_RUNNER_TEMP_INVALID")
    return root / _FILENAME


def _blocks(source: str) -> dict[str, tuple[str, list[str]]]:
    lines = source.splitlines()
    found: dict[str, tuple[str, list[str]]] = {}
    index = 0
    while index < len(lines):
        match = _HEADER.fullmatch(lines[index])
        if match is None:
            index += 1
            continue
        name = _normalize(match.group(1))
        version = match.group(2)
        hashes: list[str] = []
        cursor = index + 1
        while cursor < len(lines) and _HASH.fullmatch(lines[cursor]):
            hashes.append(lines[cursor])
            cursor += 1
        found[name] = (version, [lines[index], *hashes])
        index = cursor
    return found


def render_hosted_control_plane_lock(source: str) -> str:
    blocks = _blocks(source)
    rendered = ["--index-url https://pypi.org/simple", ""]
    for package, expected_version in _REQUIRED.items():
        block = blocks.get(package)
        if block is None:
            raise RuntimeError(f"CLOUDFLARE_HOSTED_LOCK_PACKAGE_MISSING:{package}")
        version, lines = block
        if version != expected_version:
            raise RuntimeError(f"CLOUDFLARE_HOSTED_LOCK_VERSION_DRIFT:{package}")
        if len(lines) < 2:
            raise RuntimeError(f"CLOUDFLARE_HOSTED_LOCK_HASH_MISSING:{package}")
        rendered.extend(lines)
    return "\n".join(rendered) + "\n"


def write_hosted_control_plane_lock() -> Path:
    try:
        source = _CANONICAL_LOCK.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("CLOUDFLARE_HOSTED_LOCK_CANONICAL_UNREADABLE") from exc
    output = hosted_lock_path()
    if output.is_symlink():
        raise RuntimeError("CLOUDFLARE_HOSTED_LOCK_PATH_INVALID")
    output.write_text(render_hosted_control_plane_lock(source), encoding="utf-8")
    print("CLOUDFLARE_HOSTED_CONTROL_PLANE_LOCK=READY")
    return output


def main() -> int:
    try:
        write_hosted_control_plane_lock()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
