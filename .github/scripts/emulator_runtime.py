"""Read-only provenance for native/ART failures on the owned disposable AVD."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess

from kernel_page_size import system_image

RUNTIME_PROPERTIES = (
    "ro.build.fingerprint",
    "ro.build.version.sdk",
    "ro.build.version.security_patch",
    "ro.product.cpu.abi",
    "persist.sys.dalvik.vm.lib.2",
    "dalvik.vm.usejit",
    "dalvik.vm.usejitprofiles",
)


def _package_revision(path: Path) -> dict:
    try:
        with path.open("rb") as source:
            content = source.read(65537)
        if len(content) > 65536:
            raise ValueError("SDK package metadata exceeds diagnostic limit")
        text = content.decode("utf-8-sig")
        revisions = re.findall(r"^Pkg\.Revision\s*=\s*([^\r\n]+)$", text, re.MULTILINE)
        if len(revisions) != 1 or re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,3}", revisions[0].strip()) is None:
            raise ValueError("SDK package revision is missing or ambiguous")
        return {"revision": revisions[0].strip()}
    except (OSError, UnicodeError, ValueError) as error:
        return {"unavailable": type(error).__name__}


def snapshot_runtime_environment(device, sdk: Path, api: int) -> dict:
    """Record the installed versions, never alter JIT or relabel a failing run."""
    image = system_image(api)
    report = {
        "system_image": image,
        "sdk_packages": {
            "emulator": _package_revision(sdk / "emulator" / "source.properties"),
            "platform-tools": _package_revision(sdk / "platform-tools" / "source.properties"),
            "system-image": _package_revision(sdk.joinpath(*image.split(";"), "source.properties")),
        },
    }
    try:
        response = device("shell", "getprop", timeout=10)
        if response.returncode:
            report["properties_unavailable"] = "getprop failed"
        else:
            parsed = {}
            for key, value in re.findall(r"^\[([^\]\r\n]+)\]: \[([^\]\r\n]*)\]\s*$", response.stdout, re.MULTILINE):
                if key in RUNTIME_PROPERTIES:
                    if key in parsed:
                        raise ValueError("Runtime property is ambiguous")
                    parsed[key] = value[:512]
            # An absent/empty property means unset, not a disabled JIT. Preserve
            # that distinction when comparing an ART crash to another image.
            report["properties"] = {key: parsed.get(key) for key in RUNTIME_PROPERTIES}
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        if getattr(error, "emulator_transport_lost", False):
            # The caller requires a completely fresh AVD after proven transport
            # loss. A diagnostic read cannot consume that control signal.
            raise
        report["properties_unavailable"] = type(error).__name__
    return report
