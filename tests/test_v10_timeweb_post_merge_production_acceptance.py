from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit

from scripts import check_v10_timeweb_post_merge_production_acceptance as guard
from scripts import timeweb_production_acceptance as acceptance

ROOT=Path(__file__).resolve().parents[1]
SHA="a"*40
ROLLBACK_SHA="b"*40
DIGESTS=tuple(ch*64 for ch in "123456")

class _Response:
    def __init__(self,payload:object)->None:
        self.status=200;self.headers={"Content-Type":"application/json"};self._raw=json.dumps(payload).encode()
    def __enter__(self)->"_Response":return self
    def __exit__(self,exc_type:type[BaseException]|None,exc:BaseException|None,traceback:object)->None:del exc_type,exc,traceback
    def read(self,limit:int)->bytes:return self._raw[:limit]

class _Opener:
    def __init__(self,enabled:bool=True)->None:self.enabled=enabled
    def open(self,request:object,timeout:float)->_Response:
        del timeout
        path=urlsplit(str(request.full_url)).path
        if path=="/livez":return _Response({"status":"ok","release_sha":SHA})
        if path=="/healthz":return _Response({"status":"ok","database":"READY","synthetic_preview":False,"release_sha":SHA})
        if path=="/api/v10/web/auth/providers":
            return _Response([{"provider":"telegram","enabled":True}] if self.enabled else [{"provider":"telegram","enabled":False,"reason":"PUBLIC_MULTI_USER_DISABLED"}])
        raise AssertionError(path)

def _kwargs()->dict[str,str]:
    return {"p2_candidate_evidence_sha256":DIGESTS[0],"p3_cutover_evidence_sha256":DIGESTS[1],"p4_ingress_evidence_sha256":DIGESTS[2],"p5_readiness_sha256":DIGESTS[3],"p5_live_evidence_sha256":DIGESTS[4],"rollback_release_sha":ROLLBACK_SHA,"rollback_evidence_sha256":DIGESTS[5]}

class TimewebPostMergeProductionAcceptanceTests(unittest.TestCase):
    def test_repository_contract_passes(self)->None:guard.validate(ROOT)
    def test_acceptance_seal_is_deterministic_and_source_bound(self)->None:
        evidence=acceptance._evidence(**_kwargs())
        first=acceptance.production_acceptance_seal(SHA,evidence)
        self.assertEqual(first,acceptance.production_acceptance_seal(SHA,evidence))
        self.assertNotEqual(first,acceptance.production_acceptance_seal("c"*40,evidence))
    def test_accept_requires_live_telegram_and_emits_seal(self)->None:
        output=StringIO()
        with redirect_stdout(output):
            seal=acceptance.run(operation="accept",expected_sha=SHA,observed_main_sha=SHA,confirmation=acceptance.ACCEPT_CONFIRMATION,opener=_Opener(),**_kwargs())
        self.assertIsNotNone(seal);self.assertIn("TIMEWEB_PRODUCTION_ACCEPTANCE=ACCEPTED",output.getvalue())
    def test_accept_rejects_disabled_telegram(self)->None:
        with self.assertRaisesRegex(acceptance.ProductionAcceptanceStopped,"TIMEWEB_PRODUCTION_ACCEPTANCE_PROVIDER_SURFACE_INVALID"):
            acceptance.run(operation="accept",expected_sha=SHA,observed_main_sha=SHA,confirmation=acceptance.ACCEPT_CONFIRMATION,opener=_Opener(False),**_kwargs())
    def test_accept_rejects_main_drift(self)->None:
        with self.assertRaisesRegex(acceptance.ProductionAcceptanceStopped,"TIMEWEB_PRODUCTION_ACCEPTANCE_MAIN_SHA_DRIFT"):
            acceptance.run(operation="observe",expected_sha=SHA,observed_main_sha="c"*40,opener=_Opener())
    def test_accept_rejects_rollback_collision(self)->None:
        values=_kwargs();values["rollback_release_sha"]=SHA
        with self.assertRaisesRegex(acceptance.ProductionAcceptanceStopped,"TIMEWEB_PRODUCTION_ACCEPTANCE_ROLLBACK_SHA_COLLISION"):
            acceptance.run(operation="accept",expected_sha=SHA,observed_main_sha=SHA,confirmation=acceptance.ACCEPT_CONFIRMATION,opener=_Opener(),**values)

if __name__=="__main__":
    unittest.main()
