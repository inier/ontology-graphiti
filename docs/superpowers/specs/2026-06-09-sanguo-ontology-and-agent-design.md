# 三国演义本体 & 三国战纪智能体 — 设计文档

**日期**: 2026-06-09
**作者**: AI 代理
**状态**: 已批准
**关联**: ODAP 平台（specs/001-odap-platform/） / CopilotKit 评估（specs/002-copilotkit-eval/）

---

## 1. 目标

在 ODAP 平台之上，**作为业务场景**构建"三国演义"本体（基于四大名著），并实现一个**完整的智能体"三国战纪智能体"**，能够：
- 接受用户的自然语言三国问题
- 通过 Agent Loop（OODA）+ 定制 Skills，跨实体推理三国知识
- 通过 QAPanel（已有）和 OntologySemanticNetwork（已有）展示答案与图谱

**重要前提**：三国场景是**平台上的一个业务场景**（类似"情报研判工作空间"），不是独立的系统。复用平台的全部现有能力：
- 鉴权、JWT、Workspace、Scenario、Ontology、Agent、QA、Skills
- 已有 8 个 Agent 工具 (query_entities, query_relations, analyze_graph, search_graph, get_entity_details, list_workspaces, get_workspace_info, create_workspace_summary)
- OpenHarness v1/v2 已就位

**问题修复原则**：构建过程中如发现平台问题阻塞本体设计和应用，必须修复平台，**记录在 docs/ISSUES_SANGUO.md**。

---

## 2. 总体架构

```
┌────────────────────────────────────────────────────────────────────────┐
│                          ODAP 平台（既有）                               │
├────────────────────────────────────────────────────────────────────────┤
│  Frontend: QAPanel + OntologySemanticNetwork（已有 /qa, /ontology）    │
│  Agent:    OODA Loop + OpenHarness v1/v2 + 8 tools（已有）              │
│  Skills:   /api/skill/*（已注册 9 类技能包，已有）                        │
│  Ontology: /api/ontology/model/entity-types, instances, documents      │
│  OMS:      /api/ontology/oms/{object,action}-types                      │
│  Ingest:   /api/ontology/ingestion/upload, batch, extract               │
│  Workspaces/Scenarios: /api/workspaces/.../scenarios                    │
├────────────────────────────────────────────────────────────────────────┤
│  本任务新增：                                                            │
│   1. 三国数据层 (odap/biz/sanguo/data/)                                  │
│      - data/characters.py       30 个人物 + 势力归属                      │
│      - data/factions.py         3 个势力 (魏蜀吴)                         │
│      - data/locations.py        20 个地点                                 │
│      - data/events.py           40 个事件 (184-280 AD)                   │
│      - data/relationships.py    跨实体关系（结义、君臣、敌对、亲属等）      │
│   2. 三国本体构建 (scripts/build_sanguo_ontology.py)                    │
│      - 创建工作空间 X、场景 X-1                                         │
│      - 注入实体类型、关系类型、实例                                      │
│      - 触发 OMS object-types 注册                                       │
│   3. 时间推进事件提取 (odap/biz/sanguo/event_extractor.py)              │
│      - 6 个时间锚点 (184/190/200/208/220/263)                          │
│      - 每个事件 → 调用 /api/ontology/ingestion/extract                  │
│      - 自动触发本体的 instance 创建 / 关系更新                           │
│   4. 三国战纪 Skills (odap/tools/sanguo/)                              │
│      - skill_character_lookup      人物查询                              │
│      - skill_event_timeline        事件时间线                            │
│      - skill_faction_membership     势力归属                             │
│      - skill_battle_detail          战役详情                             │
│   5. 三国战纪智能体 (odap/biz/sanguo/agent/sanguo_agent.py)            │
│      - 继承 OODA Loop                                                  │
│      - 加载三国 Skills + 平台 8 个 Agent tools                         │
│      - NL 路由：问题 → 工具选择 → 推理 → 答案                            │
│   6. 端到端验证 (scripts/e2e_sanguo_test.py)                            │
│      - 7 个核心 Q&A 场景（如"赤壁之战双方参战人物"）                       │
│      - 验证 QAPanel + OntologySemanticNetwork 显示正常                  │
│   7. 问题记录与修复 (docs/ISSUES_SANGUO.md)                              │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 数据规模（精简版）

| 实体类型 | 数量 | 示例 |
|----------|------|------|
| 势力 (Faction) | 3 | 魏、蜀、吴 |
| 君主 (Ruler) | 4 | 曹操、刘备、孙权、司马炎 |
| 核心人物 (Character) | 30 | 关羽、张飞、诸葛亮、周瑜、陆逊、司马懿... |
| 地点 (Location) | 20 | 许昌、成都、建业、洛阳、赤壁、荆州... |
| 战役 (Battle) | 8 | 官渡、赤壁、夷陵、合肥... |
| 事件 (Event) | 40 | 黄巾起义、桃园结义、三顾茅庐... |
| 关系 (Relation) | 60+ | 结义、君臣、敌对、亲属、师徒 |

**时间锚点（事件提取驱动）**:
- 184 AD 黄巾起义 → 张角/刘备/关羽/张飞登场
- 190 AD 群雄讨董 → 18 路诸侯
- 200 AD 官渡之战 → 曹操 vs 袁绍
- 208 AD 赤壁之战 → 孙刘联军 vs 曹操
- 220 AD 曹丕代汉 → 三国鼎立
- 263 AD 蜀汉灭亡 → 三国归晋

---

## 4. 实施阶段（TDD 全程）

| 阶段 | 任务 | 验证方式 | 平台/本体归属 |
|------|------|----------|--------------|
| **P0** | 平台 API 健康检查 | smoke test | 平台 |
| **P1** | 修复发现的平台 P0 问题 | pytest | 平台 |
| **P2** | 写三国数据模块 + 单测 | pytest tests/unit/biz/sanguo/ | 平台(测试基础设施) |
| **P3** | 写 build_sanguo_ontology.py | 端到端 API 验证 | 本体构建 |
| **P4** | 写 event_extractor.py + 时间锚点 | 时间推进测试 | 本体应用 |
| **P5** | 写 4 个三国 Skills | pytest + skill registry | 本体应用 |
| **P6** | 写 SanguoAgent | 端到端 Q&A | 本体应用 |
| **P7** | 写 e2e_sanguo_test.py | 全链路 | 端到端 |
| **P8** | 整理 ISSUES_SANGUO.md + 修复 | 全部 pytest 通过 | 平台 |

---

## 5. 关键设计决策

### 5.1 平台 vs 本体的边界

- **平台代码** = `odap/biz/core/`、`odap/biz/integration/`、`odap/infra/`、`odap/web/`
- **本体应用代码**（三国）= `odap/biz/sanguo/`（**新建领域**）+ `odap/tools/sanguo/`（**新建技能**）
- **不修改** `odap/biz/core/{ontology,agent,qa}/` 的内部实现（保持 6 层调用链）；通过 API 调平台
- **可扩展**：把"三国"看作一个 biz/ 子领域，不与 7 大领域耦合

### 5.2 Skills vs 平台 Agent tools

- 平台已有 8 个 **Agent tools**（被 OpenHarness 调用）— 通用
- 三国 Skills 是 **领域定制**（在 `odap/tools/sanguo/`）— 调用平台 API + 业务逻辑
- 三国 Skills 通过 `/api/skill/register` 注册到平台

### 5.3 智能体实现路径

```
用户问题
  ↓ POST /api/qa/ask
  ↓ SanguoAgent.process_query()  (odap/biz/sanguo/agent/sanguo_agent.py)
    ├─ 路由 (意图分类：人物/事件/势力/战役/时间)
    ├─ 选 skill (从 4 个三国 skills)
    ├─ 必要时调平台 tools (query_entities 等)
    └─ 综合答案
  ↓ 返回给 QAPanel
```

### 5.4 事件提取驱动本体更新

- `event_extractor.py` 模拟"外部信息输入"
- 每个事件 = 一段结构化文本
- 调 `/api/ontology/ingestion/extract` 让平台做 NLP 提取
- 平台返回新实体/关系 → 调 `/api/ontology/model/instances` POST

---

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 平台 API 文档不全 | 通过 `openapi.json` 探索 + 逐步试错 |
| 平台 ingestion 需 LLM（OPENAI_API_KEY） | 编写 mock 路径 + 真实路径双轨 |
| 端到端可能阻塞于单点 | 每阶段都有可独立验证的产物 |
| 时间推进可能与现状冲突 | 加 `if exists → skip` 保护 |
| Skills 注册到平台需要重启 | 在 init 脚本里集中调用一次 |

---

## 7. 验收标准

- [ ] P0-P8 全部 8 个阶段产出物在 `git status` 中可见
- [ ] `pytest tests/unit/biz/sanguo/` 全部通过
- [ ] `python scripts/build_sanguo_ontology.py` 跑通，平台数据可视化
- [ ] `python scripts/e2e_sanguo_test.py` 7 个 Q&A 全部通过
- [ ] QAPanel 中可查询"赤壁之战双方参战人物"并得到正确答案
- [ ] OntologySemanticNetwork 中可看到至少 50 个三国节点
- [ ] `docs/ISSUES_SANGUO.md` 中每条问题都有：发现时间、复现步骤、影响、修复状态
