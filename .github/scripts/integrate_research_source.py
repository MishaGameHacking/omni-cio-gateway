"""One-use source integration; no cloud operations or blocked planner upload."""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
EXPECTED={
    'backend/app.py':'e804a5e65432ea3eb3649bac89680c7be78ba69c',
    'app/src/main/java/ru/omnicio/app/ui/analysis/AnalysisScreens.kt':'e80f79d14db1408ab2a59e09c98f8151038aa9e0',
    'app/src/debug/java/ru/omnicio/app/ProfileUiProbeActivity.kt':'2e6ea4d4372c378dc47410cd3e2ac4d6d70ee89c',
}


def read(path): return (ROOT/path).read_text(encoding='utf-8')
def write(path,text): (ROOT/path).write_text(text,encoding='utf-8',newline='\n')
def replace_once(path,before,after):
    text=read(path)
    if text.count(before)!=1: raise RuntimeError('Source anchor changed: '+path)
    write(path,text.replace(before,after,1))

for path,expected in EXPECTED.items():
    data=subprocess.run(['git','show','HEAD:'+path],cwd=ROOT,capture_output=True,check=True,timeout=15).stdout
    actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data,usedforsecurity=False).hexdigest()
    if actual!=expected: raise RuntimeError('Pinned committed source changed: '+path)
    if read(path)!=data.decode('utf-8').replace('\r\n','\n'):
        raise RuntimeError('Checkout differs from committed source: '+path)

app=read('backend/app.py').rstrip()+'''

try:
    from .portfolio_research import router as portfolio_research_router
except ImportError:
    from portfolio_research import router as portfolio_research_router
app.include_router(portfolio_research_router)
'''
ast.parse(app)
write('backend/app.py',app)
path='app/src/main/java/ru/omnicio/app/ui/analysis/AnalysisScreens.kt'
text=read(path)
start=text.index('fun IdeasScreen(')
anchor='            when (val current = state) {'
pos=text.index(anchor,start)
text=text[:pos]+'''            item {
                ru.omnicio.app.ui.research.PortfolioResearchPanel(accessToken)
            }

'''+text[pos:]
write(path,text)
replace_once('app/src/debug/java/ru/omnicio/app/ProfileUiProbeActivity.kt',
             '        val checksPassed = runRefreshStateRegressionChecks()',
             '        check(runInstrumentLinkRegressions() == 15)\n        val checksPassed = runRefreshStateRegressionChecks()')
replace_once('backend/tests/test_portfolio_research_integration.py',
             'tempfile.TemporaryDirectory(ignore_cleanup_errors=True)', 'tempfile.TemporaryDirectory()')
p='backend/research_store.py';text=read(p);a=text.index('def latest_verified(')
text=text[:a]+'''def latest_verified(connect, kind: str, subject: str, at: datetime) -> dict | None:
    candidates = [raw for raw in records(connect, kind, subject)
                  if stamp(raw['source']['published_at']) <= at and stamp(raw['source']['checked_at']) <= at]
    latest = max(candidates, key=lambda item: (stamp(item['source']['published_at']), stamp(item['source']['checked_at'])), default=None)
    return latest if latest and Source(**latest['source']).valid(at) else None
'''
ast.parse(text);write(p,text)
print('Research router/panel/15 link regressions connected; no deployment, APK release or planner substitution.')
