"""Build and check N02/N04 source only on the existing Timeweb host."""
import hashlib
import urllib.request

url='https://raw.githubusercontent.com/MishaGameHacking/omni-cio-gateway/8f4567419dd991eda49ebf3b637c08f5a10e46fd/deploy/plan-20261027/operation.py'
with urllib.request.urlopen(url,timeout=20) as response:
    raw=response.read(65537)
if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!='78a363c5b1227d87a8b08586fe391295954f9a94be8bd130357a94a59c881cd3':
    raise RuntimeError('verified_candidate_driver_mismatch')
script=raw.decode()
# Preserve the first failed test collection. Correct only its import order;
# production imports/tests and assertions are not weakened.
old='from backend import volume_market as market'
if script.count(old)!=1:raise RuntimeError('test_import_patch_mismatch')
script=script.replace(old,'from backend import app as backend\nfrom backend import volume_market as market')
# The successful current-day HTTPS response is already preserved. Do not repeat
# the owner-authenticated request merely because the test driver is corrected.
start=script.index('# Reuse the exact already-inspected')
end=script.index("lock = open('/var/lock/analyst-ai-plan-development.lock'",start)
script=script[:start]+'''probe=json.loads((ROOT/'plan-audit-40465301512/calendar-diagnostic.json').read_text())
if probe.get('calendar',{}).get('http_status')!=200 or probe['calendar'].get('exchange_count')!=148:
    raise RuntimeError('preserved_calendar_correction_evidence_missing')
print('REUSED_CALENDAR_PROBE_RUN=40465301512',flush=True)
'''+script[end:]
insertion=r'''
additional_files={
 'backend/portfolio_accounting.py':('portfolio_accounting.py','719b349fe033e354b560d44234579ea5dd9826ec3a13c66c7739cf8d8e63ceef'),
 'backend/tests/test_portfolio_accounting.py':('test_portfolio_accounting.py','493930a9685845a94043c0c40d77c808d191f5942d1813c65ba744d54c01ea26'),
}
for destination,(name,expected) in additional_files.items():
    if (work/destination).exists():raise RuntimeError('new_accounting_source_already_exists')
    source_url='https://raw.githubusercontent.com/MishaGameHacking/omni-cio-gateway/'+ENVELOPE['github_sha']+'/deploy/plan-20261027/'+name
    with urllib.request.urlopen(source_url,timeout=20) as response:
        content=response.read(131073)
    if len(content)>131072 or hashlib.sha256(content).hexdigest()!=expected:raise RuntimeError('accounting_source_transport_mismatch')
    (work/destination).write_bytes(content)
'''
marker='# Both baseline and candidate are tested with the same new regression, in copies.'
if script.count(marker)!=1:raise RuntimeError('candidate_extension_marker_missing')
script=script.replace(marker,insertion+'\n'+marker)
marker="check('full-backend',work,"
if script.count(marker)!=1:raise RuntimeError('targeted_accounting_marker_missing')
script=script.replace(marker,"check('accounting-regressions',work,['-m','pytest','backend/tests/test_portfolio_accounting.py','-q','--junitxml='+str(evidence/'accounting.xml')])\n"+marker)
script=script.replace("'full_backend':results(evidence/'full.xml')","'accounting':results(evidence/'accounting.xml'),'full_backend':results(evidence/'full.xml')")
script=script.replace("for p in [relative,'backend/tests/test_calendar_start_date.py']","for p in [relative,'backend/tests/test_calendar_start_date.py',*additional_files]")
exec(compile(script,'timeweb-n02-n04-candidate-driver','exec'),{'ENVELOPE':ENVELOPE,'__name__':'__main__'})
