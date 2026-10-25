"""Public APK delivery while the private backend is unavailable.

Uses the existing release-channel contract and byte verification. This app
does not create a database, accept a session, publish or certify a release.
"""
from __future__ import annotations

from typing import NoReturn

from fastapi import FastAPI, HTTPException

if __package__:
    from .client_updates import install_routes
else:
    from client_updates import install_routes


def _private_database_unavailable() -> NoReturn:
    """Public update requests must never open a private database."""
    raise RuntimeError("private_database_unavailable")


def _reject_unrestored_session() -> NoReturn:
    """No supplied token authorizes a private session in this service."""
    raise HTTPException(
        status_code=401,
        detail="authentication_required",
        headers={"Cache-Control": "no-store", "WWW-Authenticate": "Bearer"},
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="Analyst AI public updates",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )
    install_routes(app, _private_database_unavailable, _reject_unrestored_session)
    return app
