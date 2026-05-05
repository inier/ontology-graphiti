"""
数据采集层 - 手动输入处理模块
实现 ADR-031 L2: Data Ingestion & Normalization

ManualInputHandler: 表单/JSON/自然语言 → OntologyDocument
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from odap.biz.ontology.schema.document import (
    OntologyDocument, OntologyEntity, OntologyRelation, OntologyEvent,
    OntologyAction, OntologyRule, OntologyConstraint, VersionRef,
    DataSource, DocumentMeta, TemporalInfo, SourceType, DocType,
    EntityType, ActionStatus, OntologyDocumentSchema,
)

logger = logging.getLogger("data_ingestion")


class ManualInputHandler:
    """
    处理用户手动输入的动态信息

    输入模式:
    1. 结构化 dict（来自 Web 表单）
    2. 自由 JSON 字符串（直接粘贴）
    3. 自然语言（LLM 转换，可选）
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def from_form(self, form_data: dict, scenario_id: str = None) -> OntologyDocument:
        """从表单 dict 构建 OntologyDocument"""
        now = datetime.now(timezone.utc).isoformat()

        doc = OntologyDocument(
            doc_id=form_data.get("doc_id") or f"manual-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}",
            doc_type=form_data.get("doc_type", DocType.EVENT.value),
            source=DataSource(
                type=SourceType.MANUAL.value,
                collected_at=now,
                confidence=1.0,
                author=form_data.get("author"),
            ),
            meta=DocumentMeta(
                title=form_data.get("title", "手动输入事件"),
                description=form_data.get("description", ""),
                tags=form_data.get("tags", []),
            ),
            scenario_id=scenario_id or form_data.get("scenario_id"),
        )

        # 解析实体
        for e_data in form_data.get("entities", []):
            doc.entities.append(OntologyEntity(**{
                k: v for k, v in e_data.items()
                if k in OntologyEntity.__dataclass_fields__
            }))

        # 解析关系
        for r_data in form_data.get("relations", []):
            temporal_data = r_data.pop("temporal", {})
            rel = OntologyRelation(**{
                k: v for k, v in r_data.items()
                if k in OntologyRelation.__dataclass_fields__ and k != "temporal"
            })
            if temporal_data:
                rel.temporal = TemporalInfo(**temporal_data)
            doc.relations.append(rel)

        # 解析事件
        for e_data in form_data.get("events", []):
            doc.events.append(OntologyEvent(**{
                k: v for k, v in e_data.items()
                if k in OntologyEvent.__dataclass_fields__
            }))

        # 版本
        doc.ontology_version.commit_message = f"手动输入: {doc.meta.title}"

        # 验证
        result = OntologyDocumentSchema.validate(doc)
        if not result.is_valid:
            raise ValueError(f"表单数据验证失败: {'; '.join(result.errors)}")

        return doc

    async def from_json(self, raw_json: str, scenario_id: str = None) -> OntologyDocument:
        """验证并解析 JSON 字符串"""
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 格式错误: {e}")

        # Schema 验证
        result = OntologyDocumentSchema.validate(data)
        if not result.is_valid:
            raise ValueError(f"Schema 验证失败: {'; '.join(result.errors)}")

        doc = OntologyDocument.from_dict(data)
        if scenario_id:
            doc.scenario_id = scenario_id
        doc.source.type = SourceType.MANUAL.value

        return doc

    async def from_natural_language(self, text: str, scenario_id: str = None) -> OntologyDocument:
        """
        自然语言转 OntologyDocument（使用 LLM 转换）
        如果没有 LLM，生成基础文档
        """
        if self.llm is None:
            # 无 LLM：生成最简 event 文档
            now = datetime.now(timezone.utc).isoformat()
            doc = OntologyDocument(
                doc_type=DocType.EVENT.value,
                source=DataSource(type=SourceType.MANUAL.value, collected_at=now),
                meta=DocumentMeta(title="自然语言输入", description=text[:500]),
                scenario_id=scenario_id,
            )
            doc.events.append(OntologyEvent(
                event_type="generic",
                timestamp=now,
                description=text[:500],
            ))
            doc.ontology_version.commit_message = f"自然语言输入: {text[:50]}"
            return doc

        # 使用 LLM 转换
        prompt = f"""将以下自然语言描述转换为 OntologyDocument JSON 格式（只输出 JSON）:

{text}

参考格式:
{{
  "doc_id": "manual-xxxxx",
  "doc_type": "event",
  "source": {{"type": "manual", "collected_at": "{datetime.now(timezone.utc).isoformat()}", "confidence": 0.95}},
  "meta": {{"title": "...", "description": "...", "tags": []}},
  "entities": [...],
  "relations": [...],
  "events": [...],
  "actions": [],
  "rules": [],
  "constraints": [],
  "ontology_version": {{"version_id": "", "parent_version": null, "commit_message": "..."}}
}}"""

        try:
            if hasattr(self.llm, 'complete'):
                response = await self.llm.complete(prompt)
            elif hasattr(self.llm, 'chat'):
                response = await self.llm.chat([{"role": "user", "content": prompt}])
            else:
                response = ""

            # 提取 JSON
            text_resp = response.strip()
            if "```json" in text_resp:
                text_resp = text_resp.split("```json")[1].split("```")[0].strip()
            elif "```" in text_resp:
                text_resp = text_resp.split("```")[1].split("```")[0].strip()

            data = json.loads(text_resp)
            doc = OntologyDocument.from_dict(data)
            if scenario_id:
                doc.scenario_id = scenario_id
            return doc
        except Exception as e:
            logger.error(f"LLM 转换失败: {e}，降级到基础文档")
            now = datetime.now(timezone.utc).isoformat()
            doc = OntologyDocument(
                doc_type=DocType.EVENT.value,
                source=DataSource(type=SourceType.MANUAL.value, collected_at=now),
                meta=DocumentMeta(title="自然语言输入", description=text[:500]),
                scenario_id=scenario_id,
            )
            doc.events.append(OntologyEvent(
                event_type="generic",
                timestamp=now,
                description=text[:500],
            ))
            doc.ontology_version.commit_message = f"自然语言输入: {text[:50]}"
            return doc
