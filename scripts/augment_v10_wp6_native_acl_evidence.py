from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterable


SENTINEL_PATH = Path(
    r"C:\ProgramData\OmniCIO\secrets\execution\wp6-ci-deny-sentinel.txt"
)
RUNNER_ROOT = Path(r"C:\actions-runner")
RUNNER_SERVICE_MARKER = RUNNER_ROOT / ".service"
SE_FILE_OBJECT = 1
DACL_SECURITY_INFORMATION = 0x00000004
ACL_SIZE_INFORMATION_CLASS = 2
ACCESS_ALLOWED_ACE_TYPE = 0x00
ACCESS_DENIED_ACE_TYPE = 0x01
FILE_READ_DATA = 0x00000001
BROAD_READ_SIDS = frozenset({"S-1-1-0", "S-1-5-11", "S-1-5-32-545"})


class NativeAclError(RuntimeError):
    pass


@dataclass(frozen=True)
class IdentitySids:
    runner: str
    runtime: str
    execution: str


@dataclass(frozen=True)
class Ace:
    ace_type: int
    sid: str
    mask: int


@dataclass(frozen=True)
class AclEvidence:
    execution_read_data: bool
    runtime_read_data: bool
    runner_read_data: bool
    broad_read_data: bool


class ACL_SIZE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("AceCount", wintypes.DWORD),
        ("AclBytesInUse", wintypes.DWORD),
        ("AclBytesFree", wintypes.DWORD),
    ]


def classify_aces(aces: Iterable[Ace], identities: IdentitySids) -> AclEvidence:
    allow_masks: dict[str, int] = {}
    deny_masks: dict[str, int] = {}
    for ace in aces:
        target = allow_masks if ace.ace_type == ACCESS_ALLOWED_ACE_TYPE else deny_masks
        target[ace.sid] = target.get(ace.sid, 0) | int(ace.mask)

    def direct_read_data(sid: str) -> bool:
        allowed = bool(allow_masks.get(sid, 0) & FILE_READ_DATA)
        denied = bool(deny_masks.get(sid, 0) & FILE_READ_DATA)
        return allowed and not denied

    return AclEvidence(
        execution_read_data=direct_read_data(identities.execution),
        runtime_read_data=direct_read_data(identities.runtime),
        runner_read_data=direct_read_data(identities.runner),
        broad_read_data=any(direct_read_data(sid) for sid in BROAD_READ_SIDS),
    )


def resolve_identity_sids() -> IdentitySids:
    if os.name != "nt":
        raise NativeAclError("WINDOWS_REQUIRED")

    command = (
        "$ErrorActionPreference='Stop';"
        "$marker='C:\\actions-runner\\.service';"
        "if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { throw 'runner-service-marker-missing' };"
        "$serviceName=(Get-Content -LiteralPath $marker -Raw -ErrorAction Stop).Trim();"
        "if (-not $serviceName.StartsWith('actions.runner.', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'runner-service-marker-invalid' };"
        "$services=@(Get-CimInstance Win32_Service | Where-Object { $_.Name -eq $serviceName });"
        "if ($services.Count -ne 1) { throw 'runner-service-binding' };"
        "$runnerSid=([System.Security.Principal.NTAccount]::new($services[0].StartName)).Translate("
        "[System.Security.Principal.SecurityIdentifier]).Value;"
        "$runtimeSid=(Get-LocalUser -Name 'omni-cio-runtime' -ErrorAction Stop).SID.Value;"
        "$executionSid=(Get-LocalUser -Name 'omni-cio-execution' -ErrorAction Stop).SID.Value;"
        "[ordered]@{runner=$runnerSid;runtime=$runtimeSid;execution=$executionSid} | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise NativeAclError("IDENTITY_RESOLUTION_FAILED")
    try:
        payload = json.loads(completed.stdout)
        identities = IdentitySids(
            runner=str(payload["runner"]),
            runtime=str(payload["runtime"]),
            execution=str(payload["execution"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise NativeAclError("IDENTITY_RESOLUTION_INVALID") from exc
    if not all(value.startswith("S-") for value in identities.__dict__.values()):
        raise NativeAclError("IDENTITY_RESOLUTION_INVALID")
    return identities


def _sid_to_string(
    advapi32: ctypes.WinDLL, kernel32: ctypes.WinDLL, sid_ptr: int
) -> str:
    convert = advapi32.ConvertSidToStringSidW
    convert.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    convert.restype = wintypes.BOOL
    local_free = kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p

    output = wintypes.LPWSTR()
    if not convert(ctypes.c_void_p(sid_ptr), ctypes.byref(output)):
        raise NativeAclError("SID_CONVERSION_FAILED")
    try:
        value = output.value
        if not value:
            raise NativeAclError("SID_CONVERSION_FAILED")
        return value
    finally:
        local_free(ctypes.cast(output, ctypes.c_void_p))


def read_native_dacl_aces(path: Path) -> list[Ace]:
    if os.name != "nt":
        raise NativeAclError("WINDOWS_REQUIRED")

    advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    kernel32 = ctypes.WinDLL("Kernel32.dll", use_last_error=True)

    get_named_security_info = advapi32.GetNamedSecurityInfoW
    get_named_security_info.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_int,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    get_named_security_info.restype = wintypes.DWORD

    get_acl_information = advapi32.GetAclInformation
    get_acl_information.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_int,
    ]
    get_acl_information.restype = wintypes.BOOL

    get_ace = advapi32.GetAce
    get_ace.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    get_ace.restype = wintypes.BOOL

    local_free = kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p

    dacl = ctypes.c_void_p()
    security_descriptor = ctypes.c_void_p()
    result = get_named_security_info(
        str(path),
        SE_FILE_OBJECT,
        DACL_SECURITY_INFORMATION,
        None,
        None,
        ctypes.byref(dacl),
        None,
        ctypes.byref(security_descriptor),
    )
    if result != 0:
        raise NativeAclError(f"NATIVE_DACL_QUERY_FAILED_{result}")
    try:
        if not dacl.value:
            raise NativeAclError("NULL_DACL_FORBIDDEN")

        info = ACL_SIZE_INFORMATION()
        if not get_acl_information(
            dacl,
            ctypes.byref(info),
            ctypes.sizeof(info),
            ACL_SIZE_INFORMATION_CLASS,
        ):
            raise NativeAclError("ACL_INFORMATION_FAILED")

        aces: list[Ace] = []
        for index in range(info.AceCount):
            ace_ptr = ctypes.c_void_p()
            if not get_ace(dacl, index, ctypes.byref(ace_ptr)) or not ace_ptr.value:
                raise NativeAclError("ACE_READ_FAILED")
            ace_type = ctypes.c_ubyte.from_address(ace_ptr.value).value
            if ace_type not in {ACCESS_ALLOWED_ACE_TYPE, ACCESS_DENIED_ACE_TYPE}:
                raise NativeAclError("UNSUPPORTED_DACL_ACE_TYPE")
            mask = ctypes.c_uint32.from_address(ace_ptr.value + 4).value
            sid_ptr = ace_ptr.value + 8
            sid = _sid_to_string(advapi32, kernel32, sid_ptr)
            aces.append(Ace(ace_type=ace_type, sid=sid, mask=mask))
        return aces
    finally:
        if security_descriptor.value:
            local_free(security_descriptor)


def augment_profile(profile_path: Path, evidence: AclEvidence) -> None:
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
        runtime = profile["runtime"]
        execution = profile["execution"]
        boundaries = profile["boundaries"]
        if not all(
            isinstance(section, dict) for section in (runtime, execution, boundaries)
        ):
            raise TypeError
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise NativeAclError("PROFILE_INVALID") from exc

    runtime["execution_secret_direct_read_grant"] = evidence.runtime_read_data
    execution["execution_secret_direct_read_grant"] = evidence.execution_read_data
    boundaries["execution_secret_broad_read_exposure"] = evidence.broad_read_data

    try:
        profile_path.write_text(
            json.dumps(profile, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise NativeAclError("PROFILE_WRITE_FAILED") from exc


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("WP6 native DACL evidence augmentation: FAIL:USAGE", file=sys.stderr)
        return 2

    profile_path = Path(args[0])
    try:
        identities = resolve_identity_sids()
        evidence = classify_aces(read_native_dacl_aces(SENTINEL_PATH), identities)
        if evidence.runner_read_data:
            raise NativeAclError("RUNNER_SENTINEL_DATA_GRANT_PRESENT")
        augment_profile(profile_path, evidence)
    except NativeAclError as exc:
        print(f"WP6 native DACL evidence augmentation: FAIL:{exc}", file=sys.stderr)
        return 1

    print("WP6 native DACL evidence augmentation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
