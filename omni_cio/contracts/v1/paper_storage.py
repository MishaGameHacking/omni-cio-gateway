from __future__ import annotations

from base64 import b64decode
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel


PositiveInt = Annotated[int, Field(gt=0)]
HexDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
KeyId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,127}$")]
AlgorithmId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.:+-]{2,127}$")]
Base64Value = Annotated[str, Field(min_length=4, max_length=12_000_000)]


class PaperLedgerEncryptedEnvelopeV1(ContractModel):
    format_version: Literal["1.0"] = "1.0"
    storage_format: Literal["paper-ledger-encrypted-json-v1"] = (
        "paper-ledger-encrypted-json-v1"
    )
    encryption_boundary: Literal["external-aead-key-manager"] = (
        "external-aead-key-manager"
    )
    encryption_algorithm: AlgorithmId
    encryption_key_id: KeyId
    created_at: datetime
    sequence: PositiveInt
    record_digest: HexDigest
    associated_data_digest: HexDigest
    nonce_b64: Base64Value
    ciphertext_b64: Base64Value
    plaintext_size: Annotated[int, Field(gt=0, le=5 * 1024 * 1024)]
    ciphertext_size: Annotated[int, Field(gt=0, le=8 * 1024 * 1024)]
    external_key_management: Literal[True] = True
    authenticated_encryption_required: Literal[True] = True
    storage_backend_attached: Literal[True] = True
    atomic_write_required: Literal[True] = True
    paper_only: Literal[True] = True
    broker_order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("created_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper storage timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("nonce_b64", "ciphertext_b64")
    @classmethod
    def validate_base64(cls, value: str) -> str:
        try:
            decoded = b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("paper storage value must be strict base64") from exc
        if not decoded:
            raise ValueError("paper storage base64 value cannot be empty")
        return value

    @model_validator(mode="after")
    def validate_sizes(self) -> PaperLedgerEncryptedEnvelopeV1:
        if len(b64decode(self.ciphertext_b64, validate=True)) != self.ciphertext_size:
            raise ValueError("paper storage ciphertext size does not match payload")
        nonce_size = len(b64decode(self.nonce_b64, validate=True))
        if nonce_size < 12 or nonce_size > 64:
            raise ValueError("paper storage nonce size is outside safe bounds")
        return self
