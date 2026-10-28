"""Normalize exact one-shot patcher literals before applying source changes."""
from pathlib import Path

patcher = Path(".github/scripts/apply_sonar_staging_patches.py")
value = patcher.read_text(encoding="utf-8")
old = """    ('r"[0-9](?:\\\\.[0-9]{1,3})?"', 'r"\\\\d(?:\\\\.\\\\d{1,3})?"'),"""
new = """    ('r"[0-9](?:\\.[0-9]{1,3})?"', 'r"\\\\d(?:\\.\\\\d{1,3})?"'),"""
if value.count(old) != 1:
    raise RuntimeError("escaped theme regex patch entry changed")
value = value.replace(old, new)

start_marker = 'old = """                foreground, background = ("disabledInk", "disabledContainer")'
end_marker = r'value = value.replace(old, "                foreground, background = _switch_roles(checked, enabled)\n")' + "\n"
end_marker = end_marker.replace('\\"', '"')
start = value.find(start_marker)
end = value.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError("theme nested switch patch block changed")
value = value[:start] + value[end + len(end_marker):]

# Navigation-test rewrites are line-sensitive because Python consumes a source
# backslash at the end of a line inside triple-quoted patch strings. Remove the
# brittle block and apply those changes directly below.
patch_lines = value.splitlines()
nav_starts = [index for index, line in enumerate(patch_lines)
              if line == 'path = ".github/scripts/tests/test_navigation_detail_probe.py"']
if len(nav_starts) != 1:
    raise RuntimeError("navigation patch section start changed")
nav_start = nav_starts[0]
nav_end = next((index for index in range(nav_start + 1, len(patch_lines))
                if patch_lines[index] == 'path = ".github/scripts/theme_lifecycle_probe.py"'), -1)
if nav_end < 0:
    raise RuntimeError("navigation patch section end changed")
del patch_lines[nav_start:nav_end]
value = "\n".join(patch_lines) + "\n"
patcher.write_text(value, encoding="utf-8")

source = Path(".github/scripts/theme_state_evidence.py")
lines = source.read_text(encoding="utf-8").splitlines()
indices = [index for index, line in enumerate(lines)
           if line.strip().startswith('foreground, background = ("disabledInk", "disabledContainer")')]
if len(indices) != 1:
    raise RuntimeError("theme nested switch source changed")
index = indices[0]
if index + 1 >= len(lines) or lines[index + 1].strip() != '(("onPrimary", "primary") if checked else ("outline", "surfaceContainerHighest"))':
    raise RuntimeError("theme nested switch continuation changed")
indent = lines[index][:-len(lines[index].lstrip())]
lines[index:index + 2] = [indent + "foreground, background = _switch_roles(checked, enabled)"]
source.write_text("\n".join(lines) + "\n", encoding="utf-8")

navigation = Path(".github/scripts/tests/test_navigation_detail_probe.py")
navigation_text = navigation.read_text(encoding="utf-8")
if navigation_text.count("from unittest.mock import patch") != 1:
    raise RuntimeError("navigation mock import changed")
navigation_text = navigation_text.replace("from unittest.mock import patch", "from unittest.mock import Mock, patch", 1)
clock_old = 'patch("profile_ui_probe.time.monotonic", lambda: now[0])'
clock_new = 'patch("profile_ui_probe.time.monotonic", side_effect=lambda: now[0])'
clock_count = navigation_text.count(clock_old)
if clock_count != 5:
    raise RuntimeError(f"navigation monotonic source count changed: {clock_count}")
navigation_text = navigation_text.replace(clock_old, clock_new)
user_marker = 'USER = "synthetic-business-00000000-0000-0000-0000-000000000001"\n\n\n'
user_helper = '''USER = "synthetic-business-00000000-0000-0000-0000-000000000001"


def enter_wide_viewport(probe):
    with details.wide_emulator_viewport(probe, {}):
        pass


'''
if navigation_text.count(user_marker) != 1:
    raise RuntimeError("navigation helper insertion point changed")
navigation_text = navigation_text.replace(user_marker, user_helper)
nav_lines = navigation_text.splitlines()


def method_span(name):
    starts = [index for index, line in enumerate(nav_lines)
              if line.startswith(f"    def {name}(")]
    if len(starts) != 1:
        raise RuntimeError(f"navigation method changed: {name}")
    start = starts[0]
    end = next((index for index in range(start + 1, len(nav_lines))
                if nav_lines[index].startswith("    def ") or nav_lines[index].startswith("class ")), len(nav_lines))
    return start, end


def prepare_expected_failure(name):
    start, end = method_span(name)
    calls = [index for index in range(start, end)
             if 'case(probe).observed("strategy")' in nav_lines[index]]
    if len(calls) != 1:
        raise RuntimeError(f"navigation failure call changed: {name}")
    call = calls[0]
    with_lines = [index for index in range(start, call)
                  if nav_lines[index].lstrip().startswith("with ")]
    if not with_lines:
        raise RuntimeError(f"navigation failure context changed: {name}")
    context = with_lines[-1]
    if not any("self.assertRaises(AssertionError)" in nav_lines[index]
               for index in range(context, call)):
        raise RuntimeError(f"navigation expected failure missing: {name}")
    indentation = nav_lines[context][:-len(nav_lines[context].lstrip())]
    nav_lines.insert(context, indentation + "navigation_case = case(probe)")
    call += 1
    nav_lines[call] = nav_lines[call].replace('case(probe).observed("strategy")',
                                              'navigation_case.observed("strategy")')


for method_name in (
    "test_persistent_counter_disagreement_fails_at_the_original_deadline",
    "test_a_forever_stale_equal_pair_remains_a_failure",
    "test_mutation_contract_failure_and_changed_user_still_fail_immediately",
):
    prepare_expected_failure(method_name)


def replace_viewport_failure(message):
    matches = [index for index, line in enumerate(nav_lines)
               if line.strip() == f'self.fail("{message}")']
    if len(matches) != 1:
        raise RuntimeError(f"navigation viewport failure changed: {message}")
    failure = matches[0]
    owner = failure - 1
    if owner < 0 or nav_lines[owner].strip() != "with details.wide_emulator_viewport(probe, {}):":
        raise RuntimeError(f"navigation viewport context changed: {message}")
    indentation = nav_lines[owner][:-len(nav_lines[owner].lstrip())]
    nav_lines[owner:failure + 1] = [indentation + "enter_wide_viewport(probe)"]


for failure_message in (
    "Ambiguous or unowned display was admitted",
    "Unowned display was admitted",
    "Unauthenticated frame source was admitted",
):
    replace_viewport_failure(failure_message)

lambda_lines = [index for index, line in enumerate(nav_lines)
                if line.strip() == "probe.read_tree = lambda: frame()"]
if len(lambda_lines) != 1:
    raise RuntimeError("navigation read_tree lambda changed")
read_index = lambda_lines[0]
indentation = nav_lines[read_index][:-len(nav_lines[read_index].lstrip())]
nav_lines[read_index] = indentation + "probe.read_tree = Mock(return_value=frame())"
navigation.write_text("\n".join(nav_lines) + "\n", encoding="utf-8")
