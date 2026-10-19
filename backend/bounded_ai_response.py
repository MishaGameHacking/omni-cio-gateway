"""Bound both wire bytes and decoded bytes before parsing a paid AI response.

Only identity and gzip are negotiated. Read raw HTTP bytes: iter_bytes() can
inflate an entire compression bomb before its caller can enforce a size limit.
No unbounded flush, automatic retry, response-body logging or global state.
"""
from __future__ import annotations

from collections.abc import Callable
import math
import time
import zlib

import httpx

ACCEPT_ENCODING = "gzip, identity"
MAX_GZIP_MEMBERS = 16


class ResponseBodyError(RuntimeError):
    """Fixed non-secret error code; the caller preserves uncertain accounting."""


def _check_deadline(deadline: float, clock: Callable[[], float]) -> None:
    if clock() >= deadline:
        raise ResponseBodyError("ai_response_deadline")


def _append(data: bytearray, chunk: bytes, limit: int) -> None:
    # Check BEFORE copying into the retained body, not after allocation.
    if len(chunk) > limit - len(data):
        raise ResponseBodyError("ai_response_too_large")
    data.extend(chunk)


def _encoding(response: httpx.Response) -> str:
    value = response.headers.get("Content-Encoding", "identity").strip().lower()
    if value not in {"identity", "gzip"}:
        raise ResponseBodyError("ai_response_encoding_unsupported")
    return value


class _GzipBody:
    def __init__(self) -> None:
        self.decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        self.members = 1

    def _next_member(self) -> None:
        if self.decoder.eof:
            self.members += 1
            if self.members > MAX_GZIP_MEMBERS:
                raise ResponseBodyError("ai_response_gzip_members_exceeded")
            self.decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)

    def append(self, chunk: bytes, data: bytearray, limit: int) -> None:
        # A concatenated gzip body is ONE document; never ignore later members.
        while chunk:
            self._next_member()
            try:
                decoded = self.decoder.decompress(chunk, limit - len(data) + 1)
            except zlib.error:
                raise ResponseBodyError("ai_response_encoding_invalid") from None
            _append(data, decoded, limit)
            chunk = self.decoder.unconsumed_tail or self.decoder.unused_data

    def finish(self) -> None:
        # flush(length) does NOT impose a maximum output size. With the bounded
        # decompression above all complete output is already collected.
        if not self.decoder.eof:
            raise ResponseBodyError("ai_response_encoding_invalid")


def _validate_limits(limit: int, deadline: float) -> None:
    if type(limit) is not int or not 1 <= limit <= 2 * 1024 * 1024:
        raise ValueError("ai_response_limit_invalid")
    if isinstance(deadline, bool) or not isinstance(deadline, (int, float)) or not math.isfinite(deadline):
        raise ValueError("ai_response_deadline_invalid")


def _buffered_body(response: httpx.Response, encoding: str, limit: int) -> bytes:
    # MockTransport and explicitly pre-read identity responses have no raw
    # stream left. Encoded pre-read content cannot prove bounded decompression.
    if encoding != "identity":
        raise ResponseBodyError("ai_response_encoded_body_already_read")
    data = response.content
    if len(data) > limit:
        raise ResponseBodyError("ai_response_too_large")
    return data


def read_bounded_body(response: httpx.Response, *, limit: int, deadline: float,
                      clock: Callable[[], float] = time.monotonic) -> bytes:
    """Collect a bounded identity/gzip body, preserving HTTPX transport errors.

    The response must be enclosed in the caller's stream context, which closes
    the connection on every failure. The deadline is checked at entry, every raw
    chunk and EOF; a blocking socket read is additionally bounded by HTTPX's
    read timeout, not preempted by this synchronous collector.
    """
    _validate_limits(limit, deadline)
    _check_deadline(deadline, clock)
    encoding = _encoding(response)
    if response.is_stream_consumed:
        data = _buffered_body(response, encoding, limit)
        _check_deadline(deadline, clock)
        return data
    decoder = _GzipBody() if encoding == "gzip" else None
    data = bytearray()
    wire_bytes = 0
    for chunk in response.iter_raw():
        _check_deadline(deadline, clock)
        wire_bytes += len(chunk)
        if wire_bytes > limit:
            raise ResponseBodyError("ai_response_wire_too_large")
        if decoder is None:
            _append(data, chunk, limit)
        else:
            decoder.append(chunk, data, limit)
    _check_deadline(deadline, clock)
    if decoder is not None:
        decoder.finish()
    return bytes(data)
