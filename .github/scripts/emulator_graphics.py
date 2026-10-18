"""Observe the disposable emulator's graphics path; never infer it from a flag.

The system compositor can use Skia/Vulkan independently of the app. Only the
current candidate process's Filament GL header proves its actual GLES context.
These checks supplement the existing native, rendered-frame and UI gates.
"""
from __future__ import annotations

import re
import subprocess


# Use SwiftShader's Vulkan implementation behind guest ANGLE. This is distinct
# from the legacy direct SwiftShader GLES compiler that rejected Filament GLSL.
# Lavapipe booted the API35 guest but stalled all guest commands during install.
EMULATOR_GPU_MODE = "swiftshader"
EMULATOR_FEATURES = "Vulkan,GuestAngle"
MAX_LOG_CHARACTERS = 2 * 1024 * 1024
_HEADER = re.compile(
    r"^\s*(?:[0-9]{4}-)?[0-9]{2}-[0-9]{2}\s+"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+\s+"
    r"(?P<pid>[0-9]+)\s+[0-9]+\s+I\s+Filament\s*:\s*"
    r"\[(?P<vendor>[^\]\r\n]{1,512})\],\s*"
    r"\[(?P<renderer>[^\]\r\n]{1,1536})\],\s*"
    r"\[(?P<version>OpenGL ES [^\]\r\n]{1,512})\],\s*"
    r"\[(?P<shading_language_version>[^\]\r\n]{1,512})\]\s*$"
)


def _identity(value: str, label: str, minimum: int) -> str:
    if not isinstance(value, str) or re.fullmatch(r"\d{1,10}", value.strip(), flags=re.ASCII) is None:
        raise ValueError("Missing or ambiguous candidate " + label)
    number = int(value.strip())
    if not minimum <= number <= 2147483647:
        raise ValueError("Invalid candidate " + label)
    return str(number)


def parse_filament_renderer(output: str, *, uid: str, pid: str) -> dict[str, object]:
    """Parse only a complete GL header from the exact freshly launched process.

    An engine can be recreated within one process. Identical repeated headers
    are retained as a count; conflicting contexts cannot prove the chosen path.
    Commas inside ANGLE's renderer string are part of that field, not separators.
    """
    current_uid = _identity(uid, "UID", 10000)
    current_pid = _identity(pid, "PID", 1)
    if not isinstance(output, str) or len(output) > MAX_LOG_CHARACTERS:
        raise ValueError("Filament context evidence exceeds its bounded log read")
    observed: dict[str, str] | None = None
    count = 0
    for line in output.splitlines():
        match = _HEADER.fullmatch(line)
        if match is None:
            continue
        if match.group("pid") != current_pid:
            raise ValueError("Filament context evidence contains another process")
        header = {key: match.group(key).strip() for key in (
            "vendor", "renderer", "version", "shading_language_version",
        )}
        if not all(header.values()):
            raise ValueError("Filament context evidence contains an empty GL field")
        if observed is not None and observed != header:
            raise ValueError("Filament context evidence contains conflicting GL headers")
        observed = header
        count += 1
    if observed is None:
        raise ValueError("The current candidate process did not report a Filament GL context")
    return {"source": "candidate-filament-logcat", "uid": int(current_uid),
            "pid": int(current_pid), "header_count": count, **observed}


def read_filament_renderer(device, *, uid: str, pid: str) -> dict[str, object]:
    """Use both current package UID and fresh pidof PID, without clearing logs."""
    current_uid = _identity(uid, "UID", 10000)
    current_pid = _identity(pid, "PID", 1)
    result = device(
        "logcat", "-d", "-b", "main", "-v", "threadtime",
        "--uid=" + current_uid, "--pid=" + current_pid, "Filament:I", "*:S",
        timeout=10,
    )
    if result.returncode:
        raise RuntimeError("Could not read the current candidate's Filament GL context")
    return parse_filament_renderer(result.stdout, uid=current_uid, pid=current_pid)


def require_guest_angle(observed: dict[str, object]) -> None:
    """Reject silent fallback to the legacy GLES compiler or missing evidence.

    This proves ANGLE's Vulkan path, not completed rendering or performance.
    The recorded renderer keeps the actual Vulkan device/driver string; the
    requested CLI setting is never substituted for this observation.
    """
    renderer = observed.get("renderer")
    version = observed.get("version")
    if not isinstance(renderer, str) or not isinstance(version, str):
        raise ValueError("Missing actual Filament GLES renderer/version")
    version_match = re.match(r"OpenGL ES (\d+)\.(\d+)\b", version, flags=re.ASCII)
    if version_match is None:
        raise ValueError("Invalid actual Filament GLES version")
    if (int(version_match.group(1)), int(version_match.group(2))) < (3, 0):
        raise ValueError("Filament requires a GLES 3.0 or newer context")
    if re.search(r"\bANGLE\b", renderer) is None or re.search(r"\bVulkan\b", renderer) is None:
        raise ValueError("The candidate did not use the required ANGLE-on-Vulkan GLES compiler")


def snapshot_system_graphics(device) -> dict[str, object]:
    """Bounded pre-launch context, distinct from authoritative app GL evidence.

    A Skia/Vulkan SurfaceFlinger does not have to expose a GLES line. Missing
    diagnostic data is recorded; it never satisfies the later app context gate.
    """
    properties: dict[str, object] = {}
    for name in ("ro.hardware.egl", "ro.hardware.vulkan", "debug.hwui.renderer", "debug.renderengine.backend"):
        try:
            result = device("shell", "getprop", name, timeout=10)
            properties[name] = {"returncode": result.returncode,
                                "value": result.stdout.strip()[:256] if result.returncode == 0 else ""}
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            properties[name] = {"error_type": type(exc).__name__}
    compositor: dict[str, object]
    try:
        result = device("shell", "dumpsys", "SurfaceFlinger", timeout=10)
        lines = []
        if result.returncode == 0:
            for line in result.stdout[:MAX_LOG_CHARACTERS].splitlines():
                if re.search(r"GLES|Vulkan|Skia|RenderEngine", line, re.IGNORECASE):
                    lines.append(line.strip()[:512])
                    if len(lines) == 24:
                        break
        compositor = {"source": "dumpsys SurfaceFlinger", "returncode": result.returncode,
                      "graphics_lines": lines}
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        compositor = {"source": "dumpsys SurfaceFlinger", "error_type": type(exc).__name__}
    return {"requested_gpu_mode": EMULATOR_GPU_MODE, "requested_features": EMULATOR_FEATURES,
            "properties": properties, "system_compositor": compositor}
