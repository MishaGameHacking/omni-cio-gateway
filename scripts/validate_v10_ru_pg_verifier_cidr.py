from __future__ import annotations

import ipaddress
import os
from pathlib import Path


CIDR_ENV = "OMNI_V10_RU_PG_VERIFIER_CIDR"

# This module validates an explicit authority input. It does not discover NAT egress.


class VerifierCidrStopped(RuntimeError):
    pass


def _required_verifier_cidr() -> str:
    raw = os.environ.get(CIDR_ENV, "").strip()
    if not raw:
        raise VerifierCidrStopped("RU_PG_VERIFIER_CIDR_REQUIRED")
    try:
        network = ipaddress.ip_network(raw, strict=True)
    except ValueError:
        raise VerifierCidrStopped("RU_PG_VERIFIER_CIDR_INVALID") from None
    if (
        not isinstance(network, ipaddress.IPv4Network)
        or network.prefixlen != 32
        or raw != str(network)
        or not network.network_address.is_global
    ):
        raise VerifierCidrStopped("RU_PG_VERIFIER_CIDR_INVALID")
    return str(network)


def _github_env_path() -> Path:
    raw = os.environ.get("GITHUB_ENV", "").strip()
    if not raw:
        raise VerifierCidrStopped("RU_PG_GITHUB_ENV_REQUIRED")
    path = Path(raw)
    if not path.is_absolute():
        raise VerifierCidrStopped("RU_PG_GITHUB_ENV_INVALID")
    return path


def validate() -> str:
    cidr = _required_verifier_cidr()
    address = cidr.removesuffix("/32")
    print(f"::add-mask::{address}")
    print(f"::add-mask::{cidr}")
    with _github_env_path().open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{CIDR_ENV}={cidr}\n")
    print("RU_PG_VERIFIER_CIDR=READY source=workflow_input mask=/32")
    return cidr


def main() -> int:
    try:
        validate()
    except VerifierCidrStopped as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
