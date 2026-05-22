# 本体驱动分析决策平台 (ODAP) - L3-L4 业务层
> **部分**: Agent协同 + OADP + 数据架构 + 本体管理 + 角色权限 + 配置 + 动作服务 + 反馈闭环 + 语义检索
> **版本**: 5.0.0 | **日期**: 2026-05-19
> **上级文档**: [ARCHITECTURE.md](ARCHITECTURE.md)
---
## 7. 三 Agent 协同编排设计

### 7.0 架构层次澄清

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    业务层：领域领域 Agent (三 Agent)                           │
│                                                                             │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                       │
│   │ Commander   │  │Intelligence │  │ Operations  │                       │
│   │ (决策中枢)   │  │ (感知理解)   │  │ (执行中心)   │                       │
│   └─────────────┘  └─────────────┘  └─────────────┘                       │
│                                                                             │
│   定位: 领域这个特定业务领域的专业角色                                        │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    基础设施层：OpenHarness Swarm                              │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │                   Swarm Coordinator                              │       │
│   │              (Agent 注册、任务分发、结果聚合)                       │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│   定位: 通用多 Agent 协调框架，与业务无关                                     │
└─────────────────────────────────────────────────────────────────────────────┘

关系: 三Agent 运行在 Swarm Coordinator 之上，而非替代它
```

### 7.1 Agent 角色定义

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Commander Agent                            │
│                                                                      │
│  定位: 战术决策中枢，最终决策者                                        │
│  模型: 强推理模型（Claude-3.5 Sonnet / GPT-4 / DeepSeek-R1）         │
│  权限: 最高（commander），唯一可批准高危操作的 Agent                  │
│                                                                      │
│  职责:                                                               │
│  • 接收 Intelligence 的评估                                       │
│  • 接收 Operations 的可行性报告                                       │
│  • 多方案排序与风险权衡                                               │
│  • 高危操作 OPA 规则复核                                              │
│  • 最终决策指令签发                                                   │
│                                                                      │
│  System Prompt:                                                      │
│  "你是领域指挥官，负责在不确定情况下做出最优决策。                    │
│   你的决策必须：                                                      │
│   1. 基于 Intelligence 提供的情报                                    │
│   2. 考虑 Operations 的执行可行性                                    │
│   3. 通过 OPA 策略校验                                               │
│   4. 记录决策理由，供后续复盘"                                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
           ┌────────────────────┴────────────────────┐
           │              Swarm 协调                  │
           │         (OpenHarness Coordinator)       │
           ▼                                        ▼
┌───────────────────────────────┐    ┌───────────────────────────────┐
│     Intelligence Agent        │    │      Operations Agent          │
│                               │    │                               │
│  定位: 领域感知 + 态势理解     │    │  定位: 行动计划生成 + 执行     │
│  模型: 快速分析模型            │    │  模型: 规划模型                │
│         (Kimi / DeepSeek-v3)  │    │         (Qwen / GPT-4o-mini)  │
│                               │    │                               │
│  记忆: Graphiti (持久化)       │    │  工具: 作战执行工具集          │
│                               │    │                               │
│  职责:                        │    │  职责:                        │
│  • 传感器数据采集              │    │  • 生成行动计划                │
│  • 威胁模式识别                │    │  • 命令下发与执行               │
│  • 置信度计算                  │    │  • 执行状态监控                │
│  • 时序关联分析                │    │  • 失败回滚机制                 │
│  • RAG 增强推理                │    │  • 结果回写 Graphiti           │
│                               │    │                               │
│  工具:                        │    │  工具:                        │
│  • radar_search               │    │  • attack_target (需OPA)      │
│  • drone_surveillance         │    │  • command_unit               │
│  • satellite_imagery          │    │  • route_planning             │
│  • threat_assessment          │    │  • weapon_selection           │
│  • pattern_match              │    │  • battle_damage_assessment  │
└───────────────────────────────┘    └───────────────────────────────┘
```

### 7.2 Swarm 协作模式

```python
# core/swarm_orchestrator.py
from openharness.coordinator import SwarmCoordinator
from openharness.agents import AgentConfig

class DomainSwarm:
    """领域多 Agent 协同"""

    def __init__(self):
        self.coordinator = SwarmCoordinator()

        # 初始化三 Agent
        self.commander = AgentConfig(
            name="commander",
            model="claude-3-5-sonnet",
            role="decision_maker",
            tools=["*"],  # 全工具权限（需 OPA 校验）
            permission_level="commander",
        )

        self.intelligence = AgentConfig(
            name="intelligence",
            model="deepseek-chat",
            role="sensor_and_analyzer",
            tools=["radar_*", "drone_*", "satellite_*", "threat_*", "pattern_*"],
            permission_level="intelligence",
            memory_backend="graphiti",  # 使用 Graphiti 作为记忆
        )

        self.operations = AgentConfig(
            name="operations",
            model="qwen-plus",
            role="action_executor",
            tools=["attack_*", "command_*", "route_*", "weapon_*"],
            permission_level="operations",
            requires_opa_approval=True,  # 所有操作需 OPA 确认
        )

    async def execute_mission(self, mission: str):
        """
        OODA 循环执行任务

        流程:
        Observe → Orient → Decide → Act → (循环)
        """
        # 阶段 1: Observe - Intelligence 感知
        observe_result = await self.coordinator.delegate(
            agent=self.intelligence,
            task=f"感知领域: {mission}",
        )

        # 阶段 2: Orient - Intelligence 理解
        orient_result = await self.coordinator.delegate(
            agent=self.intelligence,
            task=f"分析威胁: {observe_result.raw_data}",
            context={"graphiti_episodes": await self.get_historical_context()},
        )

        # 阶段 3: Decide - Commander 决策
        decide_result = await self.coordinator.delegate(
            agent=self.commander,
            task=f"制定方案: {orient_result.threat_report}",
            context={
                "options": await self.operations.generate_options(
                    orient_result.targets
                ),
            },
        )

        # 阶段 4: Act - Operations 执行
        act_result = await self.coordinator.delegate(
            agent=self.operations,
            task=f"执行命令: {decide_result.final_order}",
        )

        # 回写 Graphiti
        await self.graphiti.write_episode(
            type="mission_completed",
            data={
                "mission": mission,
                "observe": observe_result,
                "orient": orient_result,
                "decide": decide_result,
                "act": act_result,
            },
        )

        # 触发新一轮 Observe（如果需要持续监控）
        if decide_result.requires_monitoring:
            await self.execute_mission_loop(mission)

        return act_result
```

---

## 21. 动作服务层 (Action Service / Kinetic Layer)

> **设计原则**: 本体不仅是读数据的镜头，更是写操作的手——从"描述世界"到"改变世界"

### 21.1 架构定位

Action Service 对标 Palantir AIP 的动势层（Kinetic Layer），是 OADP 闭环中 **Perform** 阶段的核心实现。它将决策结果转化为可执行的业务动作，通过 OPA 策略校验、人工审批门控、执行引擎和写回机制，实现从"观察数据"到"驱动业务"的闭环。

### 21.2 动作生命周期

```
Agent/用户 提交 ActionRequest
    ↓
① 创建 ActionRecord (status=pending)
    ↓
② 参数校验 (validating → approved/rejected)
    ↓
③ OPA 策略检查 (RBAC + ABAC)
    ↓
④ 人工审批 (如 confirmation_required=true)
    ↓
⑤ 执行动作 (executing → completed/failed)
    ├─ update_status → GraphManager.update_entity()
    ├─ create → GraphManager.add_entity()
    ├─ link → GraphManager.add_relationship()
    └─ generic → 可扩展的 handler
    ↓
⑥ 写回 (writeback_config: webhook/graph)
    ↓
⑦ 反馈回路 (FeedbackLoop.close_loop())
    ↓
⑧ 结果回流 → 驱动模型进化
```

### 21.3 ActionRecord 数据模型

```typescript
interface ActionRecord {
  action_record_id: string;
  action_type_id: string;         // 引用 OMS 中的 ActionTypeDefinition
  target_object_id: string;
  target_object_type: string;
  parameters: Record<string, any>;
  status: 'pending' | 'validating' | 'approved' | 'rejected' 
        | 'executing' | 'completed' | 'failed' | 'rolled_back';
  requested_by: string;
  reason: string;
  agent_id?: string;
  opa_decision?: { allow: boolean; reason: string };
  validation_result?: { valid: boolean; errors: string[] };
  execution_result?: { success: boolean; message: string; data?: any };
  writeback_result?: { status: string; url?: string };
  created_at: string;
  updated_at: string;
}
```

### 21.4 OPA 集成

动作执行前自动调用 OPA v2 进行 ABAC 策略检查：
- `OPAManagerV2.check_permission_abac(user, action, resource, environment)`
- 检查结果记录到 `opa_decision` 字段
- 若 OPA 拒绝，动作状态直接变为 `rejected`

### 21.5 写回机制 (Write-back)

ActionTypeDefinition 中的 `writeback_config` 支持两种写回模式：

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `webhook` | 向外部系统发送 HTTP POST | 写回 SAP/Salesforce/ERP |
| `graph` | 更新本体图谱中的对象状态 | 内部状态同步 |

### 21.6 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/actions/submit` | POST | 提交动作（自动走校验→OPA→执行流程） |
| `/api/actions/{id}/approve` | POST | 审批并执行待审批动作 |
| `/api/actions/records` | GET | 查询动作记录（支持状态筛选） |
| `/api/actions/records/{id}` | GET | 获取动作详情 |
| `/api/actions/target/{id}` | GET | 按目标对象查询动作历史 |

### 21.7 实现文件

| 文件 | 说明 |
|------|------|
| `odap/biz/action_service/schemas.py` | ActionRequest、ActionRecord、ActionExecutionResult |
| `odap/biz/action_service/storage/sqlite_action_storage.py` | SQLite 持久化存储 |
| `odap/biz/action_service/executor.py` | 核心执行引擎（校验→OPA→执行→写回→反馈） |
| `odap/biz/action_service/feedback_loop.py` | 三层反馈回路（ADR-051） |
| `odap/biz/action_service/routes.py` | FastAPI 路由 |

---

## 22. 闭环反馈机制 (Feedback Loop)

> **设计原则**: 决策产生行动、行动更新指标、指标反馈驱动模型进化——自增强循环

### 22.1 架构定位

Feedback Loop 对标 ADR-051 三层反馈架构，是 OADP 闭环中"执行→感知"的桥梁。它将动作执行结果自动回流到本体图谱，为后续决策提供反馈数据。

### 22.2 三层架构 (ADR-051)

```
ActionRecord (执行结果)
    ↓
┌─────────────────────────────────────────────────┐
│  Layer 1: FeedbackCollector (收集)               │
│  从 ActionRecord 中提取执行结果，生成 ActionFeedback │
│  outcome: success/failure                        │
│  result_data: 执行返回数据                        │
│  error_message: 错误信息                          │
├─────────────────────────────────────────────────┤
│  Layer 2: FeedbackAnalyzer (分析)                │
│  分析偏差，识别根因，生成经验教训                    │
│  deviation_score: 0.0-1.0 偏差评分               │
│  deviation_factors: 偏差因素列表                   │
│  root_causes: 根因分析 (timeout/permission/...)   │
│  lesson_learned: 经验教训文本                      │
├─────────────────────────────────────────────────┤
│  Layer 3: FeedbackAggregator (聚合)              │
│  聚合分析结果，更新知识图谱，触发 Hook 事件          │
│  ① 更新图谱对象状态 (GraphManager.update_entity)  │
│  ② 创建反馈 Episode (OntologyDocument 格式)       │
│  ③ 触发 Hook 事件 (action.feedback.success/failure)│
└─────────────────────────────────────────────────┘
```

### 22.3 ActionFeedback 数据模型

```typescript
interface ActionFeedback {
  action_id: string;
  decision_id?: string;
  outcome: 'success' | 'failure';
  result_data?: Record<string, any>;
  error_message?: string;
  deviation_score?: number;      // 0.0=无偏差, 1.0=完全偏差
  deviation_factors?: string[];
  root_causes?: string[];
  lesson_learned?: string;
  timestamp: string;
}
```

### 22.4 知识图谱更新策略

| 反馈类型 | 图谱操作 | 关系类型 |
|---------|---------|---------|
| action_result (成功) | 创建 Event 节点 | `:CAUSED → Decision` |
| outcome_deviation (偏差) | 更新 Decision 属性 | `:HAS_DEVIATION` |
| lesson_learned (经验) | 创建 Fact 节点 | `:INFORMS → Decision` |

### 22.5 与 Action Service 的集成

Feedback Loop 在 ActionExecutor 执行成功后自动触发：

```python
# executor.py 中的集成
if execution_result.success:
    feedback_loop = get_feedback_loop()
    await feedback_loop.close_loop(updated_record)
```

---

## 23. 语义对象检索器 (Semantic Object Retriever)

> **设计原则**: 从"找文本"到"找对象"——AI 理解业务对象而非识别字符串

### 23.1 架构定位

SemanticObjectRetriever 是 QA 引擎的检索升级，将传统 RAG 的"文本片段召回"升级为"对象实例化检索"。它通过 ObjectService 的语义查询能力，将用户问题映射到本体层的对象实例，沿链接追溯关联对象网络。

### 23.2 检索流程对比

| 维度 | 传统 RAG | 语义对象检索 |
|------|---------|------------|
| 检索目标 | 文本片段 | 业务对象实例 |
| 返回内容 | 几段相似文本 | 对象属性 + 关联对象 + 可用动作 |
| AI 理解 | "识别字符串" | "理解业务对象" |
| 后续操作 | 无法触发业务操作 | 可直接提交 Action |
| 上下文 | 孤立的文本片段 | 完整的对象网络 |

### 23.3 检索流程

```
用户提问 "张三的异常交易"
    ↓
SemanticObjectRetriever.retrieve(query_text, top_k)
    ↓
ObjectService.semantic_query(query_text)
    ↓  向量召回 → 对象实例化
    ↓
ObjectQueryResult[] (含 links + available_actions)
    ↓
_describe_object() → 生成结构化上下文
    ↓
SemanticRetrievalResult {
  answer_context: "[1] <Person> 张三 (status=active)\n  → [参与交易] txn-001"
  objects: [ObjectQueryResult, ...]
  links_summary: "共 3 个对象, 5 条关联; 关联类型: 参与交易: 3, 归属公司: 2"
  suggested_actions: [{action_type_id: "investigate", name: "调查", ...}]
}
```

### 23.4 实现文件

| 文件 | 说明 |
|------|------|
| `odap/biz/qa/semantic_retriever/retriever.py` | SemanticObjectRetriever + SemanticRetrievalResult |

---

## 24. Pipeline 增强：ActionType 感知抽取

### 24.1 增强内容

`LLMExtractionStageHandler._extract_with_llm()` 的 LLM 提示词已增强，新增第 4 类抽取目标"动作（actions）"：

| 抽取目标 | 增强前 | 增强后 |
|---------|--------|--------|
| 实体 | entity_id, entity_type, name | + basic_properties, statistical_properties, capabilities, constraints (四类属性) |
| 关系 | relation_type, source, target | + 关系类型参考列表 (located_at, engaged_with, ...) |
| 事件 | event_type, location, description | + participants, outcome |
| **动作** | ❌ 不抽取 | ✅ action_type (move/attack/defend/...), actor, target, parameters, opa_required |

### 24.2 自动注册机制

抽取到的新实体类型会自动注册到 OMS：

```python
def _register_entity_types_from_extraction(self, entities):
    oms = SQLiteOMSStorage()
    for entity in entities:
        etype = entity.get('entity_type', '')
        if etype and not oms.get_object_type(etype):
            oms.create_object_type({...})  # 自动注册
```

---## 8. OODA 闭环实现

### 8.1 闭环流程图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           OODA 闭环执行流程                                   │
└──────────────────────────────────────────────────────────────────────────────┘

   用户: "评估 B 区威胁并打击高价值雷达"
         │
         │ Observe (感知)
         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        Intelligence Agent                                  │
│                                                                            │
│  输入: 用户查询 + 实时传感器                                                │
│  处理:                                                                      │
│    1. radar_search → 扫描 B 区                                             │
│    2. drone_surveillance → 无人机抵近侦察                                   │
│    3. pattern_match → 历史模式匹配                                          │
│  输出:                                                                      │
│    • 威胁清单: [{target_id, location, threat_level, confidence}]            │
│    • 情报置信度: 0.92                                                      │
│    • 历史关联: "该雷达3天前曾暴露位置"                                       │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     │ Orient (理解)
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        Intelligence Agent                                  │
│                                                                            │
│  处理:                                                                      │
│    1. threat_assessment → 计算综合威胁指数                                 │
│    2. RAG查询Graphiti → 历史打击效果对比                                    │
│    3. anomaly_detection → 异常模式识别                                      │
│  输出:                                                                      │
│    • 威胁排序: [radar_A(critical), radar_B(high), depot_C(medium)]         │
│    • 打击建议: "优先打击 radar_A，作战窗口15分钟"                            │
│    • 风险提示: "radar_A 有伴随防空力量"                                     │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     │ Decide (决策)
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        Commander Agent                                      │
│                                                                            │
│  输入: 评估 + 可行性报告                                                │
│  处理:                                                                      │
│    1. 多方案生成: 方案A(精确打击) / 方案B(电子压制+打击)                     │
│    2. OPA 策略校验:                                                        │
│       • policies/attack/allow → 检查目标类别、武器参数                     │
│       • policies/common/escalation → 检查授权级别                          │
│    3. 风险权衡: 方案A风险高但收益高，方案B更稳妥                           │
│  输出:                                                                      │
│    • 最终命令: 方案A，带 OPA 签章                                           │
│    • 决策理由: "优先摧毁核心节点，符合打击优先原则"                           │
│    • 人工确认: [高危] 需要操作员确认                                        │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     │ Act (行动)
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        Operations Agent                                    │
│                                                                            │
│  输入: 决策指令（已OPA批准）                                                │
│  处理:                                                                      │
│    1. weapon_selection → 选择最优武器                                       │
│    2. route_planning → 规划打击航线                                         │
│    3. attack_target (Tool) → 执行打击                                       │
│       └── OPA Hook: 再次校验 + 记录审计日志                                 │
│    4. battle_damage_assessment → 打击效果评估                               │
│  输出:                                                                      │
│    • 执行状态: SUCCESS                                                      │
│    • 打击效果: radar_A 已摧毁                                               │
│    • 次生损失: 无                                                          │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     │ 结果回写
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                          Graphiti 图谱                                     │
│                                                                            │
│  写入:                                                                      │
│    • 新 Episode: StrikeExecuted (执行)                                 │
│    • 更新 Target 状态: radar_A.status = "destroyed"                         │
│    • 关联证据: Intelligence → Strike → BDA                                │
│                                                                            │
│  触发: 新一轮 Observe（持续监控）                                           │
└────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 实时反馈机制

```python
# core/ooda_loop.py
from typing import AsyncGenerator
import json

class OODALoop:
    """OODA 循环执行器，支持流式输出"""

    async def execute_streaming(
        self,
        mission: str,
    ) -> AsyncGenerator[dict, None]:
        """流式执行 OODA，返回每一步的实时状态"""

        yield {
            "phase": "observe",
            "status": "started",
            "agent": "intelligence",
            "message": "开始感知 B 区领域态势...",
        }

        # Observe
        observe_result = await self.intelligence.observe(mission)
        yield {
            "phase": "observe",
            "status": "completed",
            "agent": "intelligence",
            "data": observe_result,
        }

        # Orient
        yield {"phase": "orient", "status": "started", "agent": "intelligence"}
        orient_result = await self.intelligence.orient(observe_result)
        yield {"phase": "orient", "status": "completed", "data": orient_result}

        # Decide
        yield {"phase": "decide", "status": "started", "agent": "commander"}
        decide_result = await self.commander.decide(orient_result)
        yield {"phase": "decide", "status": "completed", "data": decide_result}

        # Act
        if decide_result.requires_human_confirmation:
            yield {
                "phase": "act",
                "status": "waiting_confirmation",
                "data": decide_result.pending_order,
            }
            # 等待用户确认...
            confirmed = await self.wait_for_confirmation()
            if not confirmed:
                yield {"phase": "act", "status": "cancelled"}
                return

        yield {"phase": "act", "status": "executing", "agent": "operations"}
        act_result = await self.operations.act(decide_result.final_order)

        # 回写 Graphiti
        await self.graphiti.write_episode(act_result)
        yield {"phase": "act", "status": "completed", "data": act_result}
```

---


## 9. 数据架构

### 9.1 数据流总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据流                                          │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐     ┌──────────────┐     ┌─────────────┐     ┌────────────┐
  │ 传感器    │────►│ Intelligence │────►│   Graphiti  │◄────│  外部数据源 │
  │ Radar    │     │    Agent     │     │   (持久化)   │     │  气象/地形  │
  │ Drone    │     └──────────────┘     └──────┬──────┘     └────────────┘
  │ Satellite│              ▲                   │
  └──────────┘              │                   ▼
                             │            ┌─────────────┐
                             └────────────│   RAG       │
                                          │  增强推理    │
                                          └─────────────┘

  ┌──────────┐     ┌──────────────┐     ┌─────────────┐
  │ Commander│────►│    OPA       │────►│  Operations │
  │  Agent   │     │  (策略校验)   │     │    Agent    │
  └──────────┘     └──────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  执行结果    │
                                        │  回写Graphiti│
                                        └─────────────┘
```

### 9.2 存储层次

| 存储层 | 技术 | 用途 | 数据示例 |
|--------|------|------|---------|
| **向量存储** | Neo4j Vector | RAG 语义搜索 | 情报文本嵌入 |
| **图存储** | Neo4j | 实体关系 | Target-THREATENED_BY→Intelligence |
| **时序存储** | Graphiti Episode | 双时态事实 | [valid_from, valid_to, recorded_at] |
| **结构化存储** | PostgreSQL | 业务主数据 | 决策指令、授权配置 |
| **对象存储** | S3/MinIO | 文件资产 | 领域图像、雷达回波 |
| **模拟推演存储** | Redis + 临时PostgreSQL | 沙箱推演数据、方案版本 | 推演结果、参数快照 |

---


## 13. 本体管理层

### 13.1 本体定位

本体（Ontology）是系统的"词汇表"，定义了领域上所有实体、关系和属性。本体作为统一的语义层，支撑 Graphiti 图谱和前端展示。

### 13.2 领域实体定义（中英文）

```typescript
// ontology/entities.ts

export const BATTLEFIELD_ONTOLOGY = {
  // ===== 作战单位 =====
  Unit: {
    name: { zh: '作战单位', en: 'Unit' },
    description: '执行执行任务的实体',
    attributes: {
      unit_id: { zh: '单位ID', en: 'Unit ID', type: 'string', required: true },
      unit_type: {
        zh: '单位类型',
        en: 'Unit Type',
        type: 'enum',
        values: ['infantry', 'armor', 'aviation', 'naval', 'electronic_warfare'],
        required: true
      },
      affiliation: {
        zh: '所属方',
        en: 'Affiliation',
        type: 'enum',
        values: ['friendly', 'enemy', 'neutral', 'unknown'],
        required: true
      },
      status: {
        zh: '状态',
        en: 'Status',
        type: 'enum',
        values: ['active', 'deployed', 'damaged', 'destroyed', 'retreating'],
        required: true
      },
      position: {
        zh: '位置坐标',
        en: 'Position',
        type: 'object',
        properties: { lat: 'number', lon: 'number', altitude: 'number' }
      },
      combat_capability: {
        zh: '执行能力指数',
        en: 'Combat Capability',
        type: 'number',
        range: [0, 100]
      },
    },
  },

  // ===== 目标 =====
  Target: {
    name: { zh: '目标', en: 'Target' },
    description: '需要监视或打击的目标实体',
    attributes: {
      target_id: { zh: '目标ID', en: 'Target ID', type: 'string', required: true },
      target_type: {
        zh: '目标类型',
        en: 'Target Type',
        type: 'enum',
        values: ['radar', 'command_center', 'supply_depot', 'missile_launcher', 'air_defense', 'communications'],
        required: true
      },
      threat_level: {
        zh: '威胁等级',
        en: 'Threat Level',
        type: 'enum',
        values: ['critical', 'high', 'medium', 'low']
      },
      location: { zh: '位置坐标', en: 'Location', type: 'object' },
      status: { zh: '状态', en: 'Status', type: 'enum', values: ['active', 'destroyed', 'unknown'] },
      protected: { zh: '受保护', en: 'Protected', type: 'boolean', default: false },
    },
  },

  // ===== 情报报告 =====
  IntelligenceReport: {
    name: { zh: '情报报告', en: 'Intelligence Report' },
    description: '来自各种传感器的情报数据',
    attributes: {
      report_id: { zh: '报告ID', en: 'Report ID', type: 'string' },
      source: {
        zh: '来源',
        en: 'Source',
        type: 'enum',
        values: ['satellite', 'drone', 'radar', 'human', 'sigint', 'document']
      },
      confidence: { zh: '置信度', en: 'Confidence', type: 'number', range: [0, 1] },
      detected_at: { zh: '发现时间', en: 'Detected At', type: 'datetime' },
      content: { zh: '内容摘要', en: 'Content', type: 'string' },
      attached_files: { zh: '附件', en: 'Attached Files', type: 'array' },
    },
  },

  // ===== 决策指令 =====
  StrikeOrder: {
    name: { zh: '决策指令', en: 'Strike Order' },
    description: '下达的执行命令',
    attributes: {
      order_id: { zh: '命令ID', en: 'Order ID', type: 'string' },
      target_id: { zh: '目标ID', en: 'Target ID', type: 'string' },
      weapon_type: { zh: '武器类型', en: 'Weapon Type', type: 'enum' },
      issued_by: { zh: '签发人', en: 'Issued By', type: 'string' },
      status: {
        zh: '执行状态',
        en: 'Status',
        type: 'enum',
        values: ['pending', 'approved', 'executed', 'failed', 'cancelled']
      },
      executed_at: { zh: '执行时间', en: 'Executed At', type: 'datetime' },
      result: { zh: '执行结果', en: 'Result', type: 'string' },
    },
  },

  // ===== 武器装备 =====
  Weapon: {
    name: { zh: '武器装备', en: 'Weapon' },
    description: '可用于打击的系统',
    attributes: {
      weapon_id: { zh: '装备ID', en: 'Weapon ID', type: 'string' },
      weapon_type: { zh: '武器类型', en: 'Type', type: 'enum' },
      effective_range: { zh: '有效射程(km)', en: 'Effective Range', type: 'number' },
      yield: { zh: '当量', en: 'Yield', type: 'number' },
      status: { zh: '状态', en: 'Status', type: 'enum' },
      carrier_unit: { zh: '搭载单位', en: 'Carrier Unit', type: 'string' },
    },
  },

  // ===== 保护区域 =====
  ProtectedZone: {
    name: { zh: '保护区域', en: 'Protected Zone' },
    description: '禁止攻击的保护性区域或目标',
    attributes: {
      zone_id: { zh: '区域ID', en: 'Zone ID', type: 'string' },
      zone_type: {
        zh: '区域类型',
        en: 'Zone Type',
        type: 'enum',
        values: ['civilian', 'medical', 'historical', 'diplomatic', 'neutral']
      },
      boundary: { zh: '边界坐标', en: 'Boundary', type: 'array' },
      description: { zh: '描述', en: 'Description', type: 'string' },
    },
  },
};
```

### 13.3 关系类型定义

```typescript
export const BATTLEFIELD_RELATIONS = {
  // 单位间关系
  'Unit - [:DEPLOYED_TO]-> Target': {
    zh: '单位部署到目标区域',
    en: 'Unit deployed to target area',
  },
  'Unit - [:BELONGS_TO]-> Unit': {
    zh: '单位隶属关系',
    en: 'Unit affiliation',
  },
  'Unit - [:COMMANDED_BY]-> Unit': {
    zh: '指挥关系',
    en: 'Command relationship',
  },

  // 情报关系
  'IntelligenceReport - [:DETECTED]-> Target': {
    zh: '情报发现目标',
    en: 'Intelligence detected target',
  },
  'IntelligenceReport - [:EVIDENCE_FOR]-> StrikeOrder': {
    zh: '情报为决策指令提供依据',
    en: 'Intelligence provides evidence for strike order',
  },

  // 打击关系
  'StrikeOrder - [:TARGETS]-> Target': {
    zh: '决策指令指向目标',
    en: 'Strike order targets',
  },
  'Weapon - [:MOUNTED_ON]-> Unit': {
    zh: '武器挂载在单位上',
    en: 'Weapon mounted on unit',
  },

  // 保护关系
  'Target - [:LOCATED_IN]-> ProtectedZone': {
    zh: '目标位于保护区域内',
    en: 'Target located in protected zone',
  },
};
```

### 13.4 多数据源接入架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          多数据源接入层 (Multi-Source Adapter)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   结构化数据源   │  │  非结构化数据源   │  │   实时数据源     │             │
│  │  Structured     │  │  Unstructured    │  │  Real-time      │             │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤             │
│  │ • PostgreSQL    │  │ • PDF 文档      │  │ • WebSocket     │             │
│  │ • MySQL         │  │ • 图像/视频     │  │ • Kafka         │             │
│  │ • MongoDB       │  │ • 语音转文本    │  │ • MQTT          │             │
│  │ • Elasticsearch │  │ • 网页爬虫     │  │ • Redis PubSub  │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           │                      │                      │                       │
│           ▼                      ▼                      ▼                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      统一数据抽象层 (Data Abstraction)                 │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │   │
│  │  │  DataEntity  │  │ DataDocument │  │ DataStream   │            │   │
│  │  │  结构化实体  │  │ 非结构化文档 │  │ 实时数据流   │            │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘            │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      本体映射层 (Ontology Mapping)                    │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │   │
│  │  │  FieldMapper  │  │ ParserMapper │  │ StreamMapper │            │   │
│  │  │  字段映射     │  │ 解析器映射   │  │ 流映射       │            │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘            │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Graphiti 图谱 (知识融合)                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 13.5 数据源配置模型

```python
# models/data_source.py

@dataclass
class DataSource:
    id: str
    name: str                          # 数据源名称
    source_type: DataSourceType        # 数据源类型
    connection_config: Dict[str, Any]  # 连接配置
    ontology_mapping: OntologyMapping  # 本体映射规则
    status: str                       # active/inactive/error
    refresh_interval: int             # 刷新间隔(秒)
    credential_id: str               # 凭证ID(加密存储)
    created_at: datetime
    updated_at: datetime


class DataSourceType(Enum):
    # 结构化数据源
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    ELASTICSEARCH = "elasticsearch"

    # 非结构化数据源
    PDF_DOCUMENT = "pdf_document"
    IMAGE_ARCHIVE = "image_archive"
    VIDEO_ARCHIVE = "video_archive"
    WEB_CRAWLER = "web_crawler"
    VOICE_TRANSCRIPT = "voice_transcript"

    # 实时数据源
    WEBSOCKET = "websocket"
    KAFKA = "kafka"
    MQTT = "mqtt"
    REDIS_PUBSUB = "redis_pubsub"


@dataclass
class OntologyMapping:
    """本体映射配置"""
    source_entity_type: str           # 源数据类型
    target_ontology_class: str        # 目标本体类
    field_mappings: List[FieldMapping]  # 字段映射
    transformation_rules: List[str]    # 转换规则
    filter_conditions: List[str]      # 过滤条件


@dataclass
class FieldMapping:
    source_field: str                 # 源字段
    target_field: str                 # 目标字段
    transform_type: TransformType     # 转换类型
    transform_params: Dict[str, Any]  # 转换参数

### 13.6 本体管理引擎

**核心功能**：将信息采集到本体图谱构建的黑盒过程透明化，提供可视化审计界面。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         本体管理引擎                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │  Ingestion Audit│    │  Ontology Builder│    │  Version Control│         │
│  │  • 数据来源     │    │  • 实体提取     │    │  • 版本追踪     │         │
│  │  • 处理过程     │    │  • 关系识别     │    │  • 变更对比     │         │
│  │  • 转换规则     │    │  • 属性映射     │    │  • 回滚机制     │         │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│           │                     │                     │                    │
│           └─────────────────────┼─────────────────────┘                    │
│                                 ▼                                          │
│                    ┌────────────────────────┐                              │
│                    │  Validation Engine    │                              │
│                    │  • 数据质量检查       │                              │
│                    │  • 一致性验证         │                              │
│                    │  • 完整性验证         │                              │
│                    └──────────┬─────────────┘                              │
│                               │                                            │
│                               ▼                                            │
│                    ┌────────────────────────┐                              │
│                    │  Audit Dashboard      │                              │
│                    │  • 实时监控           │                              │
│                    │  • 历史审计           │                              │
│                    │  • 异常告警           │                              │
│                    └────────────────────────┘                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 13.6.1 数据摄入审计流程

| 阶段 | 描述 | 审计点 |
|------|------|--------|
| **数据采集** | 从外部源获取数据 | 数据来源、格式、时间戳 |
| **预处理** | 数据清洗、标准化 | 清洗规则、处理结果 |
| **标准化** | 转换为 OntologyDocument | 转换规则、映射关系 |
| **构建** | 构建本体结构 | 实体提取、关系识别 |
| **存储** | 写入 Graphiti/Neo4j | 写入状态、时间戳 |
| **验证** | 数据质量检查 | 验证结果、异常信息 |

#### 13.6.2 本体构建可视化

**功能**：
- 实时展示实体提取过程
- 可视化关系识别算法
- 属性映射配置界面
- 构建过程时间线
- 异常检测与告警

#### 13.6.3 技术实现

```python
# services/ontology_management_engine.py

class OntologyManagementEngine:
    """本体管理引擎"""
    
    def __init__(self, ingestion_audit, ontology_builder, version_control, validation_engine):
        self.ingestion_audit = ingestion_audit
        self.ontology_builder = ontology_builder
        self.version_control = version_control
        self.validation_engine = validation_engine
    
    def process_data(self, data_source, data):
        """处理数据并构建本体"""
        # 1. 数据摄入审计
        audit_id = self.ingestion_audit.start_audit(data_source, data)
        
        try:
            # 2. 数据预处理
            processed_data = self.ingestion_audit.preprocess(data)
            
            # 3. 标准化为 OntologyDocument
            ontology_doc = self.ingestion_audit.standardize(processed_data)
            
            # 4. 构建本体
            build_result = self.ontology_builder.build(ontology_doc)
            
            # 5. 验证
            validation_result = self.validation_engine.validate(build_result)
            
            # 6. 版本控制
            version_id = self.version_control.create_version(build_result)
            
            # 7. 完成审计
            self.ingestion_audit.complete_audit(audit_id, {
                'processed_data': processed_data,
                'ontology_doc': ontology_doc,
                'build_result': build_result,
                'validation_result': validation_result,
                'version_id': version_id
            })
            
            return {
                'success': True,
                'version_id': version_id,
                'audit_id': audit_id
            }
            
        except Exception as e:
            self.ingestion_audit.fail_audit(audit_id, str(e))
            return {
                'success': False,
                'error': str(e),
                'audit_id': audit_id
            }
```

### 13.7 数据接入处理器

```python
# services/data_ingestion.py

class DataIngestionService:
    """数据接入服务"""

    def __init__(
        self,
        source_adapters: Dict[DataSourceType, DataSourceAdapter],
        ontology_mapper: OntologyMapper,
        graphiti_client: GraphitiClient,
    ):
        self.source_adapters = source_adapters
        self.ontology_mapper = ontology_mapper
        self.graphiti_client = graphiti_client

    async def ingest(self, data_source: DataSource, data: Any) -> IngestionResult:
        # 1. 数据解析 - 适配器统一化
        adapter = self.source_adapters[data_source.source_type]
        parsed_data = await adapter.parse(data)

        # 2. 本体映射 - 转换为图谱实体
        entities = await self.ontology_mapper.map(
            parsed_data,
            data_source.ontology_mapping
        )

        # 3. 图谱写入
        for entity in entities:
            await self.graphiti_client.add_entity(entity)

        # 4. 审计记录
        await self.audit_log.record_ingestion(
            source=data_source.id,
            record_count=len(entities)
        )

        return IngestionResult(success=True, count=len(entities))


class DataSourceAdapter(ABC):
    """数据源适配器基类"""

    @abstractmethod
    async def parse(self, raw_data: Any) -> ParsedData:
        """解析原始数据为统一格式"""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """测试数据源连接"""
        pass


class StructuredDataAdapter(DataSourceAdapter):
    """结构化数据适配器"""

    async def parse(self, raw_data: Any) -> ParsedData:
        # 保持原始结构
        return ParsedData(
            data_type=DataType.STRUCTURED,
            records=raw_data if isinstance(raw_data, list) else [raw_data],
            schema=self.extract_schema(raw_data)
        )


class PDFDocumentAdapter(DataSourceAdapter):
    """PDF 文档适配器"""

    def __init__(self, ocr_service: OCRService, llm_extractor: LLMExtractor):
        self.ocr_service = ocr_service
        self.llm_extractor = llm_extractor

    async def parse(self, raw_data: bytes) -> ParsedData:
        # 1. OCR 提取文本
        text = await self.ocr_service.extract(raw_data)

        # 2. LLM 抽取结构化信息
        structured = await self.llm_extractor.extract(
            text,
            extraction_schema=self.get_schema()
        )

        return ParsedData(
            data_type=DataType.DOCUMENT,
            raw_text=text,
            entities=structured,
            metadata={'source': 'pdf', 'page_count': self.get_page_count(raw_data)}
        )


class KafkaStreamAdapter(DataSourceAdapter):
    """Kafka 流数据适配器"""

    def __init__(self, kafka_config: KafkaConfig):
        self.consumer = AIOKafkaConsumer(**kafka_config)

    async def parse(self, raw_data: ConsumerRecord) -> ParsedData:
        return ParsedData(
            data_type=DataType.STREAM,
            records=[{
                'topic': raw_data.topic,
                'partition': raw_data.partition,
                'offset': raw_data.offset,
                'timestamp': raw_data.timestamp,
                'value': json.loads(raw_data.value)
            }],
            metadata={'kafka_topic': raw_data.topic}
        )
```

### 13.8 技能自动注册机制

```python
# services/skill_registry.py

class SkillRegistry:
    """技能注册表 - 支持热插拔"""

    def __init__(self, config_store: ConfigStore):
        self.config_store = config_store
        self.skills: Dict[str, SkillMetadata] = {}
        self.enabled_skills: Set[str] = set()

    async def register(self, skill_id: str, skill_config: SkillConfig):
        """注册新技能 - 立即生效"""
        # 1. 验证技能配置
        await self.validate_skill(skill_config)

        # 2. 加载技能模块
        module = await self.load_skill_module(skill_config)

        # 3. 注册到运行时
        self.skills[skill_id] = SkillMetadata(
            id=skill_id,
            module=module,
            config=skill_config,
            registered_at=datetime.now(),
            status='registered'
        )

        # 4. 如果启用则激活
        if skill_config.enabled:
            await self.enable(skill_id)

        # 5. 持久化注册信息
        await self.config_store.save_skill_registration(skill_id, skill_config)

        # 6. 发布注册事件
        await self.event_bus.publish(SkillRegisteredEvent(skill_id))

    async def enable(self, skill_id: str):
        """启用技能 - 立即生效"""
        if skill_id not in self.skills:
            raise SkillNotFoundError(skill_id)

        skill = self.skills[skill_id]

        # 重新加载模块
        await self.reload_skill_module(skill_id)

        self.enabled_skills.add(skill_id)
        skill.status = 'enabled'

        # 通知 Agent 系统
        await self.notify_agent_system(skill_id, enabled=True)

        await self.event_bus.publish(SkillEnabledEvent(skill_id))

    async def disable(self, skill_id: str):
        """禁用技能 - 立即生效"""
        if skill_id in self.enabled_skills:
            self.enabled_skills.remove(skill_id)

        self.skills[skill_id].status = 'disabled'

        # 通知 Agent 系统
        await self.notify_agent_system(skill_id, enabled=False)

        await self.event_bus.publish(SkillDisabledEvent(skill_id))

    def get_enabled_skills(self) -> List[SkillMetadata]:
        """获取所有启用的技能"""
        return [self.skills[sid] for sid in self.enabled_skills]
```

### 13.9 规则引擎集成

```python
# services/rule_engine.py

class RuleEngine:
    """规则引擎 - 支持规则组合"""

    def __init__(
        self,
        rule_repository: RuleRepository,
        condition_evaluator: ConditionEvaluator,
    ):
        self.rule_repository = rule_repository
        self.condition_evaluator = condition_evaluator

    async def evaluate(
        self,
        context: EvaluationContext,
        rule_group_id: str
    ) -> EvaluationResult:
        """评估规则组"""
        rules = await self.rule_repository.get_by_group(rule_group_id)
        results = []

        for rule in sorted(rules, key=lambda r: r.priority):
            # 评估条件
            if await self.condition_evaluator.evaluate(rule.conditions, context):
                # 执行动作
                action_result = await self.execute_action(rule.action, context)
                results.append(RuleResult(rule_id=rule.id, executed=True, result=action_result))

                # 如果规则指定为独占执行，则跳出
                if rule.exclusive:
                    break
            else:
                results.append(RuleResult(rule_id=rule.id, executed=False))

        return EvaluationResult(results=results)

    async def create_rule(self, rule_config: RuleConfig) -> Rule:
        """创建规则"""
        # 1. 验证规则语法
        await self.validate_rule_syntax(rule_config)

        # 2. 编译条件表达式
        compiled_conditions = await self.compile_conditions(rule_config.conditions)

        # 3. 保存规则
        rule = Rule(
            id=self.generate_id(),
            name=rule_config.name,
            group_id=rule_config.group_id,
            conditions=compiled_conditions,
            action=rule_config.action,
            priority=rule_config.priority,
            enabled=True,
        )
        await self.rule_repository.save(rule)

        # 4. 通知规则引擎重载
        await self.reload_rules()

        return rule


@dataclass
class Rule:
    id: str
    name: str
    group_id: str                    # 规则组
    conditions: CompiledConditions    # 编译后的条件
    action: RuleAction               # 执行动作
    priority: int                     # 优先级(越小越先)
    exclusive: bool                  # 独占执行
    enabled: bool
    version: str
    created_at: datetime





## 14. 角色与权限管理

### 14.1 角色管理定位

角色是权限的载体，通过角色实现技能、策略、规则的可配置组合。

### 14.2 系统预定义角色

| 角色ID | 角色名称 | 描述 |
|--------|----------|------|
| `commander` | 指挥官 | 最终决策者，拥有最高权限 |
| `intelligence_officer` | 情报分析员 | 情报收集、分析和评估 |
| `operator` | 操作员 | 执行具体操作命令 |
| `admin` | 系统管理员 | 系统配置和本体管理 |
| `auditor` | 审计员 | 查看审计日志，但不能操作 |

### 14.3 角色配置结构

```typescript
// types/role.ts

interface Role {
  id: string;
  name: string;                    // 角色名称
  description: string;              // 角色描述
  skills: string[];                 // 绑定的技能列表
  policies: PolicyBinding[];        // 绑定的 OPA 策略
  rules: RuleBinding[];             // 绑定的业务规则
  permissions: Permission[];       // 直接权限（覆盖）
  metadata: Record<string, any>;     // 扩展元数据
}

interface PolicyBinding {
  policyId: string;                // 策略 ID
  version?: string;                 // 策略版本（空=最新）
  priority: number;                 // 优先级（数值越大越优先）
  enabled: boolean;                 // 是否启用
}

interface RuleBinding {
  ruleId: string;                   // 规则 ID
  params: Record<string, any>;      // 规则参数
  enabled: boolean;                 // 是否启用
}

interface Permission {
  resource: string;                 // 资源类型
  actions: string[];                // 操作列表
  conditions?: Record<string, any>; // 条件约束
}
```

### 14.4 角色分配流程

```
用户登录
    ↓
获取用户角色列表
    ↓
加载角色配置（技能/策略/规则）
    ↓
OPA 权限校验
    ↓
Skill 注册
    ↓
进入对应工作台
```

### 14.5 角色热生效机制

| 操作 | 生效方式 | 延迟 |
|------|----------|------|
| 新增角色 | 立即生效 | < 1s |
| 修改角色技能绑定 | 刷新 Token 后生效 | 下次登录 |
| 修改 OPA 策略 | 自动热加载 | < 5s |
| 禁用角色 | 立即生效 | < 1s |

### 14.6 角色管理 API

```typescript
// 角色 CRUD
POST   /api/v1/roles              // 创建角色
GET    /api/v1/roles              // 列表角色
GET    /api/v1/roles/:id          // 获取角色详情
PUT    /api/v1/roles/:id          // 更新角色
DELETE /api/v1/roles/:id         // 删除角色

// 角色绑定
POST   /api/v1/roles/:id/skills   // 绑定技能
DELETE /api/v1/roles/:id/skills/:skillId  // 解绑技能
POST   /api/v1/roles/:id/policies // 绑定策略
POST   /api/v1/roles/:id/rules    // 绑定规则

// 用户角色
POST   /api/v1/users/:id/roles    // 分配角色
DELETE /api/v1/users/:id/roles/:roleId  // 移除角色
```

### 14.7 角色定义

```typescript
// roles/definitions.ts

export const SYSTEM_ROLES = {
  // ===== 操作角色 =====
  commander: {
    name: { zh: '指挥官', en: 'Commander' },
    description: '领域最高决策者，有权下达决策指令',
    permissions: {
      skills: ['*'],  // 所有技能权限
      targets: ['*'],  // 可操作所有目标
      strike_approval: true,  // 可批准打击
      ooda_phases: ['observe', 'orient', 'decide', 'act'],
    },
    required_conditions: {
      min_rank: 'colonel',
      security_clearance: 4,
    },
  },

  intelligence_officer: {
    name: { zh: '情报分析员', en: 'Intelligence Officer' },
    description: '负责情报收集、分析和评估',
    permissions: {
      skills: ['radar_search', 'drone_surveillance', 'threat_assessment', 'pattern_match'],
      targets: ['*'],
      strike_approval: false,
      ooda_phases: ['observe', 'orient'],
    },
  },

  operator: {
    name: { zh: '操作员', en: 'Operator' },
    description: '执行具体操作命令',
    permissions: {
      skills: ['command_unit', 'route_planning'],
      targets: ['unrestricted'],
      strike_approval: false,
      ooda_phases: ['act'],
    },
  },

  // ===== 管理角色 =====
  admin: {
    name: { zh: '系统管理员', en: 'Administrator' },
    description: '系统配置和本体管理',
    permissions: {
      simulation_control: true,
      ontology_edit: true,
      policy_edit: true,
      role_manage: true,
      audit_view: true,
    },
  },

  auditor: {
    name: { zh: '审计员', en: 'Auditor' },
    description: '查看审计日志，但不能操作',
    permissions: {
      simulation_control: false,
      ontology_edit: false,
      policy_edit: false,
      role_manage: false,
      audit_view: true,
    },
  },
};
```



### 14.8 角色管理接口

```typescript
// 后端: role_controller.py
class RoleController {
  // 角色 CRUD
  async createRole(role: RoleCreate): Promise<Role>;
  async getRole(roleId: string): Promise<Role>;
  async updateRole(roleId: string, updates: RoleUpdate): Promise<Role>;
  async deleteRole(roleId: string): Promise<void>;

  // 角色 Skill 分配
  async assignSkills(roleId: string, skillIds: string[]): Promise<void>;
  async getRoleSkills(roleId: string): Promise<Skill[]>;

  // 角色 OPA 策略绑定
  async bindPolicies(roleId: string, policyIds: string[]): Promise<void>;
  async getRolePolicies(roleId: string): Promise<Policy[]>;

  // 修改生效控制
  async applyRoleChanges(roleId: string): Promise<void>;
  // 或设置为自动应用
  async setAutoApply(roleId: string, enabled: boolean): Promise<void>;
}

// 前端: RoleManagement
const RoleManagement: React.FC = () => {
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);

  return (
    <Card>
      <Table dataSource={roles} rowKey="id">
        <Column title="角色名" dataIndex={['name', 'zh']} />
        <Column title="描述" dataIndex={['description']} />
        <Column
          title="操作"
          render={(_, record) => (
            <Space>
              <Button onClick={() => setSelectedRole(record)}>编辑</Button>
              <Button onClick={() => applyChanges(record.id)}>应用修改</Button>
              <Switch
                checked={record.auto_apply}
                onChange={(checked) => setAutoApply(record.id, checked)}
              />
              <Text type="secondary">自动应用</Text>
            </Space>
          )}
        />
      </Table>

      {selectedRole && (
        <RoleEditDrawer
          role={selectedRole}
          onSave={handleSave}
          onClose={() => setSelectedRole(null)}
        />
      )}
    </Card>
  );
};
```


---


## 16. 配置中心（已整合）

> 配置中心功能已整合到各模块的配置管理中，详见第20章。


## 20. 配置管理详细设计

> 本章详细描述配置中心的功能设计。配置管理功能已整合到各模块中，通过统一的 `infra/config/` 模块进行集中管理。
### 20.1 配置分层

```
配置中心
├── 系统配置
│   ├── 数据库配置
│   ├── 缓存配置
│   └── 日志配置
├── LLM 配置
│   ├── 模型选择
│   ├── API 密钥
│   └── 温度参数
├── Graphiti 配置
│   ├── Neo4j 连接
│   └── 向量索引
├── OPA 配置
│   ├── 服务地址
│   └── Bundle URL
├── Skill 配置
│   ├── 启用列表
│   └── 参数配置
├── 前端配置
│   ├── 主题
│   └── WebSocket URL
└── 多模态配置
    ├── OCR 模型
    ├── 图像识别模型
    └── 文档解析配置
```

### 20.2 配置模型

```typescript
// config/config_model.ts

export interface ConfigGroup {
  id: string;
  name: { zh: string; en: string };
  description: { zh: string; en: string };
  icon: string;
  configs: ConfigItem[];
}

export interface ConfigItem {
  key: string;              // 配置键
  name: { zh: string; en: string };
  description: { zh: string; en: string };
  type: 'string' | 'number' | 'boolean' | 'select' | 'json' | 'secret';
  default?: any;
  value?: any;
  options?: { label: string; value: any }[];  // for select type
  validation?: {
    pattern?: string;
    min?: number;
    max?: number;
    required?: boolean;
  };
  secret?: boolean;  // 是否加密存储
}

export const CONFIG_GROUPS: ConfigGroup[] = [
  {
    id: 'llm',
    name: { zh: '大模型配置', en: 'LLM Configuration' },
    description: { zh: '配置 LLM 模型和 API', en: 'Configure LLM models and APIs' },
    icon: 'robot',
    configs: [
      {
        key: 'llm.provider',
        name: { zh: '模型提供商', en: 'Provider' },
        description: { zh: '选择 LLM 提供商', en: 'Select LLM provider' },
        type: 'select',
        options: [
          { label: 'OpenAI', value: 'openai' },
          { label: 'Anthropic', value: 'anthropic' },
          { label: 'DeepSeek', value: 'deepseek' },
        ],
      },
      {
        key: 'llm.commander_model',
        name: { zh: 'Commander 模型', en: 'Commander Model' },
        description: { zh: 'Commander Agent 使用的模型', en: 'Model for Commander Agent' },
        type: 'select',
        options: [
          { label: 'GPT-4', value: 'gpt-4' },
          { label: 'Claude-3.5 Sonnet', value: 'claude-3-5-sonnet' },
        ],
      },
      {
        key: 'llm.api_key',
        name: { zh: 'API 密钥', en: 'API Key' },
        description: { zh: 'LLM 提供商的 API 密钥', en: 'LLM provider API key' },
        type: 'secret',
        secret: true,
      },
    ],
  },
  {
    id: 'multimodal',
    name: { zh: '多模态配置', en: 'Multimodal Configuration' },
    description: { zh: '配置多模态处理模型', en: 'Configure multimodal processing models' },
    icon: 'scan',
    configs: [
      {
        key: 'multimodal.ocr_enabled',
        name: { zh: '启用 OCR', en: 'Enable OCR' },
        description: { zh: '是否启用文档 OCR 识别', en: 'Enable document OCR' },
        type: 'boolean',
        default: true,
      },
      {
        key: 'multimodal.ocr_model',
        name: { zh: 'OCR 模型', en: 'OCR Model' },
        description: { zh: 'OCR 使用的模型', en: 'Model for OCR' },
        type: 'select',
        options: [
          { label: 'EasyOCR', value: 'easyocr' },
          { label: 'PaddleOCR', value: 'paddleocr' },
        ],
      },
      {
        key: 'multimodal.vision_model',
        name: { zh: '图像识别模型', en: 'Vision Model' },
        description: { zh: '图像分析的模型', en: 'Model for image analysis' },
        type: 'select',
        options: [
          { label: 'GPT-4V', value: 'gpt-4v' },
          { label: 'Claude Vision', value: 'claude-vision' },
        ],
      },
    ],
  },
];
```

### 20.3 前端配置界面

```typescript
// frontend: ConfigCenter
const ConfigCenter: React.FC = () => {
  const [activeGroup, setActiveGroup] = useState('llm');
  const [configs, setConfigs] = useState<Record<string, any>>({});
  const [saving, setSaving] = useState(false);

  const activeGroupData = CONFIG_GROUPS.find((g) => g.id === activeGroup);

  return (
    <Split horizontal defaultSizes={[200, '1fr']}>
      {/* 左侧：分组列表 */}
      <Menu
        mode="vertical"
        selectedKeys={[activeGroup]}
        onClick={({ key }) => setActiveGroup(key)}
        items={CONFIG_GROUPS.map((g) => ({
          key: g.id,
          icon: <Icon name={g.icon} />,
          label: g.name.zh,
        }))}
      />

      {/* 右侧：配置项 */}
      <Card title={activeGroupData?.name.zh}>
        <Descriptions column={1} bordered>
          {activeGroupData?.configs.map((config) => (
            <Descriptions.Item
              key={config.key}
              label={
                <Space direction="vertical" size={0}>
                  <Text strong>{config.name.zh}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {config.description.zh}
                  </Text>
                </Space>
              }
            >
              <ConfigInput config={config} value={configs[config.key]} />
            </Descriptions.Item>
          ))}
        </Descriptions>

        <Space style={{ marginTop: 16 }}>
          <Button type="primary" loading={saving} onClick={handleSave}>
            保存配置
          </Button>
          <Button onClick={handleReset}>重置</Button>
        </Space>
      </Card>
    </Split>
  );
};
```

---




