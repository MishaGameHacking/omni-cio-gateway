"""Read-only operational evidence and Android tool inventory on Timeweb.

No app imports, credential decryption, broker calls, DB writes, installation,
service restart or build. Only bounded metadata and aggregate version claims.
"""
from contextlib import closing
import datetime
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request

ROOT=Path('/var/lib/analyst-ai-build/development')
DEPLOY=ROOT/'runtime-layer-deployment-40473816699/deployment.json'
lock=open('/var/lock/analyst-ai-plan-development.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
receipt=json.loads(DEPLOY.read_text())
if receipt.get('status')!='passed' or receipt.get('phase')!='deployed':raise RuntimeError('verified_deployment_missing')
for name,row in receipt['files'].items():
 path=Path('/opt/analyst-ai/backend')/name
 if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=row['new']['sha256']:
  raise RuntimeError('runtime_source_changed_since_delivery')
now=int(time.time())
report={'schema':1,'server_id':9417611,'run_id':ENVELOPE['run_id'],'github_sha':ENVELOPE['github_sha'],
 'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'application_imported':False,'runtime_changed':False,'database_mode':'ro/query_only',
 'broker_requested':False,'paid_ai_requested':False,'deployed_hashes_match':True}
expected_backend={"ai_budget.py":{"bytes":11358,"sha256":"7fa2a785f26e1227252c8785f1e12029192b093ad2809a020f1cd647f7bcf947"},"ai_guarded_client.py":{"bytes":16889,"sha256":"349f89534b0e562aaf84a6bdbce9db28db5a9719cd3682ba3bf23daaec2d59ae"},"ai_jobs.py":{"bytes":10904,"sha256":"38205417d64d14847620a4f45a2a20ad1f0d7cd5bab512c1feca8bfd53a45194"},"ai_policy.py":{"bytes":5269,"sha256":"44cfdcdf2d862a681287f2a20dc387051fe227dcb2c68d5d18247d349a714fa9"},"ai_route_catalog.py":{"bytes":4865,"sha256":"a88981df52942a4c08fd60018aabf333ceaa85e8c4db8e79930f75b5e9e5a3c9"},"allocation_plan.py":{"bytes":14103,"sha256":"90f3396a685ef9968c30fa5c5c1f7acfb9983825993d4c0b9b68710ce07fd4ad"},"analysis_engine.py":{"bytes":11660,"sha256":"2700fdde343666a6e2441a943fb11dac2a5ea3906c04520b90c2b2721bde22e1"},"android_runtime_contract.py":{"bytes":3142,"sha256":"1ed9a56769d308c9f5457fa383517a80965cd474dff8851e16a85390954335c2"},"app.py":{"bytes":29265,"sha256":"33950c712e6442ce00af8de84f1e2c174c75d140728c1c093f00d717f5948c40"},"application_hierarchy.py":{"bytes":6850,"sha256":"cabb4e0c1607e9a5d76ff4ef82d1eb1ba2f218435c4c43283a2ca6e96a79b424"},"automation_ui_evidence.py":{"bytes":8099,"sha256":"4a06b75ba342d80f7bcee6d0fbbb985d6562d390deb147438c04c48be91ae35c"},"autonomous_ai.py":{"bytes":54368,"sha256":"09d0f79dc25c6e0a21af0f4aad81845ac11333f5338bb899666535ef990d2e53"},"autonomous_controller.py":{"bytes":36417,"sha256":"1930c63e307d45b86a68fad0506a34b069a5fdf68cef99a6ed1e8d17588fb56e"},"background_dispatch.py":{"bytes":9212,"sha256":"eefe68f2ff91f7be346fc8026ad4e15296bc197d73379e5c7158ed295e7add25"},"bounded_ai_response.py":{"bytes":4723,"sha256":"95d51fa2f6a2c6190ae572a2c88cf13ca2803af999d9a77ddfd908c6c397db14"},"broker_connections.py":{"bytes":6568,"sha256":"d0e4079f030ccc466da0b5224478a75841c02cfbf17a1151286a5f56845f5651"},"client_compatibility.py":{"bytes":2245,"sha256":"cf585f4a740198325e47166b318f12c41017491e34edb27c5511c53790a7d8e9"},"client_diagnostics.py":{"bytes":8863,"sha256":"6316faa45abc793adb16fb6d8b42993e2c778e9411e31ed525c1742c379e1bc0"},"client_updates.py":{"bytes":13743,"sha256":"79c1f8670cc61f94f917c9ad4b6e394f1430a08b61b8ef87216624fec12b9184"},"credit_evidence.py":{"bytes":15694,"sha256":"96af887aa723e8e74e7d037f4785da532d6aa16ef6916eaf099c0ba847b4fd80"},"event_monitor.py":{"bytes":13793,"sha256":"68cf1edfba5226f1f866c9dceb904787e0b68b9808329b08e90418face9573d4"},"evidence_history.py":{"bytes":3273,"sha256":"e9f16324ac661abfcd4c8ee6e6deaa7b7748245891e8c5c5c15d02c63a28ce12"},"evidence_order.py":{"bytes":3041,"sha256":"46368a7a78a2fbfc55198e222795abe977c490c3f07703ddcb8f4afd2f45f2d7"},"evidence_revision.py":{"bytes":3100,"sha256":"7fa8f33904ac8f363f7eaddbba29ff9942ce7e1e4ad958ad23fc1185852876c4"},"installation_evidence.py":{"bytes":8652,"sha256":"04e13002c8b5e5046a86e3a5e8de1edc354888eb581202f010ee992563468c3c"},"investment_chat_policy.py":{"bytes":9474,"sha256":"65130e31014142a968546beeebd58d93422c7f7ff027b34f587a890002f529f2"},"investment_links.py":{"bytes":1418,"sha256":"55d7d36ab4847509fde4e1e46dcc6811b215d2b07ddbb5c5ada22a7ce4dd0688"},"market_schedule.py":{"bytes":8984,"sha256":"184f3f8a4aca281579a6768e442a357b02bc8620f813a3e6f162a75ed4982498"},"model_json_limits.py":{"bytes":2324,"sha256":"2cd9d1f126965ee947b25ee0a5fb82ec5e43b018c5040cd6871b76ca9af7a1ae"},"monitoring_access.py":{"bytes":1772,"sha256":"9c6156d1452db85c8adad877e8d9ffe336f499cb44752174e9761a01881fa6cc"},"operations_ledger.py":{"bytes":20220,"sha256":"c6874e515e2e526328cdbc3f1f8741c788004765f76f22f057518e7fad90e414"},"owner_access.py":{"bytes":6178,"sha256":"5bd31e342cea7dbbf1814874a8702140d5669534cd2948c33982b319beee78d3"},"owner_app.py":{"bytes":5798,"sha256":"09dda073a447e12f742e4540945e1695be14ce943cf9471189cf4ca80c3d729b"},"paper_execution.py":{"bytes":28296,"sha256":"c219c230ab1783c1d5a4242017dd2320fc9341cbdfc8d368445646cc4cd86414"},"portfolio_accounting.py":{"bytes":13415,"sha256":"719b349fe033e354b560d44234579ea5dd9826ec3a13c66c7739cf8d8e63ceef"},"portfolio_details.py":{"bytes":29229,"sha256":"d677d2d74f1761b53c507ae716da29d7312f7c526e99a873686008e6ba986a57"},"portfolio_mandate.py":{"bytes":4743,"sha256":"a8647933e107a3e1427438999b266869ae9be456786710cea56f997d57459c78"},"portfolio_research.py":{"bytes":20571,"sha256":"6f657312995316d157424319e75ed876c9d567f52e7a0d267fc30266fac87b70"},"portfolio_risk.py":{"bytes":23821,"sha256":"b796b20085311a6318436c263abe66068dfe8e75e844e6329beec20cc670ce43"},"portfolio_scenarios.py":{"bytes":7489,"sha256":"64d2a12e69b5d1dd482d2148d222d1f717b4f04ef6a5218da8357d82faf438ec"},"public_sources.py":{"bytes":23399,"sha256":"274849ad97b7e7cf6bd0cf4bdfd4298da04b94464df85b3e6d9333be1ddcc614"},"public_updates_app.py":{"bytes":1219,"sha256":"65223e183ab426c2e9fb7619e97aa321f6a9b9c1e4f72392ee8b4fe056edf0d8"},"purchase_policy.py":{"bytes":12689,"sha256":"53a264d7d091125c759b1d0cbf7d49542be3e27ca44c3661ea56b3d03aec0040"},"release_bytes.py":{"bytes":1807,"sha256":"71de304be624aed78b53966c66c863aef41d6c961c92badea1f399cd07785ac5"},"release_contract.py":{"bytes":5885,"sha256":"dd6bcbf3c3802dd47003657ee13c548270b0e992cb210fdb3bc2727572d4d933"},"release_json.py":{"bytes":4285,"sha256":"04a760b02105322f41d400cbdd6d44a4519c4e8dcd03ffd53fcd6da5fadf6b97"},"release_lock.py":{"bytes":1638,"sha256":"548c06b4d8bcc9323eb5e1d49ef17fe4f8689967c2240fd1710653bcab08ce74"},"release_publication.py":{"bytes":10167,"sha256":"9f083c508dbfc1e34721e6379044d2071c6e0752029f739e7280a9c65cb6a914"},"research_clock.py":{"bytes":3137,"sha256":"267d22a868657d288c89d286ec9007ebf3d01ce25e486f718c5aabbcdf612d70"},"research_import.py":{"bytes":7893,"sha256":"806548c1c80d087c3cefe29f9181678f1257faa29760f02ff60e2f57b8e34e4f"},"research_profile_cache.py":{"bytes":554,"sha256":"20cb8cd5533dd63ae414ea383dfd1221476762e583e21a67b39602cf5bca3d23"},"research_snapshot.py":{"bytes":3527,"sha256":"6971a39d7ba336d3f57b9ec166f61b1687669bc7ec10e982f2473e520da82252"},"research_store.py":{"bytes":9508,"sha256":"703b1a251bf3bbae73b8b82bf7647d19a45f3eb0951887bb9822adcc59d5b874"},"risk_math.py":{"bytes":13842,"sha256":"f2492cbbbb7750099b74c5a0564a497d21fef5ffe413971690fe62fb2d049c5c"},"risk_preview.py":{"bytes":11526,"sha256":"295a41d0495440366c4cef2aa5f89c6bde5a138e63f269ad7b2b1e050927f82c"},"source_observability.py":{"bytes":10906,"sha256":"2aeacae6cbb082f2592b67494b8bf3b5b4ed2c13761c5dc9b13524194f3874c6"},"telegram_browser_app.py":{"bytes":16927,"sha256":"5a1ef0f644948cad8d38b4537b9b5c938582fea79955c143453c797b67c46793"},"telegram_oidc.py":{"bytes":5217,"sha256":"3d7e64b50811b4b1ff70ec2512f1895f493de77932814976e87e0e509322b3a8"},"timeweb_ai.py":{"bytes":9066,"sha256":"e473a8cddb469b3f5b0a4290fb003d94e03ebb8e960de914406e84e24f7c59a3"},"tinvest_portfolio.py":{"bytes":16296,"sha256":"6213499c73fb69b76ddd09a50f4f3a3eb4ac95e42965416d907b201b0711f754"},"volume.py":{"bytes":630,"sha256":"2efb14fb95452af54a91899f9b7d3b8dcef694026493eb1061e34e7906e79741"},"volume_analysis.py":{"bytes":7324,"sha256":"398c8955a399b7c55eda1939f6cfc5f2c2a137f2a844351f8a8c0cb1931e63cc"},"volume_catalogue.py":{"bytes":5085,"sha256":"f205f57a01804ef79d67e838db832ec62f5cf0353fafff6ed7fb43c0e1aa6e1b"},"volume_chat.py":{"bytes":44737,"sha256":"0d258ed870086bbf47ac6747c62484b265a6784bf307f740262acf2d30591c66"},"volume_contract.py":{"bytes":8050,"sha256":"e00250093544aec09f78d86afa597db7aaec690921fc6c90dad6ce01f26a2a41"},"volume_credit.py":{"bytes":4722,"sha256":"13a868cf49a848849d68b7f79ee607d7f29318d1fd97ba5c8e35495582cdea41"},"volume_devices.py":{"bytes":3348,"sha256":"68440c1b92d81d72d4e01dc16731fa76f4637647e221cb846e0ba67fe08d10dd"},"volume_impact.py":{"bytes":11925,"sha256":"38d91ef35eb5e1c850fe64d5ea32c4f9cdd7a501137d0cb922af9a51d4a51d82"},"volume_jobs.py":{"bytes":19692,"sha256":"4094b142b0f2b7522380e2d61bcb41a312493b5597bb1140f09a9a341ab5af06"},"volume_live.py":{"bytes":8495,"sha256":"be782c7cb5c078edbd9693a72909c3b0b455fb73ebe066516f21fe352c9b8b2a"},"volume_market.py":{"bytes":33085,"sha256":"9c1536cfaddacc2e9bed9a21b24e868ba1a95267f38cf2bb362ec606fd26096c"},"volume_monitor.py":{"bytes":14599,"sha256":"66ff4c8837ea154c7728b3775c8a0c1e349e7746a2254d87f4edd3224c606e64"},"volume_news.py":{"bytes":6801,"sha256":"355d506a59d43089ba4dc4326a3a3fbd6bb009180afecc4be67318b25e01bc57"},"volume_notifications.py":{"bytes":16328,"sha256":"74752d772493b173cd33c0cdf207f9d52f2d30c55ffdc78bedd3e68994e9885d"},"volume_plans.py":{"bytes":16128,"sha256":"54bd52e549ae5fac4af52a01f0d4515710042383a34207e22f3d591a106ec88e"},"volume_purchases.py":{"bytes":14574,"sha256":"21c5db4e53222f8b813e7da22115338f0c8c00dc4149ec0ac0677037cb2aaabe"},"volume_state.py":{"bytes":41301,"sha256":"0aeea80a5043a936619a302c415455542f0b7c7ddc62a8179c33a753823779bd"},"volume_workspace.py":{"bytes":42407,"sha256":"e650c0542d5a1752f186f9ce0e08dbddc3ba71a214e52356bef2b53c93587803"},"workspace_readiness.py":{"bytes":7340,"sha256":"9e1cdd9b97dcca318a5ce899f73299e252deb5d035cd06b5fef2d72155824e7c"}}
source_rows={}
for name,expected in expected_backend.items():
 path=Path('/opt/analyst-ai/backend')/name
 if not path.is_file() or path.is_symlink() or path.resolve(strict=True)!=path or path.stat().st_size>512*1024:
  source_rows[name]={'status':'unavailable'}
  continue
 raw=path.read_bytes()
 actual={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
 source_rows[name]={'status':'observed',**actual,'matches_candidate_base':actual==expected}
report['backend_source_inventory']=source_rows
report['all_backend_sources_match_candidate_base']=all(row.get('matches_candidate_base') is True for row in source_rows.values())

for name in ('analyst-ai-owner.service','analyst-ai-updates.service'):
 result=subprocess.run(['systemctl','show',name,'--property=ActiveState,SubState,NRestarts'],capture_output=True,text=True,timeout=10)
 if result.returncode:raise RuntimeError('service_status_unavailable')
 report[name]=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)

# Inspect only DATABASE_PATH. The broker token and encryption key are not read.
database=None
for line in Path('/etc/analyst-ai/backend.env').read_text().splitlines():
 key,sep,value=line.partition('=')
 if key=='DATABASE_PATH' and sep:
  values=shlex.split(value,comments=False)
  if len(values)!=1:raise RuntimeError('database_configuration_invalid')
  database=Path(values[0]).resolve()
if database is None:database=Path('/var/lib/analyst-ai/backend.db')
if not database.is_file() or not database.is_relative_to('/var/lib/analyst-ai'):
 raise RuntimeError('database_location_unverified')
with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
 db.execute('PRAGMA query_only=ON')
 db.execute('PRAGMA busy_timeout=2000')
 db.set_progress_handler(lambda: 1 if time.monotonic()>deadline else 0,10000)
 deadline=time.monotonic()+8
 tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
 if {'client_versions','sessions','users','installation_owner'}<=tables:
  rows=db.execute('''SELECT cv.version_code,COUNT(*),MAX(cv.observed_at)
   FROM client_versions cv JOIN sessions s ON s.token_hash=cv.session_hash AND s.user_id=cv.user_id
   JOIN users u ON u.id=cv.user_id JOIN installation_owner io ON io.singleton=1 AND io.telegram_sub=u.telegram_sub
   WHERE s.expires_at>=? AND cv.observed_at BETWEEN ? AND ? AND cv.package_name=?
   GROUP BY cv.version_code ORDER BY cv.version_code DESC LIMIT 10''',
   (now,now-86400,now,'ru.omnicio.app.debug')).fetchall()
  report['authenticated_client_version_claims']={'window_seconds':86400,'device_attestation':False,
   'groups':[{'version_code':row[0],'active_session_count':row[1],
              'latest_reported_at_utc':datetime.datetime.fromtimestamp(row[2],datetime.timezone.utc).isoformat()} for row in rows]}
 if {'workspace_snapshots','users','installation_owner'}<=tables:
  # Only timing/status fields are selected. No financial amounts or identifiers.
  fields=('$.as_of','$.event_monitor.checked_at','$.event_monitor.complete','$.event_monitor.calendar',
   '$.event_monitor.news','$.event_monitor.operations','$.event_monitor.payout_announcements',
   '$.calendar.state','$.calendar.data.as_of')
  columns=','.join('json_extract(w.payload_json,?)' for _ in fields)
  query='SELECT '+columns+",json_array_length(json_extract(w.payload_json,'$.calendar.data.exchanges')) FROM workspace_snapshots w JOIN users u ON u.id=w.user_id JOIN installation_owner io ON io.singleton=1 AND io.telegram_sub=u.telegram_sub WHERE w.currency='RUB' AND json_valid(w.payload_json) LIMIT 2"
  rows=db.execute(query,fields).fetchall()
  names=('valuation_as_of','event_checked_at','events_complete','calendar_attempt','news_attempt',
   'operations_attempt','payouts_attempt','calendar_state','calendar_as_of','calendar_exchange_count')
  report['saved_owner_snapshot_status']={'current_broker_fingerprint_revalidated':False,
   'scope':'saved_owner_RUB_snapshots_only','rows':[dict(zip(names,row)) for row in rows]}
 report['read_only_verified']=db.execute('PRAGMA query_only').fetchone()[0]==1

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
opener=urllib.request.build_opener(NoRedirect())
for name,url in [('health','https://analyst-ai-2941515.twc1.net/health'),
                 ('policy','https://analyst-ai-2941515.twc1.net/client/update-policy?package_name=ru.omnicio.app.debug')]:
 try:
  with opener.open(url,timeout=12) as response:
   raw=response.read(65537)
   if len(raw)>65536:raise RuntimeError('public_response_limit')
   value=json.loads(raw)
   report[name]={'http_status':response.status,'response_sha256':hashlib.sha256(raw).hexdigest()}
   if name=='policy':report[name].update({key:value.get(key) for key in ('version_code','version_name','package_name','min_sdk','apk_bytes','apk_sha256','certificate_sha256')})
 except (OSError,ValueError) as error:
  report[name]={'error_type':type(error).__name__}

sdk=Path('/opt/analyst-android-sdk')
files=['platforms/android-37/android.jar','build-tools/37.0.0/apksigner','build-tools/37.0.0/aapt',
 'build-tools/37.0.0/zipalign','platform-tools/adb','emulator/emulator','cmdline-tools/latest/bin/sdkmanager']
report['android_environment']={'sdk_root':str(sdk),'files':{name:(sdk/name).is_file() for name in files},
 'system_images_api37':[str(path.relative_to(sdk)) for path in (sdk/'system-images/android-37').glob('*/*/source.properties')][:12],
 'jdk17':Path('/usr/lib/jvm/java-17-openjdk-amd64/bin/java').is_file(),'kvm_available':Path('/dev/kvm').exists(),
 'gradle98_cached':[str(path) for path in Path('/var/cache/analyst-ai/gradle/wrapper/dists').glob('gradle-9.8.1-bin/*/gradle-9.8.1/bin/gradle')][:4],
 'signing_keystore_present':Path('/var/lib/analyst-ai-build/.android/debug.keystore').is_file()}
workspace=Path('/srv/analyst-ai/workspace')
if (workspace/'.git').exists():
 result=subprocess.run(['git','rev-parse','HEAD'],cwd=workspace,capture_output=True,text=True,timeout=5)
 head=result.stdout.strip()
 report['android_environment']['existing_workspace_head']=head if re.fullmatch(r'[0-9a-f]{40}',head) else None
mem={}
for line in Path('/proc/meminfo').read_text().splitlines():
 key,_,value=line.partition(':')
 if key in {'MemTotal','MemAvailable','SwapTotal','SwapFree'}:mem[key+'_kib']=int(value.split()[0])
report['capacity']={**mem,'disk_free_bytes':shutil.disk_usage(ROOT).free}
counts={}
for path in Path('/proc').glob('[0-9]*/comm'):
 try:name=path.read_text().strip()
 except OSError:continue
 if name in {'java','adb','qemu-system-x86','emulator','gradle'}:counts[name]=counts.get(name,0)+1
report['active_build_process_names']=counts
report['status']='observed'
directory=ROOT/('post-runtime-observation-'+ENVELOPE['run_id']+'-'+str(time.time_ns()))
directory.mkdir(mode=0o700)
(directory/'observation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
