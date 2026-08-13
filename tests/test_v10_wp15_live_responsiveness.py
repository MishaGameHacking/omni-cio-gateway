from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import inspect
from pathlib import Path
from types import SimpleNamespace
import threading
import time
from typing import Any

import httpx
from t_tech.invest import Client

import apps.api.app as app_module
from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.web.api_v1 import SESSION_COOKIE, WebApiServicesV1, create_web_api
from omni_cio.web.session_v1 import SessionRegistryV1


NOW = datetime(2026, 8, 13, 5, 0, tzinfo=timezone.utc)
CONNECTION_ID = "broker-connection:v1:" + ("a" * 64)


class _EmptyRepository:
    def list_read_connections(self, *, tenant_id: str) -> tuple[Any, ...]:
        del tenant_id
        return ()


class _BlockingLiveAcceptance:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def start(
        self,
        *,
        user_id: str,
        tenant_id: str,
        connection_id: str,
        account_index: int,
    ) -> Any:
        assert user_id == OWNER_USER_ID
        assert tenant_id == OWNER_TENANT_ID
        assert connection_id == CONNECTION_ID
        assert account_index == 0
        self.started.set()
        if not self.release.wait(timeout=3.0):
            raise RuntimeError("blocking test release was not signalled")
        return SimpleNamespace(
            challenge_id="fixture-challenge",
            expires_at=NOW,
            masked_account="***2048",
            access_level="READ_ONLY",
            portfolio_total="150.00",
            portfolio_currency="RUB",
            sample=SimpleNamespace(
                label="Synthetic Share",
                quantity="3",
                unit_price="50",
                market_value="150",
                currency="RUB",
            ),
            freshness_state="FRESH",
            retrieved_at=NOW,
            evaluated_at=NOW,
            age_seconds="0",
            normalized_position_count=1,
        )


def _web_app(service: _BlockingLiveAcceptance) -> tuple[Any, str]:
    sessions = SessionRegistryV1()
    session_token, _ = sessions.create(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        now=NOW,
    )
    app = create_web_api(
        WebApiServicesV1(
            sessions=sessions,
            broker_repository=_EmptyRepository(),  # type: ignore[arg-type]
            provisioning=object(),  # type: ignore[arg-type]
            live_acceptance=service,  # type: ignore[arg-type]
            now=lambda: NOW,
        )
    )
    return app, session_token


def test_wp15_live_start_does_not_block_the_asgi_event_loop() -> None:
    service = _BlockingLiveAcceptance()
    app, session_token = _web_app(service)

    async def exercise() -> None:
        transport = httpx.ASGITransport(
            app=app,
            client=("127.0.0.1", 50000),
        )
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://127.0.0.1",
        ) as client:
            client.cookies.set(SESSION_COOKIE, session_token)
            safety_release = threading.Timer(1.0, service.release.set)
            safety_release.daemon = True
            safety_release.start()
            started_at = time.monotonic()
            request_task = asyncio.create_task(
                client.post(
                    "/api/v10/web/wp15-live-acceptance/start",
                    json={"connection_id": CONNECTION_ID, "account_index": 0},
                )
            )
            try:
                await asyncio.sleep(0.05)
                assert time.monotonic() - started_at < 0.5
                assert await asyncio.to_thread(service.started.wait, 0.5)

                health = await asyncio.wait_for(
                    client.get("/api/v10/web/health"),
                    timeout=0.5,
                )
                assert health.status_code == 200
                assert health.json()["state"] == "READY"

                service.release.set()
                response = await asyncio.wait_for(request_task, timeout=1.0)
                assert response.status_code == 200
                assert response.headers["cache-control"] == "no-store"
            finally:
                service.release.set()
                safety_release.cancel()
                if not request_task.done():
                    await asyncio.wait_for(request_task, timeout=1.0)

    asyncio.run(exercise())


def test_wp15_live_client_uses_a_finite_grpc_deadline(monkeypatch: Any) -> None:
    assert "interceptors" in inspect.signature(Client).parameters
    captured: dict[str, Any] = {}

    class _FakeClient:
        def __init__(self, token: str, **kwargs: Any) -> None:
            captured["token"] = token
            captured["kwargs"] = kwargs

        def __enter__(self) -> object:
            return object()

        def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
            del exc_type, exc, traceback

    monkeypatch.setattr(app_module, "Client", _FakeClient)
    factory = app_module._live_client_factory_builder("fixture-read-value")
    with factory():
        pass

    assert captured["token"] == "fixture-read-value"
    interceptors = captured["kwargs"]["interceptors"]
    assert len(interceptors) == 1
    interceptor = interceptors[0]
    assert isinstance(interceptor, app_module._UnaryUnaryDeadlineInterceptor)

    def invoke(existing_timeout: float | None) -> float:
        details = SimpleNamespace(
            method=b"/fixture.Service/Read",
            timeout=existing_timeout,
            metadata=(),
            credentials=None,
            wait_for_ready=None,
            compression=None,
        )
        captured_timeout: list[float] = []

        def continuation(call_details: Any, request: object) -> object:
            del request
            captured_timeout.append(float(call_details.timeout))
            return object()

        interceptor.intercept_unary_unary(continuation, details, object())
        return captured_timeout[0]

    assert invoke(None) == app_module._WP15_LIVE_RPC_TIMEOUT_SECONDS
    assert invoke(2.0) == 2.0


def test_wp15_live_ui_exposes_pending_state_before_snapshot_arrives() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "apps"
        / "web"
        / "src"
        / "app-shell"
        / "pages.tsx"
    ).read_text(encoding="utf-8")

    assert "Получаем live READ snapshot из T-Invest" in source
    assert '{liveWorking ? "Получаем snapshot…" : "Live READ acceptance"}' in source
    assert 'aria-busy={liveWorking}' in source
