from __future__ import annotations

import base64
import hashlib
import json
import logging
import ssl
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager, closing
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import certifi
import httpx
import jwt
from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from jwt import PyJWKClient
from pydantic import BaseModel

DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "/var/lib/analyst-ai/backend.db"))
TELEGRAM_CLIENT_ID = os.environ["TELEGRAM_CLIENT_ID"]
TELEGRAM_CLIENT_SECRET = os.environ["TELEGRAM_CLIENT_SECRET"]
BACKEND_PUBLIC_URL = os.environ["BACKEND_PUBLIC_URL"].rstrip("/")
TELEGRAM_REDIRECT_URI = os.getenv(
    "TELEGRAM_REDIRECT_URI",
    f"{BACKEND_PUBLIC_URL}/auth/telegram/callback",
)
APP_DEEP_LINK = os.getenv("APP_DEEP_LINK", "analystai://auth")
FERNET_KEY = os.environ["FERNET_KEY"].encode()
FERNET = Fernet(FERNET_KEY)

TELEGRAM_ISSUER = "https://oauth.telegram.org"
TELEGRAM_AUTH_URL = "https://oauth.telegram.org/auth"
TELEGRAM_TOKEN_URL = "https://oauth.telegram.org/token"
TELEGRAM_JWKS_URL = "https://oauth.telegram.org/.well-known/jwks.json"
TINVEST_ACCOUNTS_URL = (
    "https://invest-public-api.tbank.ru/rest/"
    "tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts"
)
# Public Ministry root is pinned by its X.509 DER fingerprint. It is used ONLY
# for T-Invest requests, never for the general HTTPS trust store.
TINVEST_ROOT_CA_PATH = Path(__file__).resolve().parent / "certs" / "russian_trusted_root_ca.pem"
TINVEST_ROOT_CA_SHA256 = "d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31"

LOGIN_TX_TTL = 10 * 60
LOGIN_CODE_TTL = 5 * 60
SESSION_TTL = 30 * 24 * 60 * 60

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    try:
        from .autonomous_ai import init_autonomous_db, start_scheduler, stop_scheduler
    except ImportError:
        from autonomous_ai import init_autonomous_db, start_scheduler, stop_scheduler

    init_autonomous_db()
    scheduler_task = start_scheduler()
    try:
        yield
    finally:
        await stop_scheduler(scheduler_task)


app = FastAPI(
    title="Analyst AI Backend",
    version="0.1.0",
    lifespan=lifespan,
)
jwks_client = PyJWKClient(TELEGRAM_JWKS_URL)
logger = logging.getLogger(__name__)


class SessionExchange(BaseModel):
    code: str


class TInvestTokenPayload(BaseModel):
    token: str


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with closing(connect()) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_sub TEXT NOT NULL UNIQUE,
                telegram_id TEXT,
                name TEXT,
                username TEXT,
                picture TEXT,
                tinvest_token_encrypted BLOB,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS login_transactions (
                state TEXT PRIMARY KEY,
                verifier TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS login_codes (
                code_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                used INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            );
            """
        )
        db.commit()


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def purge_expired(db: sqlite3.Connection) -> None:
    now = int(time.time())
    db.execute("DELETE FROM login_transactions WHERE created_at < ?", (now - LOGIN_TX_TTL,))
    db.execute("DELETE FROM login_codes WHERE expires_at < ? OR used = 1", (now,))
    db.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))


def current_user(authorization: str | None = Header(default=None)) -> sqlite3.Row:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_session")
    raw = authorization[7:].strip()
    if not raw:
        raise HTTPException(status_code=401, detail="missing_session")

    with closing(connect()) as db:
        purge_expired(db)
        row = db.execute(
            """
            SELECT users.*
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at >= ?
            """,
            (hash_token(raw), int(time.time())),
        ).fetchone()
        db.commit()
    if row is None:
        raise HTTPException(status_code=401, detail="invalid_session")
    return row


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/auth/telegram/start")
def telegram_start() -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = b64url(hashlib.sha256(verifier.encode()).digest())
    now = int(time.time())

    with closing(connect()) as db:
        purge_expired(db)
        db.execute(
            "INSERT INTO login_transactions(state, verifier, created_at) VALUES (?, ?, ?)",
            (state, verifier, now),
        )
        db.commit()

    redirect_uri = TELEGRAM_REDIRECT_URI
    query = urlencode(
        {
            "client_id": TELEGRAM_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid profile",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return RedirectResponse(f"{TELEGRAM_AUTH_URL}?{query}", status_code=302)


def mobile_login_result(
    *,
    code: str | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Try to return to Android; keep a user-clickable fallback for browsers blocking deep links."""
    query = {"code": code} if code else {"error": error or "telegram_failed"}
    target = f"{APP_DEEP_LINK}?{urlencode(query)}"
    link_href = escape(target, quote=True)
    script_target = json.dumps(target).replace("<", "\\u003c").replace(">", "\\u003e")
    message = (
        "Telegram подтверждён. Возвращаем вас в Analyst AI."
        if code else
        "Авторизация не завершена. Вернитесь в Analyst AI, чтобы попробовать ещё раз."
    )
    page = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Возврат в Analyst AI</title>
<style>
  body {{ min-height: 100vh; display: grid; place-items: center; margin: 0;
          padding: 20px; box-sizing: border-box; background: #151c25;
          color: #f8fafc; font: 16px/1.5 system-ui, sans-serif; }}
  main {{ text-align: center; max-width: 440px; }}
  a {{ display: block; margin-top: 22px; padding: 14px 20px; border-radius: 12px;
       background: #229ed9; color: white; font-weight: 600; text-decoration: none; }}
  small {{ color: #a8b4c3; }}
</style>
</head>
<body>
<main>
  <h1>Analyst AI</h1>
  <p>{message}</p>
  <a href="{link_href}">Открыть Analyst AI</a>
  <p><small>Если приложение не открылось автоматически, нажмите кнопку выше.</small></p>
</main>
<script>window.location.replace({script_target});</script>
</body>
</html>"""
    return HTMLResponse(
        content=page,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store, private",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'",
        },
    )


@app.get("/api/auth/social/telegram/callback", include_in_schema=False)
@app.get(
    "/auth/telegram/callback",
    responses={
        400: {"description": "Invalid or expired Telegram login state."},
        401: {"description": "Telegram token exchange or ID token validation failed."},
    },
)
def telegram_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    if error is not None:
        return mobile_login_result(error="telegram_denied")
    if not code or not state:
        return mobile_login_result(error="telegram_invalid_response", status_code=400)
    with closing(connect()) as db:
        purge_expired(db)
        tx = db.execute(
            "SELECT verifier, created_at FROM login_transactions WHERE state = ?",
            (state,),
        ).fetchone()
        db.execute("DELETE FROM login_transactions WHERE state = ?", (state,))
        db.commit()

    if tx is None or int(time.time()) - tx["created_at"] > LOGIN_TX_TTL:
        return mobile_login_result(error="telegram_expired", status_code=400)

    redirect_uri = TELEGRAM_REDIRECT_URI
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                TELEGRAM_TOKEN_URL,
                auth=(TELEGRAM_CLIENT_ID, TELEGRAM_CLIENT_SECRET),
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": TELEGRAM_CLIENT_ID,
                    "code_verifier": tx["verifier"],
                },
            )
    except httpx.HTTPError:
        logger.exception("Telegram token exchange is unavailable")
        return mobile_login_result(error="telegram_unavailable", status_code=503)
    if response.status_code != 200:
        logger.warning("Telegram token exchange returned HTTP %s", response.status_code)
        return mobile_login_result(error="telegram_exchange_failed", status_code=401)

    try:
        id_token = response.json()["id_token"]
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=TELEGRAM_CLIENT_ID,
            issuer=TELEGRAM_ISSUER,
        )
        sub = str(claims["sub"])
    except (KeyError, ValueError, jwt.PyJWTError, TypeError):
        logger.exception("Telegram ID token is invalid")
        return mobile_login_result(error="telegram_invalid_token", status_code=401)
    except Exception:
        logger.exception("Telegram signing keys are temporarily unavailable")
        return mobile_login_result(error="telegram_unavailable", status_code=503)
    telegram_id = str(claims.get("id") or sub)
    now = int(time.time())

    with closing(connect()) as db:
        existing = db.execute(
            "SELECT id FROM users WHERE telegram_sub = ?",
            (sub,),
        ).fetchone()

        if existing is None:
            cursor = db.execute(
                """
                INSERT INTO users(
                    telegram_sub, telegram_id, name, username, picture,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sub,
                    telegram_id,
                    claims.get("name"),
                    claims.get("preferred_username"),
                    claims.get("picture"),
                    now,
                    now,
                ),
            )
            user_id = int(cursor.lastrowid)
        else:
            user_id = int(existing["id"])
            db.execute(
                """
                UPDATE users
                SET telegram_id = ?, name = ?, username = ?, picture = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    telegram_id,
                    claims.get("name"),
                    claims.get("preferred_username"),
                    claims.get("picture"),
                    now,
                    user_id,
                ),
            )

        one_time = secrets.token_urlsafe(40)
        db.execute(
            "INSERT INTO login_codes(code_hash, user_id, expires_at, used) VALUES (?, ?, ?, 0)",
            (hash_token(one_time), user_id, now + LOGIN_CODE_TTL),
        )
        db.commit()

    return mobile_login_result(code=one_time)


@app.post(
    "/auth/session",
    responses={
        401: {"description": "The one-time login code is invalid or expired."},
    },
)
def exchange_session(payload: SessionExchange) -> dict:
    now = int(time.time())
    code_hash = hash_token(payload.code.strip())

    with closing(connect()) as db:
        purge_expired(db)
        row = db.execute(
            """
            SELECT login_codes.user_id, users.telegram_id, users.name,
                   users.username, users.picture
            FROM login_codes
            JOIN users ON users.id = login_codes.user_id
            WHERE login_codes.code_hash = ? AND login_codes.used = 0
                  AND login_codes.expires_at >= ?
            """,
            (code_hash, now),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="invalid_login_code")

        db.execute("UPDATE login_codes SET used = 1 WHERE code_hash = ?", (code_hash,))
        session = secrets.token_urlsafe(48)
        db.execute(
            "INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (hash_token(session), row["user_id"], now + SESSION_TTL),
        )
        db.commit()

    return {
        "access_token": session,
        "expires_in": SESSION_TTL,
        "user": {
            "telegram_id": row["telegram_id"],
            "name": row["name"],
            "username": row["username"],
            "picture": row["picture"],
        },
    }


@app.get(
    "/me",
    responses={
        401: {"description": "Analyst AI session is missing, invalid, or expired."},
    },
)
def me(user: sqlite3.Row = Depends(current_user)) -> dict:
    return {
        "telegram_id": user["telegram_id"],
        "name": user["name"],
        "username": user["username"],
        "picture": user["picture"],
        "tinvest_connected": user["tinvest_token_encrypted"] is not None,
    }


@app.get(
    "/tinvest/status",
    responses={
        401: {"description": "Analyst AI session is missing, invalid, or expired."},
    },
)
def tinvest_status(user: sqlite3.Row = Depends(current_user)) -> dict[str, bool]:
    return {"connected": user["tinvest_token_encrypted"] is not None}


def tinvest_ssl_context() -> ssl.SSLContext:
    """Trust the fingerprint-verified Ministry CA only for T-Invest HTTPS."""
    try:
        certificate_bytes = TINVEST_ROOT_CA_PATH.read_bytes()
        certificate = x509.load_pem_x509_certificate(certificate_bytes)
        if certificate.fingerprint(hashes.SHA256()).hex() != TINVEST_ROOT_CA_SHA256:
            raise ValueError("T-Invest certificate fingerprint mismatch")
        context = ssl.create_default_context(cafile=certifi.where())
        context.load_verify_locations(cadata=certificate_bytes.decode("ascii"))
        return context
    except (OSError, ValueError, ssl.SSLError, UnicodeDecodeError) as exc:
        raise RuntimeError("T-Invest trusted certificate configuration is invalid") from exc


@app.post(
    "/tinvest/token",
    responses={
        400: {"description": "The T-Invest token is empty."},
        401: {"description": "Analyst AI session is invalid or expired."},
        422: {"description": "T-Invest rejected the access token."},
        502: {"description": "Unexpected response from T-Invest."},
        503: {"description": "T-Invest is unavailable or its TLS connection failed."},
        504: {"description": "T-Invest connection timed out."},
    },
)
def save_tinvest_token(
    payload: TInvestTokenPayload,
    user: sqlite3.Row = Depends(current_user),
) -> dict[str, bool]:
    token = payload.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="empty_tinvest_token")

    try:
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=7.0),
            verify=tinvest_ssl_context(),
            follow_redirects=False,
        ) as client:
            response = client.post(
                TINVEST_ACCOUNTS_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={},
            )
    except httpx.TimeoutException:
        logger.warning("T-Invest GetAccounts timed out")
        raise HTTPException(status_code=504, detail="tinvest_timeout") from None
    except httpx.TransportError as exc:
        # Never log the supplied access token or the upstream response body.
        transport_details = str(exc).lower()
        is_tls_error = any(word in transport_details for word in (
            "certificate", "ssl", "tls", "handshake",
        ))
        detail = "tinvest_tls_error" if is_tls_error else "tinvest_connection_failed"
        logger.warning("T-Invest GetAccounts transport failed (%s)", detail)
        raise HTTPException(status_code=503, detail=detail) from None
    except (RuntimeError, ssl.SSLError):
        logger.exception("Unable to initialize verified T-Invest TLS")
        raise HTTPException(status_code=503, detail="tinvest_tls_error") from None

    if response.status_code in (401, 403):
        # Do not confuse T-Invest API token rejection with an invalid
        # Analyst AI session (which is already handled by current_user).
        raise HTTPException(status_code=422, detail="invalid_tinvest_token")
    if response.status_code == 429:
        raise HTTPException(status_code=503, detail="tinvest_rate_limited")
    if response.status_code in (408, 504):
        raise HTTPException(status_code=504, detail="tinvest_timeout")
    if response.status_code >= 500:
        logger.warning("T-Invest GetAccounts returned upstream HTTP %d", response.status_code)
        raise HTTPException(status_code=503, detail="tinvest_upstream_unavailable")
    if response.status_code != 200:
        logger.warning("T-Invest GetAccounts returned unexpected HTTP %d", response.status_code)
        raise HTTPException(status_code=502, detail="tinvest_unexpected_status")

    try:
        accounts = response.json()["accounts"]
        if not isinstance(accounts, list):
            raise ValueError("accounts is not a list")
    except (ValueError, TypeError, KeyError):
        logger.warning("T-Invest GetAccounts returned an unexpected response schema")
        raise HTTPException(status_code=502, detail="tinvest_invalid_response") from None

    # Save only a successfully validated token, never the raw upstream payload.
    encrypted = FERNET.encrypt(token.encode())
    with closing(connect()) as db:
        db.execute(
            "UPDATE users SET tinvest_token_encrypted = ?, updated_at = ? WHERE id = ?",
            (encrypted, int(time.time()), user["id"]),
        )
        db.commit()

    return {"connected": True}


@app.delete(
    "/tinvest/token",
    responses={
        401: {"description": "Analyst AI session is missing, invalid, or expired."},
    },
)
def delete_tinvest_token(user: sqlite3.Row = Depends(current_user)) -> dict[str, bool]:
    with closing(connect()) as db:
        db.execute(
            "UPDATE users SET tinvest_token_encrypted = NULL, updated_at = ? WHERE id = ?",
            (int(time.time()), user["id"]),
        )
        db.commit()
    return {"connected": False}

try:
    from .tinvest_portfolio import router as tinvest_portfolio_router
except ImportError:
    from tinvest_portfolio import router as tinvest_portfolio_router

app.include_router(tinvest_portfolio_router)

try:
    from .autonomous_ai import router as autonomous_ai_router
except ImportError:
    from autonomous_ai import router as autonomous_ai_router

app.include_router(autonomous_ai_router)
