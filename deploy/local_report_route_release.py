"""Connect the verified isolated model to existing public-report ingestion only."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shlex

import gpt6_protocol_release as core

BASE = "68e0fb73feddf178c29d990633edae42aa7adda3"
SOURCE = "853090e11dcefef693366159c97316e55045c4c9"
TEST_RUN = "41088491538"
MODULES = frozenset({"local_research.py", "osint_worker.py"})
BASE_UPDATES = {"ai_guarded_client.py":"74624ef4b36a841584496b9234c144648c407035",
                "decision_cycle.py":"f432496fe0eed0302e38ddd90a582708eeea4063"}
MODEL_SHA = "0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0"
DROPIN = Path("/etc/systemd/system/analyst-ai-owner.service.d/79-local-research.conf")
SETTING = b"[Service]\nEnvironment=LOCAL_RESEARCH_ENABLED=true\n"
WORKER_RECEIPT = Path("/opt/analyst-local-ai/activation-receipt.json")


def check_worker(receipt):
    result=receipt.get("smoke",{})
    core.need(receipt.get("status")=="local_worker_active" and receipt.get("server_id")==9417611
              and receipt.get("source_commit")==SOURCE and receipt.get("model_sha256")==MODEL_SHA
              and receipt.get("model_network_allowed") is False and receipt.get("model_broker_credentials") is False
              and result.get("status")=="source_excerpt_selection" and result.get("trade_permission") is False
              and result.get("model_sha256")==MODEL_SHA, "qualified_local_worker_required")


@contextmanager
def route_control(path, reload_units):
    parent=path.parent
    core.need(parent.parent.resolve(strict=True)==parent.parent,"unsafe_unit_parent")
    if not parent.exists() and not parent.is_symlink():
        parent.mkdir(mode=0o755)
    core.need(parent.is_dir() and not parent.is_symlink() and parent.resolve(strict=True)==parent
              and parent.stat().st_uid==os.getuid() and parent.stat().st_mode&0o022==0,"unsafe_unit_directory")
    core.need(not path.exists() and not path.is_symlink(),"local_route_already_configured")
    with path.open("xb") as stream:
        os.fchmod(stream.fileno(),0o644)
        stream.write(SETTING)
    try:
        reload_units()
        yield
    except BaseException:
        core.need(core.read_regular(path)==SETTING,"local_route_changed_during_rollback")
        path.unlink()
        reload_units()
        raise


def run(envelope):
    bundle=envelope.get("payload",{})
    core.need(bundle.get("source_commit")==SOURCE and bundle.get("run_id")==TEST_RUN
              and bundle.get("base_commit")==BASE and set(bundle.get("files",{}))==MODULES,
              "exact_local_report_release_required")
    core.need(WORKER_RECEIPT.stat().st_uid==0 and WORKER_RECEIPT.stat().st_mode&0o022==0,"unsafe_model_receipt")
    check_worker(json.loads(core.read_regular(WORKER_RECEIPT)))
    core.need(core.systemctl("is-active","analyst-local-research.service")=="active", "local_worker_not_running")
    # An EnvironmentFile or final UnsetEnvironment can override Environment=.
    env_file=core.read_regular(core.CONFIGURATION)
    core.need(not any(line.lstrip().startswith(b"LOCAL_RESEARCH_ENABLED=") for line in env_file.splitlines()),
              "owner_local_route_override_exists")
    original=core.activated_services
    @contextmanager
    def services_and_route():
        with route_control(DROPIN,lambda:core.systemctl("daemon-reload")):
            with original():
                unset=shlex.split(core.systemctl("show","analyst-ai-owner.service","--property=UnsetEnvironment","--value"))
                core.need(not any(item.split("=",1)[0]=="LOCAL_RESEARCH_ENABLED" for item in unset),"local_route_overridden")
                # Inspect the one public feature flag, never log any service environment.
                pid=core.systemctl("show","analyst-ai-owner.service","--property=MainPID","--value")
                core.need(re.fullmatch(r"[1-9][0-9]*",pid) is not None,"owner_process_missing")
                with Path("/proc",pid,"environ").open("rb") as stream:
                    raw=stream.read(1024**2+1)
                core.need(len(raw)<=1024**2 and [item for item in raw.split(b"\0") if item.startswith(b"LOCAL_RESEARCH_ENABLED=")]
                          ==[b"LOCAL_RESEARCH_ENABLED=true"],"local_route_not_effective")
                del raw
                yield
    old_base,old_modules,old_blobs=core.BASE,core.MODULES,core.BASELINE_BLOBS
    core.BASE,core.MODULES,core.BASELINE_BLOBS=BASE,MODULES,{**old_blobs,**BASE_UPDATES}
    core.activated_services=services_and_route
    try:
        core.run(envelope)
    finally:
        core.BASE,core.MODULES,core.BASELINE_BLOBS=old_base,old_modules,old_blobs
        core.activated_services=original
    print("LOCAL_RESEARCH_ROUTE="+json.dumps({"source_commit":SOURCE,"status":"enabled",
          "scope":"relevant_public_report_ingestion","trade_permission":False,
          "broker_configuration_changed":False,"external_model_routing_changed":False}),flush=True)


if __name__=="__main__":
    try:
        run(ENVELOPE)
    except Exception as error:
        code=str(error) if re.fullmatch(r"[a-z_]{1,100}",str(error)) else type(error).__name__
        print(json.dumps({"status":"failed","code":code}),flush=True)
        raise SystemExit(1) from None
