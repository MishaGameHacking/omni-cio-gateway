"""Calculate dated comparisons on checked public input. No I/O, model facts or broker access."""
from datetime import date
from decimal import Decimal, InvalidOperation
import json
import re


def build(rows):
    facts={}; dates=set()
    for row in rows:
        day=date.fromisoformat(row["date"]).isoformat()
        identifier=row["id"]; field=identifier.split("-",1)[0]
        if (field not in {"fx","share"} or identifier!=field+"-"+day or identifier in facts
                or not re.fullmatch(r"[a-f0-9]{64}",row["source_sha256"])):
            raise ValueError("invalid_source_record")
        try:
            v=Decimal(row["value"])
        except (InvalidOperation,TypeError):
            raise ValueError("invalid_observation") from None
        if not v.is_finite() or not 0<v<=1000000 or len(v.as_tuple().digits)>14 or v.as_tuple().exponent < -12:
            raise ValueError("invalid_observation")
        facts[identifier]=(v,row["source_sha256"]); dates.add(day)
    if len(dates)>2:
        raise ValueError("explicit_two_date_window_required")
    if len(dates)<2:
        return []
    start,end=sorted(dates)
    catalog=[]
    for a,b in [(start,end),(end,start)]:
        fx=["fx-"+a,"fx-"+b]; share=["share-"+a,"share-"+b]
        for metric,ids in [
                ("Официальный курс ЦБ: рублей за один доллар США",fx),
                ("Цена закрытия одной акции SBER на TQBR в рублях",share),
                ("Эквивалент рублёвой цены закрытия одной акции SBER в долларах США по курсу ЦБ",share+fx)]:
            if not all(k in facts for k in ids): continue
            earlier,later=[facts[k][0] for k in ids[:2]]
            if len(ids)==4:
                # Comparing p1/r1 to p2/r2 by cross multiplication is exact.
                earlier*=facts[ids[3]][0]; later*=facts[ids[2]][0]
            catalog.append({"id":"ABCDEF"[len(catalog)],"metric":metric,"from":a,"to":b,
                "answer":"up" if later>earlier else "down" if later<earlier else "flat",
                "evidence":sorted(ids),"source_hashes":{k:facts[k][1] for k in sorted(ids)}})
    return catalog


def menu(catalog):
    return [{k:r[k] for k in ("id","metric","from","to")} for r in catalog]


def resolve(raw,catalog):
    def unique(pairs):
        if len(dict(pairs))!=len(pairs):raise ValueError("duplicate_field")
        return dict(pairs)
    if not isinstance(raw,str) or len(raw.encode())>128:
        raise ValueError("invalid_selection")
    r=json.loads(raw,object_pairs_hook=unique)
    if not isinstance(r,dict) or set(r)!={"id"} or not isinstance(r["id"],str):
        raise ValueError("invalid_selection")
    if r["id"]=="NONE":
        return {"answer":"unknown","evidence":[],"source_hashes":{}}
    selected=[o for o in catalog if o["id"]==r["id"]]
    if len(selected)!=1:raise ValueError("invalid_selection")
    return {k:selected[0][k] for k in ("answer","evidence","source_hashes")}
