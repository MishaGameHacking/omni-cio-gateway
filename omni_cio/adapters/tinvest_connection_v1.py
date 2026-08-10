from __future__ import annotations

from collections.abc import Callable
import hmac
from typing import Any

from omni_cio.adapters.tinvest_market_v1 import TInvestMarketReadAdapter
from omni_cio.adapters.tinvest_read_v1 import (
    ACCESS_LEVEL_NAMES,
    ACCOUNT_STATUS_NAMES,
    AccountBindingError,
    BrokerAccountBindingV1,
    TInvestReadAdapter,
    _accounts,
    _binding_for_account,
    _enum_name,
    _field,
)


_READ_ONLY = "ACCOUNT_ACCESS_LEVEL_READ_ONLY"
_NO_ACCESS = "ACCOUNT_ACCESS_LEVEL_NO_ACCESS"
_OPEN = "ACCOUNT_STATUS_OPEN"


def _readable_open_accounts(
    response: Any,
) -> tuple[tuple[str, BrokerAccountBindingV1], ...]:
    """Return verified READ-only open accounts without exposing them outside this module."""
    bindings: list[tuple[str, BrokerAccountBindingV1]] = []
    seen_raw_ids: set[str] = set()

    for account in _accounts(response):
        status = _enum_name(_field(account, "status"), ACCOUNT_STATUS_NAMES)
        access_level = _enum_name(
            _field(account, "access_level"),
            ACCESS_LEVEL_NAMES,
        )
        if status != _OPEN or access_level == _NO_ACCESS:
            continue
        if access_level != _READ_ONLY:
            raise AccountBindingError("BROKER_READ_CREDENTIAL_NOT_READ_ONLY")

        raw_account_id, binding = _binding_for_account(account)
        if raw_account_id in seen_raw_ids:
            raise AccountBindingError("DUPLICATE_ACCESSIBLE_ACCOUNT_BINDING")
        seen_raw_ids.add(raw_account_id)
        bindings.append((raw_account_id, binding))

    if not bindings:
        raise AccountBindingError("NO_ACCESSIBLE_OPEN_ACCOUNT")

    bindings.sort(key=lambda pair: pair[1].broker_account_id)
    return tuple(bindings)


def discover_read_account_bindings(
    client_factory: Callable[[], Any],
) -> tuple[BrokerAccountBindingV1, ...]:
    """Discover all READ-only broker accounts as masked, non-secret bindings.

    The raw broker account identifiers are intentionally retained only inside the adapter
    boundary. The Web/API layer receives canonical broker-account IDs, fingerprints and
    masked labels, never the provider account ID itself.
    """
    with client_factory() as client:
        response = client.users.get_accounts()
        return tuple(binding for _, binding in _readable_open_accounts(response))


class TInvestConnectionReadAdapter(TInvestReadAdapter):
    """Connection-scoped WP15 adapter for one verified broker account.

    A READ credential may expose one or many T-Invest accounts. This adapter binds the
    operation to exactly one preselected account fingerprint owned by the authenticated
    tenant/BrokerConnection. Broader token authority, absent identity and duplicate
    bindings fail closed before any portfolio/operations read is made.
    """

    def _bind_account(
        self,
        client: Any,
    ) -> tuple[str, BrokerAccountBindingV1]:
        response = self._call_read("GET_ACCOUNTS", client.users.get_accounts)
        matches: list[tuple[str, BrokerAccountBindingV1]] = []
        for raw_account_id, binding in _readable_open_accounts(response):
            if hmac.compare_digest(
                binding.account_fingerprint_sha256,
                self._expected_account_fingerprint,
            ):
                matches.append((raw_account_id, binding))

        if not matches:
            raise AccountBindingError("EXPECTED_ACCOUNT_NOT_ACCESSIBLE")
        if len(matches) != 1:
            raise AccountBindingError("DUPLICATE_EXPECTED_ACCOUNT_BINDING")
        return matches[0]


class TInvestConnectionMarketReadAdapter(
    TInvestMarketReadAdapter,
    TInvestConnectionReadAdapter,
):
    """Market companion using the same exact connection-scoped account binding."""
