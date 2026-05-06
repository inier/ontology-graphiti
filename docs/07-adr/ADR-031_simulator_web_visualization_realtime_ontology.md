# ADR-031: 模拟器 Web 可视化与实时本体热写入架构

## 状态
已接受

## 上下文

现有 `SimulationEngine`（Phase 2）仅提供 Python API 层面的沙箱推演能力，存在以下五个核心缺口：

1. **无可视化界面**：模拟数据无法通过 Web 页面展示事件发展脉络（时间线、关系图谱、态势地图）
2. **数据来源单一**：模拟初始数据完全由代码内置，无法从外部真实事件资料（新闻纪实、情报报告）中采集并自动结构化
3. **交互能力缺失**：无法在界面上手动输入动态信息、按涉事多方随机生成，也不支持导入/导出模拟数据包
4. **本体写入割裂**：模拟数据与本体图谱（Graphiti/Neo4j）之间没有自动同步机制，写入后需重启服务才能感知新版本
5. **格式未统一**：不同模拟数据来源格式不一，无法沉淀为可复用的标准本体 JSON

面向的参考系统：Palantir AIP/Foundry（本体驱动分析）、WorldModels/NetLogo（模拟世界运行）、OpenCog AtomSpace（本体知识图谱实时更新）、oTree（交互式多方模拟）。

---

## 决策

### 总体架构：四层扩展

在现有 `SimulationEngine` 之上新增四个子系统，形成完整的**模拟器增强层**：

```
┌───────────────────────────────────────────────────────────────┐
│                  Simulator Enhanced Layer                     │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  L1: Web Visualization                                  │  │
│  │  FastAPI + WebSocket + Vue3/D3.js                       │  │
│  │  时间线面板 | 关系图谱 | 态势地图 | 实时事件流         │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         │ REST/WebSocket                       │
│  ┌──────────────────────┴──────────────────────────────────┐  │
│  │  L2: Data Ingestion & Normalization                     │  │
│  │  联网检索 (SerpAPI/Tavily) → LLM 归纳 → 标准本体 JSON   │  │
│  │  手动输入 | 随机生成 | 导入/导出 (JSON/YAML)            │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         │ OntologyDocument                     │
│  ┌──────────────────────┴──────────────────────────────────┐  │
│  │  L3: Ontology Hot-Write Pipeline                        │  │
│  │  OntologyVersionManager → Graphiti.add_episode()        │  │
│  │  → Hook 触发 → 图谱自动扩展（无需重启）                 │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         │                                       │
│  ┌──────────────────────┴──────────────────────────────────┐  │
│  │  L4: 现有 SimulationEngine (Phase 2)                    │  │
│  │  沙箱 | 版本管理 | OODA 编排                            │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

---

### L1 决策：Web 可视化服务

**选择**: FastAPI（后端 API/WebSocket）+ 独立 HTML/JS 前端（无需 Node.js 构建链，便于快速迭代）

**核心视图**：
- **事件时间线视图**：按时间戳排列的事件序列，支持播放/暂停/快进
- **实体关系图谱**：D3.js Force Graph，节点=实体，边=关系，颜色=涉事方
- **态势地图**：Leaflet.js 地图叠加层（位置实体、移动轨迹、控制区域）
- **实体属性面板**：点击节点展开基础属性/统计属性/历史变更

**数据协议**：WebSocket 推送 `SimulatorEvent` 流，前端维护本地状态机实现时间线回放。

---

### L2 决策：数据采集与归纳

**联网采集路径**：
```
用户输入事件关键词
  → 联网检索 (Tavily API / SerpAPI，降级到 DuckDuckGo)
  → LLM 归纳（结构化抽取：实体/关系/事件/时间戳）
  → 写入 OntologyDocument（标准 JSON，见 ADR-032）
  → 用户审核确认 → 触发本体写入
```

**手动输入路径**：Web 界面 JSON Schema 表单（基于 OntologyDocument 格式），支持验证和预览。

**随机生成路径**：按指定涉事方（如：红方/蓝方/中立方）和事件模板自动随机填充，使用 LLM 生成合理描述。

**导入/导出**：
- 导出：单个事件、整个场景版本、全量本体快照，格式为 `.odoc.json`
- 导入：校验 OntologyDocument Schema → 冲突检测 → 版本化写入

---

### L3 决策：本体热写入管道

**核心设计**：本体更新不依赖服务重启，通过以下机制实现热生效：

```python
class OntologyHotWritePipeline:
    """
    写入 → 版本化 → 触发 Hook → Graphiti 实时更新
    无需重启服务
    """
    async def ingest(self, doc: OntologyDocument) -> OntologyVersion:
        # 1. 校验格式
        validated = await self.validator.validate(doc)
        
        # 2. 版本化存储（不可变快照）
        version = await self.version_manager.commit(validated)
        
        # 3. 触发 Hook（异步，不阻塞响应）
        await self.hook_system.emit("ontology.updated", {
            "version_id": version.id,
            "diff": version.diff_from_parent,
        })
        
        # 4. Graphiti Episode 写入（核心图谱实时扩展）
        await self.graphiti_writer.write_episode(
            content=doc.to_episode_text(),
            entity_edges=doc.extract_relations(),
        )
        
        return version
```

**热生效保证**：
- Graphiti 的 `add_episode()` 是 idempotent 写入，无需锁定
- `HookSystem.emit()` 异步广播，已订阅的下游（Intelligence Agent、OPA Watcher）自动感知
- 版本号写入 Neo4j 节点属性，查询时可按版本过滤

---

## 后果

### 变得更容易
- ✅ 非技术用户可通过 Web 界面直观查看事件发展脉络
- ✅ 真实事件资料（新闻/报告）可自动归纳为可用于分析的本体数据
- ✅ 模拟数据与图谱保持同步，Intelligence Agent 的 RAG 能立即感知新数据
- ✅ 所有模拟数据格式统一，可沉淀复用

### 变得更难
- ❌ 联网检索需要外部 API（Tavily/SerpAPI），引入外部依赖
- ❌ Web 服务与现有 asyncio 事件循环需要协调运行
- ❌ LLM 归纳质量依赖 Prompt 精度，需要持续迭代
- ❌ 本体热写入并发场景需要考虑写冲突（乐观锁）

## 可逆性
**高**。Web 服务和数据采集层可独立启停。本体热写入管道通过 Hook 系统解耦，可通过禁用 Hook 回退到手动同步模式。

## 相关 ADR
- ADR-018: 模拟领域数据生成引擎（被本 ADR 扩展）
- ADR-036: Palantir AIP Ontology 参考架构（本体格式来源）
- ADR-027: Hook 系统作为可扩展性核心（热写入通知机制）
- ADR-032: 标准化本体 JSON 格式（OntologyDocument 格式定义）
