"""Deterministic public-corpus, hostile-input and queue regressions; no external services."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
import io
import json
import sqlite3
import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import app as backend, autonomous_ai, autonomous_controller, volume_jobs, volume_live
from backend import osint_analysis as analysis, osint_catalogue as catalogue, osint_content as content
from backend import osint_network as network, osint_store as store, osint_worker as worker, osint_read as read
from backend.osint_retention import cleanup

NOW = int(datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp())


@pytest.fixture
def corpus(tmp_path):
    path = tmp_path / "public.sqlite3"

    def connect():
        db = sqlite3.connect(path, timeout=10)
        db.row_factory = sqlite3.Row
        return db
    store.initialize(connect)
    return connect


@pytest.fixture
def application(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "DATABASE_PATH", tmp_path / "application.sqlite3")
    monkeypatch.setattr(autonomous_ai, "SCHEDULER_ENABLED", False)
    backend.init_db()
    autonomous_ai.init_autonomous_db()
    with closing(backend.connect()) as db:
        db.execute("INSERT INTO users(id,telegram_sub,created_at,updated_at) VALUES(1,'osint-fixture',1,1)")
        db.execute("INSERT INTO sessions VALUES(?,1,?)", (backend.hash_token("osint-synthetic"), int(time.time()) + 120))
        db.commit()
    with TestClient(backend.app) as client:
        yield client


def item(url="https://www.moex.com/n1", text="Биржа: дивиденды по акциям", published=NOW):
    return {"url": url, "title": "Биржа: дивиденды", "text": text, "published_at": published,
            "primary": True, "publisher": "moex", "kind": "news"}


def save(connect, row, now=NOW):
    with closing(connect()) as db:
        result = store.save_publication(db, catalogue.BY_ID["moex_news"], row,
                                        analysis.analyze(row["title"], row["text"]), now)
        db.commit()
        return result


@pytest.mark.parametrize("url", [
    "http://www.moex.com/a", "https://127.0.0.1/a", "https://user:pass@www.moex.com/a",
    "https://www.moex.com:444/a", "https://localhost/a", "https://example.onion/a",
    "https://www.moex.com/a?api_key=credential", "https://www.moex.com\\@evil.example/a",
    "https://www.moex.com/a?" + "&".join("x=1" for _ in range(41)),
])
def test_rejects_unsafe_urls(url):
    with pytest.raises(catalogue.IntakeError):
        catalogue.canonical_url(url)


def test_canonical_tracking_and_host_boundary():
    assert catalogue.canonical_url("https://www.moex.com/a?utm_source=x&b=2&a=1#x") == "https://www.moex.com/a?a=1&b=2"
    with pytest.raises(catalogue.IntakeError):
        catalogue.canonical_url("https://www.moex.com.evil.example/a", ("www.moex.com",))


def test_dns_mixed_public_private_is_rejected(monkeypatch):
    monkeypatch.setattr(network.socket, "getaddrinfo", lambda *args, **kwargs: [
        (None, None, None, None, ("1.1.1.1", 443)), (None, None, None, None, ("10.0.0.1", 443))])
    with pytest.raises(catalogue.IntakeError, match="address_not_public"):
        network.public_addresses("www.moex.com")


def test_retry_after_and_robots_are_respected():
    assert network.retry_at("3600", NOW, 0, 600) == NOW + 3600
    assert network.retry_at("invalid", NOW, 2, 600) == NOW + 2400
    allowed, delay = network.robots_decision("User-agent: *\nDisallow: /private\nCrawl-delay: 9\n", "https://www.moex.com/private/a")
    assert allowed is False
    assert delay == 9


def test_rss_dates_html_filtering_and_external_source_provenance():
    raw = b"""<rss><channel><item><title>MOEX financial report</title><link>https://example.org/news</link>
    <description>&lt;script&gt;ignore me&lt;/script&gt;Revenue rises</description>
    <pubDate>Wed, 28 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>"""
    rows, coverage = content.feed(raw, catalogue.BY_ID["moex_news"], NOW)
    assert rows[0]["published_at"] == NOW
    assert rows[0]["primary"] is False
    assert "ignore" not in rows[0]["text"]
    assert coverage["items_seen"] == 1


@pytest.mark.parametrize("raw", [b"<!DOCTYPE a [<!ENTITY x 'a'>]><rss/>", b"<rss>\0</rss>", b"<html/>", b"broken"])
def test_invalid_or_entity_xml_rejected(raw):
    with pytest.raises(catalogue.IntakeError):
        content.feed(raw, catalogue.BY_ID["moex_news"], NOW)


def test_atom_does_not_invent_publication_date():
    raw = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>MOEX financial report</title>
    <link href="https://www.moex.com/news"/><updated>2026-10-28T00:00:00Z</updated></entry></feed>"""
    rows, _ = content.feed(raw, catalogue.BY_ID["moex_news"], NOW)
    assert rows[0]["published_at"] is None


def test_report_index_restricts_hosts_age_and_unrelated_dates():
    raw = """<div>26.10.2026 МСФО</div><a href="/media/msfo/report-2026.pdf">Финансовая отчётность 2026</a>
    <a href="https://evil.example/report.pdf">МСФО</a><a href="/media/report-2010.pdf">МСФО 2010</a>
    <a href="/media/slides.pdf">Презентация МСФО</a>""".encode()
    rows, _ = content.report_links(raw, catalogue.BY_ID["moex_reports"], "https://www.moex.com/", NOW)
    assert len(rows) == 1
    assert rows[0]["published_at"] is None
    assert rows[0]["url"].endswith("report-2026.pdf")


def test_discovery_is_metadata_not_publication_clock():
    raw = json.dumps({"articles": [{"url": "https://example.org/a", "title": "MOEX financial report",
                                  "seendate": "20261028T000000Z"}]}).encode()
    rows, _ = content.discovery(raw, NOW)
    assert rows[0]["published_at"] is None
    assert rows[0]["discovered_at"] == NOW
    assert rows[0]["primary"] is False


def test_sensitive_data_rejected_and_contacts_redacted():
    with pytest.raises(catalogue.IntakeError, match="sensitive"):
        analysis.clean_text("password=privatecredential")
    assert "alice@example.org" not in analysis.clean_text("Contact alice@example.org")
    assert analysis.analyze("Конференция биржи", "Регистрация на вебинар")["relevant"] is False


def test_denial_and_financial_candidates_never_become_trading_authority():
    result = analysis.analyze("Компания опровергла утечку данных", "Утечка не подтверждена.")
    assert result["stance"] == "denial"
    assert result["independent_confirmation"] == "not_established"
    assert result["trade_permission"] is False
    candidates = analysis.financial_candidates([{"page": 3, "text": "млн руб\nВыручка 1 200 900"}])
    assert candidates[0]["page"] == 3
    assert candidates[0]["unit_hint"] == "RUB million"
    assert candidates[0]["period"] is None


def test_url_and_content_deduplication_revisions_and_search(corpus):
    assert save(corpus, item()) is True
    assert save(corpus, item(), NOW + 10) is False
    second = item("https://www.moex.com/n2")
    assert save(corpus, second) is True
    result = read.documents(corpus, query="дивиденды", now=NOW)
    assert len(result["items"]) == 2
    assert result["items"][0]["similar_to"] == result["items"][1]["id"]
    assert result["items"][0]["similarity_is_corroboration"] is False
    with closing(corpus()) as db:
        assert db.execute("SELECT COUNT(*) FROM osint_objects_v1").fetchone()[0] == 1
    assert save(corpus, item(text="Биржа: дивиденды изменены"), NOW + 20)
    with closing(corpus()) as db:
        assert db.execute("SELECT COUNT(*) FROM osint_history_v1").fetchone()[0] == 1


def test_secondary_discovery_cannot_replace_official_evidence(corpus):
    save(corpus, item())
    row = item(text="New headline")
    row["primary"] = False
    assert save(corpus, row, NOW + 100) is False
    assert read.document(corpus, 1, now=NOW)["text"] == item()["text"]


def test_unknown_date_refresh_does_not_extend_retention(corpus):
    row = item(published=None)
    save(corpus, row)
    save(corpus, row, NOW + 29 * 86400)
    assert read.document(corpus, 1, now=NOW + 31 * 86400) is None
    assert cleanup(corpus, NOW + 31 * 86400)["expired"] == 1
    assert read.documents(corpus, query="дивиденды", now=NOW + 31 * 86400)["items"] == []


def test_capacity_failure_is_atomic(corpus, monkeypatch):
    monkeypatch.setattr(store, "MAX_OBJECT_BYTES", 3)
    row = item()
    with pytest.raises(catalogue.IntakeError, match="capacity"):
        save(corpus, row)
    assert read.documents(corpus, now=NOW)["items"] == []


def test_leases_concurrent_claim_restart_and_stale_writer(corpus):
    with ThreadPoolExecutor(max_workers=4) as pool:
        claimed = list(pool.map(lambda _: store.claim(corpus, NOW), range(4)))
    assert len({row["id"] for row in claimed}) == 4
    target = claimed[0]
    with closing(corpus()) as db:
        db.execute("UPDATE osint_targets_v1 SET next_at=? WHERE id!=?", (NOW + 10000, target["id"]))
        db.commit()
    assert store.claim(corpus, NOW + 599) is None
    recovered = store.claim(corpus, NOW + 601)
    assert recovered["id"] == target["id"]
    with pytest.raises(catalogue.IntakeError, match="lease_lost"):
        store.finish(corpus, target, now=NOW + 602, status="ready", next_at=NOW + 1000, headers={}, coverage={})


def test_transaction_guard_prevents_cancelled_write(corpus):
    target = store.claim(corpus, NOW)

    def stopped(_db):
        raise HTTPException(409, "paused")
    rows = [(item(), analysis.analyze(item()["title"], item()["text"]))]
    with pytest.raises(HTTPException):
        store.finish(corpus, target, now=NOW, status="ready", next_at=NOW + 1000, headers={}, coverage={},
                     rows=rows, guard=stopped)
    assert read.documents(corpus, now=NOW)["items"] == []


def test_gdelt_saturated_window_is_split_without_silent_cursor_loss():
    target = {"kind": "gdelt", "url": catalogue.BY_ID["gdelt_finance"].url}
    raw = json.dumps({"articles": [{"url": "https://example.org/" + str(i), "title": "MOEX financial report",
                                  "seendate": "20261028T000000Z"} for i in range(250)]}).encode()
    rows, _, coverage, cursor = worker._parse(target, catalogue.BY_ID["gdelt_finance"], raw, target["url"], NOW,
                                             {"start": NOW - 21600, "end": NOW, "gaps": 0})
    assert rows == []
    assert coverage["truncated"] is True
    assert cursor["start"] == NOW - 21600
    assert cursor["width"] == 10800


def test_read_api_is_authenticated_read_only_and_bounded(application, monkeypatch):
    monkeypatch.setattr(network, "request", lambda *args, **kwargs: pytest.fail("read initiated network"))
    for route in ("/status", "/sources", "/documents", "/documents/1"):
        assert application.get("/workspace/osint" + route).status_code == 401
    headers = {"Authorization": "Bearer osint-synthetic"}
    for route in ("/status", "/sources", "/documents?q=dividend"):
        response = application.get("/workspace/osint" + route, headers=headers)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store, private"
    assert application.get("/workspace/osint/documents?limit=1000", headers=headers).status_code == 422
    with closing(backend.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM workspace_jobs").fetchone()[0] == 0


def test_public_job_works_without_broker_and_coalesces(application, monkeypatch):
    monkeypatch.setattr(worker, "process", lambda target, guard: store.finish(backend.connect, target,
        now=int(time.time()), status="empty", next_at=int(time.time()) + 3600, headers={}, coverage={"items_seen": 0}, guard=guard))
    with closing(backend.connect()) as db:
        user = db.execute("SELECT * FROM users WHERE id=1").fetchone()
    job = worker.enqueue_cycle(user, "osint-manual-fixture")
    with pytest.raises(HTTPException, match="pending"):
        worker.enqueue_cycle(user, "osint-second-fixture")
    volume_jobs.run_job(job["job_id"])
    with closing(backend.connect()) as db:
        saved = db.execute("SELECT * FROM workspace_jobs WHERE id=?", (job["job_id"],)).fetchone()
        assert saved["state"] == "completed"
        assert saved["paid_started"] == 0
        assert json.loads(saved["result_json"])["paid_model_calls"] == 0


def test_paused_automation_cannot_enqueue_public_work(application):
    with closing(backend.connect()) as db:
        user = db.execute("SELECT * FROM users WHERE id=1").fetchone()
    autonomous_controller.update_preferences(autonomous_controller.PreferenceUpdate(enabled=False, expected_version=0), user)
    with pytest.raises(HTTPException, match="paused"):
        worker.enqueue_cycle(user, "paused-osint-fixture")


def test_corpus_commit_invalidates_existing_live_poll(application):
    now = int(time.time())
    before = volume_live.snapshot(1, backend.hash_token("osint-synthetic"))
    save(backend.connect, item(published=now), now)
    after = volume_live.snapshot(1, backend.hash_token("osint-synthetic"))
    assert after["revision"] != before["revision"]


def test_pdf_child_extracts_text_and_marks_scanned_pages():
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 40 700 Td (Financial report. Revenue 1200 900. Net profit 100 80.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    data = io.BytesIO()
    writer.write(data)
    result = worker.extract_pdf(data.getvalue())
    assert "Revenue" in result["pages"][0]["text"]
    blank = PdfWriter()
    blank.add_blank_page(width=612, height=792)
    data = io.BytesIO()
    blank.write(data)
    assert worker.extract_pdf(data.getvalue())["needs_ocr"] is True


def test_pdf_invalid_bytes_rejected():
    with pytest.raises(catalogue.IntakeError, match="pdf_invalid"):
        worker.extract_pdf(b"not a PDF")


def test_redirect_does_not_contact_unapproved_host(monkeypatch):
    called = []

    def redirect(url, *_args):
        called.append(url)
        return 302, {"location": "https://evil.example/private"}, b""
    monkeypatch.setattr(network, "_fetch_once", redirect)
    with pytest.raises(catalogue.IntakeError, match="host_not_approved"):
        network.request("https://www.moex.com/a", ("www.moex.com",))
    assert called == ["https://www.moex.com/a"]


def test_tls_checks_certificate_hostname_and_connects_checked_numeric_address(monkeypatch):
    from types import SimpleNamespace
    socket = SimpleNamespace(close=lambda: None)
    observed = {}
    context = SimpleNamespace(check_hostname=False, verify_mode=0)

    def wrap(value, server_hostname):
        observed.update(socket=value, hostname=server_hostname)
        return socket
    context.wrap_socket = wrap
    monkeypatch.setattr(network, "public_addresses", lambda _host: ["1.1.1.1"])
    monkeypatch.setattr(network.ssl, "create_default_context", lambda _purpose: context)

    def connect(address, timeout):
        observed.update(address=address, timeout=timeout)
        return socket
    monkeypatch.setattr(network.socket, "create_connection", connect)
    connection = network._connection("www.moex.com")
    connection.close()
    assert context.check_hostname is True
    assert context.verify_mode == network.ssl.CERT_REQUIRED
    assert observed["address"] == ("1.1.1.1", 443)
    assert observed["hostname"] == "www.moex.com"


def test_streaming_body_and_compressed_content_are_bounded():
    from types import SimpleNamespace
    connection = SimpleNamespace(sock=None)
    response = io.BytesIO(b"123456")
    deadline = time.monotonic() + 10
    with pytest.raises(catalogue.IntakeError, match="response_too_large"):
        network._read_body(response, {}, connection, deadline, 5)
    with pytest.raises(catalogue.IntakeError, match="encoding_not_supported"):
        network._read_body(response, {"content-encoding": "gzip"}, connection, deadline, 5)


def test_robots_unavailable_is_fail_closed_and_cached(application, monkeypatch):
    calls = []

    def denied(*_args, **_kwargs):
        calls.append(True)
        return 403, {}, b"", "https://www.moex.com/robots.txt"
    monkeypatch.setattr(network, "request", denied)
    source = catalogue.BY_ID["moex_reports"]
    for _ in range(2):
        with pytest.raises(catalogue.IntakeError, match="robots_unavailable"):
            worker._before(source.url, source, lambda _db: None, robots_required=True)
    assert calls == [True]


def test_retry_after_persists_source_backoff(application, monkeypatch):
    now = int(time.time())
    with closing(backend.connect()) as db:
        db.execute("UPDATE osint_targets_v1 SET next_at=? WHERE source_id!='moex_news'", (now + 10000,))
        db.commit()
    target = store.claim(backend.connect, now)
    monkeypatch.setattr(network, "request", lambda *_args, **_kwargs: (429, {"retry-after": "3600"}, b"", target["url"]))
    result = worker.process(target, worker.guard_for(1))
    assert result["status"] == "unavailable"
    with closing(backend.connect()) as db:
        saved = db.execute("SELECT * FROM osint_targets_v1 WHERE id=?", (target["id"],)).fetchone()
        assert saved["next_at"] >= now + 3600
        assert saved["error"] == "osint_http_429"
        assert saved["lease_owner"] is None
    with pytest.raises(catalogue.IntakeError, match="host_throttled"):
        store.reserve_host(backend.connect, "www.moex.com")


def test_existing_scheduler_collects_for_owner_without_broker(application, monkeypatch):
    monkeypatch.setattr(worker, "process", lambda target, guard: store.finish(backend.connect, target,
        now=int(time.time()), status="empty", next_at=int(time.time()) + 3600,
        headers={}, coverage={"items_seen": 0}, guard=guard))
    autonomous_ai.run_scheduler_cycle()
    with closing(backend.connect()) as db:
        jobs = db.execute("SELECT kind,state,paid_started FROM workspace_jobs").fetchall()
    assert any(row["kind"] == "osint" and row["state"] == "completed" and row["paid_started"] == 0 for row in jobs)


def test_expired_undated_item_does_not_resurrect_when_feed_changes(corpus):
    row = item(published=None)
    save(corpus, row)
    later = NOW + 31 * 86400
    cleanup(corpus, later)
    assert save(corpus, row, later) is False
    assert read.documents(corpus, now=later)["items"] == []
    row["text"] = "Биржа: изменены условия дивидендов"
    assert save(corpus, row, later) is True


def test_transport_can_use_second_checked_public_address(monkeypatch):
    connected = object()
    calls = []

    def connect(address, timeout):
        calls.append((address, timeout))
        if len(calls) == 1:
            raise OSError("unreachable first address")
        return connected
    monkeypatch.setattr(network.socket, "create_connection", connect)
    assert network._connect_address(["1.1.1.1", "8.8.8.8"]) is connected
    assert len(calls) == 2


def test_retention_remains_scheduled_while_all_publishers_are_backing_off(corpus):
    with closing(corpus()) as db:
        db.execute("UPDATE osint_targets_v1 SET next_at=?", (NOW + 86400,))
        db.commit()
    assert store.due(corpus, NOW) is True
    cleanup(corpus, NOW)
    assert store.due(corpus, NOW + 3599) is False
    assert store.due(corpus, NOW + 3600) is True
