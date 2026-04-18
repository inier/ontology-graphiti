# ADR-041: 工作空间资源隔离

## 状态
已接受

## 上下文

ODAP 定位为"通用本体驱动平台"，通过工作空间机制支持多场景并行。每个工作空间需要独立本体、图谱数据、Skill 配置、OPA 策略，确保场景间零干扰。

### 隔离维度

| 资源 | 隔离需求 | 说明 |
|------|---------|------|
| 图谱数据 | **数据级隔离** | 不同工作空间的实体/关系完全不可见 |
| OPA 策略 | **策略级隔离** | 每个工作空间有独立的权限策略集 |
| Skill 配置 | **配置级隔离** | 每个工作空间启用不同的 Skill 子集 |
| 本体版本 | **版本级隔离** | 不同工作空间可使用不同版本的本体 |
| LLM 配置 | **可选隔离** | 默认共享，可按空间覆盖 |

### 隔离方案对比

| 方案 | 图谱隔离 | 策略隔离 | 优点 | 缺点 |
|------|---------|---------|------|------|
| **A. Neo4j 多数据库** | 每工作空间一个数据库 | OPA Bundle 路径前缀 | 强隔离、语义清晰 | 数据库数量有上限（Neo4j 社区版限 1 个，企业版无限制） |
| **B. 标签过滤** | 同数据库，`workspace_id` 标签 | OPA 策略内条件判断 | 简单、无数据库数量限制 | 查询必须带标签、隔离依赖代码正确性、性能随数据量下降 |
| **C. 混合隔离** | Neo4j 多数据库 + 标签回退 | OPA Bundle 路径前缀 | 兼顾强隔离和灵活性 | 实现复杂 |

### 约束

- 当前使用 Neo4j 社区版（单数据库），生产环境计划升级企业版
- 工作空间数量预估 < 20 个

## 决策

**采用方案 C：混合隔离**。

1. **图谱数据**：优先使用 Neo4j 多数据库隔离；社区版回退到标签过滤
2. **OPA 策略**：Bundle 路径前缀隔离（`/workspaces/{id}/policies/`）
3. **Skill 配置**：注册表内 `workspace_id` 过滤
4. **本体版本**：OntologyManager 内 `workspace_id` 关联

### 隔离实现

```python
class WorkspaceIsolator:
    """工作空间资源隔离器"""

    def __init__(self, neo4j_edition: str):
        self.strategy = (
            DatabaseIsolation()     # 企业版：多数据库
            if neo4j_edition == "enterprise"
            else LabelIsolation()   # 社区版：标签过滤
        )

    async def get_graph_session(self, workspace_id: str) -> AsyncSession:
        """获取工作空间隔离的 Neo4j 会话"""
        return await self.strategy.get_session(workspace_id)

    async def get_opa_bundle_path(self, workspace_id: str) -> str:
        """获取工作空间的 OPA Bundle 路径"""
        return f"/workspaces/{workspace_id}/policies/"
```

### 切换隔离策略

```python
# 环境变量控制
NEO4J_EDITION=community   # → 标签过滤
NEO4J_EDITION=enterprise  # → 多数据库

# 切换时自动迁移
async def migrate_label_to_database(workspace_id: str):
    """标签隔离 → 数据库隔离迁移"""
    # 1. 创建工作空间专属数据库
    # 2. 从主数据库导出该工作空间数据
    # 3. 导入到专属数据库
    # 4. 更新 WorkspaceIsolator 策略
```

## 后果

### 变得更容易

- **开发阶段**：社区版 + 标签过滤，零额外配置
- **生产升级**：切换环境变量即可从标签隔离升级到数据库隔离
- **安全审计**：数据库级隔离通过 Neo4j 访问控制保障，标签隔离通过代码 + OPA 保障

### 变得更难

- **双重实现**：需同时维护标签过滤和多数据库两套逻辑
- **迁移复杂度**：从标签隔离迁移到数据库隔离需要数据搬迁
- **测试覆盖**：两套隔离策略都需要测试

### 风险与缓解

| 风险 | 缓解 |
|------|------|
| 社区版标签过滤遗漏导致数据泄露 | 强制所有查询带 `workspace_id` 过滤 + 集成测试验证 |
| 迁移过程数据丢失 | 迁移前备份 + 原子性迁移 + 回滚机制 |
| 双重实现维护成本 | 标签过滤代码量小（~50 行），核心查询逻辑共享 |

## 可逆性

**高**。从标签隔离升级到数据库隔离是单向演进，升级后不可逆（数据已分散到多数据库），但可接受——生产环境应该用数据库隔离。

## 关联

- 关联 ADR-023（多工作空间隔离架构）
- 关联 ADR-002（Graphiti 知识图谱）
- 关联 ADR-003（OPA 策略治理）
- 关联 M-04 DESIGN.md
- 影响 WR-04（工作空间管理）
