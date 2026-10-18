"""Authenticated, reproducible search over actual broker catalogues, without an LLM."""
from __future__ import annotations

from typing import Any, Literal
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Query

try:
    from . import app as backend, portfolio_details as details, volume_market as market
    from .volume_contract import HTTP_ERRORS, digest, now_iso, source
except ImportError:
    import app as backend
    import portfolio_details as details
    import volume_market as market
    from volume_contract import HTTP_ERRORS, digest, now_iso, source

router = APIRouter(prefix="/workspace/catalogue", tags=["Broker instrument search"])
KINDS = {"share": "shares", "bond": "bonds", "etf": "etfs"}
FIELDS = ("uid", "ticker", "isin", "name", "classCode", "exchange", "realExchange",
          "currency", "lot", "buyAvailableFlag", "sellAvailableFlag", "apiTradeAvailableFlag",
          "forQualInvestorFlag", "requiredTests", "blockedTcaFlag", "weekendFlag",
          "subordinatedFlag", "perpetualFlag", "riskLevel", "maturityDate")


def normalized_query(value: str) -> str:
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise HTTPException(422, "catalogue_query_invalid")
    return unicodedata.normalize("NFKC", value).casefold().strip()


def normalize_catalogue(raw: dict, kind: str) -> list[dict]:
    rows = raw.get("instruments")
    if not isinstance(rows, list) or len(rows) > 100_000:
        raise HTTPException(502, "catalogue_response_invalid")
    result = {}
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("uid"), str) or not item["uid"].strip():
            raise HTTPException(502, "catalogue_identity_missing")
        row = {key: item.get(key) for key in FIELDS}
        row["instrument_type"] = kind
        uid = row["uid"]
        if uid in result and result[uid] != row:
            raise HTTPException(502, "catalogue_identity_conflict")
        result[uid] = row
    return list(result.values())


def load_catalogue(user: Any, kind: str) -> dict:
    def load():
        method = KINDS[kind]
        with details.BrokerReader(user) as reader:
            raw = market.broker_read(reader, method, {"instrumentStatus": "INSTRUMENT_STATUS_ALL"})
        rows = normalize_catalogue(raw, kind)
        rows.sort(key=lambda row: row["uid"])
        observed = now_iso()
        ref = source(method.title(), kind, observed, ttl=300)
        # Includes the observation time, so a page from a different observation
        # cannot silently replace the remainder of a previously shown result.
        return {"items": rows, "revision": digest({"items": rows, "as_of": observed}),
                "as_of": observed, "source": ref}
    return details.cached(("catalogue-v1", *details.identity(user), kind), 300, load)


def search_page(catalogue: dict, query: str, offset: int, limit: int, expected_revision: str | None) -> dict:
    normalized = normalized_query(query)
    revision = digest({"catalogue": catalogue["revision"], "query": normalized})
    if (offset > 0 and expected_revision is None) or (expected_revision is not None and expected_revision != revision):
        raise HTTPException(409, "catalogue_observation_changed")
    def keys(row):
        return [unicodedata.normalize("NFKC", "".join(char for char in str(row.get(field) or "") if not unicodedata.category(char).startswith("C"))).casefold().strip() for field in ("ticker", "isin", "name", "uid")]
    found = []
    terms = normalized.split()
    for row in catalogue["items"]:
        fields = keys(row)
        haystack = " ".join(fields)
        if all(term in haystack for term in terms):
            found.append((0 if normalized and normalized in fields else 1, fields[0], row["uid"], row))
    found.sort(key=lambda item: item[:3])
    found = [item[3] for item in found]
    selected = found[offset:offset + limit]
    return {"items": selected, "total": len(found), "catalogue_total": len(catalogue["items"]),
            "offset": offset, "next_offset": offset + limit if offset + limit < len(found) else None,
            "revision": revision, "as_of": catalogue["as_of"], "sources": [catalogue["source"]],
            "coverage": "selected_broker_instrument_class", "market_wide_analysis": False,
            "purchase_suitability_checked": False,
            "explanation": "Каталог брокера включает и недоступные инструменты. Наличие в поиске не подтверждает пригодность покупки."}


@router.get("", responses=HTTP_ERRORS)
def search(query: str = Query(default="", max_length=160), kind: Literal["share", "bond", "etf"] = "bond",
           offset: int = Query(default=0, ge=0, le=100_000), limit: int = Query(default=30, ge=1, le=100),
           revision: str | None = Query(default=None, max_length=64), user: Any = Depends(backend.current_user)) -> dict:
    normalized_query(query)
    return search_page(load_catalogue(user, kind), query, offset, limit, revision)
