"""外部内容安全过滤

移除危险 HTML 标签，标记内容来源和可信度。
"""

import re
import logging
from typing import Dict, Any, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# 危险标签（从内容中移除）
DANGEROUS_TAGS = ["script", "iframe", "object", "embed", "applet", "form"]

# 可移除的导航/装饰标签
NOISE_TAGS = ["nav", "footer", "aside", "header", "advertisement"]


def sanitize_content(content: str, crawl_method: str = "requests_fallback") -> Dict[str, Any]:
    """安全过滤爬取内容

    1. 移除危险 HTML 标签（script, iframe, object 等）
    2. 移除事件处理属性（onclick, onerror 等）
    3. 标记内容来源和可信度

    Args:
        content: 原始爬取内容
        crawl_method: 爬取方式（影响可信度标记）

    Returns:
        包含清理后内容和元数据的字典
    """
    if not content:
        return {"content": "", "warnings": [], "confidence": "low"}

    warnings = []
    cleaned = content

    # 1. 移除危险标签
    for tag in DANGEROUS_TAGS:
        pattern = rf"<{tag}[^>]*>.*?</{tag}>"
        matches = re.findall(pattern, cleaned, re.IGNORECASE | re.DOTALL)
        if matches:
            warnings.append(f"Removed {len(matches)} <{tag}> tag(s)")
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        # 自闭合标签
        self_close_pattern = rf"<{tag}[^>]*/?>"
        matches = re.findall(self_close_pattern, cleaned, re.IGNORECASE)
        if matches:
            warnings.append(f"Removed {len(matches)} self-closing <{tag}> tag(s)")
            cleaned = re.sub(self_close_pattern, "", cleaned, flags=re.IGNORECASE)

    # 2. 移除事件处理属性
    event_pattern = r'\s+on\w+\s*=\s*["\'][^"\']*["\']'
    event_matches = re.findall(event_pattern, cleaned, re.IGNORECASE)
    if event_matches:
        warnings.append(f"Removed {len(event_matches)} event handler attribute(s)")
        cleaned = re.sub(event_pattern, "", cleaned, flags=re.IGNORECASE)

    # 3. 移除 javascript: 链接
    js_link_pattern = r'href\s*=\s*["\']javascript:[^"\']*["\']'
    js_matches = re.findall(js_link_pattern, cleaned, re.IGNORECASE)
    if js_matches:
        warnings.append(f"Removed {len(js_matches)} javascript: link(s)")
        cleaned = re.sub(js_link_pattern, 'href="#"', cleaned, flags=re.IGNORECASE)

    # 4. 确定可信度
    confidence = "medium" if crawl_method == "crawl4ai" else "low"

    return {
        "content": cleaned.strip(),
        "warnings": warnings,
        "confidence": confidence,
        "sanitized": bool(warnings),
    }


def mark_external_content(data: Dict[str, Any], crawl_method: str = "requests_fallback") -> Dict[str, Any]:
    """标记外部内容来源和可信度

    在爬取结果中添加来源标记，便于后续处理时区分内部和外部数据。
    """
    source = "external"
    confidence = data.get("confidence", "low")

    # 根据爬取方式调整可信度
    if crawl_method == "crawl4ai":
        confidence = "medium"
    elif crawl_method == "requests_fallback":
        confidence = "low"

    data["source"] = source
    data["confidence"] = confidence
    data["crawl_method"] = crawl_method

    # 对内容进行安全过滤
    content = data.get("content", "")
    if content and "<" in content:  # 仅对 HTML 内容过滤
        sanitize_result = sanitize_content(content, crawl_method)
        data["content"] = sanitize_result["content"]
        if sanitize_result["warnings"]:
            data["sanitize_warnings"] = sanitize_result["warnings"]
        data["confidence"] = sanitize_result["confidence"]

    return data
