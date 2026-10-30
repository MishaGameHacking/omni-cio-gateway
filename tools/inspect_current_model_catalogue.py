"""Only catalogue metadata; no paid inference and no runtime configuration edit."""
import importlib.util
import json
import os
from pathlib import Path


def main():
    spec = importlib.util.spec_from_file_location('audit', Path('deploy/live_readiness_audit.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        report = module.read_catalogue(os.environ['TIMEWEB_CLOUD_TOKEN'])
    except module.AuditError as error:
        report = {'status': 'unavailable', 'code': str(error), 'model_inference_called': False}
    Path('plan-reports').mkdir(exist_ok=True)
    Path('plan-reports/current-model-catalogue.json').write_text(json.dumps(report, indent=2) + '\n')
    print('MODEL_CATALOGUE=' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
