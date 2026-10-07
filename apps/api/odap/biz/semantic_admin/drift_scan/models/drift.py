"""语义漂移模型 —— 报告与发现（BeModel 语义漂移两条检测线参照）。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DriftKind(str, Enum):
    FORK = "fork"
    EVOLUTION = "evolution"

    def __str__(self) -> str:
        return self.value


class EvolutionSource(str, Enum):
    VERSION_SNAPSHOT = "version_snapshot"
    INDICATOR_CALIBER = "indicator_caliber"
    USL_TERM = "usl_term"

    def __str__(self) -> str:
        return self.value


@dataclass
class DriftFinding:
    kind: str
    subject: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    report_id: str = ""
    source: str = ""                      # evolution 来源；fork 为空
    subject_label: str = ""
    field_name: Optional[str] = None      # 字段级 diff 的字段；__added__/__removed__
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    sides: Optional[List[Dict[str, Any]]] = None    # fork 两侧证据
    version_ref: Optional[Dict[str, Any]] = None    # {version_a,version_b} 或 {prev_at,cur_at}
    at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "report_id": self.report_id, "kind": self.kind,
            "source": self.source, "subject": self.subject,
            "subject_label": self.subject_label, "field": self.field_name,
            "old_value_json": self.old_value, "new_value_json": self.new_value,
            "sides_json": self.sides, "version_ref_json": self.version_ref, "at": self.at,
        }


@dataclass
class DriftReport:
    trigger: str                          # manual | commit
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ontology_id: Optional[str] = None
    scope: Dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=_utc_now_iso)
    finished_at: Optional[str] = None
    status: str = "ok"                    # ok | failed
    error: Optional[str] = None
    source_errors: Dict[str, str] = field(default_factory=dict)
    counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "trigger": self.trigger, "ontology_id": self.ontology_id,
            "scope_json": self.scope, "started_at": self.started_at,
            "finished_at": self.finished_at, "status": self.status, "error": self.error,
            "source_errors_json": self.source_errors, "counts_json": self.counts,
        }


__all__ = ["DriftReport", "DriftFinding", "DriftKind", "EvolutionSource"]
