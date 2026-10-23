"""Telegram browser login that does not require Moscow-server egress to Telegram.

The production Moscow network can serve the application and reach ordinary HTTPS
hosts, but it cannot establish an IPv4/IPv6 connection to oauth.telegram.org.
Telegram's official browser Login library completes PKCE inside the user's popup
and returns a signed ``id_token`` to this origin. This module verifies that token
locally against a deployment-pinned JWKS snapshot, then reuses the existing
one-time Android deep-link/session handoff from :mod:`app`.

The legacy manual OIDC callback remains registered for old browser tabs, but the
canonical ``/auth/telegram/start`` route is replaced at import time. Uvicorn must
therefore load ``telegram_browser_app:app`` rather than ``app:app``.
"""
from __future__ import annotations

import json
import logging
import re
import secrets
import time
from contextlib import closing
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import jwt
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

try:
    from . import app as legacy
except ImportError:  # Production runs with /opt/analyst-ai/backend as cwd.
    import app as legacy

LOGGER = logging.getLogger(__name__)
TELEGRAM_LOGIN_SCRIPT = "https://oauth.telegram.org/js/telegram-login.js?3"
TELEGRAM_JWKS_PATH = Path(__file__).resolve().with_name("telegram_jwks.json")
MAX_ID_TOKEN_LENGTH = 16_384
BEGIN_IMMEDIATE = "BEGIN IMMEDIATE"


class TelegramBrowserToken(BaseModel):
    state: str = Field(min_length=32, max_length=256)
    id_token: str = Field(min_length=64, max_length=MAX_ID_TOKEN_LENGTH)


class TelegramTokenError(ValueError):
    """The browser supplied a token that cannot authenticate a Telegram user."""


class TelegramKeyUnavailable(RuntimeError):
    """The pinned Telegram signing-key set is absent or structurally invalid."""


def _safe_script_value(value: str) -> str:
    return json.dumps(value, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e")


def _deep_link(*, code: str | None = None, error: str | None = None) -> str:
    query = {"code": code} if code else {"error": error or "telegram_failed"}
    return f"{legacy.APP_DEEP_LINK}?{urlencode(query)}"


def _json_result(
    *,
    code: str | None = None,
    error: str | None = None,
    message: str,
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        {
            "deep_link": _deep_link(code=code, error=error),
            "message": message,
        },
        status_code=status_code,
        headers={
            "Cache-Control": "no-store, private",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Cross-Origin-Resource-Policy": "same-origin",
        },
    )


def _remove_legacy_start_route() -> None:
    retained = []
    removed = 0
    for route in legacy.app.router.routes:
        methods = getattr(route, "methods", None) or set()
        if getattr(route, "path", None) == "/auth/telegram/start" and "GET" in methods:
            removed += 1
            continue
        retained.append(route)
    if removed != 1:
        raise RuntimeError(f"Expected one legacy Telegram start route, found {removed}")
    legacy.app.router.routes[:] = retained


def _login_page(state: str, nonce: str) -> HTMLResponse:
    client_id = str(legacy.TELEGRAM_CLIENT_ID)
    if re.fullmatch(r"[1-9]\d{3,24}", client_id) is None:
        raise RuntimeError("TELEGRAM_CLIENT_ID must be a numeric BotFather client id")

    csp_nonce = secrets.token_urlsafe(24)
    nonce_attr = escape(csp_nonce, quote=True)
    state_js = _safe_script_value(state)
    login_nonce_js = _safe_script_value(nonce)
    client_id_js = _safe_script_value(client_id)
    complete_url_js = _safe_script_value(f"{legacy.BACKEND_PUBLIC_URL}/auth/telegram/complete")

    page = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>Вход в Analyst AI</title>
<style nonce="{nonce_attr}">
  :root {{ color-scheme: light dark; --accent:#1686b4; --accent2:#7654c7;
           --bg:#f4f7ff; --card:rgba(255,255,255,.86); --text:#101318;
           --muted:#596171; --danger:#b3263c; --border:rgba(87,97,206,.42); }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg:#06131f; --card:rgba(10,39,55,.9);
           --text:#f7f9ff; --muted:#bac3d1; --danger:#ff8995; --border:rgba(120,113,255,.62); }} }}
  * {{ box-sizing:border-box; }}
  body {{ min-height:100vh; margin:0; padding:max(24px,env(safe-area-inset-top)) 20px
         max(24px,env(safe-area-inset-bottom)); display:grid; place-items:center;
         background:radial-gradient(circle at 82% 7%,rgba(125,91,236,.17),transparent 32%),
                    radial-gradient(circle at 9% 92%,rgba(34,185,204,.16),transparent 35%),var(--bg);
         color:var(--text); font:17px/1.48 system-ui,-apple-system,"Segoe UI",sans-serif; }}
  main {{ width:min(100%,520px); padding:30px 24px; border:1px solid var(--border);
          border-radius:28px; background:var(--card); box-shadow:0 12px 34px rgba(13,25,67,.16);
          backdrop-filter:blur(14px); }}
  .mark {{ width:76px; height:76px; margin:0 auto 20px; display:grid; place-items:center;
           border-radius:24px; font-size:38px; background:linear-gradient(145deg,#2a9fc4,#7654c7);
           color:white; box-shadow:0 12px 28px rgba(81,83,193,.25); }}
  h1 {{ margin:0; text-align:center; font-size:clamp(30px,8vw,44px); line-height:1.1; }}
  p {{ color:var(--muted); }}
  .privacy {{ margin:18px 0 24px; padding:16px; border-radius:18px;
              background:color-mix(in srgb,var(--accent) 8%,transparent); }}
  button,a {{ width:100%; min-height:56px; border:0; border-radius:18px; font:700 18px/1.2 inherit;
              display:flex; align-items:center; justify-content:center; text-decoration:none; }}
  button {{ cursor:pointer; color:white; background:linear-gradient(100deg,var(--accent),var(--accent2));
            box-shadow:0 10px 24px rgba(49,113,183,.24); }}
  button:disabled {{ opacity:.62; cursor:wait; }}
  a {{ margin-top:14px; color:var(--accent); border:1px solid var(--border); background:transparent; }}
  #status {{ min-height:48px; margin:18px 2px 0; text-align:center; }}
  #status.error {{ color:var(--danger); }}
  small {{ display:block; margin-top:22px; color:var(--muted); text-align:center; }}
</style>
<script nonce="{nonce_attr}" async src="{TELEGRAM_LOGIN_SCRIPT}"></script>
</head>
<body>
<main>
  <div class="mark" aria-hidden="true">✦</div>
  <h1>Вход через Telegram</h1>
  <p class="privacy">Telegram подтверждает вашу учётную запись в защищённом окне.
     Analyst AI получает только подписанный результат входа и не получает пароль Telegram.</p>
  <button id="telegram-login" type="button">Продолжить в Telegram</button>
  <a id="open-app" href="{escape(legacy.APP_DEEP_LINK, quote=True)}" hidden>Открыть Analyst AI</a>
  <p id="status" role="status" aria-live="polite">Нажмите кнопку и подтвердите вход.</p>
  <small>После подтверждения вы автоматически вернётесь в приложение.</small>
</main>
<script nonce="{nonce_attr}">
(() => {{
  "use strict";
  const clientId = Number({client_id_js});
  const state = {state_js};
  const loginNonce = {login_nonce_js};
  const completeUrl = {complete_url_js};
  const button = document.getElementById("telegram-login");
  const status = document.getElementById("status");
  const openApp = document.getElementById("open-app");

  function setStatus(message, failed = false) {{
    status.textContent = message;
    status.className = failed ? "error" : "";
  }}

  function returnToApp(deepLink, message) {{
    if (typeof deepLink !== "string" || !deepLink.startsWith("analystai://auth?")) {{
      throw new Error("invalid_deep_link");
    }}
    openApp.href = deepLink;
    openApp.hidden = false;
    setStatus(message || "Возвращаем вас в Analyst AI.");
    window.location.replace(deepLink);
  }}

  async function finishTelegramLogin(result) {{
    button.disabled = true;
    if (!result || result.error || typeof result.id_token !== "string") {{
      setStatus("Telegram не завершил вход. Закройте окно и повторите попытку.", true);
      button.disabled = false;
      return;
    }}
    try {{
      const response = await fetch(completeUrl, {{
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: {{"Content-Type":"application/json","X-Requested-With":"AnalystAI"}},
        body: JSON.stringify({{state: state, id_token: result.id_token}})
      }});
      const body = await response.json();
      if (body && body.deep_link) {{
        returnToApp(body.deep_link, body.message);
        return;
      }}
      setStatus("Сервер не подтвердил вход. Повторите попытку.", true);
      button.disabled = false;
    }} catch (_error) {{
      setStatus("Не удалось передать подтверждение в Analyst AI. Проверьте сеть и повторите.", true);
      button.disabled = false;
    }}
  }}

  function beginTelegramLogin() {{
    const login = window.Telegram && window.Telegram.Login;
    if (!login || typeof login.auth !== "function") {{
      setStatus("Модуль Telegram ещё загружается. Подождите несколько секунд и нажмите снова.", true);
      return;
    }}
    setStatus("Откройте окно Telegram и подтвердите вход.");
    login.auth({{client_id: clientId, scope:["profile"], lang:"ru", nonce:loginNonce}}, finishTelegramLogin);
  }}

  button.addEventListener("click", beginTelegramLogin);
}})();
</script>
</body>
</html>"""
    return HTMLResponse(
        page,
        headers={
            "Cache-Control": "no-store, private",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Cross-Origin-Opener-Policy": "same-origin-allow-popups",
            "Cross-Origin-Resource-Policy": "same-origin",
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src 'nonce-{csp_nonce}' https://oauth.telegram.org; "
                f"style-src 'nonce-{csp_nonce}'; "
                "connect-src 'self'; img-src data: https:; "
                "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
            ),
        },
    )


def _consume_transaction(state: str) -> str | None:
    now = int(time.time())
    with closing(legacy.connect()) as db:
        db.execute(BEGIN_IMMEDIATE)
        legacy.purge_expired(db)
        transaction = db.execute(
            "SELECT verifier, created_at FROM login_transactions WHERE state = ?",
            (state,),
        ).fetchone()
        db.execute("DELETE FROM login_transactions WHERE state = ?", (state,))
        db.commit()
    if transaction is None or now - int(transaction["created_at"]) > legacy.LOGIN_TX_TTL:
        return None
    return str(transaction["verifier"])


def _load_pinned_key(token: str):
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as error:
        raise TelegramTokenError("invalid_header") from error
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise TelegramTokenError("unsupported_signing_header")
    kid = header["kid"]
    try:
        if TELEGRAM_JWKS_PATH.is_symlink():
            raise TelegramKeyUnavailable("jwks_symlink")
        payload = json.loads(TELEGRAM_JWKS_PATH.read_text(encoding="utf-8"))
        keys = payload.get("keys")
        if not isinstance(keys, list):
            raise TelegramKeyUnavailable("jwks_keys_missing")
        matches = [
            key for key in keys
            if isinstance(key, dict)
            and key.get("kid") == kid
            and key.get("alg") == "RS256"
            and key.get("kty") == "RSA"
            and key.get("use", "sig") == "sig"
            and ("key_ops" not in key or "verify" in key.get("key_ops", []))
        ]
        if len(matches) != 1:
            raise TelegramKeyUnavailable("jwks_kid_unavailable")
        return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(matches[0]))
    except TelegramKeyUnavailable:
        raise
    except (OSError, ValueError, TypeError) as error:
        raise TelegramKeyUnavailable("jwks_invalid") from error


def _nonce_matches(received: object, expected: object) -> bool:
    # Our login nonces are nonempty ASCII token_urlsafe strings. compare_digest
    # rejects non-ASCII str with TypeError; malformed signed claims must instead
    # follow the ordinary invalid-token response without relaxing signature checks.
    if not isinstance(received, str) or not isinstance(expected, str):
        return False
    if not received or not expected or not received.isascii() or not expected.isascii():
        return False
    return secrets.compare_digest(received, expected)


def verify_browser_id_token(token: str, expected_nonce: str) -> dict:
    key = _load_pinned_key(token)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=legacy.TELEGRAM_CLIENT_ID,
            issuer=legacy.TELEGRAM_ISSUER,
            leeway=60,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
        )
    except jwt.PyJWTError as error:
        raise TelegramTokenError("invalid_claims_or_signature") from error
    nonce = claims.get("nonce")
    if not _nonce_matches(nonce, expected_nonce):
        raise TelegramTokenError("nonce_mismatch")
    subject = claims.get("sub")
    if not isinstance(subject, (str, int)) or not str(subject).strip() or len(str(subject)) > 256:
        raise TelegramTokenError("invalid_subject")
    return claims


def _issue_login_code(claims: dict) -> str:
    subject = str(claims["sub"])
    telegram_id = str(claims.get("id") or subject)
    now = int(time.time())
    with closing(legacy.connect()) as db:
        db.execute(BEGIN_IMMEDIATE)
        existing = db.execute(
            "SELECT id FROM users WHERE telegram_sub = ?",
            (subject,),
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
                    subject,
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
            (legacy.hash_token(one_time), user_id, now + legacy.LOGIN_CODE_TTL),
        )
        db.commit()
    return one_time


_remove_legacy_start_route()


@legacy.app.get(
    "/auth/telegram/start",
    response_class=HTMLResponse,
    responses={503: {"description": "Telegram browser login is not configured."}},
)
def telegram_browser_start() -> HTMLResponse:
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    now = int(time.time())
    with closing(legacy.connect()) as db:
        db.execute(BEGIN_IMMEDIATE)
        legacy.purge_expired(db)
        db.execute(
            "INSERT INTO login_transactions(state, verifier, created_at) VALUES (?, ?, ?)",
            (state, nonce, now),
        )
        db.commit()
    return _login_page(state, nonce)


@legacy.app.post(
    "/auth/telegram/complete",
    responses={
        400: {"description": "The browser login transaction expired."},
        401: {"description": "Telegram ID token validation failed."},
        503: {"description": "Pinned Telegram signing keys are unavailable."},
    },
)
def telegram_browser_complete(payload: TelegramBrowserToken, request: Request) -> JSONResponse:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != legacy.BACKEND_PUBLIC_URL:
        return _json_result(
            error="telegram_invalid_response",
            message="Источник подтверждения Telegram не совпал с Analyst AI.",
            status_code=400,
        )

    expected_nonce = _consume_transaction(payload.state)
    if expected_nonce is None:
        return _json_result(
            error="telegram_expired",
            message="Время подтверждения истекло. Начните вход заново.",
            status_code=400,
        )

    try:
        claims = verify_browser_id_token(payload.id_token, expected_nonce)
    except TelegramKeyUnavailable:
        LOGGER.exception("Pinned Telegram signing keys are unavailable")
        return _json_result(
            error="telegram_unavailable",
            message="Ключи проверки Telegram временно недоступны. Повторите позже.",
            status_code=503,
        )
    except TelegramTokenError:
        LOGGER.warning("Telegram browser ID token did not pass validation")
        return _json_result(
            error="telegram_invalid_token",
            message="Telegram не подтвердил подлинность входа. Начните вход заново.",
            status_code=401,
        )

    one_time = _issue_login_code(claims)
    return _json_result(
        code=one_time,
        message="Telegram подтверждён. Возвращаем вас в Analyst AI.",
    )


app = legacy.app
