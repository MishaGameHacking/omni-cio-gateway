from __future__ import annotations

from pathlib import Path

import pytest

from apps.api import timeweb_postgres_tls
from scripts import timeweb_postgres_production_dataplane as dataplane
from scripts import timeweb_postgres_production_network_scope as scope


_PUBLIC_ADDRESS = "8.8.8.8"
_OTHER_PUBLIC_ADDRESS = "8.8.4.4"


class _Api:
    pass


def test_dataplane_proof_exports_only_after_live_bound_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github_env = tmp_path / "github-env"
    monkeypatch.setenv("GITHUB_ENV", str(github_env))
    observed: list[str] = []

    monkeypatch.setattr(
        scope,
        "verify_network_scope",
        lambda *_args, **_kwargs: _PUBLIC_ADDRESS,
    )
    monkeypatch.setattr(
        timeweb_postgres_tls,
        "install_timeweb_postgres_ca",
        lambda: tmp_path / "provider-ca.crt",
    )

    def prove(*_args: object, public_hostaddr: str, **_kwargs: object) -> str:
        observed.append(public_hostaddr)
        return public_hostaddr

    monkeypatch.setattr(
        timeweb_postgres_tls,
        "probe_timeweb_postgres_bound_public_transport",
        prove,
    )

    actual = dataplane.prove_production_dataplane(
        api=_Api(),
        project_id="42",
        target_host="db.twc1.net",
        verifier_cidr="8.8.4.4/32",
        bootstrap_dsn="provider-dsn",
    )

    assert actual == _PUBLIC_ADDRESS
    assert observed == [_PUBLIC_ADDRESS]
    assert (
        github_env.read_text(encoding="utf-8")
        == f"{dataplane.PUBLIC_HOSTADDR_ENV}={_PUBLIC_ADDRESS}\n"
    )


def test_dataplane_timeout_rechecks_stable_control_plane(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ENV", str(tmp_path / "github-env"))
    calls = 0

    def stable(*_args: object, **_kwargs: object) -> str:
        nonlocal calls
        calls += 1
        return _PUBLIC_ADDRESS

    monkeypatch.setattr(scope, "verify_network_scope", stable)
    monkeypatch.setattr(
        timeweb_postgres_tls,
        "install_timeweb_postgres_ca",
        lambda: tmp_path / "provider-ca.crt",
    )
    monkeypatch.setattr(
        timeweb_postgres_tls,
        "probe_timeweb_postgres_bound_public_transport",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            timeweb_postgres_tls.TimewebPostgresTlsError(
                "TIMEWEB_PG_TLS_TCP_TIMEOUT"
            )
        ),
    )

    with pytest.raises(
        dataplane.ProductionDataplaneStopped,
        match="TIMEWEB_PG_PRODUCTION_DATAPLANE_TCP_TIMEOUT_CONTROL_PLANE_STABLE",
    ):
        dataplane.prove_production_dataplane(
            api=_Api(),
            project_id="42",
            target_host="db.twc1.net",
            verifier_cidr="8.8.4.4/32",
            bootstrap_dsn="provider-dsn",
        )

    assert calls == 2


def test_dataplane_timeout_prefers_public_binding_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ENV", str(tmp_path / "github-env"))
    addresses = iter((_PUBLIC_ADDRESS, _OTHER_PUBLIC_ADDRESS))
    monkeypatch.setattr(
        scope,
        "verify_network_scope",
        lambda *_args, **_kwargs: next(addresses),
    )
    monkeypatch.setattr(
        timeweb_postgres_tls,
        "install_timeweb_postgres_ca",
        lambda: tmp_path / "provider-ca.crt",
    )
    monkeypatch.setattr(
        timeweb_postgres_tls,
        "probe_timeweb_postgres_bound_public_transport",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            timeweb_postgres_tls.TimewebPostgresTlsError(
                "TIMEWEB_PG_TLS_TCP_TIMEOUT"
            )
        ),
    )

    with pytest.raises(
        dataplane.ProductionDataplaneStopped,
        match="TIMEWEB_PG_PRODUCTION_DATAPLANE_PUBLIC_IPV4_DRIFT",
    ):
        dataplane.prove_production_dataplane(
            api=_Api(),
            project_id="42",
            target_host="db.twc1.net",
            verifier_cidr="8.8.4.4/32",
            bootstrap_dsn="provider-dsn",
        )


def test_dataplane_nontransient_tls_failure_is_not_hidden(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ENV", str(tmp_path / "github-env"))
    calls = 0

    def scope_once(*_args: object, **_kwargs: object) -> str:
        nonlocal calls
        calls += 1
        return _PUBLIC_ADDRESS

    monkeypatch.setattr(scope, "verify_network_scope", scope_once)
    monkeypatch.setattr(
        timeweb_postgres_tls,
        "install_timeweb_postgres_ca",
        lambda: tmp_path / "provider-ca.crt",
    )
    monkeypatch.setattr(
        timeweb_postgres_tls,
        "probe_timeweb_postgres_bound_public_transport",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            timeweb_postgres_tls.TimewebPostgresTlsError(
                "TIMEWEB_PG_TLS_CERT_VERIFY_FAILED"
            )
        ),
    )

    with pytest.raises(
        dataplane.ProductionDataplaneStopped,
        match="TIMEWEB_PG_TLS_CERT_VERIFY_FAILED",
    ):
        dataplane.prove_production_dataplane(
            api=_Api(),
            project_id="42",
            target_host="db.twc1.net",
            verifier_cidr="8.8.4.4/32",
            bootstrap_dsn="provider-dsn",
        )

    assert calls == 1


def test_dataplane_export_requires_github_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_ENV", raising=False)

    with pytest.raises(
        dataplane.ProductionDataplaneStopped,
        match="TIMEWEB_PG_PRODUCTION_DATAPLANE_GITHUB_ENV_REQUIRED",
    ):
        dataplane._export_public_hostaddr(_PUBLIC_ADDRESS)
