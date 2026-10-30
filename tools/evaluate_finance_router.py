"""Same historical material and scoring as the initial E4B run; arithmetic is code-owned.

The model sees the question and available dated operations, never the oracle,
computed direction, or prices. This tests the combined system, not native maths.
"""
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"research"),str(ROOT/"tools")]
import financial_evidence as calc
import evaluate_finance_reasoning as raw
import evaluate_local_e4b as model

ARCHIVE="546ac8e113dee245064ab620ad8be0c2cb7b09d9f67340e4f9e2f696e8a2d909"
SYSTEM=('Ты выбираешь расчёт, который точно отвечает на вопрос о двух датах. '
        'Сопоставь объект, единицу и порядок дат. Если подходящего расчёта нет, верни NONE. '
        'Если вопрос говорит «между датами», используй указанный основной период. '
        'Выведи только JSON с одним полем id, например {"id":"NONE"}; id возьми из меню. '
        'Не рассчитывай числа и не добавляй текст.')


def rows_and_proof():
    path=ROOT/"prior-evidence.zip"
    if path.stat().st_size>32768 or hashlib.sha256(path.read_bytes()).hexdigest()!=ARCHIVE:
        raise ValueError("evidence_artifact_mismatch")
    with zipfile.ZipFile(path) as z:
        items=z.infolist()
        if len(items)!=1 or items[0].filename!="finance-reasoning-evaluation.json" or items[0].file_size>32768:
            raise ValueError("evidence_archive_shape")
        receipt=json.loads(z.read(items[0]))
    old=receipt["observations"]
    if receipt.get("status")!="measured" or receipt.get("source_failures")!={} or len(old)!=4:
        raise ValueError("prior_evidence_missing")
    # Compare the actual public observations, including nominal, source URLs,
    # session, and response-byte hashes, against this run's independent fetches.
    fresh=raw.capture()
    if fresh["source_failures"] or old!=fresh["observations"]:
        raise ValueError("public_evidence_changed_or_unavailable")
    return old


def cases(rows):
    checks=[("original",*case,rows) for case in raw.comparisons(rows)]
    for case,question in [
            ("other_issuer","Как изменилась рублёвая цена закрытия акции Газпрома с 6 на 7 июня 2024?"),
            ("missing_yield","Как изменилась доходность облигаций эмитента между датами?")]:
        checks.append(("extra",case,question,"unknown",[],rows))
    fx=["fx-"+d for d in raw.DAYS]
    d={r["id"]:Decimal(r["value"]) for r in rows}
    inverse="up" if d[fx[0]]>d[fx[1]] else "down" if d[fx[0]]<d[fx[1]] else "flat"
    checks.append(("extra","reverse_period","Сравни курс доллара в рублях в обратном порядке: "
                   "начни с 7 июня 2024 и закончи 6 июня 2024. Как он изменился?",inverse,fx,rows))
    trimmed=[r for r in rows if r["id"]!=fx[1]]
    checks.append(("extra","missing_fx_input","Как изменился эквивалент закрытия SBER в долларах "
                   "по курсу ЦБ с 6 на 7 июня 2024?","unknown",[],trimmed))
    return checks


def child(path):
    import litert_lm as lm
    from importlib.metadata import version
    if version("litert-lm-api")!="0.18.1":raise ValueError("invalid_runtime")
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_CPU,(1100,1105))
    resource.setrlimit(resource.RLIMIT_AS,(12*1024**3,12*1024**3))
    lm.set_min_log_severity(lm.LogSeverity.ERROR); result=[]
    with lm.Engine(str(model.MODEL),backend=lm.Backend.CPU(thread_count=2),max_num_tokens=2048,
                   cache_dir=str(model.CACHE/("engine-"+model.MODEL_SHA[:16]))) as engine:
        for group,name,q,expected,cites,rows in cases(json.loads(Path(path).read_text())):
            catalog=calc.build(rows)
            prompt=json.dumps({"вопрос":q,"основной период":list(raw.DAYS),"меню":calc.menu(catalog)},ensure_ascii=False)
            if len(engine.tokenize(SYSTEM+prompt))+320>2048:raise ValueError("context_overflow")
            started=time.monotonic(); schema=False; answer=False; evidence=False
            try:
                with engine.create_conversation(messages=[lm.Message.system(SYSTEM)],tools=[],automatic_tool_calling=False,
                    max_output_tokens=224,thinking_config=lm.ThinkingConfig(enable_thinking=True,thinking_token_budget=128),
                    sampler_config=lm.SamplerConfig(top_k=1,temperature=0.0,seed=7),
                    extra_context={"enable_thinking":True}) as conversation:
                    response=conversation.send_message(prompt)
                blocks=response.get("content",[]) if isinstance(response,dict) else []
                final=[b.get("text") for b in blocks if isinstance(b,dict) and b.get("type")=="text"]
                if len(final)==1:
                    resolved=calc.resolve(final[0],catalog); schema=True
                    answer=resolved["answer"]==expected
                    evidence=set(resolved["evidence"])==set(cites) and len(resolved["evidence"])==len(cites)
            except (TypeError,ValueError,RuntimeError,RecursionError):
                pass
            result.append({"suite":group,"case":name,"valid_selection":schema,"answer_correct":answer,
                 "exact_evidence":evidence,"passed":schema and answer and evidence,"seconds":round(time.monotonic()-started,2)})
    print(json.dumps({"cases":result,"peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2)}))


def main():
    if sys.platform!="linux" or os.environ.get("WSL_DISTRO_NAME")!="Ubuntu-24.04":raise ValueError("owner_wsl_required")
    if sys.argv[1:2]==["--infer"] and len(sys.argv)==3:
        child(sys.argv[2]);return
    if sys.argv[1:]:raise ValueError("unexpected_arguments")
    report={"status":"not_measured","accepted":False,"model":model.MODEL_ID,"revision":model.REVISION,
            "cpu_threads":2,"thinking_token_budget":128,"reference_archive_sha256":ARCHIVE,
            "account_requests":0,"paid_calls":0,"production_activated":False}
    try:
        rows=rows_and_proof()
        report["primary_source_hashes"]=sorted(set(r["source_sha256"] for r in rows))
        if model.mem_available()<7168*1024**2 or not model.MODEL.is_file() or model.MODEL.stat().st_size!=model.MODEL_BYTES or model.sha(model.MODEL)!=model.MODEL_SHA:
            raise ValueError("host_capacity_or_weights_unverified")
        with tempfile.TemporaryDirectory(prefix="analyst-router-") as td:
            folder=Path(td); snap=folder/"public.json";snap.write_text(json.dumps(rows))
            subprocess.run([sys.executable,"-m","venv",str(folder/"venv")],check=True,capture_output=True,timeout=60)
            py=str(folder/"venv/bin/python"); req=folder/"requirements.txt"
            req.write_text("litert-lm-api==0.18.1 --hash=sha256:"+model.RUNTIME_SHA+"\n")
            subprocess.run([py,"-m","pip","install","--only-binary=:all:","--require-hashes","--no-deps",
                "--disable-pip-version-check","-r",str(req)],check=True,capture_output=True,timeout=150)
            measured=subprocess.run([py,"-I",str(Path(__file__).resolve()),"--infer",str(snap)],stdin=subprocess.DEVNULL,
                capture_output=True,timeout=650)
            if measured.returncode or len(measured.stdout)>16384:raise ValueError("bounded_inference_failed")
            report.update(json.loads(measured.stdout.splitlines()[-1]))
        result=report["cases"];report["status"]="measured"
        report["accepted"]=len(result)==10 and all(r["passed"] and r["seconds"]<=75 for r in result) and report["peak_rss_mib"]<=5120
    except (OSError,ValueError,IndexError,subprocess.SubprocessError,zipfile.BadZipFile) as e:
        report["reason"]=str(e) if type(e) is ValueError and str(e) in {
            "evidence_artifact_mismatch","evidence_archive_shape","prior_evidence_missing","public_evidence_changed_or_unavailable",
            "host_capacity_or_weights_unverified","bounded_inference_failed"} else type(e).__name__
    (ROOT/"finance-router-evaluation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("FINANCE_ROUTER="+json.dumps(report),flush=True)
    if not report["accepted"]:raise SystemExit(1)


if __name__=="__main__":
    main()
