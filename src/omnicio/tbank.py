"""Thin T-Invest API adapter for owner broker connectivity."""

from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Literal

TBankEnvironment = Literal["prod", "sandbox"]

logger = logging.getLogger(__name__)

_ENDPOINTS: dict[str, str] = {
    "prod": (
        "https://invest-public-api.tbank.ru/rest/"
        "tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts"
    ),
    "sandbox": (
        "https://sandbox-invest-public-api.tbank.ru/rest/"
        "tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts"
    ),
}


class TBankError(RuntimeError):
    """Base T-Invest provider failure that never contains the submitted token."""


class TBankTokenRejected(TBankError):
    """The provider rejected or cannot authorize the submitted token."""


class TBankUnavailable(TBankError):
    """The provider cannot be reached or returned an unusable response."""


@dataclass(frozen=True, slots=True)
class TBankAccount:
    id: str
    name: str
    type: str
    status: str


@dataclass(frozen=True, slots=True)
class TBankInvestClient:
    timeout_seconds: int = 10

    def get_accounts(
        self,
        token: str,
        environment: TBankEnvironment,
    ) -> list[TBankAccount]:
        clean_token = _validate_token(token)
        endpoint = _ENDPOINTS.get(environment)
        if endpoint is None:
            raise TBankUnavailable("unsupported T-Invest environment")

        request = urllib.request.Request(
            endpoint,
            data=json.dumps({"status": "ACCOUNT_STATUS_OPEN"}).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {clean_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                raw = response.read().decode()
        except urllib.error.HTTPError as exc:
            tracking_id = exc.headers.get("x-tracking-id", "")
            logger.warning(
                "T-Invest request failed status=%s tracking_id=%s",
                exc.code,
                tracking_id or "-",
            )
            if exc.code in {401, 403}:
                raise TBankTokenRejected("T-Invest token was rejected") from exc
            if exc.code == 429 or exc.code >= 500:
                raise TBankUnavailable(
                    f"T-Invest API unavailable: HTTP {exc.code}"
                ) from exc
            raise TBankUnavailable(
                f"T-Invest API rejected request: HTTP {exc.code}"
            ) from exc
        except urllib.error.URLError as exc:
            reason = exc.reason
            reason_name = type(reason).__name__
            logger.warning(
                "T-Invest network failure reason=%s",
                reason_name,
            )
            if isinstance(reason, ssl.SSLCertVerificationError):
                raise TBankUnavailable(
                    "T-Invest TLS certificate verification failed"
                ) from exc
            raise TBankUnavailable(
                f"T-Invest API unavailable: {reason_name}"
            ) from exc
        except TimeoutError as exc:
            logger.warning("T-Invest request timed out")
            raise TBankUnavailable("T-Invest API request timed out") from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TBankUnavailable("T-Invest API returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise TBankUnavailable("T-Invest API returned invalid payload")
        items = payload.get("accounts")
        if not isinstance(items, list):
            raise TBankUnavailable("T-Invest API response has no accounts list")

        accounts: list[TBankAccount] = []
        for item in items:
            if not isinstance(item, dict):
                raise TBankUnavailable("T-Invest API returned malformed account")
            account_id = str(item.get("id") or "").strip()
            if not account_id:
                raise TBankUnavailable("T-Invest API returned account without id")
            accounts.append(
                TBankAccount(
                    id=account_id,
                    name=str(item.get("name") or "").strip(),
                    type=str(item.get("type") or "").strip(),
                    status=str(item.get("status") or "").strip(),
                )
            )
        return accounts


def _validate_token(token: str) -> str:
    clean = token.strip()
    if not 20 <= len(clean) <= 4096:
        raise TBankTokenRejected("T-Invest token has invalid length")
    if "\n" in clean or "\r" in clean:
        raise TBankTokenRejected("T-Invest token contains an invalid newline")
    return clean
