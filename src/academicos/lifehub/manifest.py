from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EffectPermission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    destination: str

    @field_validator("kind", "destination")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value or any(ch.isspace() for ch in value):
            raise ValueError("effect kind/destination must be nonempty without whitespace")
        return value


class PermissionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage_read: list[str] = Field(default_factory=list)
    storage_write: list[str] = Field(default_factory=list)
    network_retrieval: list[str] = Field(default_factory=list)
    localhost_ports: list[int] = Field(default_factory=list)
    effect_request: list[EffectPermission] = Field(default_factory=list)

    @field_validator("localhost_ports")
    @classmethod
    def validate_ports(cls, value: list[int]) -> list[int]:
        for port in value:
            if not 1 <= port <= 65535:
                raise ValueError(f"invalid localhost port: {port}")
        return value


class ExtensionContribution(BaseModel):
    """One extension supplied by a plugin.

    `point` is intentionally an unrestricted identifier. The kernel indexes it but does
    not own a closed list of extension kinds. Consumers (the shell or another plugin)
    decide how a point is interpreted.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    point: str
    title: str | None = None
    entrypoint: str | None = None
    contract: str | None = None
    activation: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "point")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("extension id/point cannot be empty")
        if any(ch.isspace() for ch in cleaned):
            raise ValueError("extension id/point cannot contain whitespace")
        return cleaned


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: int = 1
    api: str = "lifehub@1"
    id: str
    name: str
    version: str
    description: str | None = None
    activation: list[str] = Field(default_factory=list)
    permissions: PermissionSpec = Field(default_factory=PermissionSpec)
    contributes: list[ExtensionContribution] = Field(default_factory=list)

    @field_validator("manifest_version")
    @classmethod
    def validate_manifest_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError(f"unsupported manifest_version: {value}")
        return value

    @field_validator("api")
    @classmethod
    def validate_api(cls, value: str) -> str:
        if value != "lifehub@1":
            raise ValueError(f"unsupported LifeHub API: {value}")
        return value

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        cleaned = value.strip()
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789._-"
        if not cleaned or any(ch not in allowed for ch in cleaned):
            raise ValueError("plugin id must use lowercase letters, digits, '.', '_' or '-'")
        return cleaned

    @model_validator(mode="after")
    def validate_unique_extensions(self) -> PluginManifest:
        seen: set[str] = set()
        for extension in self.contributes:
            if extension.id in seen:
                raise ValueError(f"duplicate extension id in plugin {self.id}: {extension.id}")
            seen.add(extension.id)
        return self


def load_manifest(path: str | Path) -> PluginManifest:
    payload = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    if "manifest_version" not in payload:
        payload = _upgrade_legacy_manifest(payload)
    return PluginManifest.model_validate(payload)


def _upgrade_legacy_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """Read v0.1 demo manifests without making their closed schema part of the kernel."""
    permissions = dict(payload.get("permissions", {}))
    contributions: list[dict[str, Any]] = []
    for widget in payload.get("widgets", []):
        widget = dict(widget)
        contributions.append(
            {
                "id": str(widget["id"]),
                "point": "workspace.widget",
                "title": widget.get("title"),
                "entrypoint": "lifehub.primitive",
                "config": {
                    "namespace": widget.get("namespace"),
                    "renderer": widget.get("renderer", "list"),
                    "width": widget.get("width", 4),
                    "height": widget.get("height", 3),
                    "limit": widget.get("limit", 8),
                    "description": widget.get("description"),
                    "default_workspace": True,
                },
            }
        )
    return {
        "manifest_version": 1,
        "api": "lifehub@1",
        "id": payload["id"],
        "name": payload["name"],
        "version": payload["version"],
        "description": payload.get("description"),
        "activation": [],
        "permissions": {
            "storage_read": [],
            "storage_write": permissions.get("storage_write", []),
            "network_retrieval": permissions.get("network_hosts", []),
            "localhost_ports": permissions.get("localhost_ports", []),
        },
        "contributes": contributions,
    }
