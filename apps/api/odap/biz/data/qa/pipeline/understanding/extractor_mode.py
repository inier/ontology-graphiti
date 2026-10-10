"""提取模式（EntityExtractor mode）运行时解析器。

三级解析：sa_config（scope=entity_extractor / key=mode） > EXTRACTOR_MODE 环境变量 > 默认 query。

设计要点（ADR-089 C-D11/C-D13）：
  - mode ∈ {off, inject, query}；默认 query。
  - 配置存储复用既有 `sa_config` 动态配置底座（scope=`entity_extractor`, key=`mode`,
    config_value={"value": "<mode>"}）。
  - 读取失败绝不抛异常（规则 14）：warning + 降级到下一级，最终回退默认。
  - 读取经 public 路径（`odap.biz.semantic_admin.sa_config`），不深插内部实现。
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MODE = "query"
AVAILABLE_MODES = ("off", "inject", "query")

# 配置存储键（sa_config）
CONFIG_SCOPE = "entity_extractor"
CONFIG_KEY = "mode"

MODE_DESCRIPTIONS = {
    "off": "关闭归一化：实体原词直通（历史行为，可回滚）",
    "inject": "预加载全量 USL 字典 + 实体集合后注入（对照/兼容）",
    "query": "按需查询本体（ontology_semantics 工具）：归一化 + 幻觉过滤（默认）",
}

_ENV_VAR = "EXTRACTOR_MODE"


def _read_from_sa_config() -> Optional[str]:
    """从 sa_config 读 mode；任何异常 → None + warning（绝不抛）。"""
    try:
        from odap.biz.semantic_admin.sa_config.services import (
            get_sa_config_service,
        )
        r = get_sa_config_service().get_config(CONFIG_SCOPE, CONFIG_KEY)
        if not isinstance(r, dict) or r.get("status") != "ok":
            return None
        value = r.get("config_value")
        if isinstance(value, dict):
            value = value.get("value")
        if isinstance(value, str):
            return value
        return None
    except Exception as e:  # 规则 14：失败显式兜底可观测
        logger.warning("读取 extractor mode 配置失败，降级：%s", e)
        return None


def effective_mode_from(mode_value: Optional[str]) -> str:
    """给定「显式配置值」求生效 mode：配置 > env > 默认。供端点复用，避免逻辑漂移。"""
    if mode_value in AVAILABLE_MODES:
        return mode_value
    v = os.environ.get(_ENV_VAR)
    if v in AVAILABLE_MODES:
        return v
    return DEFAULT_MODE


def resolve_extractor_mode() -> str:
    """三级解析：sa_config > EXTRACTOR_MODE env > DEFAULT_MODE。"""
    return effective_mode_from(_read_from_sa_config())


__all__ = [
    "DEFAULT_MODE",
    "AVAILABLE_MODES",
    "MODE_DESCRIPTIONS",
    "CONFIG_SCOPE",
    "CONFIG_KEY",
    "resolve_extractor_mode",
    "effective_mode_from",
]
