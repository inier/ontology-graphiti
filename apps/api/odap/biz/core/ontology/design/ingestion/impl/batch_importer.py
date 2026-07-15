import csv
import io
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BatchImporter:
    def __init__(self, storage=None):
        self.storage = storage

    def _validate_against_entity_type(self, entity_type_id: str, properties: Dict[str, Any]) -> Optional[str]:
        """根据实体类型定义验证属性完整性，返回错误信息或 None"""
        try:
            from odap.biz.core.ontology.model.storage.sqlite_model_storage import SQLiteModelStorage
            model_storage = SQLiteModelStorage()
            entity_type = model_storage.get_entity_type(entity_type_id)
            if not entity_type:
                return None  # 实体类型不存在时跳过验证（由后续逻辑处理）
            et_props = entity_type.get("properties", [])
            for prop_def in et_props:
                if prop_def.get("required", False):
                    prop_name = prop_def.get("name", "")
                    if prop_name not in properties or properties[prop_name] is None or properties[prop_name] == "":
                        return f"Required property '{prop_name}' is missing"
            return None
        except Exception:
            return None  # 验证失败时不阻塞导入流程

    def import_csv(self, entity_type_id: str, data: str, workspace_id: str) -> Dict[str, Any]:
        success_count = 0
        fail_count = 0
        errors = []

        try:
            reader = csv.DictReader(io.StringIO(data))
            for row_idx, row in enumerate(reader):
                try:
                    row["entity_type_id"] = entity_type_id
                    row["workspace_id"] = workspace_id
                    if "id" not in row or not row["id"]:
                        row["id"] = str(uuid.uuid4())
                    now = datetime.now().isoformat()
                    properties = {k: v for k, v in row.items() if k not in ("id", "entity_type_id", "workspace_id")}

                    # 验证属性完整性：根据实体类型定义检查必填属性
                    validation_error = self._validate_against_entity_type(entity_type_id, properties)
                    if validation_error:
                        fail_count += 1
                        errors.append({"row": row_idx + 1, "error": validation_error})
                        continue

                    instance = {
                        "instance_id": row["id"],
                        "type_id": entity_type_id,
                        "properties": properties,
                        "workspace_id": workspace_id,
                        "created_at": now,
                        "updated_at": now,
                    }
                    if self.storage is not None:
                        self.storage.save_instance(instance)
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    errors.append({"row": row_idx + 1, "error": str(e)})

            return {
                "status": "success",
                "success_count": success_count,
                "fail_count": fail_count,
                "errors": errors,
                "format": "csv",
                "entity_type_id": entity_type_id,
                "workspace_id": workspace_id,
            }
        except Exception as e:
            logger.warning("CSV import failed: %s", e)
            return {
                "status": "error",
                "success_count": 0,
                "fail_count": 0,
                "errors": [{"row": 0, "error": str(e)}],
                "format": "csv",
                "entity_type_id": entity_type_id,
                "workspace_id": workspace_id,
            }

    def import_json(self, entity_type_id: str, data: Any, workspace_id: str) -> Dict[str, Any]:
        success_count = 0
        fail_count = 0
        errors = []

        try:
            if isinstance(data, str):
                parsed = json.loads(data)
            else:
                parsed = data

            items = parsed if isinstance(parsed, list) else [parsed]

            for idx, item in enumerate(items):
                try:
                    if not isinstance(item, dict):
                        fail_count += 1
                        errors.append({"index": idx, "error": "Item is not a dict"})
                        continue
                    item["entity_type_id"] = entity_type_id
                    item["workspace_id"] = workspace_id
                    if "id" not in item or not item["id"]:
                        item["id"] = str(uuid.uuid4())
                    now = datetime.now().isoformat()
                    instance = {
                        "instance_id": item["id"],
                        "type_id": entity_type_id,
                        "properties": {k: v for k, v in item.items() if k not in ("id", "entity_type_id", "workspace_id")},
                        "workspace_id": workspace_id,
                        "created_at": now,
                        "updated_at": now,
                    }
                    if self.storage is not None:
                        self.storage.save_instance(instance)
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    errors.append({"index": idx, "error": str(e)})

            return {
                "status": "success",
                "success_count": success_count,
                "fail_count": fail_count,
                "errors": errors,
                "format": "json",
                "entity_type_id": entity_type_id,
                "workspace_id": workspace_id,
            }
        except Exception as e:
            logger.warning("JSON import failed: %s", e)
            return {
                "status": "error",
                "success_count": 0,
                "fail_count": 0,
                "errors": [{"index": 0, "error": str(e)}],
                "format": "json",
                "entity_type_id": entity_type_id,
                "workspace_id": workspace_id,
            }
