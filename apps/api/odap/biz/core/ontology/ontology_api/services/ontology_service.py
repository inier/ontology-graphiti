"""OntologyService 编排层

服务层规范（AGENTS.md 规则 2）：
- 必须返回 Dict[str, Any]，禁止抛 HTTPException
- 错误格式: {"status": "error", "message": "..."}
- 成功格式: 扁平 dict
- 类型转换: Enum->.value, datetime->.isoformat(), BaseModel->扁平 dict
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..storage import Storage

logger = logging.getLogger(__name__)


class OntologyService:
    """本体管理编排服务

    职责：在 routes 和 storage 之间编排业务逻辑，包括：
    - 本体 CRUD
    - Schema 版本管理（commit / diff / rollback）
    - 各类类型定义 CRUD（object / link / action / process / rule / function / indicator）
    - 图谱数据组装
    - 数据库连接管理
    - 抽取会话管理
    """

    def __init__(self, db_path: str = None, version_adapter=None):
        self.storage = Storage(db_path=db_path) if db_path else Storage()
        self._version_adapter = version_adapter

    # ==================================================================
    # Ontology CRUD
    # ==================================================================

    def create_ontology(
        self,
        name: str,
        description: str = "",
        workspace_id: str = "",
        scenario_id: str = None,
    ) -> Dict[str, Any]:
        """创建本体 + 初始 Schema 版本 v0.1.0"""
        try:
            if not name or not str(name).strip():
                return {"status": "error", "message": "name is required and must be non-empty"}

            now = datetime.now(timezone.utc).isoformat()
            ontology_id = str(uuid.uuid4())

            ontology = {
                "ontology_id": ontology_id,
                "name": name,
                "description": description,
                "workspace_id": workspace_id,
                "scenario_id": scenario_id,
                "current_version": "v0.1.0",
                "status": "draft",
                "created_at": now,
                "updated_at": now,
            }
            self.storage.save_ontology(ontology)

            # 创建初始 Schema 版本
            version_id = f"v{datetime.now(timezone.utc).strftime('%Y%m%d')}-001"
            version = {
                "version_id": version_id,
                "ontology_id": ontology_id,
                "version_number": "0.1.0",
                "parent_version_id": None,
                "is_stable": False,
                "changelog": "Initial version",
                "schema_snapshot": None,
                "created_at": now,
            }
            self.storage.save_schema_version(version)

            return {
                "ontology_id": ontology_id,
                "name": name,
                "description": description,
                "workspace_id": workspace_id,
                "scenario_id": scenario_id,
                "current_version": "v0.1.0",
                "status": "draft",
                "created_at": now,
                "updated_at": now,
            }
        except Exception as exc:
            logger.exception("create_ontology failed")
            return {"status": "error", "message": f"create_ontology failed: {exc}"}

    def get_ontology(self, ontology_id: str) -> Dict[str, Any]:
        """获取本体详情"""
        try:
            ontology = self.storage.get_ontology(ontology_id)
            if not ontology:
                return {"status": "error", "message": f"ontology not found: {ontology_id}"}
            return ontology
        except Exception as exc:
            return {"status": "error", "message": f"get_ontology failed: {exc}"}

    def list_ontologies(self, workspace_id: str = None) -> Dict[str, Any]:
        """列出本体"""
        try:
            ontologies = self.storage.list_ontologies(workspace_id=workspace_id)
            return {"ontologies": ontologies, "count": len(ontologies)}
        except Exception as exc:
            return {"status": "error", "message": f"list_ontologies failed: {exc}"}

    def update_ontology(self, ontology_id: str, updates: Dict) -> Dict[str, Any]:
        """更新本体信息"""
        try:
            ontology = self.storage.get_ontology(ontology_id)
            if not ontology:
                return {"status": "error", "message": f"ontology not found: {ontology_id}"}

            # 合并更新字段
            for key, value in updates.items():
                if key in ("name", "description", "scenario_id", "status"):
                    ontology[key] = value

            ontology["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.storage.save_ontology(ontology)
            return ontology
        except Exception as exc:
            return {"status": "error", "message": f"update_ontology failed: {exc}"}

    def delete_ontology(self, ontology_id: str) -> Dict[str, Any]:
        """删除本体（级联删除所有关联类型定义）"""
        try:
            ontology = self.storage.get_ontology(ontology_id)
            if not ontology:
                return {"status": "error", "message": f"ontology not found: {ontology_id}"}

            # 级联删除关联的类型定义
            self.storage.delete_object_types_by_ontology(ontology_id)
            self.storage.delete_link_types_by_ontology(ontology_id)
            self.storage.delete_action_types_by_ontology(ontology_id)
            self.storage.delete_process_types_by_ontology(ontology_id)
            self.storage.delete_rule_types_by_ontology(ontology_id)
            self.storage.delete_function_types_by_ontology(ontology_id)
            self.storage.delete_indicator_types_by_ontology(ontology_id)
            self.storage.delete_schema_versions_by_ontology(ontology_id)
            self.storage.delete_extraction_sessions_by_ontology(ontology_id)

            ok = self.storage.delete_ontology(ontology_id)
            if not ok:
                return {"status": "error", "message": f"ontology not found: {ontology_id}"}
            return {"ontology_id": ontology_id, "deleted": True}
        except Exception as exc:
            return {"status": "error", "message": f"delete_ontology failed: {exc}"}

    # ==================================================================
    # Schema Version Management
    # ==================================================================

    def commit_schema_version(
        self, ontology_id: str, changelog: str = ""
    ) -> Dict[str, Any]:
        """提交当前 Schema 版本快照

        流程：
        1. 获取所有当前类型定义
        2. 序列化为 schema_snapshot
        3. 将当前工作版本标记为 stable
        4. 创建新的工作版本（minor version +1）
        5. 更新本体 current_version
        """
        try:
            ontology = self.storage.get_ontology(ontology_id)
            if not ontology:
                return {"status": "error", "message": f"ontology not found: {ontology_id}"}

            # 1. 收集所有当前类型定义
            snapshot = self._build_schema_snapshot(ontology_id)

            # 2. 查找当前工作版本
            versions = self.storage.list_schema_versions(ontology_id)
            current_working = None
            for v in versions:
                if not v.get("is_stable"):
                    current_working = v
                    break

            now = datetime.now(timezone.utc).isoformat()

            # 3. 将当前工作版本标记为 stable 并保存快照
            if current_working:
                current_working["is_stable"] = True
                current_working["changelog"] = changelog or current_working.get("changelog", "")
                current_working["schema_snapshot"] = json.dumps(snapshot, ensure_ascii=False)
                self.storage.save_schema_version(current_working)
                parent_version_id = current_working["version_id"]
                old_version_number = current_working["version_number"]
            else:
                parent_version_id = None
                old_version_number = "0.1.0"

            # 4. 计算新版本号（minor +1）
            new_version_number = self._increment_minor_version(old_version_number)
            new_version_id = f"v{datetime.now(timezone.utc).strftime('%Y%m%d')}-{len(versions) + 1:03d}"

            new_version = {
                "version_id": new_version_id,
                "ontology_id": ontology_id,
                "version_number": new_version_number,
                "parent_version_id": parent_version_id,
                "is_stable": False,
                "changelog": "",
                "schema_snapshot": None,
                "created_at": now,
            }
            self.storage.save_schema_version(new_version)

            # 5. 更新本体 current_version
            ontology["current_version"] = f"v{new_version_number}"
            ontology["updated_at"] = now
            self.storage.save_ontology(ontology)

            # 通知 VersionStorageAdapter（如果已注入），将版本同步到 design 模块存储
            if self._version_adapter is not None:
                try:
                    version_data = {
                        "id": current_working["version_id"] if current_working else new_version_id,
                        "ontology_id": ontology_id,
                        "version_number": old_version_number,
                        "parent_version_id": current_working.get("parent_version_id") if current_working else None,
                        "status": "released",
                        "change_summary": changelog or "",
                        "created_at": now,
                        "is_current": False,
                        "is_stable": True,
                        "doc_snapshot": json.dumps(snapshot, ensure_ascii=False) if snapshot else None,
                    }
                    self._version_adapter.save_version(version_data)
                    logger.debug("OntologyService: version_adapter notified for ontology=%s", ontology_id)
                except Exception as adapter_exc:
                    logger.warning("OntologyService: version_adapter notification failed: %s", adapter_exc)

            return {
                "version_id": current_working["version_id"] if current_working else new_version_id,
                "version_number": old_version_number,
                "is_stable": True,
                "changelog": changelog,
                "schema_snapshot": snapshot,
                "created_at": now,
            }
        except Exception as exc:
            logger.exception("commit_schema_version failed")
            return {"status": "error", "message": f"commit_schema_version failed: {exc}"}

    def list_schema_versions(self, ontology_id: str) -> Dict[str, Any]:
        """列出版本历史"""
        try:
            versions = self.storage.list_schema_versions(ontology_id)
            return {"versions": versions, "count": len(versions)}
        except Exception as exc:
            return {"status": "error", "message": f"list_schema_versions failed: {exc}"}

    def diff_schema_versions(
        self,
        ontology_id: str,
        version_id_a: str,
        version_id_b: str,
    ) -> Dict[str, Any]:
        """对比两个 Schema 版本的差异

        比较维度：object_types / link_types / action_types / process_types /
                  rule_types / function_types / indicator_types
        每个维度输出：added / modified / deleted
        """
        try:
            ver_a = self.storage.get_schema_version(version_id_a)
            ver_b = self.storage.get_schema_version(version_id_b)

            if not ver_a:
                return {"status": "error", "message": f"version not found: {version_id_a}"}
            if not ver_b:
                return {"status": "error", "message": f"version not found: {version_id_b}"}

            snap_a = ver_a.get("schema_snapshot") or {}
            snap_b = ver_b.get("schema_snapshot") or {}

            # 如果快照是字符串则解析
            if isinstance(snap_a, str):
                snap_a = json.loads(snap_a)
            if isinstance(snap_b, str):
                snap_b = json.loads(snap_b)

            diff_result = {}
            # 每个分类的主键字段不同：link_types 用 link_id，action_types 用 action_type_id
            category_key_map = {
                "object_types": "type_id",
                "link_types": "link_id",
                "action_types": "action_type_id",
                "process_types": "type_id",
                "rule_types": "type_id",
                "function_types": "type_id",
                "indicator_types": "type_id",
            }

            for category, pk_field in category_key_map.items():
                items_a = {item[pk_field]: item for item in snap_a.get(category, [])}
                items_b = {item[pk_field]: item for item in snap_b.get(category, [])}

                ids_a = set(items_a.keys())
                ids_b = set(items_b.keys())

                added = [items_b[k] for k in (ids_b - ids_a)]
                deleted = [items_a[k] for k in (ids_a - ids_b)]
                modified = [
                    items_b[k] for k in (ids_a & ids_b)
                    if items_a[k] != items_b[k]
                ]

                diff_result[category] = {
                    "added": added,
                    "modified": modified,
                    "deleted": deleted,
                    "added_count": len(added),
                    "modified_count": len(modified),
                    "deleted_count": len(deleted),
                }

            return {
                "version_a": {
                    "version_id": ver_a["version_id"],
                    "version_number": ver_a["version_number"],
                },
                "version_b": {
                    "version_id": ver_b["version_id"],
                    "version_number": ver_b["version_number"],
                },
                "diff": diff_result,
            }
        except Exception as exc:
            logger.exception("diff_schema_versions failed")
            return {"status": "error", "message": f"diff_schema_versions failed: {exc}"}

    def rollback_schema_version(
        self, ontology_id: str, target_version_id: str
    ) -> Dict[str, Any]:
        """回滚到指定 Schema 版本

        流程：
        1. 加载目标版本的 schema_snapshot
        2. 删除当前所有类型定义
        3. 从快照重建类型定义
        4. 更新本体 current_version
        """
        try:
            ontology = self.storage.get_ontology(ontology_id)
            if not ontology:
                return {"status": "error", "message": f"ontology not found: {ontology_id}"}

            target_version = self.storage.get_schema_version(target_version_id)
            if not target_version:
                return {"status": "error", "message": f"version not found: {target_version_id}"}

            snapshot = target_version.get("schema_snapshot")
            if not snapshot:
                return {"status": "error", "message": "target version has no schema snapshot"}

            if isinstance(snapshot, str):
                snapshot = json.loads(snapshot)

            now = datetime.now(timezone.utc).isoformat()

            # 2. 删除当前所有类型定义
            self.storage.delete_object_types_by_ontology(ontology_id)
            self.storage.delete_link_types_by_ontology(ontology_id)
            self.storage.delete_action_types_by_ontology(ontology_id)
            self.storage.delete_process_types_by_ontology(ontology_id)
            self.storage.delete_rule_types_by_ontology(ontology_id)
            self.storage.delete_function_types_by_ontology(ontology_id)
            self.storage.delete_indicator_types_by_ontology(ontology_id)

            # 3. 从快照重建类型定义
            for obj_type in snapshot.get("object_types", []):
                obj_type["updated_at"] = now
                self.storage.save_object_type(obj_type)

            for link_type in snapshot.get("link_types", []):
                link_type["updated_at"] = now
                self.storage.save_link_type(link_type)

            for action_type in snapshot.get("action_types", []):
                action_type["updated_at"] = now
                self.storage.save_action_type(action_type)

            for process_type in snapshot.get("process_types", []):
                process_type["updated_at"] = now
                self.storage.save_process_type(process_type)

            for rule_type in snapshot.get("rule_types", []):
                self.storage.save_rule_type(rule_type)

            for function_type in snapshot.get("function_types", []):
                self.storage.save_function_type(function_type)

            for indicator_type in snapshot.get("indicator_types", []):
                self.storage.save_indicator_type(indicator_type)

            # 4. 更新本体 current_version
            ontology["current_version"] = f"v{target_version['version_number']}"
            ontology["updated_at"] = now
            self.storage.save_ontology(ontology)

            return {
                "ontology_id": ontology_id,
                "rolled_back_to": target_version_id,
                "version_number": target_version["version_number"],
                "restored_types": {
                    "object_types": len(snapshot.get("object_types", [])),
                    "link_types": len(snapshot.get("link_types", [])),
                    "action_types": len(snapshot.get("action_types", [])),
                    "process_types": len(snapshot.get("process_types", [])),
                    "rule_types": len(snapshot.get("rule_types", [])),
                    "function_types": len(snapshot.get("function_types", [])),
                    "indicator_types": len(snapshot.get("indicator_types", [])),
                },
            }
        except Exception as exc:
            logger.exception("rollback_schema_version failed")
            return {"status": "error", "message": f"rollback_schema_version failed: {exc}"}

    # ==================================================================
    # ObjectType CRUD
    # ==================================================================

    def create_object_type(self, ontology_id: str, type_data: Dict) -> Dict[str, Any]:
        """创建对象类型定义"""
        try:
            if not type_data.get("name"):
                return {"status": "error", "message": "name is required for object type"}

            now = datetime.now(timezone.utc).isoformat()
            type_id = str(uuid.uuid4())

            obj_type = {
                "type_id": type_id,
                "ontology_id": ontology_id,
                "version_id": type_data.get("version_id"),
                "name": type_data["name"],
                "display_name": type_data.get("display_name"),
                "description": type_data.get("description", ""),
                "properties": type_data.get("properties", []),
                "links": type_data.get("links", []),
                "actions": type_data.get("actions", []),
                "primary_key": type_data.get("primary_key", []),
                "classification_level": type_data.get("classification_level", "U"),
                "icon": type_data.get("icon"),
                "color": type_data.get("color"),
                "is_active": type_data.get("is_active", True),
                "parent_type": type_data.get("parent_type"),
                "created_at": now,
                "updated_at": now,
            }
            self.storage.save_object_type(obj_type)
            return obj_type
        except Exception as exc:
            return {"status": "error", "message": f"create_object_type failed: {exc}"}

    def get_object_type(self, type_id: str) -> Dict[str, Any]:
        """获取对象类型定义"""
        try:
            obj_type = self.storage.get_object_type(type_id)
            if not obj_type:
                return {"status": "error", "message": f"object type not found: {type_id}"}
            return obj_type
        except Exception as exc:
            return {"status": "error", "message": f"get_object_type failed: {exc}"}

    def list_object_types(self, ontology_id: str) -> Dict[str, Any]:
        """列出对象类型定义"""
        try:
            object_types = self.storage.list_object_types(ontology_id)
            return {"object_types": object_types, "count": len(object_types)}
        except Exception as exc:
            return {"status": "error", "message": f"list_object_types failed: {exc}"}

    def update_object_type(self, type_id: str, updates: Dict) -> Dict[str, Any]:
        """更新对象类型定义"""
        try:
            obj_type = self.storage.get_object_type(type_id)
            if not obj_type:
                return {"status": "error", "message": f"object type not found: {type_id}"}

            updatable_fields = [
                "name", "display_name", "description", "properties", "links",
                "actions", "primary_key", "classification_level", "icon",
                "color", "is_active", "parent_type", "version_id",
            ]
            for field in updatable_fields:
                if field in updates:
                    obj_type[field] = updates[field]

            obj_type["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.storage.save_object_type(obj_type)
            return obj_type
        except Exception as exc:
            return {"status": "error", "message": f"update_object_type failed: {exc}"}

    def delete_object_type(self, type_id: str) -> Dict[str, Any]:
        """删除对象类型定义"""
        try:
            ok = self.storage.delete_object_type(type_id)
            if not ok:
                return {"status": "error", "message": f"object type not found: {type_id}"}
            return {"type_id": type_id, "deleted": True}
        except Exception as exc:
            return {"status": "error", "message": f"delete_object_type failed: {exc}"}

    # ==================================================================
    # LinkType CRUD
    # ==================================================================

    def create_link_type(self, ontology_id: str, link_data: Dict) -> Dict[str, Any]:
        """创建关系类型定义"""
        try:
            if not link_data.get("name"):
                return {"status": "error", "message": "name is required for link type"}
            if not link_data.get("source_type"):
                return {"status": "error", "message": "source_type is required for link type"}
            if not link_data.get("target_type"):
                return {"status": "error", "message": "target_type is required for link type"}

            now = datetime.now(timezone.utc).isoformat()
            link_id = str(uuid.uuid4())

            link_type = {
                "link_id": link_id,
                "ontology_id": ontology_id,
                "version_id": link_data.get("version_id"),
                "name": link_data["name"],
                "source_type": link_data["source_type"],
                "target_type": link_data["target_type"],
                "cardinality": link_data.get("cardinality", "ONE_TO_MANY"),
                "link_type": link_data.get("link_type", "ASSOCIATION"),
                "is_bidirectional": link_data.get("is_bidirectional", False),
                "reverse_name": link_data.get("reverse_name"),
                "description": link_data.get("description", ""),
                "created_at": now,
                "updated_at": now,
            }
            self.storage.save_link_type(link_type)
            return link_type
        except Exception as exc:
            return {"status": "error", "message": f"create_link_type failed: {exc}"}

    def list_link_types(self, ontology_id: str) -> Dict[str, Any]:
        """列出关系类型定义"""
        try:
            link_types = self.storage.list_link_types(ontology_id)
            return {"link_types": link_types, "count": len(link_types)}
        except Exception as exc:
            return {"status": "error", "message": f"list_link_types failed: {exc}"}

    def update_link_type(self, link_id: str, updates: Dict) -> Dict[str, Any]:
        """更新关系类型定义"""
        try:
            link_type = self.storage.get_link_type(link_id)
            if not link_type:
                return {"status": "error", "message": f"link type not found: {link_id}"}

            updatable_fields = [
                "name", "source_type", "target_type", "cardinality",
                "link_type", "is_bidirectional", "reverse_name",
                "description", "version_id",
            ]
            for field in updatable_fields:
                if field in updates:
                    link_type[field] = updates[field]

            link_type["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.storage.save_link_type(link_type)
            return link_type
        except Exception as exc:
            return {"status": "error", "message": f"update_link_type failed: {exc}"}

    def delete_link_type(self, link_id: str) -> Dict[str, Any]:
        """删除关系类型定义"""
        try:
            ok = self.storage.delete_link_type(link_id)
            if not ok:
                return {"status": "error", "message": f"link type not found: {link_id}"}
            return {"link_id": link_id, "deleted": True}
        except Exception as exc:
            return {"status": "error", "message": f"delete_link_type failed: {exc}"}

    # ==================================================================
    # ActionType CRUD
    # ==================================================================

    def create_action_type(self, ontology_id: str, action_data: Dict) -> Dict[str, Any]:
        """创建动作类型定义"""
        try:
            if not action_data.get("name"):
                return {"status": "error", "message": "name is required for action type"}
            if not action_data.get("target_object_type"):
                return {"status": "error", "message": "target_object_type is required for action type"}

            now = datetime.now(timezone.utc).isoformat()
            action_type_id = str(uuid.uuid4())

            action_type = {
                "action_type_id": action_type_id,
                "ontology_id": ontology_id,
                "version_id": action_data.get("version_id"),
                "name": action_data["name"],
                "target_object_type": action_data["target_object_type"],
                "description": action_data.get("description", ""),
                "parameters": action_data.get("parameters", []),
                "required_roles": action_data.get("required_roles", []),
                "confirmation_required": action_data.get("confirmation_required", True),
                "created_at": now,
                "updated_at": now,
            }
            self.storage.save_action_type(action_type)
            return action_type
        except Exception as exc:
            return {"status": "error", "message": f"create_action_type failed: {exc}"}

    def list_action_types(self, ontology_id: str) -> Dict[str, Any]:
        """列出动作类型定义"""
        try:
            action_types = self.storage.list_action_types(ontology_id)
            return {"action_types": action_types, "count": len(action_types)}
        except Exception as exc:
            return {"status": "error", "message": f"list_action_types failed: {exc}"}

    def update_action_type(self, action_type_id: str, updates: Dict) -> Dict[str, Any]:
        """更新动作类型定义"""
        try:
            action_type = self.storage.get_action_type(action_type_id)
            if not action_type:
                return {"status": "error", "message": f"action type not found: {action_type_id}"}

            updatable_fields = [
                "name", "target_object_type", "description",
                "parameters", "required_roles", "confirmation_required", "version_id",
            ]
            for field in updatable_fields:
                if field in updates:
                    action_type[field] = updates[field]

            action_type["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.storage.save_action_type(action_type)
            return action_type
        except Exception as exc:
            return {"status": "error", "message": f"update_action_type failed: {exc}"}

    def delete_action_type(self, action_type_id: str) -> Dict[str, Any]:
        """删除动作类型定义"""
        try:
            ok = self.storage.delete_action_type(action_type_id)
            if not ok:
                return {"status": "error", "message": f"action type not found: {action_type_id}"}
            return {"action_type_id": action_type_id, "deleted": True}
        except Exception as exc:
            return {"status": "error", "message": f"delete_action_type failed: {exc}"}

    # ==================================================================
    # ProcessType CRUD
    # ==================================================================

    def create_process_type(self, ontology_id: str, data: Dict) -> Dict[str, Any]:
        """创建业务过程类型定义"""
        try:
            if not data.get("name"):
                return {"status": "error", "message": "name is required for process type"}

            now = datetime.now(timezone.utc).isoformat()
            type_id = str(uuid.uuid4())

            process_type = {
                "type_id": type_id,
                "ontology_id": ontology_id,
                "version_id": data.get("version_id"),
                "name": data["name"],
                "display_name": data.get("display_name"),
                "description": data.get("description", ""),
                "flow_node_schema": data.get("flow_node_schema", []),
                "related_object_types": data.get("related_object_types", []),
                "created_at": now,
                "updated_at": now,
            }
            self.storage.save_process_type(process_type)
            return process_type
        except Exception as exc:
            return {"status": "error", "message": f"create_process_type failed: {exc}"}

    def list_process_types(self, ontology_id: str) -> Dict[str, Any]:
        """列出业务过程类型定义"""
        try:
            process_types = self.storage.list_process_types(ontology_id)
            return {"process_types": process_types, "count": len(process_types)}
        except Exception as exc:
            return {"status": "error", "message": f"list_process_types failed: {exc}"}

    def update_process_type(self, type_id: str, updates: Dict) -> Dict[str, Any]:
        """更新业务过程类型定义"""
        try:
            process_type = self.storage.get_process_type(type_id)
            if not process_type:
                return {"status": "error", "message": f"process type not found: {type_id}"}

            updatable_fields = [
                "name", "display_name", "description",
                "flow_node_schema", "related_object_types", "version_id",
            ]
            for field in updatable_fields:
                if field in updates:
                    process_type[field] = updates[field]

            process_type["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.storage.save_process_type(process_type)
            return process_type
        except Exception as exc:
            return {"status": "error", "message": f"update_process_type failed: {exc}"}

    def delete_process_type(self, type_id: str) -> Dict[str, Any]:
        """删除业务过程类型定义"""
        try:
            ok = self.storage.delete_process_type(type_id)
            if not ok:
                return {"status": "error", "message": f"process type not found: {type_id}"}
            return {"type_id": type_id, "deleted": True}
        except Exception as exc:
            return {"status": "error", "message": f"delete_process_type failed: {exc}"}

    # ==================================================================
    # RuleType CRUD
    # ==================================================================

    def create_rule_type(self, ontology_id: str, data: Dict) -> Dict[str, Any]:
        """创建规则类型定义"""
        try:
            if not data.get("name"):
                return {"status": "error", "message": "name is required for rule type"}

            now = datetime.now(timezone.utc).isoformat()
            type_id = str(uuid.uuid4())

            rule_type = {
                "type_id": type_id,
                "ontology_id": ontology_id,
                "version_id": data.get("version_id"),
                "name": data["name"],
                "display_name": data.get("display_name"),
                "description": data.get("description", ""),
                "condition_schema": data.get("condition_schema", {}),
                "consequence_schema": data.get("consequence_schema", {}),
                "priority_levels": data.get("priority_levels", ["low", "medium", "high"]),
                "related_object_types": data.get("related_object_types", []),
                "created_at": now,
            }
            self.storage.save_rule_type(rule_type)
            return rule_type
        except Exception as exc:
            return {"status": "error", "message": f"create_rule_type failed: {exc}"}

    def list_rule_types(self, ontology_id: str) -> Dict[str, Any]:
        """列出规则类型定义"""
        try:
            rule_types = self.storage.list_rule_types(ontology_id)
            return {"rule_types": rule_types, "count": len(rule_types)}
        except Exception as exc:
            return {"status": "error", "message": f"list_rule_types failed: {exc}"}

    def update_rule_type(self, type_id: str, updates: Dict) -> Dict[str, Any]:
        """更新规则类型定义"""
        try:
            rule_type = self.storage.get_rule_type(type_id)
            if not rule_type:
                return {"status": "error", "message": f"rule type not found: {type_id}"}

            updatable_fields = [
                "name", "display_name", "description",
                "condition_schema", "consequence_schema",
                "priority_levels", "related_object_types", "version_id",
            ]
            for field in updatable_fields:
                if field in updates:
                    rule_type[field] = updates[field]

            self.storage.save_rule_type(rule_type)
            return rule_type
        except Exception as exc:
            return {"status": "error", "message": f"update_rule_type failed: {exc}"}

    def delete_rule_type(self, type_id: str) -> Dict[str, Any]:
        """删除规则类型定义"""
        try:
            ok = self.storage.delete_rule_type(type_id)
            if not ok:
                return {"status": "error", "message": f"rule type not found: {type_id}"}
            return {"type_id": type_id, "deleted": True}
        except Exception as exc:
            return {"status": "error", "message": f"delete_rule_type failed: {exc}"}

    # ==================================================================
    # FunctionType CRUD
    # ==================================================================

    def create_function_type(self, ontology_id: str, data: Dict) -> Dict[str, Any]:
        """创建逻辑函数类型定义"""
        try:
            if not data.get("name"):
                return {"status": "error", "message": "name is required for function type"}

            now = datetime.now(timezone.utc).isoformat()
            type_id = str(uuid.uuid4())

            function_type = {
                "type_id": type_id,
                "ontology_id": ontology_id,
                "version_id": data.get("version_id"),
                "name": data["name"],
                "display_name": data.get("display_name"),
                "description": data.get("description", ""),
                "logic_types": data.get("logic_types", ["filter", "transform", "validate", "compute"]),
                "expression_schema": data.get("expression_schema", {}),
                "related_object_types": data.get("related_object_types", []),
                "created_at": now,
            }
            self.storage.save_function_type(function_type)
            return function_type
        except Exception as exc:
            return {"status": "error", "message": f"create_function_type failed: {exc}"}

    def list_function_types(self, ontology_id: str) -> Dict[str, Any]:
        """列出逻辑函数类型定义"""
        try:
            function_types = self.storage.list_function_types(ontology_id)
            return {"function_types": function_types, "count": len(function_types)}
        except Exception as exc:
            return {"status": "error", "message": f"list_function_types failed: {exc}"}

    def update_function_type(self, type_id: str, updates: Dict) -> Dict[str, Any]:
        """更新逻辑函数类型定义"""
        try:
            function_type = self.storage.get_function_type(type_id)
            if not function_type:
                return {"status": "error", "message": f"function type not found: {type_id}"}

            updatable_fields = [
                "name", "display_name", "description",
                "logic_types", "expression_schema",
                "related_object_types", "version_id",
            ]
            for field in updatable_fields:
                if field in updates:
                    function_type[field] = updates[field]

            self.storage.save_function_type(function_type)
            return function_type
        except Exception as exc:
            return {"status": "error", "message": f"update_function_type failed: {exc}"}

    def delete_function_type(self, type_id: str) -> Dict[str, Any]:
        """删除逻辑函数类型定义"""
        try:
            ok = self.storage.delete_function_type(type_id)
            if not ok:
                return {"status": "error", "message": f"function type not found: {type_id}"}
            return {"type_id": type_id, "deleted": True}
        except Exception as exc:
            return {"status": "error", "message": f"delete_function_type failed: {exc}"}

    # ==================================================================
    # IndicatorType CRUD
    # ==================================================================

    def create_indicator_type(self, ontology_id: str, data: Dict) -> Dict[str, Any]:
        """创建指标类型定义"""
        try:
            if not data.get("name"):
                return {"status": "error", "message": "name is required for indicator type"}

            now = datetime.now(timezone.utc).isoformat()
            type_id = str(uuid.uuid4())

            indicator_type = {
                "type_id": type_id,
                "ontology_id": ontology_id,
                "version_id": data.get("version_id"),
                "name": data["name"],
                "display_name": data.get("display_name"),
                "description": data.get("description", ""),
                "indicator_types": data.get("indicator_types", ["kpi", "metric", "dimension"]),
                "formula_schema": data.get("formula_schema", {}),
                "allowed_units": data.get("allowed_units", []),
                "related_object_types": data.get("related_object_types", []),
                "created_at": now,
            }
            self.storage.save_indicator_type(indicator_type)
            return indicator_type
        except Exception as exc:
            return {"status": "error", "message": f"create_indicator_type failed: {exc}"}

    def list_indicator_types(self, ontology_id: str) -> Dict[str, Any]:
        """列出指标类型定义"""
        try:
            indicator_types = self.storage.list_indicator_types(ontology_id)
            return {"indicator_types": indicator_types, "count": len(indicator_types)}
        except Exception as exc:
            return {"status": "error", "message": f"list_indicator_types failed: {exc}"}

    def update_indicator_type(self, type_id: str, updates: Dict) -> Dict[str, Any]:
        """更新指标类型定义"""
        try:
            indicator_type = self.storage.get_indicator_type(type_id)
            if not indicator_type:
                return {"status": "error", "message": f"indicator type not found: {type_id}"}

            updatable_fields = [
                "name", "display_name", "description",
                "indicator_types", "formula_schema",
                "allowed_units", "related_object_types", "version_id",
            ]
            for field in updatable_fields:
                if field in updates:
                    indicator_type[field] = updates[field]

            self.storage.save_indicator_type(indicator_type)
            return indicator_type
        except Exception as exc:
            return {"status": "error", "message": f"update_indicator_type failed: {exc}"}

    def delete_indicator_type(self, type_id: str) -> Dict[str, Any]:
        """删除指标类型定义"""
        try:
            ok = self.storage.delete_indicator_type(type_id)
            if not ok:
                return {"status": "error", "message": f"indicator type not found: {type_id}"}
            return {"type_id": type_id, "deleted": True}
        except Exception as exc:
            return {"status": "error", "message": f"delete_indicator_type failed: {exc}"}

    # ==================================================================
    # Graph Data
    # ==================================================================

    def get_ontology_graph(self, ontology_id: str) -> Dict[str, Any]:
        """获取本体图谱数据（节点 + 边）

        节点来自 object_type_definitions，边来自 link_type_definitions。
        """
        try:
            object_types = self.storage.list_object_types(ontology_id)
            link_types = self.storage.list_link_types(ontology_id)

            nodes = []
            for obj in object_types:
                nodes.append({
                    "id": obj["type_id"],
                    "name": obj["name"],
                    "display_name": obj.get("display_name"),
                    "type": "object_type",
                    "properties": {
                        "property_count": len(obj.get("properties", [])),
                        "link_count": len(obj.get("links", [])),
                        "classification_level": obj.get("classification_level", "U"),
                    },
                })

            edges = []
            for link in link_types:
                edges.append({
                    "id": link["link_id"],
                    "source": link["source_type"],
                    "target": link["target_type"],
                    "name": link["name"],
                    "type": link.get("link_type", "ASSOCIATION").lower(),
                    "cardinality": link.get("cardinality", "ONE_TO_MANY"),
                })

            return {"nodes": nodes, "edges": edges}
        except Exception as exc:
            return {"status": "error", "message": f"get_ontology_graph failed: {exc}"}

    # ==================================================================
    # Database Connection
    # ==================================================================

    def save_database_connection(self, data: Dict) -> Dict[str, Any]:
        """保存数据库连接配置"""
        try:
            if not data.get("name"):
                return {"status": "error", "message": "name is required for database connection"}
            if not data.get("db_type"):
                return {"status": "error", "message": "db_type is required for database connection"}
            if not data.get("database"):
                return {"status": "error", "message": "database is required for database connection"}
            if not data.get("workspace_id"):
                return {"status": "error", "message": "workspace_id is required for database connection"}

            now = datetime.now(timezone.utc).isoformat()
            connection_id = data.get("connection_id") or str(uuid.uuid4())

            conn_data = {
                "connection_id": connection_id,
                "name": data["name"],
                "db_type": data["db_type"],
                "host": data.get("host", "localhost"),
                "port": data.get("port"),
                "database": data["database"],
                "username": data.get("username"),
                "password_encrypted": data.get("password_encrypted"),
                "workspace_id": data["workspace_id"],
                "created_at": now,
            }
            self.storage.save_database_connection(conn_data)
            return conn_data
        except Exception as exc:
            return {"status": "error", "message": f"save_database_connection failed: {exc}"}

    def list_database_connections(self, workspace_id: str) -> Dict[str, Any]:
        """列出数据库连接配置"""
        try:
            connections = self.storage.list_database_connections(workspace_id)
            return {"connections": connections, "count": len(connections)}
        except Exception as exc:
            return {"status": "error", "message": f"list_database_connections failed: {exc}"}

    def delete_database_connection(self, connection_id: str) -> Dict[str, Any]:
        """删除数据库连接配置"""
        try:
            ok = self.storage.delete_database_connection(connection_id)
            if not ok:
                return {"status": "error", "message": f"database connection not found: {connection_id}"}
            return {"connection_id": connection_id, "deleted": True}
        except Exception as exc:
            return {"status": "error", "message": f"delete_database_connection failed: {exc}"}

    # ==================================================================
    # Extraction Session
    # ==================================================================

    def create_extraction_session(
        self,
        ontology_id: str,
        extraction_type: str,
        input_data: Dict,
        session_id: str = None,
    ) -> Dict[str, Any]:
        """创建抽取/提取会话"""
        try:
            if not extraction_type:
                return {"status": "error", "message": "extraction_type is required"}

            now = datetime.now(timezone.utc).isoformat()
            session_id = session_id or str(uuid.uuid4())

            session = {
                "session_id": session_id,
                "ontology_id": ontology_id,
                "extraction_type": extraction_type,
                "status": "pending",
                "input_data": input_data,
                "result_data": None,
                "conflicts": [],
                "created_at": now,
            }
            self.storage.save_extraction_session(session)
            return session
        except Exception as exc:
            return {"status": "error", "message": f"create_extraction_session failed: {exc}"}

    def get_extraction_session(self, session_id: str) -> Dict[str, Any]:
        """获取抽取/提取会话"""
        try:
            session = self.storage.get_extraction_session(session_id)
            if not session:
                return {"status": "error", "message": f"extraction session not found: {session_id}"}
            return session
        except Exception as exc:
            return {"status": "error", "message": f"get_extraction_session failed: {exc}"}

    def update_extraction_session(self, session_id: str, updates: Dict) -> Dict[str, Any]:
        """更新抽取/提取会话"""
        try:
            session = self.storage.get_extraction_session(session_id)
            if not session:
                return {"status": "error", "message": f"extraction session not found: {session_id}"}

            updatable_fields = ["status", "result_data", "conflicts", "input_data"]
            for field in updatable_fields:
                if field in updates:
                    session[field] = updates[field]

            self.storage.save_extraction_session(session)
            return session
        except Exception as exc:
            return {"status": "error", "message": f"update_extraction_session failed: {exc}"}

    # ==================================================================
    # 内部工具方法
    # ==================================================================

    def _build_schema_snapshot(self, ontology_id: str) -> Dict[str, Any]:
        """构建当前本体的 Schema 快照

        收集所有类型定义，序列化为可存储的 JSON 结构。
        """
        return {
            "object_types": self.storage.list_object_types(ontology_id),
            "link_types": self.storage.list_link_types(ontology_id),
            "action_types": self.storage.list_action_types(ontology_id),
            "process_types": self.storage.list_process_types(ontology_id),
            "rule_types": self.storage.list_rule_types(ontology_id),
            "function_types": self.storage.list_function_types(ontology_id),
            "indicator_types": self.storage.list_indicator_types(ontology_id),
        }

    @staticmethod
    def _increment_minor_version(version_number: str) -> str:
        """递增 minor 版本号

        例: "0.1.0" -> "0.2.0", "1.3.5" -> "1.4.5"
        """
        try:
            parts = version_number.split(".")
            if len(parts) != 3:
                return "0.2.0"
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{major}.{minor + 1}.0"
        except (ValueError, IndexError):
            return "0.2.0"
