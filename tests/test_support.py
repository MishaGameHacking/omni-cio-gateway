from __future__ import annotations

from argparse import Namespace
from uuid import UUID

import pytest

from omnicio.db import UserRecord
from omnicio.support import SupportCommandError, run_command, validate_reason


class FakeDatabase:
    def __init__(self) -> None:
        self.user = UserRecord(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            public_id=1,
            status="active",
        )
        self.last_reason = ""

    def support_user_by_public_id(self, public_id: int):
        return self.user if public_id == 1 else None

    def support_revoke_all_sessions(self, *, public_id: int, reason: str):
        self.last_reason = reason
        return self.user if public_id == 1 else None

    def support_change_status(self, **kwargs):
        self.last_reason = kwargs["reason"]
        if kwargs["public_id"] != 1:
            return None
        self.user = UserRecord(
            id=self.user.id,
            public_id=self.user.public_id,
            status=kwargs["target_status"],
        )
        return self.user, True


def test_get_uses_public_id_without_exposing_internal_uuid() -> None:
    result = run_command(
        FakeDatabase(),
        Namespace(command="get", public_id="000000001"),
    )

    assert '"public_id": "000000001"' in result
    assert '"status": "active"' in result
    assert "00000000-0000-0000-0000-000000000001" not in result


def test_block_records_reason_and_changes_status() -> None:
    database = FakeDatabase()
    result = run_command(
        database,
        Namespace(
            command="block",
            public_id="000000001",
            reason="CASE-42",
        ),
    )

    assert database.last_reason == "CASE-42"
    assert '"status": "blocked"' in result
    assert '"changed": true' in result


def test_reason_is_bounded() -> None:
    assert validate_reason("CASE-1") == "CASE-1"

    with pytest.raises(SupportCommandError):
        validate_reason("")
    with pytest.raises(SupportCommandError):
        validate_reason("x" * 201)
