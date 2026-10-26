"""Freeze reviewed source text and render the existing Windows-only build transport."""
from pathlib import Path
import ast, base64, difflib, hashlib, importlib.util, json, zlib
import yaml

HERE=Path(__file__).resolve().parent
CONTEXT=HERE.parent
BASE='d871af24f6f8e606476d986faf4e595c4c500389'
SOURCE='de9339350d25e0f3731f8ccc3702f8be5d2a2110b2433b1c5d9ea74035e51d89'

def load_admin(name,path,pin=None):
    raw=path.read_bytes()
    if pin: assert hashlib.sha256(raw).hexdigest()==pin,(name,'pin')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def digest(raw):return hashlib.sha256(raw).hexdigest()
def jb(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
def blob(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--include-autosave',action='store_true')
    p.add_argument('--portfolio-mandate',action='store_true')
    p.add_argument('--repair-v12-jvm',action='store_true');args=p.parse_args()
    if args.portfolio_mandate:
        assert args.include_autosave and not args.repair_v12_jvm
    version_code,version_name=(48,'0.14.1') if args.portfolio_mandate else (47,'0.14.0')
    output=args.output.absolute()
    assert output.parent==CONTEXT and not output.exists(),'New output under context required'
    source=load_admin('single_style_source_text',HERE/'prepare_single_style.py')
    if args.repair_v12_jvm:
        assert args.include_autosave
        reviewed=(CONTEXT/'candidate47-autosave-v12/reviewed-files.json').read_bytes()
        assert digest(reviewed)=='ad9eb517c3953d7bc30550d3439bd316e086ba6cc4ac054c30489b2697d92f56'
        files={row['path']:row['content'] for row in json.loads(reviewed)['files']}
        gradle=files['app/build.gradle.kts']
        assert gradle.count('    testImplementation(libs.junit)')==1
        files['app/build.gradle.kts']=gradle.replace('    testImplementation(libs.junit)',
            '    testImplementation(libs.junit)\n    // Real JSON operations for JVM model checks; never packaged in the Android app.\n    testImplementation("org.json:json:20260814")')
    else:
        files=dict(source.FILES)
        dock=load_admin('brain_dock_source_text',HERE/'prepare_brain_dock.py')
        dock.apply(files, source.base)
        controls=load_admin('smart_controls_source_text',HERE/'prepare_smart_controls.py')
        controls.apply(files, source.base)
    if args.include_autosave and not args.repair_v12_jvm:
        autosave=load_admin('autosave_source_text',HERE/'prepare_autosave.py')
        autosave.apply(files, source.base)
        editors=load_admin('automatic_editors_source_text',HERE/'prepare_automatic_editors.py')
        editors.apply(files, source.base)
        recovery=load_admin('autosave_recovery_source_text',HERE/'prepare_autosave_recovery.py')
        recovery.apply(files, source.base)
        native_controls=load_admin('native_controls_source_text',HERE/'prepare_native_controls.py')
        native_controls.apply(files, source.base)
        popup=load_admin('popup_fixture_source_text',HERE/'prepare_popup_fixture.py')
        popup.apply(files, source.base)
        performance=load_admin('portfolio_performance_source_text',HERE/'prepare_portfolio_performance.py')
        performance.apply(files, source.base)
        gradle=files['app/build.gradle.kts']
        assert gradle.count('    testImplementation(libs.junit)')==1
        files['app/build.gradle.kts']=gradle.replace('    testImplementation(libs.junit)',
            '    testImplementation(libs.junit)\n    // Real JSON operations for JVM model checks; never packaged in the Android app.\n    testImplementation("org.json:json:20260814")')
    if args.include_autosave:
        lock=source.base('app/gradle.lockfile')
        assert 'org.json:json:' not in lock
        anchor='org.hamcrest:hamcrest-core:1.3=debugUnitTestCompileClasspath,debugUnitTestRuntimeClasspath\n'
        assert lock.count(anchor)==1
        # JSON-java has no runtime dependencies; retain strict existing configurations.
        files['app/gradle.lockfile']=lock.replace(anchor, anchor+
            'org.json:json:20260814=debugUnitTestCompileClasspath,debugUnitTestRuntimeClasspath\n')
    for path in ('app/build.gradle.kts','.github/scripts/tests/test_android17_live_spectrum.py',
                 '.github/scripts/tests/test_spectrum_brand_identity.py'):
        text=files[path].replace('versionCode = 46','versionCode = 47').replace('versionName = "0.13.8"','versionName = "0.14.0"')
        text=text.replace('int(version.group(1)), 46','int(version.group(1)), 47')
        files[path]=text
    if args.portfolio_mandate:
        for name in ('prepare_mandate48.py','prepare_mandate_ui48.py','prepare_mandate_tests48.py'):
            module=load_admin('mandate_source_text_'+name.replace('.','_'),HERE/name)
            module.apply(files,source.base)
        for path in ('app/build.gradle.kts','.github/scripts/tests/test_android17_live_spectrum.py',
                     '.github/scripts/tests/test_spectrum_brand_identity.py'):
            text=files[path].replace('versionCode = 47','versionCode = 48').replace('versionName = "0.14.0"','versionName = "0.14.1"')
            files[path]=text.replace('int(version.group(1)), 47','int(version.group(1)), 48')
    marker='app/src/debug/java/ru/omnicio/app/ProfileUiProbeActivity.kt'
    files[marker]=files[marker].replace('probe-primary-foreground:${MaterialTheme.colorScheme.onPrimary.toArgb()',
                                      'probe-primary-foreground:${MaterialTheme.colorScheme.onPrimaryContainer.toArgb()')
    # Inspect the original successful build45, rather than blessing a failed46 as a base.
    native=load_admin('verified_native45',CONTEXT/'prepare_native45_counter.py',
                     '6b9a7a7787cb295243e726db48c9fa90ccf41124c9e0db1c6f0a16a8397197ed')
    request=json.loads((CONTEXT/'continued45-40342969750/native45-request.json').read_bytes())
    native.validate(request)
    helper=load_admin('build45_transport',CONTEXT/'prepare_candidate45.py',
                     '69bfb8dbefd2cb3ce7bbf03dbd3bbbaf90c66b8b6fb5d38873a6f27e878ecf9a')
    helper.verify_transport_source()
    rows=[];diff=[]
    for path,text in sorted(files.items()):
        old=source.base(path)
        if old==text:continue
        assert path.startswith(('app/','backend/','.github/scripts/','ci-ui-driver/')) and '..' not in Path(path).parts
        raw=text.encode();previous=old.encode() if old is not None else None
        if path.endswith('.py'):ast.parse(raw,filename=path)
        rows.append({'path':path,'old_git_blob':blob(previous) if previous is not None else None,
            'old_sha256':digest(previous) if previous is not None else None,'old_bytes':len(previous) if previous is not None else None,
            'new_sha256':digest(raw),'new_bytes':len(raw),'content':text})
        diff.extend(difflib.unified_diff((old or '').splitlines(keepends=True),text.splitlines(keepends=True),
                                       fromfile='a/'+path,tofile='b/'+path))
    assert len({r['path'].casefold() for r in rows})==len(rows)
    review={'schema':1,'kind':'single_style47_owner_reference','base_commit':BASE,'base_source_sha256':SOURCE,
        'verified_base45_request':request,'version_before':{'code':45,'name':'0.13.7'},
        'version_after':{'code':version_code,'name':version_name},'application_or_tests_executed':False,'files':rows}
    review_raw=jb(review)
    bundle=json.dumps({'reference_commit':BASE,'files':rows},ensure_ascii=True,separators=(',',':')).encode()
    # Preserve the laptop's <=100-files-per-bundle boundary instead of weakening it.
    transports=[]; bundle_specs=[]
    for index,start in enumerate(range(0,len(rows),100)):
        name='n00-single-style47' if index==0 else 'n00-single-style47-part'+str(index+1)
        chunk=json.dumps({'reference_commit':BASE,'files':rows[start:start+100]},ensure_ascii=True,separators=(',',':')).encode()
        encoded=base64.b64encode(zlib.compress(chunk,9))
        transports.append((name,encoded))
        bundle_specs.append({'name':name,'transport_sha256':digest(encoded),'decoded_sha256':digest(chunk)})
    assert 1<=len(transports)<=8
    transport=transports[0][1]
    manifest=json.dumps({'schema':1,'base_commit':BASE,'bundles':bundle_specs},separators=(',',':')).encode()
    bootstrap=helper.bootstrap(BASE,SOURCE)
    guest=helper.read_pinned(CONTEXT/'full-build-baseline/n00-linux-guest.py',helper.BASELINE_GUEST_SHA256)
    workflow=yaml.safe_load(helper.workflow(BASE,bootstrap,guest,transport,manifest))
    workflow['name']=f'Implement the owner single style and portfolio hierarchy; verify candidate{version_code}'
    develop=workflow['jobs']['develop']
    develop['name']=f'Apply candidate{version_code} on the authorized Windows laptop and complete every build check'
    staged=artifact=0
    for step in develop['steps']:
        if step.get('name')=='Stage verified administrative transport: n00-native45.b64':
            step.clear();step.update(helper.stage('n00-single-style47.b64',transport));staged+=1
        if step.get('uses','').startswith('actions/upload-artifact@'):
            assert step['with']['name']=='n00-candidate45-build-checks'
            step['with']['name']=f'n00-candidate{version_code}-build-checks'
            step['with']['path']+='\n${{ github.workspace }}/windows-development-${{ github.run_id }}-${{ github.run_attempt }}/app/build/test-results/testDebugUnitTest/*.xml'
            artifact+=1
    assert staged==artifact==1
    stage_index=next(i for i,step in enumerate(develop['steps']) if step.get('name')=='Stage verified administrative transport: patch-manifest.json')
    develop['steps'][stage_index:stage_index]=[helper.stage(name+'.b64',raw) for name,raw in transports[1:]]
    workflow_raw=yaml.safe_dump(workflow,allow_unicode=True,sort_keys=False,width=120).encode()
    assert b'n00-native45' not in workflow_raw
    summary={'state':'prepared_source_text_only','base_commit':BASE,'base_source_sha256':SOURCE,
        'base_build_run':40342969750,'source_paths':len(rows),'new_paths':sum(r['old_git_blob'] is None for r in rows),
        'version_code':version_code,'version_name':version_name+'-preview','reviewed_files_sha256':digest(review_raw),
        'bundle_sha256':digest(bundle),'transport_sha256':digest(transport),'patch_manifest_sha256':digest(manifest),
        'bootstrap_sha256':digest(bootstrap),'workflow_sha256':digest(workflow_raw),
        'source_generator_sha256':digest((HERE/'prepare_single_style.py').read_bytes()),
        'dock_generator_sha256':digest((HERE/'prepare_brain_dock.py').read_bytes()),
        'controls_generator_sha256':digest((HERE/'prepare_smart_controls.py').read_bytes()),
        'bundle_specs':bundle_specs,
        'autosave_included':args.include_autosave,
        'autosave_generator_sha256':digest((HERE/'prepare_autosave.py').read_bytes()) if args.include_autosave else None,
        'automatic_editors_generator_sha256':digest((HERE/'prepare_automatic_editors.py').read_bytes()) if args.include_autosave else None,
        'autosave_recovery_generator_sha256':digest((HERE/'prepare_autosave_recovery.py').read_bytes()) if args.include_autosave else None,
        'native_controls_generator_sha256':digest((HERE/'prepare_native_controls.py').read_bytes()) if args.include_autosave and not args.repair_v12_jvm else None,
        'popup_fixture_generator_sha256':digest((HERE/'prepare_popup_fixture.py').read_bytes()) if args.include_autosave and not args.repair_v12_jvm else None,
        'portfolio_performance_generator_sha256':digest((HERE/'prepare_portfolio_performance.py').read_bytes()) if args.include_autosave and not args.repair_v12_jvm else None,
        'mandate_generators':{name:digest((HERE/name).read_bytes()) for name in ('prepare_mandate48.py','prepare_mandate_ui48.py','prepare_mandate_tests48.py')} if args.portfolio_mandate else None,
        'applied_on_windows':False,'build_passed':False,'native_passed':False,'deployed':False,'plan_complete':False,
        'supersedes':'Unpublished multi-theme46. Failed builds remain original failed evidence.'}
    if args.repair_v12_jvm:
        for key in tuple(summary):
            if key.endswith('_generator_sha256'): summary[key]=None
        summary['repair_of_reviewed_files_sha256']=digest(reviewed)
        summary['repair_reason']='Original Windows225 JVM checks:8 failures because Android JSONObject was a JVM stub. Add pinned test-only org.json implementation and matching two-configuration dependency lock; preserve all assertions.'
    output.mkdir()
    outputs={'reviewed-files.json':review_raw,'bundle.json':bundle,'n00-single-style47.b64':transport,
        'patch-manifest.json':manifest,'windows-full-development.py':bootstrap,'n00-linux-guest.py':guest,
        'workflow.yml':workflow_raw,'manifest-summary.json':jb(summary),'candidate.patch':''.join(diff).encode()}
    outputs.update({name+'.b64':raw for name,raw in transports[1:]})
    for path,raw in outputs.items():(output/path).write_bytes(raw)
    for row in rows:
        path=output/'source'/row['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_text(row['content'])
    print(json.dumps(summary))

if __name__=='__main__':main()
