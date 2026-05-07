# 存储结构重新设计 - 检查清单

## 设计文档检查

- [ ] 核心架构文档审查完成
- [ ] 存储相关 ADR 审查完成
- [ ] 现有数据模型审查完成
- [ ] 数据模型定义完成
- [ ] 关系映射定义完成
- [ ] 存储方案对比完成
- [ ] 数据迁移策略定义完成
- [ ] 实施路径定义完成

## 交付物检查

- [ ] 数据模型图（ER 图）
- [ ] 实体关系说明
- [ ] 存储方案对比表
- [ ] 数据迁移策略文档
- [ ] 实施路径文档
- [ ] 过时文档清单

## 代码实现检查

### SQLite 存储
- [ ] Workspace 表定义
- [ ] Scenario 表定义
- [ ] IngestRecord 表定义
- [ ] OntologyVersion 表定义
- [ ] 外键关系定义
- [ ] 索引策略实现
- [ ] 路径配置为 /app/data/ontology.db

### MongoDB 存储
- [ ] ontology_documents 集合定义
- [ ] 文档结构定义
- [ ] 索引策略实现

### Neo4j 存储
- [ ] Entity 节点定义
- [ ] Relation 边定义
- [ ] AuditEvent 节点定义
- [ ] 索引策略实现

### 存储接口
- [ ] 统一存储接口抽象
- [ ] 工厂模式实现
- [ ] 连接失败回退逻辑

## 文档清理检查

- [ ] 识别与新设计冲突的文档
- [ ] 识别重复的文档
- [ ] 移动过时文档到 archive
- [ ] 更新文档索引
- [ ] 创建新文档引用关系

## 测试检查

### 单元测试
- [ ] WorkspaceStorage CRUD 测试
- [ ] ScenarioStorage CRUD 测试
- [ ] IngestRecordStorage CRUD 测试
- [ ] OntologyVersionStorage CRUD 测试
- [ ] OntologyDocumentStorage CRUD 测试
- [ ] GraphStorage CRUD 测试

### 集成测试
- [ ] 完整摄入流程测试
- [ ] 版本创建流程测试
- [ ] 图谱生成流程测试
- [ ] 数据持久化测试
- [ ] 容器重启后数据恢复测试

### 性能测试
- [ ] SQLite 查询性能测试
- [ ] MongoDB 查询性能测试
- [ ] Neo4j 图查询性能测试
- [ ] 索引有效性验证