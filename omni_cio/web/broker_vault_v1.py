from __future__ import annotations

from collections.abc import Callable
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import secrets


READ_CONNECTION_ROOT = Path(
    r"C:\ProgramData\OmniCIO\secrets\read-broker\connections"
)
READ_CONNECTION_MARKER = ".omni-cio-wp17-read-vault-owned"
READ_CONNECTION_MARKER_VALUE = "OMNI-CIO-V10-WP17-READ-CONNECTION-VAULT-v1"
_SECRET_REF_RE = re.compile(r"^read-connection:v1:(?P<digest>[a-f0-9]{64})$")
_CRYPTPROTECT_LOCAL_MACHINE = 0x4


class ReadConnectionVaultError(RuntimeError):
    """Fail-closed error for the WP17 connection-scoped READ secret boundary."""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def new_read_connection_secret_ref() -> str:
    return f"read-connection:v1:{secrets.token_hex(32)}"


def _digest_from_ref(secret_ref: str) -> str:
    match = _SECRET_REF_RE.fullmatch(secret_ref)
    if match is None:
        raise ReadConnectionVaultError("READ_CONNECTION_SECRET_REF_INVALID")
    return match.group("digest")


def _zero(buffer: bytearray) -> None:
    for index in range(len(buffer)):
        buffer[index] = 0


def _windows_protect(payload: bytes) -> bytes:
    if os.name != "nt":
        raise ReadConnectionVaultError("WINDOWS_DPAPI_REQUIRED")
    if not payload:
        raise ReadConnectionVaultError("READ_CONNECTION_PLAINTEXT_EMPTY")
    windll_type = getattr(ctypes, "WinDLL", None)
    if windll_type is None:
        raise ReadConnectionVaultError("WINDOWS_DPAPI_UNAVAILABLE")
    crypt32 = windll_type("crypt32", use_last_error=True)
    kernel32 = windll_type("kernel32", use_last_error=True)
    protect = crypt32.CryptProtectData
    protect.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.c_wchar_p,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    protect.restype = wintypes.BOOL
    local_free = kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p

    input_buffer = ctypes.create_string_buffer(payload)
    input_blob = _DataBlob(
        len(payload),
        ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    output_blob = _DataBlob()
    if not protect(
        ctypes.byref(input_blob),
        "Omni-CIO V10 WP17 READ connection",
        None,
        None,
        None,
        _CRYPTPROTECT_LOCAL_MACHINE,
        ctypes.byref(output_blob),
    ):
        raise ReadConnectionVaultError("READ_CONNECTION_DPAPI_ENCRYPT_FAILED")
    try:
        if not output_blob.pbData or output_blob.cbData <= 0:
            raise ReadConnectionVaultError("READ_CONNECTION_DPAPI_OUTPUT_EMPTY")
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        if output_blob.pbData and output_blob.cbData > 0:
            ctypes.memset(output_blob.pbData, 0, output_blob.cbData)
        if output_blob.pbData:
            local_free(output_blob.pbData)


def _windows_unprotect(payload: bytes) -> bytes:
    if os.name != "nt":
        raise ReadConnectionVaultError("WINDOWS_DPAPI_REQUIRED")
    if not payload:
        raise ReadConnectionVaultError("READ_CONNECTION_CIPHERTEXT_EMPTY")
    windll_type = getattr(ctypes, "WinDLL", None)
    if windll_type is None:
        raise ReadConnectionVaultError("WINDOWS_DPAPI_UNAVAILABLE")
    crypt32 = windll_type("crypt32", use_last_error=True)
    kernel32 = windll_type("kernel32", use_last_error=True)
    unprotect = crypt32.CryptUnprotectData
    unprotect.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(ctypes.c_wchar_p),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    unprotect.restype = wintypes.BOOL
    local_free = kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p

    input_buffer = ctypes.create_string_buffer(payload)
    input_blob = _DataBlob(
        len(payload),
        ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    output_blob = _DataBlob()
    if not unprotect(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    ):
        raise ReadConnectionVaultError("READ_CONNECTION_DPAPI_DECRYPT_FAILED")
    try:
        if not output_blob.pbData or output_blob.cbData <= 0:
            raise ReadConnectionVaultError("READ_CONNECTION_DPAPI_OUTPUT_EMPTY")
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        if output_blob.pbData and output_blob.cbData > 0:
            ctypes.memset(output_blob.pbData, 0, output_blob.cbData)
        if output_blob.pbData:
            local_free(output_blob.pbData)


class ReadBrokerConnectionVaultV1:
    def __init__(
        self,
        *,
        root: Path = READ_CONNECTION_ROOT,
        protect: Callable[[bytes], bytes] | None = None,
        unprotect: Callable[[bytes], bytes] | None = None,
        require_marker: bool = True,
    ) -> None:
        self._root = root
        self._protect = protect or _windows_protect
        self._unprotect = unprotect or _windows_unprotect
        self._require_marker = require_marker

    def _require_ready(self) -> None:
        if not self._root.is_dir():
            raise ReadConnectionVaultError("READ_CONNECTION_VAULT_NOT_PROVISIONED")
        if not self._require_marker:
            return
        marker = self._root / READ_CONNECTION_MARKER
        try:
            value = marker.read_text(encoding="ascii")
        except OSError as exc:
            raise ReadConnectionVaultError("READ_CONNECTION_VAULT_MARKER_MISSING") from exc
        if value != READ_CONNECTION_MARKER_VALUE:
            raise ReadConnectionVaultError("READ_CONNECTION_VAULT_MARKER_INVALID")

    def _path(self, secret_ref: str) -> Path:
        digest = _digest_from_ref(secret_ref)
        return self._root / f"{digest}.dpapi"

    def store(self, *, secret_ref: str, token: str) -> None:
        self._require_ready()
        normalized = token.strip()
        if not normalized or len(normalized) > 16384:
            raise ReadConnectionVaultError("READ_CONNECTION_TOKEN_INVALID")
        plaintext = bytearray(normalized.encode("utf-8"))
        protected = bytearray()
        destination = self._path(secret_ref)
        temporary = self._root / f".{destination.name}.{secrets.token_hex(8)}.tmp"
        try:
            protected.extend(self._protect(bytes(plaintext)))
            if not protected:
                raise ReadConnectionVaultError("READ_CONNECTION_CIPHERTEXT_EMPTY")
            with temporary.open("xb") as handle:
                handle.write(protected)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        except OSError as exc:
            raise ReadConnectionVaultError("READ_CONNECTION_SECRET_WRITE_FAILED") from exc
        finally:
            _zero(plaintext)
            _zero(protected)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def load(self, *, secret_ref: str) -> str:
        self._require_ready()
        path = self._path(secret_ref)
        try:
            protected = path.read_bytes()
        except OSError as exc:
            raise ReadConnectionVaultError("READ_CONNECTION_SECRET_UNAVAILABLE") from exc
        plaintext = bytearray()
        try:
            plaintext.extend(self._unprotect(protected))
            try:
                token = plaintext.decode("utf-8").strip()
            except UnicodeDecodeError as exc:
                raise ReadConnectionVaultError(
                    "READ_CONNECTION_PLAINTEXT_ENCODING_INVALID"
                ) from exc
            if not token:
                raise ReadConnectionVaultError("READ_CONNECTION_TOKEN_EMPTY")
            return token
        finally:
            _zero(plaintext)

    def revoke(self, *, secret_ref: str) -> bool:
        self._require_ready()
        path = self._path(secret_ref)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise ReadConnectionVaultError("READ_CONNECTION_SECRET_DELETE_FAILED") from exc
        return True
