"""TBox 目录（ObjectType / RelationType / Indicator）真读实现。

数据来源：SQLite `ontology_api.db`（TBox 真相源的持久化实现），经 ontology 域内的
`OntologyService` 读取 —— 不新建存储、不复制 SQL（单一事实来源）。

提供两件事：
1. `lookup(term)`：把业务词映射到 TBox 元素（`ObjectType:<id>` / `RelationType:<id>` /
   `metric:<name>`）。**只做精确/归一化等值匹配**（确定性，符合 ADR-056/ADR-095 的
   「同义词泛化必须走字典精确查表」原则），不做模糊相似。
2. `snapshot_hash()`：TBox 快照哈希（`sha256:...`），用于溯源版本锚定（AC-38）。
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_KIND_OBJECT = "ObjectType"
_KIND_RELATION = "RelationType"
_KIND_METRIC = "metric"


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


class TBoxCatalog:
    """TBox 元素索引（按 workspace 装配）。"""

    def __init__(self, ontology_service_factory: Optional[Callable[[], Any]] = None):
        self._factory = ontology_service_factory or _default_service_factory
        self._service: Any = None
        self._index: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._loaded_workspaces: set[str] = set()

    # ── 装配 ──────────────────────────────────────────────────────────────
    def _svc(self) -> Any:
        if self._service is None:
            self._service = self._factory()
        return self._service

    def reset(self) -> None:
        """清空缓存（测试隔离 / TBox 变更后强制重载）。"""
        self._service = None
        self._index.clear()
        self._loaded_workspaces.clear()

    def load(self, workspace_id: str = "") -> None:
        """加载某 workspace 的 TBox 元素索引（幂等）。"""
        key = workspace_id or ""
        if key in self._loaded_workspaces:
            return
        index: Dict[str, Dict[str, Any]] = {}
        svc = self._svc()

        ontologies_resp = svc.list_ontologies(workspace_id=workspace_id or None)
        if isinstance(ontologies_resp, dict) and ontologies_resp.get("status") == "error":
            raise RuntimeError(f"TBox 读取失败（list_ontologies）：{ontologies_resp.get('message')}")
        ontologies = (ontologies_resp or {}).get("ontologies") or []

        for ontology in ontologies:
            ontology_id = ontology.get("ontology_id") or ontology.get("id")
            if not ontology_id:
                continue
            for kind, resp_key in ((_KIND_OBJECT, "object_types"),
                                   (_KIND_RELATION, "link_types"),
                                   (_KIND_METRIC, "indicator_types")):
                resp = self._list_by_kind(svc, kind, ontology_id)
                for item in (resp or {}).get(resp_key) or []:
                    self._index_item(index, kind, item)

        self._index[key] = index
        self._loaded_workspaces.add(key)
        logger.info(
            "TBox catalog loaded: workspace=%s elements=%d ontologies=%d",
            key or "-", len(index), len(ontologies),
        )

    def _list_by_kind(self, svc: Any, kind: str, ontology_id: str) -> Dict[str, Any]:
        if kind == _KIND_OBJECT:
            return svc.list_object_types(ontology_id)
        if kind == _KIND_RELATION:
            return svc.list_link_types(ontology_id)
        return svc.list_indicator_types(ontology_id)

    @staticmethod
    def _index_item(index: Dict[str, Dict[str, Any]], kind: str, item: Dict[str, Any]) -> None:
        raw_id = item.get("id") or item.get("type_id") or item.get("object_type_id") \
            or item.get("link_type_id") or item.get("indicator_type_id") or ""
        name = item.get("name") or item.get("display_name") or item.get("label") or raw_id
        if not raw_id and not name:
            return
        element = {
            "kind": kind,
            "id": str(raw_id or name),
            "name": str(name),
            "display_name": str(item.get("display_name") or ""),
            "label": str(item.get("label") or ""),
            "ontology_id": str(item.get("ontology_id") or ""),
        }
        for alias in {element["id"], element["name"], element["display_name"], element["label"]}:
            normalized = _norm(alias)
            if normalized and normalized not in index:
                index[normalized] = element

    # ── 查询 ──────────────────────────────────────────────────────────────
    def lookup(self, term: str, workspace_id: str = "") -> Optional[Tuple[str, Dict[str, Any]]]:
        """精确查表：`term` → `("<Kind>:<id>", element)`；未命中返回 None（不猜）。"""
        self.load(workspace_id)
        element = self._index.get(workspace_id or "", {}).get(_norm(term))
        if element is None:
            return None
        return f"{element['kind']}:{element['id']}", element

    def exists(self, kind: str, ref_id: str, workspace_id: str = "") -> bool:
        """按 `Kind:ID` 判定 TBox 元素是否存在（证据解析用，AC-37）。"""
        self.load(workspace_id)
        target = _norm(f"{kind}:{ref_id}")
        for element in self._index.get(workspace_id or "", {}).values():
            if _norm(f"{element['kind']}:{element['id']}") == target:
                return True
        return False

    def snapshot_hash(self, workspace_id: str = "") -> str:
        """TBox 快照哈希：对 (kind, id, name) 排序后 sha256（AC-38 版本锚定）。"""
        self.load(workspace_id)
        index = self._index.get(workspace_id or "", {})
        unique: Dict[str, Tuple[str, str, str]] = {}
        for element in index.values():
            key = f"{element['kind']}:{element['id']}"
            unique[key] = (element["kind"], element["id"], element["name"])
        payload = "\n".join(
            f"{k}|{unique[k][0]}|{unique[k][1]}|{unique[k][2]}" for k in sorted(unique)
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def elements(self, workspace_id: str = "") -> List[Dict[str, Any]]:
        self.load(workspace_id)
        seen: Dict[str, Dict[str, Any]] = {}
        for element in self._index.get(workspace_id or "", {}).values():
            seen[f"{element['kind']}:{element['id']}"] = element
        return [seen[k] for k in sorted(seen)]


def _default_service_factory() -> Any:
    """默认装配：ontology 域内的 OntologyService（同一域，无需经门面）。"""
    from odap.biz.core.ontology.ontology_api.services import OntologyService

    return OntologyService()


__all__ = ["TBoxCatalog", "_KIND_OBJECT", "_KIND_RELATION", "_KIND_METRIC"]
