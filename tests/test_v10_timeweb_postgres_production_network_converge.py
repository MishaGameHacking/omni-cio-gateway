from __future__ import annotations

from typing import Any

import pytest

from scripts import provision_v10_timeweb_postgres_public_ipv4_tls as transport
from scripts import timeweb_postgres_production_network_converge as converge


CIDR = "8.8.8.8/32"
DATABASE_ID = "901"
GROUP_ID = "group-prod"
PAGE = "?limit=100&offset=0"
GROUPS_PATH = f"/api/v1/firewall/groups{PAGE}"
GROUP_PATH = f"/api/v1/firewall/groups/{GROUP_ID}"
RULES_PATH = f"{GROUP_PATH}/rules{PAGE}"
RESOURCES_PATH = f"{GROUP_PATH}/resources{PAGE}"
SERVICE_GROUPS_PATH = f"/api/v1/firewall/service/dbaas/{DATABASE_ID}{PAGE}"


def _page(key: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {key: rows, "meta": {"total": len(rows)}}


class FakeApi:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, path: str, *, timeout: float = 30.0) -> Any:
        del timeout
        self.calls.append(path)
        return self.responses[path]


class FakeMutation:
    def __init__(
        self,
        api: FakeApi,
        *,
        ambiguous_operation: str | None = None,
    ) -> None:
        self.api = api
        self.ambiguous_operation = ambiguous_operation
        self.calls: list[tuple[str, str, str, dict[str, object] | None]] = []

    def mutate_once(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        body: dict[str, object] | None = None,
        expected_statuses: frozenset[int],
        reconcile_statuses: frozenset[int] = frozenset(),
        timeout: float = 30.0,
    ) -> Any:
        del expected_statuses, reconcile_statuses, timeout
        self.calls.append((method, path, operation, body))
        if operation == "PRODUCTION_FIREWALL_GROUP_CREATE":
            self.api.responses[GROUPS_PATH] = _page(
                "groups",
                [{"id": GROUP_ID, "name": converge.FIREWALL_NAME}],
            )
            self.api.responses[GROUP_PATH] = {
                "group": {
                    "id": GROUP_ID,
                    "name": converge.FIREWALL_NAME,
                    "description": converge.FIREWALL_DESCRIPTION,
                    "policy": "DROP",
                }
            }
            self.api.responses[RULES_PATH] = _page("rules", [])
            self.api.responses[RESOURCES_PATH] = _page("resources", [])
        elif operation == "PRODUCTION_FIREWALL_RULE_CREATE":
            assert body is not None
            self.api.responses[RULES_PATH] = _page(
                "rules",
                [{"id": "rule-prod", **body}],
            )
        elif operation == "PRODUCTION_FIREWALL_RESOURCE_LINK":
            self.api.responses[RESOURCES_PATH] = _page(
                "resources",
                [{"id": DATABASE_ID, "type": "dbaas"}],
            )
            self.api.responses[SERVICE_GROUPS_PATH] = _page(
                "groups",
                [{"id": GROUP_ID}],
            )
        else:
            raise AssertionError(operation)
        if operation == self.ambiguous_operation:
            raise transport.AmbiguousMutation(
                "TIMEWEB_MUTATION_AMBIGUOUS",
                operation=operation,
            )
        return {}


def _base_responses() -> dict[str, Any]:
    return {
        GROUPS_PATH: _page("groups", []),
        SERVICE_GROUPS_PATH: _page("groups", []),
    }


def _existing_group_responses(
    *,
    rules: list[dict[str, Any]] | None = None,
    resources: list[dict[str, Any]] | None = None,
    attached: bool = False,
) -> dict[str, Any]:
    return {
        GROUPS_PATH: _page(
            "groups",
            [{"id": GROUP_ID, "name": converge.FIREWALL_NAME}],
        ),
        GROUP_PATH: {
            "group": {
                "id": GROUP_ID,
                "name": converge.FIREWALL_NAME,
                "description": converge.FIREWALL_DESCRIPTION,
                "policy": "DROP",
            }
        },
        RULES_PATH: _page("rules", rules or []),
        RESOURCES_PATH: _page("resources", resources or []),
        SERVICE_GROUPS_PATH: _page(
            "groups",
            [{"id": GROUP_ID}] if attached else [],
        ),
    }


def _exact_rule() -> dict[str, Any]:
    return {
        "id": "rule-prod",
        "description": converge.RULE_DESCRIPTION,
        "direction": "ingress",
        "port": "5432",
        "protocol": "tcp",
        "cidr": CIDR,
    }


def test_converges_missing_firewall_in_safe_order() -> None:
    api = FakeApi(_base_responses())
    mutation = FakeMutation(api)

    converge.converge_missing_firewall(
        mutation,
        api,
        database_id=DATABASE_ID,
        verifier_cidr=CIDR,
        sleeper=lambda _: None,
        delays=(),
    )

    assert [call[2] for call in mutation.calls] == [
        "PRODUCTION_FIREWALL_GROUP_CREATE",
        "PRODUCTION_FIREWALL_RULE_CREATE",
        "PRODUCTION_FIREWALL_RESOURCE_LINK",
    ]
    assert {call[0] for call in mutation.calls} == {"POST"}
    assert api.responses[SERVICE_GROUPS_PATH]["groups"] == [{"id": GROUP_ID}]


def test_existing_attached_firewall_is_read_only() -> None:
    api = FakeApi(
        _existing_group_responses(
            rules=[_exact_rule()],
            resources=[{"id": DATABASE_ID, "type": "dbaas"}],
            attached=True,
        )
    )
    mutation = FakeMutation(api)

    converge.converge_missing_firewall(
        mutation,
        api,
        database_id=DATABASE_ID,
        verifier_cidr=CIDR,
    )

    assert mutation.calls == []


def test_rejects_existing_named_group_with_wrong_rule() -> None:
    wrong = _exact_rule()
    wrong["cidr"] = "1.1.1.1/32"
    api = FakeApi(_existing_group_responses(rules=[wrong]))
    mutation = FakeMutation(api)

    with pytest.raises(
        converge.ProductionNetworkConvergeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_BOOTSTRAP_RULE_DRIFT",
    ):
        converge.converge_missing_firewall(
            mutation,
            api,
            database_id=DATABASE_ID,
            verifier_cidr=CIDR,
        )

    assert mutation.calls == []


def test_rejects_existing_named_group_with_other_resource() -> None:
    api = FakeApi(
        _existing_group_responses(
            rules=[_exact_rule()],
            resources=[{"id": "902", "type": "dbaas"}],
        )
    )
    mutation = FakeMutation(api)

    with pytest.raises(
        converge.ProductionNetworkConvergeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCE_SCOPE_WIDENED",
    ):
        converge.converge_missing_firewall(
            mutation,
            api,
            database_id=DATABASE_ID,
            verifier_cidr=CIDR,
        )

    assert mutation.calls == []


def test_ambiguous_resource_link_is_reconciled_without_replay() -> None:
    api = FakeApi(
        _existing_group_responses(
            rules=[_exact_rule()],
        )
    )
    mutation = FakeMutation(
        api,
        ambiguous_operation="PRODUCTION_FIREWALL_RESOURCE_LINK",
    )

    converge.converge_missing_firewall(
        mutation,
        api,
        database_id=DATABASE_ID,
        verifier_cidr=CIDR,
        sleeper=lambda _: None,
        delays=(),
    )

    operations = [call[2] for call in mutation.calls]
    assert operations == ["PRODUCTION_FIREWALL_RESOURCE_LINK"]


def test_confirmation_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(converge.CONFIRMATION_ENV, raising=False)

    with pytest.raises(
        converge.ProductionNetworkConvergeStopped,
        match="TIMEWEB_PG_PRODUCTION_NETWORK_CONVERGE_CONFIRMATION_REQUIRED",
    ):
        converge._required_confirmation()


def test_confirmation_accepts_exact_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(converge.CONFIRMATION_ENV, converge.CONFIRMATION)

    converge._required_confirmation()
