from __future__ import annotations

from pathlib import Path


repo_path = Path("omni_cio/persistence/repository.py")
repo = repo_path.read_text(encoding="utf-8")

repo = repo.replace(
    '        )\n\ndef _persist_tenant(connection: ConnectionLike, record: TenantV1) -> None:',
    '        )\n\n\ndef _persist_tenant(connection: ConnectionLike, record: TenantV1) -> None:',
    1,
)
repo = repo.replace('        return format(value, "")', '        return format(value, "f")', 1)

old_incident = '''    revision_hash = model_record_sha256(record)
    existing = connection.execute(
        "SELECT revision FROM omni_cio_v10.incident_revisions "
        "WHERE incident_id = %s AND record_sha256 = %s",
        (record.incident_id, revision_hash),
    ).fetchone()
    if existing is not None:
        revision = int(existing[0])
    else:
        connection.execute(
            "SELECT incident_id FROM omni_cio_v10.incidents "
            "WHERE incident_id = %s FOR UPDATE",
            (record.incident_id,),
        )
        row = connection.execute(
            "SELECT COALESCE(MAX(revision), 0) + 1 FROM omni_cio_v10.incident_revisions "
            "WHERE incident_id = %s",
            (record.incident_id,),
        ).fetchone()
        if row is None:
            raise PersistenceConflictError("cannot allocate incident revision")
        revision = int(row[0])
        connection.execute(
            "INSERT INTO omni_cio_v10.incident_revisions "
            "(incident_id, revision, status, revised_at, record_sha256) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                record.incident_id,
                revision,
                record.status.value,
                _utc(record.opened_at),
                revision_hash,
            ),
        )
'''
new_incident = '''    revision_hash = model_record_sha256(record)
    connection.execute(
        "SELECT incident_id FROM omni_cio_v10.incidents "
        "WHERE incident_id = %s FOR UPDATE",
        (record.incident_id,),
    )
    existing = connection.execute(
        "SELECT revision FROM omni_cio_v10.incident_revisions "
        "WHERE incident_id = %s AND record_sha256 = %s",
        (record.incident_id, revision_hash),
    ).fetchone()
    if existing is not None:
        revision = int(existing[0])
    else:
        row = connection.execute(
            "SELECT COALESCE(MAX(revision), 0) + 1 FROM omni_cio_v10.incident_revisions "
            "WHERE incident_id = %s",
            (record.incident_id,),
        ).fetchone()
        if row is None:
            raise PersistenceConflictError("cannot allocate incident revision")
        revision = int(row[0])
        connection.execute(
            "INSERT INTO omni_cio_v10.incident_revisions "
            "(incident_id, revision, status, revised_at, record_sha256) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                record.incident_id,
                revision,
                record.status.value,
                _utc(record.opened_at),
                revision_hash,
            ),
        )
'''
if old_incident not in repo:
    raise SystemExit("incident revision block not found")
repo = repo.replace(old_incident, new_incident, 1)
repo_path.write_text(repo, encoding="utf-8", newline="\n")

rehearsal_path = Path("scripts/rehearse_v10_wp13_persistence.py")
rehearsal = rehearsal_path.read_text(encoding="utf-8")

migration_anchor = '''def _expect_database_failure(connection: psycopg.Connection[Any], sql: str) -> None:
'''
concurrency_helper = '''def _concurrent_catalog_replay(
    dsn: str,
    catalog: CanonicalDomainCatalogV1,
) -> int:
    barrier = threading.Barrier(2)

    def worker() -> int:
        with psycopg.connect(dsn) as connection:
            barrier.wait(timeout=10)
            return PostgresDomainRepository(connection).persist_catalog(catalog)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker) for _ in range(2)]
        revisions = [future.result(timeout=60) for future in futures]

    if len(set(revisions)) != 1:
        raise AssertionError(
            f"concurrent immutable replay produced different revisions: {revisions!r}"
        )
    return revisions[0]


'''
if migration_anchor not in rehearsal:
    raise SystemExit("rehearsal helper anchor not found")
rehearsal = rehearsal.replace(migration_anchor, concurrency_helper + migration_anchor, 1)

old_signature = '''def _exercise(
    connection: psycopg.Connection[Any],
    *,
    migration_race_pass: bool,
) -> dict[str, Any]:
'''
new_signature = '''def _exercise(
    connection: psycopg.Connection[Any],
    *,
    dsn: str,
    migration_race_pass: bool,
) -> dict[str, Any]:
'''
if old_signature not in rehearsal:
    raise SystemExit("exercise signature not found")
rehearsal = rehearsal.replace(old_signature, new_signature, 1)

roundtrip_anchor = '''    roundtripped = load_catalog(connection)
    if roundtripped != catalog:
        raise AssertionError("canonical catalog round-trip changed identity or scope")

'''
concurrency_exercise = '''    roundtripped = load_catalog(connection)
    if roundtripped != catalog:
        raise AssertionError("canonical catalog round-trip changed identity or scope")

    acknowledged_incident = catalog.incidents[0].model_copy(
        update={"status": IncidentStatus.ACKNOWLEDGED}
    )
    acknowledged_catalog = CanonicalDomainCatalogV1.model_validate(
        {
            **catalog.model_dump(mode="python"),
            "incidents": (acknowledged_incident,),
        }
    )
    concurrent_revision = _concurrent_catalog_replay(dsn, acknowledged_catalog)
    if load_catalog(connection) != acknowledged_catalog:
        raise AssertionError("concurrent incident revision replay changed durable state")

'''
if roundtrip_anchor not in rehearsal:
    raise SystemExit("round-trip anchor not found")
rehearsal = rehearsal.replace(roundtrip_anchor, concurrency_exercise, 1)

rehearsal = rehearsal.replace(
    '        "state_revision": first_revision,\n',
    '        "state_revision": concurrent_revision,\n',
    1,
)
rehearsal = rehearsal.replace(
    '        "conflicting_replay_rejected": True,\n',
    '        "conflicting_replay_rejected": True,\n        "concurrent_write_idempotency": True,\n',
    1,
)

old_call = '''                _exercise(connection, migration_race_pass=migration_race_pass)
'''
new_call = '''                _exercise(
                    connection,
                    dsn=dsn,
                    migration_race_pass=migration_race_pass,
                )
'''
if old_call not in rehearsal:
    raise SystemExit("exercise call not found")
rehearsal = rehearsal.replace(old_call, new_call, 1)

rehearsal_path.write_text(rehearsal, encoding="utf-8", newline="\n")
