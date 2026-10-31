"""One reversible recovery boot of the owner's existing migration source VM."""
import json
import os
import time
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def main():
    assert os.environ['GITHUB_REPOSITORY']=='MishaGameHacking/omni-cio-gateway'
    assert os.environ['GITHUB_REF']=='refs/heads/codex/lenovo-transfer-2026-10-31'
    assert os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_RUN_ATTEMPT']=='1'
    token=os.environ.pop('TIMEWEB_CLOUD_TOKEN')
    opener=urllib.request.build_opener(NoRedirect())
    def call(method,path,body=None):
        request=urllib.request.Request('https://api.timeweb.cloud/api/v1'+path,method=method,
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json'},
            data=None if body is None else json.dumps(body).encode())
        try:
            with opener.open(request,timeout=45) as response:
                raw=response.read(1024*1024+1)
                assert len(raw)<=1024*1024
                return response.status,json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            # The previous request was rejected with 400 before any state change.
            # Capture only provider validation fields for this fixed boot-mode request.
            if method=='POST' and exc.code==400:
                data=json.loads(exc.read(16384))
                print(json.dumps({'provider_validation':{k:data[k] for k in
                    ('error_code','error','message','errors','response_id') if k in data}}),flush=True)
            raise
    def server():
        status,data=call('GET','/servers/9417611');s=data['server']
        ips=[ip.get('ip') for net in s.get('networks',[]) if net.get('type')=='public'
             for ip in net.get('ips',[]) if ip.get('type')=='ipv4']
        assert status==200 and s.get('id')==9417611 and s.get('project_id')==2941515
        assert s.get('name')=='Analyst AI runtime 20261025' and s.get('availability_zone')=='ams-1'
        assert ips==['83.217.195.29']
        return s
    before=server()
    assert before.get('status')=='on' and before.get('boot_mode')=='std'
    print(json.dumps({'phase':'before','server_id':9417611,'status':before.get('status'),'boot_mode':before.get('boot_mode')}),flush=True)
    status,_=call('POST','/servers/9417611/boot-mode',{'boot_mode':'recovery_disk'})
    print(json.dumps({'phase':'requested_once','http_status':status,'disk_reinstallation':False}),flush=True)
    for _ in range(18):
        time.sleep(10)
        current=server()
        print(json.dumps({'phase':'observe','status':current.get('status'),'boot_mode':current.get('boot_mode')}),flush=True)
        if current.get('status')=='on' and current.get('boot_mode')=='cd':
            return
    raise RuntimeError('recovery_boot_not_observed')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        result={'status':'failed','error_type':type(exc).__name__}
        if isinstance(exc,urllib.error.HTTPError):result['http_status']=exc.code
        print(json.dumps(result),flush=True)
        raise SystemExit(1)
