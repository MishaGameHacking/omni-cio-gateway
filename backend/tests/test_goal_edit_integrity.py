"""Goal edits cannot resurrect deleted records or cross the user boundary."""
import pytest

from backend.tests.test_volume_workspace import fixture
from backend import volume_state as state
from backend.volume_contract import money

GOALS = "/workspace/goals"


def goal_request(request_id="goal-create-integrity"):
    return {"request_id": request_id, "title": "Saved goal",
            "target": money("500", "RUB"), "reserve": money("50", "RUB")}


def test_deleted_goal_cannot_be_recreated_by_stale_editor(fixture):
    client = fixture["client"]
    body = goal_request()
    created = client.post(GOALS, json=body)
    assert created.status_code == 200
    identifier = created.json()["id"]
    assert client.delete(f"{GOALS}/{identifier}").status_code == 200
    # A duplicate acknowledged request returns its receipt without inserting again.
    assert client.post(GOALS, json=body).json() == created.json()
    edit = {**body, "id": identifier, "request_id": "goal-stale-edit", "title": "Late edit"}
    failed = client.post(GOALS, json=edit)
    assert failed.status_code == 404
    assert failed.json()["detail"] == "goal_not_found"
    assert client.get(GOALS).json()["items"] == []


def test_other_users_goal_id_is_not_an_editable_owned_record(fixture):
    payload = state.GoalWrite(**goal_request("goal-other-owner"))
    other = state.save_goal(payload, user=fixture["other"])
    edit = {**goal_request("goal-cross-owner-edit"), "id": other["id"]}
    failed = fixture["client"].post(GOALS, json=edit)
    assert failed.status_code == 404
    assert fixture["client"].get(GOALS).json()["items"] == []
    assert state.goal_data(fixture["other"])["items"][0]["title"] == "Saved goal"


def test_existing_goal_edit_is_applied_once_and_keeps_its_identity(fixture):
    client = fixture["client"]
    original = client.post(GOALS, json=goal_request()).json()
    edit = {**goal_request("goal-edit-integrity"), "id": original["id"], "title": " Updated goal ",
            "target": money("800", "RUB")}
    first = client.post(GOALS, json=edit)
    assert first.status_code == 200
    assert client.post(GOALS, json=edit).json() == first.json()
    goals = client.get(GOALS).json()["items"]
    assert len(goals) == 1
    assert goals[0]["id"] == original["id"]
    assert goals[0]["title"] == "Updated goal"
    assert goals[0]["target"] == money("800", "RUB")


@pytest.mark.parametrize("title", [" ", "\t\n", "\u00a0"])
def test_blank_goal_title_never_creates_a_record(fixture, title):
    body = {**goal_request(), "title": title}
    failed = fixture["client"].post(GOALS, json=body)
    assert failed.status_code == 422
    assert fixture["client"].get(GOALS).json()["items"] == []
