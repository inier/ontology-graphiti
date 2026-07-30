"""MdlEngine — MDL/DSL 推理 Thin Adapter (spec 008 / FR-004 / US3 / Q6 决策).

设计 (Q6 决策: 禁止新发明 DSL):
  · 不发明新 DSL 语法 — 仅解析 query 字符串中的 HE YAML 模板引用
  · 复用 HE 模板体系 (packages/hyper-extract/.../templates/presets/*)
  · Phase 1: 仅解析 + 模板存在性校验 (不调 LLM/embedder)
  · Phase 2+: 接 Template.create(name, lang, llm, embedder) 全量执行
  · 模板不存在 → status=degraded (不阻断, 优雅降级)
  · 缺 template 关键字 → ValueError (契约违反)
  · 所有函数体 ≤ 40 行 (Constitution I)
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("semantic_retrieval.mdl")


class MdlEngine:
    """MDL/DSL 推理：解析 HE YAML 模板引用 + 参数补全 (Phase 1)。"""

    def __init__(self, *, template_registry: Any = None):
        # Phase 2+ 注入 HE Template 体系；Phase 1 不强依赖
        self._registry = template_registry

    # ── 公共 API ─────────────────────────────────────────────────────────

    async def reason(self, workspace_id: str, *, query: str) -> Dict[str, Any]:
        """解析 MDL query → 结构化 reasoning。"""
        _ = workspace_id  # Phase 2+ 透传给 HE Template.create
        parsed = self._parse_query(query)
        warnings: List[str] = []
        status = self._resolve_status(parsed["template"], warnings)
        reasoning = self._build_reasoning(parsed, status)
        return {
            "mode": "mdl",
            "reasoning": reasoning,
            "warnings": warnings,
            "total": 1 if status == "ok" else 0,
        }

    async def search(
        self, workspace_id: str, query: str, limit: int = 20
    ) -> Dict[str, Any]:
        """UnifiedRouter 适配器：query → MDL 推理。"""
        _ = limit
        return await self.reason(workspace_id, query=query)

    # ── 内部辅助（Constitution I：≤ 40 行） ──────────────────────────────

    @staticmethod
    def _parse_query(query: str) -> Dict[str, Any]:
        """解析多行 query: template/entity/params 三段。

        契约: 首行必须含 'template:'；缺失 → ValueError。
        """
        lines = [ln.strip() for ln in query.splitlines() if ln.strip()]
        template = MdlEngine._extract_field(lines, "template")
        if not template:
            raise ValueError(
                "MDL query 缺少 'template:' 字段 — Q6 决策：MDL 必须复用 HE 模板引用"
            )
        entity = MdlEngine._extract_field(lines, "entity") or ""
        params = MdlEngine._parse_params(lines)
        return {"template": template, "entity": entity, "params": params}

    @staticmethod
    def _extract_field(lines: List[str], field: str) -> Optional[str]:
        """从 lines 中提取 'field: value' 形式的值。"""
        prefix = f"{field}:"
        for ln in lines:
            if ln.lower().startswith(prefix):
                return ln[len(prefix):].strip()
        return None

    @staticmethod
    def _parse_params(lines: List[str]) -> Dict[str, Any]:
        """解析 params 行：JSON 串 / key=value kv 串 均支持。"""
        raw = MdlEngine._extract_field(lines, "params")
        if not raw:
            return {}
        # 优先 JSON
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {"value": obj}
        except (json.JSONDecodeError, TypeError):
            pass
        # 回退 key=value, key=value
        result: Dict[str, Any] = {}
        for kv in raw.split(","):
            kv = kv.strip()
            if not kv or "=" not in kv:
                continue
            k, v = kv.split("=", 1)
            result[k.strip()] = MdlEngine._coerce(v.strip())
        return result

    @staticmethod
    def _coerce(value: str) -> Any:
        """尝试将字符串值转 int/float/bool，失败保留原字符串。"""
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value

    def _resolve_status(self, template: str, warnings: List[str]) -> str:
        """模板存在性校验：注册表查无 → degraded + warning。"""
        if self._registry is None:
            # Phase 1 无注册表：所有模板引用标记为 degraded（未执行 LLM）
            warnings.append(
                f"模板 '{template}' 未执行 LLM 推理（Phase 1 仅解析，Phase 2+ 接 HE Template.create）"
            )
            return "degraded"
        try:
            exists = self._registry.exists(template) if hasattr(
                self._registry, "exists"
            ) else False
        except Exception:  # noqa: BLE001 — registry 故障兜底
            exists = False
        if not exists:
            warnings.append(f"模板 '{template}' 在 HE preset 中未找到，已降级")
            return "degraded"
        return "ok"

    @staticmethod
    def _build_reasoning(
        parsed: Dict[str, Any], status: str
    ) -> Dict[str, Any]:
        """组装 reasoning 结构（同 /chain 结构，FR-004 契约对齐）。"""
        return {
            "chain_id": f"mdl-{uuid.uuid4().hex[:8]}",
            "template": parsed["template"],
            "entity": parsed["entity"],
            "params": parsed["params"],
            "status": status,
            "conclusion": (
                f"模板 {parsed['template']} 应用于 {parsed['entity']}"
                if parsed["entity"]
                else f"模板 {parsed['template']} 已解析"
            ),
            "confidence": 0.0 if status == "degraded" else 0.8,
            "cycle_detected": False,
            "conflicts": [],
        }
