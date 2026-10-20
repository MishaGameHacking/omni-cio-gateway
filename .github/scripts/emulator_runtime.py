"""Read-only provenance for native/ART failures on the owned disposable AVD."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess

from kernel_page_size import system_image

SOURCE_PROPERTIES = "source.properties"
RUNTIME_PROPERTIES = (
    "ro.build.fingerprint",
    "ro.build.version.sdk",
    "ro.build.version.security_patch",
    "ro.product.cpu.abi",
    "persist.sys.dalvik.vm.lib.2",
    "dalvik.vm.usejit",
    "dalvik.vm.usejitprofiles",
    "qemu.hw.mainkeys",
)


def _package_revision(path: Path) -> dict:
    try:
        with path.open("rb") as source:
            content = source.read(65537)
        if len(content) > 65536:
            raise ValueError("SDK package metadata exceeds diagnostic limit")
        text = content.decode("utf-8-sig")
        revisions = []
        for line in text.splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "Pkg.Revision":
                revisions.append(value.strip())
        if len(revisions) != 1 or re.fullmatch(r"\d+(?:\.\d+){0,3}", revisions[0], re.ASCII) is None:
            raise ValueError("SDK package revision is missing or ambiguous")
        return {"revision": revisions[0]}
    except (OSError, ValueError) as error:
        return {"unavailable": type(error).__name__}


def _runtime_properties(output: str) -> dict:
    parsed = {}
    for line in output.splitlines():
        if not line.startswith("[") or not line.endswith("]"):
            continue
        key, separator, value = line[1:-1].partition("]: [")
        if not separator or key not in RUNTIME_PROPERTIES:
            continue
        if key in parsed:
            raise ValueError("Runtime property is ambiguous")
        parsed[key] = value[:512]
    # Missing and empty properties differ from disabled JIT.
    return {key: parsed.get(key) for key in RUNTIME_PROPERTIES}


def snapshot_runtime_environment(device, sdk: Path, api: int, *, page_size_bytes: int = 4096) -> dict:
    """Record the installed versions, never alter JIT or relabel a failing run."""
    image = system_image(api, page_size_bytes)
    report = {
        "system_image": image,
        "sdk_packages": {
            "emulator": _package_revision(sdk / "emulator" / SOURCE_PROPERTIES),
            "platform-tools": _package_revision(sdk / "platform-tools" / SOURCE_PROPERTIES),
            "system-image": _package_revision(sdk.joinpath(*image.split(";"), SOURCE_PROPERTIES)),
        },
    }
    try:
        response = device("shell", "getprop", timeout=10)
        if response.returncode:
            report["properties_unavailable"] = "getprop failed"
        else:
            report["properties"] = _runtime_properties(response.stdout)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        if getattr(error, "emulator_transport_lost", False):
            # The caller requires a completely fresh AVD after proven transport
            # loss. A diagnostic read cannot consume that control signal.
            raise
        report["properties_unavailable"] = type(error).__name__
    return report
