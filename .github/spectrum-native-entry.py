"""One-use migration entry; candidate contains only native product code and tests."""
from pathlib import Path
import json

path = Path('.github/spectrum-native.py')
source = path.read_text(encoding='utf-8')
old = "content.index('AppScreen.Education -> EducationScreen(')"
new = "content.index('AppScreen.Education -> {')"
if source.count(old) != 1:
    raise RuntimeError('Unexpected education navigation boundary')
source = source.replace(old, new)
exec(compile(source, str(path), 'exec'))
manifest_path = Path('spectrum-generated.json')
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
manifest['deletions'].append('.github/spectrum-native-entry.py')
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
