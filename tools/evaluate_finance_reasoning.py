"""Evidence-only, CPU reasoning evaluation on public historical CBR and MOEX records.

Owner WSL only. No account data, secrets, paid model, order endpoint or production
state. A pass qualifies this small historical benchmark only. The model's private
reasoning is neither logged nor used as evidence.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import evaluate_local_e4b as baseline

DAYS = ("2024-06-06", "2024-06-07")
CBR = "https://www.cbr.ru/scripts/XML_daily.asp?date_req="
MOEX = ("https://iss.moex.com/iss/history/engines/stock/markets/shares/boards/TQBR/securities/SBER.json"
        "?from=2024-06-06&till=2024-06-07&iss.only=history&iss.meta=off"
        "&history.columns=BOARDID,TRADEDATE,SECID,CLOSE,CURRENCYID,TRADINGSESSION")
CAP = 512 * 1024
SYSTEM = ('Сравни только переданные исторические наблюдения. Не используй память, '
          'прогнозы или современные цены. Поле answer: up, down, flat или unknown. '
          'Если нужного периода или показателя нет, верни unknown и пустой список. '
          'evidence: идентификаторы всех и только необходимых наблюдений. '
          'Верни единственный объект JSON {"answer":"unknown","evidence":[]}.')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError("source_redirect")


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent":"AnalystAI-public-research-evaluation/1",
                                                   "Accept-Encoding":"identity"})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=12) as response:
        if response.status != 200 or response.geturl() != url or response.headers.get("Content-Encoding","identity") != "identity":
            raise ValueError("unexpected_source_response")
        body = response.read(CAP+1)
    if not 0 < len(body) <= CAP:
        raise ValueError("source_size")
    return body


def positive(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("invalid_number")
    number = Decimal(str(value).replace(",", "."))
    if not number.is_finite() or not 0 < number <= 1000000:
        raise ValueError("invalid_number")
    return number


def digest(b):
    return hashlib.sha256(b).hexdigest()


def cbr_row(day, url, body):
    if b"<!ENTITY" in body.upper() or b"<!DOCTYPE" in body.upper():
        raise ValueError("unexpected_xml")
    root = ET.fromstring(body)
    if root.tag != "ValCurs" or root.get("Date") != datetime.fromisoformat(day).strftime("%d.%m.%Y"):
        raise ValueError("source_date_or_schema")
    usd = [row for row in root.findall("Valute") if row.findtext("CharCode")=="USD"]
    if len(usd)!=1 or usd[0].findtext("NumCode")!="840" or usd[0].findtext("Nominal")!="1":
        raise ValueError("currency_or_nominal")
    return {"id":"fx-"+day, "date":day, "metric":"официальный курс ЦБ, RUB за 1 USD",
            "value":str(positive(usd[0].findtext("Value"))), "url":url, "source_sha256":digest(body)}


def moex_rows(body):
    table=json.loads(body, parse_float=Decimal)["history"]
    cols=table["columns"]
    expected={"BOARDID","TRADEDATE","SECID","CLOSE","CURRENCYID","TRADINGSESSION"}
    if not isinstance(cols,list) or set(cols)!=expected or len(cols)!=len(expected):
        raise ValueError("source_columns")
    if not isinstance(table["data"],list) or len(table["data"])>40:
        raise ValueError("source_rows")
    by_day={}
    for values in table["data"]:
        if not isinstance(values,list) or len(values)!=len(cols):
            raise ValueError("source_columns")
        r=dict(zip(cols,values))
        if r["BOARDID"]!="TQBR" or r["SECID"]!="SBER" or r["TRADEDATE"] not in DAYS:
            raise ValueError("unexpected_security_or_date")
        # Compare the same reported session on both dates. Preserve its raw ID
        # in the evidence and do not combine differently scoped observations.
        key=(r["TRADEDATE"],str(r["TRADINGSESSION"]))
        if key in by_day or r["CURRENCYID"] not in ("SUR","RUB"):
            raise ValueError("ambiguous_row_or_currency")
        by_day[key]=positive(r["CLOSE"])
    session=next((s for s in ("3","1") if all((d,s) in by_day for d in DAYS)),None)
    if session is None:
        raise ValueError("comparable_sessions_missing")
    return [{"id":"share-"+d,"date":d,"metric":"закрытие SBER, TQBR, RUB за акцию",
             "session":session,"value":str(by_day[d,session]),"url":MOEX,"source_sha256":digest(body)} for d in DAYS]


def capture():
    observations=[]; failures={}
    def attempt(key, proc):
        try:
            observations.extend(proc())
        except urllib.error.HTTPError as e:
            failures[key]="http_"+str(e.code)
        except (OSError, ValueError, InvalidOperation, ET.ParseError, KeyError, TypeError) as e:
            failures[key]=type(e).__name__
    for d in DAYS:
        url=CBR+datetime.fromisoformat(d).strftime("%d/%m/%Y")
        attempt("cbr-"+d,lambda d=d,url=url:[cbr_row(d,url,fetch(url))])
    attempt("moex",lambda:moex_rows(fetch(MOEX)))
    return {"observed_at_utc":datetime.now(timezone.utc).isoformat(),
            "observations":observations,"source_failures":failures}


def comparisons(rows):
    values={r["id"]:Decimal(r["value"]) for r in rows}
    direction=lambda a,b: "up" if b>a else "down" if b<a else "flat"
    fx=["fx-"+d for d in DAYS]; share=["share-"+d for d in DAYS]
    tasks=[]
    for name,ids,question in [
            ("official_fx",fx,"Как изменился официальный курс одного доллара в рублях с 6 на 7 июня 2024?"),
            ("rub_close",share,"Как изменилась рублёвая цена закрытия SBER с 6 на 7 июня 2024?")]:
        if all(k in values for k in ids):
            tasks.append((name,question,direction(values[ids[0]],values[ids[1]]),ids))
    if all(k in values for k in fx+share):
        tasks.append(("usd_equivalent","Как изменился долларовый эквивалент цены закрытия одной акции, "
                      "если делить рублёвое закрытие каждой даты на её официальный курс RUB за USD?",
                      direction(values[share[0]]*values[fx[1]],values[share[1]]*values[fx[0]]),share+fx))
    if rows:
        tasks.extend([("missing_payout","Как изменился размер объявленных дивидендов SBER между датами?","unknown",[]),
                      ("missing_rating","Как изменился кредитный рейтинг эмитента SBER между датами?","unknown",[]),
                      ("future_missing","Как изменилось закрытие SBER с 7 на 10 июня 2024?","unknown",[])])
    return tasks


def unique_pairs(pairs):
    parsed=dict(pairs)
    if len(parsed)!=len(pairs):
        raise ValueError("duplicate_field")
    return parsed


def score(raw, expected, citations):
    if not isinstance(raw,str) or len(raw.encode())>2048:
        return False
    try:
        r=json.loads(raw,object_pairs_hook=unique_pairs)
    except (ValueError,RecursionError):
        return False
    if not isinstance(r,dict) or set(r)!={"answer","evidence"} or r["answer"]!=expected:
        return False
    e=r["evidence"]
    return isinstance(e,list) and all(isinstance(x,str) for x in e) and len(e)==len(citations) and set(e)==set(citations)


def child(path):
    import litert_lm as lm
    from importlib.metadata import version
    if version("litert-lm-api")!="0.18.1":
        raise ValueError("wrong_runtime")
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_AS,(12*1024**3,12*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(740,745))
    rows=json.loads(Path(path).read_text())["observations"]
    public=[{k:r[k] for k in ("id","date","metric","value")} for r in reversed(rows)]
    lm.set_min_log_severity(lm.LogSeverity.ERROR)
    cases=[]
    with lm.Engine(str(baseline.MODEL),backend=lm.Backend.CPU(thread_count=2),max_num_tokens=2048,
                   cache_dir=str(baseline.CACHE/("engine-"+baseline.MODEL_SHA[:16]))) as engine:
        for name,question,expected,ids in comparisons(rows):
            prompt=json.dumps({"вопрос":question,"наблюдения":public},ensure_ascii=False)
            if len(engine.tokenize(SYSTEM+prompt))+320>2048:
                raise ValueError("context_overflow")
            start=time.monotonic(); valid=False
            try:
                with engine.create_conversation(messages=[lm.Message.system(SYSTEM)],tools=[],automatic_tool_calling=False,
                    max_output_tokens=224,thinking_config=lm.ThinkingConfig(enable_thinking=True,thinking_token_budget=128),
                    sampler_config=lm.SamplerConfig(top_k=1,temperature=0.0,seed=7),
                    extra_context={"enable_thinking":True}) as conversation:
                    reply=conversation.send_message(prompt)
                # Discard any thinking blocks; never print prompts or model text.
                blocks=reply.get("content",[]) if isinstance(reply,dict) else []
                final=[v.get("text") for v in blocks if isinstance(v,dict) and v.get("type")=="text"]
                valid=len(final)==1 and score(final[0],expected,ids)
            except (ValueError,RuntimeError,TypeError):
                pass
            cases.append({"case":name,"correct_answer_and_exact_evidence":valid,"seconds":round(time.monotonic()-start,2)})
    print(json.dumps({"cases":cases,"peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2)}))


def main():
    if sys.platform!="linux" or os.environ.get("WSL_DISTRO_NAME")!="Ubuntu-24.04":
        raise ValueError("owner_wsl_required")
    if sys.argv[1:2]==["--infer"] and len(sys.argv)==3:
        child(sys.argv[2]);return
    if sys.argv[1:]:
        raise ValueError("unexpected_arguments")
    report={"schema":1,"task":"historical_evidence_reasoning","model":baseline.MODEL_ID,
            "revision":baseline.REVISION,"weight_sha256":baseline.MODEL_SHA,"cpu_threads":2,
            "thinking_enabled":True,"thinking_token_budget":128,"accepted":False,
            "production_activated":False,"paid_ai_calls":0,"account_requests":0}
    try:
        data=capture(); report.update(data)
        if len(comparisons(data["observations"]))<=3:
            raise ValueError("comparable_source_pair_unavailable")
        if baseline.mem_available()<7168*1024**2 or not baseline.MODEL.is_file():
            raise ValueError("evaluation_host_or_cached_weights_unavailable")
        if baseline.MODEL.stat().st_size!=baseline.MODEL_BYTES or baseline.sha(baseline.MODEL)!=baseline.MODEL_SHA:
            raise ValueError("weight_hash_mismatch")
        with tempfile.TemporaryDirectory(prefix="analyst-reasoning-") as td:
            folder=Path(td); snap=folder/"public.json"; snap.write_text(json.dumps(data))
            subprocess.run([sys.executable,"-m","venv",str(folder/"venv")],check=True,capture_output=True,timeout=60)
            py=str(folder/"venv/bin/python")
            req=folder/"requirements.txt"
            req.write_text("litert-lm-api==0.18.1 --hash=sha256:"+baseline.RUNTIME_SHA+"\n")
            subprocess.run([py,"-m","pip","install","--only-binary=:all:","--require-hashes","--no-deps",
                "--disable-pip-version-check","-r",str(req)],check=True,capture_output=True,timeout=150)
            result=subprocess.run([py,"-I",str(Path(__file__).resolve()),"--infer",str(snap)],
                    stdin=subprocess.DEVNULL,capture_output=True,timeout=510)
            if result.returncode or len(result.stdout)>8192:
                raise ValueError("bounded_inference_failed")
            report.update(json.loads(result.stdout.splitlines()[-1]))
        cases=report["cases"]
        report["accepted"]=not data["source_failures"] and len(cases)==6 and all(
            r["correct_answer_and_exact_evidence"] and r["seconds"]<=75 for r in cases) and report["peak_rss_mib"]<=5120
        report["status"]="measured"
    except (ValueError,OSError,subprocess.SubprocessError,IndexError) as e:
        code=str(e) if isinstance(e,ValueError) and str(e) in {
            "comparable_source_pair_unavailable","evaluation_host_or_cached_weights_unavailable",
            "weight_hash_mismatch","bounded_inference_failed"} else type(e).__name__
        report.update(status="not_measured",reason=code)
    (ROOT/"finance-reasoning-evaluation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINANCE_REASONING="+json.dumps({k:v for k,v in report.items() if k!="observations"}),flush=True)
    if not report["accepted"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
