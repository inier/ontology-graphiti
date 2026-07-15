"""
多数据源统一接入 - 对齐 docs/03-modules/infra/DESIGN.md / ADR-013

功能:
- 统一的 DataSource 抽象
- 多格式数据读取 (JSON, CSV, Parquet, PDF, TXT)
- 数据管道编排 (Pipeline)
- 质量检查和转换
"""

import os
import json
import uuid
import time
import threading
from typing import Dict, Any, List, Optional, Iterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod


class DataFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"
    PDF = "pdf"
    TXT = "txt"
    MARKDOWN = "markdown"
    XML = "xml"
    YAML = "yaml"
    RAW = "raw"


class PipelineStage(str, Enum):
    EXTRACT = "extract"
    TRANSFORM = "transform"
    VALIDATE = "validate"
    LOAD = "load"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DataRecord:
    id: str
    source_id: str
    content: Dict[str, Any]
    format: DataFormat = DataFormat.JSON
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "content": self.content,
            "format": self.format.value,
            "metadata": self.metadata,
            "ingested_at": self.ingested_at.isoformat(),
        }


@dataclass
class StageResult:
    stage: PipelineStage
    status: StageStatus
    records_in: int = 0
    records_out: int = 0
    records_failed: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    pipeline_id: str
    pipeline_name: str
    stages: List[StageResult] = field(default_factory=list)
    total_records_in: int = 0
    total_records_out: int = 0
    total_duration_ms: float = 0.0
    success: bool = False
    error: Optional[str] = None


class DataSourceConnector(ABC):
    """数据源连接器抽象"""

    @abstractmethod
    def connect(self) -> bool:
        ...

    @abstractmethod
    def read(self, **kwargs) -> Iterator[DataRecord]:
        ...

    @abstractmethod
    def close(self):
        ...


class FileDataSource(DataSourceConnector):
    """文件数据源"""

    SUPPORTED_EXTENSIONS = {
        '.json': DataFormat.JSON,
        '.csv': DataFormat.CSV,
        '.parquet': DataFormat.PARQUET,
        '.pdf': DataFormat.PDF,
        '.txt': DataFormat.TXT,
        '.md': DataFormat.MARKDOWN,
        '.xml': DataFormat.XML,
        '.yaml': DataFormat.YAML,
        '.yml': DataFormat.YAML,
    }

    def __init__(self, file_path: str, source_id: str = None):
        self.file_path = file_path
        self.source_id = source_id or os.path.basename(file_path)
        self._format = self._detect_format()
        self._connected = False

    def _detect_format(self) -> DataFormat:
        _, ext = os.path.splitext(self.file_path)
        return self.SUPPORTED_EXTENSIONS.get(ext.lower(), DataFormat.RAW)

    def connect(self) -> bool:
        self._connected = os.path.exists(self.file_path)
        return self._connected

    def read(self, **kwargs) -> Iterator[DataRecord]:
        if not self._connected:
            self.connect()
        if not self._connected:
            return

        limit = kwargs.get("limit", 0)
        count = 0

        try:
            if self._format == DataFormat.JSON:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if limit and count >= limit:
                            break
                        yield DataRecord(
                            id=str(uuid.uuid4())[:12],
                            source_id=self.source_id,
                            content=item,
                            format=self._format,
                        )
                        count += 1

            elif self._format == DataFormat.CSV:
                import csv
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if limit and count >= limit:
                            break
                        yield DataRecord(
                            id=str(uuid.uuid4())[:12],
                            source_id=self.source_id,
                            content=dict(row),
                            format=self._format,
                        )
                        count += 1

            elif self._format in (DataFormat.TXT, DataFormat.MARKDOWN):
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    yield DataRecord(
                        id=str(uuid.uuid4())[:12],
                        source_id=self.source_id,
                        content={"text": content},
                        format=self._format,
                        metadata={"filename": os.path.basename(self.file_path)},
                    )

            elif self._format == DataFormat.YAML:
                try:
                    import yaml
                except ImportError:
                    return
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    for item in (data if isinstance(data, list) else [data]):
                        if limit and count >= limit:
                            break
                        yield DataRecord(
                            id=str(uuid.uuid4())[:12],
                            source_id=self.source_id,
                            content=item,
                            format=self._format,
                        )
                        count += 1

            elif self._format == DataFormat.PARQUET:
                try:
                    import pandas as pd
                    df = pd.read_parquet(self.file_path)
                    for _, row in df.iterrows():
                        if limit and count >= limit:
                            break
                        yield DataRecord(
                            id=str(uuid.uuid4())[:12],
                            source_id=self.source_id,
                            content=row.to_dict(),
                            format=self._format,
                        )
                        count += 1
                except ImportError:
                    pass

        except Exception as e:
            raise RuntimeError(f"Failed to read {self.file_path}: {e}")

    def close(self):
        self._connected = False


class DataTransformer:
    """数据转换器"""

    def __init__(self):
        self._transforms: List[Callable[[DataRecord], DataRecord]] = []

    def add_transform(self, transform: Callable[[DataRecord], DataRecord]):
        self._transforms.append(transform)

    def apply(self, record: DataRecord) -> Optional[DataRecord]:
        try:
            result = record
            for transform in self._transforms:
                result = transform(result)
                if result is None:
                    return None
            return result
        except Exception:
            return None


class DataValidator:
    """数据验证器"""

    def __init__(self):
        self._rules: List[Callable[[DataRecord], Optional[str]]] = []

    def add_rule(self, rule: Callable[[DataRecord], Optional[str]]):
        """添加验证规则, 返回 None 表示通过, 返回 str 表示错误信息"""
        self._rules.append(rule)

    def validate(self, record: DataRecord) -> List[str]:
        errors = []
        for rule in self._rules:
            error = rule(record)
            if error:
                errors.append(error)
        return errors

    def is_valid(self, record: DataRecord) -> bool:
        return len(self.validate(record)) == 0


class DataPipeline:
    """数据管道"""

    MAX_ERRORS = 100

    def __init__(self, name: str):
        self.name = name
        self._sources: List[DataSourceConnector] = []
        self._transformer = DataTransformer()
        self._validator = DataValidator()
        self._loader: Optional[Callable[[List[DataRecord]], int]] = None
        self._lock = threading.Lock()

    def add_source(self, source: DataSourceConnector):
        self._sources.append(source)

    def add_transform(self, transform: Callable[[DataRecord], DataRecord]):
        self._transformer.add_transform(transform)

    def add_validator(self, rule: Callable[[DataRecord], Optional[str]]):
        self._validator.add_rule(rule)

    def set_loader(self, loader: Callable[[List[DataRecord]], int]):
        self._loader = loader

    def run(self, source_kwargs: Dict = None) -> PipelineResult:
        pipeline_id = str(uuid.uuid4())[:16]
        result = PipelineResult(pipeline_id=pipeline_id, pipeline_name=self.name)
        all_records: List[DataRecord] = []
        total_start = time.time()

        extract_result = self._run_extract(source_kwargs or {})
        result.stages.append(extract_result)
        if extract_result.status == StageStatus.FAILED:
            result.success = False
            result.error = extract_result.error
            return result
        all_records = extract_result.details.get("records", [])

        transform_result = self._run_transform(all_records)
        result.stages.append(transform_result)
        all_records = transform_result.details.get("records", [])

        validate_result = self._run_validate(all_records)
        result.stages.append(validate_result)
        all_records = validate_result.details.get("records", [])

        load_result = self._run_load(all_records)
        result.stages.append(load_result)

        result.total_records_in = extract_result.records_out
        result.total_records_out = load_result.records_out
        result.total_duration_ms = (time.time() - total_start) * 1000
        result.success = all(s.status == StageStatus.SUCCESS for s in result.stages if s.status != StageStatus.SKIPPED)
        return result

    def _run_extract(self, kwargs: Dict) -> StageResult:
        result = StageResult(stage=PipelineStage.EXTRACT, status=StageStatus.RUNNING)
        start = time.time()
        records = []
        errors = []

        for source in self._sources:
            try:
                if not source.connect():
                    errors.append(f"Failed to connect to source")
                    continue
                for record in source.read(**kwargs):
                    records.append(record)
            except Exception as e:
                errors.append(str(e))
            finally:
                source.close()

        result.records_in = 0
        result.records_out = len(records)
        result.duration_ms = (time.time() - start) * 1000
        result.details = {"records": records, "errors": errors[:self.MAX_ERRORS]}

        if errors:
            result.status = StageStatus.FAILED
            result.error = errors[0]
        elif not records:
            result.status = StageStatus.SKIPPED
        else:
            result.status = StageStatus.SUCCESS

        return result

    def _run_transform(self, records: List[DataRecord]) -> StageResult:
        result = StageResult(stage=PipelineStage.TRANSFORM, status=StageStatus.RUNNING)
        start = time.time()
        transformed = []
        failed = 0

        for record in records:
            transformed_record = self._transformer.apply(record)
            if transformed_record:
                transformed.append(transformed_record)
            else:
                failed += 1

        result.records_in = len(records)
        result.records_out = len(transformed)
        result.records_failed = failed
        result.duration_ms = (time.time() - start) * 1000
        result.details = {"records": transformed}
        result.status = StageStatus.SUCCESS if failed == 0 else (
            StageStatus.FAILED if failed == len(records) else StageStatus.SUCCESS
        )
        return result

    def _run_validate(self, records: List[DataRecord]) -> StageResult:
        result = StageResult(stage=PipelineStage.VALIDATE, status=StageStatus.RUNNING)
        start = time.time()
        valid = []
        errors = []

        for record in records:
            record_errors = self._validator.validate(record)
            if not record_errors:
                valid.append(record)
            else:
                errors.extend(record_errors)

        result.records_in = len(records)
        result.records_out = len(valid)
        result.records_failed = len(records) - len(valid)
        result.duration_ms = (time.time() - start) * 1000
        result.details = {"records": valid, "errors": errors[:self.MAX_ERRORS]}
        result.status = StageStatus.SUCCESS if len(valid) > 0 else StageStatus.SKIPPED
        return result

    def _run_load(self, records: List[DataRecord]) -> StageResult:
        result = StageResult(stage=PipelineStage.LOAD, status=StageStatus.RUNNING)
        start = time.time()

        if self._loader:
            try:
                count = self._loader(records)
                result.records_out = count
                result.status = StageStatus.SUCCESS
            except Exception as e:
                result.error = str(e)
                result.status = StageStatus.FAILED
        else:
            result.status = StageStatus.SKIPPED

        result.records_in = len(records)
        result.duration_ms = (time.time() - start) * 1000
        return result
