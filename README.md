# 战场情报分析与打击决策系统

基于 Graphiti + OPA + Skill 架构的智能战场决策系统，参考 Palantir AIP 架构设计。

## 🏗️ 核心架构

系统采用六层架构，参考 Palantir AIP 架构设计：

```
┌─────────────────────────────────────────────────────────────────┐
│                         1. 交互层                                  │
│                    用户/指挥官 - 自然语言指令                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         2. 调度层                                  │
│              LLM Dispatcher + 语义路由 - 意图识别                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         3. 治理层                                  │
│                    OPA (策略引擎) - 权限校验                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         4. 上下文层                                │
│              Graphiti (检索器) - 参数提取                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         5. 执行层                                  │
│                   Skill Executor - 业务逻辑执行                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         6. 记忆层                                  │
│              Graphiti (写入器) - 状态更新                          │
└─────────────────────────────────────────────────────────────────┘
```

## 📂 项目目录结构

```
graphiti/
├── main.py                     # 系统入口
├── config.py                   # 配置管理
├── requirements.txt            # 依赖列表
│
├── core/                       # 核心层
│   ├── __init__.py
│   ├── graph_manager.py        # Graphiti图谱管理
│   ├── orchestrator.py         # 智能体编排器
│   ├── opa_manager.py          # OPA策略管理
│   ├── intelligence_collector.py # 情报自动收集
│   └── decision_recommender.py  # 打击决策推荐
│
├── skills/                     # 技能层
│   ├── __init__.py             # 技能自动注册
│   ├── intelligence.py          # 情报技能 (2个)
│   ├── operations.py            # 作战技能 (2个)
│   ├── analysis.py              # 分析技能 (6个)
│   ├── recommendation.py        # 推荐技能 (4个)
│   ├── task_management.py       # 任务管理技能 (6个)
│   ├── ontology_management.py   # 本体管理技能 (9个)
│   ├── policy.py               # 策略技能 (10个)
│   ├── computation.py           # 计算推理技能 (4个)
│   ├── visualization_skill.py    # 可视化技能 (4个)
│   └── planning.py              # 规划编排技能 (4个)
│
├── data/                       # 数据层
│   ├── __init__.py
│   └── simulation_data.py       # 模拟数据生成
│
├── ontology/                   # 本体层
│   ├── __init__.py
│   ├── domain_ontology.py   # 领域本体定义
│   └── ontology_manager.py       # 本体管理器
│
├── visualization/              # 可视化层
│   ├── __init__.py
│   ├── visualization.py         # 态势可视化
│   └── dialog_interface.py      # 对话界面
│
├── core/                       # 策略文件
│   └── opa_policy.rego         # OPA策略定义
│
├── docs/                       # 文档
│   └── req-alpha.md            # 需求文档
│
└── tests/                      # 测试
    └── test_system.py           # 系统测试
```

## 🎯 Skill 体系 (共56个)

### 1. 记忆与感知类 (9个) - ontology_management.py

| Skill | 描述 |
|-------|------|
| query_ontology | 查询本体 |
| export_ontology | 导出本体 |
| import_ontology | 导入本体 |
| list_ontology_versions | 列出本体版本 |
| rollback_ontology | 回滚本体版本 |
| get_current_ontology | 获取当前本体 |
| update_ontology | 更新本体 |
| get_entity_history | 获取实体历史 |
| search_ontology_hybrid | 混合检索本体 |

### 2. 治理与合规类 (10个) - policy.py

| Skill | 描述 |
|-------|------|
| simulate_policy_execution | 模拟策略执行 |
| get_policy_version | 获取策略版本 |
| rollback_policy | 回退策略版本 |
| export_policy | 导出策略 |
| import_policy | 导入策略 |
| list_policy_versions | 列出策略版本 |
| rollback_policy_version | 回滚策略版本 |
| check_permission | 检查权限 |
| get_policy_history | 获取策略执行历史 |
| clear_policy_history | 清除策略执行历史 |

### 3. 情报类 (2个) - intelligence.py

| Skill | 描述 |
|-------|------|
| search_radar | 搜索雷达 |
| analyze_domain | 分析战场态势 |

### 4. 作战类 (2个) - operations.py

| Skill | 描述 |
|-------|------|
| attack_target | 攻击目标 |
| command_unit | 指挥部队 |

### 5. 分析类 (6个) - analysis.py

| Skill | 描述 |
|-------|------|
| analyze_entity_status | 分析实体状态 |
| analyze_battle_events | 分析战场事件 |
| analyze_force_comparison | 分析力量对比 |
| analyze_weapon_capabilities | 分析武器能力 |
| analyze_civilian_infrastructure | 分析民用基础设施 |
| get_domain_summary | 获取战场态势摘要 |

### 6. 推荐类 (4个) - recommendation.py

| Skill | 描述 |
|-------|------|
| recommend_strike_targets | 推荐打击目标 |
| recommend_task_planning | 推荐任务规划 |
| recommend_force_deployment | 推荐兵力部署 |
| check_strike_risk | 检查打击风险 |

### 7. 任务管理类 (6个) - task_management.py

| Skill | 描述 |
|-------|------|
| reserve_task | 预留任务 |
| get_reserved_tasks | 获取所有预留任务 |
| clear_reserved_tasks | 清除所有预留任务 |
| get_task_by_id | 根据ID获取任务 |
| cancel_task | 取消任务 |
| query_tasks_by_status | 根据状态查询任务 |

### 8. 计算推理类 (4个) - computation.py

| Skill | 描述 |
|-------|------|
| calculate_distance | 计算距离 |
| predict_outcome | 预测攻击结果 |
| analyze_threat_level | 分析威胁等级 |
| calculate_strike_damage | 计算打击毁伤 |

### 9. 可视化类 (4个) - visualization_skill.py

| Skill | 描述 |
|-------|------|
| generate_map_overlay | 生成地图叠加层 |
| summarize_mission | 生成任务摘要 |
| generate_domain_report | 生成战场态势报告 |
| generate_situation_awareness | 生成态势感知数据 |

### 10. 规划编排类 (4个) - planning.py

| Skill | 描述 |
|-------|------|
| create_plan | 创建执行计划 |
| execute_workflow | 执行工作流 |
| validate_plan | 验证计划可行性 |
| estimate_resources | 估算资源需求 |

## 🔧 技术栈

| 层级 | 技术组件 | 作用 |
|------|----------|------|
| **基础设施** | Python 3.8+ | 运行环境 |
| **核心图谱** | Neo4j + Graphiti / NetworkX (回退) | 知识存储与动态记忆 |
| **数据建模** | Pydantic | 本体定义与数据验证 |
| **AI核心** | LangChain (可选) | 逻辑推理与生成 |
| **前端可视化** | Plotly + Matplotlib | 3D态势感知与图谱交互 |
| **安全** | OPA (Open Policy Agent) | 细粒度权限控制 |

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 Neo4j (可选)

如果使用 Neo4j 作为图数据库：

```bash
# 安装 Neo4j
brew install neo4j  # macOS
# 或使用 Docker
docker pull neo4j:latest
docker run -d -p 7474:7474 -p 7687:7687 neo4j:latest
```

如果不安装 Neo4j，系统会自动使用 NetworkX 作为回退模式。

### 3. 运行系统

```bash
# 运行主程序
python main.py

# 运行测试
python tests/test_system.py

# 运行对话界面
python visualization/dialog_interface.py

# 运行可视化
python visualization/visualization.py
```

## 📖 使用示例

### 场景1: 情报查询

```python
from core.orchestrator import SelfCorrectingOrchestrator

orchestrator = SelfCorrectingOrchestrator(user_role="pilot")
result = orchestrator.run("帮我看看 B 区有没有雷达")
```

### 场景2: 权限拦截

```python
# 飞行员尝试攻击 - 会被拦截
orchestrator.run("攻击 RADAR_01")
# 输出: {'status': 'denied', 'message': '权限不足或违反策略'}
```

### 场景3: 指挥官攻击

```python
# 指挥官尝试攻击 - 成功
orchestrator = SelfCorrectingOrchestrator(user_role="commander")
orchestrator.run("攻击 RADAR_01")
# 输出: {'status': 'success', 'message': '成功攻击目标'}
```

### 场景4: 策略拦截

```python
# 攻击民用设施 - 会被拦截
orchestrator.run("攻击 HOSPITAL_01")
# 输出: {'status': 'denied', 'message': '权限不足或违反策略'}
```

## 🔐 OPA 策略配置

策略文件位于 `core/opa_policy.rego`，定义了角色权限和限制：

```rego
package aip.authz

default allow = false

# 指挥官可以攻击
allow {
    input.user.role == "commander"
    input.action == "attack"
}

# 飞行员可以查看情报
allow {
    input.user.role == "pilot"
    input.action == "view_intelligence"
}

# 禁止攻击民用设施
deny {
    input.action == "attack"
    input.resource.type == "CivilianInfrastructure"
}
```

## 📊 Graphiti 特性

系统支持 Graphiti 的核心特性：

1. **双时态数据模型**: 区分"发生时间"与"摄入时间"
2. **混合检索**: 结合语义搜索、关键词匹配和图遍历
3. **增量更新**: 新数据即时更新，无需全量重算
4. **可追溯性**: 完整记录每次决策的依据

## 📁 生成的文件

运行后会生成以下文件：

- `domain_graph.png` - 领域图谱静态图
- `domain_visualization.html` - 交互式可视化
- `domain_status.png` - 领域状态饼图
- `action_dynamics.html` - 处置动态查看
- `ontology_query.html` - 本体可视化查询
- `ontology_aggregation.html` - 本体属性聚合

## 📝 许可证

