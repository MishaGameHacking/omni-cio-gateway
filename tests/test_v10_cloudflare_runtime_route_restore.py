from __future__ import annotations

from urllib.parse import quote
import unittest

from apps.api.cloudflare_runtime import (
    CloudflareEdgeRouteRestoreV1,
    _INTERNAL_PROXY_PATH,
    _validated_route,
)


_SHA = "a" * 40


def _encoded(value: str) -> bytes:
    return quote(value, safe="~()*!.'-").encode("ascii")


def _scope(*, raw_path: str = "/api/v10/example", raw_query: str = "") -> dict:
    return {
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "path": _INTERNAL_PROXY_PATH,
        "raw_path": _INTERNAL_PROXY_PATH.encode("ascii"),
        "query_string": b"",
        "headers": [
            (b"host", b"omni-cio.internal"),
            (b"x-omni-edge-provider", b"cloudflare"),
            (b"x-omni-source-sha", _SHA.encode("ascii")),
            (b"x-omni-route-path", _encoded(raw_path)),
            (b"x-omni-route-query", _encoded(raw_query)),
        ],
    }


class CloudflareRuntimeRouteTests(unittest.IsolatedAsyncioTestCase):
    def test_validated_route_restores_api_path_and_query(self) -> None:
        path, raw_path, query = _validated_route(
            _scope(
                raw_path="/api/v10/example%20item",
                raw_query="page=1%20two",
            ),
            _SHA,
        )
        self.assertEqual(path, "/api/v10/example item")
        self.assertEqual(raw_path, b"/api/v10/example%20item")
        self.assertEqual(query, b"page=1%20two")

    def test_validated_route_rejects_non_api_path(self) -> None:
        scope = _scope(raw_path="/private")
        with self.assertRaisesRegex(ValueError, "outside API boundary"):
            _validated_route(scope, _SHA)

    def test_validated_route_rejects_wrong_release_sha(self) -> None:
        scope = _scope()
        headers = list(scope["headers"])
        headers[2] = (b"x-omni-source-sha", ("b" * 40).encode("ascii"))
        scope["headers"] = headers
        with self.assertRaisesRegex(ValueError, "source sha invalid"):
            _validated_route(scope, _SHA)

    async def test_wrapper_restores_scope_and_removes_route_headers(self) -> None:
        captured: list[dict] = []

        async def app(scope, receive, send) -> None:
            del receive, send
            captured.append(scope)

        async def receive() -> dict:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: dict) -> None:
            del message

        wrapper = CloudflareEdgeRouteRestoreV1(app, release_sha=_SHA)
        await wrapper(
            _scope(raw_path="/healthz", raw_query="probe=1"),
            receive,
            send,
        )
        self.assertEqual(len(captured), 1)
        restored = captured[0]
        self.assertEqual(restored["path"], "/healthz")
        self.assertEqual(restored["raw_path"], b"/healthz")
        self.assertEqual(restored["query_string"], b"probe=1")
        header_names = {key.lower() for key, _ in restored["headers"]}
        self.assertNotIn(b"x-omni-route-path", header_names)
        self.assertNotIn(b"x-omni-route-query", header_names)

    async def test_wrapper_rejects_direct_non_proxy_http_request(self) -> None:
        messages: list[dict] = []

        async def app(scope, receive, send) -> None:
            del scope, receive, send
            self.fail("downstream app must not receive direct container HTTP ingress")

        async def receive() -> dict:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: dict) -> None:
            messages.append(message)

        scope = _scope()
        scope["path"] = "/healthz"
        wrapper = CloudflareEdgeRouteRestoreV1(app, release_sha=_SHA)
        await wrapper(scope, receive, send)
        self.assertEqual(messages[0]["status"], 404)

    async def test_wrapper_rejects_websocket_with_websocket_close(self) -> None:
        messages: list[dict] = []

        async def app(scope, receive, send) -> None:
            del scope, receive, send
            self.fail("downstream app must not receive direct websocket ingress")

        async def receive() -> dict:
            return {"type": "websocket.connect"}

        async def send(message: dict) -> None:
            messages.append(message)

        scope = _scope()
        scope["type"] = "websocket"
        wrapper = CloudflareEdgeRouteRestoreV1(app, release_sha=_SHA)
        await wrapper(scope, receive, send)
        self.assertEqual(messages, [{"type": "websocket.close", "code": 1008}])


if __name__ == "__main__":
    unittest.main()
