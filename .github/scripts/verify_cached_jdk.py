"""Use the signing runner's completed Temurin 17 cache without a network bootstrap.

Layout matches the pinned actions/setup-java tool cache. This does not install a
JDK, change a signing key, or accept JAVA_HOME/PATH as an alternate source.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import subprocess

CACHE_FAMILY = "Java_Temurin-Hotspot_jdk"
CACHE_VERSION = re.compile(r"17\.(\d+)\.(\d+)-(\d+)", re.ASCII)
PROPERTIES = {"java.specification.version", "java.vendor", "java.runtime.version",
              "java.home", "os.arch", "sun.arch.data.model"}


class CachedJdkError(RuntimeError):
    """The configured cache does not prove a runnable supported JDK."""


def _checked(path: Path, root: Path, *, directory: bool = False) -> Path:
    details = path.lstat()
    reparse = getattr(details, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    if (reparse or not expected_type(details.st_mode)
            or path.resolve(strict=True) != path or not path.is_relative_to(root)):
        raise CachedJdkError("Cache paths must be regular, unlinked and inside the configured root")
    return path


def discover(cache: str) -> Path:
    root = Path(cache)
    if not cache or not root.is_absolute() or any(character in cache for character in "\r\n\0"):
        raise CachedJdkError("An absolute RUNNER_TOOL_CACHE is required")
    _checked(root, root, directory=True)
    family = _checked(root / CACHE_FAMILY, root, directory=True)
    candidates = []
    for version in family.iterdir():
        match = CACHE_VERSION.fullmatch(version.name)
        if match is None:
            continue
        _checked(version, root, directory=True)
        marker = version / "x64.complete"
        try:
            _checked(marker, root)
        except FileNotFoundError:
            continue
        home = _checked(version / "x64", root, directory=True)
        candidates.append((tuple(map(int, match.groups())), home))
    if not candidates:
        raise CachedJdkError("A completed stable Temurin 17 x64 cache is required")
    home = max(candidates, key=lambda candidate: candidate[0])[1]
    for name in ("java.exe", "javac.exe", "keytool.exe"):
        executable = _checked(home / "bin" / name, root)
        if executable.stat().st_size == 0:
            raise CachedJdkError("Cached JDK executable is empty")
    return home


def _run(command: list[str], env: dict[str, str]) -> str:
    result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=30, check=False, env=env)
    if result.returncode != 0 or len(result.stdout) > 65_536:
        raise CachedJdkError("Cached JDK executable failed verification")
    return result.stdout.decode("utf-8", errors="replace")


def verify(home: Path, env: dict[str, str]) -> str:
    output = _run([str(home / "bin/java.exe"), "-XshowSettings:properties", "-version"], env)
    properties = {}
    for line in output.splitlines():
        name, separator, value = line.strip().partition(" = ")
        if separator and name in PROPERTIES:
            if name in properties:
                raise CachedJdkError("Cached JDK reported duplicate properties")
            properties[name] = value
    expected = {"java.specification.version": "17", "java.vendor": "Eclipse Adoptium",
                "sun.arch.data.model": "64"}
    if (any(properties.get(name) != value for name, value in expected.items())
            or properties.get("os.arch") not in {"amd64", "x86_64"}
            or Path(properties.get("java.home", "")).resolve(strict=True) != home):
        raise CachedJdkError("Cached Java must be Temurin 17 x64 from the selected directory")
    runtime = properties.get("java.runtime.version", "")
    if re.fullmatch(r"17(?:\.\d+)*(?:\+\d+)?", runtime, re.ASCII) is None:
        raise CachedJdkError("Cached Java must report a stable version 17 runtime")
    compiler = _run([str(home / "bin/javac.exe"), "-version"], env).strip()
    if re.fullmatch(r"javac 17(?:\.\d+)*(?:\+\d+)?", compiler, re.ASCII) is None:
        raise CachedJdkError("Cached javac must report version 17")
    return runtime


def configure(env: dict[str, str]) -> str:
    home = discover(env.get("RUNNER_TOOL_CACHE", ""))
    runtime = verify(home, env)
    outputs = [Path(env.get(name, "")) for name in ("GITHUB_ENV", "GITHUB_PATH")]
    for output in outputs:
        if not output.is_absolute():
            raise CachedJdkError("GitHub environment files must be absolute regular files")
        _checked(output, output.parent)
    with outputs[0].open("a", encoding="utf-8", newline="\n") as target:
        target.write(f"JAVA_HOME={home}\nJAVA_HOME_17_X64={home}\n")
    with outputs[1].open("a", encoding="utf-8", newline="\n") as target:
        target.write(f"{home / 'bin'}\n")
    return runtime


def main() -> None:
    try:
        runtime = configure(dict(os.environ))
    except (OSError, ValueError, subprocess.SubprocessError, CachedJdkError):
        raise SystemExit("CACHED_JDK_ERROR=Completed Temurin 17 x64 verification failed") from None
    print(f"CACHED_JDK_VERIFIED=Temurin;java_runtime={runtime};architecture=x64")


if __name__ == "__main__":
    main()
