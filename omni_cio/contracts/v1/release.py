from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel


NonNegativeInt = Annotated[int, Field(ge=0)]


class ReadOnlyActionV1(ContractModel):
    path: Annotated[str, Field(pattern=r"^/[A-Za-z0-9_./{}-]*$")]
    method: Literal["get"] = "get"
    operation_id: Annotated[
        str,
        Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{2,127}$"),
    ]
    public: bool
    authentication_required: bool

    @model_validator(mode="after")
    def validate_action(self) -> ReadOnlyActionV1:
        if self.public == self.authentication_required:
            raise ValueError(
                "public and authentication_required must be logical opposites"
            )
        return self


class ReadOnlyReleaseManifestV1(ContractModel):
    generated_at: datetime
    app_version: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
    entrypoint: Literal["app:app"] = "app:app"
    openapi_version: Annotated[str, Field(pattern=r"^3\.[0-9]+\.[0-9]+$")]
    server_urls: Annotated[tuple[str, ...], Field(min_length=1)]
    actions: Annotated[tuple[ReadOnlyActionV1, ...], Field(min_length=1)]
    action_count: NonNegativeInt
    public_action_count: NonNegativeInt
    authenticated_action_count: NonNegativeInt
    get_only: Literal[True] = True
    operation_ids_unique: Literal[True] = True
    approved_https_servers_only: Literal[True] = True
    forbidden_surface_count: Literal[0] = 0
    trading_methods: Literal[False] = False

    @field_validator("generated_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("release manifest timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_manifest(self) -> ReadOnlyReleaseManifestV1:
        if self.action_count != len(self.actions):
            raise ValueError("action_count does not reconcile")
        public_count = sum(action.public for action in self.actions)
        authenticated_count = sum(
            action.authentication_required for action in self.actions
        )
        if self.public_action_count != public_count:
            raise ValueError("public action count does not reconcile")
        if self.authenticated_action_count != authenticated_count:
            raise ValueError("authenticated action count does not reconcile")
        if public_count + authenticated_count != self.action_count:
            raise ValueError("every action must have an authentication classification")
        operation_ids = [action.operation_id for action in self.actions]
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("operation IDs must be unique")
        route_keys = [(action.path, action.method) for action in self.actions]
        if len(route_keys) != len(set(route_keys)):
            raise ValueError("release actions must be unique by path and method")
        return self
