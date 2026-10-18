"""Execute selected real definitions without booting the application monolith.

This probes JSON/SQL/admission helpers and a mocked pre-dispatch boundary. It
intentionally does NOT establish HTTP dependency injection, ledger integration,
provider compatibility, full worker execution or Android readiness.
"""
import ast
from contextlib import closing
import json
import math
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException
import pytest
from backend.ai_policy import AnalysisTier
from backend.ai_route_catalog import Candidate, CatalogError

ROOT = Path(__file__).resolve().parents[1]


def definitions(path, names, namespace):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    assert {node.name for node in selected} == set(names)
    for node in selected:
        node.decorator_list = []
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(ROOT / path), "exec"), namespace)
    return namespace


@pytest.fixture
def guard():
    names = ["GuardError", "_reject_nonfinite", "_finite_float", "_unique_json_object", "_model_json", "_result_content", "reject", "configured_route", "GuardedAIClient"]
    return definitions("ai_guarded_client.py", names, {
        "json": json, "math": math, "Route": SimpleNamespace, "CatalogError": CatalogError,
        "token_cost": lambda inputs, outputs, in_rate, out_rate: inputs * in_rate + outputs * out_rate,
    })


@pytest.mark.parametrize("text", ['{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{"x":1e999}', '{"x":-1e999}'])
def test_non_finite_json_is_not_a_financial_value(guard, text):
    with pytest.raises(guard["GuardError"], match="nonfinite"):
        guard["_model_json"](text)


@pytest.mark.parametrize("text", ['{"x":1,"x":2}', '{"usage":{"n":1,"n":2}}'])
def test_duplicate_json_keys_fail_closed(guard, text):
    with pytest.raises(guard["GuardError"], match="duplicate"):
        guard["_model_json"](text)


def test_finite_json_is_preserved(guard):
    assert guard["_model_json"]('{"amount":-0.125,"items":[1,true,null]}') == {"amount": -0.125, "items": [1, True, None]}


@pytest.mark.parametrize("content", ['{"x":NaN}', '{"x":1e999}', '{"x":1,"x":2}'])
def test_model_content_uses_the_same_strict_decoder(guard, content):
    with pytest.raises(guard["GuardError"]):
        guard["_result_content"]({"choices": [{"message": {"content": content}}]})


def test_selector_minimizes_total_cost_not_input_price_only(guard):
    routes = {"A": SimpleNamespace(input_rate=1, output_rate=100, input_allowance=0, identifier="a"),
              "B": SimpleNamespace(input_rate=5, output_rate=2, input_allowance=0, identifier="b")}
    guard["approved_candidates"] = lambda *args, **kwargs: (Candidate("A", 200000), Candidate("B", 200000))
    guard["_configured_label"] = lambda label, env, now: routes[label]
    choose = guard["configured_route"]
    assert choose(AnalysisTier.STANDARD, {}, at=100, input_bytes=2000, max_output_tokens=600).identifier == "b"
    assert choose(AnalysisTier.STANDARD, {}, at=100, input_bytes=100000, max_output_tokens=1).identifier == "a"


@pytest.mark.parametrize("input_bytes,output", [(True, 10), (-1, 10), (110001, 10), (10, True), (10, 4001)])
def test_selector_rejects_invalid_resource_bounds(guard, input_bytes, output):
    with pytest.raises(guard["GuardError"]):
        guard["configured_route"](AnalysisTier.STANDARD, {}, at=100, input_bytes=input_bytes, max_output_tokens=output)


@pytest.fixture
def chat(tmp_path, guard):
    path = tmp_path / "history.sqlite"
    def connect():
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        return db
    with closing(connect()) as db:
        db.executescript("""
        CREATE TABLE workspace_chat_threads(id TEXT,user_id INTEGER);
        CREATE TABLE workspace_chat_messages(user_id INTEGER,thread_id TEXT,job_id TEXT,role TEXT,text TEXT);
        INSERT INTO workspace_chat_threads VALUES ('one',1),('two',2);
        INSERT INTO workspace_chat_messages VALUES (1,'one','old','user','Объясни инфляцию');
        INSERT INTO workspace_chat_messages VALUES (1,'one','current','user','Почему?');
        INSERT INTO workspace_chat_messages VALUES (1,'one','later','user','Поздний вопрос');
        INSERT INTO workspace_chat_messages VALUES (2,'two','foreign','user','Чужой вопрос');
        """)
        db.commit()
    return definitions("volume_chat.py", ["_thread", "_message_boundary", "_policy_history", "model_messages", "_dispatch_guard"], {
        "closing": closing, "backend": SimpleNamespace(connect=connect), "GuardError": guard["GuardError"],
        "HTTPException": HTTPException, "Any": Any, "json": json, "SYSTEM": "fixture",
        "state": SimpleNamespace(encode=json.dumps),
        "fact_packet": lambda user, context: {"sources": [], "allowed_highlights": [], "facts": []},
    })


def test_queued_history_excludes_current_and_later_questions(chat):
    assert chat["_policy_history"](1, "one", "current") == ["Объясни инфляцию"]
    model, _ = chat["model_messages"]({"id": 1}, "Почему?", {}, "one", "current")
    history = json.loads(model[1]["content"])["recent_conversation"]
    assert history == [{"role": "user", "text": "Объясни инфляцию"}]


def test_history_cannot_borrow_another_users_thread(chat):
    with pytest.raises(HTTPException) as error:
        chat["_policy_history"](1, "two")
    assert error.value.status_code == 404


def test_boundary_cannot_borrow_another_job(chat, guard):
    with pytest.raises(guard["GuardError"], match="question_missing"):
        chat["_policy_history"](1, "one", "foreign")


def test_queued_route_cannot_change_or_exceed_reserved_quote(chat, guard):
    plan = SimpleNamespace(tier=AnalysisTier.STANDARD, policy_version="v1")
    selected = {"selected_tier": "standard", "policy_version": "v1", "route_id": "a", "cost_ceiling_micro_rub": 100}
    check = chat["_dispatch_guard"](selected, plan)
    check(SimpleNamespace(identifier="a"), 100)
    for route, ceiling in (("b", 100), ("a", 101)):
        with pytest.raises(guard["GuardError"], match="route_or_cost_changed"):
            check(SimpleNamespace(identifier=route), ceiling)


def test_cost_change_is_rejected_before_ledger_or_provider(guard):
    client = object.__new__(guard["GuardedAIClient"])
    client.connect = lambda: None
    client.check_ready = lambda *args, **kwargs: SimpleNamespace(input_allowance=0, input_rate=1, output_rate=1)
    guard["assert_monitoring_access"] = lambda connect: None
    def deny(route, ceiling):
        raise guard["GuardError"]("quote_changed_before_spend")
    client.route_guard = deny
    # Deliberately no ledger, queue, HTTP transport or credentials. Accessing any
    # of them would fail the test rather than masquerade as successful dispatch.
    with pytest.raises(guard["GuardError"], match="quote_changed_before_spend"):
        client._complete(AnalysisTier.STANDARD, [{"role": "user", "content": "fixture"}], 10)
