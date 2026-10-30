"""Stage pinned source and weights without activation for the reviewed owner transport."""
import json
import hashlib
import io
import math
import os
from pathlib import Path
import zipfile

ARTIFACT_SHA256 = "a2d4494ee0aa8f4eec5964d9040d9495638d5490303f29d7537d864d9df2fd3e"


def verify_evaluation(raw):
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != ARTIFACT_SHA256:
        raise ValueError("evaluation_archive_changed")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) != 1 or entries[0].filename != "local-research-evaluation.json" or entries[0].file_size > 32768:
            raise ValueError("evaluation_archive_invalid")
        report = json.loads(archive.read(entries[0]))
    if report.get("model_sha256") != "0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0" \
            or report.get("selector_sha256") != "4bcc429dee99740c29cdfe773e6f7b53e5bffe10cc50ced8c6fb899ce2a233db" \
            or report.get("status") != "evaluated" or report.get("quality_gate_passed") is not True \
            or report.get("resource_gate_passed") is not True or report.get("cpu_threads") != 2:
        raise ValueError("evaluation_gate_failed")
    rows = report.get("cases")
    if not isinstance(rows, list) or len(rows) != 12:
        raise ValueError("evaluation_cases_incomplete")
    if any(row.get("schema_valid") is not True or row.get("selection_correct") is not True
           or type(row.get("seconds")) not in (int, float) or not math.isfinite(row["seconds"])
           or not 0 <= row["seconds"] <= 12 for row in rows):
        raise ValueError("evaluation_case_failed")
    memory = report.get("peak_rss_mib")
    if type(memory) not in (int, float) or not math.isfinite(memory) or not 0 < memory <= 5120:
        raise ValueError("evaluation_memory_failed")


def main():
    verify_evaluation((Path(os.environ["RUNNER_TEMP"]) / "local-e4b-evaluation.zip").read_bytes())
    target = Path("deploy/plan-20261027")
    if not target.is_dir() or target.is_symlink():
        raise ValueError("transport_directory_missing")
    (target / "operation.py").write_bytes(Path("deploy/prepare_local_ai_runtime.py").read_bytes())
    (target / "payload.json").write_text(json.dumps({"source_commit": "853090e11dcefef693366159c97316e55045c4c9"}))


if __name__ == "__main__":
    main()
