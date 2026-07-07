"""
知识库文档清洗管道（Pipeline 模式）

清洗级别配置（环境变量 CLEANING_LEVEL，默认 "basic"）：
  - basic: 空白规范化 + 控制字符移除 + 智能分段
  - llm_enhanced: basic + LLM 实体预提取

约束：
  - 清洗失败不阻塞上传（降级到原始内容）
  - 支持异步清洗（通过 asyncio.create_task 后台执行）
"""

import re
import json
import os
import asyncio
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# ── 环境变量配置 ──────────────────────────────────────
CLEANING_LEVEL = os.getenv("CLEANING_LEVEL", "basic").lower()
SEGMENT_MIN_LENGTH = int(os.getenv("CLEANING_SEGMENT_MIN_LENGTH", "20"))
SEGMENT_MAX_LENGTH = int(os.getenv("CLEANING_SEGMENT_MAX_LENGTH", "2000"))
LLM_ENTITY_EXTRACT_LENGTH = int(os.getenv("CLEANING_LLM_EXTRACT_LENGTH", "5000"))


class CleaningPipeline:
    """文档清洗管道 — 链式执行多个清洗步骤"""

    def __init__(self, level: str = None):
        self.level = level or CLEANING_LEVEL

    # ── 步骤 1: 空白规范化 ─────────────────────────────

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """规范化空白字符：
        - 统一换行为 \n
        - 合并连续空行为最多 2 个
        - 去除行首行尾空白
        """
        if not text:
            return ""

        # 统一换行符
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 合并连续空白行（最多保留 1 个空行作为段落分隔）
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 去除每行首尾空白
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines)

    # ── 步骤 2: 移除控制字符 ───────────────────────────

    @staticmethod
    def remove_control_chars(text: str) -> str:
        """移除不可见控制字符（保留 \n, \t）"""
        if not text:
            return ""

        # 移除 NUL (0x00), BEL (0x07), BS (0x08), VT (0x0B), FF (0x0C),
        # SO/SI (0x0E-0x1F), DEL (0x7F)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

        # 移除零宽字符（BOM/ZWSP/ZWNJ/ZWJ 等）
        text = re.sub(r"[\u200b-\u200f\u2028-\u202f\uFEFF]", "", text)

        return text

    # ── 步骤 3: 智能分段 ───────────────────────────────

    @staticmethod
    def segment_text(
        text: str,
        min_length: int = None,
        max_length: int = None,
    ) -> List[Dict[str, Any]]:
        """按段落/标题智能分段，返回分段列表。

        Returns:
            [{ "index": 0, "content": "...", "type": "paragraph"|"heading"|"list_item" }]
        """
        if not text:
            return []

        min_len = min_length or SEGMENT_MIN_LENGTH
        max_len = max_length or SEGMENT_MAX_LENGTH

        segments: List[Dict[str, Any]] = []
        idx = 0

        for para in text.split("\n"):
            para = para.strip()
            if not para:
                continue

            # 识别标题（Markdown # 风格 或 全中文标题）
            heading_match = re.match(r"^(#{1,6}\s)|([\u4e00-\u9fff\w]{2,20}[。，：；！？\s]*$)", para)
            is_heading = bool(heading_match) and len(para) <= 80

            # 识别列表项
            is_list_item = bool(re.match(r"^[\s]*[-*+\d.]+\s", para))

            # 过长的段落按句子边界拆分
            if len(para) > max_len:
                sub_parts = _split_long_paragraph(para, max_len)
                for part in sub_parts:
                    if len(part) >= min_len:
                        segments.append({
                            "index": idx,
                            "content": part,
                            "type": "heading" if is_heading else ("list_item" if is_list_item else "paragraph"),
                        })
                        idx += 1
            elif len(para) >= min_len:
                segments.append({
                    "index": idx,
                    "content": para,
                    "type": "heading" if is_heading else ("list_item" if is_list_item else "paragraph"),
                })
                idx += 1

        return segments


def _split_long_paragraph(text: str, max_len: int) -> List[str]:
    """将过长段落按句子边界（。！？\n）拆分"""
    parts = []
    remaining = text

    while len(remaining) > max_len:
        # 在 max_len 范围内找最佳分割点
        chunk = remaining[:max_len]
        # 优先找句号
        for sep in ["。", "！", "？", "\n", "；", "，", ".", "!", "?"]:
            pos = chunk.rfind(sep)
            if pos > max_len * 0.3:  # 至少保留 30%
                parts.append(remaining[: pos + 1])
                remaining = remaining[pos + 1 :]
                break
        else:
            # 找不到合适的分割点，直接按长度截断
            parts.append(chunk)
            remaining = remaining[max_len:]

    if remaining:
        parts.append(remaining)

    return parts


# ── 步骤 4: LLM 实体预提取（可选，llm_enhanced 级别） ──

async def extract_key_entities(text: str, max_length: int = None) -> Dict[str, Any]:
    """利用 LLM 从文本中预提取关键实体/术语，返回带标注的实体映射。

    Returns:
        { "entities": [...], "keywords": [...], "summary": "..." }
    """
    max_len = max_length or LLM_ENTITY_EXTRACT_LENGTH
    truncated = text[:max_len]

    prompt = f"""请从以下文本中提取关键信息，以 JSON 格式返回：
{{
  "entities": [{{"name": "实体名", "type": "类型（人/组织/地点/设备/概念/事件等）"}}],
  "keywords": ["关键术语1", "关键术语2"],
  "summary": "100字以内的内容摘要"
}}

文本内容：
---BEGIN TEXT---
{truncated}
---END TEXT---

只返回 JSON，不要额外说明。"""

    try:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return {"entities": [], "keywords": [], "summary": ""}

        from odap.infra.llm.llm_service import ZhipuAIClient
        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.prompts.models import Message

        api_base = os.getenv("OPENAI_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
        model = os.getenv("OPENAI_MODEL", "glm-4-flash")
        config = LLMConfig(model=model, api_key=api_key, base_url=api_base, temperature=0.3)
        llm = ZhipuAIClient(config=config)

        messages = [
            Message(role="system", content="你是信息提取专家，只返回 JSON。"),
            Message(role="user", content=prompt),
        ]
        response, _, _ = await llm._generate_response(messages)

        if response and isinstance(response, dict):
            return {
                "entities": response.get("entities", []),
                "keywords": response.get("keywords", []),
                "summary": response.get("summary", ""),
            }

        # 尝试从字符串解析
        if isinstance(response, str):
            import re as _re
            json_match = _re.search(r"\{.*\}", response, _re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                return {
                    "entities": parsed.get("entities", []),
                    "keywords": parsed.get("keywords", []),
                    "summary": parsed.get("summary", ""),
                }

        return {"entities": [], "keywords": [], "summary": ""}
    except Exception as e:
        logger.warning("LLM 实体预提取失败: %s", repr(e))
        return {"entities": [], "keywords": [], "summary": ""}


# ── 管道入口 ──────────────────────────────────────────

class DocumentCleaningResult:
    """清洗结果"""

    def __init__(self):
        self.raw_content: str = ""
        self.cleaned_content: str = ""
        self.segments: List[Dict[str, Any]] = []
        self.entities: List[Dict[str, Any]] = []
        self.keywords: List[str] = []
        self.summary: str = ""
        self.level: str = "basic"
        self.error: Optional[str] = None
        self.cleaning_status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_content": self.raw_content,
            "cleaned_content": self.cleaned_content,
            "segments_count": len(self.segments),
            "segments": self.segments,
            "entities": self.entities,
            "keywords": self.keywords,
            "summary": self.summary,
            "level": self.level,
            "error": self.error,
            "cleaning_status": self.cleaning_status,
        }


async def clean_document(raw_content: str, level: str = None) -> DocumentCleaningResult:
    """执行完整的文档清洗管道。

    Args:
        raw_content: 原始文档文本
        level: 清洗级别（basic / llm_enhanced），默认使用环境变量

    Returns:
        DocumentCleaningResult
    """
    pipeline = CleaningPipeline(level=level)
    result = DocumentCleaningResult()
    result.raw_content = raw_content
    result.level = pipeline.level

    if not raw_content or not raw_content.strip():
        result.cleaned_content = ""
        result.cleaning_status = "done"
        return result

    try:
        result.cleaning_status = "processing"

        # 步骤 1: 空白规范化
        text = pipeline.normalize_whitespace(raw_content)

        # 步骤 2: 移除控制字符
        text = pipeline.remove_control_chars(text)

        # 步骤 3: 智能分段
        result.segments = pipeline.segment_text(text)
        result.cleaned_content = text

        # 步骤 4: LLM 实体预提取（仅 llm_enhanced 级别）
        if pipeline.level == "llm_enhanced":
            llm_result = await extract_key_entities(text)
            result.entities = llm_result.get("entities", [])
            result.keywords = llm_result.get("keywords", [])
            result.summary = llm_result.get("summary", "")

        result.cleaning_status = "done"

    except Exception as e:
        logger.warning("文档清洗管道失败，降级到原始内容: %s", repr(e))
        result.cleaned_content = raw_content or ""
        result.error = str(e)
        result.cleaning_status = "failed"
        # 降级：使用原始内容
        if not result.segments:
            result.segments = [{"index": 0, "content": raw_content[:2000], "type": "paragraph"}]

    return result


async def background_clean_and_update(
    doc_id: str,
    kb_id: str,
    raw_content: str,
    level: str = None,
):
    """后台异步执行清洗并更新数据库。

    此函数由 routes.py 在文档创建后通过 asyncio.create_task 调用。
    清洗失败不会影响文档上传流程。
    """
    try:
        from ..storage.sqlite_kb_storage import SQLiteKnowledgeBaseStorage

        storage = SQLiteKnowledgeBaseStorage()

        # 更新状态为 processing
        storage.update_document_cleaning_status(doc_id, "processing", level or CLEANING_LEVEL)

        # 执行清洗
        result = await clean_document(raw_content, level)

        # 更新数据库
        storage.update_document_cleaned_content(
            doc_id=doc_id,
            raw_content=result.raw_content,
            cleaned_content=result.cleaned_content,
            cleaning_status=result.cleaning_status,
            cleaning_level=result.level,
            keywords=result.keywords,
            summary=result.summary,
            segments=result.segments,
            entities=result.entities,
        )

        logger.info(
            "文档 %s 清洗完成: level=%s status=%s segments=%d entities=%d",
            doc_id,
            result.level,
            result.cleaning_status,
            len(result.segments),
            len(result.entities),
        )

    except Exception as e:
        logger.error("后台清洗任务异常 doc_id=%s: %s", doc_id, repr(e), exc_info=True)
        try:
            from ..storage.sqlite_kb_storage import SQLiteKnowledgeBaseStorage
            storage = SQLiteKnowledgeBaseStorage()
            storage.update_document_cleaning_status(doc_id, "failed", level or CLEANING_LEVEL)
        except Exception:
            pass
