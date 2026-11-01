"""Bounded local inference over one private socket, with no HTTP fallback.

One monotonic deadline covers connect, send, HTTP headers and the entire body.
Per-read inactivity timeouts alone do not bound a peer sending occasional bytes.
This closes the client connection, not the model process; the isolated worker has
its own existing native-inference watchdog. There are no retry/watchdog threads.
"""
from __future__ import annotations

import http.client
import json
import os
import socket
import stat
import time

MODEL_ID = "gemma-4-E4B-it-local-0b2a8980ce15"
MODEL_SHA256 = "0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0"
SOCKET = "/run/analyst-local-ai/research.sock"
MAX_INPUT_BYTES = 110_000
MAX_OUTPUT_BYTES = 64_000
MAX_OUTPUT_TOKENS = 1600
TIMEOUT_SECONDS = 240


class LocalAIError(ValueError):
    pass


def ensure_ready():
    try:
        info = os.stat(SOCKET, follow_symlinks=False)
        if not stat.S_ISSOCK(info.st_mode):
            raise OSError
    except OSError:
        raise LocalAIError("local_ai_unavailable") from None


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("local_ai_deadline")
    return remaining


class _DeadlineSocket(socket.socket):
    """socket.makefile/SocketIO reads pass through recv_into on this socket."""
    def __init__(self, deadline):
        super().__init__(socket.AF_UNIX, socket.SOCK_STREAM)
        self._deadline = deadline

    def _arm(self):
        self.settimeout(_remaining(self._deadline))

    def connect(self, address):
        self._arm()
        return super().connect(address)

    def sendall(self, data, flags=0):
        self._arm()
        return super().sendall(data, flags)

    def recv_into(self, buffer, nbytes=0, flags=0):
        self._arm()
        return super().recv_into(buffer, nbytes, flags)

    def recv(self, bufsize, flags=0):
        self._arm()
        return super().recv(bufsize, flags)


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, host, *, timeout, deadline):
        super().__init__(host, timeout=timeout)
        self._deadline = deadline

    def connect(self):
        self.sock = _DeadlineSocket(self._deadline)
        self.sock.connect(SOCKET)


def complete(messages, max_output_tokens):
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= MAX_OUTPUT_TOKENS:
        raise LocalAIError("local_ai_output_limit_exceeded")
    try:
        payload = json.dumps({"messages": messages, "max_output_tokens": max_output_tokens},
                             ensure_ascii=False, allow_nan=False).encode("utf-8", "strict")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise LocalAIError("local_ai_request_invalid") from None
    if len(payload) > MAX_INPUT_BYTES:
        raise LocalAIError("local_ai_context_too_large")
    deadline = time.monotonic() + TIMEOUT_SECONDS
    connection = UnixConnection("local-ai", timeout=TIMEOUT_SECONDS, deadline=deadline)
    response = None
    try:
        connection.request("POST", "/complete", body=payload,
                           headers={"Content-Type": "application/json", "Accept-Encoding": "identity"})
        response = connection.getresponse()
        if response.status != 200:
            raise LocalAIError("local_ai_unavailable")
        if response.getheader("X-Model-SHA256") != MODEL_SHA256:
            raise LocalAIError("local_ai_model_changed")
        if response.getheader("Content-Encoding", "identity") != "identity":
            raise LocalAIError("local_ai_encoding_invalid")
        raw = response.read(MAX_OUTPUT_BYTES + 1)
        _remaining(deadline)
        if len(raw) > MAX_OUTPUT_BYTES:
            raise LocalAIError("local_ai_response_too_large")
        return raw
    except TimeoutError:
        raise LocalAIError("local_ai_timeout") from None
    except (OSError, http.client.HTTPException):
        raise LocalAIError("local_ai_unavailable") from None
    finally:
        # HTTP/1.0/Connection:close can detach the response from HTTPConnection.
        # Close both, including partial/oversized bodies and rejected headers.
        try:
            if response is not None:
                response.close()
        finally:
            connection.close()
