# 全链路架构设计：数据摄入→本体构建→用户问答→Skill执行

> **版本**: 1.0.0 | **日期**: 2026-05-06 | **状态**: 设计稿
>
> **目标**: 设计从数据摄入到Skill执行的完整闭环链路，确保各环节无缝衔接

---

## 目录

1. [现有架构检查与补充](#1-现有架构检查与补充)
2. [全链路总览](#2-全链路总览)
3. [Phase 1: 数据摄入](#3-phase-1-数据摄入)
4. [Phase 2: 自动本体构建](#4-phase-2-自动本体构建)
5. [Phase 3: 用户问答（基于本体查询）](#5-phase-3-用户问答基于本体查询)
6. [Phase 4: Skill执行与建议](#6-phase-4-skill执行与建议)
7. [Phase 5: 闭环反馈](#7-phase-5-闭环反馈)
8. [跨Phase状态管理](#8-跨phase状态管理)
9. [实施路线图](#9-实施路线图)

---

## 1. 现有架构检查与补充

### 1.1 架构完整性检查

基于对现有文档体系（ARCHITECTURE.md v4.1.0 + 子文档）的审查：

| 检查项 | 状态 | 发现 |
|--------|------|------|
| 四层组件定位 | ✅ 完善 | L1 OpenHarness, L2 Graphiti, L3 Skills, L4 OPA 职责清晰 |
| 工作空间隔离 | ✅ 完善 | 隔离/共享/共用三分类模型设计合理 |
| OADP闭环体系 | ✅ 完善 | Observe→Analyze→Decide→Perform 语义清晰 |
| 前端架构 | ⚠️ 部分 | 有三栏布局雏形但未完成，缺Ant Design X集成 |
| 图谱可视化 | ❌ 不足 | 仅有基础集成，缺乏完整的交互系统设计 |
| Skill管理 | ⚠️ 部分 | 有热插拔架构(ADR-014)，缺可视化管理层 |
| 数据摄入链路 | ❌ 不足 | 缺从前端到Graphiti的完整摄入流程设计 |
| 问答引擎 | ⚠️ 部分 | QA Engine设计存在，但缺与Skill系统的深度联动 |
| 闭环反馈 | ⚠️ 部分 | ADR-051存在，但缺与各环节的实际集成点定义 |

### 1.2 架构补充项

基于审查发现，需要补充以下设计：

| 编号 | 补充项 | 类型 | 覆盖率 |
|------|--------|------|--------|
| S1 | 数据摄入前端→后端→Graphiti完整流程 | 新增 | 0% → 100% |
| S2 | 自动本体构建Pipeline（含人工确认节点） | 新增 | 0% → 100% |
| S3 | 问答中Skill推荐与执行的一体化交互 | 增强 | 30% → 100% |
| S4 | 全链路状态管理与事件总线 | 新增 | 0% → 100% |
| S5 | Skill新增后自动生效的端到端流程 | 增强 | 40% → 100% |

---

## 2. 全链路总览

### 2.1 核心数据流

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ODAP 全链路数据流                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │ Phase1   │    │   Phase2     │    │   Phase3     │    │   Phase4     │     │
│  │ 数据摄入 │───▶│  本体构建     │───▶│  用户问答     │───▶│  Skill执行   │     │
│  │ Ingest   │    │  Ontology    │    │  Q&A         │    │  Execute     │     │
│  └────┬─────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘     │
│       │                 │                   │                   │            │
│       ▼                 ▼                   ▼                   ▼            │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                          数据层 (Data Layer)                             │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │  │
│  │  │ 原始文档存储  │  │ Graphiti KG  │  │ 会话存储     │                   │  │
│  │  │ (FileSystem)  │  │   (Neo4j)    │  │ (PostgreSQL) │                   │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                   │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                          │
│                                      ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                         Phase5: 闭环反馈                                 │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐       │  │
│  │  │ 用户评分    │  │ Skill结果   │  │ 本体更新    │  │ 提示词优化  │       │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘       │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 状态机总览

```
                    ┌──────────┐
                    │  IDLE    │
                    └────┬─────┘
                         │ 用户上传数据
                         ▼
                    ┌──────────┐
                    │INGESTING │
                    └────┬─────┘
                         │ 解析完成
                         ▼
                    ┌──────────┐
               ┌───▶│REVIEWING │◀──────┐
               │    └────┬─────┘       │ 用户修正
               │         │ 确认构建     │
               │         ▼             │
               │    ┌──────────┐       │
               │    │ BUILDING │       │
               │    └────┬─────┘       │
               │         │ 构建完成     │
               │         ▼             │
               │    ┌──────────┐       │
               │    │ QA_READY │       │
               │    └────┬─────┘       │
               │         │ 用户提问     │
               │         ▼             │
               │    ┌──────────┐       │
               │    │ANSWERING │       │
               │    └────┬─────┘       │
               │         │ LLM返回+Suggestion
               │         ▼             │
               │    ┌──────────┐       │
               │    │SUGGESTING│       │
               │    └────┬─────┘       │
               │         │ 用户接受Skill
               │         ▼             │
               │    ┌──────────┐       │
               └────┤EXECUTING │───────┘
                    │ (Skill)  │  结果反馈
                    └──────────┘
```

---

## 3. Phase 1: 数据摄入

### 3.1 摄入流程

```
┌────────────────────────────────────────────────────────────────────┐
│                      数据摄入流程 (Data Ingestion)                   │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │ 选择来源  │───▶│ 上传文件  │───▶│ 文档解析  │───▶│ 信息抽取  │   │
│  │ Source   │    │ Upload   │    │ Parse    │    │ Extract  │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │
│                                                         │        │
│                                                         ▼        │
│                                                  ┌──────────┐   │
│                                                  │ 结果预览  │   │
│                                                  │ Preview  │   │
│                                                  └────┬─────┘   │
│                                                       │ 确认    │
│                                                       ▼        │
│                                                  → Phase 2     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 3.2 支持的输入源

| 源类型 | 格式 | 处理组件 |
|--------|------|---------|
| 文档上传 | PDF, DOCX, Markdown, TXT, XLSX | 多模态文档处理流水线 (ADR-019) |
| 文本粘贴 | 纯文本/富文本 | 前端直接处理 |
| 数据库连接 | PostgreSQL, MySQL, SQLite | MCP数据源连接器 (ADR-026) |
| API数据源 | REST/GraphQL | MCP协议集成 |

### 3.3 前端摄入界面

数据摄入采用分步向导模式（Step Wizard），核心状态包括：数据源选择 → 文件上传 → 文档解析 → 实体抽取预览 → 审核确认。每个步骤通过 `IngestionState` 接口管理状态流转。

> **📘 实现参考**: `ARCHITECTURE_FULL_CHAIN.md` [§3.3 前端摄入组件](ARCHITECTURE_FULL_CHAIN.md) — 含完整的 IngestionWizard TSX 组件代码和状态管理实现。

### 3.4 后端API

```typescript
// POST /api/v1/ingest/upload
interface IngestUploadRequest {
  workspace_id: string
  files: File[]
  options?: {
    split_strategy: 'paragraph' | 'sentence' | 'fixed_size'
    chunk_size?: number           // 默认1000
    extract_entities: boolean     // 默认true
    extract_relations: boolean    // 默认true
    extract_events: boolean       // 默认false
  }
}

interface IngestResult {
  job_id: string
  status: 'processing' | 'done' | 'error'
  entities: ExtractedEntity[]
  relations: ExtractedRelation[]
  events: ExtractedEvent[]
  stats: {
    total_chunks: number
    total_entities: number
    total_relations: number
    time_elapsed_ms: number
  }
}
```

---

## 4. Phase 2: 自动本体构建

### 4.1 构建流水线

```
┌───────────────────────────────────────────────────────────────────┐
│                    自动本体构建流水线                                │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Phase1 输出                                                     │
│  (提取实体+关系+事件)                                              │
│       │                                                           │
│       ▼                                                           │
│  ┌─────────────────────┐                                         │
│  │ 1. 实体标准化        │  ← 去重、同义词合并、链接已有实体         │
│  │    Entity Normalize  │                                         │
│  └─────────┬───────────┘                                         │
│            ▼                                                      │
│  ┌─────────────────────┐                                         │
│  │ 2. 关系验证          │  ← 验证关系两端实体存在、类型兼容         │
│  │    Relation Validate │                                         │
│  └─────────┬───────────┘                                         │
│            ▼                                                      │
│  ┌─────────────────────┐                                         │
│  │ 3. 一致性检查        │  ← 检测冲突、冗余、孤立节点               │
│  │    Consistency Check │                                         │
│  └─────────┬───────────┘                                         │
│            ▼                                                      │
│  ┌─────────────────────┐                                         │
│  │ 4. 人工审核          │  ← ⚠️ 关键决策点：用户确认/修正/拒绝     │
│  │    Human Review     │                                         │
│  └─────────┬───────────┘                                         │
│            ▼                                                      │
│  ┌─────────────────────┐                                         │
│  │ 5. 写入Graphiti      │  ← 创建节点+关系+事务时间戳              │
│  │    Commit to KG     │                                         │
│  └─────────┬───────────┘                                         │
│            ▼                                                      │
│  ┌─────────────────────┐                                         │
│  │ 6. 版本快照          │  ← 创建本体版本记录                      │
│  │    Version Snapshot  │                                         │
│  └─────────────────────┘                                         │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### 4.2 人工审核界面

审核面板按"实体/关系/冲突"分 Tab，支持逐条审批（通过/驳回/编辑）、批量确认、一键构建本体。

> **📘 实现参考**: `ARCHITECTURE_FULL_CHAIN.md` [§4.2 人工审核界面](ARCHITECTURE_FULL_CHAIN.md) — 含完整的 OntologyReviewPanel TSX 组件代码和审核工作流实现。

### 4.3 写入Graphiti

```python
# ontology_builder.py
async def build_ontology(workspace_id: str, entities: list[dict], relations: list[dict]):
    """
    将审核通过的实体和关系批量写入Graphiti
    每个写入操作记录transaction_time时间戳
    """
    graphiti_client = await get_graphiti_client(workspace_id)

    node_ids = {}
    for entity in entities:
        node = await graphiti_client.add_entity(
            name=entity["name"],
            entity_type=entity["type"],
            properties=entity["properties"],
            workspace_id=workspace_id,
            transaction_time=datetime.now(timezone.utc)
        )
        node_ids[entity["id"]] = node.uuid

    for relation in relations:
        await graphiti_client.add_relation(
            source_uuid=node_ids[relation["source_id"]],
            target_uuid=node_ids[relation["target_id"]],
            relation_type=relation["type"],
            properties=relation.get("properties", {}),
            workspace_id=workspace_id,
            transaction_time=datetime.now(timezone.utc)
        )

    # 创建版本快照
    ontology_version = await create_ontology_version(
        workspace_id=workspace_id,
        entities=entities,
        relations=relations
    )

    logger.info(f"本体构建完成: workspace={workspace_id}, "
                f"entities={len(entities)}, relations={len(relations)}, "
                f"version={ontology_version.id}")
```

---

## 5. Phase 3: 用户问答（基于本体查询）

### 5.1 问答链路

```
用户输入问题
    │
    ▼
┌──────────────────┐
│ 1. 意图识别       │  ← LLM判断：信息查询/数据分析/决策建议/动作执行
│    Intent Detect  │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 2. 实体链接       │  ← 在Graphiti中搜索问题涉及的实体
│    Entity Link    │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 3. 上下文检索     │  ← 获取实体属性 + N跳关系子图
│    Context Fetch  │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 4. RAG增强        │  ← 将子图数据+实体属性注入Prompt
│    RAG Augment    │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 5. LLM推理        │  ← 生成回答 + 实体标记 + Skill建议
│    LLM Infer      │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 6. 流式输出       │  ← SSE: token + 实体链接 + suggestion事件
│    Stream Output  │
└──────────────────┘
```

### 5.2 Prompt模板（RAG增强）

```
你是ODAP的本体驱动分析助手。基于以下本体知识回答用户问题。

## 工作空间: {workspace_name}
## 当前场景: {scenario_name}

## 相关实体
{for entity in relevant_entities}
- **{entity.name}** ({entity.type})
  属性: {entity.properties_summary}
  关联: {entity.related_entities_summary}
{end for}

## 相关关系
{for relation in relevant_relations}
- [{relation.source_name}] --{relation.type}--> [{relation.target_name}]
{end for}

## 可用Skill
{for skill in enabled_skills}
- {skill.name}: {skill.description}
{end for}

## 用户问题
{user_question}

## 回答要求
1. 直接回答用户问题
2. 引用的实体使用 [[entity:实体ID:实体名称]] 格式标记
3. 在回答末尾，如有相关操作建议，使用 <<suggestion:SkillID:建议描述>> 格式标记
4. 如果问题不明确，主动请求澄清
```

### 5.3 问答前端组件

基于 Ant Design X 的 `useXChat` Hook 实现流式问答，SSE 流式传输消息内容、Skill 建议和实体链接事件。

> **📘 实现参考**: `ARCHITECTURE_FULL_CHAIN.md` [§5.3 问答前端组件](ARCHITECTURE_FULL_CHAIN.md) — 含完整的 QASession TSX 组件、SSE 流处理、Markdown 实体链接和 Sender 配置。

---

## 6. Phase 4: Skill执行与建议

### 6.1 Skill建议生成与执行

```
问答回答中标记 <<suggestion:SkillID:描述>>
    │
    ▼
┌───────────────────────┐
│ 前端解析suggestion标签 │  ← 提取到右侧SuggestionPanel
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ 用户查看+确认          │  ← 可编辑参数
│ 可选：一键执行          │
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ OPA策略校验            │  ← 检查权限+危险级别
│ Permission Check       │
└───────────┬───────────┘
            ▼
    ┌───────┴───────┐
    │ 通过           │ 拒绝
    ▼               ▼
┌──────────┐   ┌──────────┐
│ 执行Skill │   │ 拒绝提示  │
│ Execute  │   │ Deny     │
└────┬─────┘   └──────────┘
     ▼
┌──────────┐
│ 结果展示  │  ← Markdown/表格/图表
│ Result   │
└────┬─────┘
     ▼
→ Phase5 闭环反馈
```

### 6.2 右侧Suggestion面板

问答完成后，右侧面板展示 Skill 执行建议卡片，包含技能名称、类别标签、置信度进度条。用户可一键执行或忽略。

> **📘 实现参考**: `ARCHITECTURE_FULL_CHAIN.md` [§6.2 右侧Suggestion面板](ARCHITECTURE_FULL_CHAIN.md) — 含完整的 SuggestionPanel TSX 组件代码和事件总线集成。

### 6.3 Skill新增后自动生效流程

```
用户通过Skill管理界面新增Skill
    │
    ▼
┌─────────────────────┐
│ 1. 前端提交到API     │  POST /api/v1/skills/create
│    含Markdown内容    │
└────────┬────────────┘
         ▼
┌─────────────────────┐
│ 2. SkillRegistry     │  ← 写入skills目录
│    保存文件          │    格式: skills/{category}/{name}.md
└────────┬────────────┘
         ▼
┌─────────────────────┐
│ 3. 触发热加载         │  ← 调用OpenHarness Bridge
│    notify_change()   │    SkillRegistry.notify_change(skill_id)
└────────┬────────────┘
         ▼
┌─────────────────────┐
│ 4. OpenHarness       │  ← 重新扫描skills目录
│    重新加载          │    注册新的Python Skill Handler
└────────┬────────────┘
         ▼
┌─────────────────────┐
│ 5. WebSocket推送     │  ← 通知所有前端Skill列表变更
│    前端自动刷新      │    包括问答界面的可用Skill列表
└─────────────────────┘

总耗时：< 3 秒
```

---

## 7. Phase 5: 闭环反馈

### 7.1 反馈收集机制

| 反馈来源 | 收集方式 | 反馈内容 | 消费方 |
|---------|---------|---------|--------|
| 用户评分 | 消息气泡内 👍/👎按钮 | 回答质量评分 | QA Engine提示词优化 |
| Skill执行结果 | 执行完成后自动采集 | 成功/失败/耗时/输出 | 本体更新 + Skill改进 |
| 手动修正 | 图谱编辑/关系修改 | 实体/关系修正 | Graphiti增量更新 |
| 用户标注 | 实体标记/备注 | 人工标注信息 | 本体增强 |
| 对话结束 | 会话摘要生成 | 关键决策/行动记录 | 审计日志 + 知识积累 |

### 7.2 反馈利用架构

```python
class FeedbackEngine:
    """闭环反馈引擎"""

    async def process_feedback(self, event: FeedbackEvent):
        match event.type:
            case "qa_rating":
                await self._update_prompt_quality(event)
            case "skill_result":
                await self._update_ontology_from_skill(event)
                await self._record_skill_analytics(event)
            case "manual_edit":
                await self._apply_edit_to_graphiti(event)
            case "session_complete":
                await self._generate_session_insights(event)

    async def _update_ontology_from_skill(self, event):
        """Skill执行结果反馈到本体"""
        # 例如：StrikeOrder执行后，更新Target实体的状态
        if event.skill_type == "StrikeOrder":
            await graphiti.update_entity(
                entity_id=event.result["target_id"],
                properties={"status": "destroyed"},
                transaction_time=datetime.now(timezone.utc)
            )
```

---

## 8. 跨Phase状态管理

### 8.1 全局事件总线

```typescript
// 跨组件/跨Phase的事件定义
const EventBus = {
  // Phase1 → Phase2
  'ingest:complete': { jobId: string, entities: ExtractedEntity[] }
  'ingest:ready_for_review': { jobId: string }

  // Phase2
  'ontology:review:approve': { entityId: string }
  'ontology:review:reject': { entityId: string, reason: string }
  'ontology:build:start': { workspaceId: string }
  'ontology:build:complete': { versionId: string, stats: BuildStats }

  // Phase3
  'qa:message:sent': { sessionId: string, message: string }
  'qa:entity:linked': { entityId: string }
  'qa:answer:streaming': { token: string }
  'qa:answer:complete': { messageId: string, suggestions: Suggestion[] }

  // Phase3 → Phase4
  'suggestion:new': Suggestion
  'suggestion:dismiss': { suggestionId: string }
  'skill:execute:start': { skillId: string, params: any }
  'skill:execute:complete': { skillId: string, result: any }

  // Phase5
  'feedback:rating': { messageId: string, rating: 1|-1 }
  'feedback:manual_edit': { entityId: string, changes: any }

  // 跨领域
  'workspace:switch': { workspaceId: string }
  'scenario:switch': { scenarioId: string }
  'skill:registered': { skillId: string }       // Skill新增后自动生效通知
  'skill:unregistered': { skillId: string }
}
```

### 8.2 Zustand全局Store

使用 Zustand 管理全局状态，跨 Phase 共享工作空间、场景、会话、摄入进度和 Skill 执行状态。

> **📘 实现参考**: `ARCHITECTURE_FULL_CHAIN.md` [§8.2 Zustand全局Store](ARCHITECTURE_FULL_CHAIN.md) — 含完整的 ODAPGlobalStore 接口定义、selector 和 action 实现。

---

## 9. 实施路线图

### 9.1 阶段规划

```
Phase 1: 基础链路打通 (W1-W2)
├── W1: 文件上传→文档解析→实体抽取 后端
├── W1: 摄入Wizard前端组件
├── W2: 抽取结果→Graphiti写入
└── W2: 基础审核界面

Phase 2: 问答增强 (W3-W4)
├── W3: QA Engine对接Graphiti RAG
├── W3: SSE流式输出 + 实体链接
├── W4: Skill建议标签解析 + 右侧SuggestionPanel
└── W4: Skill执行集成

Phase 3: 闭环反馈 (W5-W6)
├── W5: 用户评分 + Skill结果反馈
├── W5: 本体增量更新机制
├── W6: 会话摘要生成
└── W6: 端到端集成测试

Phase 4: 自动生效 (W7)
├── W7: Skill热加载完善
├── W7: WebSocket变更推送
└── W7: 全链路性能优化
```

### 9.2 依赖关系

```
Phase1 数据摄入 ────┐
                    ├──▶ Phase3 问答 (需要本体数据)
Phase2 本体构建 ────┘
                    │
Phase3 问答 ────────▶ Phase4 Skill执行 (由建议触发)
                    │
Phase4 Skill执行 ───▶ Phase5 闭环反馈 (由结果触发)
                    │
Phase5 反馈 ────────▶ Phase2 本体 (更新) ← 形成闭环
```

---

## 附录：关键API接口汇总

| 方法 | 路径 | Phase | 说明 |
|------|------|-------|------|
| POST | `/api/v1/ingest/upload` | P1 | 上传文件+启动解析 |
| GET | `/api/v1/ingest/job/{id}` | P1 | 查询解析进度 |
| GET | `/api/v1/ingest/job/{id}/preview` | P1 | 获取抽取结果预览 |
| POST | `/api/v1/ontology/build` | P2 | 提交构建请求 |
| GET | `/api/v1/ontology/build/{id}/status` | P2 | 查询构建进度 |
| GET | `/api/v1/ontology/entities` | P2/P3 | 查询本体实体列表 |
| GET | `/api/v1/ontology/entities/{id}` | P3 | 查询实体详情(含关系) |
| POST | `/api/v1/qa/chat/stream` | P3 | SSE流式问答 |
| GET | `/api/v1/qa/sessions` | P3 | 会话历史列表 |
| GET | `/api/v1/skills` | P4 | Skill列表 |
| POST | `/api/v1/skills/create` | P4 | 创建Skill |
| PUT | `/api/v1/skills/{id}` | P4 | 更新Skill |
| POST | `/api/v1/skills/{id}/toggle` | P4 | 启用/禁用Skill |
| POST | `/api/v1/skills/{id}/execute` | P4 | 执行Skill |
| POST | `/api/v1/skills/sync` | P4 | 触发热加载同步 |
| POST | `/api/v1/feedback/rating` | P5 | 提交评分反馈 |
| WS | `/ws/events` | ALL | 实时事件推送 |

---

*关联文档:*
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [ADR-052 WebUI选型](../07-adr/ADR-052_webui_opensource_selection.md)
- [ADR-053 Skill管理选型](../07-adr/ADR-053_skill_management_selection.md)
- [图谱可视化优化设计](../03-modules/visualization/DESIGN_GRAPH_OPTIMIZATION.md)
- [ODAP综合优化设计文档](../01-product-design/ODAP综合优化设计文档.md)