# 全链路深入设计文档：Phase 1~5 详细实现

> **版本**: 2.3.0 | **日期**: 2026-05-07 | **状态**: 深度设计稿
>
> **前置文档**: [ARCHITECTURE_FULL_CHAIN.md](ARCHITECTURE_FULL_CHAIN.md) —
> **v2.3 变更**: §3.7-3.8 精简去重，引用 session_memory/DESIGN.md 为权威来源
>
> **v2.0.0 新增**: Phase 1 数据库Schema/任务队列/WebSocket进度 | Phase 2 版本管理/回滚/差异可视化 | Phase 3 会话记忆/上下文窗口/引用溯源 | Phase 4 热重载/并发控制/版本化 | Phase 5 A/B测试/反馈聚合/异常检测

---

## 目录

1. [Phase 1: 数据摄入深入设计](#phase-1-数据摄入深入设计)
   - 1.10 [数据库Schema设计](#110-数据库schema设计)
   - 1.11 [任务队列与异步处理](#111-任务队列与异步处理)
   - 1.12 [WebSocket实时进度推送](#112-websocket实时进度推送)
2. [Phase 2: 自动本体构建深入设计](#phase-2-自动本体构建深入设计)
    - 2.7 [API 路由](#27-api-路由)
    - 2.8 [版本管理系统](#28-版本管理系统)
    - 2.9 [回滚机制](#29-回滚机制)
    - 2.10 [本体版本差异可视化](#210-本体版本差异可视化)
3. [Phase 3: 用户问答深入设计](#phase-3-用户问答深入设计)
   - 3.7 [会话记忆管理](#37-会话记忆管理)
   - 3.8 [多轮对话与上下文窗口管理](#38-多轮对话与上下文窗口管理)
   - 3.9 [引用溯源与答案可信度](#39-引用溯源与答案可信度)
4. [Phase 4: Skill执行深入设计](#phase-4-skill执行深入设计)
   - 4.5 [Skill热重载机制](#45-skill热重载机制)
   - 4.6 [Skill并发控制与限流](#46-skill并发控制与限流)
   - 4.7 [Skill版本化](#47-skill版本化)
5. [Phase 5: 闭环反馈深入设计](#phase-5-闭环反馈深入设计)
   - 5.7 [A/B测试框架](#57-ab测试框架-prompt优化)
   - 5.8 [反馈分析聚合引擎](#58-反馈分析聚合引擎)
   - 5.9 [异常检测系统](#59-异常检测系统)
   - 5.10 [前端反馈仪表盘](#510-前端反馈仪表盘)

---

## Phase 1: 数据摄入深入设计

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           数据摄入系统 (Data Ingestion)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐  │
│  │   前端界面    │───▶│   API Gateway │───▶│  Ingestion   │───▶│ 存储层   │  │
│  │  IngestWizard │    │  /api/v1/ingest│    │   Service    │    │          │  │
│  └──────────────┘    └──────────────┘    └──────┬───────┘    └────┬─────┘  │
│                                                  │                 │       │
│                                                  ▼                 ▼       │
│                                           ┌──────────────┐  ┌──────────┐  │
│                                           │ Document     │  │ Raw File │  │
│                                           │ Processor    │  │ Storage  │  │
│                                           └──────┬───────┘  └──────────┘  │
│                                                  │                         │
│                          ┌───────────────────────┼───────────────────────┐  │
│                          ▼                       ▼                       ▼  │
│                   ┌────────────┐        ┌────────────┐         ┌──────────┐ │
│                   │ PDF Parser │        │ DOCX Parser│         │ Markdown │  │
│                   │            │        │            │         │  Parser  │  │
│                   └─────┬──────┘        └─────┬──────┘         └────┬─────┘ │
│                         │                     │                     │       │
│                         └─────────────────────┼─────────────────────┘       │
│                                               ▼                             │
│                                      ┌──────────────┐                      │
│                                      │ Chunk Splitter│                      │
│                                      │ (Text Segmentation)│                 │
│                                      └──────┬───────┘                      │
│                                             ▼                              │
│                          ┌──────────────────┼──────────────────┐          │
│                          ▼                  ▼                  ▼          │
│                   ┌────────────┐    ┌────────────┐    ┌────────────┐     │
│                   │ NER Engine │    │Relation Extr│    │ Event Det. │     │
│                   │ (实体识别)  │    │ (关系抽取)  │    │ (事件检测)  │     │
│                   └─────┬──────┘    └─────┬──────┘    └─────┬──────┘     │
│                         │                 │                 │            │
│                         └─────────────────┼─────────────────┘            │
│                                           ▼                              │
│                                  ┌────────────────┐                      │
│                                  │ Result Merger   │                      │
│                                  │ & Deduplication │                      │
│                                  └───────┬────────┘                      │
│                                          ▼                               │
│                                  ┌────────────────┐                      │
│                                  │  IngestionJob   │                      │
│                                  │  (DB Record)    │                      │
│                                  └────────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心数据模型

```python
# odap/ingestion/models.py

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from uuid import uuid4

class IngestSourceType(str, Enum):
    FILE_UPLOAD = "file_upload"          # 文件上传
    TEXT_PASTE = "text_paste"            # 文本粘贴
    DB_CONNECT = "db_connect"            # 数据库连接
    API_SOURCE = "api_source"            # API数据源

class IngestJobStatus(str, Enum):
    PENDING = "pending"                  # 等待处理
    UPLOADING = "uploading"              # 文件上传中
    PARSING = "parsing"                  # 文档解析中
    EXTRACTING = "extracting"            # 信息抽取中
    MERGING = "merging"                  # 结果合并中
    COMPLETED = "completed"              # 处理完成
    REVIEW_READY = "review_ready"        # 等待人工审核
    FAILED = "failed"                    # 处理失败
    CANCELLED = "cancelled"              # 已取消

class ChunkStrategy(str, Enum):
    PARAGRAPH = "paragraph"              # 按段落
    SENTENCE = "sentence"                # 按句子
    FIXED_SIZE = "fixed_size"            # 固定大小
    SEMANTIC = "semantic"                # 语义分块

class ExtractedEntity(BaseModel):
    """抽取的实体"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str                           # 实体名称
    type: str                           # 实体类型 (Campaign/Unit/Weapon/Intel等)
    aliases: list[str] = []             # 别名列表
    properties: dict = {}               # 提取的属性
    confidence: float = 0.0             # 置信度 0-1
    source_chunk_ids: list[str] = []    # 来源chunk ID列表
    source_text: str = ""               # 来源文本片段

class ExtractedRelation(BaseModel):
    """抽取的关系"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_entity_id: str              # 源实体ID
    target_entity_id: str              # 目标实体ID
    type: str                          # 关系类型 (COMMANDED_BY/EQUIPPED_WITH等)
    properties: dict = {}              # 关系属性
    confidence: float = 0.0            # 置信度
    source_chunk_ids: list[str] = []   # 来源chunk
    source_text: str = ""              # 来源文本

class ExtractedEvent(BaseModel):
    """抽取的事件"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str                    # 事件类型
    description: str                   # 事件描述
    participants: list[str] = []       # 参与实体ID
    timestamp: Optional[datetime] = None
    properties: dict = {}
    confidence: float = 0.0
    source_chunk_ids: list[str] = []

class IngestionJob(BaseModel):
    """摄入任务"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    scenario_id: str
    source_type: IngestSourceType
    status: IngestJobStatus = IngestJobStatus.PENDING
    chunk_strategy: ChunkStrategy = ChunkStrategy.PARAGRAPH
    chunk_size: int = 1000              # chunk最大字数

    # 输入
    original_files: list[str] = []     # 原始文件路径
    raw_text: str = ""                 # 原始文本(文本粘贴模式)

    # 输出
    chunks: list[dict] = []            # 文本分块
    entities: list[ExtractedEntity] = []
    relations: list[ExtractedRelation] = []
    events: list[ExtractedEvent] = []

    # 统计
    stats: dict = {}
    errors: list[dict] = []

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
```

### 1.3 文档处理器设计

```python
# odap/ingestion/document_processor.py

import fitz  # PyMuPDF for PDF
import docx  # python-docx
import markdown
from pathlib import Path
from typing import Protocol

class DocumentParser(Protocol):
    """文档解析器协议"""
    def parse(self, file_path: Path) -> str:
        """解析文档为纯文本"""
        ...

class PDFParser:
    """PDF解析器"""
    def parse(self, file_path: Path) -> str:
        doc = fitz.open(str(file_path))
        texts = []
        for page in doc:
            texts.append(page.get_text())
        doc.close()
        return "\n\n".join(texts)

class DocxParser:
    """Word文档解析器"""
    def parse(self, file_path: Path) -> str:
        doc = docx.Document(str(file_path))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

class MarkdownParser:
    """Markdown解析器"""
    def parse(self, file_path: Path) -> str:
        return file_path.read_text(encoding="utf-8")

class ExcelParser:
    """Excel解析器(结构化数据转文本)"""
    def parse(self, file_path: Path) -> str:
        import pandas as pd
        df = pd.read_excel(file_path)
        return df.to_markdown(index=False)

# 解析器注册表
PARSER_REGISTRY: dict[str, DocumentParser] = {
    ".pdf": PDFParser(),
    ".docx": DocxParser(),
    ".doc": DocxParser(),
    ".md": MarkdownParser(),
    ".markdown": MarkdownParser(),
    ".txt": MarkdownParser(),
    ".xlsx": ExcelParser(),
    ".xls": ExcelParser()
}

def parse_document(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    parser = PARSER_REGISTRY.get(ext)
    if not parser:
        raise ValueError(f"不支持的文件格式: {ext}")
    return parser.parse(file_path)
```

### 1.4 文本分块策略

```python
# odap/ingestion/chunker.py

import re
from typing import Iterator

class TextChunker:
    """文本分块器 - 支持多种分块策略"""

    DEFAULT_CHUNK_SIZE = 1000          # 字符数

    def chunk(self, text: str, strategy: ChunkStrategy, size: int = DEFAULT_CHUNK_SIZE) -> list[dict]:
        chunks = []
        raw_chunks = list(self._split(text, strategy, size))

        for i, chunk_text in enumerate(raw_chunks):
            chunks.append({
                "id": f"chunk_{i:04d}",
                "text": chunk_text.strip(),
                "index": i,
                "char_count": len(chunk_text),
                "prev_chunk_id": f"chunk_{i-1:04d}" if i > 0 else None,
                "next_chunk_id": f"chunk_{i+1:04d}" if i < len(raw_chunks) - 1 else None
            })

        return chunks

    def _split(self, text: str, strategy: ChunkStrategy, size: int) -> Iterator[str]:
        match strategy:
            case ChunkStrategy.PARAGRAPH:
                yield from self._paragraph_split(text)
            case ChunkStrategy.SENTENCE:
                yield from self._sentence_split(text, size)
            case ChunkStrategy.FIXED_SIZE:
                yield from self._fixed_size_split(text, size)
            case ChunkStrategy.SEMANTIC:
                yield from self._semantic_split(text, size)

    def _paragraph_split(self, text: str) -> Iterator[str]:
        """按双换行分割段落，保留段落完整性"""
        paragraphs = re.split(r'\n\s*\n', text)
        return (p for p in paragraphs if p.strip())

    def _sentence_split(self, text: str, max_size: int) -> Iterator[str]:
        """按句子分割，控制每个chunk的最大长度"""
        sentences = re.split(r'(?<=[。！？.!?\n])\s*', text)
        buffer = ""
        for sent in sentences:
            if len(buffer) + len(sent) > max_size and buffer:
                yield buffer
                buffer = sent
            else:
                buffer += sent
        if buffer:
            yield buffer

    def _fixed_size_split(self, text: str, size: int) -> Iterator[str]:
        """固定大小分块，在句子边界断句"""
        start = 0
        while start < len(text):
            end = start + size
            if end >= len(text):
                yield text[start:]
                break

            # 回退到最近的句子边界
            cut_point = max(
                text.rfind("。", start, end),
                text.rfind("！", start, end),
                text.rfind("？", start, end),
                text.rfind("\n", start, end)
            )
            if cut_point > start:
                end = cut_point + 1

            yield text[start:end]
            start = end

    def _semantic_split(self, text: str, size: int) -> Iterator[str]:
        """语义分块 - 使用LLM识别主题边界 (高级策略，按需启用)"""
        # Phase 1 可先简化为段落分块，后续迭代引入LLM语义分割
        yield from self._paragraph_split(text)
```

### 1.5 信息抽取引擎

```python
# odap/ingestion/extractor.py

import asyncio
import json
from typing import Optional
from openai import AsyncOpenAI

class ExtractionEngine:
    """基于LLM的信息抽取引擎 - 从文本中提取实体、关系、事件"""

    ENTITY_TYPES = [
        "Person", "Organization", "Location", "Date", "Event",
        "Weapon", "Unit", "Campaign", "Target", "Intel",
        "StrikeOrder", "Facility", "Document", "Concept"
    ]

    RELATION_TYPES = [
        "COMMANDED_BY", "EQUIPPED_WITH", "LOCATED_AT",
        "TARGETS", "PARTICIPATED_IN", "DERIVED_FROM",
        "BELONGS_TO", "LED_BY", "CAUSED", "RESULTED_IN"
    ]

    def __init__(self, llm_client: AsyncOpenAI, model: str = "gpt-4"):
        self.llm = llm_client
        self.model = model

    async def extract(
        self,
        chunks: list[dict],
        extract_entities: bool = True,
        extract_relations: bool = True,
        extract_events: bool = False,
        progress_callback: Optional[callable] = None
    ) -> dict:
        """批量处理所有chunk，返回聚合结果"""
        all_entities: list[ExtractedEntity] = []
        all_relations: list[ExtractedRelation] = []
        all_events: list[ExtractedEvent] = []

        total = len(chunks)
        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(i / total)

            result = await self._extract_from_chunk(
                chunk,
                extract_entities=extract_entities,
                extract_relations=extract_relations,
                extract_events=extract_events
            )

            all_entities.extend(result.get("entities", []))
            all_relations.extend(result.get("relations", []))
            all_events.extend(result.get("events", []))

        if progress_callback:
            progress_callback(1.0)

        # 合并去重
        merged = await self._merge_and_deduplicate(all_entities, all_relations, all_events)
        return merged

    async def _extract_from_chunk(self, chunk: dict, **opts) -> dict:
        """从单个chunk抽取信息"""
        prompt = self._build_extraction_prompt(chunk["text"], **opts)

        response = await self.llm.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        content = response.choices[0].message.content
        raw_result = json.loads(content)

        # 添加chunk来源信息
        return self._enrich_with_source(raw_result, chunk["id"])

    def _build_extraction_prompt(self, text: str, extract_entities: bool, extract_relations: bool, extract_events: bool) -> str:
        type_list = ", ".join(self.ENTITY_TYPES)
        rel_list = ", ".join(self.RELATION_TYPES)

        tasks = []
        if extract_entities:
            tasks.append(f"- 识别文本中的实体(类型: {type_list})，提取{name, type, aliases, properties, confidence}")
        if extract_relations:
            tasks.append(f"- 识别实体间的关系(类型: {rel_list})，提取{source_entity_name, target_entity_name, type, confidence}")
        if extract_events:
            tasks.append("- 识别文本中描述的事件，提取{event_type, description, participants, confidence}")

        return f"""分析以下文本并提取结构化信息:

## 文本内容
{text[:3000]}  # 限制输入长度

## 任务
{chr(10).join(tasks)}

## 输出格式 (JSON)
{{
  "entities": [
    {{"name": "", "type": "", "aliases": [], "properties": {{}}, "confidence": 0.95}}
  ],
  "relations": [
    {{"source_entity_name": "", "target_entity_name": "", "type": "" , "confidence": 0.9}}
  ],
  "events": [
    {{"event_type": "", "description": "", "participants": [], "confidence": 0.85}}
  ]
}}"""

    def _enrich_with_source(self, raw: dict, chunk_id: str) -> dict:
        for entity in raw.get("entities", []):
            entity["source_chunk_ids"] = [chunk_id]
            entity["id"] = str(uuid4())
        for rel in raw.get("relations", []):
            rel["source_chunk_ids"] = [chunk_id]
            rel["id"] = str(uuid4())
        for evt in raw.get("events", []):
            evt["source_chunk_ids"] = [chunk_id]
            evt["id"] = str(uuid4())
        return raw

    async def _merge_and_deduplicate(
        self,
        entities: list[ExtractedEntity],
        relations: list[ExtractedRelation],
        events: list[ExtractedEvent]
    ) -> dict:
        """跨chunk合并去重：同名实体合并，关系去重"""
        # 实体合并：按名称+类型分组
        entity_groups: dict[tuple[str, str], list[ExtractedEntity]] = {}
        for e in entities:
            key = (e.name.lower().strip(), e.type)
            if key not in entity_groups:
                entity_groups[key] = []
            entity_groups[key].append(e)

        merged_entities = []
        for (name, etype), group in entity_groups.items():
            # 合并：取最高置信度、聚合alias和properties
            best = max(group, key=lambda x: x.confidence)
            all_aliases = list(set(a for e in group for a in e.aliases))
            all_props = {}
            for e in group:
                all_props.update(e.properties)
            all_chunks = list(set(c for e in group for c in e.source_chunk_ids))

            merged_entities.append(ExtractedEntity(
                id=best.id,
                name=best.name,
                type=etype,
                aliases=all_aliases,
                properties=all_props,
                confidence=max(e.confidence for e in group),
                source_chunk_ids=all_chunks
            ))

        # 关系去重：按(源名, 目标名, 类型)去重
        seen_rels = set()
        merged_relations = []
        for r in relations:
            key = (r.source_entity_id, r.target_entity_id, r.type)
            if key not in seen_rels:
                seen_rels.add(key)
                merged_relations.append(r)

        return {
            "entities": merged_entities,
            "relations": merged_relations,
            "events": events
        }
```

### 1.6 Ingestion Service

```python
# odap/ingestion/service.py

import asyncio
from pathlib import Path
from openai import AsyncOpenAI
from .models import *
from .document_processor import parse_document
from .chunker import TextChunker
from .extractor import ExtractionEngine

class IngestionService:
    """数据摄入服务 - 编排完整的摄入流程"""

    def __init__(self, upload_dir: Path, llm_client: AsyncOpenAI):
        self.upload_dir = upload_dir
        self.llm = llm_client
        self.chunker = TextChunker()
        self.extractor = ExtractionEngine(llm_client)
        self._active_jobs: dict[str, IngestionJob] = {}

    async def create_job(
        self,
        workspace_id: str,
        scenario_id: str,
        source_type: IngestSourceType,
        files: list[bytes] = None,
        file_names: list[str] = None,
        raw_text: str = "",
        chunk_strategy: ChunkStrategy = ChunkStrategy.PARAGRAPH,
        chunk_size: int = 1000
    ) -> IngestionJob:
        """创建摄入任务并启动处理"""
        job = IngestionJob(
            workspace_id=workspace_id,
            scenario_id=scenario_id,
            source_type=source_type,
            chunk_strategy=chunk_strategy,
            chunk_size=chunk_size
        )

        # 保存上传文件
        if files and file_names:
            workspace_dir = self.upload_dir / workspace_id
            workspace_dir.mkdir(parents=True, exist_ok=True)

            for file_data, fname in zip(files, file_names):
                file_path = workspace_dir / fname
                file_path.write_bytes(file_data)
                job.original_files.append(str(file_path))

        if raw_text:
            job.raw_text = raw_text

        self._active_jobs[job.id] = job

        # 异步启动处理
        asyncio.create_task(self._process_job(job))
        return job

    async def _process_job(self, job: IngestionJob):
        """后台处理摄入任务"""
        try:
            # Step 1: 解析文档 → 纯文本
            job.status = IngestJobStatus.PARSING
            all_text = job.raw_text

            for file_path_str in job.original_files:
                file_path = Path(file_path_str)
                all_text += "\n\n" + parse_document(file_path)

            if not all_text.strip():
                raise ValueError("未提取到任何文本内容")

            # Step 2: 文本分块
            job.chunks = self.chunker.chunk(all_text, job.chunk_strategy, job.chunk_size)
            job.stats["chunk_count"] = len(job.chunks)
            job.stats["total_chars"] = sum(c["char_count"] for c in job.chunks)

            # Step 3: 信息抽取 (带进度)
            job.status = IngestJobStatus.EXTRACTING
            result = await self.extractor.extract(
                job.chunks,
                progress_callback=lambda p: setattr(job, 'stats', {**job.stats, 'extract_progress': p})
            )

            job.entities = result["entities"]
            job.relations = result["relations"]
            job.events = result["events"]

            job.stats["entity_count"] = len(job.entities)
            job.stats["relation_count"] = len(job.relations)
            job.stats["event_count"] = len(job.events)

            job.status = IngestJobStatus.REVIEW_READY
            job.completed_at = datetime.now()

        except Exception as e:
            job.status = IngestJobStatus.FAILED
            job.errors.append({"step": str(job.status), "error": str(e)})
            raise

    def get_job(self, job_id: str) -> Optional[IngestionJob]:
        return self._active_jobs.get(job_id)

    def cancel_job(self, job_id: str):
        job = self._active_jobs.get(job_id)
        if job and job.status not in (IngestJobStatus.COMPLETED, IngestJobStatus.FAILED):
            job.status = IngestJobStatus.CANCELLED
```

### 1.7 前端IngestionWizard组件

```typescript
// frontend/src/modules/ingestion/components/IngestionWizard.tsx

import React, { useState, useCallback } from 'react'
import { Steps, Upload, Button, Card, Progress, Space, Radio, Select, Input, Typography } from 'antd'
import { InboxOutlined, FileTextOutlined, DatabaseOutlined, ApiOutlined } from '@ant-design/icons'
import { useMutation } from '@tanstack/react-query'
import { IngestionAPI } from '@/services/api'
import { ExtractedEntity, ExtractedRelation, IngestionJob, ChunkStrategy } from '@/types/ingestion'
import { EntityPreviewTable } from './EntityPreviewTable'
import { RelationPreviewTable } from './RelationPreviewTable'
import { ErrorDisplay } from './ErrorDisplay'

const { Dragger } = Upload
const { Title, Text } = Typography

const STEP_DEFINITIONS = [
  { key: 'select_source', title: '选择来源' },
  { key: 'upload',        title: '上传数据' },
  { key: 'config',        title: '处理配置' },
  { key: 'processing',    title: '处理中' },
  { key: 'preview',       title: '结果预览' }
]

export const IngestionWizard: React.FC<{ onComplete: (job: IngestionJob) => void }> = ({ onComplete }) => {
  const [currentStep, setCurrentStep] = useState(0)
  const [sourceType, setSourceType] = useState<'file' | 'text' | 'db' | 'api'>('file')
  const [files, setFiles] = useState<File[]>([])
  const [rawText, setRawText] = useState('')
  const [chunkStrategy, setChunkStrategy] = useState<ChunkStrategy>('paragraph')
  const [chunkSize, setChunkSize] = useState(1000)
  const [job, setJob] = useState<IngestionJob | null>(null)

  // 创建摄入任务 mutation
  const createJob = useMutation({
    mutationFn: () => IngestionAPI.uploadFiles({
      workspace_id: currentWorkspaceId,
      scenario_id: currentScenarioId,
      source_type: sourceType,
      files: sourceType === 'file' ? files : undefined,
      raw_text: sourceType === 'text' ? rawText : undefined,
      chunk_strategy: chunkStrategy,
      chunk_size: chunkSize
    }),
    onSuccess: (data) => {
      setJob(data)
      pollJobStatus(data.id)
    }
  })

  // 轮询处理状态
  const pollJobStatus = async (jobId: string) => {
    const poll = setInterval(async () => {
      const updated = await IngestionAPI.getJob(jobId)
      setJob(updated)

      if (['review_ready', 'failed'].includes(updated.status)) {
        clearInterval(poll)
        if (updated.status === 'review_ready') {
          setCurrentStep(4) // 跳到预览步骤
        }
      }
    }, 1000)
  }

  const renderStepContent = () => {
    switch (currentStep) {
      case 0: // 选择来源
        return (
          <div className="source-selector">
            <Title level={4}>选择数据来源</Title>
            <Radio.Group value={sourceType} onChange={e => setSourceType(e.target.value)} size="large">
              <Radio.Button value="file">
                <FileTextOutlined /> 文件上传
              </Radio.Button>
              <Radio.Button value="text">
                <InboxOutlined /> 文本粘贴
              </Radio.Button>
              <Radio.Button value="db" disabled>
                <DatabaseOutlined /> 数据库 (即将支持)
              </Radio.Button>
              <Radio.Button value="api" disabled>
                <ApiOutlined /> API (即将支持)
              </Radio.Button>
            </Radio.Group>
          </div>
        )

      case 1: // 上传
        return sourceType === 'file' ? (
          <Dragger
            multiple
            accept=".pdf,.docx,.doc,.md,.txt,.xlsx,.xls"
            beforeUpload={(file) => { setFiles(prev => [...prev, file]); return false }}
            onRemove={(file) => setFiles(prev => prev.filter(f => f.name !== file.name))}
            fileList={files as any}
          >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p>拖拽文件到此处或点击选择</p>
            <p className="ant-upload-hint">支持 PDF, Word, Markdown, TXT, Excel</p>
          </Dragger>
        ) : (
          <Input.TextArea
            rows={10}
            value={rawText}
            onChange={e => setRawText(e.target.value)}
            placeholder="粘贴文本内容..."
          />
        )

      case 2: // 处理配置
        return (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <div>
              <Text strong>文本分块策略</Text>
              <Select value={chunkStrategy} onChange={setChunkStrategy} style={{ width: 200 }}>
                <Select.Option value="paragraph">按段落</Select.Option>
                <Select.Option value="sentence">按句子</Select.Option>
                <Select.Option value="fixed_size">固定大小</Select.Option>
              </Select>
            </div>
            {chunkStrategy !== 'paragraph' && (
              <div>
                <Text strong>最大Chunk大小 (字符数)</Text>
                <Input type="number" value={chunkSize} onChange={e => setChunkSize(+e.target.value)} min={100} max={4000} />
              </div>
            )}
          </Space>
        )

      case 3: // 处理中
        return (
          <Card>
            <Progress
              percent={job?.stats?.extract_progress ? job.stats.extract_progress * 100 : 0}
              status={job?.status === 'failed' ? 'exception' : 'active'}
            />
            <Text type="secondary">状态: {job?.status ?? '准备中...'}</Text>
            {job?.status === 'failed' && <ErrorDisplay errors={job.errors} />}
          </Card>
        )

      case 4: // 结果预览
        return job ? (
          <div className="preview-result">
            <Title level={4}>
              抽取结果预览
              <Text type="secondary" style={{ fontSize: 14, marginLeft: 12 }}>
                实体: {job.entities.length} | 关系: {job.relations.length} | 事件: {job.events.length}
              </Text>
            </Title>
            <EntityPreviewTable entities={job.entities as ExtractedEntity[]} />
            <RelationPreviewTable relations={job.relations as ExtractedRelation[]} />
          </div>
        ) : null

      default:
        return null
    }
  }

  return (
    <div className="ingestion-wizard">
      <Steps current={currentStep} items={STEP_DEFINITIONS.map(s => ({ title: s.title }))} />

      <div className="step-content" style={{ marginTop: 32, minHeight: 300 }}>
        {renderStepContent()}
      </div>

      <div className="step-actions" style={{ marginTop: 24, textAlign: 'right' }}>
        {currentStep > 0 && currentStep < 4 && (
          <Button onClick={() => setCurrentStep(s => s - 1)}>上一步</Button>
        )}
        {currentStep < 2 && (
          <Button
            type="primary"
            onClick={() => setCurrentStep(s => s + 1)}
            disabled={sourceType === 'file' && files.length === 0 || sourceType === 'text' && !rawText.trim()}
            style={{ marginLeft: 8 }}
          >
            下一步
          </Button>
        )}
        {currentStep === 2 && (
          <Button
            type="primary"
            onClick={() => { setCurrentStep(3); createJob.mutate() }}
            loading={createJob.isPending}
            style={{ marginLeft: 8 }}
          >
            开始处理
          </Button>
        )}
        {currentStep === 4 && (
          <Button
            type="primary"
            onClick={() => { job && onComplete(job) }}
            style={{ marginLeft: 8 }}
          >
            确认，进入本体构建 →
          </Button>
        )}
      </div>
    </div>
  )
}
```

### 1.8 API 路由定义

```python
# odap/api/routes/ingestion.py

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/ingest", tags=["ingestion"])

class CreateJobRequest(BaseModel):
    workspace_id: str
    scenario_id: str
    source_type: IngestSourceType
    chunk_strategy: ChunkStrategy = ChunkStrategy.PARAGRAPH
    chunk_size: int = 1000
    raw_text: Optional[str] = None

@router.post("/upload")
async def create_ingestion_job(
    req: CreateJobRequest = Form(...),
    files: list[UploadFile] = File(default=[])
):
    """创建摄入任务: 上传文件并启动处理"""
    file_data = [await f.read() for f in files]
    file_names = [f.filename for f in files]

    job = await ingestion_service.create_job(
        workspace_id=req.workspace_id,
        scenario_id=req.scenario_id,
        source_type=req.source_type,
        files=file_data if file_data else None,
        file_names=file_names if file_names else None,
        raw_text=req.raw_text,
        chunk_strategy=req.chunk_strategy,
        chunk_size=req.chunk_size
    )

    return JSONResponse({
        "job_id": job.id,
        "status": job.status,
        "message": "摄入任务已创建"
    })

@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """查询摄入任务状态和结果"""
    job = ingestion_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")

    return {
        "job_id": job.id,
        "status": job.status,
        "stats": job.stats,
        "entities": [e.dict() for e in job.entities] if job.status == IngestJobStatus.REVIEW_READY else [],
        "relations": [r.dict() for r in job.relations] if job.status == IngestJobStatus.REVIEW_READY else [],
        "events": [e.dict() for e in job.events] if job.status == IngestJobStatus.REVIEW_READY else [],
        "errors": job.errors
    }

@router.post("/job/{job_id}/cancel")
async def cancel_job(job_id: str):
    """取消摄入任务"""
    job = ingestion_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    ingestion_service.cancel_job(job_id)
    return {"message": "任务已取消"}

@router.get("/parsers")
async def list_parsers():
    """列出支持的文档格式"""
    return {
        "parsers": [
            {"extension": ".pdf",  "mime": "application/pdf"},
            {"extension": ".docx", "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
            {"extension": ".md",   "mime": "text/markdown"},
            {"extension": ".txt",  "mime": "text/plain"},
            {"extension": ".xlsx", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        ]
    }
```

### 1.9 错误处理与重试机制

```python
# odap/ingestion/retry.py

import asyncio
from functools import wraps
from typing import TypeVar, Callable

T = TypeVar("T")

class IngestError(Exception):
    """摄入错误基类"""
    pass

class ParseError(IngestError):
    """文档解析错误"""
    pass

class ExtractionError(IngestError):
    """信息抽取错误"""
    pass

class LLMTimeoutError(ExtractionError):
    """LLM调用超时"""
    pass

def retry_async(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff: float = 2.0,
    retryable_exceptions: tuple = (LLMTimeoutError,)
):
    """异步重试装饰器 - 指数退避"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exc = e
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (backoff ** attempt), max_delay)
                        await asyncio.sleep(delay)
                    else:
                        raise
                except Exception:
                    raise  # 非可重试异常直接传播
            raise last_exc
        return wrapper
    return decorator
```

### 1.10 数据库Schema设计

```sql
-- odap/ingestion/schema.sql

CREATE TABLE ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    scenario_id UUID NOT NULL,
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('file_upload','text_paste','db_connect','api_source')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','uploading','parsing','extracting','merging','completed','review_ready','failed','cancelled')),
    chunk_strategy VARCHAR(20) NOT NULL DEFAULT 'paragraph',
    chunk_size INTEGER NOT NULL DEFAULT 1000 CHECK (chunk_size BETWEEN 100 AND 8000),
    raw_text TEXT,
    stats JSONB DEFAULT '{}'::jsonb,
    errors JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_by UUID NOT NULL
);

CREATE TABLE ingestion_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES ingestion_jobs(id) ON DELETE CASCADE,
    original_name VARCHAR(512) NOT NULL,
    storage_path VARCHAR(1024) NOT NULL,
    mime_type VARCHAR(128),
    file_size_bytes BIGINT,
    sha256_hash VARCHAR(64),
    parse_status VARCHAR(20) DEFAULT 'pending',
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ingestion_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES ingestion_jobs(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    prev_chunk_id UUID REFERENCES ingestion_chunks(id),
    next_chunk_id UUID REFERENCES ingestion_chunks(id),
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE extracted_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES ingestion_jobs(id) ON DELETE CASCADE,
    name VARCHAR(512) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    aliases TEXT[] DEFAULT '{}',
    properties JSONB DEFAULT '{}'::jsonb,
    confidence FLOAT NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    review_status VARCHAR(20) DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected','linked','edited')),
    linked_entity_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE extracted_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES ingestion_jobs(id) ON DELETE CASCADE,
    source_entity_id UUID NOT NULL,
    target_entity_id UUID NOT NULL,
    relation_type VARCHAR(64) NOT NULL,
    properties JSONB DEFAULT '{}'::jsonb,
    confidence FLOAT NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    review_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ingestion_jobs_workspace ON ingestion_jobs(workspace_id, created_at DESC);
CREATE INDEX idx_ingestion_jobs_status ON ingestion_jobs(status) WHERE status IN ('pending','extracting');
CREATE INDEX idx_extracted_entities_job ON extracted_entities(job_id, confidence DESC);
CREATE INDEX idx_extracted_entities_type ON extracted_entities(entity_type, review_status);
CREATE INDEX idx_extracted_relations_job ON extracted_relations(job_id, confidence DESC);
CREATE INDEX idx_ingestion_chunks_embedding ON ingestion_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### 1.11 任务队列与异步处理

```python
# odap/ingestion/queue.py

import asyncio
import redis.asyncio as redis
from dataclasses import dataclass
from typing import Optional

@dataclass
class QueueConfig:
    max_concurrent_jobs: int = 3           # 最大并发摄取任务数
    job_timeout_seconds: int = 600         # 单个任务超时时间
    retry_max_attempts: int = 3
    retry_backoff_base: float = 5.0

class IngestionQueue:
    """基于Redis的摄取任务队列 - 支持优先级、并发控制、超时处理"""

    def __init__(self, redis_client: redis.Redis, config: QueueConfig = QueueConfig()):
        self.redis = redis_client
        self.config = config
        self._active_semaphore = asyncio.Semaphore(config.max_concurrent_jobs)
        self._running_tasks: dict[str, asyncio.Task] = {}

    async def enqueue(self, job_id: str, priority: int = 0) -> bool:
        """将任务加入队列，priority越大优先级越高"""
        score = priority * 1e12 - time.time()  # ZSET score: 高优先级排前面
        await self.redis.zadd("ingestion:queue", {job_id: score})
        await self.redis.hset(f"ingestion:job:{job_id}", mapping={
            "status": "queued",
            "enqueued_at": datetime.now().isoformat()
        })
        return True

    async def dequeue(self) -> Optional[str]:
        """从队列取出最高优先级任务"""
        jobs = await self.redis.zrevrange("ingestion:queue", 0, 0)
        if not jobs:
            return None
        job_id = jobs[0]
        await self.redis.zrem("ingestion:queue", job_id)
        return job_id

    async def start_worker(self, ingestion_service: "IngestionService"):
        """启动队列消费者 - 持续消费并执行任务"""
        while True:
            job_id = await self.dequeue()
            if job_id is None:
                await asyncio.sleep(1)
                continue

            async with self._active_semaphore:
                task = asyncio.create_task(
                    self._execute_with_timeout(job_id, ingestion_service)
                )
                self._running_tasks[job_id] = task

                task.add_done_callback(lambda t, jid=job_id: self._cleanup(jid))

    async def _execute_with_timeout(self, job_id: str, service: "IngestionService"):
        """带超时保护的任务执行"""
        try:
            job = service.get_job(job_id)
            if not job:
                return

            await asyncio.wait_for(
                service._process_job(job),
                timeout=self.config.job_timeout_seconds
            )
        except asyncio.TimeoutError:
            job = service.get_job(job_id)
            if job:
                job.status = IngestJobStatus.FAILED
                job.errors.append({"step": "queue", "error": "任务执行超时"})
            await self.redis.hset(f"ingestion:job:{job_id}", "status", "failed_timeout")
        except Exception as e:
            await self.redis.hset(f"ingestion:job:{job_id}", "status", f"failed:{str(e)[:200]}")

    def _cleanup(self, job_id: str):
        self._running_tasks.pop(job_id, None)

    async def cancel_job(self, job_id: str) -> bool:
        """取消队列中或执行中的任务"""
        await self.redis.zrem("ingestion:queue", job_id)

        task = self._running_tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def get_queue_stats(self) -> dict:
        """获取队列统计信息"""
        return {
            "queued": await self.redis.zcard("ingestion:queue"),
            "running": len(self._running_tasks),
            "max_concurrent": self.config.max_concurrent_jobs
        }
```

### 1.12 WebSocket实时进度推送

```python
# odap/ingestion/ws_progress.py

import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from typing import Optional

class ProgressWebSocketManager:
    """WebSocket进度管理器 - 向客户端实时推送摄入进度"""

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}  # job_id → ws集合

    async def connect(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        self._connections.setdefault(job_id, set()).add(websocket)

    async def disconnect(self, websocket: WebSocket, job_id: str):
        conns = self._connections.get(job_id, set())
        conns.discard(websocket)
        if not conns:
            self._connections.pop(job_id, None)

    async def broadcast_progress(self, job_id: str, event: dict):
        """向订阅了指定job_id的所有客户端推送事件"""
        conns = self._connections.get(job_id, set())
        if not conns:
            return

        message = json.dumps(event, ensure_ascii=False, default=str)
        dead: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            conns.discard(ws)

    async def broadcast_job_event(self, job_id: str, stage: str, detail: dict = None):
        """推送摄入阶段事件"""
        await self.broadcast_progress(job_id, {
            "type": "job_progress",
            "job_id": job_id,
            "stage": stage,          # parsing / chunking / extracting / merging / done
            "detail": detail or {},
            "timestamp": datetime.now().isoformat()
        })

ws_progress_manager = ProgressWebSocketManager()


@router.websocket("/ws/ingest/{job_id}")
async def ingest_progress_ws(websocket: WebSocket, job_id: str):
    """WebSocket端点: 实时接收摄入进度"""
    await ws_progress_manager.connect(websocket, job_id)
    try:
        while True:
            # 保持连接，等待客户端消息(ping)或断开
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        await ws_progress_manager.disconnect(websocket, job_id)
```

---

## Phase 2: 自动本体构建深入设计

### 2.1 构建流水线架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        本体构建流水线 (Ontology Build Pipeline)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 1 输出 (entities, relations, events)                                 │
│       │                                                                     │
│       ▼                                                                     │
│  ┌──────────────────────────┐                                              │
│  │ Normalization Stage      │  ← 实体标准化: 去重、同义词合并、链接已有实体  │
│  │ 实体标准化                │                                              │
│  └──────────┬───────────────┘                                              │
│             ▼                                                               │
│  ┌──────────────────────────┐                                              │
│  │ Validation Stage          │  ← 关系验证: 类型兼容性检查                  │
│  │ 关系验证                  │                                              │
│  └──────────┬───────────────┘                                              │
│             ▼                                                               │
│  ┌──────────────────────────┐                                              │
│  │ Consistency Stage        │  ← 一致性检查: 冲突检测、冗余检测、孤立节点    │
│  │ 一致性检查                │                                              │
│  └──────────┬───────────────┘                                              │
│             ▼                                                               │
│  ┌──────────────────────────┐                                              │
│  │ Review Stage             │  ← ⚠️ 人工决策点                              │
│  │ 人工审核                  │     • 确认/拒绝/修改实体                      │
│  │                          │     • 确认/拒绝/修改关系                      │
│  │                          │     • 解决冲突                               │
│  └──────────┬───────────────┘                                              │
│             ▼                                                               │
│  ┌──────────────────────────┐                                              │
│  │ Commit Stage             │  ← 写入Graphiti + 创建版本快照                 │
│  │ 提交写入                  │                                              │
│  └──────────┬───────────────┘                                              │
│             ▼                                                               │
│  ┌──────────────────────────┐                                              │
│  │ Notification Stage       │  ← 通知问答引擎 + 图谱刷新                      │
│  │ 变更通知                  │                                              │
│  └──────────────────────────┘                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 实体标准化引擎

```python
# odap/ontology_builder/normalizer.py

from difflib import SequenceMatcher
from typing import Optional

class EntityNormalizer:
    """实体标准化 - 链接同名/近名实体，合并同义词"""

    SIMILARITY_THRESHOLD = 0.85           # 名称相似度阈值

    def normalize(
        self,
        new_entities: list[ExtractedEntity],
        existing_entities: list[dict]       # 来自Graphiti的已有实体
    ) -> tuple[list[ExtractedEntity], list[dict]]:
        """
        返回:
        - normalized: 标准化后的实体列表
        - link_map: 链接到已有实体的映射 {new_entity_id: existing_entity_id}
        """
        normalized = []
        link_map = {}

        # 建立已有实体索引: name → entity
        existing_index: dict[str, dict] = {}
        for e in existing_entities:
            key = e["name"].lower().strip()
            existing_index[key] = e

        for entity in new_entities:
            existing = self._find_match(entity, existing_entities, existing_index)
            if existing:
                # 链接到已有实体: 合并属性
                entity.properties = {**existing.get("properties", {}), **entity.properties}
                link_map[entity.id] = existing["id"]
            normalized.append(entity)

        # 跨新实体去重
        normalized = self._deduplicate_within_batch(normalized)
        return normalized, link_map

    def _find_match(
        self,
        entity: ExtractedEntity,
        existing: list[dict],
        index: dict
    ) -> Optional[dict]:
        """查找匹配的已有实体"""
        # 精确匹配
        key = entity.name.lower().strip()
        if key in index:
            return index[key]

        # 模糊匹配
        for e in existing:
            similarity = SequenceMatcher(None, key, e["name"].lower().strip()).ratio()
            if similarity >= self.SIMILARITY_THRESHOLD:
                return e

        # 别名匹配
        for e in existing:
            for alias in entity.aliases:
                if alias.lower().strip() == e["name"].lower().strip():
                    return e

        return None

    def _deduplicate_within_batch(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """同一批次内去重"""
        seen = {}
        result = []
        for e in entities:
            key = (e.name.lower().strip(), e.type)
            if key in seen:
                # 合并到已有的
                existing = seen[key]
                existing.aliases = list(set(existing.aliases + e.aliases))
                existing.properties.update(e.properties)
                existing.source_chunk_ids = list(set(existing.source_chunk_ids + e.source_chunk_ids))
                existing.confidence = max(existing.confidence, e.confidence)
            else:
                seen[key] = e
                result.append(e)
        return result
```

### 2.3 关系验证器

```python
# odap/ontology_builder/validator.py

from dataclasses import dataclass

@dataclass
class RelationRule:
    """关系规则: 定义允许的源类型→目标类型组合"""
    source_types: list[str]
    target_types: list[str]
    relation_type: str

# 关系类型约束表
RELATION_RULES: list[RelationRule] = [
    RelationRule(["Unit"], ["Unit", "Campaign"], "COMMANDED_BY"),
    RelationRule(["Unit"], ["Weapon"], "EQUIPPED_WITH"),
    RelationRule(["Unit", "Weapon", "Campaign"], ["Location"], "LOCATED_AT"),
    RelationRule(["Campaign", "StrikeOrder"], ["Target", "Unit", "Location"], "TARGETS"),
    RelationRule(["Intel"], ["Event", "Unit", "Target"], "DERIVED_FROM"),
    RelationRule(["Unit"], ["Campaign", "Event"], "PARTICIPATED_IN"),
]

class RelationValidator:
    """关系验证器 - 检查关系类型兼容性"""

    def validate(
        self,
        relations: list[ExtractedRelation],
        entities: dict[str, ExtractedEntity]   # id→entity 映射
    ) -> list[dict]:
        """验证所有关系，返回问题列表"""
        issues = []

        for rel in relations:
            source = entities.get(rel.source_entity_id)
            target = entities.get(rel.target_entity_id)

            if not source or not target:
                issues.append({
                    "type": "missing_entity",
                    "relation_id": rel.id,
                    "entity_id": rel.source_entity_id if not source else rel.target_entity_id,
                    "message": "关系引用的实体不存在"
                })
                continue

            # 检查关系类型兼容性
            rule = self._find_rule(rel.type)
            if rule:
                if source.type not in rule.source_types:
                    issues.append({
                        "type": "incompatible_type",
                        "relation_id": rel.id,
                        "entity_id": source.id,
                        "entity_type": source.type,
                        "relation_type": rel.type,
                        "message": f"源实体类型 '{source.type}' 不允许作为 '{rel.type}' 的源"
                    })
                if target.type not in rule.target_types:
                    issues.append({
                        "type": "incompatible_type",
                        "relation_id": rel.id,
                        "entity_id": target.id,
                        "entity_type": target.type,
                        "relation_type": rel.type,
                        "message": f"目标实体类型 '{target.type}' 不允许作为 '{rel.type}' 的目标"
                    })
            else:
                # 未定义的关系类型 → 标记为可疑但不拒绝
                issues.append({
                    "type": "unknown_relation",
                    "relation_id": rel.id,
                    "relation_type": rel.type,
                    "message": f"未知的关系类型 '{rel.type}'"
                })

        return issues

    def _find_rule(self, relation_type: str) -> Optional[RelationRule]:
        return next((r for r in RELATION_RULES if r.relation_type == relation_type), None)
```

### 2.4 一致性检查器

```python
# odap/ontology_builder/consistency.py

class ConsistencyChecker:
    """一致性检查 - 冲突检测 + 冗余检测 + 孤立节点"""

    def check(
        self,
        entities: list[ExtractedEntity],
        relations: list[ExtractedRelation]
    ) -> list[dict]:
        issues = []

        # 1. 检测冗余关系 (A→B 同类型存在多条)
        rel_pairs = {}
        for rel in relations:
            key = (rel.source_entity_id, rel.target_entity_id, rel.type)
            if key in rel_pairs:
                issues.append({
                    "type": "duplicate_relation",
                    "duplicate_ids": [rel_pairs[key].id, rel.id],
                    "message": f"发现重复关系: {rel.type}"
                })
            rel_pairs[key] = rel

        # 2. 检测孤立节点 (没有参与任何关系的实体)
        connected = set()
        for rel in relations:
            connected.add(rel.source_entity_id)
            connected.add(rel.target_entity_id)

        isolated = [
            e for e in entities
            if e.id not in connected and e.type not in ("Concept", "Document")
        ]
        for e in isolated:
            issues.append({
                "type": "isolated_entity",
                "entity_id": e.id,
                "entity_name": e.name,
                "message": f"实体 '{e.name}' 没有参与任何关系"
            })

        # 3. 检测自引用 (A→A)
        for rel in relations:
            if rel.source_entity_id == rel.target_entity_id:
                issues.append({
                    "type": "self_reference",
                    "relation_id": rel.id,
                    "message": f"关系 '{rel.type}' 的源和目标指向同一实体"
                })

        return issues
```

### 2.5 人工审核界面详细设计

```typescript
// frontend/src/modules/ontology/pages/OntologyReviewPage.tsx

import React, { useState, useMemo, useCallback } from 'react'
import {
  Table, Tag, Button, Space, Modal, Input, Tabs,
  Typography, Badge, Card, Statistic, Row, Col, Popconfirm
} from 'antd'
import {
  CheckOutlined, CloseOutlined, EditOutlined,
  WarningOutlined, MergeCellsOutlined, LinkOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { ExtractedEntity, ExtractedRelation, ValidationIssue } from '@/types/ontology'

const { Title, Text } = Typography

type ReviewStatus = 'pending' | 'approved' | 'rejected' | 'edited' | 'linked'

interface ReviewItem {
  id: string
  data: ExtractedEntity | ExtractedRelation
  originalData: ExtractedEntity | ExtractedRelation  // 原始抽取结果，用于撤销
  type: 'entity' | 'relation'
  status: ReviewStatus
  rejectReason?: string
  linkedToId?: string           // 链接到的已有实体ID
  confidence: number
}

export const OntologyReviewPage: React.FC<{
  ingestionJobId: string
  onBuildComplete: (versionId: string) => void
}> = ({ ingestionJobId, onBuildComplete }) => {
  const [activeTab, setActiveTab] = useState<'entities' | 'relations' | 'issues'>('entities')
  const [reviewItems, setReviewItems] = useState<ReviewItem[]>([])
  const [issues, setIssues] = useState<ValidationIssue[]>([])
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [editingItem, setEditingItem] = useState<ReviewItem | null>(null)
  const [linkModalVisible, setLinkModalVisible] = useState(false)
  const [linkingItem, setLinkingItem] = useState<ReviewItem | null>(null)
  const [buildLoading, setBuildLoading] = useState(false)

  // 统计
  const stats = useMemo(() => ({
    total: reviewItems.length,
    approved: reviewItems.filter(i => i.status === 'approved').length,
    rejected: reviewItems.filter(i => i.status === 'rejected').length,
    pending: reviewItems.filter(i => i.status === 'pending').length,
    edited: reviewItems.filter(i => i.status === 'edited').length,
    linked: reviewItems.filter(i => i.status === 'linked').length,
    issues: issues.length,
    avgConfidence: reviewItems.length > 0
      ? reviewItems.reduce((s, i) => s + i.confidence, 0) / reviewItems.length
      : 0
  }), [reviewItems, issues])

  // 批量操作
  const handleApproveAll = useCallback(() => {
    setReviewItems(prev => prev
      .filter(i => i.status === 'pending' || i.status === 'edited')
      .map(i => ({ ...i, status: 'approved' as ReviewStatus }))
    )
  }, [])

  const handleRejectLowConfidence = useCallback((threshold: number) => {
    const confirm = () => {
      setReviewItems(prev => prev.map(item =>
        item.status === 'pending' && item.confidence < threshold
          ? { ...item, status: 'rejected' as ReviewStatus, rejectReason: `置信度过低(<${threshold})` }
          : item
      ))
    }
    // 简化确认流程，生产环境应使用 Modal.confirm
    confirm()
  }, [])

  // 单个操作
  const approveItem = (id: string) =>
    setReviewItems(prev => prev.map(item => item.id === id ? { ...item, status: 'approved' } : item))

  const rejectItem = (id: string, reason: string = '用户拒绝') =>
    setReviewItems(prev => prev.map(item =>
      item.id === id ? { ...item, status: 'rejected', rejectReason: reason } : item
    ))

  const linkItem = (id: string, existingEntityId: string) =>
    setReviewItems(prev => prev.map(item =>
      item.id === id ? { ...item, status: 'linked', linkedToId: existingEntityId } : item
    ))

  // 提价构建
  const handleBuildOntology = async () => {
    setBuildLoading(true)
    const approvedItems = reviewItems.filter(i =>
      ['approved', 'edited', 'linked'].includes(i.status)
    )
    try {
      const result = await OntologyAPI.build({
        workspace_id: currentWorkspaceId,
        scenario_id: currentScenarioId,
        entities: approvedItems.filter(i => i.type === 'entity').map(i => i.data),
        relations: approvedItems.filter(i => i.type === 'relation').map(i => i.data)
      })
      onBuildComplete(result.version_id)
    } catch (err) {
      // 错误处理
    } finally {
      setBuildLoading(false)
    }
  }

  // 实体表格列定义
  const entityColumns: ColumnsType<ReviewItem> = [
    {
      title: '状态',
      dataIndex: 'status',
      width: 80,
      render: (status: ReviewStatus) => {
        const config: Record<ReviewStatus, { color: string; label: string }> = {
          pending:  { color: 'default', label: '待审核' },
          approved: { color: 'success', label: '已确认' },
          rejected: { color: 'error',   label: '已拒绝' },
          edited:   { color: 'warning', label: '已修改' },
          linked:   { color: 'blue',    label: '已链接' }
        }
        return <Tag color={config[status].color}>{config[status].label}</Tag>
      }
    },
    {
      title: '实体名称',
      dataIndex: ['data', 'name'],
      render: (name: string, record: ReviewItem) => (
        <Text strong={record.status !== 'rejected'} delete={record.status === 'rejected'}>{name}</Text>
      )
    },
    {
      title: '类型',
      dataIndex: ['data', 'type'],
      render: (type: string) => <Tag color="blue">{type}</Tag>,
      filters: uniqueValues(reviewItems.filter(i => i.type === 'entity').map(i => (i.data as ExtractedEntity).type))
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      width: 100,
      render: (c: number) => {
        let color = '#52c41a'
        if (c < 0.7) color = '#ff4d4f'
        else if (c < 0.85) color = '#faad14'
        return <Tag color={color}>{(c * 100).toFixed(0)}%</Tag>
      },
      sorter: (a, b) => a.confidence - b.confidence
    },
    {
      title: '操作',
      width: 200,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<CheckOutlined />} onClick={() => approveItem(record.id)}>确认</Button>
          <Button size="small" icon={<CloseOutlined />} onClick={() => rejectItem(record.id)}>拒绝</Button>
          {record.linkedToId ? (
            <Tag icon={<LinkOutlined />} color="blue">已链接</Tag>
          ) : (
            <Button size="small" icon={<LinkOutlined />}
                    onClick={() => { setLinkingItem(record); setLinkModalVisible(true) }}>
              链接
            </Button>
          )}
        </Space>
      )
    }
  ]

  return (
    <div className="ontology-review-page">
      {/* 顶部统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={4}><Card><Statistic title="总计"   value={stats.total} /></Card></Col>
        <Col span={4}><Card><Statistic title="待审核" value={stats.pending} valueStyle={{ color: '#faad14' }} /></Card></Col>
        <Col span={4}><Card><Statistic title="已确认" value={stats.approved} valueStyle={{ color: '#52c41a' }} /></Card></Col>
        <Col span={4}><Card><Statistic title="已拒绝" value={stats.rejected} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
        <Col span={4}><Card><Statistic title="信任度" value={`${(stats.avgConfidence * 100).toFixed(0)}%`} /></Card></Col>
        <Col span={4}>
          <Card>
            <Badge count={stats.issues} offset={[10, 0]}>
              <Statistic title="问题" value={stats.issues} valueStyle={{ color: stats.issues > 0 ? '#ff4d4f' : '#52c41a' }} />
            </Badge>
          </Card>
        </Col>
      </Row>

      {/* 主Tab */}
      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <Tabs.TabPane tab={`实体 (${reviewItems.filter(i => i.type === 'entity').length})`} key="entities">
          <Table<ReviewItem>
            dataSource={reviewItems.filter(i => i.type === 'entity')}
            columns={entityColumns}
            rowKey="id"
          />
        </Tabs.TabPane>

        <Tabs.TabPane tab={`关系 (${reviewItems.filter(i => i.type === 'relation').length})`} key="relations">
          {/* 关系表格类似设计，略 */}
        </Tabs.TabPane>

        <Tabs.TabPane
          tab={<Badge count={issues.length}><Text>冲突/问题</Text></Badge>}
          key="issues"
        >
          {/* 问题列表 */}
        </Tabs.TabPane>
      </Tabs>

      {/* 底部操作区 */}
      <div className="review-footer" style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
        <Space>
          <Button onClick={handleApproveAll}>全部确认</Button>
          <Button onClick={() => handleRejectLowConfidence(0.7)}>拒绝低置信度 (&lt;70%)</Button>
        </Space>

        <Button
          type="primary"
          size="large"
          icon={<CheckOutlined />}
          onClick={handleBuildOntology}
          loading={buildLoading}
          disabled={stats.pending > 0}
        >
          构建本体 ({stats.approved + stats.edited + stats.linked} 个实体/关系)
        </Button>
      </div>
    </div>
  )
}
```

### 2.6 写入Graphiti实现

```python
# odap/ontology_builder/graphiti_writer.py

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from typing import Optional

class GraphitiWriter:
    """将审核通过的实体关系批量写入Graphiti"""

    def __init__(self, graphiti: Graphiti):
        self.graphiti = graphiti
        self.group_id = str(uuid4())      # 本次构建的分组ID

    async def commit(
        self,
        workspace_id: str,
        entities: list[ExtractedEntity],
        relations: list[ExtractedRelation],
        entity_link_map: dict[str, str] = None    # 链接到已有实体的映射
    ) -> dict:
        """
        写入Graphiti并返回构建统计
        支持事务性写入: 所有操作在同一批次中执行
        """
        entity_link_map = entity_link_map or {}
        created_nodes = {}
        linked_count = 0

        # 写入实体节点
        for entity in entities:
            if entity.id in entity_link_map:
                # 更新已有实体 (追加新属性)
                existing_id = entity_link_map[entity.id]
                await self.graphiti.add_entity_node(
                    uuid=existing_id,
                    name=entity.name,
                    group_id=self.group_id,
                    summary=f"属性更新: {json.dumps(entity.properties, ensure_ascii=False)}",
                    created_at=datetime.now()
                )
                linked_count += 1
            else:
                # 创建新实体
                node = await self.graphiti.add_entity_node(
                    name=entity.name,
                    entity_type=entity.type,
                    group_id=self.group_id,
                    summary=f"实体类型: {entity.type}, 属性: {json.dumps(entity.properties, ensure_ascii=False)[:500]}",
                    created_at=datetime.now()
                )
                created_nodes[entity.id] = node.uuid

        # 写入关系边
        new_relations = 0
        for relation in relations:
            source_uuid = (
                entity_link_map.get(relation.source_entity_id) or
                created_nodes.get(relation.source_entity_id)
            )
            target_uuid = (
                entity_link_map.get(relation.target_entity_id) or
                created_nodes.get(relation.target_entity_id)
            )

            if source_uuid and target_uuid:
                await self.graphiti.add_relationship_edge(
                    source_uuid=source_uuid,
                    target_uuid=target_uuid,
                    relationship_type=relation.type,
                    group_id=self.group_id,
                    summary=f"关系类型: {relation.type}, 置信度: {relation.confidence:.2f}",
                    created_at=datetime.now()
                )
                new_relations += 1

        # 创建本体版本快照
        version = await self._create_version_snapshot(
            workspace_id=workspace_id,
            created_count=len(created_nodes),
            linked_count=linked_count,
            new_relations=new_relations
        )

        return {
            "group_id": self.group_id,
            "version_id": version.id,
            "new_nodes": len(created_nodes),
            "linked_nodes": linked_count,
            "new_relations": new_relations
        }

    async def _create_version_snapshot(self, workspace_id: str, created_count: int, linked_count: int, new_relations: int) -> "OntologyVersion":
        version = OntologyVersion(
            id=str(uuid4()),
            workspace_id=workspace_id,
            group_id=self.group_id,
            timestamp=datetime.now(timezone.utc),
            stats={
                "created_entities": created_count,
                "linked_entities": linked_count,
                "new_relations": new_relations
            }
        )
        # 存储到DB
        return version
```

### 2.7 API 路由

```python
# odap/api/routes/ontology_build.py

router = APIRouter(prefix="/api/v1/ontology", tags=["ontology_build"])

class BuildRequest(BaseModel):
    workspace_id: str
    scenario_id: str
    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]

@router.post("/build")
async def build_ontology(req: BuildRequest):
    """提交本体构建请求"""
    # 验证阶段
    normalizer = EntityNormalizer()
    validator = RelationValidator()
    checker = ConsistencyChecker()

    # 获取已有实体
    existing = await graphiti_client.get_entities(req.workspace_id)
    normalized_entities, link_map = normalizer.normalize(req.entities, existing)

    # 验证关系
    entities_index = {e.id: e for e in normalized_entities}
    relation_issues = validator.validate(req.relations, entities_index)
    consistency_issues = checker.check(normalized_entities, req.relations)

    all_issues = relation_issues + consistency_issues

    if all_issues:
        return {
            "status": "issues_found",
            "issues": all_issues,
            "normalized_entities": [e.dict() for e in normalized_entities],
            "link_map": link_map
        }

    # 写入Graphiti
    writer = GraphitiWriter(graphiti_client)
    result = await writer.commit(req.workspace_id, normalized_entities, req.relations, link_map)

    # 通知变更
    await event_bus.publish("ontology:updated", {
        "workspace_id": req.workspace_id,
        "version_id": result["version_id"]
    })

    return {
        "status": "success",
        "version_id": result["version_id"],
        "stats": result
    }

@router.get("/versions/{workspace_id}")
async def list_versions(workspace_id: str):
    """列出某工作空间的本体版本历史"""
    return await version_manager.list_versions(workspace_id)

@router.post("/versions/{version_id}/rollback")
async def rollback_version(version_id: str):
    """回滚到指定版本"""
    previous = await version_manager.get_version(version_id)
    if not previous:
        raise HTTPException(404, "版本不存在")

    # 删除当前group_id之后的所有节点和边
    # 重新加载previous版本的快照
    result = await version_manager.rollback(version_id)
    await event_bus.publish("ontology:updated", {"version_id": result["new_version_id"]})

    return {"status": "rolled_back", "version_id": result["new_version_id"]}
```

### 2.8 版本管理系统

```python
# odap/ontology_builder/version_manager.py

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

@dataclass
class OntologyVersion:
    id: str                              # 版本ID (UUID)
    workspace_id: str
    version_number: str                  # 语义版本号, 如 "1.4.0"
    group_id: str                        # Graphiti group_id (全局唯一，用于快照隔离)
    parent_version_id: Optional[str]     # 父版本ID (形成版本链)
    snapshot: dict                       # 完整快照: {entities, relations, metadata}
    change_summary: dict                 # 变更摘要: {added, modified, deleted}
    created_at: datetime
    created_by: str
    comment: str = ""

class OntologyVersionManager:
    """本体版本管理器 - 快照、比较、回滚、分支"""

    def __init__(self, db_pool, graphiti_client):
        self.db = db_pool
        self.graphiti = graphiti_client

    async def create_version(
        self,
        workspace_id: str,
        entities: list[ExtractedEntity],
        relations: list[ExtractedRelation],
        comment: str = ""
    ) -> OntologyVersion:
        """创建新版本快照"""
        # 获取上一个版本号
        last_version = await self._get_latest_version(workspace_id)
        new_number = self._bump_version(last_version.version_number if last_version else "0.0.0")

        # 生成唯一group_id (用于Graphiti中的数据隔离)
        group_id = _generate_group_id(workspace_id, new_number)

        # 构造完整快照
        snapshot = {
            "version": new_number,
            "entities": [self._serialize_entity(e) for e in entities],
            "relations": [self._serialize_relation(r) for r in relations],
            "entity_count": len(entities),
            "relation_count": len(relations)
        }

        # 计算与父版本的差异
        change_summary = await self._compute_diff(
            workspace_id, last_version, entities, relations
        ) if last_version else {"added": len(entities), "modified": 0, "deleted": 0}

        version = OntologyVersion(
            id=str(uuid4()),
            workspace_id=workspace_id,
            version_number=new_number,
            group_id=group_id,
            parent_version_id=last_version.id if last_version else None,
            snapshot=snapshot,
            change_summary=change_summary,
            created_at=datetime.now(timezone.utc),
            created_by="system",
            comment=comment
        )

        # 持久化到DB
        await self.db.execute(
            """INSERT INTO ontology_versions (id, workspace_id, version_number, group_id, parent_version_id,
               snapshot, change_summary, created_at, created_by, comment)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
            version.id, version.workspace_id, version.version_number, version.group_id,
            version.parent_version_id, json.dumps(snapshot), json.dumps(change_summary),
            version.created_at, version.created_by, version.comment
        )

        return version

    async def get_version(self, version_id: str) -> Optional[OntologyVersion]:
        """获取指定版本"""
        row = await self.db.fetchrow(
            "SELECT * FROM ontology_versions WHERE id = $1", version_id
        )
        return self._row_to_version(row) if row else None

    async def list_versions(self, workspace_id: str, limit: int = 20) -> list[OntologyVersion]:
        """列出所有版本历史 (倒序)"""
        rows = await self.db.fetch(
            "SELECT * FROM ontology_versions WHERE workspace_id = $1 ORDER BY created_at DESC LIMIT $2",
            workspace_id, limit
        )
        return [self._row_to_version(r) for r in rows]

    async def get_version_chain(self, workspace_id: str) -> list[dict]:
        """获取版本演化链 (用于前端可视化)"""
        versions = await self.list_versions(workspace_id)
        chain = []
        for v in reversed(versions):  # 从旧到新
            chain.append({
                "version": v.version_number,
                "id": v.id,
                "entity_count": v.snapshot["entity_count"],
                "relation_count": v.snapshot["relation_count"],
                "changes": v.change_summary,
                "created_at": v.created_at.isoformat(),
                "comment": v.comment
            })
        return chain

    async def compare_versions(self, version_id_a: str, version_id_b: str) -> dict:
        """比较两个版本的差异 - 返回可渲染的diff结构"""
        v_a = await self.get_version(version_id_a)
        v_b = await self.get_version(version_id_b)
        if not v_a or not v_b:
            raise ValueError("版本不存在")

        entities_a = {e["name"]: e for e in v_a.snapshot["entities"]}
        entities_b = {e["name"]: e for e in v_b.snapshot["entities"]}

        diff = {
            "entities_added": [e for name, e in entities_b.items() if name not in entities_a],
            "entities_removed": [e for name, e in entities_a.items() if name not in entities_b],
            "entities_modified": [],
            "relations_added": 0,
            "relations_removed": 0,
            "relations_modified": 0
        }

        # 检测修改的实体
        for name, e_a in entities_a.items():
            e_b = entities_b.get(name)
            if e_b and e_a["properties"] != e_b["properties"]:
                diff["entities_modified"].append({
                    "name": name,
                    "before": e_a["properties"],
                    "after": e_b["properties"]
                })

        # 关系计数
        diff["relations_added"] = len(v_b.snapshot["relations"]) - len(v_a.snapshot["relations"])
        if diff["relations_added"] < 0:
            diff["relations_removed"] = abs(diff["relations_added"])
            diff["relations_added"] = 0

        return diff

    def _bump_version(self, current: str) -> str:
        """递增语义版本号: 每次摄入→补丁版本+1"""
        parts = [int(x) for x in current.split(".")]
        parts[2] += 1  # patch bump
        if parts[2] >= 100:
            parts[1] += 1
            parts[2] = 0
        return ".".join(str(p) for p in parts)

    async def _get_latest_version(self, workspace_id: str) -> Optional[OntologyVersion]:
        row = await self.db.fetchrow(
            "SELECT * FROM ontology_versions WHERE workspace_id = $1 ORDER BY created_at DESC LIMIT 1",
            workspace_id
        )
        return self._row_to_version(row) if row else None

    async def _compute_diff(
        self,
        workspace_id: str,
        prev: OntologyVersion,
        new_entities: list,
        new_relations: list
    ) -> dict:
        prev_entity_names = {e["name"] for e in prev.snapshot["entities"]}
        new_entity_names = {e.name for e in new_entities}
        return {
            "added": len(new_entity_names - prev_entity_names),
            "modified": len(new_entity_names & prev_entity_names),
            "deleted": len(prev_entity_names - new_entity_names)
        }

    def _serialize_entity(self, e: ExtractedEntity) -> dict:
        return {
            "name": e.name,
            "type": e.type,
            "aliases": e.aliases,
            "properties": e.properties,
            "confidence": e.confidence
        }

    def _serialize_relation(self, r: ExtractedRelation) -> dict:
        return {
            "source_entity_id": r.source_entity_id,
            "target_entity_id": r.target_entity_id,
            "type": r.type,
            "properties": r.properties,
            "confidence": r.confidence
        }

    def _row_to_version(self, row) -> OntologyVersion:
        return OntologyVersion(
            id=row["id"],
            workspace_id=row["workspace_id"],
            version_number=row["version_number"],
            group_id=row["group_id"],
            parent_version_id=row["parent_version_id"],
            snapshot=json.loads(row["snapshot"]),
            change_summary=json.loads(row["change_summary"]),
            created_at=row["created_at"],
            created_by=row["created_by"],
            comment=row.get("comment", "")
        )
```

### 2.9 回滚机制

```python
# odap/ontology_builder/rollback.py

class OntologyRollbackEngine:
    """本体回滚引擎 - 支持精确回滚到任意历史版本"""

    def __init__(self, version_manager: OntologyVersionManager, graphiti_client):
        self.versions = version_manager
        self.graphiti = graphiti_client

    async def rollback(self, target_version_id: str) -> dict:
        """
        回滚到指定版本。关键原则:
        1. 不删除任何数据 (Graphiti双时态特性)
        2. 创建新transaction_time的快照恢复
        3. 所有"被回滚的变更"可追溯
        """
        target = await self.versions.get_version(target_version_id)
        if not target:
            raise ValueError(f"目标版本 {target_version_id} 不存在")

        latest = await self.versions._get_latest_version(target.workspace_id)
        if not latest:
            raise ValueError("当前工作空间无版本")

        # 1. 创建回滚版本 (基于target的快照，但使用新的version number和group_id)
        rollback_version = await self.versions.create_version(
            workspace_id=target.workspace_id,
            entities=[self._deserialize_entity(e) for e in target.snapshot["entities"]],
            relations=[self._deserialize_relation(r) for r in target.snapshot["relations"]],
            comment=f"回滚至版本 {target.version_number} (来自 {latest.version_number})"
        )

        # 2. 将回滚版本的实体/关系写入Graphiti (新transaction_time)
        writer = GraphitiWriter(self.graphiti)
        await writer.commit(
            workspace_id=target.workspace_id,
            entities=[self._deserialize_entity(e) for e in target.snapshot["entities"]],
            relations=[self._deserialize_relation(r) for r in target.snapshot["relations"]],
            link_map={},
            group_id=rollback_version.group_id
        )

        # 3. 记录审计日志
        await audit_logger.log(
            event="ontology_rollback",
            workspace_id=target.workspace_id,
            from_version=latest.version_number,
            to_version=rollback_version.version_number,
            target_snapshot_version=target.version_number,
            rollback_version_id=rollback_version.id
        )

        return {
            "status": "rolled_back",
            "from_version": latest.version_number,
            "to_version": rollback_version.version_number,
            "rollback_version_id": rollback_version.id,
            "restored_entities": target.snapshot["entity_count"],
            "restored_relations": target.snapshot["relation_count"]
        }

    def _deserialize_entity(self, data: dict) -> ExtractedEntity:
        return ExtractedEntity(
            name=data["name"],
            type=data["type"],
            aliases=data.get("aliases", []),
            properties=data.get("properties", {}),
            confidence=data.get("confidence", 1.0)
        )

    def _deserialize_relation(self, data: dict) -> ExtractedRelation:
        return ExtractedRelation(
            source_entity_id=data["source_entity_id"],
            target_entity_id=data["target_entity_id"],
            type=data["type"],
            properties=data.get("properties", {}),
            confidence=data.get("confidence", 1.0)
        )
```

### 2.10 本体版本差异可视化

```typescript
// frontend/src/modules/ontology/components/VersionDiffViewer.tsx

import React, { useMemo } from 'react'
import { Timeline, Tag, Card, Descriptions, Collapse, Typography, Space, Badge, Tabs } from 'antd'
import {
  PlusOutlined, MinusOutlined, EditOutlined,
  ClockCircleOutlined, RollbackOutlined
} from '@ant-design/icons'
import ReactDiffViewer, { DiffMethod } from 'react-diff-viewer-continued'

const { Title, Text } = Typography
const { Panel } = Collapse

interface VersionDiff {
  entities_added: any[]
  entities_removed: any[]
  entities_modified: { name: string; before: any; after: any }[]
  relations_added: number
  relations_removed: number
  relations_modified: number
  stats: {
    entity_count_before: number
    entity_count_after: number
    relation_count_before: number
    relation_count_after: number
  }
}

export const VersionDiffViewer: React.FC<{
  workspaceId: string
  versionIdA: string
  versionIdB: string
}> = ({ workspaceId, versionIdA, versionIdB }) => {
  const { data: diff, isLoading } = useQuery({
    queryKey: ['ontology-diff', workspaceId, versionIdA, versionIdB],
    queryFn: () => OntologyAPI.compareVersions(versionIdA, versionIdB)
  })

  const diffStats = useMemo(() => {
    if (!diff) return { added: 0, removed: 0, modified: 0, total: 0 }
    return {
      added: diff.entities_added.length + diff.relations_added,
      removed: diff.entities_removed.length + diff.relations_removed,
      modified: diff.entities_modified.length + diff.relations_modified,
      total: diff.entities_added.length + diff.entities_removed.length +
             diff.entities_modified.length + diff.relations_added +
             diff.relations_removed + diff.relations_modified
    }
  }, [diff])

  if (isLoading) return <div>加载差异数据中...</div>
  if (!diff) return <div>无法加载差异数据</div>

  return (
    <div className="version-diff-viewer">
      {/* Diff 统计概览 */}
      <Card style={{ marginBottom: 16 }}>
        <Space size="large">
          <Statistic title="总计变更" value={diffStats.total} />
          <Badge status="success" text={<Text>{diffStats.added} 新增</Text>} />
          <Badge status="error" text={<Text>{diffStats.removed} 删除</Text>} />
          <Badge status="warning" text={<Text>{diffStats.modified} 修改</Text>} />
          <Divider type="vertical" />
          <Text type="secondary">
            实体: {diff.stats.entity_count_before} → {diff.stats.entity_count_after}
          </Text>
          <Text type="secondary">
            关系: {diff.stats.relation_count_before} → {diff.stats.relation_count_after}
          </Text>
        </Space>
      </Card>

      <Tabs defaultActiveKey="entities">
        <Tabs.TabPane tab={`实体变更 (${diff.entities_added.length + diff.entities_removed.length + diff.entities_modified.length})`} key="entities">
          {/* 新增实体 */}
          {diff.entities_added.length > 0 && (
            <Collapse defaultActiveKey={['added']}>
              <Panel header={<Badge status="success" text={`新增实体 (${diff.entities_added.length})`} />} key="added">
                {diff.entities_added.map((e: any) => (
                  <Card key={e.name} size="small" style={{ marginBottom: 8 }}>
                    <Tag color="green" icon={<PlusOutlined />}>{e.type}</Tag>
                    <Text strong>{e.name}</Text>
                    <pre style={{ marginTop: 8, fontSize: 12 }}>
                      {JSON.stringify(e.properties, null, 2)}
                    </pre>
                  </Card>
                ))}
              </Panel>
            </Collapse>
          )}

          {/* 删除实体 */}
          {diff.entities_removed.length > 0 && (
            <Collapse defaultActiveKey={['removed']} style={{ marginTop: 8 }}>
              <Panel header={<Badge status="error" text={`删除实体 (${diff.entities_removed.length})`} />} key="removed">
                {diff.entities_removed.map((e: any) => (
                  <Card key={e.name} size="small" style={{ marginBottom: 8, opacity: 0.6 }}>
                    <Tag color="red" icon={<MinusOutlined />}>{e.type}</Tag>
                    <Text delete>{e.name}</Text>
                  </Card>
                ))}
              </Panel>
            </Collapse>
          )}

          {/* 修改实体 */}
          {diff.entities_modified.map((e: any) => (
            <Card key={e.name} size="small" style={{ marginBottom: 8, marginTop: 8 }}>
              <Tag color="orange" icon={<EditOutlined />}>已修改</Tag>
              <Text strong>{e.name}</Text>
              <div style={{ marginTop: 8 }}>
                <ReactDiffViewer
                  oldValue={JSON.stringify(e.before, null, 2)}
                  newValue={JSON.stringify(e.after, null, 2)}
                  splitView
                  compareMethod={DiffMethod.WORDS}
                  leftTitle="修改前"
                  rightTitle="修改后"
                  styles={{ diffContainer: { fontSize: 12 } }}
                />
              </div>
            </Card>
          ))}
        </Tabs.TabPane>
        <Tabs.TabPane tab={`关系变更 (${diff.relations_added + diff.relations_removed + diff.relations_modified})`} key="relations">
          {/* 关系变更统计简化展示 */}
          <Descriptions bordered>
            <Descriptions.Item label="新增关系">{diff.relations_added} 条</Descriptions.Item>
            <Descriptions.Item label="删除关系">{diff.relations_removed} 条</Descriptions.Item>
            <Descriptions.Item label="修改关系">{diff.relations_modified} 条</Descriptions.Item>
          </Descriptions>
        </Tabs.TabPane>
      </Tabs>
    </div>
  )
}

// 版本演化时间线
export const VersionTimeline: React.FC<{ workspaceId: string }> = ({ workspaceId }) => {
  const { data: versions } = useQuery({
    queryKey: ['ontology-versions', workspaceId],
    queryFn: () => OntologyAPI.listVersions(workspaceId)
  })

  return (
    <Timeline mode="left">
      {versions?.map((v: any) => (
        <Timeline.Item
          key={v.id}
          dot={<ClockCircleOutlined style={{ fontSize: 16 }} />}
          label={v.version}
          color="blue"
        >
          <Card size="small">
            <Text type="secondary">实体: {v.entity_count} | 关系: {v.relation_count}</Text>
            <br />
            <Text>
              +{v.changes.added} / ~{v.changes.modified} / -{v.changes.deleted}
            </Text>
            {v.comment && <><br /><Text italic>{v.comment}</Text></>}
            <br />
            <Space style={{ marginTop: 4 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {new Date(v.created_at).toLocaleString()}
              </Text>
              <Button size="small" type="link" icon={<RollbackOutlined />}>
                回滚至此版本
              </Button>
            </Space>
          </Card>
        </Timeline.Item>
      ))}
    </Timeline>
  )
}
```

---

## Phase 3: 用户问答深入设计

### 3.1 增强的RAG问答架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          RAG 增强问答引擎 (QA Engine)                       │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  用户输入 ──▶ ┌────────────┐ ──▶ ┌──────────────┐ ──▶ ┌──────────────┐   │
│              │ 查询理解    │     │ 多路检索      │     │ 上下文构造    │   │
│              │ Understand  │     │ Retrieve      │     │ Context      │   │
│              └──────┬───────┘     └───────┬───────┘     └───────┬──────┘   │
│                     │                     │                       │        │
│                     ▼                     ▼                       ▼        │
│              ┌──────────────┐   ┌──────────────────┐    ┌──────────────┐   │
│              │ 意图识别      │   │ Graphiti Entity  │    │ Prompt模板   │   │
│              │ • 信息查询    │   │ Search           │    │ + 实体嵌入   │   │
│              │ • 数据分析    │   │ + Vector Search  │    │ + 时序上下文  │   │
│              │ • 决策建议    │   │ + Cypher查询     │    │ + Skill列表   │   │
│              │ • 动作执行    │   └────────┬─────────┘    └───────┬───────┘   │
│              └──────┬───────┘                                       │        │
│                     │                                               ▼        │
│                     ▼                                       ┌──────────────┐   │
│              ┌──────────────┐                              │ LLM推理      │   │
│              │ 歧义检查      │                              │ + 来源标注    │   │
│              │ • 实体不明确  │                              │ + Skill建议   │   │
│              │ • 需要具体化  │                              │ + 实体标记    │   │
│              └──────┬───────┘                              └───────┬───────┘   │
│                     │                                               │        │
│                     ▼                                               ▼        │
│              ┌──────────────┐                              ┌──────────────┐   │
│              │ 反问澄清      │                              │ SSE流式输出  │   │
│              │ (如果需要)    │                              │ → 用户界面    │   │
│              └──────────────┘                              └──────────────┘   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 查询理解与意图识别

```python
# odap/qa_engine/query_understanding.py

from enum import Enum

class IntentType(str, Enum):
    INFO_QUERY = "info_query"           # 信息查询 (这是什么/有什么/是谁)
    DATA_ANALYSIS = "data_analysis"     # 数据分析 (统计/趋势/对比)
    DECISION_SUPPORT = "decision"       # 决策建议 (怎么办/如何做)
    ACTION_EXECUTION = "action"         # 动作执行 (执行XX操作/发送指令)

class QueryUnderstanding:
    """查询理解: 意图识别 + 实体链接 + 歧义检测"""

    async def analyze(
        self,
        query: str,
        workspace_id: str,
        scenario_id: str,
        session_context: list[dict]      # 会话上下文
    ) -> dict:
        """
        分析用户查询，返回:
        - intent: 意图类型
        - linked_entities: 在Graphiti中找到的实体ID列表
        - ambiguous_entities: 可能有歧义的实体名→候选列表
        - require_clarification: 是否需要反问澄清
        """

        # 1. 意图识别
        intent = await self._detect_intent(query)

        # 2. 实体链接: 模糊搜索Graphiti中的实体
        candidates = await self._search_entities(query, workspace_id)

        # 3. 歧义检测
        ambiguous = self._detect_ambiguity(candidates, session_context)

        # 4. 判断是否需要澄清
        require_clarification = bool(ambiguous) and intent != IntentType.INFO_QUERY

        return {
            "intent": intent,
            "linked_entities": [
                c["entity_id"] for c in candidates if c["score"] > 0.8
            ],
            "ambiguous_entities": [
                {"name": name, "candidates": cands}
                for name, cands in ambiguous.items()
            ],
            "require_clarification": require_clarification,
            "top_candidates": sorted(candidates, key=lambda x: x["score"], reverse=True)[:5]
        }

    async def _detect_intent(self, query: str) -> IntentType:
        """使用LLM进行意图分类"""
        # 这里使用轻量级分类prompt，避免和主问答LLM混淆
        # 也可以用关键词+规则做快速分类
        analysis_keywords = ["统计", "分析", "趋势", "对比", "占比", "分布"]
        decision_keywords = ["怎么办", "如何应对", "建议", "方案", "决策"]
        action_keywords = ["执行", "下达", "命令", "派遣", "行动"]

        if any(kw in query for kw in action_keywords):
            return IntentType.ACTION_EXECUTION
        if any(kw in query for kw in decision_keywords):
            return IntentType.DECISION_SUPPORT
        if any(kw in query for kw in analysis_keywords):
            return IntentType.DATA_ANALYSIS
        return IntentType.INFO_QUERY

    async def _search_entities(self, query: str, workspace_id: str) -> list[dict]:
        """在Graphiti中搜索匹配的实体"""
        # 使用Graphiti的全文检索 + 语义检索
        results = await graphiti_client.search_entities(
            query=query,
            workspace_id=workspace_id,
            limit=10
        )
        return [
            {"entity_id": r.uuid, "name": r.name, "type": r.entity_type, "score": r.score}
            for r in results
        ]

    def _detect_ambiguity(self, candidates: list[dict], context: list) -> dict:
        """歧义检测: 如果同一个实体名匹配到多个候选，需要用户确认"""
        ambiguous = {}
        name_groups = {}
        for c in candidates:
            name_groups.setdefault(c["name"], []).append(c)

        for name, group in name_groups.items():
            if len(group) > 1:
                ambiguous[name] = group

        return ambiguous
```

### 3.3 Prompt模板（本体驱动）

```python
# odap/qa_engine/prompt_templates.py

SYSTEM_PROMPT = """你是ODAP系统(本体驱动分析决策平台)的智能分析助手。你的核心职责是基于系统内本体知识,回答用户问题并提供可执行的建议。

## 核心原则
1. **基于事实**: 所有结论必须基于提供的本体知识和检索结果
2. **实体可追踪**: 引用的实体/关系必须标注来源(标记格式 [[entity:实体ID:实体名称]])
3. **Suggestion可执行**: 给出的建议如涉及Skills,须标记 <<suggestion:SkillID:描述>>
4. **保持克制**: 不确定的信息勿猜测,主动请求更多相关信息
5. **时序感知**: 注意信息的valid_time和transaction_time,说明信息的时间敏感度

## 输出格式
- 直接回答用户问题
- 实体引用: [[entity:实体ID:实体名称]]
- Skill建议: <<suggestion:SkillID:建议描述&默认参数JSON>>
- 如需澄清: 以列表形式反问具体需求

## 工作空间信息
- 工作空间: {workspace_name}
- 当前场景: {scenario_name}
- 本体版本: {ontology_version}
"""

USER_QUERY_PROMPT = """## 检索到的相关实体
{entity_context}

## 检索到的相关关系
{relation_context}

## 更多补充信息
{additional_context}

## 可用Skills
{available_skills}

## 用户问题
{user_question}

## 你的回答"""

def build_entity_context(entities: list[dict]) -> str:
    """构造实体上下文"""
    if not entities:
        return "（未找到相关实体）"

    lines = []
    for e in entities:
        props_summary = json.dumps(e.get("properties", {}), ensure_ascii=False, default=str)
        lines.append(
            f"- **{e['name']}** (ID: {e['id']}) [类型: {e['type']}] "
            f"[valid_time: {e.get('valid_time', 'N/A')}]\n"
            f"  属性: {props_summary}\n"
            f"  关系数: {e.get('relation_count', 0)}条"
        )
    return "\n".join(lines)
```

### 3.4 流式SSE输出实现

```python
# odap/qa_engine/streaming.py

import asyncio
from fastapi.responses import StreamingResponse
from typing import AsyncIterator

class StreamEventType(str, Enum):
    TOKEN = "token"                # token增量
    TOOL_CALL = "tool_call"        # Skill调用
    SUGGESTION = "suggestion"      # 执行建议
    ENTITY_LINK = "entity_link"    # 实体链接标记
    ERROR = "error"                # 错误
    DONE = "done"                  # 完成

async def stream_qa_response(
    query: str,
    workspace_id: str,
    scenario_id: str,
    session_id: str,
    llm_client: AsyncOpenAI
) -> AsyncIterator[str]:
    """SSE流式问答响应生成器"""

    # Step 1: 查询理解
    yield _sse_event(StreamEventType.TOKEN, {"content": "🔍 分析中..."})
    understanding = await query_understanding.analyze(query, workspace_id, scenario_id, session_context)

    if understanding["require_clarification"]:
        clarification = build_clarification_message(understanding["ambiguous_entities"])
        yield _sse_event(StreamEventType.TOKEN, {"content": clarification})
        yield _sse_event(StreamEventType.DONE, {})
        return

    # Step 2: 检索上下文
    yield _sse_event(StreamEventType.TOKEN, {"content": "📊 检索本体知识..."})
    linked_ids = understanding["linked_entities"]
    entity_data, relation_data = await retrieve_context(linked_ids, workspace_id)

    # Step 3: 构造Prompt
    prompt = build_qa_prompt(query, entity_data, relation_data, workspace_id, session_id)

    # Step 4: 流式输出LLM响应
    yield _sse_event(StreamEventType.TOKEN, {"content": "\n\n"})

    buffer = ""
    async for chunk in llm_client.chat.completions.create(
        model="gpt-4",
        messages=prompt,
        stream=True,
        temperature=0.7
    ):
        delta = chunk.choices[0].delta.content
        if delta:
            buffer += delta
            yield _sse_event(StreamEventType.TOKEN, {"content": delta})

            # 检测实体链接标记: [[entity:123:名称]]
            if "]]" in buffer:
                links = parse_entity_links(buffer)
                for link in links:
                    yield _sse_event(StreamEventType.ENTITY_LINK, {"entity_id": link[0], "entity_name": link[1]})

    # Step 5: 解析suggestion标记
    suggestions = parse_suggestions(buffer)
    for s in suggestions:
        yield _sse_event(StreamEventType.SUGGESTION, {"skill_id": s["id"], "description": s["description"]})

    # Step 6: SSEDone
    yield _sse_event(StreamEventType.DONE, {"message_id": str(uuid4())})

def _sse_event(event_type: str, data: dict) -> str:
    """SSE 事件格式"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

@router.get("/qa/chat/stream")
async def stream_chat(
    query: str,
    workspace_id: str,
    scenario_id: str,
    session_id: str
):
    """SSE流式问答端点"""
    return StreamingResponse(
        stream_qa_response(query, workspace_id, scenario_id, session_id, llm_client),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"      # Nginx禁用缓冲
        }
    )
```

### 3.5 前端SSE消费端

```typescript
// frontend/src/hooks/useSSEChat.ts

import { useState, useRef, useCallback } from 'react'

interface SSEEventHandler {
  onToken: (token: string) => void
  onEntityLink: (entityId: string, entityName: string, sourceText: string) => void
  onSuggestion: (skillId: string, description: string, params?: any) => void
  onToolCall: (toolName: string, args: any) => void
  onError: (error: string) => void
  onDone: (messageId: string) => void
}

interface UseSSEChatOptions {
  apiPath: string
  onEvents: SSEEventHandler
  getExtraParams: () => Record<string, string>
}

export const useSSEChat = (options: UseSSEChatOptions) => {
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const bufferRef = useRef<string>('')

  const sendMessage = useCallback(async (content: string) => {
    if (isStreaming) return

    setIsStreaming(true)
    const abort = new AbortController()
    abortRef.current = abort

    try {
      const params = new URLSearchParams({
        query: content,
        ...options.getExtraParams()
      })

      const response = await fetch(`${options.apiPath}?${params}`, {
        headers: { Accept: 'text/event-stream' },
        signal: abort.signal
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let currentEventType = ''
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          // 解析SSE格式: event: xxx \n data: {json}
          if (line.startsWith('event: ')) {
            currentEventType = line.slice(7).trim()
          } else if (line.startsWith('data: ') && currentEventType) {
            const dataStr = line.slice(6).trim()
            if (!dataStr) continue

            try {
              const data = JSON.parse(dataStr)
              dispatchSSEEvent(currentEventType, data, options.onEvents)
            } catch {} // 忽略空data block
          }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        options.onEvents.onError(err.message)
      }
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [isStreaming, options])

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
    setIsStreaming(false)
  }, [])

  return { sendMessage, stopStreaming, isStreaming }
}

function dispatchSSEEvent(type: string, data: any, handlers: SSEEventHandler) {
  switch (type) {
    case 'token':
      handlers.onToken(data.content ?? '')
      break
    case 'entity_link':
      handlers.onEntityLink(data.entity_id, data.entity_name ?? '', data.source_text ?? '')
      break
    case 'suggestion':
      handlers.onSuggestion(data.skill_id, data.description ?? '', data.params)
      break
    case 'tool_call':
      handlers.onToolCall(data.tool_name, data.arguments ?? {})
      break
    case 'error':
      handlers.onError(data.error ?? '')
      break
    case 'done':
      handlers.onDone(data.message_id ?? '')
      break
  }
}
```

### 3.6 与图谱的联动

```typescript
// 消息内容解析: 将实体标记渲染为可点击的Tag
const parseContentWithEntities = (content: string, onEntityClick: (id: string) => void): React.ReactNode[] => {
  const regex = /\[\[entity:([^:]+):([^\]]+)\]\]/g
  const parts: React.ReactNode[] = []
  let lastIndex = 0
  let match

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push(content.slice(lastIndex, match.index))
    }
    parts.push(
      <Tag
        key={`entity-${match[1]}`}
        color="blue"
        style={{ cursor: 'pointer', margin: '0 2px' }}
        onClick={() => onEntityClick(match![1])}
      >
        {match[2]}
      </Tag>
    )
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < content.length) {
    parts.push(content.slice(lastIndex))
  }

  return parts
}
```

### 3.7 会话记忆管理

多轮对话中，基于 Redis 的会话记忆系统负责消息存储、滑动窗口控制、自动摘要压缩。核心组件：`ConversationMemory`（Redis List 存储、窗口裁剪）、摘要生成（每 N 轮触发 LLM 摘要压缩）、实体去重提示（提取已讨论实体列表）。

> **📘 完整模块设计见**: [session_memory/DESIGN.md §2 会话记忆管理](../../03-modules/session_memory/DESIGN.md#2-会话记忆管理) — 含 ContextWindow 模型、MemoryCompactor 压缩策略、SessionStore 持久化方案。

### 3.8 多轮对话与上下文窗口管理

在 LLM token 限制下，`ContextWindowManager` 按优先级分配 token 预算：System Prompt → 会话历史摘要(25%) → 实体/关系上下文(50%) → 用户查询。超预算时自动截断历史，保留最近消息。

> **📘 完整模块设计见**: [session_memory/DESIGN.md §2.1-2.2](../../03-modules/session_memory/DESIGN.md#21-上下文窗口模型) — 含 ChatMessage 模型、ContextWindow available_tokens 计算、MemoryCompactor 二次压缩。

### 3.9 引用溯源与答案可信度

```python
# odap/qa_engine/citation.py

from dataclasses import dataclass

@dataclass
class Citation:
    """答案引用 - 可追溯到具体数据源"""
    source_type: str                  # "entity" | "document" | "chunk"
    source_id: str
    source_name: str
    excerpt: str                      # 关键原文摘录
    confidence: float

@dataclass
class AnswerWithCitations:
    answer: str
    citations: list[Citation]
    entity_links: list[dict]
    suggestions: list[dict]
    overall_confidence: float         # 整体可信度

class CitationTracker:
    """引用追踪器 - 为LLM输出的每个断言建立溯源链"""

    async def extract_citations(
        self,
        llm_response: str,
        entity_context: list[dict],
        chunk_sources: list[dict]
    ) -> list[Citation]:
        """从LLM响应中提取实体引用标记，关联到原始数据源"""
        citations = []

        # 解析 [[entity:ID:名称]] 标记
        entity_pattern = re.compile(r'\[\[entity:([^:]+):([^\]]+)\]\]')
        for match in entity_pattern.finditer(llm_response):
            entity_id = match.group(1)
            entity_name = match.group(2)

            # 查找对应的entity上下文
            entity_data = next(
                (e for e in entity_context if e.get("id") == entity_id), None
            )

            if entity_data:
                citation = Citation(
                    source_type="entity",
                    source_id=entity_id,
                    source_name=entity_name,
                    excerpt=entity_data.get("description", ""),
                    confidence=entity_data.get("confidence", 0.0)
                )
                citations.append(citation)

        return citations

    def calculate_overall_confidence(
        self,
        citations: list[Citation],
        llm_response: str,
        hallucination_check: bool = True
    ) -> float:
        """计算答案的整体可信度"""
        if not citations:
            return 0.3  # 无引用 → 低可信度

        confidence_scores = [c.confidence for c in citations if c.confidence > 0]
        if not confidence_scores:
            return 0.4

        # 加权平均: 引用数量 * 平均置信度
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        citation_coverage = min(1.0, len(citations) / 3)  # 理想情况下至少3个引用

        return round(avg_confidence * 0.7 + citation_coverage * 0.3, 2)

    def build_citation_footer(self, citations: list[Citation]) -> str:
        """生成引用脚注 (Markdown格式)"""
        if not citations:
            return ""

        lines = ["\n---\n**📚 引用来源:**"]
        for i, c in enumerate(citations, 1):
            lines.append(
                f"{i}. **{c.source_name}** "
                f"(`{c.source_type}:{c.source_id[:8]}...`) "
                f"[可信度: {c.confidence:.0%}]"
            )
            if c.excerpt:
                lines.append(f"   > {c.excerpt[:200]}")
        return "\n".join(lines)
```

```typescript
// frontend/src/modules/qa/components/CitationPopover.tsx

import React from 'react'
import { Popover, Tag, Typography, Space, Progress } from 'antd'
import { LinkOutlined, InfoCircleOutlined, FileTextOutlined } from '@ant-design/icons'

const { Text, Paragraph } = Typography

interface Citation {
  source_type: 'entity' | 'document' | 'chunk'
  source_id: string
  source_name: string
  excerpt: string
  confidence: number
}

export const CitationPopover: React.FC<{
  citation: Citation
  onNavigateToEntity?: (entityId: string) => void
}> = ({ citation, onNavigateToEntity }) => {
  const content = (
    <div style={{ maxWidth: 400 }}>
      <Space direction="vertical" size="small">
        <div>
          <Text type="secondary">来源类型: </Text>
          <Tag color={citation.source_type === 'entity' ? 'blue' : 'green'}>
            {citation.source_type === 'entity' ? '本体实体' :
             citation.source_type === 'document' ? '原始文档' : '文本片段'}
          </Tag>
        </div>
        <div>
          <Text type="secondary">ID: </Text>
          <Text code>{citation.source_id}</Text>
        </div>
        {citation.excerpt && (
          <Paragraph
            ellipsis={{ rows: 3, expandable: true }}
            style={{ marginBottom: 8, fontStyle: 'italic' }}
          >
            "{citation.excerpt}"
          </Paragraph>
        )}
        <div>
          <Text type="secondary">可信度: </Text>
          <Progress
            percent={citation.confidence * 100}
            size="small"
            status={citation.confidence > 0.8 ? 'success' : citation.confidence > 0.6 ? 'normal' : 'exception'}
            style={{ width: 120 }}
          />
        </div>
      </Space>
    </div>
  )

  return (
    <Popover content={content} title="引用详情" trigger="hover">
      <Tag
        color="blue"
        style={{ cursor: 'pointer' }}
        icon={<LinkOutlined />}
        onClick={() => onNavigateToEntity?.(citation.source_id)}
      >
        {citation.source_name}
        <InfoCircleOutlined style={{ marginLeft: 4 }} />
      </Tag>
    </Popover>
  )
}

// 答案可信度指示器
export const ConfidenceIndicator: React.FC<{ confidence: number }> = ({ confidence }) => {
  const getStatus = () => {
    if (confidence >= 0.8) return { color: '#52c41a', text: '高可信度' }
    if (confidence >= 0.6) return { color: '#faad14', text: '中等可信度' }
    return { color: '#ff4d4f', text: '低可信度' }
  }
  const status = getStatus()

  return (
    <Popover content={`基于 ${confidence >= 0.8 ? '多个' : '有限'} 引用来源计算`}>
      <Tag color={status.color === '#52c41a' ? 'success' : status.color === '#faad14' ? 'warning' : 'error'}>
        {status.text}: {(confidence * 100).toFixed(0)}%
      </Tag>
    </Popover>
  )
}
```

### 3.10 思维链渲染组件设计

> **对应需求**: FR-401 (Agent 决策过程可视化), FR-1101 (推理路径可视化)
> **关联模块**: [session_memory/DESIGN.md](../../03-modules/session_memory/DESIGN.md)

```python
# odap/qa_engine/cot_renderer.py

from enum import Enum
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class CoTNodeType(str, Enum):
    INTENT = "intent"
    ENTITY_LINK = "entity_link"
    CONTEXT_FETCH = "context_fetch"
    RAG_AUGMENT = "rag_augment"
    LLM_INFER = "llm_infer"
    TOOL_CALL = "tool_call"
    DECISION = "decision"
    SYNTHESIS = "synthesis"

class CoTNode(BaseModel):
    id: str
    type: CoTNodeType
    label: str
    detail: str = ""
    status: str = "pending"
    parent_id: Optional[str] = None
    children_ids: list[str] = []
    timing_ms: Optional[int] = None

class CoTTree(BaseModel):
    root_id: str
    nodes: dict[str, CoTNode]
    version: int = 1

class CoTBuilder:
    """在 QA 推理过程中逐步构建思维链树"""

    def __init__(self, user_query: str):
        root = CoTNode(id="root", type=CoTNodeType.INTENT,
                       label=f"用户问题: {user_query[:60]}...", status="done")
        self._tree = CoTTree(root_id="root", nodes={"root": root})
        self._counter = 0

    def add_node(self, parent_id: str, node_type: CoTNodeType,
                 label: str, detail: str = "") -> CoTNode:
        self._counter += 1
        node = CoTNode(id=f"n{self._counter}", type=node_type,
                       label=label, detail=detail, parent_id=parent_id)
        self._tree.nodes[node.id] = node
        self._tree.nodes[parent_id].children_ids.append(node.id)
        return node

    def mark_done(self, node_id: str, detail: str = "", timing_ms: int = 0):
        node = self._tree.nodes[node_id]
        node.status = "done"
        node.detail = detail or node.detail
        node.timing_ms = timing_ms

    def mark_error(self, node_id: str, error: str):
        node = self._tree.nodes[node_id]
        node.status = "error"
        node.detail = error

    def to_frontend(self) -> dict:
        """序列化为前端渲染结构"""
        return {
            "rootId": self._tree.root_id,
            "nodes": {
                nid: {
                    "id": n.id, "type": n.type.value,
                    "label": n.label, "detail": n.detail,
                    "status": n.status, "parentId": n.parent_id,
                    "childrenIds": n.children_ids, "timingMs": n.timing_ms,
                }
                for nid, n in self._tree.nodes.items()
            }
        }
```

**前端交互规则**:
- 推理进行中：当前节点显示为 `running` 状态，带脉冲动画
- 已完成节点：可点击展开详情面板，展示中间结果
- 错误节点：红色高亮，展示错误信息，提供"重试"按钮
- 回溯操作：点击任意已完成节点的"回溯"按钮，从该节点重新开始推理，裁剪后续子树

### 3.11 角色视图差异化渲染

> **对应需求**: FR-1103 (基于角色的视图)
> **关联模块**: [ontology/DESIGN.md](../../03-modules/ontology/DESIGN.md)

| 角色 | 默认视图 | 核心关注 | 可执行操作 | 布局差异 |
|------|---------|---------|-----------|---------|
| **Commander** | 态势总览 | 全局态势、决策结论 | 发起指令、审批方案 | 图谱全屏优先，问答侧栏可折叠 |
| **Analyst** | 分析面板 | 实体细节、数据证据 | 查询挖掘、标注关联 | 图谱+问答并排，强调实体属性面板 |
| **Operator** | 任务看板 | 待执行技能、任务队列 | 执行任务、汇报结果 | 右侧 Skill 面板常驻，其余可折叠 |

```typescript
type RoleView = 'commander' | 'analyst' | 'operator'

interface RoleViewConfig {
  defaultLayout: 'overview' | 'analysis' | 'taskboard'
  graphPanel: { visible: boolean; zoom: number; expanded: boolean }
  chatPanel: { visible: boolean; expanded: boolean }
  suggestionPanel: { visible: boolean; expanded: boolean }
  entityPanel: { visible: boolean }
}

const ROLE_VIEW_CONFIGS: Record<RoleView, RoleViewConfig> = {
  commander: {
    defaultLayout: 'overview',
    graphPanel:  { visible: true,  zoom: 0.6, expanded: true },
    chatPanel:   { visible: true,  expanded: false },   // 可折叠侧栏
    suggestionPanel: { visible: true, expanded: true },
    entityPanel: { visible: false },
  },
  analyst: {
    defaultLayout: 'analysis',
    graphPanel:  { visible: true,  zoom: 0.8, expanded: true },
    chatPanel:   { visible: true,  expanded: true },
    suggestionPanel: { visible: true, expanded: false },
    entityPanel: { visible: true },                    // 实体属性面板常驻
  },
  operator: {
    defaultLayout: 'taskboard',
    graphPanel:  { visible: true,  zoom: 0.5, expanded: false },
    chatPanel:   { visible: true,  expanded: false },
    suggestionPanel: { visible: true, expanded: true },  // Skill面板常驻
    entityPanel: { visible: false },
  },
}

const RoleAwareLayout: React.FC<{ role: RoleView; children: React.ReactNode }> = ({ role, children }) => {
  const config = ROLE_VIEW_CONFIGS[role]
  const [panels, setPanels] = useState(config)

  // 角色变更时平滑过渡布局
  useEffect(() => {
    setPanels(config)
  }, [role])

  return (
    <Layout className={`role-view role-${role}`}>
      {panels.graphPanel.visible && (
        <Panel key="graph" expanded={panels.graphPanel.expanded}
          onToggle={() => setPanels(p => ({...p, graphPanel: {...p.graphPanel, expanded: !p.graphPanel.expanded}}))}>
          <GraphView zoom={panels.graphPanel.zoom} />
        </Panel>
      )}
      {panels.chatPanel.visible && (
        <Panel key="chat" expanded={panels.chatPanel.expanded}
          onToggle={() => setPanels(p => ({...p, chatPanel: {...p.chatPanel, expanded: !p.chatPanel.expanded}}))}>
          <ChatArea />
        </Panel>
      )}
      {panels.suggestionPanel.visible && (
        <Panel key="suggestions" expanded={panels.suggestionPanel.expanded}>
          <SuggestionPanel />
        </Panel>
      )}
      {panels.entityPanel.visible && (
        <EntityDetailPanel />
      )}
    </Layout>
  )
}
```

---

## Phase 4: Skill执行深入设计

### 4.1 Skill建议生成机制

```python
# odap/skill_engine/suggestion.py

class SkillSuggester:
    """基于问答上下文和意图,推荐相关的Skills"""

    def __init__(self, skill_registry: dict):
        self.registry = skill_registry

    def generate_suggestions(
        self,
        intent: IntentType,
        linked_entities: list[dict],
        user_query: str,
        available_skills: list[dict]
    ) -> list[dict]:
        """生成Skill执行建议"""

        suggestions = []

        for skill in available_skills:
            score = self._score_skill_relevance(skill, intent, linked_entities, user_query)

            if score > 0.5:
                suggestions.append({
                    "skill_id": skill["id"],
                    "skill_name": skill["name"],
                    "description": skill["description"],
                    "category": skill["category"],
                    "confidence": score,
                    "recommended_params": self._infer_default_params(
                        skill, linked_entities
                    ),
                    "reason": self._build_reason(score, intent, skill)
                })

        return sorted(suggestions, key=lambda x: x["confidence"], reverse=True)

    def _score_skill_relevance(
        self,
        skill: dict,
        intent: IntentType,
        entities: list[dict],
        query: str
    ) -> float:
        """基于多维度打分"""
        score = 0.0

        # 1. 意图匹配: ACTION_EXECUTION意图下所有skill得分+0.3
        if intent == IntentType.ACTION_EXECUTION:
            score += 0.3

        # 2. 实体类型匹配: skill支持的输入类型 vs 当前实体类型
        required_types = skill.get("required_entity_types", [])
        matched_entities = [
            e for e in entities
            if not required_types or e.get("type") in required_types
        ]
        if matched_entities:
            score += 0.3 * min(1.0, len(matched_entities) / len(entities)) if entities else 0

        # 3. 关键词匹配: skill描述中包含query关键词
        query_keywords = set(query.lower().split())
        skill_keywords = set(skill["description"].lower().split())
        overlap = query_keywords & skill_keywords
        if overlap:
            score += 0.2 * min(1.0, len(overlap) / len(query_keywords))

        # 4. 决策建议意图: 分析类skill得分+0.2
        if intent == IntentType.DECISION_SUPPORT and skill["category"] in ["analysis", "intelligence"]:
            score += 0.2

        return min(1.0, score)

    def _infer_default_params(self, skill: dict, entities: list[dict]) -> dict:
        """推断Skill的默认参数: 自动填充当前实体ID"""
        params = {}
        input_schema = skill.get("input_schema", {})

        for param_name, param_def in input_schema.get("properties", {}).items():
            param_type = param_def.get("type", "")
            # 自动填充entity_id型参数
            if param_type == "string" and "entity" in param_def.get("format", ""):
                matching = [e for e in entities if e.get("type") in param_def.get("entity_types", [])]
                if matching:
                    params[param_name] = matching[0]["id"]

        return params

    def _build_reason(self, score: float, intent: IntentType, skill: dict) -> str:
        if score > 0.8: return f"高度相关: 基于当前{intent}意图,建议{sdkill['name']}"
        if score > 0.6: return f"相关: {skill['category']}类skill可辅助当前任务"
        return "可能相关"
```

### 4.2 OPA权限校验完整流程

```python
# odap/skill_engine/opa_gateway.py

import opa_client

class OPASkillGateway:
    """OPA Skill执行权限网关 - 高危技能强制执行OPA校验"""

    def __init__(self, opa_url: str):
        self.opa = opa_client.OPAClient(opa_url)

    async def check_permission(
        self,
        skill_id: str,
        skill_category: str,
        danger_level: str,
        user_input_params: dict,
        workspace_id: str,
        user_role: str
    ) -> dict:
        """
        执行前OPA校验
        返回: {allowed: bool, denied_reasons: list[str], warnings: list[str]}
        """

        # 构造OPA查询
        input_data = {
            "skill": {
                "id": skill_id,
                "category": skill_category,
                "danger_level": danger_level
            },
            "params": user_input_params,
            "context": {
                "workspace_id": workspace_id,
                "user_role": user_role,
                "timestamp": datetime.now().isoformat()
            }
        }

        # 调用OPA
        result = await self.opa.evaluate(
            package="odap.skill",
            rule="allow_skill_execution",
            input=input_data
        )

        # 高危技能的额外检查
        if danger_level in ("critical", "high"):
            audit_result = await self.opa.evaluate(
                package="odap.skill",
                rule="audit_skill_execution",
                input=input_data
            )
            result.extend(audit_result)

        return self._parse_opa_result(result)

    def _parse_opa_result(self, raw: dict) -> dict:
        """解析OPA返回结果"""
        decisions = raw.get("result", {}).get("decisions", [])

        allowed = all(d.get("allowed", False) for d in decisions)
        denied = [d for d in decisions if not d.get("allowed", False)]
        warnings = [d for d in decisions if d.get("warning")]

        return {
            "allowed": allowed,
            "denied_reasons": [d.get("reason", "") for d in denied],
            "warnings": [d.get("warning", "") for d in warnings],
            "denied_details": denied
        }

    async def report_execution_result(
        self,
        skill_id: str,
        execution_result: dict,
        workspace_id: str
    ):
        """报告执行结果给OPA,用于策略更新"""
        await self.opa.send_data({
            "event_type": "skill_executed",
            "skill_id": skill_id,
            "result": execution_result,
            "workspace_id": workspace_id,
            "timestamp": datetime.now().isoformat()
        })
```

### 4.3 Skill执行引擎

```python
# odap/skill_engine/executor.py

import asyncio
from typing import Optional

class SkillExecutionEngine:
    """Skill执行引擎 - 支持同步/异步、单个/批量执行"""

    def __init__(
        self,
        skill_registry: SkillRegistry,
        opa_gateway: OPASkillGateway,
        auditor: AuditLogger
    ):
        self.registry = skill_registry
        self.opa = opa_gateway
        self.auditor = auditor

    async def execute(
        self,
        skill_id: str,
        params: dict,
        workspace_id: str,
        user_id: str,
        user_role: str,
        execute_immediately: bool = False
    ) -> SkillExecutionResult:
        """
        执行一个Skill
        - 获取Skill元数据
        - OPA权限校验
        - 执行Skill
        - 审计记录
        - 结果返回
        """

        # 获取Skill元数据
        skill = self.registry.get(skill_id)
        if not skill:
            raise SkillNotFoundError(f"Skill '{skill_id}' 未注册")

        # OPA校验
        opa_result = await self.opa.check_permission(
            skill_id=skill_id,
            skill_category=skill.category,
            danger_level=skill.danger_level,
            user_input_params=params,
            workspace_id=workspace_id,
            user_role=user_role
        )

        if not opa_result["allowed"]:
            return SkillExecutionResult(
                success=False,
                denied=True,
                reasons=opa_result["denied_reasons"]
            )

        # 审计: 执行前记录
        audit_id = await self.auditor.log(
            event="skill_execution_start",
            skill_id=skill_id,
            workspace_id=workspace_id,
            user_id=user_id,
            params=params
        )

        try:
            # 执行Skill
            start_time = time.time()
            result = await skill.execute(**params)
            elapsed = time.time() - start_time

            # 审计: 执行后记录
            await self.auditor.log(
                event="skill_execution_complete",
                audit_id=audit_id,
                elapsed_ms=elapsed * 1000,
                success=True
            )

            # 通知OPA (用于策略优化)
            await self.opa.report_execution_result(skill_id, {"success": True, "elapsed": elapsed}, workspace_id)

            return SkillExecutionResult(
                success=True,
                result=result,
                elapsed_ms=elapsed * 1000,
                audit_id=audit_id
            )

        except Exception as e:
            error_trace = traceback.format_exc()
            await self.auditor.log_anomaly(
                audit_id=audit_id,
                error=str(e),
                traceback=error_trace
            )

            return SkillExecutionResult(
                success=False,
                error=str(e),
                audit_id=audit_id
            )
```

### 4.4 Skill新增后自动生效流程

```
前端创建/编辑Skill
     │
     ▼ POST /api/v1/skills/create 或 PUT /api/v1/skills/{id}
     │
┌─────────────────────────────────────────────────────────────────┐
│  Skill Registry Backend                                           │
│  1. 验证Skill格式与完整性                                         │
│  2. 写入文件系统 (skills/{category}/{name}.md)                    │
│  3. 生成/更新Skill元数据DB记录                                    │
│  4. 自动同步到OpenHarness                                         │
│  5. 新增 → 自动启用 (enable=true)                                 │
│  6. 推送 WebSocket 通知所有客户端                                 │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  OpenHarness Skill Bridge                                         │
│  - 扫描skills目录,发现变更                                        │
│  - 调用 SkillRegistry.register(new_skill)                         │
│  - OpenHarness Agent 重新加载 Tool 列表                           │
│  - 立即生效 (不需要重启)                                          │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼ WebSocket → 前端自动刷新
┌──────────────────────────────────────────────────────────────────┐
│  前端 Skill Store 自动更新:                                       │
│  - 问答界面: 可用Skill列表更新 (ChatInput 的 tool_choice 更新)     │
│  - Skill管理界面: 列表刷新                                       │
└──────────────────────────────────────────────────────────────────┘

总耗时: < 3 秒, 用户无感知
```

```python
# Skill创建API - 自动生效核心逻辑

@router.post("/skills/create")
async def create_skill(
    content: str,           # Markdown内容
    category: str,
    workspace_id: str
):
    """创建Skill并自动生效"""

    # 1. 解析Markdown，提取元数据
    metadata = parse_skill_markdown(content)
    skill_id = f"{category}/{metadata['name']}"

    # 2. 写入文件系统
    skill_path = SKILLS_BASE_DIR / category / f"{metadata['name']}.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(content, encoding="utf-8")

    # 3. 自动同步到OpenHarness
    from odap.openharness_bridge import sync_skill_to_openharness
    reg_result = await sync_skill_to_openharness(skill_path)

    # 4. 新增Skill自动启用
    skill_meta = SkillMetadata(
        id=skill_id,
        name=metadata["name"],
        description=metadata["description"],
        category=category,
        version="1.0.0",
        enabled=True,                   # ← 自动启用
        registered_at=datetime.now(timezone.utc),
        openharness_status="active"
    )

    # 5. 推送变更
    await ws_manager.broadcast(
        event="skill:registered",
        data=skill_meta.dict()
    )

    return {
        "skill_id": skill_id,
        "status": "active",
        "auto_synced": True,
        "message": f"Skill '{metadata['name']}' 已创建并自动生效"
    }
```

### 4.5 Skill热重载机制

```python
# odap/skill_engine/hotreload.py

import asyncio
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class SkillFileWatcher(FileSystemEventHandler):
    """文件系统监听器 - 检测skills目录变更并自动热重载"""

    def __init__(self, skill_registry: "SkillRegistry", debounce_seconds: float = 2.0):
        self.registry = skill_registry
        self.debounce = debounce_seconds
        self._pending: dict[str, asyncio.Task] = {}

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".md"):
            return
        self._schedule_reload(event.src_path, "modified")

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".md"):
            return
        self._schedule_reload(event.src_path, "created")

    def on_deleted(self, event):
        if event.is_directory or not event.src_path.endswith(".md"):
            return
        self._schedule_reload(event.src_path, "deleted")

    def _schedule_reload(self, file_path: str, change_type: str):
        """防抖调度: 合并短时间内的多次文件变更"""
        if file_path in self._pending:
            self._pending[file_path].cancel()

        async def delayed_reload():
            await asyncio.sleep(self.debounce)
            await self._reload_skill(file_path, change_type)

        self._pending[file_path] = asyncio.create_task(delayed_reload())

    async def _reload_skill(self, file_path: str, change_type: str):
        """重新加载单个Skill"""
        try:
            skill_path = Path(file_path)
            skill_id = self._path_to_skill_id(skill_path)

            match change_type:
                case "deleted":
                    await self.registry.unregister(skill_id)
                    logger.info(f"Skill已卸载: {skill_id}")
                case "created" | "modified":
                    content = skill_path.read_text(encoding="utf-8")
                    metadata = parse_skill_markdown(content)
                    await self.registry.register_or_update(
                        skill_id=skill_id,
                        metadata=metadata,
                        content=content
                    )
                    logger.info(f"Skill已热重载: {skill_id} ({change_type})")

            # 通知OpenHarness刷新Tool列表
            await sync_skill_to_openharness(skill_path, action=change_type)

            # WebSocket推送变更
            await ws_manager.broadcast("skill:reloaded", {
                "skill_id": skill_id,
                "change_type": change_type,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Skill热重载失败 {file_path}: {e}")

    def _path_to_skill_id(self, path: Path) -> str:
        relative = path.relative_to(SKILLS_BASE_DIR)
        return str(relative.with_suffix("")).replace("\\", "/")

class SkillHotReloadManager:
    """Skill热重载管理器 - 启动文件监听"""

    def __init__(self, registry: "SkillRegistry", skills_dir: Path):
        self.observer = Observer()
        self.watcher = SkillFileWatcher(registry)
        self.skills_dir = skills_dir

    def start(self):
        """启动文件监听"""
        self.observer.schedule(self.watcher, str(self.skills_dir), recursive=True)
        self.observer.start()
        logger.info(f"Skill热重载已启动, 监听目录: {self.skills_dir}")

    def stop(self):
        self.observer.stop()
        self.observer.join()
```

### 4.6 Skill并发控制与限流

```python
# odap/skill_engine/concurrency.py

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field

@dataclass
class RateLimitConfig:
    max_concurrent_per_skill: int = 3      # 单个skill最大并发执行数
    max_concurrent_per_workspace: int = 10  # 单个workspace最大并发
    global_max_concurrent: int = 50         # 全局最大并发
    execution_timeout: float = 300.0        # 单次执行超时(秒)
    cooldown_seconds: float = 1.0           # 同skill最小调用间隔

class SkillConcurrencyController:
    """Skill并发控制器 - 多层限流 + 资源隔离"""

    def __init__(self, config: RateLimitConfig = RateLimitConfig()):
        self.config = config
        self._skill_semaphores: dict[str, asyncio.Semaphore] = {}
        self._workspace_semaphores: dict[str, asyncio.Semaphore] = {}
        self._global_semaphore = asyncio.Semaphore(config.global_max_concurrent)
        self._last_execution: dict[str, float] = defaultdict(float)
        self._active_executions: dict[str, set[str]] = defaultdict(set)

    async def acquire(self, skill_id: str, workspace_id: str) -> bool:
        """申请执行许可 - 多层校验"""
        # 1. 冷却检查
        now = time.time()
        last = self._last_execution.get(skill_id, 0)
        if now - last < self.config.cooldown_seconds:
            return False

        # 2. Skill级别限流
        sem = self._skill_semaphores.setdefault(
            skill_id,
            asyncio.Semaphore(self.config.max_concurrent_per_skill)
        )
        if sem.locked():
            return False

        # 3. Workspace级别限流
        ws_sem = self._workspace_semaphores.setdefault(
            workspace_id,
            asyncio.Semaphore(self.config.max_concurrent_per_workspace)
        )
        if ws_sem.locked():
            return False

        # 4. 全局限流
        if self._global_semaphore.locked():
            return False

        # 全部通过 → 获取所有信号量
        await sem.acquire()
        await ws_sem.acquire()
        await self._global_semaphore.acquire()

        self._last_execution[skill_id] = now
        self._active_executions[workspace_id].add(skill_id)
        return True

    async def release(self, skill_id: str, workspace_id: str):
        """释放执行许可"""
        self._skill_semaphores.get(skill_id)?.release()
        self._workspace_semaphores.get(workspace_id)?.release()
        self._global_semaphore.release()
        self._active_executions[workspace_id].discard(skill_id)

    async def execute_with_control(
        self,
        skill_id: str,
        workspace_id: str,
        execution_fn: callable
    ) -> dict:
        """带并发控制的执行包装器"""
        acquired = await self.acquire(skill_id, workspace_id)
        if not acquired:
            return {
                "success": False,
                "error": "rate_limited",
                "message": "当前Skill/Workspace执行已达上限,请稍后重试"
            }

        try:
            result = await asyncio.wait_for(
                execution_fn(),
                timeout=self.config.execution_timeout
            )
            return {"success": True, "result": result}
        except asyncio.TimeoutError:
            return {"success": False, "error": "timeout", "message": "Skill执行超时"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            await self.release(skill_id, workspace_id)

    def get_status(self, workspace_id: str = None) -> dict:
        """获取当前并发状态"""
        skill_stats = {
            sid: sem._value for sid, sem in self._skill_semaphores.items()
        }
        return {
            "global_available": self._global_semaphore._value,
            "active_skills": skill_stats,
            "workspace_active": list(self._active_executions.get(workspace_id, set()))
                if workspace_id else {}
        }
```

### 4.7 Skill版本化

```python
# odap/skill_engine/versioning.py

import semver
from datetime import datetime, timezone
from typing import Optional

@dataclass
class SkillVersion:
    skill_id: str
    version: str                       # 语义版本 "1.2.0"
    content_hash: str                  # MD内容SHA256
    changelog: str
    created_at: datetime
    created_by: str
    is_active: bool
    activation_reason: str = ""

class SkillVersionManager:
    """Skill版本管理器 - 版本追踪、回滚、AB测试"""

    def __init__(self, db_pool, skills_base_dir: Path):
        self.db = db_pool
        self.base_dir = skills_base_dir

    async def create_version(
        self,
        skill_id: str,
        content: str,
        changelog: str,
        created_by: str,
        auto_activate: bool = True
    ) -> SkillVersion:
        """创建Skill新版本"""
        # 生成内容hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # 获取上一个版本号
        prev = await self._get_latest_version(skill_id)
        new_version = self._bump_version(
            prev.version if prev else "0.1.0",
            changelog
        )

        # 持久化版本
        version = SkillVersion(
            skill_id=skill_id,
            version=new_version,
            content_hash=content_hash,
            changelog=changelog,
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
            is_active=False
        )

        await self.db.execute(
            """INSERT INTO skill_versions (skill_id, version, content_hash, changelog,
               created_at, created_by, is_active)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            version.skill_id, version.version, version.content_hash,
            version.changelog, version.created_at, version.created_by, False
        )

        if auto_activate:
            await self.activate_version(skill_id, new_version, "自动激活新版本")

        return version

    async def activate_version(
        self,
        skill_id: str,
        version: str,
        reason: str = ""
    ) -> bool:
        """激活指定版本 (同时停用其他版本)"""
        # 停用当前活跃版本
        await self.db.execute(
            "UPDATE skill_versions SET is_active = false WHERE skill_id = $1 AND is_active = true",
            skill_id
        )

        # 激活目标版本
        result = await self.db.execute(
            "UPDATE skill_versions SET is_active = true, activation_reason = $3 WHERE skill_id = $1 AND version = $2",
            skill_id, version, reason
        )

        if result == "UPDATE 0":
            raise ValueError(f"版本 {skill_id}@{version} 不存在")

        # 同步到OpenHarness
        await sync_skill_version_to_openharness(skill_id, version)

        # 通知
        await ws_manager.broadcast("skill:version_activated", {
            "skill_id": skill_id,
            "version": version,
            "reason": reason
        })

        return True

    async def rollback_version(self, skill_id: str, target_version: str) -> dict:
        """回滚到指定版本"""
        # 获取目标版本内容
        version = await self._get_version(skill_id, target_version)
        if not version:
            raise ValueError(f"版本不存在: {skill_id}@{target_version}")

        # 恢复文件内容
        skill_path = self.base_dir / f"{skill_id}.md"
        old_content = skill_path.read_text(encoding="utf-8")

        # 创建回滚版本 (新版本号, 内容是旧版本的)
        rollback_version = await self.create_version(
            skill_id=skill_id,
            content=old_content,  # 使用target版本的内容
            changelog=f"回滚至版本 {target_version}",
            created_by="system",
            auto_activate=True
        )

        return {
            "status": "rolled_back",
            "skill_id": skill_id,
            "from_version": version.version,
            "to_version": rollback_version.version
        }

    async def list_versions(self, skill_id: str) -> list[dict]:
        """列出某Skill的所有版本历史"""
        rows = await self.db.fetch(
            """SELECT * FROM skill_versions WHERE skill_id = $1
               ORDER BY created_at DESC LIMIT 20""",
            skill_id
        )
        return [
            {
                "version": r["version"],
                "changelog": r["changelog"],
                "is_active": r["is_active"],
                "created_at": r["created_at"].isoformat(),
                "created_by": r["created_by"],
                "content_hash": r["content_hash"][:12]
            }
            for r in rows
        ]

    def _bump_version(self, current: str, changelog: str) -> str:
        """根据changelog内容决定版本递增策略"""
        v = semver.VersionInfo.parse(current)

        breaking_keywords = ["breaking", "不兼容", "重构"]
        feature_keywords = ["新增", "add", "feature", "支持"]

        if any(kw in changelog.lower() for kw in breaking_keywords):
            return str(v.bump_major())
        if any(kw in changelog.lower() for kw in feature_keywords):
            return str(v.bump_minor())
        return str(v.bump_patch())

    async def _get_latest_version(self, skill_id: str) -> Optional[SkillVersion]:
        row = await self.db.fetchrow(
            "SELECT * FROM skill_versions WHERE skill_id = $1 ORDER BY created_at DESC LIMIT 1",
            skill_id
        )
        return self._row_to_version(row) if row else None

    async def _get_version(self, skill_id: str, version: str) -> Optional[SkillVersion]:
        row = await self.db.fetchrow(
            "SELECT * FROM skill_versions WHERE skill_id = $1 AND version = $2",
            skill_id, version
        )
        return self._row_to_version(row) if row else None

    def _row_to_version(self, row) -> SkillVersion:
        return SkillVersion(
            skill_id=row["skill_id"],
            version=row["version"],
            content_hash=row["content_hash"],
            changelog=row["changelog"],
            created_at=row["created_at"],
            created_by=row["created_by"],
            is_active=row["is_active"],
            activation_reason=row.get("activation_reason", "")
        )
```

---

## Phase 5: 闭环反馈深入设计

### 5.1 反馈收集完整机制

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          闭环反馈收集体系                                    │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Feed 1: 用户评分          Feed 2: Skill结果         Feed 3: 手动修正      │
│   ┌───────────────┐       ┌───────────────┐       ┌───────────────┐       │
│   │ 消息气泡 👍/👎  │       │ Skill执行完成   │       │ 图谱编辑面板   │       │
│   │ optional: 匿名  │       │ 自动采集:       │       │ 用户修改:      │       │
│   │  补充书面反馈  │       │ 成功/失败/输出   │       │ 重命名/改属性   │       │
│   │               │       │ 耗时/token用量   │       │ 添加/删除关系   │       │
│   └───────┬───────┘       └───────┬───────┘       └───────┬───────┘       │
│           │                       │                       │               │
│           └───────────────────────┼───────────────────────┘               │
│                                   ▼                                       │
│                          ┌─────────────────┐                             │
│                          │ Feedback Engine  │                             │
│                          │ 反馈引擎          │                             │
│                          └────────┬─────────┘                            │
│                                   │                                      │
│        ┌──────────────────────────┼──────────────────────────────┐       │
│        ▼                          ▼                              ▼       │
│  ┌───────────┐           ┌───────────────┐             ┌───────────────┐  │
│  │Prompt优化  │           │ 本体增量更新   │             │ Skill增强     │  │
│  │模板调优     │          │ Graphiti       │             │ 参数优化/新增  │  │
│  │RAG质量改进  │          │ 实体/关系修正   │             │ 版本迭代       │  │
│  └───────────┘           └───────────────┘             └───────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 5.2 反馈引擎核心

```python
# odap/feedback/engine.py

class FeedbackEngine:
    """闭环反馈引擎 - 收集+分析+利用反馈"""

    def __init__(self, graphiti_client, skill_registry, prompt_manager):
        self.graphiti = graphiti_client
        self.skills = skill_registry
        self.prompts = prompt_manager

    async def process_event(self, event: FeedbackEvent):
        """处理反馈事件 - 路由到对应处理器"""
        match event.event_type:
            case "qa_rating":
                await self._handle_qa_rating(event)
            case "skill_result":
                await self._handle_skill_result(event)
            case "manual_entity_edit":
                await self._handle_entity_edit(event)
            case "manual_relation_edit":
                await self._handle_relation_edit(event)
            case "session_summary":
                await self._handle_session_summary(event)
            case "prompt_version_update":
                await self._handle_prompt_update(event)

    async def _handle_qa_rating(self, event: FeedbackEvent):
        """处理问答评分反馈"""
        data = event.data
        rating = data.get("rating")         # 1↗ 或 -1↘
        reason = data.get("reason", "")     # 可选的书面反馈
        message_id = data.get("message_id")

        # 记录评分
        await self._store_feedback({
            "type": "qa_rating",
            "message_id": message_id,
            "rating": rating,
            "reason": reason,
            "timestamp": datetime.now()
        })

        # 如果是负面评分 → 标记为问题案例供人工审查
        if rating == -1:
            await self._flag_problematic_answer(
                message_id=message_id,
                reason=reason
            )

        # 累积评分用于batch优化班长人prompt模板
        recent_stats = await self._get_recent_rating_stats(hours=24)
        if recent_stats["negative_rate"] > 0.3:
            await self._trigger_prompt_optimization(recent_stats)

    async def _handle_skill_result(self, event: FeedbackEvent):
        """处理Skill执行结果反馈"""
        data = event.data
        skill_id = data["skill_id"]
        result = data["result"]
        success = data["success"]

        # 1. 记录Skill执行统计
        self._record_skill_analytics(skill_id, success, result)

        # 2. 如果Skill产生了副作用 → 更新本体
        if result.get("affected_entities"):
            for entity_id, changes in result["affected_entities"].items():
                await self.graphiti.update_entity(
                    entity_id=entity_id,
                    properties=changes,
                    transaction_time=datetime.now(timezone.utc)
                )
                logger.info(f"本体更新: entity={entity_id}, changes={changes}")

        # 3. 如果Skill失败 → 记录为技能改进信号
        if not success:
            await self._flag_skill_improvement_needed(skill_id, result.get("error", ""))

    async def _handle_entity_edit(self, event: FeedbackEvent):
        """用户手动修正实体 → 增量更新Graphiti"""
        data = event.data
        entity_id = data["entity_id"]
        changes = data["changes"]

        # 直接应用到Graphiti
        await self.graphiti.update_entity(
            entity_id=entity_id,
            properties=changes.get("properties", {}),
            name=changes.get("name"),
            transaction_time=datetime.now(timezone.utc)
        )

        # 增量记录 (不创建完整版本 - 手动编辑粒度小)
        await self._log_incremental_change("entity_edit", entity_id, changes)

    async def _handle_relation_edit(self, event: FeedbackEvent):
        """用户手动修正关系"""
        data = event.data
        if data.get("action") == "add":
            await self.graphiti.add_relationship_edge(
                source_uuid=data["source_id"],
                target_uuid=data["target_id"],
                relationship_type=data["type"],
                created_at=datetime.now()
            )
        elif data.get("action") == "delete":
            await self.graphiti.delete_relationship(data["edge_id"])

    async def _handle_session_summary(self, event: FeedbackEvent):
        """会话摘要: 提取关键洞察供下次会话参考"""
        data = event.data
        # 1. 提取此次会话的决策动点
        decisions = data.get("decisions", [])

        # 2. 提取涉及的实体变更
        entity_changes = data.get("entity_changes", [])

        # 3. 保存为本体上下文 + 审计记录
        await self._store_session_insights(
            session_id=data["session_id"],
            workspace_id=data["workspace_id"],
            decisions=decisions,
            entity_changes=entity_changes
        )

    async def _handle_prompt_update(self, event: FeedbackEvent):
        """提示词模板版本更新"""
        version_id = event.data["version_id"]
        # 使新旧回答质量指标进入对比阶段
        # Phase 5 产出: 标注本版本的改善信号
        await self.prompts.activate_version(version_id)
        await self._record_prompt_version_change(version_id)
```

### 5.3 本体增量更新

```python
# odap/feedback/incremental_update.py

class IncrementalOntologyUpdater:
    """本体增量更新器 - 小步快跑，避免全量重建"""

    def __init__(self, graphiti_client):
        self.graphiti = graphiti_client
        self.pending_updates: list[dict] = []

    async def queue_update(self, workspace_id: str, change_type: str, target_id: str, changes: dict):
        """将更新放入队列,批量执行"""
        self.pending_updates.append({
            "workspace_id": workspace_id,
            "change_type": change_type,
            "target_id": target_id,
            "changes": changes
        })

    async def flush(self, batch_size: int = 50):
        """批量刷更新到Graphiti"""
        batch = self.pending_updates[:batch_size]

        for update in batch:
            match update["change_type"]:
                case "entity_property_update":
                    await self.graphiti.update_entity(
                        entity_id=update["target_id"],
                        properties=update["changes"]["properties"],
                        transaction_time=datetime.now(timezone.utc)
                    )
                case "entity_status_update":
                    # 例如: Skill执行后 Target.status = "destroyed"
                    await self.graphiti.update_entity(
                        entity_id=update["target_id"],
                        properties={"status": update["changes"]["status"]},
                        valid_time=update["changes"].get("valid_time"),
                        transaction_time=datetime.now(timezone.utc)
                    )
                case "entity_delete":
                    await self.graphiti.delete_entity(update["target_id"])
                case "relation_delete":
                    await self.graphiti.delete_relationship(update["target_id"])
                case "relation_add":
                    await self.graphiti.add_relationship_edge(
                        source_uuid=update["changes"]["source_id"],
                        target_uuid=update["changes"]["target_id"],
                        relationship_type=update["changes"]["type"],
                        created_at=datetime.now()
                    )

        self.pending_updates = self.pending_updates[batch_size:]

    # 定时执行: 每30秒批量刷
    async def start_periodic_flush(self):
        while True:
            await asyncio.sleep(30)
            await self.flush()
```

### 5.4 审计日志记录

```python
# odap/feedback/audit.py

class AuditLogger:
    """审计日志 - 全链路可追踪"""

    async def log(self, event: str, **kwargs) -> str:
        entry = {
            "id": str(uuid4()),
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs
        }
        await self._write_to_db(entry)
        return entry["id"]

    async def log_chain(self, events: list[dict]) -> list[str]:
        """批量日志: 为Phase 5的闭环反馈提供完整时序"""
        ids = []
        for e in events:
            eid = await self.log(**e)
            ids.append(eid)
        return ids

    async def query(
        self,
        workspace_id: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> list[dict]:
        """审计查询 - 支持按workspace/事件类型/时间过滤"""
        filters = {
            k: v for k, v in
            {"workspace_id": workspace_id, "event": event_type}.items()
            if v is not None
        }
        return await self._query_db(filters, since, limit)
```

### 5.5 前端反馈交互

```typescript
// 消息气泡内评分按钮
const MessageRating: React.FC<{ messageId: string }> = ({ messageId }) => {
  const [rating, setRating] = useState<1 | -1 | null>(null)

  const handleRate = async (r: 1 | -1) => {
    setRating(r)
    await FeedbackAPI.submitRating({
      message_id: messageId,
      rating: r,
      workspace_id: currentWorkspaceId
    })
    // Toast提示
    message.info('已记录反馈，感谢！')
  }

  return (
    <div className="message-rating" style={{ marginTop: 4 }}>
      <Button
        size="small"
        type={rating === 1 ? 'primary' : 'text'}
        icon={<LikeOutlined />}
        onClick={() => handleRate(1)}
        disabled={rating !== null}
      />
      <Button
        size="small"
        type={rating === -1 ? 'primary' : 'text'}
        icon={<DislikeOutlined />}
        onClick={() => handleRate(-1)}
        disabled={rating !== null}
        style={{ marginLeft: 8 }}
      />
    </div>
  )
}

// 执行反馈收集Hook
const useSkillResultFeedback = () => {
  const submitSkillResult = useMutation({
    mutationFn: (data: SkillResultFeedback) =>
      FeedbackAPI.submitSkillResult(data),
    onSuccess: () => {
      eventBus.emit('feedback:skill:recorded')
    }
  })

  const handleSkillComplete = useCallback((
    skillId: string,
    result: SkillExecutionResult,
    workspaceId: string
  ) => {
    // 自动反馈: 无需用户操作
    submitSkillResult.mutate({
      skill_id: skillId,
      success: result.success,
      result: result.result ?? {},
      workspace_id: workspaceId,
      elapsed_ms: result.elapsed_ms ?? 0
    })
  }, [submitSkillResult])

  return { handleSkillComplete }
}
```

### 5.6 全链路闭环验证

```python
# odap/feedback/validation.py

class FeedbackLoopValidator:
    """验证闭环反馈是否生效 - 定期检查"""

    async def validate_loop_health(self, workspace_id: str) -> dict:
        """检查闭环各环节的健康状况"""

        checks = {}

        # 1. 检查: 最近的Skill执行是否成功见效到本体
        recent_skills = await self.auditor.query(
            workspace_id=workspace_id,
            event_type="skill_execution_complete",
            since=datetime.now() - timedelta(hours=24)
        )
        checks["skill_execution_count"] = len(recent_skills)

        # 2. 检查: 本体增量更新是否正常执行
        ontology_changes = await self.graphiti.get_changes_since(
            workspace_id=workspace_id,
            since=datetime.now() - timedelta(hours=24)
        )
        checks["ontology_change_count"] = len(ontology_changes)

        # 3. 检查: 是否有卡住的更新
        stuck_updates = self.incremental_updater.pending_updates_count
        checks["pending_updates"] = stuck_updates
        checks["is_healthy"] = stuck_updates < 100  # 小于100表示正常，否则需排查

        return checks
```

### 5.7 A/B测试框架 (Prompt优化)

```python
# odap/feedback/ab_testing.py

from typing import Optional

@dataclass
class ABTestConfig:
    test_id: str
    variant_a_id: str           # 对照组 prompt版本ID
    variant_b_id: str           # 实验组 prompt版本ID
    start_time: datetime
    end_time: Optional[datetime] = None
    traffic_split: float = 0.5  # B组流量比例 (0.5=50%)
    min_sample_size: int = 50   # 最少样本数才能得出结论

@dataclass
class ABTestResult:
    test_id: str
    variant_a: dict             # {rating_avg, success_rate, ...}
    variant_b: dict             # {rating_avg, success_rate, ...}
    is_significant: bool        # 统计显著性是否成立
    winner: Optional[str]       # "a" | "b" | None
    confidence_level: float     # 置信度 0.95

class ABTestEngine:
    """A/B测试框架 - 系统化评估Prompt模板变更的影响"""

    def __init__(self, redis_client, db_pool, feedback_engine: "FeedbackEngine"):
        self.redis = redis_client
        self.db = db_pool
        self.feedback = feedback_engine

    async def create_test(
        self,
        variant_a_prompt_id: str,
        variant_b_prompt_id: str,
        workspace_id: str,
        traffic_split: float = 0.5,
        min_sample_size: int = 50
    ) -> ABTestConfig:
        """创建A/B测试"""
        test_id = str(uuid4())

        config = ABTestConfig(
            test_id=test_id,
            variant_a_id=variant_a_prompt_id,
            variant_b_id=variant_b_prompt_id,
            start_time=datetime.now(timezone.utc),
            traffic_split=traffic_split,
            min_sample_size=min_sample_size
        )

        await self.redis.hset(f"ab_test:{test_id}", mapping={
            "variant_a_id": variant_a_prompt_id,
            "variant_b_id": variant_b_prompt_id,
            "workspace_id": workspace_id,
            "traffic_split": str(traffic_split),
            "min_sample_size": str(min_sample_size),
            "status": "running",
            "started_at": datetime.now().isoformat()
        })

        return config

    def assign_variant(self, test_id: str, session_id: str) -> str:
        """基于session_id的一致性哈希分配variant (确保同一会话固定分配到同一组)"""
        config = self._get_test_config(test_id)
        if not config:
            return "a"  # 默认对照组

        hash_val = int(hashlib.md5(session_id.encode()).hexdigest(), 16)
        bucket = hash_val % 100 / 100.0
        variant = "b" if bucket < config["traffic_split"] else "a"

        # 记录分配
        self.redis.hset(f"ab_test:{test_id}:assignments", session_id, variant)
        return variant

    async def record_metric(
        self,
        test_id: str,
        session_id: str,
        metric_name: str,
        value: float
    ):
        """记录测试指标"""
        variant = await self.redis.hget(
            f"ab_test:{test_id}:assignments", session_id
        )
        if not variant:
            return

        key = f"ab_test:{test_id}:metrics:{variant.decode()}:{metric_name}"
        await self.redis.rpush(key, str(value))

    async def evaluate_test(self, test_id: str) -> ABTestResult:
        """评估A/B测试结果 - 统计分析"""
        config = self._get_test_config(test_id)
        if not config:
            raise ValueError("测试不存在")

        # 收集各组指标
        metrics_a = await self._get_variant_metrics(test_id, "a")
        metrics_b = await self._get_variant_metrics(test_id, "b")

        variant_a_stats = self._calculate_stats(metrics_a)
        variant_b_stats = self._calculate_stats(metrics_b)

        # Welch's t-test (不等方差)
        t_stat, p_value = self._welch_ttest(
            metrics_a.get("qa_rating", []),
            metrics_b.get("qa_rating", [])
        )

        is_significant = p_value < 0.05 and \
            len(metrics_a.get("qa_rating", [])) >= config["min_sample_size"] and \
            len(metrics_b.get("qa_rating", [])) >= config["min_sample_size"]

        # 确定胜出者
        winner = None
        if is_significant:
            if variant_b_stats.get("rating_avg", 0) > variant_a_stats.get("rating_avg", 0):
                winner = "b"
            else:
                winner = "a"

        return ABTestResult(
            test_id=test_id,
            variant_a=variant_a_stats,
            variant_b=variant_b_stats,
            is_significant=is_significant,
            winner=winner,
            confidence_level=round(1 - p_value, 4)
        )

    async def auto_apply_winner(self, test_id: str) -> dict:
        """自动应用胜出variant (当统计显著时)"""
        result = await self.evaluate_test(test_id)

        if not result.is_significant or not result.winner:
            return {"status": "inconclusive", "message": "测试结果不显著, 继续收集数据"}

        winner_variant_id = (
            self._get_test_config(test_id)["variant_b_id"]
            if result.winner == "b"
            else self._get_test_config(test_id)["variant_a_id"]
        )

        await self.feedback.prompts.activate_version(winner_variant_id)

        await self.redis.hset(f"ab_test:{test_id}", "status", "completed")
        await self.redis.hset(f"ab_test:{test_id}", "winner", result.winner)

        return {
            "status": "applied",
            "winner": f"variant_{result.winner}",
            "activated_prompt_id": winner_variant_id
        }

    def _get_test_config(self, test_id: str) -> Optional[dict]:
        data = self.redis.hgetall(f"ab_test:{test_id}")
        return {
            k.decode(): float(v) if k == b"traffic_split" or k == b"min_sample_size" else v.decode()
            for k, v in data.items()
        } if data else None

    async def _get_variant_metrics(self, test_id: str, variant: str) -> dict:
        """获取某variant的所有指标"""
        metrics = {}
        pattern = f"ab_test:{test_id}:metrics:{variant}:*"
        # 使用Redis SCAN获取所有匹配的key
        keys = await self.redis.keys(pattern)
        for key in keys:
            metric_name = key.decode().split(":")[-1]
            values = await self.redis.lrange(key.decode(), 0, -1)
            metrics[metric_name] = [float(v) for v in values]
        return metrics

    def _calculate_stats(self, metrics: dict) -> dict:
        """计算指标统计"""
        stats = {}
        for name, values in metrics.items():
            if not values:
                continue
            stats[f"{name}_avg"] = sum(values) / len(values)
            stats[f"{name}_count"] = len(values)
            stats[f"{name}_std"] = (
                (sum((v - stats[f"{name}_avg"]) ** 2 for v in values) / len(values)) ** 0.5
            ) if len(values) > 1 else 0
        return stats

    def _welch_ttest(self, sample_a: list[float], sample_b: list[float]) -> tuple[float, float]:
        """Welch's t-test (返回 t_statistic, p_value)"""
        import scipy.stats as stats
        if len(sample_a) < 3 or len(sample_b) < 3:
            return 0, 1.0
        t_stat, p_value = stats.ttest_ind(sample_a, sample_b, equal_var=False)
        return float(t_stat), float(p_value)
```

### 5.8 反馈分析聚合引擎

```python
# odap/feedback/aggregation.py

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

class FeedbackAggregationEngine:
    """反馈聚合分析 - 从个体反馈中提取模式、趋势、洞察"""

    # 分析维度
    ANALYSIS_WINDOWS = {
        "hourly": timedelta(hours=1),
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1)
    }

    def __init__(self, db_pool, redis_client):
        self.db = db_pool
        self.redis = redis_client

    async def get_dashboard_metrics(self, workspace_id: str) -> dict:
        """获取反馈仪表盘的核心指标"""
        now = datetime.now(timezone.utc)

        return {
            "qa_quality": await self._qa_quality_metrics(workspace_id, now),
            "skill_performance": await self._skill_performance_metrics(workspace_id, now),
            "ontology_health": await self._ontology_health_metrics(workspace_id, now),
            "user_engagement": await self._user_engagement_metrics(workspace_id, now),
            "anomaly_alerts": await self._get_active_alerts(workspace_id)
        }

    async def _qa_quality_metrics(self, workspace_id: str, now: datetime) -> dict:
        """问答质量指标"""
        daily_since = now - self.ANALYSIS_WINDOWS["daily"]
        weekly_since = now - self.ANALYSIS_WINDOWS["weekly"]

        daily = await self.db.fetch("""
            SELECT
                COUNT(*) as total_messages,
                AVG(CASE WHEN rating = 1 THEN 1.0 WHEN rating = -1 THEN 0.0 ELSE NULL END) as positive_rate,
                COUNT(CASE WHEN rating = -1 THEN 1 END) as negative_count,
                AVG(confidence) as avg_confidence
            FROM qa_feedback
            WHERE workspace_id = $1 AND created_at >= $2
        """, workspace_id, daily_since)

        weekly = await self.db.fetch("""
            SELECT
                AVG(CASE WHEN rating = 1 THEN 1.0 WHEN rating = -1 THEN 0.0 ELSE NULL END) as positive_rate,
                COUNT(*) as total
            FROM qa_feedback
            WHERE workspace_id = $1 AND created_at >= $2
        """, workspace_id, weekly_since)

        return {
            "daily": {
                "total": daily[0]["total_messages"] if daily else 0,
                "positive_rate": round((daily[0]["positive_rate"] or 0) * 100, 1),
                "negative_count": daily[0]["negative_count"] or 0,
                "avg_confidence": round((daily[0]["avg_confidence"] or 0) * 100, 1)
            },
            "weekly_trend": round((weekly[0]["positive_rate"] or 0) * 100, 1)
        }

    async def _skill_performance_metrics(self, workspace_id: str, now: datetime) -> dict:
        """Skill执行效果指标"""
        daily_since = now - self.ANALYSIS_WINDOWS["daily"]

        rows = await self.db.fetch("""
            SELECT
                COUNT(*) as total_executions,
                COUNT(CASE WHEN success = true THEN 1 END) as success_count,
                AVG(elapsed_ms) as avg_elapsed,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY elapsed_ms) as p95_elapsed
            FROM skill_feedback
            WHERE workspace_id = $1 AND created_at >= $2
        """, workspace_id, daily_since)

        row = rows[0] if rows else {}
        total = row.get("total_executions", 0)

        return {
            "daily_total": total,
            "success_rate": round(row.get("success_count", 0) / total * 100, 1) if total > 0 else 0,
            "avg_latency_ms": round(row.get("avg_elapsed", 0)),
            "p95_latency_ms": round(row.get("p95_elapsed", 0))
        }

    async def _ontology_health_metrics(self, workspace_id: str, now: datetime) -> dict:
        """本体健康度指标"""
        weekly_since = now - self.ANALYSIS_WINDOWS["weekly"]

        rows = await self.db.fetch("""
            SELECT
                COUNT(DISTINCT entity_id) as entities_affected,
                COUNT(*) as total_updates,
                event_type,
                COUNT(CASE WHEN event_type = 'entity_edit' THEN 1 END) as manual_edits,
                COUNT(CASE WHEN event_type = 'skill_side_effect' THEN 1 END) as auto_updates
            FROM ontology_updates
            WHERE workspace_id = $1 AND created_at >= $2
            GROUP BY event_type
        """, workspace_id, weekly_since)

        stats = {"entities_affected": 0, "total_updates": 0, "manual_ratio": 0, "auto_ratio": 0}
        if rows:
            total = sum(r["total_updates"] for r in rows)
            manual = sum(r.get("manual_edits", 0) or 0 for r in rows)
            auto = sum(r.get("auto_updates", 0) or 0 for r in rows)
            stats = {
                "entities_affected": max(r["entities_affected"] for r in rows),
                "total_updates": total,
                "manual_ratio": round(manual / total * 100, 1) if total > 0 else 0,
                "auto_ratio": round(auto / total * 100, 1) if total > 0 else 0
            }

        return stats

    async def _user_engagement_metrics(self, workspace_id: str, now: datetime) -> dict:
        """用户活跃度指标"""
        daily_since = now - self.ANALYSIS_WINDOWS["daily"]

        rows = await self.db.fetch("""
            SELECT
                COUNT(DISTINCT user_id) as active_users,
                COUNT(DISTINCT session_id) as active_sessions
            FROM qa_feedback
            WHERE workspace_id = $1 AND created_at >= $2
        """, workspace_id, daily_since)

        row = rows[0] if rows else {}
        return {
            "daily_active_users": row.get("active_users", 0),
            "daily_active_sessions": row.get("active_sessions", 0)
        }

    async def _get_active_alerts(self, workspace_id: str) -> list[dict]:
        """获取活跃的异常告警"""
        rows = await self.db.fetch("""
            SELECT alert_type, message, severity, detected_at
            FROM anomaly_alerts
            WHERE workspace_id = $1 AND resolved = false
            ORDER BY detected_at DESC LIMIT 10
        """, workspace_id)
        return [dict(r) for r in rows]
```

### 5.9 异常检测系统

```python
# odap/feedback/anomaly_detector.py

class AnomalyDetector:
    """基于统计的异常检测 - 监控关键指标，自动告警"""

    # 阈值配置 (基于3-sigma原则)
    THRESHOLDS = {
        "qa_negative_rate": {"warning": 0.25, "critical": 0.40},        # 差评率
        "skill_failure_rate": {"warning": 0.15, "critical": 0.30},      # Skill失败率
        "response_latency_p50": {"warning": 5.0, "critical": 10.0},     # P50延迟(秒)
        "stale_updates": {"warning": 50, "critical": 200},              # 积压更新数
        "user_dropoff": {"warning": 0.3, "critical": 0.5}               # 用户流失率
    }

    def __init__(self, db_pool, redis_client, notification_service):
        self.db = db_pool
        self.redis = redis_client
        self.notifier = notification_service

    async def detect_hourly(self) -> list[dict]:
        """每小时运行一次, 检测所有工作空间的异常"""
        alerts = []

        workspaces = await self.db.fetch("SELECT id FROM workspaces WHERE active = true")
        for ws in workspaces:
            ws_alerts = await self._check_workspace(ws["id"])
            for alert in ws_alerts:
                await self._store_alert(ws["id"], alert)
            alerts.extend(ws_alerts)

        return alerts

    async def _check_workspace(self, workspace_id: str) -> list[dict]:
        """检查单个工作空间的异常"""
        alerts = []
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=1)

        # 1. QA差评率检查
        qa_stats = await self.db.fetchrow("""
            SELECT
                COUNT(CASE WHEN rating = -1 THEN 1 END)::float / NULLIF(COUNT(*), 0) as negative_rate
            FROM qa_feedback
            WHERE workspace_id = $1 AND created_at >= $2
        """, workspace_id, since)

        if qa_stats and qa_stats["negative_rate"] is not None:
            rate = float(qa_stats["negative_rate"])
            severity = self._assess_severity(rate, "qa_negative_rate")
            if severity:
                alerts.append({
                    "type": "qa_negative_rate",
                    "severity": severity,
                    "current_value": rate,
                    "message": f"问答差评率异常: {rate:.1%} (过去1小时)"
                })

        # 2. Skill失败率检查
        skill_stats = await self.db.fetchrow("""
            SELECT
                COUNT(CASE WHEN success = false THEN 1 END)::float / NULLIF(COUNT(*), 0) as failure_rate
            FROM skill_feedback
            WHERE workspace_id = $1 AND created_at >= $2
        """, workspace_id, since)

        if skill_stats and skill_stats["failure_rate"] is not None:
            rate = float(skill_stats["failure_rate"])
            severity = self._assess_severity(rate, "skill_failure_rate")
            if severity:
                alerts.append({
                    "type": "skill_failure_rate",
                    "severity": severity,
                    "current_value": rate,
                    "message": f"Skill执行失败率异常: {rate:.1%} (过去1小时)"
                })

        # 3. 本体更新积压检查
        pending = await self.redis.get(f"pending_updates:{workspace_id}")
        pending_count = int(pending) if pending else 0
        severity = self._assess_severity(pending_count, "stale_updates")
        if severity:
            alerts.append({
                "type": "stale_updates",
                "severity": severity,
                "current_value": pending_count,
                "message": f"本体更新积压异常: {pending_count}条待处理"
            })

        return alerts

    def _assess_severity(self, value: float, metric_type: str) -> Optional[str]:
        """评估严重程度"""
        thresholds = self.THRESHOLDS.get(metric_type, {})
        if value >= thresholds.get("critical", float("inf")):
            return "critical"
        if value >= thresholds.get("warning", float("inf")):
            return "warning"
        return None

    async def _store_alert(self, workspace_id: str, alert: dict):
        """持久化告警"""
        await self.db.execute(
            """INSERT INTO anomaly_alerts (workspace_id, alert_type, severity, message, detected_at)
               VALUES ($1, $2, $3, $4, $5)""",
            workspace_id, alert["type"], alert["severity"],
            alert["message"], datetime.now(timezone.utc)
        )

        # 严重告警实时推送
        if alert["severity"] == "critical":
            await self.notifier.send_critical_alert(workspace_id, alert)

    async def run_periodic(self):
        """定时任务: 每小时运行一次"""
        while True:
            await self.detect_hourly()
            await asyncio.sleep(3600)
```

### 5.10 前端反馈仪表盘

```typescript
// frontend/src/modules/feedback/components/DashboardMetrics.tsx

import React from 'react'
import { Row, Col, Card, Statistic, Progress, Alert, Timeline, Typography } from 'antd'
import {
  LikeOutlined, ThunderboltOutlined, NodeIndexOutlined,
  UserOutlined, WarningOutlined
} from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { FeedbackAPI } from '@/services/api'

const { Title, Text } = Typography

export const FeedbackDashboard: React.FC<{ workspaceId: string }> = ({ workspaceId }) => {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['feedback-dashboard', workspaceId],
    queryFn: () => FeedbackAPI.getDashboardMetrics(workspaceId),
    refetchInterval: 30000
  })

  if (isLoading || !metrics) return <div>加载中...</div>

  const { qa_quality, skill_performance, anomaly_alerts } = metrics

  return (
    <div className="feedback-dashboard">
      <Title level={4}>反馈闭环监控</Title>

      {/* 核心指标卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="问答好评率 (24h)"
              value={qa_quality.daily.positive_rate}
              suffix="%"
              prefix={<LikeOutlined />}
              valueStyle={{ color: qa_quality.daily.positive_rate > 80 ? '#3f8600' : '#cf1322' }}
            />
            <Progress
              percent={qa_quality.daily.positive_rate}
              size="small"
              status={qa_quality.daily.positive_rate > 80 ? 'success' : 'exception'}
            />
          </Card>
        </Col>

        <Col span={6}>
          <Card>
            <Statistic
              title="Skill成功率 (24h)"
              value={skill_performance.success_rate}
              suffix="%"
              prefix={<ThunderboltOutlined />}
              valueStyle={{ color: skill_performance.success_rate > 90 ? '#3f8600' : '#cf1322' }}
            />
            <Text type="secondary">P95延迟: {skill_performance.p95_latency_ms}ms</Text>
          </Card>
        </Col>

        <Col span={6}>
          <Card>
            <Statistic
              title="回答问题可信度"
              value={qa_quality.daily.avg_confidence}
              suffix="%"
              prefix={<NodeIndexOutlined />}
            />
            <Text type="secondary">本周趋势: {qa_quality.weekly_trend}%</Text>
          </Card>
        </Col>

        <Col span={6}>
          <Card>
            <Statistic
              title="问题标记"
              value={qa_quality.daily.negative_count}
              prefix={<WarningOutlined />}
              valueStyle={{ color: qa_quality.daily.negative_count > 5 ? '#cf1322' : '#3f8600' }}
            />
            <Text type="secondary">过去24小时</Text>
          </Card>
        </Col>
      </Row>

      {/* 异常告警 */}
      {anomaly_alerts?.length > 0 && (
        <Card title={<><WarningOutlined /> 活跃告警 ({anomaly_alerts.length})</>} style={{ marginBottom: 24 }}>
          {anomaly_alerts.map((alert: any) => (
            <Alert
              key={alert.detected_at}
              type={alert.severity === 'critical' ? 'error' : 'warning'}
              message={alert.alert_type}
              description={alert.message}
              style={{ marginBottom: 8 }}
              showIcon
            />
          ))}
        </Card>
      )}
    </div>
  )
}
```

### 5.11 用户反馈前端组件

> **对应需求**: FR-1104 (结果呈现与交互反馈), FR-502 (快速添加)
> **关联模块**: [session_memory/DESIGN.md](../../03-modules/session_memory/DESIGN.md)

```typescript
const FeedbackBar: React.FC<{ messageId: string; onRate: (rating: number) => void }> = ({ messageId, onRate }) => {
  const [rating, setRating] = useState<number | null>(null)
  const [comment, setComment] = useState("")
  const [showComment, setShowComment] = useState(false)

  return (
    <div className="feedback-bar">
      <Space>
        <Button.Group>
          <Button
            size="small"
            type={rating === 1 ? "primary" : "default"}
            icon={<LikeOutlined />}
            onClick={() => { setRating(1); onRate(1) }}
          />
          <Button
            size="small"
            type={rating === -1 ? "primary" : "default"}
            icon={<DislikeOutlined />}
            onClick={() => { setRating(-1); onRate(-1); setShowComment(true) }}
          />
        </Button.Group>

        <Button size="small" type="link" icon={<CommentOutlined />}
          onClick={() => setShowComment(!showComment)}>
          反馈
        </Button>

        <Button size="small" type="link" icon={<PushpinOutlined />}>
          添加到工作区
        </Button>
      </Space>

      {showComment && (
        <div className="feedback-comment">
          <Input.TextArea
            rows={2}
            placeholder="请描述问题或建议..."
            value={comment}
            onChange={e => setComment(e.target.value)}
          />
          <Button size="small" type="primary"
            onClick={() => { submitComment(messageId, comment, rating); setShowComment(false) }}>
            提交反馈
          </Button>
        </div>
      )}
    </div>
  )
}

const FeedbackTracker: React.FC<{ workspaceId: string }> = ({ workspaceId }) => {
  const [feedbackItems, setFeedbackItems] = useState<FeedbackItem[]>([])

  useEffect(() => {
    fetchFeedbackItems(workspaceId).then(setFeedbackItems)
  }, [workspaceId])

  return (
    <div className="feedback-tracker">
      <Typography.Title level={5}>我的反馈 ({feedbackItems.length})</Typography.Title>

      <List dataSource={feedbackItems}
        renderItem={(item) => (
          <List.Item
            extra={
              <Tag color={item.status === 'resolved' ? 'success' : item.status === 'acknowledged' ? 'processing' : 'default'}>
                {item.status === 'resolved' ? '已解决' : item.status === 'acknowledged' ? '处理中' : '待处理'}
              </Tag>
            }
          >
            <List.Item.Meta
              avatar={item.rating === 1 ? <LikeOutlined style={{ color: '#52c41a' }} /> : <DislikeOutlined style={{ color: '#ff4d4f' }} />}
              title={item.type === 'rating' ? '回答评分' : '文本反馈'}
              description={
                <>
                  <Text type="secondary">{formatTime(item.created_at)}</Text>
                  {item.comment && <div style={{ marginTop: 4 }}>{item.comment}</div>}
                  {item.admin_response && (
                    <Alert type="info" message="管理员回复" description={item.admin_response} style={{ marginTop: 4 }} />
                  )}
                </>
              }
            />
          </List.Item>
        )}
      />
    </div>
  )
}
```

### 5.12 性能调优策略

> **对应需求**: NFR-P01~P08 (性能要求)
> **关联文档**: [ARCHITECTURE_OPS.md](ARCHITECTURE_OPS.md)

| 优化维度 | 目标 | 策略 | 关键配置 |
|---------|------|------|---------|
| **问答延迟** | P95 < 3s | 并行化 RAG 检索 + 流式 SSE 首 token 输出 | `stream=True`, `max_context_tokens=4000` |
| **图谱查询** | P95 < 500ms | Neo4j 索引 + 连接池预热 + 查询缓存 | `db.connection.pool_size=50`, `pagecache=2G` |
| **并发能力** | 100+ 在线用户 | uvicorn workers + gthread 协程池 | `workers=4`, `limit_concurrency=200` |
| **Skill 加载** | < 30s | 懒加载 + importlib 缓存 + watchdog 去抖 | `debounce=5s`, `cache_ttl=3600` |
| **推演并发** | 10 方案并行 | Docker 容器隔离 + 资源配额 | `cpus=1`, `memory=512M` |
| **推演时长** | 平均 < 30s | 时间加速 + 跳过无关事件 | `time_scale=60x`, `event_filter=true` |

```python
# odap/core/performance.py

class PerformanceOptimizer:
    """集中管理各维度的性能优化参数，支持运行时热调"""

    def __init__(self, config: PerformanceConfig):
        self._config = config

    async def optimize_neo4j_session(self):
        """连接池预热 + 索引检查"""
        await self._run_cypher("CREATE INDEX entity_type_idx IF NOT EXISTS FOR (n:Entity) ON (n.entity_type)")
        await self._run_cypher("CREATE INDEX node_uuid_idx IF NOT EXISTS FOR (n) ON (n.uuid)")
        # 预热连接池
        for _ in range(self._config.db_pool_size):
            await self._acquire_and_release()

    def select_rag_strategy(self, query_complexity: float) -> RAGStrategy:
        """根据查询复杂度自适应选择 RAG 策略"""
        if query_complexity < 0.3:                     # 简单问题 → 轻量检索
            return RAGStrategy.LIGHTWEIGHT              # top_k=3, 不跨图
        elif query_complexity < 0.7:                   # 中等问题 → 标准检索
            return RAGStrategy.STANDARD                 # top_k=5, 1-hop
        else:                                           # 复杂问题 → 深度检索
            return RAGStrategy.DEEP                     # top_k=10, 2-hop + vector

    def compute_query_complexity(self, query: str) -> float:
        """启发式复杂度评估：基于实体数量 / 关系密度 / 语义跨度"""
        entity_count = self._count_entities_in_query(query)
        relation_density = self._estimate_relation_density(query)
        return min(1.0, 0.2 * entity_count + 0.5 * relation_density)
```

**SSE 流式优化**:

```python
class StreamingOptimizer:
    async def stream_with_early_first_token(self, prompt: str) -> AsyncGenerator[str, None]:
        """优先输出首 token，后续内容流式传输"""
        response = await self._llm.create(prompt, stream=True)

        first_token_sent = False
        async for chunk in response:
            content = chunk.choices[0].delta.content or ""
            if not first_token_sent and content:
                first_token_sent = True
                self._record_ttft()          # Time To First Token
            yield content
```

---

## 附录: 端到端应用示例

### A. 完整交互流程示例

```
Step 1 (Phase 1): 用户上传一份PDF报告"南海态势评估"
    → IngestionWizard → 选择PDF → 文档解析 → LLM信息抽取
    → 产出: 15个实体 + 23条关系 + 3个事件

Step 2 (Phase 2): 自动跳转审核页面
    → 用户确认12个实体 + 18条关系 → 提交构建
    → 写入Graphiti → 创建本体 Version 1.4.0

Step 3 (Phase 3): 用户在Q&A对话区提问
    "南海地区各参战单元的现状如何？给出建议。"
    → 检索上下文 (5个实体 + 12条关系)
    → LLM流式输出: 列出 UnitA/UnitB/...的当前状态
    → 实体标记: [[entity:E1:UnitA]] 正在前往目标区域...
    → 建议标记: <<suggestion:attack_target:对南海目标实施打击>>

Step 4 (Phase 4): 右侧SuggestionPanel显示
    "[attack_target] (置信度92%): 对南海指定目标实施打击"
    → 用户点击"立即执行"
    → OPA权限检查: role=commander → ALLOWED
    → Skill执行: attack_target({target_id: "E15", unit_id: "E1"})
    → 审计日志记录完整的执行链路

Step 5 (Phase 5): 闭环反馈生效
    → Skill执行完成, 输出 {success: true, affected_entities: ["E15"]}
    → 本体增量更新: Target E15.status = "pending-action-performed"
    → 反馈收集: 用户对Phase 3的回答点赞
    → 会话摘要: 生成Session Insight供后续参考
    → 提示词优化: AB测试框架收集质量数据用于持续改进
    → 闭环完成, 系统等待下一轮交互
```

### B. 各 Phase 关键监控metric

| Phase | Key Metrics |
|------|------------|
| P1 | 文件解析成功率、实体抽取准确率(F1)、处理耗时、LLM调用次数、队列积压数、并发饱和度 |
| P2 | 人工审核通过率、关系验证准确率、版本创建间隔、驳回原因分布、回滚频率、差异变更量 |
| P3 | 回答相关性评分、实体链接精确率、检索召回率、响应延迟(P50/P95)、会话摘要压缩率、上下文token利用率 |
| P4 | Skill执行成功率、OPA拒绝率(按role统计)、执行延迟、参数有效性、热重载延迟、并发饱和度、版本切换频率 |
| P5 | 反馈到本体更新的延迟、Prompt版本切换频率、审计日志完整性、A/B测试显著性达成率、异常告警响应时间、好评率趋势 |

---

*关联文档:*
- [ARCHITECTURE_FULL_CHAIN.md](ARCHITECTURE_FULL_CHAIN.md)
- [ODAP综合优化设计文档.md](../ODAP综合优化设计文档.md)
- [图谱可视化优化设计](../03-modules/visualization/DESIGN_GRAPH_OPTIMIZATION.md)
- [ADR-052 WebUI选型](../07-adr/ADR-052_webui_opensource_selection.md)
- [ADR-053 Skill管理选型](../07-adr/ADR-053_skill_management_selection.md)
