from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


_HASH_RE = re.compile(r"--hash=sha256:([0-9a-f]{64})")
_NAME_RE = re.compile(r"^([A-Za-z0-9_.-]+)")
_ALLOWED_WINDOWS_EXCLUSIONS = frozenset({"uvloop"})
_WINDOWS_ADDITION_BLOCKS: dict[str, tuple[str, ...]] = {
    "colorama": (
        "colorama==0.4.6 \\\n",
        "    --hash=sha256:08695f5cb7ed6e0531a20572697297273c47b8cae5a63ffc6d6ed5c201be6e44 \\\n",
        "    --hash=sha256:4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6\n",
        "    # via bandit\n",
    ),
}


@dataclass(frozen=True)
class LockedRequirement:
    name: str
    requirement: str
    hashes: frozenset[str]
    block: tuple[str, ...]


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _is_requirement_start(line: str) -> bool:
    stripped = line.strip()
    return bool(
        stripped
        and not line[:1].isspace()
        and not stripped.startswith(("#", "--", "-r ", "-c "))
    )


def _split_lock(text: str) -> tuple[list[str], list[list[str]]]:
    prefix: list[str] = []
    blocks: list[list[str]] = []
    current: list[str] | None = None

    for line in text.splitlines(keepends=True):
        if _is_requirement_start(line):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is None:
            prefix.append(line)
        else:
            current.append(line)

    if current is not None:
        blocks.append(current)
    return prefix, blocks


def _parse_block(block: list[str] | tuple[str, ...]) -> LockedRequirement:
    first = block[0].strip()
    match = _NAME_RE.match(first)
    if match is None:
        raise ValueError(f"cannot parse locked requirement: {first!r}")
    name = _canonical_name(match.group(1))
    hashes = frozenset(_HASH_RE.findall("".join(block)))
    if "==" not in first:
        raise ValueError(f"locked requirement is not exact: {first!r}")
    if not hashes:
        raise ValueError(f"locked requirement has no SHA-256 hashes: {first!r}")
    return LockedRequirement(
        name=name,
        requirement=first.rstrip(" \\"),
        hashes=hashes,
        block=tuple(block),
    )


def _windows_additions() -> dict[str, LockedRequirement]:
    additions = {
        name: _parse_block(block) for name, block in _WINDOWS_ADDITION_BLOCKS.items()
    }
    if set(additions) != set(_WINDOWS_ADDITION_BLOCKS):
        raise ValueError("invalid Windows addition map")
    return additions


def parse_lock(path: Path) -> dict[str, LockedRequirement]:
    _, blocks = _split_lock(path.read_text(encoding="utf-8"))
    parsed: dict[str, LockedRequirement] = {}
    for block in blocks:
        requirement = _parse_block(block)
        if requirement.name in parsed:
            raise ValueError(f"duplicate locked requirement: {requirement.name}")
        parsed[requirement.name] = requirement
    if not parsed:
        raise ValueError(f"lock file has no requirements: {path}")
    return parsed


def project_lock(source: Path, destination: Path) -> None:
    text = source.read_text(encoding="utf-8")
    prefix, blocks = _split_lock(text)
    removed: set[str] = set()
    output_blocks: list[list[str] | tuple[str, ...]] = []
    source_names: set[str] = set()

    for block in blocks:
        requirement = _parse_block(block)
        source_names.add(requirement.name)
        if requirement.name in _ALLOWED_WINDOWS_EXCLUSIONS:
            block_text = "".join(block).lower()
            if requirement.name == "uvloop" and "# via uvicorn" not in block_text:
                raise ValueError("uvloop exclusion is not owned by uvicorn")
            removed.add(requirement.name)
            continue
        output_blocks.append(block)

    if removed != _ALLOWED_WINDOWS_EXCLUSIONS:
        raise ValueError(
            "Windows lock projection must exclude exactly: "
            + ", ".join(sorted(_ALLOWED_WINDOWS_EXCLUSIONS))
        )

    additions = _windows_additions()
    collisions = source_names & additions.keys()
    if collisions:
        raise ValueError(
            "Windows-only additions unexpectedly exist in Linux lock: "
            + ", ".join(sorted(collisions))
        )
    output_blocks.extend(addition.block for addition in additions.values())

    destination.write_text(
        "".join(prefix) + "".join("".join(block) for block in output_blocks),
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"Windows lock projection created: {destination} "
        f"(excluded: {', '.join(sorted(removed))}; "
        f"added: {', '.join(sorted(additions))})"
    )


def verify_projection(linux_lock: Path, windows_compiled_lock: Path) -> None:
    linux = parse_lock(linux_lock)
    windows = parse_lock(windows_compiled_lock)
    additions = _windows_additions()

    missing_allowed = _ALLOWED_WINDOWS_EXCLUSIONS - linux.keys()
    if missing_allowed:
        raise ValueError(
            "Linux lock is missing allowlisted platform packages: "
            + ", ".join(sorted(missing_allowed))
        )

    unexpected_windows = _ALLOWED_WINDOWS_EXCLUSIONS & windows.keys()
    if unexpected_windows:
        raise ValueError(
            "Windows lock unexpectedly contains unsupported packages: "
            + ", ".join(sorted(unexpected_windows))
        )

    addition_collisions = linux.keys() & additions.keys()
    if addition_collisions:
        raise ValueError(
            "Windows-only additions unexpectedly exist in Linux lock: "
            + ", ".join(sorted(addition_collisions))
        )

    expected = {
        name: requirement
        for name, requirement in linux.items()
        if name not in _ALLOWED_WINDOWS_EXCLUSIONS
    }
    expected.update(additions)
    expected_names = set(expected)
    windows_names = set(windows)
    if expected_names != windows_names:
        missing = sorted(expected_names - windows_names)
        extra = sorted(windows_names - expected_names)
        raise ValueError(
            f"Windows lock package set differs; missing={missing}, extra={extra}"
        )

    mismatches: list[str] = []
    for name in sorted(expected_names):
        left = expected[name]
        right = windows[name]
        if left.requirement != right.requirement:
            mismatches.append(
                f"{name}: requirement {left.requirement!r} != {right.requirement!r}"
            )
        if left.hashes != right.hashes:
            mismatches.append(f"{name}: SHA-256 hash set differs")

    if mismatches:
        raise ValueError("Windows lock projection drift:\n- " + "\n- ".join(mismatches))

    print(
        f"Windows lock projection verified: {windows_compiled_lock} "
        f"({len(windows)} hash-locked packages)"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    project = subparsers.add_parser("project")
    project.add_argument("source", type=Path)
    project.add_argument("destination", type=Path)

    verify = subparsers.add_parser("verify")
    verify.add_argument("linux_lock", type=Path)
    verify.add_argument("windows_compiled_lock", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "project":
            project_lock(args.source, args.destination)
        else:
            verify_projection(args.linux_lock, args.windows_compiled_lock)
    except (OSError, ValueError) as exc:
        print(f"Windows CI lock validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
