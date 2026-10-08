from __future__ import annotations

from argparse import Namespace
from uuid import UUID

import pytest

from omnicio.db import UserRecord
from omnicio.support import (
    SupportCommandError,
    public_support_contact,
    run_command,
    validate_reason,
)


class FakeDatabase:
    def __init__(self) -> None:
        self.user = UserRecord(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            public_id=1,
            status="active",
            role="user",
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
            role=self.user.role,
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


def test_public_contact_is_a_user_initiated_draft_without_automatic_delivery() -> None:
    result = public_support_contact("Test operator", "support@example.org")
    assert result["configured"] is True
    assert result["mailto"] == "mailto:support@example.org"
    assert result["automatically_sent"] is False
    assert result["safe_fields"] == ["request_id", "release", "route", "description"]


@pytest.mark.parametrize(("name", "email"), [
    ("", "support@example.org"), ("Operator", ""), ("Operator", "a@example.org?bcc=bad"),
    ("Operator", "a@example.org\r\nBcc:bad@example.org"), ("Operator\nInjected", "a@example.org"),
])
def test_missing_or_injected_public_contact_stays_unavailable(name: str, email: str) -> None:
    result = public_support_contact(name, email)
    assert result["configured"] is False
    assert result["email"] is None
    assert result["mailto"] is None
