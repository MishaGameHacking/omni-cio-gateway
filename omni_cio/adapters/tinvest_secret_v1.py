from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
from typing import Any


BROKER_READ_BLOB = Path(
    r"C:\ProgramData\OmniCIO\secrets\read-broker\broker-read.dpapi"
)
WP8_STATE = Path(r"C:\ProgramData\OmniCIO\wp8\wp8-secret-store-state.json")


class BrokerReadSecretError(RuntimeError):
    """Fail-closed error for the local WP8 broker-read credential boundary."""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _windows_unprotect(payload: bytes) -> bytes:
    if os.name != "nt":
        raise BrokerReadSecretError("WINDOWS_DPAPI_REQUIRED")
    if not payload:
        raise BrokerReadSecretError("BROKER_READ_CIPHERTEXT_EMPTY")

    windll_type = getattr(ctypes, "WinDLL", None)
    if windll_type is None:
        raise BrokerReadSecretError("WINDOWS_DPAPI_UNAVAILABLE")
    crypt32 = windll_type("crypt32", use_last_error=True)
    kernel32 = windll_type("kernel32", use_last_error=True)

    crypt_unprotect = crypt32.CryptUnprotectData
    crypt_unprotect.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(ctypes.c_wchar_p),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt_unprotect.restype = wintypes.BOOL

    local_free = kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p

    input_buffer = ctypes.create_string_buffer(payload)
    input_blob = _DataBlob(
        len(payload),
        ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    output_blob = _DataBlob()
    if not crypt_unprotect(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    ):
        raise BrokerReadSecretError("BROKER_READ_DPAPI_DECRYPT_FAILED")

    try:
        if not output_blob.pbData or output_blob.cbData <= 0:
            raise BrokerReadSecretError("BROKER_READ_DPAPI_OUTPUT_EMPTY")
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        if output_blob.pbData and output_blob.cbData > 0:
            ctypes.memset(output_blob.pbData, 0, output_blob.cbData)
        if output_blob.pbData:
            local_free(output_blob.pbData)


def _broker_read_lifecycle(state: dict[str, Any]) -> dict[str, Any]:
    classes = state.get("classes", [])
    if not isinstance(classes, list):
        raise BrokerReadSecretError("WP8_SECRET_STATE_INVALID")
    for entry in classes:
        if (
            isinstance(entry, dict)
            and str(entry.get("secret_class", "")) == "broker_read"
        ):
            return entry
    raise BrokerReadSecretError("BROKER_READ_SECRET_STATE_MISSING")


def require_broker_read_active(
    *,
    state_path: Path = WP8_STATE,
) -> None:
    try:
        raw = state_path.read_text(encoding="utf-8-sig")
        state = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BrokerReadSecretError("WP8_SECRET_STATE_UNAVAILABLE") from exc
    if not isinstance(state, dict) or str(state.get("schema_version", "")) != "1":
        raise BrokerReadSecretError("WP8_SECRET_STATE_INVALID")
    entry = _broker_read_lifecycle(state)
    if (
        str(entry.get("state", "")) != "ACTIVE"
        or not bool(entry.get("provisioned"))
        or bool(entry.get("compromised"))
    ):
        raise BrokerReadSecretError("BROKER_READ_SECRET_NOT_ACTIVE")


def load_broker_read_token(
    *,
    blob_path: Path = BROKER_READ_BLOB,
    state_path: Path = WP8_STATE,
    unprotect: Callable[[bytes], bytes] | None = None,
) -> str:
    """Decrypt the WP8 broker-read DPAPI blob without CLI/env transport."""
    require_broker_read_active(state_path=state_path)
    try:
        protected = blob_path.read_bytes()
    except OSError as exc:
        raise BrokerReadSecretError("BROKER_READ_CIPHERTEXT_UNAVAILABLE") from exc

    decrypt = unprotect or _windows_unprotect
    plaintext = bytearray()
    try:
        plaintext.extend(decrypt(protected))
        if not plaintext or len(plaintext) % 2 != 0:
            raise BrokerReadSecretError("BROKER_READ_PLAINTEXT_ENCODING_INVALID")
        try:
            token = plaintext.decode("utf-16-le").strip()
        except UnicodeDecodeError as exc:
            raise BrokerReadSecretError(
                "BROKER_READ_PLAINTEXT_ENCODING_INVALID"
            ) from exc
        if not token:
            raise BrokerReadSecretError("BROKER_READ_TOKEN_EMPTY")
        return token
    finally:
        for index in range(len(plaintext)):
            plaintext[index] = 0


@contextmanager
def broker_read_client() -> Iterator[Any]:
    """Create the production T-Invest client from the protected WP8 read secret."""
    os.environ.setdefault("SSL_TBANK_VERIFY", "True")
    from t_tech.invest import Client

    token = load_broker_read_token()
    try:
        with Client(token) as client:
            yield client
    finally:
        token = ""
