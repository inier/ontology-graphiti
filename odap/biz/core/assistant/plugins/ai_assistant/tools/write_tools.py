"""Write tools — ontology mutation operations (create/update/delete types & properties).

Migrated from odap.biz.core.assistant.tools (original _add_property_*,
_create_*, _delete_*, _update_* functions).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolResult, ToolExecutionContext

logger = logging.getLogger(__name__)

# ── Re-use type name resolution from design_tools ────────────────────────────
# design_tools defines _resolve_type_name; import it to avoid duplication.
from odap.biz.core.assistant.plugins.ai_assistant.tools.design_tools import (  # noqa: E501
    _resolve_type_name,
)


# ── Input Models ─────────────────────────────────────────────────────────────

class AddPropertyInput(BaseModel):
    """Arguments for adding a property to an object type."""

    ontology_id: str = Field(description="Ontology ID")
    object_type_name: str = Field(description="Object type name (supports fuzzy matching)")
    property_name: str = Field(description="Property name to add")
    data_type: str = Field(default="STRING", description="Data type: STRING/INTEGER/FLOAT/BOOLEAN/DATETIME/TEXT")
    description: str = Field(default="", description="Property description")
    is_required: bool = Field(default=False, description="Whether this property is required")


class UpdatePropertyInput(BaseModel):
    """Arguments for updating a property in an object type."""

    ontology_id: str = Field(description="Ontology ID")
    object_type_name: str = Field(description="Object type name (supports fuzzy matching)")
    property_name: str = Field(description="Property name to update")
    data_type: str | None = Field(default=None, description="New data type (optional)")
    description: str | None = Field(default=None, description="New description (optional)")
    is_required: bool | None = Field(default=None, description="New required flag (optional)")


class RemovePropertyInput(BaseModel):
    """Arguments for removing a property from an object type."""

    ontology_id: str = Field(description="Ontology ID")
    object_type_name: str = Field(description="Object type name (supports fuzzy matching)")
    property_name: str = Field(description="Property name to remove")


class CreateObjectTypeInput(BaseModel):
    """Arguments for creating a new object type."""

    ontology_id: str = Field(description="Ontology ID")
    name: str = Field(description="Object type name")
    description: str = Field(default="", description="Object type description")
    properties: str = Field(
        default="[]",
        description=(
            "Properties as JSON string, e.g. '[{\"name\":\"id\",\"data_type\":\"STRING\"}]'"
        ),
    )


class DeleteObjectTypeInput(BaseModel):
    """Arguments for deleting an object type."""

    ontology_id: str = Field(description="Ontology ID")
    object_type_name: str = Field(description="Object type name to delete (supports fuzzy matching)")


class CreateLinkTypeInput(BaseModel):
    """Arguments for creating a relationship type."""

    ontology_id: str = Field(description="Ontology ID")
    name: str = Field(description="Relationship/link type name")
    source_type: str = Field(description="Source object type name (supports fuzzy matching)")
    target_type: str = Field(description="Target object type name (supports fuzzy matching)")
    cardinality: str = Field(
        default="ONE_TO_MANY",
        description="Cardinality: ONE_TO_ONE/ONE_TO_MANY/MANY_TO_ONE/MANY_TO_MANY",
    )
    description: str = Field(default="", description="Relationship description")


class DeleteLinkTypeInput(BaseModel):
    """Arguments for deleting a relationship type."""

    ontology_id: str = Field(description="Ontology ID")
    link_name: str = Field(description="Relationship/link type name to delete")


class AddPropertiesBatchInput(BaseModel):
    """Arguments for batch-adding multiple properties (atomic write)."""

    ontology_id: str = Field(description="Ontology ID")
    object_type_name: str = Field(description="Object type name (supports fuzzy matching, including Chinese)")
    properties: str = Field(
        description=(
            "Properties as JSON string. Two formats supported: "
            "1. Object array: [{\"name\":\"status\",\"data_type\":\"STRING\"}]  "
            "2. Key-value: {\"status\":\"STRING\",\"priority\":\"INTEGER\"}"
        ),
    )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _classify_intent(properties_str: str) -> str:
    """Classify user intent from properties string.

    Returns: 'json_array' | 'json_kv' | 'unknown'
    """
    stripped = properties_str.strip()
    if not stripped:
        return "unknown"
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            return "json_array"
        if isinstance(parsed, dict):
            return "json_kv"
    except (json.JSONDecodeError, TypeError):
        pass
    return "unknown"


# ── Tools ──────────────────────────────────────────────────────────────────

class AddPropertyTool(BaseTool):
    """Add a single property to an object type."""

    name = "add_property"
    description = (
        "给对象类型新增一个属性。"
        "参数: ontology_id(必填), object_type_name(必填,类型名,支持中英文模糊匹配), "
        "property_name(必填,属性名), data_type(可选,默认STRING), "
        "description(可选), is_required(可选,布尔值)。"
        "基于本体进行修改——通过 OntologyService.update_object_type() 持久化。"
    )
    input_model = AddPropertyInput

    async def execute(self, arguments: AddPropertyInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService

            _, target, _ = _resolve_type_name(arguments.ontology_id, arguments.object_type_name)
            if not target:
                return ToolResult(
                    output=f"对象类型「{arguments.object_type_name}」不存在",
                    is_error=True,
                )

            props = target.get("properties", [])
            existing_names = {p.get("name", "").lower() for p in props}
            if arguments.property_name.lower() in existing_names:
                return ToolResult(
                    output=f"属性「{arguments.property_name}」已存在于「{arguments.object_type_name}」中",
                    is_error=True,
                )

            props.append({
                "name": arguments.property_name,
                "data_type": arguments.data_type.upper(),
                "description": arguments.description,
                "is_required": arguments.is_required,
            })

            svc = OntologyService()
            result = svc.update_object_type(target["type_id"], {"properties": props})
            if result.get("status") == "error":
                return ToolResult(output=result.get("message", "更新失败"), is_error=True)

            logger.info("AI助手: 为「%s」新增属性「%s」(%s)", arguments.object_type_name, arguments.property_name, arguments.data_type)
            output = {
                "status": "success",
                "action": "add_property",
                "object_type": arguments.object_type_name,
                "property_name": arguments.property_name,
                "data_type": arguments.data_type,
                "message": f"已为「{arguments.object_type_name}」成功新增属性「{arguments.property_name}」({arguments.data_type})",
                "_ontology_changed": True,
            }
            return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("AddPropertyTool failed: %s", e)
            return ToolResult(output=f"新增属性失败: {e}", is_error=True)


class UpdatePropertyTool(BaseTool):
    """Update an existing property in an object type."""

    name = "update_property"
    description = (
        "更新对象类型的属性。"
        "参数: ontology_id(必填), object_type_name(必填), property_name(必填), "
        "data_type(可选), description(可选), is_required(可选)。"
        "基于本体进行修改——通过 OntologyService.update_object_type() 持久化。"
    )
    input_model = UpdatePropertyInput

    async def execute(self, arguments: UpdatePropertyInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService

            _, target, _ = _resolve_type_name(arguments.ontology_id, arguments.object_type_name)
            if not target:
                return ToolResult(
                    output=f"对象类型「{arguments.object_type_name}」不存在",
                    is_error=True,
                )

            props = target.get("properties", [])
            found = False
            for p in props:
                if p.get("name", "").lower() == arguments.property_name.lower():
                    if arguments.data_type is not None:
                        p["data_type"] = arguments.data_type.upper()
                    if arguments.description is not None:
                        p["description"] = arguments.description
                    if arguments.is_required is not None:
                        p["is_required"] = arguments.is_required
                    found = True
                    break

            if not found:
                return ToolResult(
                    output=f"属性「{arguments.property_name}」不存在于「{arguments.object_type_name}」中",
                    is_error=True,
                )

            svc = OntologyService()
            result = svc.update_object_type(target["type_id"], {"properties": props})
            if result.get("status") == "error":
                return ToolResult(output=result.get("message", "更新失败"), is_error=True)

            logger.info("AI助手: 更新「%s.%s」属性", arguments.object_type_name, arguments.property_name)
            output = {
                "status": "success",
                "action": "update_property",
                "object_type": arguments.object_type_name,
                "property_name": arguments.property_name,
                "message": f"已更新「{arguments.object_type_name}.{arguments.property_name}」属性",
                "_ontology_changed": True,
            }
            return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("UpdatePropertyTool failed: %s", e)
            return ToolResult(output=f"更新属性失败: {e}", is_error=True)


class RemovePropertyTool(BaseTool):
    """Remove a property from an object type."""

    name = "remove_property"
    description = (
        "删除对象类型的属性。"
        "参数: ontology_id(必填), object_type_name(必填), property_name(必填)。"
        "基于本体进行修改——通过 OntologyService.update_object_type() 持久化。"
    )
    input_model = RemovePropertyInput

    async def execute(self, arguments: RemovePropertyInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService

            _, target, _ = _resolve_type_name(arguments.ontology_id, arguments.object_type_name)
            if not target:
                return ToolResult(
                    output=f"对象类型「{arguments.object_type_name}」不存在",
                    is_error=True,
                )

            props = target.get("properties", [])
            new_props = [p for p in props if p.get("name", "").lower() != arguments.property_name.lower()]
            if len(new_props) == len(props):
                return ToolResult(
                    output=f"属性「{arguments.property_name}」不存在于「{arguments.object_type_name}」中",
                    is_error=True,
                )

            svc = OntologyService()
            result = svc.update_object_type(target["type_id"], {"properties": new_props})
            if result.get("status") == "error":
                return ToolResult(output=result.get("message", "更新失败"), is_error=True)

            logger.info("AI助手: 从「%s」删除属性「%s」", arguments.object_type_name, arguments.property_name)
            output = {
                "status": "success",
                "action": "remove_property",
                "object_type": arguments.object_type_name,
                "property_name": arguments.property_name,
                "message": f"已从「{arguments.object_type_name}」删除属性「{arguments.property_name}」",
                "_ontology_changed": True,
            }
            return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("RemovePropertyTool failed: %s", e)
            return ToolResult(output=f"删除属性失败: {e}", is_error=True)


class CreateObjectTypeTool(BaseTool):
    """Create a new object type in the ontology."""

    name = "create_object_type"
    description = (
        "创建新的对象类型。"
        "参数: ontology_id(必填), name(必填,类型名), description(可选), "
        "properties(可选,JSON字符串如'[{\"name\":\"id\",\"data_type\":\"STRING\"}]')。"
        "基于本体进行创建——通过 OntologyService.create_object_type() 持久化。"
    )
    input_model = CreateObjectTypeInput

    async def execute(self, arguments: CreateObjectTypeInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService

            # Check for duplicate name
            _, existing, _ = _resolve_type_name(arguments.ontology_id, arguments.name)
            if existing:
                return ToolResult(
                    output=f"对象类型「{arguments.name}」已存在",
                    is_error=True,
                )

            # Parse properties
            parsed_props = []
            if arguments.properties:
                try:
                    parsed_props = json.loads(arguments.properties) if isinstance(arguments.properties, str) else arguments.properties
                except (json.JSONDecodeError, TypeError):
                    return ToolResult(output="properties 参数不是有效的 JSON", is_error=True)

            svc = OntologyService()
            result = svc.create_object_type(arguments.ontology_id, {
                "name": arguments.name,
                "description": arguments.description,
                "properties": parsed_props,
            })
            if result.get("status") == "error":
                return ToolResult(output=result.get("message", "创建失败"), is_error=True)

            logger.info("AI助手: 创建对象类型「%s」", arguments.name)
            output = {
                "status": "success",
                "action": "create_object_type",
                "object_type": arguments.name,
                "type_id": result.get("type_id"),
                "message": f"已创建对象类型「{arguments.name}」",
                "_ontology_changed": True,
            }
            return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("CreateObjectTypeTool failed: %s", e)
            return ToolResult(output=f"创建对象类型失败: {e}", is_error=True)


class DeleteObjectTypeTool(BaseTool):
    """Delete an object type from the ontology."""

    name = "delete_object_type"
    description = (
        "删除对象类型。"
        "参数: ontology_id(必填), object_type_name(必填,要删除的类型名,支持中英文模糊匹配)。"
        "基于本体进行删除——通过 OntologyService.delete_object_type() 持久化。"
    )
    input_model = DeleteObjectTypeInput

    async def execute(self, arguments: DeleteObjectTypeInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService

            _, target, _ = _resolve_type_name(arguments.ontology_id, arguments.object_type_name)
            if not target:
                return ToolResult(
                    output=f"对象类型「{arguments.object_type_name}」不存在",
                    is_error=True,
                )

            svc = OntologyService()
            result = svc.delete_object_type(target["type_id"])
            if result.get("status") == "error":
                return ToolResult(output=result.get("message", "删除失败"), is_error=True)

            logger.info("AI助手: 删除对象类型「%s」", arguments.object_type_name)
            output = {
                "status": "success",
                "action": "delete_object_type",
                "object_type": arguments.object_type_name,
                "message": f"已删除对象类型「{arguments.object_type_name}」",
                "_ontology_changed": True,
            }
            return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("DeleteObjectTypeTool failed: %s", e)
            return ToolResult(output=f"删除对象类型失败: {e}", is_error=True)


class CreateLinkTypeTool(BaseTool):
    """Create a new relationship/link type in the ontology."""

    name = "create_link_type"
    description = (
        "创建关系类型。"
        "参数: ontology_id(必填), name(必填,关系名), "
        "source_type(必填,源类型名,支持模糊匹配), target_type(必填,目标类型名,支持模糊匹配), "
        "cardinality(可选,默认ONE_TO_MANY), description(可选)。"
        "基于本体进行创建——通过 OntologyService.create_link_type() 持久化。"
    )
    input_model = CreateLinkTypeInput

    async def execute(self, arguments: CreateLinkTypeInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService

            # Resolve source and target types
            _, src, _ = _resolve_type_name(arguments.ontology_id, arguments.source_type)
            if not src:
                return ToolResult(
                    output=f"源对象类型「{arguments.source_type}」不存在",
                    is_error=True,
                )
            _, tgt, _ = _resolve_type_name(arguments.ontology_id, arguments.target_type)
            if not tgt:
                return ToolResult(
                    output=f"目标对象类型「{arguments.target_type}」不存在",
                    is_error=True,
                )

            svc = OntologyService()
            result = svc.create_link_type(arguments.ontology_id, {
                "name": arguments.name,
                "source_type": arguments.source_type,
                "target_type": arguments.target_type,
                "cardinality": arguments.cardinality.upper(),
                "description": arguments.description,
            })
            if result.get("status") == "error":
                return ToolResult(output=result.get("message", "创建失败"), is_error=True)

            logger.info("AI助手: 创建关系「%s」(%s→%s)", arguments.name, arguments.source_type, arguments.target_type)
            output = {
                "status": "success",
                "action": "create_link_type",
                "link_name": arguments.name,
                "source_type": arguments.source_type,
                "target_type": arguments.target_type,
                "message": f"已创建关系「{arguments.name}」({arguments.source_type}→{arguments.target_type})",
                "_ontology_changed": True,
            }
            return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("CreateLinkTypeTool failed: %s", e)
            return ToolResult(output=f"创建关系类型失败: {e}", is_error=True)


class DeleteLinkTypeTool(BaseTool):
    """Delete a relationship/link type from the ontology."""

    name = "delete_link_type"
    description = (
        "删除关系类型。"
        "参数: ontology_id(必填), link_name(必填,要删除的关系名)。"
        "基于本体进行删除——通过 OntologyService.delete_link_type() 持久化。"
    )
    input_model = DeleteLinkTypeInput

    async def execute(self, arguments: DeleteLinkTypeInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService

            svc = OntologyService()
            links_resp = svc.list_link_types(arguments.ontology_id)
            links = links_resp.get("link_types", []) if isinstance(links_resp, dict) else []

            target_link = None
            for l in links:
                if l.get("name", "").lower() == arguments.link_name.lower():
                    target_link = l
                    break

            if not target_link:
                return ToolResult(
                    output=f"关系类型「{arguments.link_name}」不存在",
                    is_error=True,
                )

            result = svc.delete_link_type(target_link["link_id"])
            if result.get("status") == "error":
                return ToolResult(output=result.get("message", "删除失败"), is_error=True)

            logger.info("AI助手: 删除关系「%s」", arguments.link_name)
            output = {
                "status": "success",
                "action": "delete_link_type",
                "link_name": arguments.link_name,
                "message": f"已删除关系「{arguments.link_name}」",
                "_ontology_changed": True,
            }
            return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("DeleteLinkTypeTool failed: %s", e)
            return ToolResult(output=f"删除关系类型失败: {e}", is_error=True)


class AddPropertiesBatchTool(BaseTool):
    """Batch-add multiple properties to an object type (atomic write)."""

    name = "add_properties"
    description = (
        "批量添加多个属性到对象类型（一次原子写入，高效）。"
        "参数: ontology_id(必填), object_type_name(必填,类型名,支持中英文如里程碑=Milestone), "
        "properties(必填,JSON字符串,支持两种格式: "
        "1.对象数组如'[{\"name\":\"status\",\"data_type\":\"STRING\"}]'  "
        "2.简化键值对如'{\"status\":\"STRING\",\"priority\":\"INTEGER\"}')。"
        "基于本体进行批量修改——通过 OntologyService.update_object_type() 一次持久化所有属性。"
    )
    input_model = AddPropertiesBatchInput

    async def execute(self, arguments: AddPropertiesBatchInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService

            # Parse properties
            try:
                props_data = json.loads(arguments.properties) if isinstance(arguments.properties, str) else arguments.properties
            except (json.JSONDecodeError, TypeError):
                return ToolResult(output="properties 参数不是有效的 JSON", is_error=True)

            # Normalize to list of dicts
            if isinstance(props_data, dict):
                props_list = [
                    {"name": k, "data_type": v if isinstance(v, str) else "STRING"}
                    for k, v in props_data.items()
                ]
            elif isinstance(props_data, list):
                props_list = props_data
            else:
                return ToolResult(output="properties 格式应为对象数组或键值对对象", is_error=True)

            if not props_list:
                return ToolResult(output="没有可添加的属性", is_error=True)

            # Resolve type name
            resolved_name, target, _ = _resolve_type_name(
                arguments.ontology_id, arguments.object_type_name
            )
            if not target:
                return ToolResult(
                    output=f"对象类型「{arguments.object_type_name}」不存在",
                    is_error=True,
                )

            existing_props = target.get("properties", [])
            existing_names = {p.get("name", "").lower() for p in existing_props}

            added: list[str] = []
            skipped: list[str] = []
            for prop in props_list:
                prop_name = prop.get("name", "") if isinstance(prop, dict) else str(prop)
                if not prop_name:
                    continue
                if prop_name.lower() in existing_names:
                    skipped.append(prop_name)
                    continue

                data_type = "STRING"
                if isinstance(prop, dict):
                    data_type = str(prop.get("data_type", "STRING")).upper()

                existing_props.append({
                    "name": prop_name,
                    "data_type": data_type,
                    "description": prop.get("description", "") if isinstance(prop, dict) else "",
                    "is_required": prop.get("is_required", False) if isinstance(prop, dict) else False,
                })
                existing_names.add(prop_name.lower())
                added.append(prop_name)

            if not added:
                output = {
                    "status": "success",
                    "action": "add_properties",
                    "object_type": resolved_name,
                    "added": [],
                    "skipped": skipped,
                    "message": f"所有属性均已存在于「{resolved_name}」中，跳过: {', '.join(skipped)}",
                }
                return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)

            svc = OntologyService()
            result = svc.update_object_type(target["type_id"], {"properties": existing_props})
            if result.get("status") == "error":
                return ToolResult(output=result.get("message", "更新失败"), is_error=True)

            msg = f"已为「{resolved_name}」批量新增 {len(added)} 个属性: {', '.join(added)}"
            if skipped:
                msg += f"\n跳过已存在的属性: {', '.join(skipped)}"

            logger.info("AI助手: 批量为「%s」新增 %d 个属性", resolved_name, len(added))
            output = {
                "status": "success",
                "action": "add_properties",
                "object_type": resolved_name,
                "added": added,
                "skipped": skipped,
                "message": msg,
                "_ontology_changed": True,
            }
            return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("AddPropertiesBatchTool failed: %s", e)
            return ToolResult(output=f"批量新增属性失败: {e}", is_error=True)
