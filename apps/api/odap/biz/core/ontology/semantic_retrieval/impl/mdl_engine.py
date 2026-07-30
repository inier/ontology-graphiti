"""MdlEngine — MDL/DSL 推理 Thin Adapter (spec 008 / FR-004 / US3 / Q6 决策).

设计 (Q6 决策: 禁止新发明 DSL):
  · 不发明新 DSL 语法 — 仅解析 query 字符串中的 HE YAML 模板引用
  · 复用 HE 模板体系 (packages/hyper-extract/.../templates/presets/*)
  · Phase 2 Iter 3: 接 HEAdapter.parse() 真实执行；LLM/HE 不可用时降级 parse-only
  · 模板不存在（Gallery 查无）→ status=degraded（省 LLM token，不调 HE）
  · HE.parse 异常 → status=degraded + warning（不崩溃）
  · 缺 template 关键字 → ValueError (契约违反)
  · 所有函数体 ≤ 40 行 (Constitution I)
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("semantic_retrieval.mdl")


# ── 模块级缓存：HE Gallery preset 列表（避免每次 import hyperextract） ──────

_GALLERY_TEMPLATES: Optional[set] = None  # set[str] | None


def _get_gallery_templates() -> Optional[set]:
    """懒加载 HE Gallery preset 路径集合；失败返回 None（跳过存在性校验）。"""
    global _GALLERY_TEMPLATES
    if _GALLERY_TEMPLATES is not None:
        return _GALLERY_TEMPLATES
    try:
        from hyperextract.utils.template_engine import Template

        all_tpls = Template.list()
        _GALLERY_TEMPLATES = set(all_tpls.keys()) if all_tpls else set()
        logger.info("加载 HE Gallery preset %d 个", len(_GALLERY_TEMPLATES))
    except Exception as exc:  # noqa: BLE001 — hyperextract 可能未安装
        logger.warning("HE Gallery 加载失败，跳过模板存在性校验: %s", exc)
        _GALLERY_TEMPLATES = None
    return _GALLERY_TEMPLATES


# ── MdlExecutor: Thin Wrapper 复用 HEAdapter ──────────────────────────────

class MdlExecutor:
    """MdlEngine 内部执行器 — 封装 HE 调用 + 降级策略（所有方法 ≤40 行）。"""

    def __init__(self, *, he_adapter: Any = None):
        self._he = he_adapter

    # ── 公共 API ───────────────────────────────────────────────────────

    def template_exists(self, template_name: str) -> Optional[bool]:
        """校验模板是否在 HE Gallery preset 中。

        返回值:
          True  → 确定存在
          False → 确定不存在
          None  → 无法判断（hyperextract 未安装等），调用方应允许执行但加 warning
        """
        gallery = _get_gallery_templates()
        if gallery is None:
            return None
        return template_name in gallery

    def should_skip_he(self, parsed: Dict[str, Any]) -> Optional[str]:
        """判断是否应跳过 HE 调用；返回 skip 原因（None=不跳过）。"""
        he = self._he
        if he is None:
            return "HEAdapter 未注入，降级 parse-only"
        if not getattr(he, "is_available", lambda: False)():
            return "HE/LLM 不可用（hyperextract 未安装或依赖缺失）"
        if not parsed.get("entity"):
            return "entity 文本为空，跳过 HE 抽取"
        exists = self.template_exists(parsed["template"])
        if exists is False:
            return (
                f"模板 '{parsed['template']}' 未在 HE Gallery preset 中找到，"
                "省 LLM token 跳过执行"
            )
        return None

    def run_he(self, parsed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """调用 HEAdapter.parse()；异常返回 None 由调用方加 warning。"""
        he = self._he
        template_cfg = {
            "template_path": parsed["template"],
            "language": parsed.get("params", {}).get("language", "zh"),
        }
        # 将 params 中非保留字段追加到 template_cfg 作为 HE 参数
        for k, v in (parsed.get("params") or {}).items():
            if k in ("language", "template_path"):
                continue
            template_cfg[k] = v
        result = he.parse(parsed["entity"], template=template_cfg)
        return result


# ── MdlEngine: 对外 Thin Facade ────────────────────────────────────────────

class MdlEngine:
    """MDL/DSL 推理：解析 HE 模板引用 + 可选真实执行 HE 抽取 (Phase 2 Iter 3)。"""

    def __init__(self, *, template_registry: Any = None, he_adapter: Any = None):
        self._registry = template_registry  # 保留向后兼容（Phase 1 用法）
        self._executor = MdlExecutor(he_adapter=he_adapter)

    # ── 公共 API ───────────────────────────────────────────────────────

    async def reason(self, workspace_id: str, *, query: str) -> Dict[str, Any]:
        """解析 MDL query → 可选 HE 真实抽取 → 结构化 reasoning。"""
        _ = workspace_id
        parsed = self._parse_query(query)
        warnings: List[str] = []
        extraction: Optional[Dict[str, Any]] = None

        skip_reason = self._executor.should_skip_he(parsed)
        if skip_reason:
            warnings.append(skip_reason)
            status = "degraded"
        else:
            extraction = self._safe_run_he(parsed, warnings)
            status = "ok" if extraction is not None else "degraded"

        reasoning = self._build_reasoning(parsed, status, extraction=extraction)
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

    def _safe_run_he(
        self, parsed: Dict[str, Any], warnings: List[str]
    ) -> Optional[Dict[str, Any]]:
        """安全调用 MdlExecutor.run_he；任何异常 → warning + 返回 None。"""
        try:
            return self._executor.run_he(parsed)
        except Exception as exc:  # noqa: BLE001 — HE 内部异常不中断业务
            msg = f"HE 抽取执行异常（已降级 parse-only）: {type(exc).__name__}: {exc}"
            logger.warning(msg)
            warnings.append(msg)
            return None

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
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {"value": obj}
        except (json.JSONDecodeError, TypeError):
            pass
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

    @staticmethod
    def _build_reasoning(
        parsed: Dict[str, Any],
        status: str,
        *,
        extraction: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """组装 reasoning 结构（同 /chain 结构，FR-004 契约对齐）。"""
        confidence = 0.0 if status == "degraded" else MdlEngine._calc_confidence(extraction)
        base = {
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
            "confidence": confidence,
            "cycle_detected": False,
            "conflicts": [],
        }
        if extraction is not None:
            base["extraction"] = extraction
        return base

    @staticmethod
    def _calc_confidence(extraction: Optional[Dict[str, Any]]) -> float:
        """根据抽取结果估 confidence：有实体/关系 ≥0.5；空 0.3。"""
        if not extraction:
            return 0.3
        ent = extraction.get("entities") or []
        rel = extraction.get("relations") or []
        if ent or rel:
            return min(0.95, 0.5 + 0.02 * len(ent) + 0.03 * len(rel))
        return 0.3
