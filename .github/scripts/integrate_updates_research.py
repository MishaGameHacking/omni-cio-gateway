"""One-use, pinned source transformation; no release publication or cloud calls."""
from pathlib import Path
import hashlib
import subprocess

ROOT=Path(__file__).resolve().parents[2]
EXPECTED={
 'backend/app.py':'e804a5e65432ea3eb3649bac89680c7be78ba69c',
 'backend/autonomous_ai.py':'3f574fe387f2ad3e70d1645d5f8b80a251f7b859',
 'backend/portfolio_details.py':'94e68d3b0d0859bf14f9165b9ac9bf9c75c4ab8c',
 'app/src/main/java/ru/omnicio/app/MainActivity.kt':'d0b54fbc7c09c4fb83650daee2762d83679590bc',
 'app/src/main/java/ru/omnicio/app/data/backend/AnalystBackendClient.kt':'d06e15996cb4f7677410896ac04421caa4803e16',
 'app/src/main/java/ru/omnicio/app/data/analysis/AnalysisBackendClient.kt':'8a3a062ad91137265db694cf06cb6fb9aa22fbc3',
 'app/src/main/java/ru/omnicio/app/data/portfolio/PortfolioDataClient.kt':'45c67c9f0822dce7613bb49022c161849160bff9',
 'app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioComponents.kt':'871a0483361829640b2651e43fc9aa002c98b7a7',
 'app/src/main/AndroidManifest.xml':'b5cbedb95e29cebd4d617a7b422afca93451854b',
 'app/build.gradle.kts':'668887369178e8163406a7aa9ec6e3ac33241128',
}
source={}
for path,sha in EXPECTED.items():
    data=subprocess.check_output(['git','show','HEAD:'+path],cwd=ROOT)
    actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data,usedforsecurity=False).hexdigest()
    if actual!=sha: raise RuntimeError('Source changed: '+path)
    source[path]=data.decode().replace('\r\n','\n')


def replace(path,old,new):
    if source[path].count(old)!=1:
        raise RuntimeError('Anchor mismatch: '+path+' '+repr(old[:90]))
    source[path]=source[path].replace(old,new,1)

p='backend/app.py'
replace(p,'from fastapi import Depends, FastAPI, Header, HTTPException','from fastapi import Depends, FastAPI, Header, HTTPException, Request')
replace(p,'from pydantic import BaseModel','from pydantic import BaseModel\n\ntry:\n    from . import client_updates\nexcept ImportError:\n    import client_updates')
replace(p,'\n\ndef hash_token(value: str)', '\n    client_updates.initialize(connect)\n\n\ndef hash_token(value: str)')
replace(p,'def current_user(authorization:', 'def session_user(authorization:')
replace(p,'\n\n@app.get("/health")', '''

def current_user(request: Request, authorization: str | None = Header(default=None)) -> sqlite3.Row:
    user = session_user(authorization)
    client_updates.enforce(connect, user_id=int(user['id']), authorization=authorization or '', headers=request.headers)
    return user


@app.get("/health")''')
source[p]+='\n\nclient_updates.install_routes(app, connect, session_user)\n'
p='backend/autonomous_ai.py'
replace(p,'logger = logging.getLogger(__name__)', 'try:\n    from . import client_updates\nexcept ImportError:\n    import client_updates\n\nlogger = logging.getLogger(__name__)')
replace(p,'    previous, previous_row = _latest_snapshot(user_id)', '''    if not client_updates.user_can_run(backend.connect, user_id):
        return {'state':'paused', 'reason':'client_update_required', 'tier':'none', 'card_id':None}

    previous, previous_row = _latest_snapshot(user_id)''')
replace(p,'    current_job = CURRENT_JOB.get()', '    client_updates.assert_user_can_run(backend.connect, user_id)\n    current_job = CURRENT_JOB.get()')
replace(p,'        guarded_client = GuardedAIClient(user_id, backend.connect)', '        client_updates.assert_user_can_run(backend.connect, user_id)\n        guarded_client = GuardedAIClient(user_id, backend.connect)')
replace(p,'    _record_run(\n        user_id=user_id,','    client_updates.assert_user_can_run(backend.connect, user_id)\n    _record_run(\n        user_id=user_id,')
replace(p,"        queue.enqueue(int(user['id']))", "        if client_updates.user_can_run(backend.connect, int(user['id'])):\n            queue.enqueue(int(user['id']))")
p='backend/portfolio_details.py'
replace(p,'def record_history(user_id: int, accounts: list[dict], observed: str) -> None:\n', 'def record_history(user_id: int, accounts: list[dict], observed: str) -> None:\n    backend.client_updates.assert_user_can_run(backend.connect, user_id)\n')
p='app/src/main/java/ru/omnicio/app/MainActivity.kt'
replace(p,'@Composable\nprivate fun AnalystAiApp(', '@Composable\nprivate fun AnalystAiAppContent(')
wrapper='''
@Composable
private fun AnalystAiApp(
    authCode: String?, authError: String?, onStartTelegramLogin: () -> Unit,
    onAuthCodeConsumed: () -> Unit, initialScreenshotsBlocked: Boolean,
    onScreenshotsBlockedChange: (Boolean) -> Unit,
) {
    ru.omnicio.app.ui.updates.MandatoryUpdateHost {
        AnalystAiAppContent(authCode, authError, onStartTelegramLogin, onAuthCodeConsumed,
            initialScreenshotsBlocked, onScreenshotsBlockedChange)
    }
}

'''
source[p]+=wrapper
for p in ('app/src/main/java/ru/omnicio/app/data/backend/AnalystBackendClient.kt',
          'app/src/main/java/ru/omnicio/app/data/analysis/AnalysisBackendClient.kt'):
    replace(p,'                setRequestProperty("Accept", "application/json")','                ru.omnicio.app.data.updates.ClientVersion.attach(this)\n                setRequestProperty("Accept", "application/json")')
    replace(p,'            val status = connection.responseCode','            val status = connection.responseCode\n            ru.omnicio.app.data.updates.ClientVersion.observeStatus(status)')
    replace(p,'                status == HttpURLConnection.HTTP_UNAUTHORIZED ||','                status == 426 -> BackendResult.Failure("Обновите Analyst AI, чтобы продолжить.", retryable = true)\n                status == HttpURLConnection.HTTP_UNAUTHORIZED ||')
p='app/src/main/java/ru/omnicio/app/data/portfolio/PortfolioDataClient.kt'
replace(p,'            connection.requestMethod = "GET"','            ru.omnicio.app.data.updates.ClientVersion.attach(connection)\n            connection.requestMethod = "GET"')
replace(p,'            val status = connection.responseCode','            val status = connection.responseCode\n            ru.omnicio.app.data.updates.ClientVersion.observeStatus(status)')
replace(p,'                    401, 403 ->','                    426 -> "Обновите Analyst AI, чтобы продолжить."\n                    401, 403 ->')
replace(p,'status == 429 || status >= 500 || status == 404)', 'status == 429 || status >= 500 || status == 404 || status == 426)')
p='app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioComponents.kt'
replace(p,'                DataRow("Идентификатор", position.id)', '                DataRow("Идентификатор", position.id)\n                ru.omnicio.app.ui.instruments.BrokerInstrumentActions(position.instrumentType, position.ticker, position.isin)')
p='app/src/main/AndroidManifest.xml'
replace(p,'    <uses-permission android:name="android.permission.INTERNET" />', '''    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />
    <uses-permission android:name="android.permission.UPDATE_PACKAGES_WITHOUT_USER_ACTION" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />''')
replace(p,'    </application>', '''        <receiver android:name=".data.updates.InstallResultReceiver" android:exported="false" />
        <receiver android:name=".data.updates.AppReplacedReceiver" android:exported="false">
            <intent-filter><action android:name="android.intent.action.MY_PACKAGE_REPLACED" /></intent-filter>
        </receiver>
    </application>''')
p='app/build.gradle.kts'
replace(p,'versionCode = 22','versionCode = 23')
replace(p,'versionName = "0.5.1"','versionName = "0.6.0"')
for path,text in source.items():
    (ROOT/path).write_text(text,encoding='utf-8')
print('Integrated mandatory update gate, authenticated server pause and broker navigation. Not deployed.')
