"""Bounded local inference over one private socket, with no HTTP fallback."""
from __future__ import annotations

import http.client
import json
import os
import socket
import stat

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


class UnixConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(TIMEOUT_SECONDS)
        self.sock.connect(SOCKET)


def complete(messages, max_output_tokens):
    payload = json.dumps({"messages": messages, "max_output_tokens": max_output_tokens},
                         ensure_ascii=False, allow_nan=False).encode()
    if len(payload) > MAX_INPUT_BYTES:
        raise LocalAIError("local_ai_context_too_large")
    connection = UnixConnection("local-ai", timeout=TIMEOUT_SECONDS)
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
        if len(raw) > MAX_OUTPUT_BYTES:
            raise LocalAIError("local_ai_response_too_large")
        return raw
    except (OSError, http.client.HTTPException):
        raise LocalAIError("local_ai_unavailable") from None
    finally:
        connection.close()
