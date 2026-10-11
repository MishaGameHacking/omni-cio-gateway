"""Account selection is a compare-and-swap inside the existing owner boundary."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from uuid import UUID

import pytest
from test_workspace_postgres import DATABASE_URL, user
from test_workspace_postgres import workspace_database as workspace_database

from omnicio.db import BrokerConnectionConflict, Database, TBankConnectionRecord

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")


def select(database: Database, owner: UUID, expected: TBankConnectionRecord, account: str):
    return database.upsert_tbank_connection(
        user_id=owner, environment="prod", account_id=account, account_name="Test account",
        encrypted_credential=expected.encrypted_credential, terms_version="test-current",
        expected_connection=expected,
    )


def test_account_selection_serializes_concurrent_choices_and_rejects_foreign_context(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, _, _ = workspace_database
    owner, other = user(database, account=True), user(database, account=True)
    original = database.tbank_connection(owner)
    foreign = database.tbank_connection(other)
    assert original is not None and foreign is not None
    with pytest.raises(BrokerConnectionConflict):
        select(database, owner, foreign, "foreign-choice")
    with pytest.raises(BrokerConnectionConflict):
        select(database, owner, replace(original, encrypted_credential=b"stale-token"), "stale")

    start = Barrier(2)

    def choose(account: str) -> str:
        start.wait(timeout=5)
        try:
            return select(database, owner, original, account).account_id
        except BrokerConnectionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(choose, ("first-choice", "second-choice")))
    assert results.count("conflict") == 1
    current = database.tbank_connection(owner)
    assert current is not None
    assert current.account_id in results
    assert current.encrypted_credential == original.encrypted_credential
    assert database.tbank_connection(other) == foreign
    with pytest.raises(BrokerConnectionConflict):
        select(database, owner, original, "stale-tab-choice")

    # Switching back uses the current context; it does not require deleting the connection.
    assert select(database, owner, current, original.account_id).account_id == original.account_id
