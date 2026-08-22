from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts import diagnose_v10_render_deploy as diagnostic


EXPECTED_SHA = "a" * 40
NOT_BEFORE = "2026-08-22T14:27:00Z"
SERVICE_ID = "srv-da4r3d49v7es73919ntg"
DEPLOY_ID = "dep-da4r3e49v7es73919r70"


class DeployWindowApi:
    def request(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        expected: frozenset[int] = frozenset({200}),
        timeout: float = 30.0,
    ) -> Any:
        assert method == "GET"
        assert body is None
        assert expected == frozenset({200})
        assert timeout == 30.0
        parsed = urlsplit(path)
        assert parsed.path == f"/services/{SERVICE_ID}/deploys"
        query = parse_qs(parsed.query)
        assert query["createdAfter"] == ["2026-08-22T14:26:59Z"]
        assert query["limit"] == ["100"]
        return [
            {
                "deploy": {
                    "id": DEPLOY_ID,
                    "status": "build_failed",
                    "createdAt": "2026-08-22T14:27:04Z",
                    "commit": {"id": EXPECTED_SHA},
                }
            }
        ]


def test_deploy_search_is_server_bounded_to_current_attempt_window() -> None:
    result = diagnostic._matching_deploy(  # noqa: SLF001 - provider contract
        DeployWindowApi(),
        SERVICE_ID,
        EXPECTED_SHA,
        diagnostic._utc_timestamp(  # noqa: SLF001 - provider contract
            NOT_BEFORE,
            "TEST_INVALID_TIMESTAMP",
        ),
    )

    assert result["id"] == DEPLOY_ID


def test_saturated_provider_page_fails_closed_before_uniqueness_claim() -> None:
    payload = [
        {
            "event": {
                "id": f"evt-{index:020d}",
                "type": "deploy_ended",
            }
        }
        for index in range(diagnostic._PAGE_LIMIT)  # noqa: SLF001 - bound contract
    ]

    with pytest.raises(diagnostic.DiagnosticStopped) as exc_info:
        diagnostic._bounded_rows(  # noqa: SLF001 - pagination guard contract
            payload,
            "event",
            "RENDER_DIAGNOSTIC_EVENT_WINDOW_TRUNCATED",
        )

    assert exc_info.value.code == "RENDER_DIAGNOSTIC_EVENT_WINDOW_TRUNCATED"


def test_queued_capacity_diagnostic_is_not_labeled_terminal(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        diagnostic,
        "diagnose",
        lambda expected_sha, not_before: diagnostic.DeployDiagnostic(
            service_id=SERVICE_ID,
            deploy_id=DEPLOY_ID,
            status="queued",
            reason="PIPELINE_MINUTES_EXHAUSTED",
        ),
    )

    assert (
        diagnostic.main(
            [
                "--expected-sha",
                EXPECTED_SHA,
                "--not-before",
                NOT_BEFORE,
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "RENDER_DEPLOY_STATUS=queued" in output
    assert "RENDER_DEPLOY_REASON=PIPELINE_MINUTES_EXHAUSTED" in output
    assert "RENDER_DEPLOY_TERMINAL=NO" in output
