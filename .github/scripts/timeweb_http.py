"""Bounded, non-redirecting HTTP transport for the Timeweb reconcilers."""

from __future__ import annotations

import http.client
import io
import json
import re
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from email.message import Message
from pathlib import Path
from typing import Any

MAX_RESPONSE_BYTES = 2_000_000
TIMEWEB_HOST = "api.timeweb.cloud"


def release_version() -> str:
    """Read the reviewed checkout's version before the application is installed."""
    project = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with project.open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    if (not isinstance(version, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}", version) is None):
        raise ValueError("The reviewed project version is invalid")
    return version


def release_user_agent(component: str) -> str:
    """Keep public deployment probes attributable to the actual release version."""
    return f"{component}/{release_version()}"


def _safe_error_body(payload: object) -> io.BytesIO:
    """Retain capacity codes without reflected request data or identifiers."""
    code = payload.get("error_code", "") if isinstance(payload, dict) else ""
    safe_error = {"error_code": code if isinstance(code, str) and code in {
        "no_free_node", "servers_is_run_out_error",
    } else "unknown"}
    return io.BytesIO(json.dumps(safe_error).encode("utf-8"))


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
            except ValueError:
                payload = None
            if not 200 <= response.status < 300:
                raise urllib.error.HTTPError(
                    request.full_url, response.status, "Timeweb API request failed", Message(),
                    _safe_error_body(payload),
                )
            if not isinstance(payload, dict):
                raise urllib.error.URLError("Timeweb API response is not a JSON object")
            return payload
    except urllib.error.URLError:
        raise
    except (OSError, http.client.HTTPException) as exc:
        # A mutation may already have happened; callers must reconcile, not retry.
        raise urllib.error.URLError("Timeweb API transport failed") from exc
