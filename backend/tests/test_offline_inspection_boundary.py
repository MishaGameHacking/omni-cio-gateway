"""Synthetic local evidence only; no production filesystem, network or account."""
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "offline_inspection_boundary", Path(__file__).resolve().parents[2] / "tools/inspect_runtime_hierarchy.py")
inspector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspector)


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    root = tmp_path / "inspection"
    (root / "inputs").mkdir(parents=True)
    monkeypatch.setattr(inspector, "EVIDENCE_ROOT", root)
    return root


@pytest.mark.parametrize("name", ["../snapshot.json", "/etc/passwd", "C:\\private.json", "//server/share/input.json",
    "snapshot.json/../strategy.json", ".\\snapshot.json", "snapshot.json:stream", "snapshot.json\0",
    "snapshot.json\n", "", "other.json", None, False, 7, []])
def test_only_fixed_input_names_are_admitted(name, monkeypatch):
    reads = []
    monkeypatch.setattr(inspector, "_read_input", lambda path: reads.append(path))
    with pytest.raises(ValueError, match="^unknown_named_evidence_input$"):
        inspector.load(name)
    assert reads == []


@pytest.mark.parametrize("name", ["snapshot.json", "strategy.json"])
def test_valid_named_input_is_read_without_altering_its_bytes(evidence, name):
    target = evidence / "inputs" / name
    raw = b'{"schema": 1, "label": "synthetic"}'
    target.write_bytes(raw)
    assert inspector.load(name) == {"schema": 1, "label": "synthetic"}
    assert target.read_bytes() == raw


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'[]', b'not-json'])
def test_ambiguous_or_nonfinite_input_is_rejected(evidence, raw):
    (evidence / "inputs/snapshot.json").write_bytes(raw)
    with pytest.raises(ValueError):
        inspector.load("snapshot.json")


def test_empty_and_oversized_input_fail_before_read(evidence, monkeypatch):
    target = evidence / "inputs/snapshot.json"
    target.write_bytes(b'')
    with pytest.raises(ValueError, match="^input_size_limit$"):
        inspector.load("snapshot.json")
    target.write_bytes(b'{"value": 1}')
    monkeypatch.setattr(inspector, "MAX_INPUT_BYTES", 4)
    with pytest.raises(ValueError, match="^input_size_limit$"):
        inspector.load("snapshot.json")


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_external_file_cannot_be_imported_through_a_link(evidence, link_kind):
    external = evidence.parent / "unrelated.json"
    external.write_bytes(b'{"private": "synthetic-external-marker"}')
    target = evidence / "inputs/snapshot.json"
    if link_kind == "hardlink":
        os.link(external, target)
    else:
        target.symlink_to(external)
    with pytest.raises(ValueError, match="^single_regular_evidence_file_required$"):
        inspector.load("snapshot.json")
    assert external.read_bytes() == b'{"private": "synthetic-external-marker"}'


def test_linked_input_directory_is_rejected(evidence):
    original = evidence / "inputs"
    original.rmdir()
    outside = evidence.parent / "external-inputs"
    outside.mkdir()
    (outside / "snapshot.json").write_bytes(b'{}')
    original.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="^linked_or_non_directory_evidence_path$"):
        inspector.load("snapshot.json")


def test_file_identity_change_during_read_is_not_accepted(evidence, monkeypatch):
    (evidence / "inputs/snapshot.json").write_bytes(b'{}')
    actual_fstat = inspector.os.fstat
    calls = []
    def changed_fstat(descriptor):
        value = actual_fstat(descriptor)
        calls.append(descriptor)
        if len(calls) == 2:
            return SimpleNamespace(st_dev=value.st_dev, st_ino=value.st_ino,
                                   st_size=value.st_size + 1, st_mtime_ns=value.st_mtime_ns)
        return value
    monkeypatch.setattr(inspector.os, "fstat", changed_fstat)
    with pytest.raises(ValueError, match="^evidence_changed_during_read$"):
        inspector.load("snapshot.json")


@pytest.mark.parametrize("name", ["../hierarchy.json", "/tmp/unrelated.json", "C:\\private.json", "other.json", None])
def test_output_cannot_choose_an_arbitrary_path(evidence, name):
    with pytest.raises(ValueError, match="^unknown_named_evidence_output$"):
        inspector.save_report(name, "{}\n")
    assert not (evidence / "reports").exists()


def test_output_is_exclusive_and_preserves_original_evidence(evidence):
    inspector.save_report("hierarchy.json", '{"synthetic": true}\n')
    target = evidence / "reports/hierarchy.json"
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        inspector.save_report("hierarchy.json", "{}\n")
    assert target.read_bytes() == before
    assert json.loads(before) == {"synthetic": True}


def test_linked_output_directory_is_rejected_without_writing(evidence):
    outside = evidence.parent / "external-output"
    outside.mkdir()
    (evidence / "reports").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="^linked_or_non_directory_evidence_path$"):
        inspector.save_report("hierarchy.json", "{}\n")
    assert list(outside.iterdir()) == []


def test_cli_rejects_absolute_snapshot_before_loading(evidence, monkeypatch):
    monkeypatch.setattr(inspector.sys, "argv", ["inspect", "--snapshot", "/etc/passwd"])
    with pytest.raises(SystemExit) as stopped:
        inspector.main()
    assert stopped.value.code == 2
