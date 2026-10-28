"""Version identity changes with deployed code, never with data or credentials."""
from backend import server_version


def test_same_sources_and_restart_keep_version(tmp_path):
    (tmp_path / "app.py").write_bytes(b"print('synthetic')\n")
    (tmp_path / "requirements.txt").write_bytes(b"fastapi==0.120.0\n")
    before = server_version.source_revision(tmp_path)
    assert server_version.source_revision(tmp_path) == before
    (tmp_path / "app.py").touch()
    assert server_version.source_revision(tmp_path) == before


def test_code_and_dependency_changes_advance_identity_and_rollback_restores_it(tmp_path):
    source = tmp_path / "app.py"
    source.write_bytes(b"old\n")
    before = server_version.source_revision(tmp_path)
    source.write_bytes(b"new\n")
    assert server_version.source_revision(tmp_path) != before
    source.write_bytes(b"old\n")
    assert server_version.source_revision(tmp_path) == before
    requirements = tmp_path / "requirements.txt"
    requirements.write_bytes(b"dependency==1\n")
    with_dependencies = server_version.source_revision(tmp_path)
    assert with_dependencies != before
    requirements.write_bytes(b"dependency==2\n")
    assert server_version.source_revision(tmp_path) != with_dependencies


def test_data_test_files_and_credentials_do_not_change_source_version(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_bytes(b"synthetic code\n")
    before = server_version.source_revision(tmp_path)
    monkeypatch.setenv("TIMEWEB_AI_TOKEN", "synthetic-secret-never-returned")
    monkeypatch.setenv("AI_MODEL", "synthetic-model")
    (tmp_path / "backend.db").write_bytes(b"synthetic private data")
    (tmp_path / "backend.env").write_bytes(b"synthetic credential")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_case.py").write_bytes(b"synthetic test")
    assert server_version.source_revision(tmp_path) == before


def test_module_addition_removal_and_rename_change_identity(tmp_path):
    source = tmp_path / "app.py"
    source.write_bytes(b"synthetic\n")
    before = server_version.source_revision(tmp_path)
    module = tmp_path / "other.py"
    module.write_bytes(b"synthetic module\n")
    assert server_version.source_revision(tmp_path) != before
    module.unlink()
    assert server_version.source_revision(tmp_path) == before
    source.rename(tmp_path / "renamed.py")
    assert server_version.source_revision(tmp_path) != before


def test_metadata_is_snapshot_of_running_process_and_cannot_be_mutated():
    expected = server_version.current()
    assert len(expected["source_revision"]) == 64
    assert expected["version"] == "srv-" + expected["source_revision"][:12]
    assert expected["schema_version"] == 1
    response = server_version.current()
    response["version"] = "mutated"
    assert server_version.current() == expected
