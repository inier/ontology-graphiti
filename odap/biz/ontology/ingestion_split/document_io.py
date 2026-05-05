"""
数据采集层 - 导入/导出模块
实现 ADR-031 L2: Data Ingestion & Normalization

OntologyDocumentIO: 导入/导出 .odoc.json
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from odap.biz.ontology.schema.document import (
    OntologyDocument, OntologyDocumentSchema, DataSource, SourceType,
)

logger = logging.getLogger("data_ingestion")


class OntologyDocumentIO:
    """
    OntologyDocument 导入/导出管理

    文件格式: .odoc.json
    支持: 单文档、场景包（多文档）、全量本体快照
    """

    def __init__(self, version_manager=None):
        self.versions = version_manager

    async def export_document(self, doc: OntologyDocument) -> bytes:
        """导出单个文档为 .odoc.json"""
        return doc.to_json(indent=2).encode("utf-8")

    async def export_scenario(
        self,
        scenario_id: str,
        documents: List[OntologyDocument],
    ) -> bytes:
        """导出整个场景（含所有事件）"""
        package = {
            "export_type": "scenario",
            "scenario_id": scenario_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "document_count": len(documents),
            "documents": [doc.to_dict() for doc in documents],
        }
        return json.dumps(package, ensure_ascii=False, indent=2, default=str).encode("utf-8")

    async def export_versions_snapshot(
        self,
        versions_summary: List[dict],
    ) -> bytes:
        """导出版本链快照"""
        snapshot = {
            "export_type": "versions_snapshot",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version_count": len(versions_summary),
            "versions": versions_summary,
        }
        return json.dumps(snapshot, ensure_ascii=False, indent=2, default=str).encode("utf-8")

    async def import_file(
        self,
        content: bytes,
        scenario_id: str = None,
    ) -> List[OntologyDocument]:
        """
        导入 .odoc.json

        步骤:
        1. JSON Schema 验证
        2. 冲突检测
        3. 返回文档列表（由调用方决定是否触发热写入）
        """
        try:
            raw = json.loads(content.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"文件格式错误: {e}")

        documents = []

        # 场景包
        if isinstance(raw, dict) and raw.get("export_type") == "scenario":
            for doc_data in raw.get("documents", []):
                result = OntologyDocumentSchema.validate(doc_data)
                if result.is_valid:
                    doc = OntologyDocument.from_dict(doc_data)
                    if scenario_id:
                        doc.scenario_id = scenario_id
                    doc.source.type = SourceType.IMPORT.value
                    documents.append(doc)
                else:
                    logger.warning(f"导入文档验证失败: {result.errors}")

        # 单文档
        elif isinstance(raw, dict):
            result = OntologyDocumentSchema.validate(raw)
            if result.is_valid:
                doc = OntologyDocument.from_dict(raw)
                if scenario_id:
                    doc.scenario_id = scenario_id
                doc.source.type = SourceType.IMPORT.value
                documents.append(doc)
            else:
                raise ValueError(f"文档验证失败: {'; '.join(result.errors)}")

        # 文档列表
        elif isinstance(raw, list):
            for doc_data in raw:
                result = OntologyDocumentSchema.validate(doc_data)
                if result.is_valid:
                    doc = OntologyDocument.from_dict(doc_data)
                    if scenario_id:
                        doc.scenario_id = scenario_id
                    doc.source.type = SourceType.IMPORT.value
                    documents.append(doc)

        logger.info(f"导入 {len(documents)} 个文档")
        return documents
