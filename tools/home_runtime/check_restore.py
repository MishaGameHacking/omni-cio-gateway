"""Exercise online backup, key restoration and password sessions on the credential-free Lenovo guest."""
from contextlib import closing
import json
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile

from cryptography.fernet import Fernet, InvalidToken
from checked_auth import process, req
from checked_backup import snapshot


def need(ok, message):
    if not ok:
        raise ValueError(message)


def run():
    need(os.geteuid() != 0 and Path('/etc/analyst-home-stage').read_text().strip() == 'analyst-home-public-stage-1'
         and not Path('/etc/analyst-protected-home').exists(), 'wrong_guest')
    with tempfile.TemporaryDirectory(prefix='analyst-restore-check-') as tmp:
        work = Path(tmp)
        original, restored = work/'original.sqlite', work/'restored.sqlite'
        config = work/'restore.key'
        key = Fernet.generate_key()
        subject = 'restore-check-' + secrets.token_hex(12)
        password, bootstrap = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        nonce = secrets.token_bytes(32)
        base = {'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','BACKEND_PUBLIC_URL':'https://restore-check.invalid',
                'ANALYST_OWNER_TELEGRAM_SUB':subject,'ANALYSIS_SCHEDULER_ENABLED':'false',
                'AI_EXTERNAL_PROCESSING_APPROVED':'false','PYTHONDONTWRITEBYTECODE':'1'}
        with process({**base,'DATABASE_PATH':str(original),'FERNET_KEY':key.decode(),
                      'ANALYST_OWNER_BOOTSTRAP_SECRET':bootstrap}) as port:
            code, grant = req(port,'/auth/owner/setup',{'password':password,'device_name':'restore-check'},
                              {'X-Owner-Bootstrap':bootstrap})
            need(code == 200 and grant.get('access_token'), 'setup_failed')
            headers = {'Authorization':'Bearer '+grant['access_token']}
            need(req(port,'/me',headers=headers)[0] == 200, 'source_session_failed')
            with closing(sqlite3.connect(original)) as writer:
                need(writer.execute('PRAGMA journal_mode=WAL').fetchone() == ('wal',), 'wal_missing')
                writer.execute('CREATE TABLE restore_witness (id INTEGER PRIMARY KEY, envelope BLOB NOT NULL)')
                writer.execute('INSERT INTO restore_witness VALUES (1, ?)', (Fernet(key).encrypt(nonce),))
                writer.commit()
                writer.execute('INSERT INTO restore_witness VALUES (2, ?)', (b'uncommitted',))
                snapshot(original, restored)
                writer.rollback()
            with os.fdopen(os.open(config,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as f:
                f.write(key)
        # The second process sees only the restored database path and the separately recovered key.
        original.unlink()
        recovered_key = config.read_bytes()
        with closing(sqlite3.connect(restored.as_uri()+'?mode=ro',uri=True)) as db:
            need(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'integrity_failed')
            need(db.execute('PRAGMA foreign_key_check').fetchone() is None, 'foreign_keys_failed')
            rows = db.execute('SELECT id,envelope FROM restore_witness ORDER BY id').fetchall()
            need(len(rows)==1 and rows[0][0]==1, 'partial_transaction_in_snapshot')
            need(Fernet(recovered_key).decrypt(rows[0][1]) == nonce, 'key_pair_failed')
            try:
                Fernet(Fernet.generate_key()).decrypt(rows[0][1])
            except InvalidToken:
                pass
            else:
                raise ValueError('wrong_key_accepted')
        with process({**base,'DATABASE_PATH':str(restored),'FERNET_KEY':recovered_key.decode()}) as port:
            code, me = req(port,'/me',headers=headers)
            need(code == 200 and str(me.get('telegram_id')) == subject, 'restored_session_failed')
            login, token = req(port,'/auth/owner/login',{'password':password,'device_name':'restore-check'})
            need(login == 200 and token.get('access_token'), 'restored_login_failed')
            need(req(port,'/me')[0] == 401, 'anonymous_accepted')
    return {'sqlite':'ok','foreign_keys':'ok','uncommitted_row_excluded':True,'key_pair_verified':True,
            'wrong_key_rejected':True,'existing_session':200,'password_login':200,'anonymous_me':401,
            'test_files_removed':not work.exists(),'personal_data':False,'broker_calls':0}


if __name__=='__main__':
    try:
        print('HOME_RESTORE_REHEARSAL='+json.dumps(run()),flush=True)
    except Exception as e:
        code=str(e) if isinstance(e,ValueError) and str(e).isidentifier() else type(e).__name__
        print('HOME_RESTORE_ERROR='+code,flush=True)
        raise SystemExit(1)
