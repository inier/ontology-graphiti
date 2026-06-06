"""
模板加载器 (T321)

从同目录 templates/ 加载 YAML 模板。
- list_industries() 返回可用行业列表
- load_template(industry) 返回模板 dict
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .models import Industry


# 模板目录（相对此文件）
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def list_industries() -> List[str]:
    """列出可用行业（基于 templates 目录中的 yaml 文件）"""
    if not TEMPLATES_DIR.exists():
        return []
    return sorted(p.stem for p in TEMPLATES_DIR.glob("*.yaml"))


def load_template(industry: str | Industry) -> Optional[Dict[str, Any]]:
    """
    加载指定行业的模板。
    返回 None 表示未找到。
    """
    if isinstance(industry, Industry):
        industry = industry.value
    if industry not in {i.value for i in Industry}:
        # 仍然允许加载 templates/ 中存在的文件（即使未登记在 Industry 枚举）
        path = TEMPLATES_DIR / f"{industry}.yaml"
        if not path.exists():
            return None
    else:
        path = TEMPLATES_DIR / f"{industry}.yaml"
        if not path.exists():
            return None

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
