from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts import check_v10_timeweb_runtime_reachability as guard

ROOT=Path(__file__).resolve().parents[1]

def _write(root:Path, relative:str, source:str)->None:
    path=root/relative
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(source,encoding="utf-8")

def _fixture_root(temporary:str)->Path:
    root=Path(temporary)
    contract={"runtime_reachability":{
        "production_entry_module":"apps.api.hosted_runtime",
        "required_reachable_modules":["apps.api.telegram_auth","omni_cio.web.telegram_auth_routes_v1","omni_cio.web.telegram_auth_services_v1"],
        "inventory_path":"docs/architecture/V10_TIMEWEB_PLATFORM_PROVIDER_INVENTORY.json",
        "scan_roots":["apps","omni_cio"],
        "retired_classifications":["HISTORY","RETIRE_NOW_AFTER_AUTHORITY","RETIRE_AFTER_CUTOVER"],
        "forbidden_module_fragments":["cloudflare","neon","render","cloudru","vk_id"],
        "retained_history_may_exist_when_unreachable":True}}
    inventory={"explicit_paths":{"apps/api/hosted_preview.py":{"classification":"HISTORY"}}}
    _write(root,"docs/architecture/V10_TIMEWEB_WORKTREE_CONVERGENCE_CONTRACT.json",json.dumps(contract))
    _write(root,"docs/architecture/V10_TIMEWEB_PLATFORM_PROVIDER_INVENTORY.json",json.dumps(inventory))
    _write(root,"apps/api/hosted_runtime.py","from apps.api.telegram_auth import build\nfrom omni_cio.web.telegram_auth_routes_v1 import install\n")
    _write(root,"apps/api/telegram_auth.py","from omni_cio.web.telegram_auth_services_v1 import TelegramServices\n")
    _write(root,"apps/api/hosted_preview.py","legacy=True\n")
    _write(root,"omni_cio/web/telegram_auth_routes_v1.py","install=object()\n")
    _write(root,"omni_cio/web/telegram_auth_services_v1.py","TelegramServices=object()\n")
    return root

class TimewebRuntimeReachabilityTests(unittest.TestCase):
    def test_current_repository_has_telegram_only_production_reachability(self)->None:
        reachable=guard.validate(ROOT)
        self.assertIn("apps.api.telegram_auth",reachable)
        self.assertIn("omni_cio.web.telegram_auth_routes_v1",reachable)
        self.assertNotIn("apps.api.hosted_preview",reachable)

    def test_retired_history_may_exist_when_unreachable(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            reachable=guard.validate(_fixture_root(temporary))
            self.assertNotIn("apps.api.hosted_preview",reachable)

    def test_reintroduced_retired_import_fails_closed(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            root=_fixture_root(temporary)
            _write(root,"apps/api/hosted_runtime.py","from apps.api.telegram_auth import build\nfrom apps.api.hosted_preview import legacy\nfrom omni_cio.web.telegram_auth_routes_v1 import install\n")
            with self.assertRaisesRegex(RuntimeError,"TIMEWEB_RUNTIME_REACHABILITY_RETIRED_MODULE_REACHED"):
                guard.validate(root)

    def test_missing_telegram_service_path_fails_closed(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            root=_fixture_root(temporary)
            _write(root,"apps/api/telegram_auth.py","value=1\n")
            with self.assertRaisesRegex(RuntimeError,"TIMEWEB_RUNTIME_REACHABILITY_TELEGRAM_PATH_MISSING"):
                guard.validate(root)

if __name__=="__main__":
    unittest.main()
