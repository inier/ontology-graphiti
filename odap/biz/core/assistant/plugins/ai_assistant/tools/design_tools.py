"""Design tools — ontology context, suggestions, completeness check.

Migrated from odap.biz.core.assistant.tools (original _suggest_*, _get_*, _check_* functions).
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from difflib import get_close_matches
from typing import Any, Dict

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolResult, ToolExecutionContext

logger = logging.getLogger(__name__)

# ── Type name alias table (Chinese → English candidates) ─────────────────────────
TYPE_NAME_ALIASES: Dict[str, list[str]] = {
    "里程碑": ["milestone"],
    "任务": ["task", "mission", "assignment"],
    "用户": ["user", "member"],
    "人员": ["user", "member", "person", "personnel"],
    "订单": ["order"],
    "产品": ["product", "item"],
    "商品": ["product", "item"],
    "事件": ["event", "incident"],
    "位置": ["location", "place"],
    "地点": ["location", "place"],
    "资产": ["asset"],
    "设备": ["device", "equipment"],
    "装备": ["equipment", "device"],
    "组织": ["organization", "org", "unit"],
    "单位": ["unit", "organization"],
    "团队": ["team", "group"],
    "报告": ["report"],
    "分析": ["analysis"],
    "战役": ["battle", "campaign"],
    "作战": ["operation", "battle", "campaign"],
    "武器": ["weapon"],
    "目标": ["target", "goal", "objective"],
    "情报": ["intelligence", "intel"],
    "威胁": ["threat"],
    "区域": ["region", "area", "zone"],
    "系统": ["system"],
    "日志": ["log", "record"],
    "记录": ["record", "log"],
    "规则": ["rule"],
    "策略": ["strategy", "policy"],
    "权限": ["permission", "role"],
    "角色": ["role"],
    "项目": ["project"],
    "文档": ["document", "doc"],
    "消息": ["message"],
    "通知": ["notification"],
    "标签": ["tag", "label"],
    "分类": ["category"],
    "评论": ["comment", "review"],
    "评分": ["rating", "score"],
    "平台": ["platform"],
    "传感器": ["sensor"],
    "信号": ["signal"],
    "载体": ["carrier", "vehicle"],
    "基地": ["base", "facility"],
    "设施": ["facility", "base"],
    "路线": ["route", "path"],
    "时间线": ["timeline"],
    "版本": ["version"],
    "快照": ["snapshot"],
}


# ── Input Models ──────────────────────────────────────────────────────────────────

class GetOntologyContextInput(BaseModel):
    """Arguments for getting ontology design context."""

    ontology_id: str = Field(description="Ontology ID to query")


class SuggestPropertiesInput(BaseModel):
    """Arguments for suggesting missing properties for an object type."""

    ontology_id: str = Field(description="Ontology ID")
    object_type_name: str = Field(description="Object type name (supports fuzzy matching)")


class SuggestRelationsInput(BaseModel):
    """Arguments for suggesting relationships for an object type."""

    ontology_id: str = Field(description="Ontology ID")
    object_type_name: str = Field(description="Object type name (supports fuzzy matching)")


class CheckCompletenessInput(BaseModel):
    """Arguments for checking ontology completeness."""

    ontology_id: str = Field(description="Ontology ID to check")


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _resolve_type_name(ontology_id: str, user_input: str, types: list | None = None) -> tuple:
    """Resolve type name with 5-level matching strategy.

    Returns (resolved_name, type_dict, all_types).
    """
    from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService

    if not user_input:
        return None, None, types or []

    if types is None:
        svc = OntologyService()
        types_resp = svc.list_object_types(ontology_id)
        types = types_resp.get("object_types", []) if isinstance(types_resp, dict) else []

    if not types:
        return None, None, types

    input_stripped = user_input.strip()
    input_lower = input_stripped.lower()

    # 1. Exact match (case-insensitive)
    for t in types:
        if t.get("name", "").lower() == input_lower:
            return t["name"], t, types

    # 2. Chinese-English alias mapping
    if input_stripped in TYPE_NAME_ALIASES:
        en_names = [en.lower() for en in TYPE_NAME_ALIASES[input_stripped]]
        for t in types:
            if t.get("name", "").lower() in en_names:
                return t["name"], t, types

    # 2b. Reverse: English input → Chinese alias
    for cn, en_list in TYPE_NAME_ALIASES.items():
        if input_lower in [en.lower() for en in en_list]:
            for t in types:
                if t.get("name", "").lower() == cn.lower():
                    return t["name"], t, types

    # 3. Substring match (≥2 chars)
    if len(input_lower) >= 2:
        for t in types:
            t_name_lower = t.get("name", "").lower()
            if t_name_lower and (input_lower in t_name_lower or t_name_lower in input_lower):
                return t["name"], t, types

    # 4. Description field match
    if len(input_lower) >= 2:
        for t in types:
            desc = (t.get("description") or "").lower()
            if input_lower in desc:
                return t["name"], t, types

    # 5. Fuzzy match by edit distance
    type_names = [t.get("name", "") for t in types if t.get("name")]
    matches = get_close_matches(input_stripped, type_names, n=1, cutoff=0.6)
    if matches:
        for t in types:
            if t.get("name") == matches[0]:
                return matches[0], t, types

    return None, None, types


# ── Tools ───────────────────────────────────────────────────────────────────────

class GetOntologyContextTool(BaseTool):
    """Get current ontology design state: types, properties, relationships, actions."""

    name = "get_ontology_context"
    description = (
        "获取当前本体设计的完整上下文：对象类型、属性、关系、动作类型。"
        "参数: ontology_id(必填)。"
        "基于本体进行查询——通过 OntologyService 获取类型/关系/动作定义。"
    )
    input_model = GetOntologyContextInput

    def is_read_only(self, arguments: GetOntologyContextInput) -> bool:
        return True

    async def execute(self, arguments: GetOntologyContextInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService

            svc = OntologyService()
            types_resp = svc.list_object_types(arguments.ontology_id)
            links_resp = svc.list_link_types(arguments.ontology_id)
            actions_resp = svc.list_action_types(arguments.ontology_id)

            obj_types = types_resp.get("object_types", []) if isinstance(types_resp, dict) else []
            link_types = links_resp.get("link_types", []) if isinstance(links_resp, dict) else []
            action_types = actions_resp.get("action_types", []) if isinstance(actions_resp, dict) else []

            summary = {
                "ontology_id": arguments.ontology_id,
                "object_type_count": len(obj_types),
                "link_type_count": len(link_types),
                "action_type_count": len(action_types),
                "object_types": [
                    {
                        "name": t.get("name", ""),
                        "property_count": len(t.get("properties", [])),
                        "properties": [p.get("name", "") for p in t.get("properties", [])],
                    }
                    for t in obj_types
                ],
                "link_types": [
                    {
                        "name": l.get("name", ""),
                        "source": l.get("source_type", ""),
                        "target": l.get("target_type", ""),
                        "cardinality": l.get("cardinality", "ONE_TO_MANY"),
                    }
                    for l in link_types
                ],
                "action_types": [
                    {
                        "name": a.get("name", ""),
                        "target": a.get("target_object_type", ""),
                        "parameters": a.get("parameters", []),
                    }
                    for a in action_types
                ],
            }
            return ToolResult(output=json.dumps(summary, ensure_ascii=False), is_error=False, metadata=summary)
        except Exception as e:
            logger.warning("GetOntologyContextTool failed: %s", e)
            return ToolResult(output=f"获取本体上下文失败: {e}", is_error=True)


class SuggestPropertiesTool(BaseTool):
    """Intelligently suggest missing properties based on ontology patterns."""

    name = "suggest_properties"
    description = (
        "建议为某个对象类型添加缺失的常用属性。"
        "参数: ontology_id(必填), object_type_name(必填,支持中英文模糊匹配)。"
        "基于本体进行查询——分析现有类型的属性分布，给出智能建议。"
    )
    input_model = SuggestPropertiesInput

    def is_read_only(self, arguments: SuggestPropertiesInput) -> bool:
        return True

    async def execute(self, arguments: SuggestPropertiesInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService
            from odap.biz.core.ontology.assistant.rules.type_inference import TypeInferenceEngine

            ont_svc = OntologyService()
            types_resp = ont_svc.list_object_types(arguments.ontology_id)
            types = types_resp.get("object_types", []) if isinstance(types_resp, dict) else []

            if not types:
                output = {
                    "status": "success",
                    "suggestions": [],
                    "count": 0,
                    "hint": "本体中尚无对象类型，请先创建类型。",
                }
                return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)

            # Resolve type name
            resolved_name, target_type, _ = _resolve_type_name(
                arguments.ontology_id, arguments.object_type_name, types
            )

            if not target_type:
                all_names = [t.get("name", "") for t in types]
                output = {
                    "status": "success",
                    "suggestions": [],
                    "count": 0,
                    "hint": f"本体中没有「{arguments.object_type_name}」。现有: {', '.join(all_names)}",
                }
                return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)

            existing_properties = [p.get("name", "") for p in target_type.get("properties", [])]
            existing_set = set(existing_properties)

            # Learn common properties from ontology
            prop_counter: Counter = Counter()
            for t in types:
                for p in t.get("properties", []):
                    prop_counter[p.get("name", "")] += 1

            threshold = max(2, len(types) // 3)
            common_props = {name for name, cnt in prop_counter.items() if cnt >= threshold}

            # Domain-specific heuristics
            name_lower = (resolved_name + " " + arguments.object_type_name).lower()
            domain_suggestions: Dict[str, str] = {}

            if "name" not in existing_set:
                domain_suggestions["name"] = "STRING"
            if "description" not in existing_set:
                domain_suggestions["description"] = "STRING"

            # Type-name-based heuristics (same logic as original)
            if any(kw in name_lower for kw in ("user", "人员", "用户", "member", "员工")):
                for p, dt in [("email", "STRING"), ("phone", "STRING"), ("is_active", "BOOLEAN")]:
                    if p not in existing_set:
                        domain_suggestions[p] = dt
            elif any(kw in name_lower for kw in ("order", "订单")):
                for p, dt in [("status", "STRING"), ("total_amount", "FLOAT"), ("user_id", "STRING")]:
                    if p not in existing_set:
                        domain_suggestions[p] = dt
            elif any(kw in name_lower for kw in ("product", "产品", "商品", "item")):
                for p, dt in [("price", "FLOAT"), ("stock", "INTEGER"), ("category", "STRING")]:
                    if p not in existing_set:
                        domain_suggestions[p] = dt
            elif any(kw in name_lower for kw in ("task", "任务", "mission", "assignment")):
                for p, dt in [("status", "STRING"), ("priority", "STRING"), ("assignee_id", "STRING"), ("due_date", "DATETIME")]:
                    if p not in existing_set:
                        domain_suggestions[p] = dt
            elif any(kw in name_lower for kw in ("milestone", "里程碑")):
                for p, dt in [("status", "STRING"), ("target_date", "DATETIME"), ("actual_date", "DATETIME"), ("progress", "INTEGER"), ("owner_id", "STRING")]:
                    if p not in existing_set:
                        domain_suggestions[p] = dt
            elif any(kw in name_lower for kw in ("event", "事件", "incident")):
                for p, dt in [("event_type", "STRING"), ("severity", "STRING"), ("occurred_at", "DATETIME"), ("location", "STRING")]:
                    if p not in existing_set:
                        domain_suggestions[p] = dt
            elif any(kw in name_lower for kw in ("location", "位置", "地点", "region", "区域")):
                for p, dt in [("latitude", "FLOAT"), ("longitude", "FLOAT"), ("address", "STRING")]:
                    if p not in existing_set:
                        domain_suggestions[p] = dt
            elif any(kw in name_lower for kw in ("asset", "资产", "device", "设备", "equipment", "装备")):
                for p, dt in [("asset_type", "STRING"), ("status", "STRING"), ("serial_number", "STRING")]:
                    if p not in existing_set:
                        domain_suggestions[p] = dt
            elif any(kw in name_lower for kw in ("organization", "组织", "unit", "单位", "team", "团队")):
                for p, dt in [("org_type", "STRING"), ("parent_id", "STRING")]:
                    if p not in existing_set:
                        domain_suggestions[p] = dt
            elif any(kw in name_lower for kw in ("report", "报告", "analysis", "分析")):
                for p, dt in [("report_type", "STRING"), ("author", "STRING"), ("published_at", "DATETIME")]:
                    if p not in existing_set:
                        domain_suggestions[p] = dt

            # Also suggest common properties from OTHER types
            for prop in common_props - existing_set:
                if prop not in domain_suggestions:
                    domain_suggestions[prop] = "STRING"

            # Use TypeInferenceEngine for accurate data types
            engine = TypeInferenceEngine()
            suggestions = []
            for prop_name, data_type in domain_suggestions.items():
                inferred = engine.infer_type(prop_name)
                suggestions.append({
                    "name": prop_name,
                    "data_type": inferred.get("inferred_type", data_type),
                    "confidence": inferred.get("confidence", 0.5),
                })

            suggestions.sort(key=lambda s: -s.get("confidence", 0))
            suggestions = suggestions[:10]

            output = {
                "status": "success",
                "suggestions": suggestions,
                "count": len(suggestions),
            }
            return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("SuggestPropertiesTool failed: %s", e)
            return ToolResult(output=f"属性建议失败: {e}", is_error=True)


class SuggestRelationsTool(BaseTool):
    """Intelligently suggest relationships based on ontology structure and naming."""

    name = "suggest_relations"
    description = (
        "建议为某个对象类型添加可能的关系。"
        "参数: ontology_id(必填), object_type_name(必填,支持中英文模糊匹配)。"
        "基于本体进行查询——分析类型间的命名关联和领域模式，给出关系建议。"
    )
    input_model = SuggestRelationsInput

    def is_read_only(self, arguments: SuggestRelationsInput) -> bool:
        return True

    async def execute(self, arguments: SuggestRelationsInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService

            svc = OntologyService()
            types_resp = svc.list_object_types(arguments.ontology_id)
            links_resp = svc.list_link_types(arguments.ontology_id)
            types = types_resp.get("object_types", []) if isinstance(types_resp, dict) else []
            links = links_resp.get("link_types", []) if isinstance(links_resp, dict) else []

            if len(types) < 2:
                output = {
                    "status": "success",
                    "suggestions": [],
                    "count": 0,
                    "hint": "本体中类型不足，至少需要 2 个对象类型才能分析关系。",
                }
                return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)

            resolved_name, _, _ = _resolve_type_name(
                arguments.ontology_id, arguments.object_type_name, types
            )

            if not resolved_name:
                all_names = [t.get("name", "") for t in types]
                output = {
                    "status": "success",
                    "suggestions": [],
                    "count": 0,
                    "hint": f"本体中没有「{arguments.object_type_name}」。现有: {', '.join(all_names)}",
                }
                return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)

            existing_pairs = set()
            for l in links:
                src = l.get("source_type", "").lower()
                tgt = l.get("target_type", "").lower()
                existing_pairs.add((src, tgt))

            src_lower = resolved_name.lower()

            scored: list[tuple[int, str, str, str]] = []
            for t in types:
                t_name = t.get("name", "")
                tgt_lower = t_name.lower()
                if not t_name or tgt_lower == src_lower:
                    continue

                score = 0
                if f"has_{tgt_lower}" not in {l.get("name", "").lower() for l in links}:
                    if tgt_lower in src_lower or src_lower in tgt_lower:
                        score += 3
                    if src_lower in ("user", "人员") and any(kw in tgt_lower for kw in ("role", "权限", "team", "组织")):
                        score += 2
                    if src_lower in ("order", "订单") and any(kw in tgt_lower for kw in ("product", "商品", "user", "customer")):
                        score += 2
                    if any(kw in src_lower for kw in ("battle", "战役", "operation", "作战")) and any(kw in tgt_lower for kw in ("unit", "单位", "force", "weapon", "武器")):
                        score += 3
                    if src_lower in ("task", "任务") and any(kw in tgt_lower for kw in ("user", "人员", "unit", "单位")):
                        score += 2
                    if src_lower in ("milestone", "里程碑") and any(kw in tgt_lower for kw in ("task", "任务", "project", "项目")):
                        score += 3

                if score > 0:
                    link_name = f"has_{tgt_lower}" if "_" not in tgt_lower else f"related_to_{tgt_lower}"
                    if (src_lower, tgt_lower) not in existing_pairs:
                        scored.append((score, link_name, resolved_name, t_name))

            scored.sort(key=lambda x: -x[0])
            suggestions = [
                {"name": name, "source_type": src, "target_type": tgt, "cardinality": "ONE_TO_MANY", "relevance": score}
                for score, name, src, tgt in scored[:6]
            ]

            if not suggestions:
                output = {
                    "status": "success",
                    "suggestions": [],
                    "count": 0,
                    "hint": f"「{resolved_name}」与其他类型之间暂时没有明显的关系建议。可以手动添加 has_ 或 belongs_to 关系。",
                }
                return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)

            output = {"status": "success", "suggestions": suggestions, "count": len(suggestions)}
            return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("SuggestRelationsTool failed: %s", e)
            return ToolResult(output=f"关系建议失败: {e}", is_error=True)


class CheckCompletenessTool(BaseTool):
    """Run completeness check on the current ontology."""

    name = "check_completeness"
    description = (
        "检查本体的完整性：孤儿类型、缺失审计字段、缺失状态字段、缺失描述。"
        "参数: ontology_id(必填)。"
        "基于本体进行查询——通过 OntologyService 获取完整类型定义后执行完整性分析。"
    )
    input_model = CheckCompletenessInput

    def is_read_only(self, arguments: CheckCompletenessInput) -> bool:
        return True

    async def execute(self, arguments: CheckCompletenessInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService
            from odap.biz.core.ontology.assistant.tools.completeness_check import completeness_check

            svc = OntologyService()
            types_resp = svc.list_object_types(arguments.ontology_id)
            links_resp = svc.list_link_types(arguments.ontology_id)
            actions_resp = svc.list_action_types(arguments.ontology_id)

            types = types_resp.get("object_types", []) if isinstance(types_resp, dict) else []
            links = links_resp.get("link_types", []) if isinstance(links_resp, dict) else []
            actions = actions_resp.get("action_types", []) if isinstance(actions_resp, dict) else []

            if not types:
                output = {
                    "status": "success",
                    "summary": {
                        "orphan_count": 0,
                        "missing_audit_count": 0,
                        "missing_status_count": 0,
                        "missing_description_count": 0,
                    },
                    "details": [],
                    "hint": "本体中尚未定义任何对象类型，请先创建类型后再运行完整性检查。",
                }
                return ToolResult(output=json.dumps(output, ensure_ascii=False), is_error=False, metadata=output)

            result = completeness_check(
                ontology_id=arguments.ontology_id,
                object_types=types,
                link_types=links,
                action_types=actions,
            )
            return ToolResult(output=json.dumps(result, ensure_ascii=False), is_error=False, metadata=result)
        except Exception as e:
            logger.warning("CheckCompletenessTool failed: %s", e)
            return ToolResult(output=f"完整性检查失败: {e}", is_error=True)
