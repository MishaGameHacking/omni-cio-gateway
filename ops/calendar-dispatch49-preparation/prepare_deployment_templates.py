"""Adapt the exact48 administrative deployer to nine reviewed N02 modules.

Only source text/AST and original evidence are handled in this environment.
No application is imported and no deployment is performed by this generator.
"""
from pathlib import Path
import ast
import hashlib
import json

CONTEXT = Path(__file__).resolve().parent.parent
OLD = CONTEXT / 'portfolio-mandate48-runtime-deployment'
OUT = CONTEXT / 'calendar49-runtime-deployment'
NAMES = ('autonomous_ai.py', 'autonomous_controller.py', 'volume_jobs.py', 'volume_workspace.py',
         'volume_monitor.py', 'volume_market.py', 'market_schedule.py', 'background_dispatch.py', 'event_monitor.py')
NEW = ('market_schedule.py', 'background_dispatch.py', 'event_monitor.py')


def replace(text, old, new):
    assert text.count(old) == 1, old[:150]
    return text.replace(old, new, 1)


def rename(text):
    for old, new in (('portfolio-mandate48', 'calendar49'), ('portfolio_mandate48', 'calendar49'),
                     ('MANDATE48', 'CALENDAR49'), ('source-backup48', 'source-backup49'),
                     ('mandate_test', 'calendar_test'), ('actual_mandate', 'actual_calendar'),
                     ('exact_four_file', 'exact_nine_file')):
        text = text.replace(old, new)
    return text


def main():
    assert not OUT.exists()
    OUT.mkdir()
    pins = {'deploy-runtime.py': '5752a33bcd436b085eb90ea154542e6c098f962067cebc448146bb59cb4abed0',
            'public-checks.py': 'a06973def653186a586ae86a56991c53c702955c0e6469c4c3ba353cd44ea210',
            'receive-deployment.py': 'd1b373e21dcb499ade417a1d59f6f3ed4b2e64b4d08785b3e5a950511bb7749a',
            'prepare-deployment.py': '5a54f16c79832f0e8bec024fac822553ebd794ca6d13341b138ddb571f276b8a'}
    originals = {}
    for name, expected in pins.items():
        raw = (OLD / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected
        originals[name] = raw.decode()
    remote = rename(originals['deploy-runtime.py'])
    remote = remote.replace('exactly four Windows-tested mandate sources', 'exactly nine Windows-tested calendar/dispatch sources')
    remote = replace(remote, "need(name == 'portfolio_mandate.py' and current_source(name) is None, 'new_module_present_before_install')",
                     "need(name in " + repr(NEW) + " and current_source(name) is None, 'new_module_present_before_install')")
    remote = replace(remote, "need(set(EXPECTED['runtime_sources']) == {'portfolio_mandate.py', 'volume_state.py', 'purchase_policy.py', 'autonomous_controller.py'}, 'deployment_scope_changed')",
                     "need(set(EXPECTED['runtime_sources']) == set(" + repr(NAMES) + "), 'deployment_scope_changed')")
    begin = remote.index("            cases = [case for case in tree.iter('testcase')")
    end = remote.index('            desired = {}', begin)
    remote = remote[:begin] + '''            contract_count = 0
            for name, contract in EXPECTED['calendar_contracts'].items():
                module = name.removesuffix('.py')
                cases = [case for case in tree.iter('testcase') if case.get('classname') in {
                    'backend.tests.' + module, module}]
                need(len(cases) == contract['count'] and
                     {case.get('name').split('[', 1)[0] for case in cases} == set(contract['names']) and
                     all(case.find('skipped') is None for case in cases), 'actual_calendar_contract_tests_missing_or_skipped')
                test_raw = member('source/backend/tests/' + name, 2 * 1024**2, files)
                need(identity(test_raw) == contract['source'], 'tested_calendar_contract_source_changed')
                contract_count += len(cases)
            need(contract_count == EXPECTED['calendar_test_count'], 'calendar_contract_count_changed')
''' + remote[end:]
    remote = replace(remote, "return desired, {'original_calendar_test_count': len(cases)",
                     "return desired, {'original_calendar_test_count': contract_count")
    outputs = {'deploy-runtime.py': remote, 'receive-deployment.py': rename(originals['receive-deployment.py']),
               'public-checks.py': originals['public-checks.py']}
    for name, value in outputs.items():
        ast.parse(value)
        (OUT / name).write_text(value)
    preparer = rename(originals['prepare-deployment.py'])
    preparer = preparer.replace('exact tested48 four-file', 'exact tested49 nine-file').replace('completed Windows48', 'completed Windows49')
    preparer = preparer.replace('MANDATE_NAMES', 'CALENDAR_NAMES').replace('windows48', 'windows49').replace('reviewed48', 'reviewed49')
    preparer = preparer.replace('candidate48', 'candidate49').replace('actual48', 'actual49')
    tree = ast.parse(preparer)
    lines = preparer.splitlines(keepends=True)
    replacements = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in {'TEMPLATE_PINS', 'CALENDAR_NAMES'} for target in node.targets):
            key = node.targets[0].id
            value = {n: hashlib.sha256(t.encode()).hexdigest() for n, t in outputs.items()} if key == 'TEMPLATE_PINS' else NAMES
            replacements.append((node.lineno - 1, node.end_lineno, key + ' = ' + repr(value) + '\n'))
    for begin, end, value in reversed(replacements):
        lines[begin:end] = [value]
    preparer = ''.join(lines)
    preparer = replace(preparer, "request['candidate_version_code'] == 48", "request['candidate_version_code'] == 49")
    preparer = replace(preparer, "request['candidate_version_name'] == '0.14.1-preview'", "request['candidate_version_name'] == '0.14.2-preview'")
    preparer = replace(preparer, "reviewed['version_before'] == {'code': 45, 'name': '0.13.7'}", "reviewed['version_before'] == {'code': 48, 'name': '0.14.1'}")
    preparer = replace(preparer, "reviewed['version_after'] == {'code': 48, 'name': '0.14.1'}", "reviewed['version_after'] == {'code': 49, 'name': '0.14.2'}")
    preparer = replace(preparer, "r'\\bversionCode\\s*=\\s*48\\b'", "r'\\bversionCode\\s*=\\s*49\\b'")
    preparer = replace(preparer, "r'\\bversionName\\s*=\\s*\"0\\.14\\.1\"'", "r'\\bversionName\\s*=\\s*\"0\\.14\\.2\"'")
    preparer = replace(preparer, "name == 'portfolio_mandate.py' and old['status'] == 'absent'",
                        'name in ' + repr(NEW) + " and old['status'] == 'absent'")
    begin = preparer.index("    names = [node.name for node in ast.walk(ast.parse(rows['backend/tests/test_portfolio_mandate.py']['content']))")
    end = preparer.index("    expected = {'schema': 1,", begin)
    preparer = preparer[:begin] + '''    contracts = {}
    for name in ('test_market_schedule.py', 'test_background_dispatch.py'):
        path = 'backend/tests/' + name
        nodes = [node for node in ast.parse(rows[path]['content']).body
                 if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
        names, count = [], 0
        for node in nodes:
            names.append(node.name)
            multiplier = 1
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and ast.unparse(decorator.func) == 'pytest.mark.parametrize':
                    multiplier *= len(ast.literal_eval(decorator.args[1]))
            count += multiplier
        need(len(names) == len(set(names)) and count >= len(names) >= 10, 'exact_calendar_contract_functions_required')
        contracts[name] = {'names': names, 'count': count, 'source': inventory['files'][path]}
    callback_raw = checked(CONTEXT / 'candidate48-mandate-v7/source/backend/app.py', inventory['files']['backend/app.py']['sha256'])
''' + preparer[end:]
    preparer = replace(preparer, "'runtime_sources': runtime_sources, 'calendar_test_names': names, 'calendar_test_count': 21,\n                'calendar_test_source': inventory['files']['backend/tests/test_portfolio_mandate.py'],\n                'callback_style_sha256': callback_style(rows['backend/app.py']['content']),",
                        "'runtime_sources': runtime_sources, 'calendar_contracts': contracts,\n                'calendar_test_count': sum(row['count'] for row in contracts.values()),\n                'callback_style_sha256': callback_style(callback_raw),")
    preparer = preparer.replace('Read exact source48 backup', 'Read exact source49 backup').replace('Deploy only four Windows-tested portfolio mandate sources', 'Deploy only nine Windows-tested calendar and event sources').replace('Apply exact Windows-tested48 portfolio mandate rules', 'Apply exact Windows-tested49 calendar and event dispatch')
    ast.parse(preparer)
    (OUT / 'prepare-deployment.py').write_text(preparer)
    print(json.dumps({'prepared_templates': len(outputs) + 1, 'runtime_modules': NAMES,
        'preparer_sha256': hashlib.sha256(preparer.encode()).hexdigest(), 'application_or_tests_executed': False}))


if __name__ == '__main__':
    main()
