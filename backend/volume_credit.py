"""Observed credit-risk changes from reviewed evidence, with no invented ratings."""
from contextlib import closing

try:
    from .credit_evidence import MAXIMUM_CREDIT_LEVEL
    from . import app as backend, research_store, volume_market as market
    from .volume_contract import digest
except ImportError:
    from credit_evidence import MAXIMUM_CREDIT_LEVEL
    import app as backend
    import research_store
    import volume_market as market
    from volume_contract import digest


def _identity(row: dict) -> tuple:
    return tuple(row.get(key) for key in ("agency", "scale", "subject_kind", "subject_id", "evidence_basis"))


def _summary(value: dict | None) -> dict:
    data = (value or {}).get("data", {})
    return {"state": (value or {}).get("state", "unavailable"), "warnings": data.get("warnings", []),
            "items": [{key: row.get(key) for key in ("agency", "scale", "subject_kind", "subject_id", "grade", "status", "outlook", "is_under_watch", "evidence_basis", "level_within_agency")}
                      for row in data.get("items", [])]}


def critical(value: dict | None, previous: dict | None = None) -> bool:
    before = {_identity(row): row for row in _summary(previous)["items"]}
    for row in _summary(value)["items"]:
        level = row.get("level_within_agency")
        prior = before.get(_identity(row), {}).get("level_within_agency")
        # Grade levels are comparable only within the same agency, scale and
        # rated object. A missing/expired grade is never a numerical downgrade.
        if row.get("outlook") in {"negative", "developing", "watch_negative"} or row.get("is_under_watch") is True or (
            type(level) is int and (level > MAXIMUM_CREDIT_LEVEL or type(prior) is int and level > prior)):
            return True
    return False


def observations(snapshot: dict) -> dict:
    with closing(backend.connect()) as db:
        research_store.initialize(db)
        subjects = {row[0] for row in db.execute("SELECT DISTINCT subject FROM research_evidence_v1 WHERE kind='rating'")}
    selected = {}
    for position in snapshot.get("positions", []):
        uid = position["instrument_uid"]
        issuer = (position.get("verified_identity") or {}).get("issuer_id")
        metadata = position.get("metadata") or {}
        has_broker_ratings = "broker_ratings" in metadata
        if uid in selected or not (uid in subjects or issuer in subjects or has_broker_ratings):
            continue
        meta = {"uid": uid, "instrumentType": position.get("instrument_type")}
        if has_broker_ratings:
            meta.update(ratings=metadata["broker_ratings"], _source={"observed_at": metadata.get("broker_ratings_observed_at")})
        value = market.rating_section(uid, meta)
        # Full action history stays in the dossier; monitoring retains only the
        # assessed current state plus its actual source records.
        value["data"] = {key: raw for key, raw in value.get("data", {}).items() if key != "history"}
        selected[uid] = value
    return selected


def record_changes_in(db, user_id: int, snapshot: dict, previous: dict | None) -> None:
    try:
        from . import volume_state as state, volume_notifications as notifications
    except ImportError:
        import volume_state as state
        import volume_notifications as notifications
    current, old = snapshot.get("rating_observations", {}), (previous or {}).get("rating_observations", {})
    for uid in current.keys() | old.keys():
        before, after = old.get(uid), current.get(uid)
        if _summary(before) == _summary(after) or before is None and not critical(after):
            continue
        new_sources = (after or {}).get("sources", [])
        old_sources = (before or {}).get("sources", [])
        ids = {r["id"] for r in new_sources}
        stale = not after or ids == {r["id"] for r in old_sources} and not _summary(after)["items"]
        event = state.event(db, user_id, "risk_rating_data_stale" if stale else "risk_rating_changed", snapshot["snapshot_id"],
            {"title": "Основание кредитного риска требует обновления" if stale else "Изменилось подтверждённое основание кредитного риска",
             "instrument_uids": [uid], "source_ids": sorted(ids | {r["id"] for r in old_sources}),
             "sources": list({r["id"]: r for r in old_sources + new_sources}.values()),
             "details": {"before": _summary(before), "after": _summary(after), "critical": critical(after, before),
                         "basis": "reviewed_agency_records_not_a_default_probability", "missing_is_not_resolved": stale}},
            digest({"uid": uid, "before": _summary(before), "after": _summary(after), "source_ids": sorted(ids)}))
        notifications.enqueue_in(db, user_id, kind="risk", title=event["title"],
                                 body="Проверьте агентство, объект рейтинга, дату и первичный источник в досье.", event_id=event["id"])


def signature(values: dict) -> str:
    return digest({uid: _summary(row) for uid, row in sorted(values.items())})

