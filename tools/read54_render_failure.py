"""Read the synthetic screenshot failure from this task's owned checkout."""
import os
from pathlib import Path
import xml.etree.ElementTree as ET
import json
if os.environ.get("COMPUTERNAME")!="LAPTOP-NPSGA016":raise RuntimeError("owner_laptop_required")
for root in Path("C:/").glob("actions-runner*"):
    path=root/"_work/omni-cio-gateway/omni-cio-gateway/visual-source-40859518254-1/app/build/test-results/updateDebugScreenshotTest"
    if not path.is_dir():continue
    for xml in path.glob("*.xml"):
        if xml.stat().st_size>4*1024*1024:continue
        doc=ET.fromstring(xml.read_bytes())
        for case in doc.iter("testcase"):
            for failure in case.findall("failure"):
                print("RENDER54_FAILURE="+json.dumps({"case":case.get("name"),"message":failure.get("message"),"details":(failure.text or "")[:9000]},ensure_ascii=True))
