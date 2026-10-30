"""Read-only integration check in the existing laptop Ubuntu, using two MOEX history series."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
import os
import pwd
import subprocess
import time


def check(value, message):
    if not value:
        raise ValueError(message)


def status(path):
    try:
        with urlopen('http://127.0.0.1:18157' + path, timeout=4) as res:
            return res.status if path != '/health' or json.load(res) == {'status': 'ok'} else 0
    except HTTPError as err:
        err.close()
        return err.code
    except OSError:
        return 0


def recent_series(market, board, security, today):
    path = f'https://iss.moex.com/iss/history/engines/stock/markets/{market}/boards/{board}/securities/{security}.json'
    params = {'from': (today-timedelta(days=10)).isoformat(), 'till': today.isoformat(),
              'iss.meta': 'off', 'iss.only': 'history', 'history.columns': 'TRADEDATE,SECID,CLOSE,NUMTRADES'}
    query = Request(path + '?' + urlencode(params), headers={'Accept': 'application/json', 'User-Agent': 'AnalystAI-public-research/1'})
    try:
        with urlopen(query, timeout=12) as reply:
            check(urlsplit(reply.geturl()).hostname == 'iss.moex.com', 'unverified_host')
            data = reply.read(256*1024+1)
            check(len(data) <= 256*1024, 'oversized')
            table = json.loads(data)['history']
        check(table['columns'] == ['TRADEDATE','SECID','CLOSE','NUMTRADES'], 'history_schema')
        dates = []
        for day, sid, close, n in table['data']:
            day = date.fromisoformat(day)
            if sid == security and close is not None and close > 0 and n and n > 0 and today-timedelta(days=10) <= day <= today:
                dates.append(day)
        check(bool(dates), 'no_traded_close_in_window')
        return {'security':security, 'status':'observed', 'latest_traded_day':max(dates).isoformat(), 'traded_days':len(set(dates))}
    except HTTPError as err:
        err.close()
        return {'security':security, 'status':'http_'+str(err.code)}
    except (OSError, URLError, ValueError, KeyError, TypeError) as err:
        return {'security':security, 'status':type(err).__name__}


if __name__ == '__main__':
    check(os.geteuid()!=0 and pwd.getpwuid(os.geteuid()).pw_name=='analyst-ai', 'unprivileged guest required')
    check(Path('/etc/analyst-home-stage').read_text().strip()=='analyst-home-public-stage-1'
          and not Path('/etc/analyst-protected-home').exists(), 'unexpected distribution')
    check(Path('/proc/1/comm').read_text().strip()=='systemd' and 'microsoft' in os.uname().release.lower(), 'not systemd in WSL')
    for _ in range(40):
        if status('/health')==200:
            break
        time.sleep(1)
    units=['analyst-ai-owner.service','analyst-local-research.service']
    active={unit:subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True,timeout=8).stdout.strip() for unit in units}
    check(all(state=='active' for state in active.values()), 'Linux service inactive')
    health, me=status('/health'),status('/me')
    check((health,me)==(200,401),'local application boundary')
    today=datetime.now(timezone(timedelta(hours=3))).date()
    rows=[recent_series('shares','TQBR','SBER',today), recent_series('bonds','TQOB','SU26238RMFS4',today)]
    print('HOME_LINUX_NOW='+json.dumps({'systemd':'active','services':active,'health':health,'anonymous':me,
          'observed_utc':datetime.now(timezone.utc).isoformat(),'market':rows,'public_only':True}),flush=True)
