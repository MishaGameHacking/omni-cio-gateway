from __future__ import annotations

import hashlib
from typing import Any

import pytest

from omni_cio.adapters.tinvest_connection_v1 import (
    TInvestConnectionReadAdapter,
    discover_read_account_bindings,
)
from omni_cio.adapters.tinvest_read_v1 import AccountBindingError


ACCOUNT_A = "account-owner-a-0001"
ACCOUNT_B = "account-owner-b-0002"
ACCOUNT_C = "account-owner-c-0003"


def fingerprint(account_id: str) -> str:
    return hashlib.sha256(account_id.encode("utf-8")).hexdigest()


def account(
    account_id: str,
    *,
    status: str = "ACCOUNT_STATUS_OPEN",
    access_level: str = "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
) -> dict[str, Any]:
    return {
        "id": account_id,
        "type": "ACCOUNT_TYPE_TINKOFF",
        "status": status,
        "access_level": access_level,
    }


class FakeUsers:
    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self._accounts = accounts

    def get_accounts(self) -> dict[str, Any]:
        return {"accounts": list(self._accounts)}


class FakeClient:
    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self.users = FakeUsers(accounts)

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb


def connection_adapter(
    client: FakeClient,
    *,
    expected_account_id: str,
) -> TInvestConnectionReadAdapter:
    return TInvestConnectionReadAdapter(
        client_factory=lambda: client,
        expected_account_fingerprint_sha256=fingerprint(expected_account_id),
        monotonic=lambda: 0.0,
        sleeper=lambda _: None,
        random_unit=lambda: 0.0,
    )


def test_broad_read_token_discovers_multiple_masked_account_bindings() -> None:
    client = FakeClient([account(ACCOUNT_A), account(ACCOUNT_B), account(ACCOUNT_C)])

    bindings = discover_read_account_bindings(lambda: client)

    assert len(bindings) == 3
    serialized = "\n".join(binding.model_dump_json() for binding in bindings)
    assert ACCOUNT_A not in serialized
    assert ACCOUNT_B not in serialized
    assert ACCOUNT_C not in serialized
    assert all(binding.access_level == "ACCOUNT_ACCESS_LEVEL_READ_ONLY" for binding in bindings)
    assert {binding.account_fingerprint_sha256 for binding in bindings} == {
        fingerprint(ACCOUNT_A),
        fingerprint(ACCOUNT_B),
        fingerprint(ACCOUNT_C),
    }


def test_broad_read_token_selects_exact_expected_account() -> None:
    client = FakeClient([account(ACCOUNT_A), account(ACCOUNT_B), account(ACCOUNT_C)])
    adapter = connection_adapter(client, expected_account_id=ACCOUNT_B)

    raw_account_id, binding = adapter._bind_account(client)

    assert raw_account_id == ACCOUNT_B
    assert binding.account_fingerprint_sha256 == fingerprint(ACCOUNT_B)
    assert binding.masked_label.endswith("0002")


def test_expected_account_absent_from_broad_read_token_fails_closed() -> None:
    client = FakeClient([account(ACCOUNT_A), account(ACCOUNT_B)])
    adapter = connection_adapter(client, expected_account_id=ACCOUNT_C)

    with pytest.raises(AccountBindingError, match="EXPECTED_ACCOUNT_NOT_ACCESSIBLE") as exc:
        adapter._bind_account(client)

    assert ACCOUNT_A not in str(exc.value)
    assert ACCOUNT_B not in str(exc.value)
    assert ACCOUNT_C not in str(exc.value)


def test_duplicate_provider_account_binding_fails_closed() -> None:
    client = FakeClient([account(ACCOUNT_A), account(ACCOUNT_A)])
    adapter = connection_adapter(client, expected_account_id=ACCOUNT_A)

    with pytest.raises(AccountBindingError, match="DUPLICATE_ACCESSIBLE_ACCOUNT_BINDING"):
        adapter._bind_account(client)


def test_no_access_account_is_ignored_but_read_only_account_remains_selectable() -> None:
    client = FakeClient(
        [
            account(ACCOUNT_A, access_level="ACCOUNT_ACCESS_LEVEL_NO_ACCESS"),
            account(ACCOUNT_B),
        ]
    )
    adapter = connection_adapter(client, expected_account_id=ACCOUNT_B)

    raw_account_id, _ = adapter._bind_account(client)

    assert raw_account_id == ACCOUNT_B


@pytest.mark.parametrize(
    "access_level",
    [
        "ACCOUNT_ACCESS_LEVEL_FULL_ACCESS",
        "ACCOUNT_ACCESS_LEVEL_UNSPECIFIED",
    ],
)
def test_broader_or_unknown_access_on_any_open_account_rejects_read_credential(
    access_level: str,
) -> None:
    client = FakeClient(
        [
            account(ACCOUNT_A),
            account(ACCOUNT_B, access_level=access_level),
        ]
    )

    with pytest.raises(AccountBindingError, match="BROKER_READ_CREDENTIAL_NOT_READ_ONLY"):
        discover_read_account_bindings(lambda: client)


def test_closed_full_access_account_does_not_expand_live_read_authority() -> None:
    client = FakeClient(
        [
            account(ACCOUNT_A),
            account(
                ACCOUNT_B,
                status="ACCOUNT_STATUS_CLOSED",
                access_level="ACCOUNT_ACCESS_LEVEL_FULL_ACCESS",
            ),
        ]
    )

    bindings = discover_read_account_bindings(lambda: client)

    assert len(bindings) == 1
    assert bindings[0].account_fingerprint_sha256 == fingerprint(ACCOUNT_A)


def test_connection_adapter_source_contains_no_write_surface() -> None:
    forbidden_attributes = ("orders", "stop_orders", "post_order")

    assert not any(hasattr(TInvestConnectionReadAdapter, name) for name in forbidden_attributes)
