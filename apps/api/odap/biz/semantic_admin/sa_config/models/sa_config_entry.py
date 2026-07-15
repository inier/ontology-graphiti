"""SaConfigEntry — 语义管理台动态配置的领域模型 (Pydantic v2 strict)。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_value_serializer(v: Any) -> str:
    """把任意可 JSON 化的 value 转成 TEXT，供 SQLite JSON 列保存。"""
    if isinstance(v, str):
        try:
            json.loads(v)
            return v
        except (ValueError, TypeError):
            return json.dumps(v, ensure_ascii=False)
    return json.dumps(v, ensure_ascii=False)


class SaConfigEntry(BaseModel):
    """一行配置：(scope, config_key) 联合唯一，config_value_json 存 TEXT(JSON)。"""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=False)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scope: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description='分组范围，例如 "domain:sanguo"、"pipeline:thresholds"、"global"',
    )
    config_key: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description='配置项 key，例如 "semantic_layer"、"quality_gate:v1"',
    )
    config_value: Dict[str, Any] = Field(
        default_factory=dict,
        description="配置值（任意 JSON-serializable dict / list / scalar）",
    )
    config_value_json: str = Field(
        default="",
        description="仅用于从 SQLite 反序列化；不建议在构造时手动传",
    )
    updated_by: str = Field(
        default="system",
        max_length=128,
        description="最后修改者 id，默认 system",
    )
    created_at: str = Field(default_factory=_utc_iso)
    updated_at: str = Field(default_factory=_utc_iso)

    @field_validator("config_value_json", mode="before")
    @classmethod
    def _coerce_value_from_json(cls, v, info):
        if isinstance(v, str) and v:
            try:
                parsed = json.loads(v)
            except (ValueError, TypeError):
                parsed = {}
            if not info.data.get("config_value"):
                info.data["config_value"] = parsed
        return v or "{}"

    def to_row(self) -> Dict[str, Any]:
        value_json = _default_value_serializer(self.config_value)
        return {
            "id": self.id,
            "scope": self.scope,
            "config_key": self.config_key,
            "config_value_json": value_json,
            "updated_by": self.updated_by or "system",
            "created_at": self.created_at or _utc_iso(),
            "updated_at": _utc_iso(),
        }

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "SaConfigEntry":
        value_json = row.get("config_value_json") or "{}"
        try:
            value = json.loads(value_json)
        except (ValueError, TypeError):
            value = {}
        return cls(
            id=str(row["id"]),
            scope=str(row["scope"]),
            config_key=str(row["config_key"]),
            config_value=value,
            config_value_json=value_json,
            updated_by=str(row.get("updated_by") or "system"),
            created_at=str(row.get("created_at") or _utc_iso()),
            updated_at=str(row.get("updated_at") or _utc_iso()),
        )


__all__ = ["SaConfigEntry"]
