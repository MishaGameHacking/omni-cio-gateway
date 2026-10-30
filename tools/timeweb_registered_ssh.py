"""Use the pinned transport, verify its temporary key assignment and bound guest propagation time."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

from observe_ssh_handshake import TRANSPORT_BLOB, category

SERVER=9417611


def assignment(document, identifier, public):
    row=document.get("ssh_key",{})
    if (type(row.get("id")) is not int or row["id"]!=identifier or not isinstance(public,str)
            or len(public.split())<2 or not isinstance(row.get("body"),str)
            or row["body"].split()[:2]!=public.split()[:2]):
        raise RuntimeError("temporary_key_record_changed")
    used=row.get("used_by")
    if not isinstance(used,list) or len(used)>8:
        raise RuntimeError("temporary_key_assignment_shape_unknown")
    seen=set()
    for entry in used:
        if type(entry) is dict:
            entry=entry.get("server_id",entry.get("id"))
        if isinstance(entry,str) and entry.isascii() and entry.isdigit() and len(entry)<=16:
            entry=int(entry)
        if type(entry) is not int:
            raise RuntimeError("temporary_key_assignment_shape_unknown")
        seen.add(entry)
    if seen-{SERVER}:
        raise RuntimeError("temporary_key_assigned_to_other_resource")
    return seen=={SERVER}


def verified_remote(error_type, state, read, *, run=subprocess.run, pause=time.sleep, clock=time.monotonic):
    deadline=None
    def remote(command, script, *, data=None, timeout=12):
        nonlocal deadline
        if script!="test $(id -u) = 0" or data is not None or timeout!=12:
            raise RuntimeError("unexpected_handshake_scope")
        if deadline is None:
            deadline=clock()+300
        if clock()>=deadline:
            raise RuntimeError("guest_key_propagation_deadline")
        identifier=state.get("id")
        if type(identifier) is not int or identifier<1:
            raise RuntimeError("temporary_key_record_missing")
        status,document=read("GET","/ssh-keys/"+str(identifier))
        if status!=200:
            raise RuntimeError("temporary_key_assignment_unavailable")
        assigned=assignment(document,identifier,state.get("public"))
        if not assigned:
            print('SSH_KEY_PROPAGATION={"assigned_to_target":false,"category":"registry_pending"}',flush=True)
            pause(min(20,max(0,deadline-clock())))
            raise error_type("temporary_key_assignment_pending")
        result=run(command+[script],input=None,capture_output=True,timeout=12)
        kind=category(result.stderr) if result.returncode else "authenticated"
        print("SSH_KEY_PROPAGATION="+json.dumps({"assigned_to_target":True,"category":kind,"exit_code":result.returncode}),flush=True)
        if result.returncode:
            if kind=="host_identity_rejected":
                raise RuntimeError("host_identity_rejected")
            if kind=="authentication_rejected":
                # Registry assignment precedes guest authorization. Keep the same
                # key, the original 12-attempt ceiling and strict host checks.
                pause(min(20,max(0,deadline-clock())))
            raise error_type("remote_command_failed_"+str(result.returncode))
        return result.stdout
    return remote


def main():
    raw=Path(__file__).with_name("owner_plan_transport_20261027.py").read_bytes()
    if hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()!=TRANSPORT_BLOB:
        raise RuntimeError("reviewed_transport_changed")
    import owner_plan_transport_20261027 as transport
    state={}
    original=transport.access.request
    def track(token,method,path,data=None,**options):
        response=original(token,method,path,data,**options)
        if method=="POST" and path=="/ssh-keys":
            row=response.get("ssh_key",response.get("ssh-key",{}))
            state.update(id=row.get("id"),public=(data or {}).get("body"))
        return response
    transport.access.request=track
    transport.p.remote=verified_remote(transport.p.ProbeError,state,transport.api)
    transport.main()


if __name__=="__main__":
    main()
