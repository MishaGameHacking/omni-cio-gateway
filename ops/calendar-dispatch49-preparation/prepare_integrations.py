"""Prepare reviewed source text; application and tests run only on the laptop."""
from pathlib import Path
import ast
import hashlib
import json

HERE = Path(__file__).resolve().parent
REFERENCE = HERE / "reference"
OUTPUT = HERE / "source-text"
INVENTORY = json.loads((HERE.parent / "build48-v7/source-final.json").read_bytes())["files"]


def base(name):
    raw = (REFERENCE / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == INVENTORY[name]["sha256"], name
    return raw.decode()


def replace(text, old, new):
    assert text.count(old) == 1, old[:160]
    return text.replace(old, new, 1)


def save(name, text):
    if name.endswith(".py"):
        ast.parse(text, filename=name)
    path = OUTPUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


jobs = base("backend/volume_jobs.py")
jobs = replace(jobs, ' + " ORDER BY q.created_at,q.id LIMIT 1"\n        row = db.execute(query, (identifier,) if identifier else ()).fetchone()',
''' + """ ORDER BY CASE WHEN q.kind='reconcile' THEN 0 ELSE MAX(1,
            CASE WHEN q.kind='events' THEN 1
                 WHEN q.kind='chat' THEN 2
                 WHEN q.kind='refresh' AND q.request_id NOT LIKE 'auto.full.%' THEN 2 ELSE 3 END
            - CAST(MAX(0, ? - q.created_at) / 300 AS INTEGER)) END, q.created_at,q.id LIMIT 1"""
        # Each five minutes of waiting promotes one level. Even catalogue/full
        # work eventually reaches the front; existing per-user leases still win.
        row = db.execute(query, ((identifier,) if identifier else ()) + (now,)).fetchone()''')
jobs = replace(jobs, '    if job["kind"] == "refresh":\n', '''    if job["kind"] == "events":
        try:
            from .event_monitor import collect_events
        except ImportError:
            from event_monitor import collect_events
        return collect_events(user, payload, checkpoint, progress)
    if job["kind"] == "refresh":
''')
jobs = replace(jobs, '    if job["kind"] == "refresh":\n        return collect(user, payload, checkpoint, progress)',
'''    if job["kind"] == "refresh":
        if job["request_id"].startswith("auto.full."):
            try:
                from .background_dispatch import automatic_collection_gate
            except ImportError:
                from background_dispatch import automatic_collection_gate
            waiting = automatic_collection_gate(user, payload, checkpoint)
            if waiting is not None:
                return waiting
        return collect(user, payload, checkpoint, progress)''')
jobs = replace(jobs, '        result = {"analysis_job_id": AnalysisQueue(backend.connect).enqueue_in(db, job["user_id"])["job_id"]}\n',
'''        result = {"analysis_job_id": AnalysisQueue(backend.connect).enqueue_in(db, job["user_id"])["job_id"]}
        try:
            from .background_dispatch import mark_manual_in
        except ImportError:
            from background_dispatch import mark_manual_in
        mark_manual_in(db, job["user_id"], result["analysis_job_id"])
''')
save("backend/volume_jobs.py", jobs)

workspace = base("backend/volume_workspace.py")
workspace = replace(workspace, 'checkpoint["news"] = safe_section(lambda: market.load_news(user), empty={"items": [], "complete": False})',
'''checkpoint["news"] = safe_section(lambda: details.cached(("workspace-news", *details.identity(user)), 600,
            lambda: market.load_news(user)), empty={"items": [], "complete": False})''')
workspace = replace(workspace, 'def persist(user: Any, snapshot: dict) -> None:',
                    'def persist(user: Any, snapshot: dict, *, expected_snapshot: dict | None = None) -> None:')
workspace = replace(workspace, '        assert_monitoring_access_in(db)\n        db.execute("""INSERT INTO workspace_snapshots',
'''        assert_monitoring_access_in(db)
        if expected_snapshot is not None:
            current = db.execute("SELECT id,broker_key,payload_json FROM workspace_snapshots WHERE user_id=? AND currency=?",
                                 (user_id, snapshot["currency"])).fetchone()
            value = None if current is None else {**json.loads(current["payload_json"]), "snapshot_id": current["id"]}
            if current is None or current["broker_key"] != state.broker_key(user) or digest(value) != digest(expected_snapshot):
                raise HTTPException(409, "workspace_snapshot_changed")
        db.execute("""INSERT INTO workspace_snapshots''')
workspace = replace(workspace, '        sections[key] = section(data, state=item_state, reason=_section_reason(section_stale, reason, item_state), as_of=section_observed, sources=(snapshot or {}).get("sources", []))',
'''        item_reason = reason
        if key in {"payouts", "events"} and key in (snapshot or {}).get("section_as_of", {}):
            # Event freshness is independent of an intentionally old valuation.
            item_state = "partial" if section_stale or section_observed is None or data.get("complete") is False else "available"
            item_reason = None
        sections[key] = section(data, state=item_state, reason=_section_reason(section_stale, item_reason, item_state), as_of=section_observed, sources=(snapshot or {}).get("sources", []))''')
save("backend/volume_workspace.py", workspace)

monitor = base("backend/volume_monitor.py")
monitor = replace(monitor, '("attribution", "payouts", "operations", "events", "news", "calendar", "collection"):',
                          '("attribution", "payouts", "operations", "events", "news", "calendar", "collection", "event_monitor"):')
save("backend/volume_monitor.py", monitor)

market = base("backend/volume_market.py")
market = replace(market, 'begin = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time(), timezone.utc)\n    finish = begin + timedelta(days=6, hours=23, minutes=59)',
'''# Include the previous UTC day so an overnight broker window is not lost.
    today = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time(), timezone.utc)
    begin = today - timedelta(days=1)
    finish = today + timedelta(days=6, hours=23, minutes=59)''')
market = replace(market, "return details.cached(('workspace-calendar', *details.identity(user)), 900, lambda: load_calendar(user))",
                          "return details.cached(('workspace-calendar', *details.identity(user)), 600, lambda: load_calendar(user))")
save("backend/volume_market.py", market)

controller = base("backend/autonomous_controller.py")
controller = replace(controller, "updated_at=? WHERE user_id=? AND request_id LIKE 'auto.full.%'",
                    "updated_at=? WHERE user_id=? AND (request_id LIKE 'auto.full.%' OR request_id LIKE 'auto.events.%')")
controller = replace(controller, '    "automation_paused": "Автоматический анализ приостановлен в настройках.",',
'''    "automation_paused": "Автоматический анализ приостановлен в настройках.",
    "market_price_polling_paused": "Опрос цен ожидает торгового окна. Проверка событий продолжается.",''')
controller = replace(controller, '    discovery = _discovery(user, active, now)\n    return {"schema_version": 1,',
'''    discovery = _discovery(user, active, now)
    try:
        from .background_dispatch import schedule
    except ImportError:
        from background_dispatch import schedule
    dispatch = schedule(user, now=datetime.fromtimestamp(now, timezone.utc), snapshot=snapshot)
    events = dispatch["events"]
    event_age = _age(events.get("last_successful_at"), now)
    if (state_name == "attention" and codes == ["workspace_collection_delayed"]
            and not dispatch["regular_price_polling_allowed"] and events.get("complete") is True
            and event_age is not None and event_age < 1200):
        state_name, codes = "waiting", ["market_price_polling_paused"]
    return {"schema_version": 1,''')
controller = replace(controller, '            "current_job": current_job,', '            "current_job": current_job, "dispatch": dispatch,')
save("backend/autonomous_controller.py", controller)

ai = base("backend/autonomous_ai.py")
ai = replace(ai, '    previous, previous_row = _latest_snapshot(user_id)\n    try:\n        snapshot = get_tinvest_portfolio',
'''    try:
        from .background_dispatch import automatic_analysis_gate
        from .volume_monitor import record_check
    except ImportError:
        from background_dispatch import automatic_analysis_gate
        from volume_monitor import record_check
    waiting = automatic_analysis_gate(user, CURRENT_JOB.get(), current_time)
    if waiting is not None:
        record_check(user_id, current_time, status="waiting", reason=waiting["reason"], tier="none")
        return {"state": "waiting", "reason": waiting["reason"], "tier": "none", "card_id": None}
    previous, previous_row = _latest_snapshot(user_id)
    try:
        snapshot = get_tinvest_portfolio''')
ai = replace(ai, '    queue = AnalysisQueue(backend.connect)\n    with closing(backend.connect()) as db:\n        users =',
'''    queue = AnalysisQueue(backend.connect)
    try:
        from .background_dispatch import enqueue_cycle
    except ImportError:
        from background_dispatch import enqueue_cycle
    with closing(backend.connect()) as db:
        users =''')
ai = replace(ai, '            _automation().enqueue_collection(user)', '            enqueue_cycle(user)')
ai = replace(ai, '        queue.enqueue(user_id)\n    try:', '    try:')
ai = replace(ai, "    return {**queue.enqueue(int(user['id'])), 'reason': 'queued_recheck',",
'''    try:
        from .background_dispatch import enqueue_manual_analysis
    except ImportError:
        from background_dispatch import enqueue_manual_analysis
    return {**enqueue_manual_analysis(user), 'reason': 'queued_recheck',''')
save("backend/autonomous_ai.py", ai)

tests = base("backend/tests/test_autonomous_controller.py")
tests = replace(tests, '    snapshot = saved(fixture, age=1900)\n    job = controller.enqueue_collection(fixture["user"])',
'''    snapshot = saved(fixture, age=1900)
    # Exercise a real collection failure in an explicitly open broker window.
    now = datetime.now(timezone.utc)
    for position in snapshot["positions"]:
        if position["instrument_type"] in {"share", "bond"}:
            position.setdefault("metadata", {})["exchange"] = "MOEX"
    snapshot["calendar"] = {"state": "available", "data": {"timezone": "UTC", "as_of": now.isoformat(),
        "exchanges": [{"exchange": "MOEX", "days": [{"date": now.isoformat(), "isTradingDay": True,
            "startTime": (now - timedelta(minutes=10)).isoformat(), "endTime": (now + timedelta(hours=1)).isoformat()}]}]}}
    workspace.persist(fixture["user"], snapshot)
    job = controller.enqueue_collection(fixture["user"])''')
save("backend/tests/test_autonomous_controller.py", tests)

for name in ("app/build.gradle.kts", ".github/scripts/tests/test_android17_live_spectrum.py", ".github/scripts/tests/test_spectrum_brand_identity.py"):
    text = base(name)
    text = text.replace('versionCode = 48', 'versionCode = 49').replace('versionName = "0.14.1"', 'versionName = "0.14.2"')
    text = text.replace('int(version.group(1)), 48', 'int(version.group(1)), 49')
    assert text != base(name), name
    save(name, text)

print(json.dumps({"prepared_source_text": True, "application_or_tests_executed": False}))
