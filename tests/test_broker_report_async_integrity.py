from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

import omni_cio.reconciliation as broker


class FakeBase:
    @staticmethod
    def json_safe_value(value: Any) -> Any:
        return value

    @staticmethod
    def safe_error_message(exc: Exception) -> str:
        return str(exc)


class FakeRequest:
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeGrpcCode:
    name = "INVALID_ARGUMENT"


class FakeRequestError(Exception):
    def __init__(self, message: str, code: str = "30058") -> None:
        super().__init__(message)
        self.code = FakeGrpcCode()
        self.metadata = SimpleNamespace(
            code=code,
            message=message,
            tracking_id="tracking-30058",
        )


class GenerateOnlyOperations:
    def __init__(self) -> None:
        self.generate_calls = 0
        self.get_calls = 0

    def get_broker_report(self, **kwargs: Any) -> dict[str, Any]:
        if "generate_broker_report_request" in kwargs:
            self.generate_calls += 1
            return {
                "generate_broker_report_response": {
                    "task_id": "task-generated-1",
                }
            }
        self.get_calls += 1
        raise AssertionError("A zero-wait generation call must not poll immediately")


class PendingOperations:
    def __init__(self) -> None:
        self.get_calls = 0

    def get_broker_report(self, **kwargs: Any) -> dict[str, Any]:
        assert "get_broker_report_request" in kwargs
        self.get_calls += 1
        raise FakeRequestError("Task not completed yet, please try again later")


class FatalOperations:
    def get_broker_report(self, **kwargs: Any) -> dict[str, Any]:
        assert "get_broker_report_request" in kwargs
        raise FakeRequestError("The account is unavailable", code="30081")


def configure_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(broker, "GenerateBrokerReportRequest", FakeRequest)
    monkeypatch.setattr(broker, "GetBrokerReportRequest", FakeRequest)
    monkeypatch.setattr(broker, "BrokerReportRequest", FakeRequest)


def interval() -> tuple[datetime, datetime]:
    return (
        datetime(2026, 7, 1, tzinfo=timezone.utc),
        datetime(2026, 7, 27, tzinfo=timezone.utc),
    )


def test_zero_wait_generation_returns_task_without_premature_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_requests(monkeypatch)
    operations = GenerateOnlyOperations()
    start_time, end_time = interval()

    generation, rows, pagination, errors = broker.load_broker_report(
        base=FakeBase,
        client=SimpleNamespace(operations=operations),
        account_id="account-1",
        start_time=start_time,
        end_time=end_time,
        task_id=None,
        wait_seconds=0,
    )

    assert generation["status"] == "pending"
    assert generation["task_id"] == "task-generated-1"
    assert generation["error"]["code"] == "BROKER_REPORT_NOT_READY"
    assert operations.generate_calls == 1
    assert operations.get_calls == 0
    assert rows == []
    assert pagination["pages_fetched"] == 0
    assert pagination["rows_received"] == 0
    assert errors == []


def test_request_error_30058_is_pending_and_preserves_existing_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_requests(monkeypatch)
    operations = PendingOperations()
    start_time, end_time = interval()

    generation, rows, pagination, errors = broker.load_broker_report(
        base=FakeBase,
        client=SimpleNamespace(operations=operations),
        account_id="account-1",
        start_time=start_time,
        end_time=end_time,
        task_id="task-existing-9",
        wait_seconds=0,
    )

    assert generation["status"] == "pending"
    assert generation["task_id"] == "task-existing-9"
    assert generation["error"]["code"] == "BROKER_REPORT_NOT_READY"
    assert generation["error"]["grpc_code"] == "INVALID_ARGUMENT"
    assert generation["error"]["exception_type"] == "FakeRequestError"
    assert "Task not completed yet" in generation["error"]["message"]
    assert operations.get_calls == 1
    assert rows == []
    assert pagination["pages_fetched"] == 0
    assert errors == []


def test_non_pending_request_error_is_not_silently_reclassified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_requests(monkeypatch)
    start_time, end_time = interval()

    client = SimpleNamespace(operations=FatalOperations())
    with pytest.raises(FakeRequestError, match="account is unavailable"):
        broker.load_broker_report(
            base=FakeBase,
            client=client,
            account_id="account-1",
            start_time=start_time,
            end_time=end_time,
            task_id="task-existing-10",
            wait_seconds=0,
        )
