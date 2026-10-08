"""Bounded, non-redirecting HTTP transport for the Timeweb reconcilers."""

from __future__ import annotations

import http.client
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from email.message import Message
from typing import Any

MAX_RESPONSE_BYTES = 2_000_000
TIMEWEB_HOST = "api.timeweb.cloud"


def request_json(request: urllib.request.Request, *, timeout: int) -> dict[str, Any]:
    """Send once to the API origin; redirects never receive credentials or bodies."""
    parsed = urllib.parse.urlsplit(request.full_url)
    if (parsed.scheme != "https" or parsed.netloc != TIMEWEB_HOST
            or not parsed.path.startswith("/api/") or parsed.fragment):
        raise urllib.error.URLError("Invalid Timeweb API origin")
    target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    try:
        with closing(http.client.HTTPSConnection(TIMEWEB_HOST, timeout=timeout)) as connection:
            connection.request(
                request.get_method(), target, body=request.data,
                headers=dict(request.header_items()),
            )
            response = connection.getresponse()
            expected_length = response.length
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise urllib.error.URLError("Timeweb API response is too large")
            if expected_length is not None and len(body) != expected_length:
                raise urllib.error.URLError("Timeweb API response is incomplete")
            try:
                payload = json.loads(body) if body else {}
            except (ValueError, UnicodeError):
                payload = None
            if not 200 <= response.status < 300:
                # Never propagate reflected request data, messages or identifiers.
                # Capacity codes remain available to the existing fallback policy.
                code = payload.get("error_code", "") if isinstance(payload, dict) else ""
                safe_error = {"error_code": code if isinstance(code, str) and code in {
                    "no_free_node", "servers_is_run_out_error",
                } else "unknown"}
                raise urllib.error.HTTPError(
                    request.full_url, response.status, "Timeweb API request failed", Message(),
                    io.BytesIO(json.dumps(safe_error).encode("utf-8")),
                )
            if not isinstance(payload, dict):
                raise urllib.error.URLError("Timeweb API response is not a JSON object")
            return payload
    except urllib.error.URLError:
        raise
    except (OSError, http.client.HTTPException) as exc:
        # A mutation may already have happened; callers must reconcile, not retry.
        raise urllib.error.URLError("Timeweb API transport failed") from exc
