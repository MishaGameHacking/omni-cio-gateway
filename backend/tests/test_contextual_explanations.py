"""Selected evidence reaches chat without crossing ownership or making a call."""
from contextlib import closing
import json
import time

import pytest
from fastapi import HTTPException
from backend import volume_chat as chat, volume_state as state, volume_explanations as explanation
from backend import osint_store, osint_read
from backend.tests.test_volume_workspace import fixture
from backend.tests.test_investment_osint import item, save


def target(kind, identifier):
    return {"mode": "portfolio", "explanation": {"kind": kind, "id": identifier}}


def test_risk_target_uses_current_owner_exposure_and_never_client_text(fixture):
    risk = state.exposure_data(fixture["snapshot"], None)
    concentration = risk["concentrations"][0]
    context = target("risk", concentration["direction"] + ":" + concentration["id"])
    packet = chat.fact_packet(fixture["user"], context)
    fact = next(f for f in packet["facts"] if f["id"].startswith("explanation:risk:"))
    assert fact["value"]["share_percent"] == concentration["share_percent"]
    assert packet["explanation_context"]["fact_ids"] == [fact["id"]]
    assert "account_id" not in fact["value"]
    invalid = target("risk", "issuer:made-up")
    with pytest.raises(HTTPException):
        chat.fact_packet(fixture["user"], invalid)


def test_notification_must_belong_to_current_owner(fixture):
    with closing(chat.backend.connect()) as db:
        db.execute("""INSERT INTO workspace_notification_outbox
            (id,user_id,kind,title,body,source_card_id,event_id,created_at,state,eligible_at)
            VALUES('foreign',?,'critical','synthetic','synthetic',NULL,'foreign-event',1,'pending',1)""",
            (fixture["other"]["id"],))
        db.commit()
    context = target("notification", "foreign")
    with pytest.raises(HTTPException) as error:
        chat.fact_packet(fixture["user"], context)
    assert error.value.status_code == 404


def test_document_is_loaded_from_durable_corpus_with_bounded_excerpt_and_source(fixture):
    now = int(time.time())
    osint_store.initialize(chat.backend.connect)
    text = "МСФО. Выручка 100 млн рублей. " * 400
    save(chat.backend.connect, item(text=text, published=now), now)
    identifier = osint_read.documents(chat.backend.connect)["items"][0]["id"]
    packet = chat.fact_packet(fixture["user"], target("document", str(identifier)))
    ctx = packet["explanation_context"]
    assert ctx["coverage"]["truncated"] is True
    assert ctx["coverage"]["total"] == len(text)
    fact = next(f for f in packet["facts"] if f["id"] in ctx["fact_ids"])
    assert len(fact["value"]["excerpt"]) == 6000
    assert fact["value"]["issuer_identity_verified"] is False
    assert fact["value"]["basis"] == "publisher_statement_not_independently_verified_financial_fact"
    assert any(s["url"] == "https://www.moex.com/n1" for s in packet["sources"])
    messages, _ = chat.model_messages(fixture["user"], "Объясни финансовую отчётность", target("document", str(identifier)))
    assert "id" not in json.loads(messages[1]["content"])["context"]["explanation_context"]


@pytest.mark.parametrize("identifier", ["-1", "0x20", "../1", "9" * 80])
def test_invalid_document_id_is_rejected_before_source_lookup(fixture, identifier):
    context = target("document", identifier)
    with pytest.raises(HTTPException) as error:
        chat.fact_packet(fixture["user"], context)
    assert error.value.status_code == 422


def test_mixed_scope_and_unavailable_document_fail_explicitly(fixture):
    mixed = {**target("document", "1"), "account_id": "owned-account-a"}
    with pytest.raises(HTTPException) as error:
        chat.fact_packet(fixture["user"], mixed)
    assert error.value.status_code == 422
    osint_store.initialize(chat.backend.connect)
    missing = target("document", "123")
    with pytest.raises(HTTPException) as error:
        chat.fact_packet(fixture["user"], missing)
    assert error.value.status_code == 404


def test_corpus_type_filter_keeps_pagination_and_does_not_fetch_network(fixture):
    now = int(time.time())
    osint_store.initialize(chat.backend.connect)
    save(chat.backend.connect, item(published=now), now)
    save(chat.backend.connect, {**item(url="https://www.moex.com/report.pdf", published=now), "kind": "report"}, now)
    rows = osint_read.documents(chat.backend.connect, kind="report")["items"]
    assert len(rows) == 1
    assert rows[0]["kind"] == "report"
    response = fixture["client"].get("/workspace/osint/documents?kind=report")
    assert response.status_code == 200
    assert [x["kind"] for x in response.json()["items"]] == ["report"]
    assert fixture["client"].get("/workspace/osint/documents?kind=anything").status_code == 422
