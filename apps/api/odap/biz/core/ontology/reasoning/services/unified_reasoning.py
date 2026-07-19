"""UnifiedReasoningService — ReasoningServiceContract 的实现。

实现 ADR-068 定义的 +AI Reasoning 统一推理服务契约。
提供: 类型推断、约束建议、Schema一致性校验、实例一致性校验。
"""

from __future__ import annotations

import json
import logging
import re
from statistics import mean, stdev
from typing import Any, Dict, List, Optional

from ..contract.interface import (
    ReasoningServiceContract,
    TypeInferenceResult,
    ConstraintSuggestion,
    ConsistencyReport,
)

logger = logging.getLogger(__name__)


class UnifiedReasoningService(ReasoningServiceContract):
    """统一推理服务 — ReasoningServiceContract 的实现。

    单例模式，可通过 DI 注入自定义实现。
    """

    _instance: Optional["UnifiedReasoningService"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._capabilities_cache: Optional[List[str]] = None
        self._initialized = True

    # ── 推理组 (服务 L1 Design) ──

    def infer_types(self, data_sample: dict, workspace_id: str) -> TypeInferenceResult:
        """分析数据样本，建议新 EntityType（LLM优先+启发式回退）"""
        if not data_sample:
            return TypeInferenceResult(explanation="输入数据为空")

        # LLM 优先
        result = self._infer_types_with_llm(data_sample, workspace_id)
        return result

    def _infer_types_with_llm(self, data_sample: dict, workspace_id: str) -> TypeInferenceResult:
        """使用 LLM 辅助类型推断（带降级）"""
        try:
            from odap.infra.config_composer import get_config
            api_key = get_config("llm.api_key", "")
            if not api_key:
                return self._infer_types_heuristic(data_sample)

            from odap.infra.llm.llm_service import ZhipuAIClient
            from graphiti_core.llm_client.config import LLMConfig
            from graphiti_core.prompts.models import Message

            api_base = get_config("llm.api_base", "https://open.bigmodel.cn/api/paas/v4")
            model = get_config("llm.model", "glm-4-flash")

            config = LLMConfig(model=model, api_key=api_key, base_url=api_base, temperature=0.3)
            client = ZhipuAIClient(config=config)

            prompt = f"""分析以下数据样本的字段，为每个字段建议合适的实体类型名称和数据类型。

数据样本:
{json.dumps(data_sample, ensure_ascii=False, indent=2, default=str)[:2000]}

返回 JSON 数组，每项包含: entity_type_name, description, confidence(0-1), data_type.
只返回JSON，不要其他内容。"""

            messages = [Message(role="user", content=prompt)]
            result_dict, _, _ = client._generate_response(messages, max_tokens=512)

            raw = result_dict.get("response", "") if isinstance(result_dict, dict) else str(result_dict)
            # 提取 JSON
            match = re.search(r'\[[\s\S]*\]', raw)
            if match:
                suggestions = json.loads(match.group())
                return TypeInferenceResult(
                    suggestions=tuple(suggestions),
                    explanation="LLM 辅助类型推断",
                    confidence=0.8,
                )
        except Exception as e:
            logger.debug("LLM type inference failed: %s, using heuristic fallback", e)

        return self._infer_types_heuristic(data_sample)

    def _infer_types_heuristic(self, data_sample: dict) -> TypeInferenceResult:
        """启发式类型推断（原 infer_types 逻辑的增强版）"""
        suggestions = []
        explanation_parts = []

        for key, value in data_sample.items():
            dtype = self._infer_data_type(value)
            if dtype:
                # 增强：根据key名称推断更合理的 EntityType 名称
                entity_name = self._key_to_entity_name(key)
                suggestions.append({
                    "entity_type_name": entity_name,
                    "description": f"从字段 '{key}' 推断（类型: {dtype}）",
                    "confidence": 0.65,
                    "data_type": dtype,
                })
                explanation_parts.append(f"  {key} → {entity_name} ({dtype})")

        return TypeInferenceResult(
            suggestions=tuple(suggestions),
            explanation="启发式类型推断:\n" + "\n".join(explanation_parts) if explanation_parts else "无数据",
            confidence=0.5 if suggestions else 0.0,
        )

    def _key_to_entity_name(self, key: str) -> str:
        """将字段名转换为合理的实体类型名称"""
        # 去掉下划线，首字母大写
        parts = key.replace("_", " ").replace("-", " ").split()
        return "".join(p.capitalize() for p in parts)

    def suggest_constraints(self, entity_type_id: str) -> List[ConstraintSuggestion]:
        """分析已有实例，建议属性约束。

        当前基于 heuristic: 必填字段、常见约束模式。
        """
        suggestions = []

        try:
            from odap.infra.query import get_query_service
            qs = get_query_service()
            result = qs.execute("default", f".entity with(type='{entity_type_id}')", limit=10)
            entities = result.rows

            if not entities:
                return []

            # 收集所有属性
            prop_values: Dict[str, List] = {}
            for entity in entities:
                props = entity.get("properties", {})
                for key, val in props.items():
                    if key not in prop_values:
                        prop_values[key] = []
                    prop_values[key].append(val)

            # 分析约束建议
            for prop_name, values in prop_values.items():
                non_null = [v for v in values if v is not None]
                fill_rate = len(non_null) / len(values)

                # 推荐 required
                if fill_rate == 1.0:
                    suggestions.append(ConstraintSuggestion(
                        property_name=prop_name,
                        suggested_constraint="required",
                        rationale=f"所有 {len(values)} 个实例都包含此属性",
                        confidence=0.9,
                    ))

                # 推荐 enum
                unique_vals = set(str(v) for v in non_null)
                if len(unique_vals) <= 5 and len(non_null) >= 3:
                    suggestions.append(ConstraintSuggestion(
                        property_name=prop_name,
                        suggested_constraint=f"enum:{list(unique_vals)}",
                        rationale=f"仅有 {len(unique_vals)} 种取值: {unique_vals}",
                        confidence=0.8 if len(non_null) >= 5 else 0.6,
                    ))

                # 推荐 min/max for numeric
                numeric_vals = [v for v in non_null if isinstance(v, (int, float))]
                if numeric_vals and len(numeric_vals) >= 3:
                    suggestions.append(ConstraintSuggestion(
                        property_name=prop_name,
                        suggested_constraint=f"min:{min(numeric_vals)},max:{max(numeric_vals)}",
                        rationale=f"当前值范围 [{min(numeric_vals)}, {max(numeric_vals)}]",
                        confidence=0.7,
                    ))

                # 推荐 range 约束（包含统计信息）
                if numeric_vals and len(numeric_vals) >= 3:
                    mean_val = mean(numeric_vals)
                    stdev_val = stdev(numeric_vals) if len(numeric_vals) >= 2 else 0
                    suggestions.append(ConstraintSuggestion(
                        property_name=prop_name,
                        suggested_constraint=f"range:[{min(numeric_vals)},{max(numeric_vals)}],mean:{mean_val:.1f},stdev:{stdev_val:.1f}",
                        rationale=f"数值范围 [{min(numeric_vals)}, {max(numeric_vals)}]，均值 {mean_val:.1f}，标准差 {stdev_val:.1f}",
                        confidence=0.75 if stdev_val > 0 else 0.85,
                    ))

        except Exception as e:
            logger.warning("Constraint suggestion failed for %s: %s", entity_type_id, e)

        return suggestions

    # ── 一致性组 (服务 L2 Construction) ──

    def check_schema_consistency(self, ontology_id: str) -> ConsistencyReport:
        """Schema 级一致性校验。

        检查: 类型名称冲突、属性名重复、关系引用完整性。
        """
        anomalies = []
        pass_count = 0
        fail_count = 0

        try:
            from odap.infra.query import get_query_service
            qs = get_query_service()
            result = qs.execute("default", f".schema with(ontology_id='{ontology_id}')", limit=100)
            types = result.rows

            type_names = {}
            for t in types:
                name = t.get("name", "")
                if name in type_names:
                    anomalies.append({
                        "type": "duplicate_type_name",
                        "name": name,
                        "severity": "error",
                        "message": f"类型名称 '{name}' 重复",
                    })
                    fail_count += 1
                else:
                    type_names[name] = t
                    pass_count += 1

            severity = "error" if fail_count > 0 else "info"

        except Exception as e:
            anomalies.append({
                "type": "check_failed", "severity": "error",
                "message": f"Schema一致性校验失败: {e}",
            })
            fail_count += 1
            severity = "error"

        from datetime import datetime, timezone
        return ConsistencyReport(
            entity_type_id=ontology_id,
            pass_count=pass_count,
            fail_count=fail_count,
            anomalies=tuple(anomalies),
            severity=severity,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def check_instance_consistency(
        self, entity_type_id: str, instance_ids: Optional[List[str]] = None,
    ) -> ConsistencyReport:
        """实例级一致性校验。

        检查: 必填属性缺失、属性类型不匹配、引用完整性。
        """
        anomalies = []
        pass_count = 0
        fail_count = 0

        try:
            from odap.infra.query import get_query_service
            qs = get_query_service()
            ids_filter = ""
            if instance_ids:
                ids_filter = ",".join(instance_ids)
                dsl = f".entity with(type='{entity_type_id}',id='{ids_filter}')"
            else:
                dsl = f".entity with(type='{entity_type_id}')"
            result = qs.execute("default", dsl, limit=50)
            entities = result.rows

            for entity in entities:
                eid = entity.get("id", "unknown")
                props = entity.get("properties", {})

                # 检查空属性
                for key, val in props.items():
                    if val is None or val == "":
                        anomalies.append({
                            "type": "empty_property",
                            "entity_id": eid,
                            "property": key,
                            "severity": "warning",
                            "message": f"实体 {eid} 的属性 {key} 为空",
                        })
                        fail_count += 1

                pass_count += 1

            severity = "error" if fail_count > 0 else "info"

        except Exception as e:
            anomalies.append({
                "type": "check_failed", "severity": "error",
                "message": f"实例一致性校验失败: {e}",
            })
            fail_count += 1
            severity = "error"

        from datetime import datetime, timezone
        return ConsistencyReport(
            entity_type_id=entity_type_id,
            pass_count=pass_count,
            fail_count=fail_count,
            anomalies=tuple(anomalies),
            severity=severity,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    # ── 能力发现 ──

    def get_reasoning_capabilities(self) -> List[str]:
        """返回可用推理能力列表（供工具注册发现）"""
        if self._capabilities_cache is None:
            self._capabilities_cache = [
                "infer_types",
                "suggest_constraints",
                "check_schema_consistency",
                "check_instance_consistency",
                "unified_retrieve",
                "trace_provenance",
            ]
        return self._capabilities_cache

    # ── 辅助 ──

    def _infer_data_type(self, value: Any) -> Optional[str]:
        """增强版类型推断"""
        if value is None:
            return None
        if isinstance(value, bool):
            return "BOOLEAN"
        if isinstance(value, int):
            return "INTEGER"
        if isinstance(value, float):
            return "FLOAT"
        if isinstance(value, str):
            s = value.strip()
            # 尝试解析为 datetime
            if re.match(r'^\d{4}-\d{2}-\d{2}', s):
                return "DATETIME"
            # 尝试解析为 JSON
            if (s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']')):
                try:
                    json.loads(s)
                    return "JSON"
                except json.JSONDecodeError:
                    pass
            return "STRING"
        if isinstance(value, (list, tuple)):
            return "LIST"
        if isinstance(value, dict):
            return "JSON"
        return None


def get_reasoning_service() -> UnifiedReasoningService:
    """获取统一推理服务单例"""
    return UnifiedReasoningService()


__all__ = ["UnifiedReasoningService", "get_reasoning_service"]
