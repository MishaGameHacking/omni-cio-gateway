import hashlib, json, os, sqlite3, subprocess
from pathlib import Path


def run():
    failed = dict(status='blocked', sent=False, completed=False, user_messages=0,
                  assistant_messages=0, answer_present=False)
    try:
        if os.getuid() != 0:
            return failed
        STAGING['verify_sources'](ENVELOPE['payload']['source_sha256'])
        expected = ENVELOPE['payload']['runtime_sha256']
        names = {'investment_chat_policy.py', 'osint_api.py', 'osint_read.py', 'osint_retention.py', 'osint_store.py', 'osint_worker.py', 'volume_chat.py', 'volume_explanations.py'}
        if set(expected) != names:
            return failed
        for name, digest in expected.items():
            if hashlib.sha256(STAGING['read_regular'](Path('/opt/analyst-ai/backend') / name)).hexdigest() != digest:
                return failed
        settings = STAGING['parse_environment'](STAGING['configuration_snapshot']()[0])
        database = Path('/var/lib/analyst-ai/backend.db')
        if Path(settings.get('DATABASE_PATH', str(database))) != database:
            return failed
        pid = subprocess.run(['systemctl', 'show', 'analyst-ai-owner.service', '--property=MainPID', '--value'],
                             capture_output=True, text=True, check=True, timeout=10).stdout.strip()
        if not pid.isdigit() or int(pid) <= 1:
            return failed
        entries = Path('/proc/' + pid + '/environ').read_bytes().split(b'\0')
        env = {k.decode(): v.decode() for k, v in (x.split(b'=', 1) for x in entries if x)}
        argv = Path('/proc/' + pid + '/cmdline').read_bytes().split(b'\0')
        interpreter = Path(argv[0].decode())
        if not str(interpreter).startswith('/opt/analyst-ai/') or not interpreter.is_file():
            return failed
        if not interpreter.name.startswith('python'):
            interpreter = interpreter.with_name('python')
        child = '''import sys,json,time
from contextlib import closing
sys.path.insert(0,'/opt/analyst-ai/backend')
import app,volume_chat as chat,volume_jobs as jobs
from fastapi import BackgroundTasks
with closing(app.connect()) as db:
 user=db.execute('SELECT u.* FROM users u JOIN installation_owner o ON o.telegram_sub=u.telegram_sub WHERE o.singleton=1').fetchone()
if user is None:raise RuntimeError('owner_missing')
core={}
exec(compile(CORE_SOURCE,'bounded-chat-verification','exec'),core)
class Api:
 def estimate(self,text,thread):
  return chat.estimate(chat.Estimate(text=text,context=chat.Context(mode='general'),tier='auto',thread_id=thread),user=user)
 def thread(self,request):
  return chat.create_thread(chat.ThreadCreate(request_id=request,title='Проверка чата версии 56'),user=user)['thread_id']
 def send(self,thread,text,request,quote):
  payload=chat.MessageCreate(request_id=request,text=text,context=chat.Context(mode='general'),tier='auto',
    max_cost_micro_rub=quote['cost_ceiling_micro_rub'],expected_route_id=quote['route_id'])
  return chat.send_message(thread,payload,BackgroundTasks(),user=user)['job_id']
 def run(self,job):
  jobs.run_job(job)
  deadline=time.monotonic()+35
  while self.state(job) in {'queued','running'} and time.monotonic()<deadline:time.sleep(1)
 def state(self,job):return jobs.get_job(int(user['id']),job)['state']
 def messages(self,thread):return chat.messages(thread,user=user)['items']
print(json.dumps(core['verify'](Api(),REQUEST_ID)))
'''
        prefix = 'CORE_SOURCE=' + repr(ENVELOPE['payload']['verified_core']) + '\nREQUEST_ID=' + repr(ENVELOPE['payload']['request_id']) + '\n'
        failed['status'] = 'unconfirmed'
        result = subprocess.run([str(interpreter), '-c', prefix + child], env=env,
                                capture_output=True, text=True, timeout=240)
        if result.returncode != 0 or len(result.stdout) > 4096:
            return failed
        value = json.loads(result.stdout)
        if set(value) != set(failed):
            return failed
        return value
    except BaseException:
        return failed


if __name__ == '__main__':
    print(json.dumps(run()), flush=True)
