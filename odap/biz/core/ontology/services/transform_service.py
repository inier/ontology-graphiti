"""
OntologyDocument 转换服务
实现多类型数据到 OntologyDocument 标准格式的转换

支持的输入类型:
- 结构化数据: JSON, CSV, Excel
- 半结构化数据: XML, YAML
- 非结构化数据: 文本, 网页, 新闻

输出: 标准的 OntologyDocument 格式
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from dataclasses import asdict

logger = logging.getLogger("ontology_transform")


class TransformationError(Exception):
    """数据转换异常"""
    def __init__(self, message: str, source_type: str = None, details: Dict = None):
        self.message = message
        self.source_type = source_type
        self.details = details or {}
        super().__init__(self.message)


class DataQualityError(Exception):
    """数据质量异常"""
    def __init__(self, errors: List[str], warnings: List[str] = None):
        self.errors = errors
        self.warnings = warnings or []
        super().__init__(f"数据质量验证失败: {'; '.join(errors)}")


class OntologyTransformService:
    """
    多类型数据到 OntologyDocument 的转换服务

    功能:
    1. 结构化数据转换 (JSON, CSV)
    2. 半结构化数据转换 (XML, YAML)
    3. 非结构化数据转换 (文本, 网页)
    4. 数据质量校验
    5. 标准化输出
    """

    # 支持的输入类型
    SUPPORTED_TYPES = [
        "json", "csv", "xml", "yaml",
        "text", "html", "url",
        "structured", "semi_structured", "unstructured"
    ]

    # 数据质量规则
    REQUIRED_FIELDS = ["doc_id", "doc_type"]
    RECOMMENDED_FIELDS = ["meta", "entities", "relations", "events"]
    ENTITY_REQUIRED_FIELDS = ["entity_id", "entity_type", "name"]

    def __init__(self):
        self.transform_count = 0
        self.error_count = 0

    async def transform(
        self,
        data: Any,
        source_type: str,
        metadata: Dict[str, Any] = None
    ) -> 'OntologyDocument':
        """
        将输入数据转换为 OntologyDocument

        Args:
            data: 输入数据
            source_type: 数据类型 (json/csv/xml/yaml/text/html/url)
            metadata: 额外元数据

        Returns:
            OntologyDocument: 转换后的本体文档
        """
        metadata = metadata or {}

        try:
            # 根据类型选择转换方法
            if source_type == "json":
                result = await self._transform_json(data, metadata)
            elif source_type == "csv":
                result = await self._transform_csv(data, metadata)
            elif source_type in ["xml", "yaml"]:
                result = await self._transform_semi_structured(data, source_type, metadata)
            elif source_type in ["text", "html"]:
                result = await self._transform_unstructured(data, source_type, metadata)
            elif source_type == "url":
                result = await self._transform_url(data, metadata)
            else:
                raise TransformationError(f"不支持的数据类型: {source_type}", source_type)

            # 数据质量校验
            quality_result = self.validate_quality(result)
            if not quality_result.is_valid:
                raise DataQualityError(quality_result.errors, quality_result.warnings)

            self.transform_count += 1
            logger.info(f"成功转换数据为 OntologyDocument: {result.doc_id}")

            return result

        except (TransformationError, DataQualityError):
            raise
        except Exception as e:
            self.error_count += 1
            logger.error(f"数据转换失败: {e}")
            raise TransformationError(str(e), source_type)

    async def _transform_json(
        self,
        data: Union[str, Dict, List],
        metadata: Dict
    ) -> 'OntologyDocument':
        """JSON 数据转换"""
        from odap.biz.core.ontology.schema.document import OntologyDocument

        # 解析 JSON 字符串
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                raise TransformationError(f"JSON 解析失败: {e}", "json")

        # 处理数组（批量数据）
        if isinstance(data, list):
            # 返回第一个文档或创建批量文档
            if len(data) > 0:
                data = data[0]
            else:
                raise TransformationError("空数组无法转换", "json")

        # 如果已经是 dict，直接验证和转换
        if isinstance(data, dict):
            # 验证必需字段
            for field in self.REQUIRED_FIELDS:
                if field not in data:
                    data[field] = self._generate_field_value(field)

            return self._dict_to_ontology_document(data, metadata)

        raise TransformationError("无效的 JSON 数据格式", "json")

    async def _transform_csv(
        self,
        data: Union[str, List[Dict]],
        metadata: Dict
    ) -> 'OntologyDocument':
        """CSV 数据转换"""
        from odap.biz.core.ontology.schema.document import (
            OntologyDocument, OntologyEntity, SourceInfo, DocumentMeta
        )

        # 解析 CSV 数据
        if isinstance(data, str):
            import csv
            import io
            reader = csv.DictReader(io.StringIO(data))
            rows = list(reader)
        elif isinstance(data, list):
            rows = data
        else:
            raise TransformationError("无效的 CSV 数据格式", "csv")

        if not rows:
            raise TransformationError("空 CSV 数据", "csv")

        # 创建本体文档
        now = datetime.now(timezone.utc).isoformat()
        doc_id = f"csv-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"

        doc = OntologyDocument(
            doc_id=doc_id,
            doc_type="batch",
            source=SourceInfo(
                type="structured",
                collected_at=now,
                confidence=0.9
            ),
            meta=DocumentMeta(
                title=metadata.get("title", f"CSV 导入 {doc_id}"),
                description=f"从 CSV 导入的 {len(rows)} 条记录",
                tags=["csv", "批量导入"]
            )
        )

        # 转换每一行为实体
        for idx, row in enumerate(rows):
            entity_id = f"row-{idx}-{uuid.uuid4().hex[:4]}"
            entity = OntologyEntity(
                entity_id=entity_id,
                entity_type="DataRecord",
                name=f"记录 {idx + 1}",
                basic_properties=dict(row)
            )
            doc.entities.append(entity)

        return doc

    async def _transform_semi_structured(
        self,
        data: str,
        source_type: str,
        metadata: Dict
    ) -> 'OntologyDocument':
        """半结构化数据转换 (XML, YAML)"""
        from odap.biz.core.ontology.schema.document import (
            OntologyDocument, SourceInfo, DocumentMeta, OntologyEntity
        )

        if source_type == "xml":
            parsed = self._parse_xml(data)
        elif source_type == "yaml":
            parsed = self._parse_yaml(data)
        else:
            raise TransformationError(f"不支持的半结构化类型: {source_type}", source_type)

        # 转换为 dict
        if isinstance(parsed, (xml.etree.ElementTree.Element,)):
            parsed = self._xml_to_dict(parsed)

        now = datetime.now(timezone.utc).isoformat()
        doc_id = f"{source_type}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"

        doc = OntologyDocument(
            doc_id=doc_id,
            doc_type="document",
            source=SourceInfo(
                type="semi_structured",
                collected_at=now,
                confidence=0.85
            ),
            meta=DocumentMeta(
                title=metadata.get("title", parsed.get("title", f"{source_type.upper()} 文档")),
                description=str(parsed)[:500]
            )
        )

        # 提取实体
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                if isinstance(value, dict):
                    entity = OntologyEntity(
                        entity_id=f"node-{uuid.uuid4().hex[:6]}",
                        entity_type="DataNode",
                        name=key,
                        basic_properties=value if isinstance(value, dict) else {"value": str(value)}
                    )
                    doc.entities.append(entity)

        return doc

    async def _transform_unstructured(
        self,
        data: str,
        source_type: str,
        metadata: Dict
    ) -> 'OntologyDocument':
        """非结构化数据转换 (文本, HTML)"""
        from odap.biz.core.ontology.schema.document import (
            OntologyDocument, SourceInfo, DocumentMeta, OntologyEvent
        )

        if source_type == "html":
            text = self._extract_text_from_html(data)
        else:
            text = data

        now = datetime.now(timezone.utc).isoformat()
        doc_id = f"text-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"

        doc = OntologyDocument(
            doc_id=doc_id,
            doc_type="event",
            source=SourceInfo(
                type="unstructured",
                collected_at=now,
                confidence=0.7
            ),
            meta=DocumentMeta(
                title=metadata.get("title", text[:100]),
                description=text[:500],
                tags=metadata.get("tags", ["非结构化数据"])
            )
        )

        # 创建一个通用事件
        event = OntologyEvent(
            event_id=f"evt-{uuid.uuid4().hex[:6]}",
            event_type="report",
            timestamp=now,
            description=text[:1000]
        )
        doc.events.append(event)

        return doc

    async def _transform_url(
        self,
        url: str,
        metadata: Dict
    ) -> 'OntologyDocument':
        """URL 数据转换 - 抓取网页内容"""
        from odap.biz.core.ontology.ingestion_split import WebScraper, FreeNewsIngester

        scraper = WebScraper()
        result = scraper.scrape(url)

        if result.get("status") == "success":
            ingester = FreeNewsIngester(scraper=scraper)
            docs = await ingester.ingest(
                url=url,
                title_hint=metadata.get("title", ""),
                event_context=metadata.get("context", "")
            )
            if docs:
                return docs[0]

        # 回退到文本转换
        return await self._transform_unstructured(
            result.get("text", f"网页内容: {url}"),
            "text",
            metadata
        )

    def _dict_to_ontology_document(self, data: Dict, metadata: Dict) -> 'OntologyDocument':
        """将 dict 转换为 OntologyDocument"""
        from odap.biz.core.ontology.schema.document import OntologyDocument

        # 提取字段
        doc_id = data.get("doc_id", f"doc-{uuid.uuid4().hex[:8]}")
        doc_type = data.get("doc_type", "document")

        # 使用 from_dict 方法
        if "entities" in data or "relations" in data:
            return OntologyDocument.from_dict(data)

        # 创建新文档
        now = datetime.now(timezone.utc).isoformat()
        from odap.biz.core.ontology.schema.document import SourceInfo, DocumentMeta

        doc = OntologyDocument(
            doc_id=doc_id,
            doc_type=doc_type,
            source=SourceInfo(
                type=metadata.get("source_type", "transformed"),
                collected_at=now,
                confidence=0.85
            ),
            meta=DocumentMeta(
                title=data.get("title", metadata.get("title", doc_id)),
                description=data.get("description", str(data)[:500]),
                tags=metadata.get("tags", [])
            )
        )

        # 添加实体
        if "entity" in data:
            from odap.biz.core.ontology.schema.document import OntologyEntity
            entity_data = data["entity"]
            if isinstance(entity_data, dict):
                entity = OntologyEntity(
                    entity_id=entity_data.get("id", f"ent-{uuid.uuid4().hex[:6]}"),
                    entity_type=entity_data.get("type", "Unknown"),
                    name=entity_data.get("name", "未命名实体"),
                    basic_properties=entity_data.get("properties", {})
                )
                doc.entities.append(entity)

        return doc

    def _parse_xml(self, xml_string: str) -> Any:
        """解析 XML 字符串"""
        import xml.etree.ElementTree as ET
        try:
            return ET.fromstring(xml_string)
        except ET.ParseError as e:
            raise TransformationError(f"XML 解析失败: {e}", "xml")

    def _parse_yaml(self, yaml_string: str) -> Dict:
        """解析 YAML 字符串"""
        try:
            import yaml
            return yaml.safe_load(yaml_string)
        except Exception as e:
            raise TransformationError(f"YAML 解析失败: {e}", "yaml")

    def _xml_to_dict(self, element) -> Dict:
        """将 XML Element 转换为 dict"""
        result = {}
        if element.attrib:
            result["@attributes"] = element.attrib
        if element.text and element.text.strip():
            result["text"] = element.text.strip()
        for child in element:
            child_dict = self._xml_to_dict(child)
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_dict)
            else:
                result[child.tag] = child_dict
        return result

    def _extract_text_from_html(self, html: str) -> str:
        """从 HTML 中提取文本"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            return soup.get_text(separator="\n", strip=True)
        except ImportError:
            # 无 bs4 时使用简单正则
            import re
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', '', text)
            return text.strip()

    def _generate_field_value(self, field: str) -> Any:
        """生成缺失字段的默认值"""
        now = datetime.now(timezone.utc).isoformat()
        if field == "doc_id":
            return f"doc-{uuid.uuid4().hex[:8]}"
        elif field == "doc_type":
            return "event"
        elif field == "created_at":
            return now
        return None

    def validate_quality(self, doc: 'OntologyDocument') -> 'QualityResult':
        """
        验证本体文档的数据质量

        Returns:
            QualityResult: 包含 is_valid, errors, warnings
        """
        errors = []
        warnings = []

        # 必需字段检查
        if not doc.doc_id:
            errors.append("doc_id 不能为空")
        if not doc.doc_type:
            errors.append("doc_type 不能为空")

        # 元数据检查
        if not doc.meta.title and not doc.meta.description:
            warnings.append("建议填写 meta.title 或 meta.description")

        # 实体验证
        entity_ids = set()
        for i, entity in enumerate(doc.entities):
            for field in self.ENTITY_REQUIRED_FIELDS:
                if not getattr(entity, field, None):
                    warnings.append(f"entities[{i}] 缺少 {field}")

            if entity.entity_id:
                if entity.entity_id in entity_ids:
                    errors.append(f"实体 ID 重复: {entity.entity_id}")
                entity_ids.add(entity.entity_id)

        # 关系验证
        for i, rel in enumerate(doc.relations):
            if rel.source_entity and rel.source_entity not in entity_ids:
                warnings.append(f"relations[{i}].source_entity '{rel.source_entity}' 未在实体列表中")
            if rel.target_entity and rel.target_entity not in entity_ids:
                warnings.append(f"relations[{i}].target_entity '{rel.target_entity}' 未在实体列表中")

        # 事件验证
        has_events = len(doc.events) > 0
        if not has_events and not doc.entities:
            warnings.append("文档没有实体和事件，建议添加至少一个实体或事件")

        return QualityResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def get_transform_stats(self) -> Dict[str, int]:
        """获取转换统计信息"""
        return {
            "transform_count": self.transform_count,
            "error_count": self.error_count,
            "success_rate": self.transform_count / max(1, self.transform_count + self.error_count)
        }


class QualityResult:
    """数据质量验证结果"""
    def __init__(self, is_valid: bool, errors: List[str], warnings: List[str]):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings


# 全局实例
_transform_service: Optional[OntologyTransformService] = None


def get_transform_service() -> OntologyTransformService:
    """获取转换服务单例"""
    global _transform_service
    if _transform_service is None:
        _transform_service = OntologyTransformService()
    return _transform_service