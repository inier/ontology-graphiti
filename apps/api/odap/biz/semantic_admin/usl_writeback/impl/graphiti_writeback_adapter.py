"""Graphiti Writeback Adapter — USL → Graphiti 双写适配器（Phase 2 Iter4）。

职责：
  1. resolve_ontology(domain_id)：把 USL Domain 映射/创建为一个 Ontology
     - 第一次调用时创建 Ontology；后续调用幂等返回 ontology_id
     - 记录在 provenance["graphiti_ontology_id"] 中避免重复创建
  2. write_term_to_graphiti(term_dict, ontology_id)：根据 SemanticType
     把 USL Term 写到对应的 Graphiti 类型表：
     - 对象类型 → create_object_type
     - 关系类型 → create_link_type（若无 source/target 信息则降级为 ObjectType）
     - 属性 → create_object_type（带属性标记）
     - 动作类型 → create_action_type
     - 过程类型 → create_process_type
     - 规则类型 → create_rule_type
  3. 幂等检查：ontology_id + canonical_name 已存在 → skip（返回 {"skipped":True}）

降级策略（AGENTS.md §C 原则）：
  - Graphiti 写入失败不影响 USL 主流程：catch Exception → 返回 error dict
  - candidate.provenance.graphiti_writeback_status 记录 {"status":"ok"/"error","message":"..."}
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# SemanticType → Graphiti 类型写入方法映射
_SEMANTIC_TYPE_TO_METHOD = {
    "对象类型": "object",
    "关系类型": "link",
    "属性": "object",
    "动作类型": "action",
    "过程类型": "process",
    "规则类型": "rule",
}


def _build_properties_from_term(term: Dict[str, Any]) -> List[Dict[str, Any]]:
    """把 Term 的 synonyms/near_synonyms/aliases 组装为 ObjectType properties。"""
    props: List[Dict[str, Any]] = []
    synonyms = list(term.get("synonyms") or [])
    near_synonyms = list(term.get("near_synonyms") or [])
    aliases = list(term.get("aliases") or [])
    definition = term.get("definition") or ""
    semantic_type = term.get("semantic_type") or "对象类型"

    # 同义词组作为多值属性 synonyms
    if synonyms:
        props.append({
            "property_id": f"prop-syn-{uuid.uuid4().hex[:8]}",
            "name": "synonyms",
            "display_name": "同义词",
            "data_type": "string[]",
            "value": synonyms,
            "description": "严格同义词列表（来自 USL Term.synonyms）",
            "is_required": False,
            "is_indexed": True,
        })
    if near_synonyms:
        props.append({
            "property_id": f"prop-near-{uuid.uuid4().hex[:8]}",
            "name": "near_synonyms",
            "display_name": "近义词",
            "data_type": "string[]",
            "value": near_synonyms,
            "description": "近义表达列表（来自 USL Term.near_synonyms）",
            "is_required": False,
            "is_indexed": False,
        })
    if aliases:
        props.append({
            "property_id": f"prop-alias-{uuid.uuid4().hex[:8]}",
            "name": "aliases",
            "display_name": "别名",
            "data_type": "string[]",
            "value": aliases,
            "description": "别名/简称/俗称列表（来自 USL Term.aliases）",
            "is_required": False,
            "is_indexed": True,
        })
    if definition:
        props.append({
            "property_id": f"prop-def-{uuid.uuid4().hex[:8]}",
            "name": "definition",
            "display_name": "术语定义",
            "data_type": "text",
            "value": definition,
            "description": "术语的自然语言定义（来自 USL Term.definition）",
            "is_required": False,
            "is_indexed": False,
        })
    # 记录原始 semantic_type 便于过滤
    props.append({
        "property_id": f"prop-st-{uuid.uuid4().hex[:8]}",
        "name": "semantic_type_tag",
        "display_name": "语义类型标签",
        "data_type": "string",
        "value": semantic_type,
        "description": "USL SemanticType 原始标签，便于本体查询时过滤",
        "is_required": False,
        "is_indexed": True,
    })
    return props


class GraphitiWritebackAdapter:
    """USL → Graphiti 双写适配器（幂等、降级友好）。"""

    def __init__(self, ontology_service=None, usl_storage=None):
        # 懒加载 OntologyService（避免 import 时依赖未就绪）
        self._ontology_service = ontology_service
        self._usl_storage = usl_storage
        # 缓存 domain_id → ontology_id，避免每次 SQL 查询
        self._domain_ontology_cache: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Lazy
    # ------------------------------------------------------------------
    def _get_ontology_service(self):
        if self._ontology_service is None:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import (
                OntologyService,
            )
            self._ontology_service = OntologyService()
        return self._ontology_service

    def _get_usl_storage(self):
        if self._usl_storage is None:
            from odap.biz.semantic_admin.usl_manager.storage import (
                SQLiteUslStorage,
            )
            self._usl_storage = SQLiteUslStorage()
        return self._usl_storage

    # ------------------------------------------------------------------
    # Domain → Ontology
    # ------------------------------------------------------------------
    def resolve_ontology(
        self,
        domain_id: str,
        *,
        workspace_id: str = "",
        scenario_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """把 USL Domain 映射为一个 Ontology（幂等创建）。

        查找顺序：
          1. self._domain_ontology_cache[domain_id] → 直接返回
          2. 查 ontology 表中 name = f"USL__{domain_code}" 的记录
          3. 不存在则 create_ontology(name=f"USL__{domain.code}", ...)

        返回: {"ontology_id": str, "created_new": bool, "domain_code": str, "domain_display_name": str}
        """
        try:
            if not domain_id:
                return {"status": "error", "message": "domain_id 不能为空"}

            # 1. 缓存命中
            if domain_id in self._domain_ontology_cache:
                return {
                    "ontology_id": self._domain_ontology_cache[domain_id],
                    "created_new": False,
                    "from_cache": True,
                }

            # 2. 查 USL Domain
            usl = self._get_usl_storage()
            domain = None
            try:
                get_domain_fn = getattr(usl, "get_domain", None)
                if get_domain_fn is not None:
                    domain = get_domain_fn(domain_id)
                else:
                    # 退化：通过 list_domains 过滤
                    list_fn = getattr(usl, "list_domains", None)
                    if list_fn is not None:
                        result = list_fn(page=1, page_size=1000)
                        items = result[0] if isinstance(result, tuple) else (
                            result.get("items") if isinstance(result, dict) else []
                        )
                        for d in items:
                            if str(d.get("id")) == str(domain_id):
                                domain = d
                                break
            except Exception:
                domain = None

            domain_code: str = ""
            domain_display: str = ""
            if domain:
                domain_code = str(domain.get("code") or f"d{domain_id[:8]}")
                domain_display = str(domain.get("display_name") or domain_code)
            else:
                domain_code = f"d{domain_id[:8]}"
                domain_display = domain_code

            ontology_name = f"USL__{domain_code}"

            # 3. 查是否已有同名 Ontology
            svc = self._get_ontology_service()
            existing_ontology: Optional[Dict[str, Any]] = None
            try:
                ws_filter = workspace_id or None
                list_result = svc.list_ontologies(workspace_id=ws_filter)
                ontologies = list_result.get("ontologies") or []
                for ont in ontologies:
                    if str(ont.get("name")) == ontology_name:
                        existing_ontology = ont
                        break
            except Exception:
                existing_ontology = None

            if existing_ontology:
                oid = str(existing_ontology["ontology_id"])
                self._domain_ontology_cache[domain_id] = oid
                return {
                    "ontology_id": oid,
                    "created_new": False,
                    "domain_code": domain_code,
                    "domain_display_name": domain_display,
                }

            # 4. 创建新 Ontology
            created = svc.create_ontology(
                name=ontology_name,
                description=(
                    f"[自动创建] USL 领域「{domain_display}」对应本体，"
                    f"用于承载 USL→Graphiti 双写的类型定义。"
                ),
                workspace_id=workspace_id or "",
                scenario_id=scenario_id,
            )
            if isinstance(created, dict) and created.get("status") == "error":
                return created
            oid = str(created["ontology_id"])
            self._domain_ontology_cache[domain_id] = oid
            return {
                "ontology_id": oid,
                "created_new": True,
                "domain_code": domain_code,
                "domain_display_name": domain_display,
            }
        except Exception as e:
            logger.exception("resolve_ontology failed")
            return {"status": "error", "message": f"resolve_ontology 失败: {e}"}

    # ------------------------------------------------------------------
    # Term → Graphiti Type（核心写入）
    # ------------------------------------------------------------------
    def write_term(
        self,
        term_dict: Dict[str, Any],
        *,
        ontology_id: str,
        force_overwrite: bool = False,
    ) -> Dict[str, Any]:
        """把一个 USL Term 写入 Graphiti 本体。

        根据 semantic_type 分派：
          对象类型/属性 → create_object_type（属性额外打 property 标签）
          关系类型       → create_link_type（缺 source/target 时降级 ObjectType）
          动作类型       → create_action_type（target_object_type=canonical 自指）
          过程类型       → create_process_type
          规则类型       → create_rule_type

        返回: {"status":"ok"/"error", "method": str, "created_new": bool, "skipped": bool,
               "type_id": str, "payload": dict}
        """
        try:
            if not term_dict or not term_dict.get("canonical"):
                return {"status": "error", "message": "term.canonical 不能为空"}
            if not ontology_id:
                return {"status": "error", "message": "ontology_id 不能为空"}

            canonical = str(term_dict["canonical"]).strip()
            semantic_type_raw = term_dict.get("semantic_type") or "对象类型"
            semantic_type = (
                semantic_type_raw.value
                if hasattr(semantic_type_raw, "value")
                else str(semantic_type_raw)
            )
            method = _SEMANTIC_TYPE_TO_METHOD.get(semantic_type, "object")
            synonyms = list(term_dict.get("synonyms") or [])
            definition = term_dict.get("definition") or ""
            display_name = (
                synonyms[0] if synonyms and not canonical == synonyms[0] else canonical
            )

            svc = self._get_ontology_service()

            # ---------------- 幂等检查 ----------------
            existing_id = self._find_existing_type(
                svc, method, ontology_id, canonical,
            )
            if existing_id and not force_overwrite:
                return {
                    "status": "ok",
                    "method": method,
                    "created_new": False,
                    "skipped": True,
                    "type_id": existing_id,
                    "reason": f"{method} type with name={canonical} already exists",
                }

            # ---------------- 分派写入 ----------------
            result: Dict[str, Any] = {}
            if method == "object":
                result = self._write_object_type(
                    svc, ontology_id, canonical, display_name,
                    definition, term_dict, semantic_type,
                    existing_id if force_overwrite else None,
                )
            elif method == "link":
                result = self._write_link_type(
                    svc, ontology_id, canonical, display_name,
                    definition, term_dict,
                    existing_id if force_overwrite else None,
                )
            elif method == "action":
                result = self._write_action_type(
                    svc, ontology_id, canonical, definition, term_dict,
                    existing_id if force_overwrite else None,
                )
            elif method == "process":
                result = self._write_process_type(
                    svc, ontology_id, canonical, display_name, definition, term_dict,
                    existing_id if force_overwrite else None,
                )
            elif method == "rule":
                result = self._write_rule_type(
                    svc, ontology_id, canonical, display_name, definition, term_dict,
                    existing_id if force_overwrite else None,
                )

            if isinstance(result, dict) and result.get("status") == "error":
                return result
            type_id = (
                result.get("type_id")
                or result.get("link_id")
                or result.get("action_type_id")
                or ""
            )
            return {
                "status": "ok",
                "method": method,
                "created_new": (not existing_id) or force_overwrite,
                "skipped": False,
                "type_id": str(type_id),
                "payload": result,
                "overwrote_existing": bool(existing_id and force_overwrite),
            }
        except Exception as e:
            logger.exception("write_term to graphiti failed")
            return {"status": "error", "message": f"write_term 失败: {e}"}

    # ------------------------------------------------------------------
    # 内部：幂等查找
    # ------------------------------------------------------------------
    @staticmethod
    def _find_existing_type(svc, method: str, ontology_id: str, name: str) -> Optional[str]:
        try:
            if method == "object":
                res = svc.list_object_types(ontology_id)
                for t in res.get("object_types") or []:
                    if str(t.get("name")) == name:
                        return str(t.get("type_id"))
            elif method == "link":
                res = svc.list_link_types(ontology_id)
                for t in res.get("link_types") or []:
                    if str(t.get("name")) == name:
                        return str(t.get("link_id"))
            elif method == "action":
                res = svc.list_action_types(ontology_id)
                for t in res.get("action_types") or []:
                    if str(t.get("name")) == name:
                        return str(t.get("action_type_id"))
            elif method == "process":
                res = svc.list_process_types(ontology_id)
                for t in res.get("process_types") or []:
                    if str(t.get("name")) == name:
                        return str(t.get("type_id"))
            elif method == "rule":
                res = svc.list_rule_types(ontology_id)
                for t in res.get("rule_types") or []:
                    if str(t.get("name")) == name:
                        return str(t.get("type_id"))
        except Exception:
            return None
        return None

    # ------------------------------------------------------------------
    # 内部：各类型具体写入
    # ------------------------------------------------------------------
    @staticmethod
    def _write_object_type(
        svc, ontology_id, canonical, display_name, definition, term_dict,
        semantic_type, existing_id=None,
    ) -> Dict[str, Any]:
        properties = _build_properties_from_term(term_dict)
        # 属性型对象：额外标记
        if semantic_type == "属性":
            properties.append({
                "property_id": f"prop-tag-{uuid.uuid4().hex[:8]}",
                "name": "usl_is_property",
                "display_name": "属性型标记",
                "data_type": "boolean",
                "value": True,
                "description": "标记此 ObjectType 由 USL 属性类型升级而来",
                "is_required": False,
                "is_indexed": True,
            })
        type_data = {
            "name": canonical,
            "display_name": display_name,
            "description": definition or f"USL 术语，语义类型={semantic_type}",
            "properties": properties,
            "links": [],
            "actions": [],
            "primary_key": [],
            "classification_level": "U",
        }
        if existing_id:
            return svc.update_object_type(existing_id, type_data)
        return svc.create_object_type(ontology_id, type_data)

    @staticmethod
    def _write_link_type(
        svc, ontology_id, canonical, display_name, definition, term_dict,
        existing_id=None,
    ) -> Dict[str, Any]:
        """关系类型写入：若缺 source/target，先尝试从 provenance 取，取不到则降级 ObjectType。"""
        provenance: Dict[str, Any] = term_dict.get("provenance") or {}
        source_type = (
            provenance.get("link_source_type")
            or provenance.get("source_canonical")
            or ""
        )
        target_type = (
            provenance.get("link_target_type")
            or provenance.get("target_canonical")
            or ""
        )
        if not source_type or not target_type:
            # 降级：当 ObjectType 写
            properties = _build_properties_from_term(term_dict)
            properties.append({
                "property_id": f"prop-link-{uuid.uuid4().hex[:8]}",
                "name": "usl_link_degraded",
                "display_name": "关系降级标记",
                "data_type": "boolean",
                "value": True,
                "description": "此 USL 关系类型因缺少 source/target，降级为 ObjectType 存储",
                "is_required": False,
                "is_indexed": True,
            })
            type_data = {
                "name": canonical,
                "display_name": display_name,
                "description": definition or f"USL 关系类型（降级 ObjectType）",
                "properties": properties,
                "links": [],
                "actions": [],
                "primary_key": [],
                "classification_level": "U",
            }
            if existing_id:
                return svc.update_object_type(existing_id, type_data)
            return svc.create_object_type(ontology_id, type_data)

        cardinality = provenance.get("cardinality") or "ONE_TO_MANY"
        is_bidirectional = bool(provenance.get("is_bidirectional"))
        link_data = {
            "name": canonical,
            "source_type": source_type,
            "target_type": target_type,
            "cardinality": cardinality,
            "link_type": provenance.get("link_type") or "ASSOCIATION",
            "is_bidirectional": is_bidirectional,
            "reverse_name": provenance.get("reverse_name") or f"逆-{canonical}",
            "description": definition or f"USL 关系类型：{canonical}",
        }
        if existing_id:
            return svc.update_link_type(existing_id, link_data)
        return svc.create_link_type(ontology_id, link_data)

    @staticmethod
    def _write_action_type(
        svc, ontology_id, canonical, definition, term_dict, existing_id=None,
    ) -> Dict[str, Any]:
        provenance = term_dict.get("provenance") or {}
        action_data = {
            "name": canonical,
            "target_object_type": provenance.get("target_object_type") or canonical,
            "description": definition or f"USL 动作类型：{canonical}",
            "parameters": provenance.get("action_parameters") or [],
            "required_roles": provenance.get("required_roles") or [],
            "confirmation_required": bool(provenance.get("confirmation_required", True)),
        }
        if existing_id:
            return svc.update_action_type(existing_id, action_data)
        return svc.create_action_type(ontology_id, action_data)

    @staticmethod
    def _write_process_type(
        svc, ontology_id, canonical, display_name, definition, term_dict,
        existing_id=None,
    ) -> Dict[str, Any]:
        provenance = term_dict.get("provenance") or {}
        data = {
            "name": canonical,
            "display_name": display_name,
            "description": definition or f"USL 过程类型：{canonical}",
            "flow_node_schema": provenance.get("flow_node_schema") or [],
            "related_object_types": provenance.get("related_object_types") or [],
        }
        if existing_id:
            return svc.update_process_type(existing_id, data)
        return svc.create_process_type(ontology_id, data)

    @staticmethod
    def _write_rule_type(
        svc, ontology_id, canonical, display_name, definition, term_dict,
        existing_id=None,
    ) -> Dict[str, Any]:
        provenance = term_dict.get("provenance") or {}
        data = {
            "name": canonical,
            "display_name": display_name,
            "description": definition or f"USL 规则类型：{canonical}",
            "condition_schema": provenance.get("condition_schema") or {},
            "consequence_schema": provenance.get("consequence_schema") or {},
            "priority_levels": provenance.get("priority_levels") or ["low", "medium", "high"],
            "related_object_types": provenance.get("related_object_types") or [],
        }
        if existing_id:
            return svc.update_rule_type(existing_id, data)
        return svc.create_rule_type(ontology_id, data)


__all__ = ["GraphitiWritebackAdapter", "_build_properties_from_term"]
