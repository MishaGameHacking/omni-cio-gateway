from __future__ import annotations

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.alerting import CbrKeyRateAlertPolicyV1


def test_alert_retention_cannot_be_shorter_than_cooldown() -> None:
    with pytest.raises(ValidationError, match="retention"):
        CbrKeyRateAlertPolicyV1(
            cooldown_seconds=3_600,
            state_retention_seconds=60,
        )


def test_alert_retention_may_equal_cooldown() -> None:
    policy = CbrKeyRateAlertPolicyV1(
        cooldown_seconds=3_600,
        state_retention_seconds=3_600,
    )

    assert policy.cooldown_seconds == policy.state_retention_seconds
