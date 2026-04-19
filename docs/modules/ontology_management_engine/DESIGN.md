# 本体管理引擎模块设计文档

> **优先级**: P0 | **相关 ADR**: ADR-038, ADR-048

## 1. 模块概述

### 1.1 模块定位

`ontology_management_engine` 是 ODAP 平台的核心引擎之一，负责本体的完整生命周期管理，包括数据摄入、本体构建、版本管理、验证等功能。它是连接原始数据与知识图谱的桥梁，确保本体的质量和一致性。

### 1.2 核心职责

| 职责 | 描述 |
|------|------|
| 数据摄入审计 | 记录数据来源、处理过程和质量指标 |
| 本体构建 | 实体提取、关系识别、属性映射 |
| 版本管理 | 版本追踪、变更对比、回滚机制 |
| 验证引擎 | 数据质量检查、一致性验证 |
| 审计仪表盘 | 监控本体健康状态和异常 |

---

## 2. 架构设计

### 2.1 模块架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       本体管理引擎 (OntologyManagementEngine)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐    ┌───────────────┐  │
│  │  数据摄入审计  │    │   本体构建器   │    │  版本管理器   │    │   验证引擎   │  │
│  │  DataIngestAudit │  │ OntologyBuilder│  │ VersionManager│  │ ValidationEngine│  │
│  └───────────────┘    └───────────────┘    └───────────────┘    └───────────────┘  │
│         │                      │                      │                      │        │
│         └──────────────────────┼──────────────────────┼──────────────────────┘        │
│                                ▼                                                  │
│                        ┌───────────────┐                                           │
│                        │  审计仪表盘   │                                           │
│                        │  AuditDashboard│                                          │
│                        └───────────────┘                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

| 组件 | 职责 | 接口 | 依赖 |
|------|------|------|------|
| **数据摄入审计** | 记录数据来源和处理过程 | `auditDataIngestion()` | 数据来源 |
| **本体构建器** | 实体提取和关系识别 | `buildOntology()` | Graphiti |
| **版本管理器** | 版本追踪和变更管理 | `manageVersion()` | 存储 |
| **验证引擎** | 数据质量和一致性检查 | `validateOntology()` | 验证规则 |
| **审计仪表盘** | 监控和可视化 | `getDashboardData()` | 各组件 |

---

## 3. 核心数据模型

### 3.1 数据摄入审计模型

```python
# ontology_management_engine/models/audit.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class DataSource(str, Enum):
    """数据来源"""
    API = "api"
    FILE = "file"
    DATABASE = "database"
    STREAM = "stream"
    MANUAL = "manual"

class ProcessingStatus(str, Enum):
    """处理状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DataIngestRecord(BaseModel):
    """数据摄入记录"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: DataSource
    source_details: Dict[str, Any] = Field(default_factory=dict)
    data_schema: Dict[str, Any] = Field(default_factory=dict)
    record_count: int = 0
    processed_count: int = 0
    failed_count: int = 0
    status: ProcessingStatus = ProcessingStatus.PENDING
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    quality_metrics: Dict[str, float] = Field(default_factory=dict)
    created_by: str = "system"

class AuditLog(BaseModel):
    """审计日志"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ingest_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    level: str = "info"
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    actor: str = "system"
```

### 3.2 本体构建模型

```python
# ontology_management_engine/models/ontology.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class OntologyStatus(str, Enum):
    """本体状态"""
    DRAFT = "draft"
    VALIDATED = "validated"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"

class EntityExtractionResult(BaseModel):
    """实体提取结果"""
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    processing_time: float = 0.0

class OntologyBuildResult(BaseModel):
    """本体构建结果"""
    build_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_ingest_id: str
    entity_count: int = 0
    relation_count: int = 0
    property_count: int = 0
    status: ProcessingStatus = ProcessingStatus.PENDING
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    ontology_version: str = "1.0.0"

class OntologyDocument(BaseModel):
    """本体文档"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    status: OntologyStatus = OntologyStatus.DRAFT
    version: str = "1.0.0"
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    properties: List[Dict[str, Any]] = Field(default_factory=list)
    validation_rules: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
    updated_by: str = "system"
```

### 3.3 版本管理模型

```python
# ontology_management_engine/models/version.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class VersionOperation(str, Enum):
    """版本操作"""
    CREATE = "create"
    UPDATE = "update"
    ROLLBACK = "rollback"
    MERGE = "merge"
    DELETE = "delete"

class VersionStatus(str, Enum):
    """版本状态"""
    DRAFT = "draft"
    RELEASED = "released"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"

class VersionChange(BaseModel):
    """版本变更"""
    change_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    field: str
    old_value: Any = None
    new_value: Any = None
    change_type: str = "update"
    timestamp: datetime = Field(default_factory=datetime.now)
    changed_by: str = "system"

class OntologyVersion(BaseModel):
    """本体版本"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ontology_id: str
    version_number: str
    parent_version_id: Optional[str] = None
    status: VersionStatus = VersionStatus.DRAFT
    changes: List[VersionChange] = Field(default_factory=list)
    change_summary: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
    is_current: bool = False
    is_stable: bool = False

class VersionComparison(BaseModel):
    """版本对比"""
    source_version_id: str
    target_version_id: str
    added_entities: List[str] = Field(default_factory=list)
    removed_entities: List[str] = Field(default_factory=list)
    modified_entities: List[str] = Field(default_factory=list)
    added_relations: List[str] = Field(default_factory=list)
    removed_relations: List[str] = Field(default_factory=list)
    modified_relations: List[str] = Field(default_factory=list)
    compatibility_score: float = 1.0
    comparison_time: datetime = Field(default_factory=datetime.now)
```

### 3.4 验证引擎模型

```python
# ontology_management_engine/models/validation.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class ValidationSeverity(str, Enum):
    """验证严重程度"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class ValidationRule(BaseModel):
    """验证规则"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    rule_type: str  # entity/relation/property
    severity: ValidationSeverity = ValidationSeverity.WARNING
    expression: str  # 规则表达式
    params: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True

class ValidationResult(BaseModel):
    """验证结果"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ontology_id: str
    ontology_version: str
    validation_time: datetime = Field(default_factory=datetime.now)
    status: str = "pending"  # pending/running/complete/failed
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    info: List[Dict[str, Any]] = Field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    overall_score: float = 1.0  # 0-1
    duration_seconds: float = 0.0

class ValidationIssue(BaseModel):
    """验证问题"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str
    rule_name: str
    severity: ValidationSeverity
    entity_id: Optional[str] = None
    relation_id: Optional[str] = None
    property_name: Optional[str] = None
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
```

---

## 4. 核心接口设计

### 4.1 数据摄入审计接口

```python
# ontology_management_engine/interfaces/audit.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IDataIngestAudit(ABC):
    """数据摄入审计接口"""
    
    @abstractmethod
    async def audit_data_ingestion(
        self, 
        data: Dict[str, Any], 
        source: str, 
        source_details: Optional[Dict[str, Any]] = None
    ) -> str:
        """审计数据摄入"""
        pass
    
    @abstractmethod
    async def get_ingest_record(self, ingest_id: str) -> Dict[str, Any]:
        """获取摄入记录"""
        pass
    
    @abstractmethod
    async def get_ingest_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取摄入历史"""
        pass
    
    @abstractmethod
    async def update_ingest_status(
        self, 
        ingest_id: str, 
        status: str, 
        errors: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """更新摄入状态"""
        pass
```

### 4.2 本体构建器接口

```python
# ontology_management_engine/interfaces/builder.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IOntologyBuilder(ABC):
    """本体构建器接口"""
    
    @abstractmethod
    async def build_ontology(
        self, 
        data: Dict[str, Any], 
        ontology_def: Dict[str, Any]
    ) -> str:
        """构建本体"""
        pass
    
    @abstractmethod
    async def extract_entities(
        self, 
        data: Dict[str, Any], 
        entity_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """提取实体"""
        pass
    
    @abstractmethod
    async def extract_relations(
        self, 
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """提取关系"""
        pass
    
    @abstractmethod
    async def get_build_result(self, build_id: str) -> Dict[str, Any]:
        """获取构建结果"""
        pass
```

### 4.3 版本管理器接口

```python
# ontology_management_engine/interfaces/version.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IVersionManager(ABC):
    """版本管理器接口"""
    
    @abstractmethod
    async def create_version(
        self, 
        ontology_id: str, 
        changes: Dict[str, Any], 
        created_by: str
    ) -> str:
        """创建版本"""
        pass
    
    @abstractmethod
    async def rollback_version(
        self, 
        version_id: str, 
        target_version_id: str
    ) -> bool:
        """回滚版本"""
        pass
    
    @abstractmethod
    async def compare_versions(
        self, 
        source_version_id: str, 
        target_version_id: str
    ) -> Dict[str, Any]:
        """对比版本"""
        pass
    
    @abstractmethod
    async def get_version_history(
        self, 
        ontology_id: str
    ) -> List[Dict[str, Any]]:
        """获取版本历史"""
        pass
    
    @abstractmethod
    async def set_current_version(
        self, 
        version_id: str
    ) -> bool:
        """设置当前版本"""
        pass
```

### 4.4 验证引擎接口

```python
# ontology_management_engine/interfaces/validation.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IValidationEngine(ABC):
    """验证引擎接口"""
    
    @abstractmethod
    async def validate_ontology(
        self, 
        ontology: Dict[str, Any], 
        rules: Optional[List[str]] = None
    ) -> str:
        """验证本体"""
        pass
    
    @abstractmethod
    async def add_validation_rule(
        self, 
        rule: Dict[str, Any]
    ) -> str:
        """添加验证规则"""
        pass
    
    @abstractmethod
    async def get_validation_result(
        self, 
        validation_id: str
    ) -> Dict[str, Any]:
        """获取验证结果"""
        pass
    
    @abstractmethod
    async def get_validation_rules(
        self, 
        rule_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取验证规则"""
        pass
```

### 4.5 审计仪表盘接口

```python
# ontology_management_engine/interfaces/dashboard.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IAuditDashboard(ABC):
    """审计仪表盘接口"""
    
    @abstractmethod
    async def get_dashboard_data(
        self, 
        time_range: Optional[str] = "7d"
    ) -> Dict[str, Any]:
        """获取仪表盘数据"""
        pass
    
    @abstractmethod
    async def get_health_metrics(
        self, 
        ontology_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取健康指标"""
        pass
    
    @abstractmethod
    async def get_anomaly_detection(
        self, 
        time_range: Optional[str] = "24h"
    ) -> List[Dict[str, Any]]:
        """获取异常检测"""
        pass
    
    @abstractmethod
    async def export_report(
        self, 
        format: str = "pdf"
    ) -> bytes:
        """导出报告"""
        pass
```

---

## 5. 实现类设计

### 5.1 数据摄入审计实现

```python
# ontology_management_engine/impl/audit.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from .models.audit import DataIngestRecord, AuditLog, DataSource, ProcessingStatus
from .interfaces.audit import IDataIngestAudit

class DataIngestAudit(IDataIngestAudit):
    """数据摄入审计实现"""
    
    def __init__(self, storage):
        self.storage = storage
    
    async def audit_data_ingestion(
        self, 
        data: Dict[str, Any], 
        source: str, 
        source_details: Optional[Dict[str, Any]] = None
    ) -> str:
        """审计数据摄入"""
        # 创建摄入记录
        record = DataIngestRecord(
            source=DataSource(source),
            source_details=source_details or {},
            record_count=len(data.get('records', [])),
            status=ProcessingStatus.PENDING
        )
        
        # 保存记录
        ingest_id = await self.storage.save_ingest_record(record.model_dump())
        
        # 记录审计日志
        await self._log_audit(
            ingest_id, "info", f"开始处理来自 {source} 的数据", {"record_count": record.record_count}
        )
        
        return ingest_id
    
    async def get_ingest_record(self, ingest_id: str) -> Dict[str, Any]:
        """获取摄入记录"""
        return await self.storage.get_ingest_record(ingest_id)
    
    async def get_ingest_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取摄入历史"""
        return await self.storage.get_ingest_records(limit=limit)
    
    async def update_ingest_status(
        self, 
        ingest_id: str, 
        status: str, 
        errors: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """更新摄入状态"""
        record = await self.storage.get_ingest_record(ingest_id)
        if not record:
            return False
        
        record['status'] = status
        if status in ['completed', 'failed']:
            record['end_time'] = datetime.now().isoformat()
            record['duration_seconds'] = (datetime.now() - datetime.fromisoformat(record['start_time'])).total_seconds()
        
        if errors:
            record['errors'] = errors
            record['failed_count'] = len(errors)
        
        await self.storage.update_ingest_record(ingest_id, record)
        
        # 记录状态变更
        await self._log_audit(
            ingest_id, "info", f"状态更新为 {status}", {"errors": len(errors) if errors else 0}
        )
        
        return True
    
    async def _log_audit(self, ingest_id: str, level: str, message: str, details: Dict[str, Any]):
        """记录审计日志"""
        log = AuditLog(
            ingest_id=ingest_id,
            level=level,
            message=message,
            details=details
        )
        await self.storage.save_audit_log(log.model_dump())
```

### 5.2 本体构建器实现

```python
# ontology_management_engine/impl/builder.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from .models.ontology import (
    EntityExtractionResult, OntologyBuildResult, 
    OntologyDocument, ProcessingStatus
)
from .interfaces.builder import IOntologyBuilder

class OntologyBuilder(IOntologyBuilder):
    """本体构建器实现"""
    
    def __init__(self, graphiti_client, storage):
        self.graphiti = graphiti_client
        self.storage = storage
    
    async def build_ontology(
        self, 
        data: Dict[str, Any], 
        ontology_def: Dict[str, Any]
    ) -> str:
        """构建本体"""
        # 创建构建结果记录
        build_result = OntologyBuildResult(
            source_ingest_id=data.get('ingest_id', ''),
            status=ProcessingStatus.PROCESSING
        )
        
        build_id = await self.storage.save_build_result(build_result.model_dump())
        
        try:
            # 提取实体
            extraction_result = await self.extract_entities(data)
            
            # 提取关系
            relations = await self.extract_relations(extraction_result.entities)
            
            # 构建本体文档
            ontology = OntologyDocument(
                name=ontology_def.get('name', 'Untitled'),
                description=ontology_def.get('description', ''),
                entities=extraction_result.entities,
                relations=relations,
                properties=ontology_def.get('properties', [])
            )
            
            # 保存本体
            ontology_id = await self.storage.save_ontology(ontology.model_dump())
            
            # 更新构建结果
            build_result.status = ProcessingStatus.COMPLETED
            build_result.entity_count = len(extraction_result.entities)
            build_result.relation_count = len(relations)
            build_result.end_time = datetime.now()
            build_result.duration_seconds = (build_result.end_time - build_result.start_time).total_seconds()
            
            await self.storage.update_build_result(build_id, build_result.model_dump())
            
        except Exception as e:
            # 处理错误
            build_result.status = ProcessingStatus.FAILED
            build_result.errors = [{'message': str(e)}]
            build_result.end_time = datetime.now()
            await self.storage.update_build_result(build_id, build_result.model_dump())
            raise
        
        return build_id
    
    async def extract_entities(
        self, 
        data: Dict[str, Any], 
        entity_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """提取实体"""
        # 实现实体提取逻辑
        entities = []
        for record in data.get('records', []):
            # 实体提取逻辑
            entity = {
                'id': record.get('id'),
                'type': record.get('type'),
                'properties': record.get('properties', {})
            }
            entities.append(entity)
        
        return EntityExtractionResult(
            entities=entities,
            relations=[],
            processing_time=0.1
        ).model_dump()
    
    async def extract_relations(
        self, 
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """提取关系"""
        # 实现关系提取逻辑
        relations = []
        # 简单示例：基于实体类型创建关系
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                if entity1['type'] == 'Person' and entity2['type'] == 'Organization':
                    relations.append({
                        'source': entity1['id'],
                        'target': entity2['id'],
                        'type': 'WORKS_FOR'
                    })
        return relations
    
    async def get_build_result(self, build_id: str) -> Dict[str, Any]:
        """获取构建结果"""
        return await self.storage.get_build_result(build_id)
```

### 5.3 版本管理器实现

```python
# ontology_management_engine/impl/version.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from .models.version import (
    OntologyVersion, VersionChange, VersionComparison,
    VersionOperation, VersionStatus
)
from .interfaces.version import IVersionManager

class VersionManager(IVersionManager):
    """版本管理器实现"""
    
    def __init__(self, storage):
        self.storage = storage
    
    async def create_version(
        self, 
        ontology_id: str, 
        changes: Dict[str, Any], 
        created_by: str
    ) -> str:
        """创建版本"""
        # 获取当前版本
        current_version = await self.storage.get_current_version(ontology_id)
        
        # 生成新版本号
        if current_version:
            version_parts = current_version['version_number'].split('.')
            new_version = f"{version_parts[0]}.{int(version_parts[1]) + 1}.0"
        else:
            new_version = "1.0.0"
        
        # 生成变更记录
        version_changes = []
        for field, change in changes.items():
            change = VersionChange(
                field=field,
                old_value=change.get('old_value'),
                new_value=change.get('new_value'),
                changed_by=created_by
            )
            version_changes.append(change.model_dump())
        
        # 创建新版本
        version = OntologyVersion(
            ontology_id=ontology_id,
            version_number=new_version,
            parent_version_id=current_version['id'] if current_version else None,
            changes=version_changes,
            change_summary=changes.get('summary', ''),
            created_by=created_by,
            is_current=True,
            is_stable=changes.get('is_stable', False)
        )
        
        version_id = await self.storage.save_version(version.model_dump())
        
        # 更新当前版本标记
        if current_version:
            await self.storage.update_version(current_version['id'], {'is_current': False})
        
        return version_id
    
    async def rollback_version(
        self, 
        version_id: str, 
        target_version_id: str
    ) -> bool:
        """回滚版本"""
        # 验证版本存在
        version = await self.storage.get_version(version_id)
        target_version = await self.storage.get_version(target_version_id)
        
        if not version or not target_version:
            return False
        
        # 验证版本属于同一本体
        if version['ontology_id'] != target_version['ontology_id']:
            return False
        
        # 执行回滚
        # 这里需要实现具体的回滚逻辑
        
        # 更新版本状态
        await self.storage.update_version(version_id, {'status': VersionStatus.ARCHIVED})
        await self.storage.update_version(target_version_id, {'is_current': True})
        
        return True
    
    async def compare_versions(
        self, 
        source_version_id: str, 
        target_version_id: str
    ) -> Dict[str, Any]:
        """对比版本"""
        # 实现版本对比逻辑
        comparison = VersionComparison(
            source_version_id=source_version_id,
            target_version_id=target_version_id,
            added_entities=[],
            removed_entities=[],
            modified_entities=[],
            added_relations=[],
            removed_relations=[],
            modified_relations=[],
            compatibility_score=0.9
        )
        
        return comparison.model_dump()
    
    async def get_version_history(
        self, 
        ontology_id: str
    ) -> List[Dict[str, Any]]:
        """获取版本历史"""
        return await self.storage.get_versions(ontology_id)
    
    async def set_current_version(
        self, 
        version_id: str
    ) -> bool:
        """设置当前版本"""
        version = await self.storage.get_version(version_id)
        if not version:
            return False
        
        # 查找当前版本
        current_version = await self.storage.get_current_version(version['ontology_id'])
        if current_version and current_version['id'] != version_id:
            await self.storage.update_version(current_version['id'], {'is_current': False})
        
        # 设置新版本为当前版本
        await self.storage.update_version(version_id, {'is_current': True})
        return True
```

### 5.4 验证引擎实现

```python
# ontology_management_engine/impl/validation.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from .models.validation import (
    ValidationRule, ValidationResult, ValidationIssue,
    ValidationSeverity
)
from .interfaces.validation import IValidationEngine

class ValidationEngine(IValidationEngine):
    """验证引擎实现"""
    
    def __init__(self, storage):
        self.storage = storage
        self._load_rules()
    
    def _load_rules(self):
        """加载验证规则"""
        # 实现规则加载逻辑
        pass
    
    async def validate_ontology(
        self, 
        ontology: Dict[str, Any], 
        rules: Optional[List[str]] = None
    ) -> str:
        """验证本体"""
        # 创建验证结果
        validation_result = ValidationResult(
            ontology_id=ontology.get('id', ''),
            ontology_version=ontology.get('version', '1.0.0'),
            status='running'
        )
        
        validation_id = await self.storage.save_validation_result(validation_result.model_dump())
        
        try:
            # 执行验证
            issues = await self._execute_validation(ontology, rules)
            
            # 分类问题
            errors = []
            warnings = []
            info = []
            
            for issue in issues:
                if issue['severity'] == ValidationSeverity.ERROR:
                    errors.append(issue)
                elif issue['severity'] == ValidationSeverity.WARNING:
                    warnings.append(issue)
                else:
                    info.append(issue)
            
            # 更新验证结果
            validation_result.status = 'complete'
            validation_result.errors = errors
            validation_result.warnings = warnings
            validation_result.info = info
            validation_result.error_count = len(errors)
            validation_result.warning_count = len(warnings)
            validation_result.info_count = len(info)
            
            # 计算总体评分
            total_issues = len(errors) * 10 + len(warnings) * 1 + len(info) * 0.1
            max_score = 100  # 假设最大可能分数
            validation_result.overall_score = max(0, 1 - total_issues / max_score)
            
            await self.storage.update_validation_result(validation_id, validation_result.model_dump())
            
        except Exception as e:
            # 处理错误
            validation_result.status = 'failed'
            validation_result.errors = [{'message': str(e)}]
            await self.storage.update_validation_result(validation_id, validation_result.model_dump())
            raise
        
        return validation_id
    
    async def _execute_validation(
        self, 
        ontology: Dict[str, Any], 
        rules: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """执行验证"""
        issues = []
        
        # 实现验证逻辑
        # 示例：验证实体数量
        if len(ontology.get('entities', [])) == 0:
            issue = ValidationIssue(
                rule_id='ENTITY_COUNT',
                rule_name='Entity Count Validation',
                severity=ValidationSeverity.WARNING,
                message='Ontology has no entities',
                details={'entity_count': 0}
            )
            issues.append(issue.model_dump())
        
        return issues
    
    async def add_validation_rule(
        self, 
        rule: Dict[str, Any]
    ) -> str:
        """添加验证规则"""
        validation_rule = ValidationRule(**rule)
        rule_id = await self.storage.save_validation_rule(validation_rule.model_dump())
        return rule_id
    
    async def get_validation_result(
        self, 
        validation_id: str
    ) -> Dict[str, Any]:
        """获取验证结果"""
        return await self.storage.get_validation_result(validation_id)
    
    async def get_validation_rules(
        self, 
        rule_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取验证规则"""
        return await self.storage.get_validation_rules(rule_type)
```

### 5.5 审计仪表盘实现

```python
# ontology_management_engine/impl/dashboard.py
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .interfaces.dashboard import IAuditDashboard

class AuditDashboard(IAuditDashboard):
    """审计仪表盘实现"""
    
    def __init__(self, storage, audit_service, validation_service):
        self.storage = storage
        self.audit_service = audit_service
        self.validation_service = validation_service
    
    async def get_dashboard_data(
        self, 
        time_range: Optional[str] = "7d"
    ) -> Dict[str, Any]:
        """获取仪表盘数据"""
        # 解析时间范围
        days = int(time_range.replace('d', ''))
        start_time = datetime.now() - timedelta(days=days)
        
        # 获取摄入数据
        ingest_records = await self.audit_service.get_ingest_history()
        recent_ingests = [r for r in ingest_records if datetime.fromisoformat(r['start_time']) >= start_time]
        
        # 获取验证数据
        validation_results = await self.storage.get_validation_results()
        recent_validations = [v for v in validation_results if datetime.fromisoformat(v['validation_time']) >= start_time]
        
        # 计算指标
        total_ingests = len(recent_ingests)
        successful_ingests = len([r for r in recent_ingests if r['status'] == 'completed'])
        failed_ingests = len([r for r in recent_ingests if r['status'] == 'failed'])
        
        total_validations = len(recent_validations)
        passed_validations = len([v for v in recent_validations if v['status'] == 'complete' and v['error_count'] == 0])
        
        # 构建仪表盘数据
        dashboard_data = {
            'time_range': time_range,
            'ingestion_metrics': {
                'total': total_ingests,
                'successful': successful_ingests,
                'failed': failed_ingests,
                'success_rate': successful_ingests / total_ingests if total_ingests > 0 else 0
            },
            'validation_metrics': {
                'total': total_validations,
                'passed': passed_validations,
                'pass_rate': passed_validations / total_validations if total_validations > 0 else 0
            },
            'recent_activities': recent_ingests[:5] + recent_validations[:5],
            'health_score': self._calculate_health_score(recent_ingests, recent_validations)
        }
        
        return dashboard_data
    
    async def get_health_metrics(
        self, 
        ontology_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取健康指标"""
        # 实现健康指标计算
        return {
            'ontology_id': ontology_id,
            'health_score': 0.95,
            'issues': [],
            'recommendations': []
        }
    
    async def get_anomaly_detection(
        self, 
        time_range: Optional[str] = "24h"
    ) -> List[Dict[str, Any]]:
        """获取异常检测"""
        # 实现异常检测逻辑
        return []
    
    async def export_report(
        self, 
        format: str = "pdf"
    ) -> bytes:
        """导出报告"""
        # 实现报告导出
        return b"Report content"
    
    def _calculate_health_score(
        self, 
        ingest_records: List[Dict[str, Any]],
        validation_results: List[Dict[str, Any]]
    ) -> float:
        """计算健康分数"""
        # 实现健康分数计算
        return 0.9
```

---

## 6. 目录结构

```
ontology_management_engine/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── audit.py         # 数据摄入审计模型
│   ├── ontology.py      # 本体构建模型
│   ├── version.py       # 版本管理模型
│   └── validation.py    # 验证引擎模型
├── interfaces/
│   ├── __init__.py
│   ├── audit.py         # 数据摄入审计接口
│   ├── builder.py       # 本体构建器接口
│   ├── version.py       # 版本管理器接口
│   ├── validation.py    # 验证引擎接口
│   └── dashboard.py     # 审计仪表盘接口
├── impl/
│   ├── __init__.py
│   ├── audit.py         # 数据摄入审计实现
│   ├── builder.py       # 本体构建器实现
│   ├── version.py       # 版本管理器实现
│   ├── validation.py    # 验证引擎实现
│   └── dashboard.py     # 审计仪表盘实现
├── services/
│   ├── __init__.py
│   ├── ingest_service.py    # 数据摄入服务
│   ├── build_service.py     # 本体构建服务
│   ├── version_service.py   # 版本管理服务
│   └── validation_service.py # 验证服务
├── storage/
│   ├── __init__.py
│   ├── mongodb_storage.py   # MongoDB存储
│   └── postgres_storage.py  # PostgreSQL存储
├── api/
│   ├── __init__.py
│   ├── routes.py        # API路由
│   └── schemas.py       # API Schema
└── config.py            # 配置
```

---

## 7. API 接口设计

### 7.1 数据摄入审计 API

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/ontology/ingest` | POST | 开始数据摄入 | `{"source": "api", "data": {...}}` | `{"ingest_id": "..."}` |
| `/api/ontology/ingest/{id}` | GET | 获取摄入状态 | N/A | `{"status": "...", "records": [...]}` |
| `/api/ontology/ingest/{id}/status` | PUT | 更新摄入状态 | `{"status": "completed", "errors": [...]}` | `{"success": true}` |
| `/api/ontology/ingest/history` | GET | 获取摄入历史 | N/A | `[{"ingest_id": "...", "status": "..."}]` |

### 7.2 本体构建 API

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/ontology/build` | POST | 构建本体 | `{"ingest_id": "...", "ontology_def": {...}}` | `{"build_id": "..."}` |
| `/api/ontology/build/{id}` | GET | 获取构建状态 | N/A | `{"status": "...", "entities": [...]}` |
| `/api/ontology/extract` | POST | 提取实体 | `{"data": {...}}` | `{"entities": [...], "relations": [...]}` |

### 7.3 版本管理 API

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/ontology/versions` | POST | 创建版本 | `{"ontology_id": "...", "changes": {...}}` | `{"version_id": "..."}` |
| `/api/ontology/versions/{id}` | GET | 获取版本详情 | N/A | `{"version_number": "...", "changes": [...]}` |
| `/api/ontology/versions/{id}/rollback` | POST | 回滚版本 | `{"target_version_id": "..."}` | `{"success": true}` |
| `/api/ontology/versions/compare` | POST | 对比版本 | `{"source_version_id": "...", "target_version_id": "..."}` | `{"differences": {...}}` |
| `/api/ontology/{id}/versions` | GET | 获取版本历史 | N/A | `[{"version_id": "...", "version_number": "..."}]` |

### 7.4 验证引擎 API

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/ontology/validate` | POST | 验证本体 | `{"ontology": {...}}` | `{"validation_id": "..."}` |
| `/api/ontology/validate/{id}` | GET | 获取验证结果 | N/A | `{"status": "...", "errors": [...]}` |
| `/api/ontology/rules` | POST | 添加验证规则 | `{"name": "...", "expression": "..."}` | `{"rule_id": "..."}` |
| `/api/ontology/rules` | GET | 获取验证规则 | N/A | `[{"rule_id": "...", "name": "..."}]` |

### 7.5 审计仪表盘 API

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/ontology/dashboard` | GET | 获取仪表盘数据 | N/A | `{"metrics": {...}, "activities": [...]}` |
| `/api/ontology/health/{id}` | GET | 获取健康指标 | N/A | `{"health_score": 0.95, "issues": [...]}` |
| `/api/ontology/anomalies` | GET | 获取异常检测 | N/A | `[{"type": "...", "severity": "..."}]` |
| `/api/ontology/report` | GET | 导出报告 | N/A | PDF/CSV 数据 |

---

## 8. 集成与依赖

### 8.1 核心依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.9+ | 运行环境 |
| Pydantic | 2.0+ | 数据验证 |
| FastAPI | 0.100+ | API框架 |
| MongoDB | 6.0+ | 存储 |
| PostgreSQL | 14.0+ | 关系型存储 |
| Neo4j | 5.0+ | 知识图谱 |
| Graphiti | 最新版 | 图谱操作 |

### 8.2 集成点

| 集成点 | 接口 | 用途 |
|---------|------|------|
| Graphiti | `graphiti_client` | 图谱操作 |
| 前端 | `/api/ontology/*` | 管理界面 |
| 数据接入 | `DataIngestAudit` | 数据来源 |
| 安全 | `OPA` | 权限控制 |

---

## 9. 部署与配置

### 9.1 配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `MONGODB_URI` | str | "mongodb://localhost:27017" | MongoDB连接 |
| `POSTGRES_URI` | str | "postgresql://localhost:5432" | PostgreSQL连接 |
| `NEO4J_URI` | str | "bolt://localhost:7687" | Neo4j连接 |
| `GRAPHITI_URL` | str | "http://localhost:8000" | Graphiti服务 |
| `LOG_LEVEL` | str | "INFO" | 日志级别 |
| `MAX_INGEST_RECORDS` | int | 10000 | 最大摄入记录数 |
| `VALIDATION_TIMEOUT` | int | 300 | 验证超时(秒) |

### 9.2 部署方式

```yaml
# docker-compose.yml
version: '3.8'
services:
  ontology-management:
    image: odap-ontology-management:latest
    ports:
      - "8001:8000"
    environment:
      - MONGODB_URI=mongodb://mongodb:27017
      - POSTGRES_URI=postgresql://postgres:postgres@postgres:5432/odap
      - NEO4J_URI=bolt://neo4j:7687
      - GRAPHITI_URL=http://graphiti:8000
    depends_on:
      - mongodb
      - postgres
      - neo4j
      - graphiti
```

---

## 10. 监控与告警

### 10.1 监控指标

| 指标 | 类型 | 说明 |
|------|------|------|
| `ontology_ingest_count` | Counter | 摄入记录数 |
| `ontology_ingest_errors` | Counter | 摄入错误数 |
| `ontology_build_duration` | Histogram | 构建时长 |
| `ontology_validation_errors` | Counter | 验证错误数 |
| `ontology_version_changes` | Counter | 版本变更数 |
| `ontology_health_score` | Gauge | 健康分数 |

### 10.2 告警规则

| 规则 | 条件 | 级别 |
|------|------|------|
| 摄入失败率 | `rate(ontology_ingest_errors[5m]) > 0.1` | 警告 |
| 构建超时 | `ontology_build_duration > 300` | 严重 |
| 验证错误 | `ontology_validation_errors > 10` | 警告 |
| 健康分数低 | `ontology_health_score < 0.7` | 严重 |

---

## 11. 测试策略

### 11.1 单元测试

| 模块 | 测试覆盖率 | 测试场景 |
|------|------------|----------|
| 数据摄入审计 | 90% | 正常摄入、失败摄入、状态更新 |
| 本体构建器 | 85% | 实体提取、关系提取、构建失败 |
| 版本管理器 | 95% | 版本创建、回滚、对比 |
| 验证引擎 | 90% | 规则验证、结果处理 |
| 审计仪表盘 | 80% | 数据聚合、指标计算 |

### 11.2 集成测试

| 测试场景 | 验证点 |
|----------|--------|
| 完整摄入-构建流程 | 数据摄入 → 实体提取 → 本体构建 → 版本创建 |
| 版本管理流程 | 创建版本 → 回滚版本 → 对比版本 |
| 验证流程 | 本体验证 → 问题修复 → 重新验证 |

### 11.3 性能测试

| 测试指标 | 目标 |
|----------|------|
| 摄入处理速度 | > 1000 条/秒 |
| 构建时间 | < 30 秒 (1000 实体) |
| 验证时间 | < 10 秒 (1000 实体) |
| API 响应 | < 500ms (P95) |

---

## 12. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-19 | 初始版本 |
| 1.1.0 | 2026-05-01 | 新增审计仪表盘、增强验证引擎 |

---

**相关文档**:
- [Graphiti 客户端模块设计](../graphiti_client/DESIGN.md)
- [本体模块设计](../ontology/DESIGN.md)
- [安全策略文档](../../security/SECURITY.md)
