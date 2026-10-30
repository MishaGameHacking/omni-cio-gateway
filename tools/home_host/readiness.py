"""One bounded admission probe within the owner's WSL, with no account credentials."""
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from concurrent.futures import ThreadPoolExecutor


def public_response(host, path, context=None, post=False):
    connection = http.client.HTTPSConnection(host, timeout=10, context=context)
    try:
        body = '{}' if post else None
        connection.request('POST' if post else 'GET', path, body=body,
                           headers={'Content-Type': 'application/json'} if post else {})
        response = connection.getresponse()
        return response.status, response.read(128 * 1024)
    except (OSError, http.client.HTTPException) as error:
        return type(error).__name__, b''
    finally:
        connection.close()


def bank(certificate):
    der = ssl.PEM_cert_to_DER_cert(certificate)
    if hashlib.sha256(der).hexdigest() != 'd26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31':
        raise ValueError('unexpected broker trust anchor')
    context = ssl.create_default_context()
    context.load_verify_locations(cadata=certificate)
    status, _ = public_response('invest-public-api.tbank.ru',
                                '/rest/tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts',
                                context=context, post=True)
    return status


def market():
    status, body = public_response('iss.moex.com', '/iss/engines/stock/markets/shares/boards/TQBR/securities/SBER.json'
                                   '?iss.meta=off&iss.only=securities&securities.columns=SECID,BOARDID')
    try:
        table = json.loads(body)['securities']
        check = any(dict(zip(table['columns'], row)) == {'SECID': 'SBER', 'BOARDID': 'TQBR'} for row in table['data'])
    except (ValueError, KeyError, TypeError):
        check = False
    return {'status': status, 'valid_reference': status == 200 and check}


def central_bank():
    status, body = public_response('www.cbr.ru', '/scripts/XML_daily.asp')
    try:
        root = ET.fromstring(body)
        check = root.tag == 'ValCurs' and bool(root.attrib.get('Date')) and root.find('Valute') is not None
    except ET.ParseError:
        check = False
    return {'status': status, 'valid_reference': status == 200 and check}


def gpu():
    exe = shutil.which('nvidia-smi') or '/usr/lib/wsl/lib/nvidia-smi'
    try:
        result = subprocess.run([exe, '--query-gpu=name,memory.total,memory.free',
                                 '--format=csv,noheader,nounits'], capture_output=True, timeout=8, text=True)
        if result.returncode == 0:
            name, total, free = result.stdout.splitlines()[0].split(',')
            return {'name': name.strip(), 'total_mib': int(total), 'free_mib': int(free) if free.strip().isdigit() else None}
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
        pass
    return None


def database_smoke():
    with tempfile.TemporaryDirectory(prefix='analyst-host-wal-') as directory:
        path = str(Path(directory) / 'probe.sqlite')
        with sqlite3.connect(path) as db:
            wal = db.execute('pragma journal_mode=wal').fetchone()[0] == 'wal'
            db.execute('create table probe(id integer primary key)')
            db.execute('insert into probe values (1)')
        db.close()
        with sqlite3.connect(path) as restored:
            ok = restored.execute('select id from probe').fetchall() == [(1,)]
        restored.close()
        return wal and ok


if __name__ == '__main__':
    pem = base64.b64decode(sys.argv[1], validate=True).decode('ascii')
    memory = {k[:-1]: int(v) // 1024 for k, v, *_ in
              (line.split() for line in Path('/proc/meminfo').read_text().splitlines()) if k in {'MemTotal:', 'MemAvailable:'}}
    cached = Path('/home/analyst-ci/.cache/analyst-local-research/'
                  '0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0.litertlm')
    try:
        available_weights = cached.is_file() and cached.stat().st_size == 3659530240
    except OSError:
        available_weights = None
    with ThreadPoolExecutor(max_workers=3) as pool:
        broker = pool.submit(bank, pem)
        moex = pool.submit(market)
        cbr = pool.submit(central_bank)
        report = {'default_root': os.geteuid() == 0, 'mem_mib': memory,
                  'pid1': Path('/proc/1/comm').read_text().strip(), 'gpu': gpu(),
                  'cpu_threads': len(os.sched_getaffinity(0)), 'default_path_has_codex': bool(shutil.which('codex')),
                  'model_file_size_matches': available_weights, 'sqlite_wal': database_smoke(),
                  'broker_http_unauthenticated': broker.result(), 'moex': moex.result(), 'cbr': cbr.result()}
    print(json.dumps(report))
