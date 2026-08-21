from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts.check_v10_exact_main_regression import (
    REQUIRED_JOBS,
    RegressionStopped,
    verify_exact_main_regression,
)


EXPECTED_SHA = "a" * 40
TOKEN = "github-token-must-never-leak"
RUN_ID = 32471423708


class FakeResponse:
    def __init__(self, payload: object, status: int = 200) -> None:
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        return self._raw if amount < 0 else self._raw[:amount]


def _run(
    *,
    status: str = "completed",
    conclusion: str | None = "success",
) -> dict[str, object]:
    return {
        "id": RUN_ID,
        "head_sha": EXPECTED_SHA,
        "head_branch": "main",
        "event": "push",
        "path": ".github/workflows/regression-shield.yml",
        "status": status,
        "conclusion": conclusion,
    }


def _jobs(*, failed_name: str | None = None) -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "status": "completed",
            "conclusion": "failure" if name == failed_name else "success",
        }
        for name in REQUIRED_JOBS
    ]


def _env() -> dict[str, str]:
    return {
        "GITHUB_REPOSITORY": "MishaGameHacking/omni-cio-gateway",
        "GITHUB_TOKEN": TOKEN,
        "EXPECTED_MAIN_SHA": EXPECTED_SHA,
    }


def _opener(
    runs: list[dict[str, object]],
    jobs: list[dict[str, object]],
    calls: list[str] | None = None,
):
    def open_request(request: object, timeout: float = 0.0) -> FakeResponse:
        del timeout
        url = str(getattr(request, "full_url"))
        if calls is not None:
            calls.append(url)
        authorization = getattr(request, "headers").get("Authorization")
        assert authorization == f"Bearer {TOKEN}"
        if "/actions/workflows/regression-shield.yml/runs?" in url:
            query = parse_qs(urlsplit(url).query)
            assert query == {
                "branch": ["main"],
                "event": ["push"],
                "head_sha": [EXPECTED_SHA],
                "per_page": ["10"],
            }
            return FakeResponse({"workflow_runs": runs})
        assert f"/actions/runs/{RUN_ID}/jobs?" in url
        query = parse_qs(urlsplit(url).query)
        assert query == {"filter": ["latest"], "per_page": ["100"]}
        return FakeResponse({"jobs": jobs})

    return open_request


def test_exact_successful_push_run_and_required_jobs_are_accepted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    run_id = verify_exact_main_regression(
        env=_env(),
        opener=_opener([_run()], _jobs(), calls),
    )

    assert run_id == RUN_ID
    assert len(calls) == 2
    captured = capsys.readouterr()
    assert "EXACT_MAIN_REGRESSION=PASS" in captured.out
    assert all(name in captured.out for name in REQUIRED_JOBS)
    assert TOKEN not in captured.out
    assert TOKEN not in captured.err


@pytest.mark.parametrize("runs", [[], [_run(), _run()]])
def test_missing_or_duplicate_regression_run_is_rejected(
    runs: list[dict[str, object]],
) -> None:
    with pytest.raises(
        RegressionStopped,
        match="REGRESSION_SHIELD_RUN_NOT_UNIQUE",
    ):
        verify_exact_main_regression(
            env=_env(),
            opener=_opener(runs, _jobs()),
        )


@pytest.mark.parametrize(
    ("run", "code"),
    [
        (_run(status="queued", conclusion=None), "REGRESSION_SHIELD_NOT_COMPLETED"),
        (_run(conclusion="failure"), "REGRESSION_SHIELD_NOT_GREEN"),
    ],
)
def test_incomplete_or_failed_regression_run_is_rejected(
    run: dict[str, object],
    code: str,
) -> None:
    with pytest.raises(RegressionStopped, match=code):
        verify_exact_main_regression(
            env=_env(),
            opener=_opener([run], _jobs()),
        )


def test_drifted_regression_run_is_rejected() -> None:
    run = _run()
    run["event"] = "workflow_dispatch"

    with pytest.raises(RegressionStopped, match="REGRESSION_SHIELD_RUN_DRIFT"):
        verify_exact_main_regression(
            env=_env(),
            opener=_opener([run], _jobs()),
        )


def test_missing_or_failed_required_job_is_rejected() -> None:
    with pytest.raises(
        RegressionStopped,
        match="REGRESSION_SHIELD_REQUIRED_JOB_NOT_UNIQUE",
    ):
        verify_exact_main_regression(
            env=_env(),
            opener=_opener([_run()], _jobs()[:-1]),
        )

    with pytest.raises(
        RegressionStopped,
        match="REGRESSION_SHIELD_REQUIRED_JOB_NOT_GREEN",
    ):
        verify_exact_main_regression(
            env=_env(),
            opener=_opener([_run()], _jobs(failed_name=REQUIRED_JOBS[0])),
        )


def test_github_api_redirect_is_rejected_without_leaking_token(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def redirecting_opener(*args: object, **kwargs: object) -> FakeResponse:
        del args, kwargs
        raise HTTPError(
            "https://api.github.com/redirect",
            302,
            "redirect forbidden",
            hdrs=None,
            fp=None,
        )

    with pytest.raises(
        RegressionStopped,
        match="GITHUB_ACTIONS_REDIRECT_FORBIDDEN",
    ):
        verify_exact_main_regression(
            env=_env(),
            opener=redirecting_opener,
        )

    captured = capsys.readouterr()
    assert TOKEN not in captured.out
    assert TOKEN not in captured.err
