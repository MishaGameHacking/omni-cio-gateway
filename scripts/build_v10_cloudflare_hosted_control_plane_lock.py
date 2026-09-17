from __future__ import annotations

import os
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
_HASH_PREFIX = "--hash=sha256:"
_HEX = frozenset("0123456789abcdef")


def _normalize(name: str) -> str:
    normalized = name.replace("_", "-").replace(".", "-").lower()
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized


def _parse_header(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", "-")):
        return None
    if stripped.endswith("\\"):
        stripped = stripped[:-1].rstrip()
    requirement, _, _marker = stripped.partition(";")
    requirement = requirement.strip()
    if requirement.count("==") != 1:
        return None
    name, version = requirement.split("==", 1)
    if not name or not version:
        return None
    if not all(character.isalnum() or character in "_.-" for character in name):
        return None
    if any(character.isspace() or character == "\\" for character in version):
        return None
    return _normalize(name), version


def _is_hash_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.endswith("\\"):
        stripped = stripped[:-1].rstrip()
    if not stripped.startswith(_HASH_PREFIX):
        return False
    digest = stripped[len(_HASH_PREFIX) :]
    return len(digest) == 64 and all(character in _HEX for character in digest)


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
        header = _parse_header(lines[index])
        if header is None:
            index += 1
            continue
        name, version = header
        hashes: list[str] = []
        cursor = index + 1
        while cursor < len(lines) and _is_hash_line(lines[cursor]):
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
