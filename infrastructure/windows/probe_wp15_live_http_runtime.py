from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection, HTTPResponse
from http.cookies import SimpleCookie
import json
import sys
from typing import Any


EXIT_LOGIN = 81
EXIT_COOKIE = 82
EXIT_SESSION = 83
EXIT_PARALLEL_DOWNSTREAM = 84
EXIT_LIVE_STATUS = 85
EXIT_LOGOUT = 86


def _request(
    port: int,
    method: str,
    path: str,
    *,
    cookie: str | None = None,
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    headers = {"Connection": "close"}
    if cookie:
        headers["Cookie"] = cookie
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers)
        response: HTTPResponse = connection.getresponse()
        payload = response.read()
        return response.status, {key.lower(): value for key, value in response.getheaders()}, payload
    finally:
        connection.close()


def _json_object(payload: bytes) -> dict[str, Any] | None:
    try:
        value = json.loads(payload.decode("utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _json_list(payload: bytes) -> list[Any] | None:
    try:
        value = json.loads(payload.decode("utf-8"))
    except Exception:
        return None
    return value if isinstance(value, list) else None


def _session_cookie(set_cookie: str | None) -> str | None:
    if not set_cookie:
        return None
    parsed = SimpleCookie()
    try:
        parsed.load(set_cookie)
    except Exception:
        return None
    morsel = parsed.get("omni_v10_session")
    if morsel is None or not morsel.value:
        return None
    return f"omni_v10_session={morsel.value}"


def _parallel_authenticated_reads(port: int, cookie: str) -> bool:
    paths = (
        "/api/v10/web/health",
        "/api/v10/web/broker-connections",
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_request, port, "GET", path, cookie=cookie) for path in paths]
        results = [future.result(timeout=8) for future in futures]

    health_status, _, health_payload = results[0]
    broker_status, _, broker_payload = results[1]
    if health_status != 200 or broker_status != 200:
        return False
    health = _json_object(health_payload)
    brokers = _json_list(broker_payload)
    return (
        health is not None
        and isinstance(health.get("state"), str)
        and isinstance(health.get("freshness"), str)
        and brokers is not None
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        return EXIT_LOGIN
    try:
        port = int(argv[1])
    except ValueError:
        return EXIT_LOGIN
    if port < 1024 or port > 65535:
        return EXIT_LOGIN

    cookie = ""
    logged_in = False
    result = 0
    try:
        try:
            status, headers, payload = _request(
                port,
                "POST",
                "/api/v10/web/private-test-login",
                body=b"{}",
            )
        except Exception:
            return EXIT_LOGIN
        if status != 200 or _json_object(payload) != {"ok": True}:
            return EXIT_LOGIN

        cookie_value = _session_cookie(headers.get("set-cookie"))
        if not cookie_value:
            return EXIT_COOKIE
        cookie = cookie_value
        logged_in = True

        try:
            status, _, payload = _request(
                port,
                "GET",
                "/api/v10/web/session",
                cookie=cookie,
            )
        except Exception:
            result = EXIT_SESSION
        else:
            session = _json_object(payload)
            if status != 200 or session is None or session.get("authenticated") is not True:
                result = EXIT_SESSION

        if result == 0:
            try:
                if not _parallel_authenticated_reads(port, cookie):
                    result = EXIT_PARALLEL_DOWNSTREAM
            except Exception:
                result = EXIT_PARALLEL_DOWNSTREAM

        if result == 0:
            try:
                status, _, payload = _request(
                    port,
                    "GET",
                    "/api/v10/web/wp15-live-acceptance/status",
                    cookie=cookie,
                )
            except Exception:
                result = EXIT_LIVE_STATUS
            else:
                live = _json_object(payload)
                if status != 200 or live != {"enabled": True}:
                    result = EXIT_LIVE_STATUS
    finally:
        if logged_in and cookie:
            try:
                status, _, payload = _request(
                    port,
                    "POST",
                    "/api/v10/web/session/logout",
                    cookie=cookie,
                    body=b"{}",
                )
                if status != 200 or _json_object(payload) != {"ok": True}:
                    if result == 0:
                        result = EXIT_LOGOUT
            except Exception:
                if result == 0:
                    result = EXIT_LOGOUT
        cookie = ""

    if result == 0:
        print("WP15_LIVE_HTTP_RUNTIME_PROBE_PASS")
    return result


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
