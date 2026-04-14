# 模拟推演引擎 (Simulation Engine) - 设计文档 v2.0

> **优先级**: P0（Phase 3 核心） | **相关 ADR**: ADR-018, ADR-031, ADR-032, ADR-021, ADR-027

**版本**: 2.0.0 | **日期**: 2026-04-14 | **基于**: Phase 2 SimulationEngine v1 + 新需求规范

---

## 1. 模块概述

模拟推演引擎 v2.0 在 Phase 2 沙箱推演基础上，大幅扩展为一个**完整的事件模拟与本体构建平台**，支持：

| 能力维度 | v1 现状 | v2 目标 |
|---------|---------|---------|
| 可视化 | 无 | Web 端时间线 + 关系图谱 + 态势地图 |
| 数据来源 | 代码内置参数 | 联网检索归纳 + 手动输入 + 随机生成 |
| 交互 | Python API | Web 界面 + 导入/导出 |
| 本体同步 | 无 | 热写入，无需重启服务 |
| 数据格式 | 自由结构 dict | 统一 OntologyDocument JSON（ADR-032） |
| 本体版本 | 文件快照 | 版本链 + Graphiti 实时扩展 |

参考实践：Palantir AIP Ontology、NetLogo 多智能体模拟、oTree 多方博弈框架、WorldModels 时序推演。

---

## 2. 整体架构

### 2.1 系统分层

```
┌─────────────────────────────────────────────────────────────────┐
│                     Simulator Enhanced Layer v2.0               │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Layer 1: Web Visualization Service                       │  │
│  │                                                           │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │  │
│  │  │ 时间线面板   │  │ 关系图谱    │  │ 态势地图        │   │  │
│  │  │ (Timeline)  │  │ (GraphView) │  │ (MapOverlay)    │   │  │
│  │  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘   │  │
│  │         │                │                  │            │  │
│  │  ┌──────┴────────────────┴──────────────────┴──────────┐ │  │
│  │  │    事件流接收器 (WebSocket EventStreamReceiver)       │ │  │
│  │  │    + 静态 REST API（场景/实体/版本查询）              │ │  │
│  │  └─────────────────────────────────────────────────────┘ │  │
│  └────────────────────────┬──────────────────────────────────┘  │
│                           │ REST / WebSocket                     │
│  ┌────────────────────────┴──────────────────────────────────┐  │
│  │  Layer 2: Data Ingestion & Normalization                  │  │
│  │                                                           │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │  │
│  │  │ 联网检索采集  │  │ 手动输入     │  │ 随机生成       │  │  │
│  │  │ NewsIngester │  │ ManualInput  │  │ RandomGen      │  │  │
│  │  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘  │  │
│  │         └─────────────────┴──────────────────┘           │  │
│  │                           │                              │  │
│  │  ┌────────────────────────▼─────────────────────────┐   │  │
│  │  │  OntologyNormalizer (LLM 归纳 → OntologyDocument) │   │  │
│  │  │  Schema Validator → 导入/导出 (.odoc.json)        │   │  │
│  │  └─────────────────────────────────────────────────┘    │  │
│  └────────────────────────┬──────────────────────────────────┘  │
│                           │ OntologyDocument                     │
│  ┌────────────────────────┴──────────────────────────────────┐  │
│  │  Layer 3: Ontology Hot-Write Pipeline                     │  │
│  │                                                           │  │
│  │  OntologyVersionManager → OntologyValidator               │  │
│  │       → Graphiti.add_episode()                            │  │
│  │       → HookSystem.emit("ontology.updated")               │  │
│  │       → 图谱自动扩展（无需重启）                          │  │
│  └────────────────────────┬──────────────────────────────────┘  │
│                           │                                      │
│  ┌────────────────────────┴──────────────────────────────────┐  │
│  │  Layer 4: SimulationEngine v1 (Phase 2，保持兼容)         │  │
│  │  SimulationSandbox | ScenarioVersion | OODA Orchestration  │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Layer 1: Web 可视化服务

### 3.1 服务架构

```python
# core/simulator_web_service.py

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
import asyncio
import json

class SimulatorWebService:
    """
    模拟器 Web 服务
    提供 REST API + WebSocket 实时事件流 + 静态前端
    """
    
    def __init__(self, engine: SimulationEngine, pipeline: OntologyHotWritePipeline):
        self.app = FastAPI(title="ODAP Simulator", version="2.0.0")
        self.engine = engine
        self.pipeline = pipeline
        self._clients: set[WebSocket] = set()
        
        # 挂载静态前端
        self.app.mount("/static", StaticFiles(directory="simulator_ui"), name="static")
        
        # 注册路由
        self._register_routes()
        
        # 订阅本体更新 Hook，广播给 WebSocket 客户端
        from core.hook_system import get_hook_system
        get_hook_system().on("ontology.updated", self._broadcast_ontology_update)
    
    # === 场景管理 ===
    
    @app.post("/api/scenarios")
    async def create_scenario(self, request: CreateScenarioRequest):
        """创建新场景"""
    
    @app.get("/api/scenarios/{scenario_id}/timeline")
    async def get_timeline(self, scenario_id: str):
        """获取事件时间线（按时间戳排序的 events 列表）"""
    
    @app.get("/api/scenarios/{scenario_id}/entities")
    async def get_entities(self, scenario_id: str, snapshot_time: str = None):
        """获取实体列表（支持时间点快照）"""
    
    @app.get("/api/scenarios/{scenario_id}/relations")
    async def get_relations(self, scenario_id: str):
        """获取关系图数据（节点 + 边，用于 D3.js）"""
    
    # === 数据写入 ===
    
    @app.post("/api/ingest/manual")
    async def ingest_manual(self, doc: dict):
        """手动输入 OntologyDocument，触发热写入"""
    
    @app.post("/api/ingest/news")
    async def ingest_news(self, request: NewsIngestRequest):
        """联网检索归纳，异步写入"""
    
    @app.post("/api/ingest/random")
    async def ingest_random(self, request: RandomGenRequest):
        """按涉事方随机生成事件"""
    
    # === 导入/导出 ===
    
    @app.get("/api/scenarios/{scenario_id}/export")
    async def export_scenario(self, scenario_id: str, format: str = "odoc"):
        """导出场景为 .odoc.json"""
    
    @app.post("/api/scenarios/import")
    async def import_scenario(self, file: UploadFile):
        """导入 .odoc.json，触发本体写入"""
    
    # === WebSocket 实时流 ===
    
    @app.websocket("/ws/events")
    async def event_stream(self, websocket: WebSocket):
        """实时事件流，推送新写入的 OntologyDocument"""
        await websocket.accept()
        self._clients.add(websocket)
        try:
            while True:
                await websocket.receive_text()  # keep-alive ping
        finally:
            self._clients.discard(websocket)
    
    async def _broadcast_ontology_update(self, event_data: dict):
        """Hook 回调：广播本体更新到所有 WebSocket 客户端"""
        msg = json.dumps({"type": "ontology_update", "data": event_data})
        dead = set()
        for ws in self._clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        self._clients -= dead
```

### 3.2 前端视图设计

前端采用**纯 HTML + Vanilla JS + CDN 依赖**（无需 Node.js 构建），放置于 `simulator_ui/` 目录。

#### 视图1：事件时间线

```
┌──────────────────────────────────────────────────────────────┐
│  ODAP 模拟器 — 事件时间线                          [导入] [导出]│
├──────────────────────────────────────────────────────────────┤
│  场景: B区遭遇战                                              │
│  ◀◀  ◀  ▶  ▶▶  ■  速度: [1x ▼]   时间范围: [全部 ▼]         │
├──────────────────────────────────────────────────────────────┤
│  08:30  [接触] 红方装甲营 ←→ 蓝方机械化步兵营    [查看详情]  │
│  08:35  [行动] 红方 发起 attack → 蓝方           [查看详情]  │
│  08:45  [状态变更] 蓝方机步营 morale: 0.72→0.61  [查看详情]  │
│  09:00  [增援] 蓝方第3连 到达 B区南侧            [查看详情]  │
│  ...                                                         │
├──────────────────────────────────────────────────────────────┤
│  [+ 手动添加事件]   [生成随机事件 for: 红方 ▼]               │
└──────────────────────────────────────────────────────────────┘
```

#### 视图2：实体关系图谱（D3.js Force Graph）

```
┌──────────────────────────────────────────────────────────────┐
│  实体关系图谱                        [筛选: 全部 ▼] [刷新]  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ○ 红方装甲营 ──engaged_with──→ ○ 蓝方机步营               │
│       │                                    │                │
│  commands                             supported_by          │
│       ↓                                    ↓                │
│   ○ 红方指挥部                      ○ 蓝方炮兵营             │
│                                                              │
│  节点颜色: 红方=红, 蓝方=蓝, 中立=灰                         │
│  节点大小: 战力值                                            │
│  点击节点: 展开属性面板                                       │
└──────────────────────────────────────────────────────────────┘
```

#### 视图3：态势地图（Leaflet.js）

```
┌──────────────────────────────────────────────────────────────┐
│  态势地图                             [图层: 全部 ▼] [实体]  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   [ OpenStreetMap 底图 ]                                     │
│                                                              │
│   ▲ 红方装甲营 (39.9, 116.4)   ← 移动轨迹箭头               │
│   ▼ 蓝方机步营 (39.85, 116.42)                               │
│   ⚡ 接触点 (39.875, 116.41)                                 │
│   ⛔ 禁击区 (红色多边形)                                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 视图4：实体属性面板（侧边栏）

```
┌──────────────────────────────────┐
│  红方装甲营                    × │
├──────────────────────────────────┤
│  基础属性                        │
│  side: red                       │
│  status: engaged                 │
│  strength: 320                   │
│  location: B区北侧               │
├──────────────────────────────────┤
│  统计属性                        │
│  combat_power: ████░ 0.78        │
│  morale:       ████░ 0.85        │
│  supply_level: ███░░ 0.60        │
├──────────────────────────────────┤
│  历史版本                        │
│  v20260414-001 (当前)            │
│  v20260413-012                   │
│  [查看变更] [回退到此版本]        │
└──────────────────────────────────┘
```

---

## 4. Layer 2: 数据采集与归纳

### 4.1 联网检索采集（NewsIngester）

```python
# core/news_ingester.py

class NewsIngester:
    """
    联网检索并归纳为 OntologyDocument
    
    检索链路：
    Tavily API (首选) → SerpAPI (备选) → DuckDuckGo HTML 解析 (降级)
    """
    
    def __init__(self, llm_client, search_api_key: str = None):
        self.llm = llm_client
        self.search_client = self._build_search_client(search_api_key)
    
    async def ingest(
        self,
        query: str,
        event_context: str = "",
        max_sources: int = 5
    ) -> list[OntologyDocument]:
        """
        1. 联网检索 query
        2. 汇总多源文本
        3. LLM 抽取 → OntologyDocument 列表
        4. Schema 验证
        """
        # 步骤1: 检索
        search_results = await self.search_client.search(
            query=query,
            max_results=max_sources,
        )
        
        # 步骤2: 汇总
        combined_text = self._combine_sources(search_results)
        
        # 步骤3: LLM 结构化抽取
        raw_docs = await self._extract_with_llm(combined_text, event_context)
        
        # 步骤4: 验证
        validated = []
        for doc in raw_docs:
            result = OntologyDocumentSchema.validate(doc)
            if result.is_valid:
                validated.append(OntologyDocument(**doc))
        
        return validated
    
    async def _extract_with_llm(self, text: str, context: str) -> list[dict]:
        """
        使用 LLM 将新闻文本抽取为 OntologyDocument JSON 列表
        
        Prompt 要点：
        - 按 OntologyDocument schema 输出 JSON
        - 抽取所有可识别实体（部队、武器、地点、指挥官）
        - 抽取关系（指挥、交战、增援、部署）
        - 抽取事件序列（按时间戳排列）
        - 抽取隐含的规则/约束（ROE 相关）
        """
        prompt = ONTOLOGY_EXTRACT_PROMPT.format(
            text=text,
            context=context,
            schema_example=ONTOLOGY_DOCUMENT_SCHEMA_EXAMPLE,
        )
        response = await self.llm.complete(prompt)
        return self._parse_json_response(response)
```

### 4.2 手动输入（ManualInputHandler）

```python
class ManualInputHandler:
    """
    处理用户通过 Web 界面手动输入的动态信息
    
    输入模式：
    1. 结构化表单（基于 JSON Schema 自动渲染）
    2. 自由 JSON 粘贴（服务端验证）
    3. 自然语言输入 → LLM 转换 → OntologyDocument
    """
    
    async def from_form(self, form_data: dict) -> OntologyDocument:
        """从表单数据构建 OntologyDocument"""
    
    async def from_json(self, raw_json: str) -> OntologyDocument:
        """验证并解析 JSON 字符串"""
    
    async def from_natural_language(self, text: str) -> OntologyDocument:
        """自然语言 → OntologyDocument（使用 LLM 转换）"""
```

### 4.3 随机生成（RandomEventGenerator）

```python
class RandomEventGenerator:
    """
    按涉事方和事件模板自动随机生成动态信息
    
    参考 NetLogo 多智能体随机行为模型：
    - 每个涉事方有行为概率表（patrol/attack/retreat/reinforce）
    - 基于当前状态（morale/supply/combat_power）权重调整
    - 事件输出符合 OntologyDocument 格式
    """
    
    PARTY_BEHAVIOR_PROFILES = {
        "red": {
            "attack": 0.4,
            "patrol": 0.3,
            "reinforce": 0.2,
            "retreat": 0.1,
        },
        "blue": {
            "attack": 0.3,
            "patrol": 0.35,
            "reinforce": 0.25,
            "retreat": 0.1,
        },
        "neutral": {
            "patrol": 0.6,
            "evacuate": 0.3,
            "report": 0.1,
        }
    }
    
    async def generate(
        self,
        parties: list[str],
        scenario_context: dict,
        count: int = 1,
        use_llm_for_description: bool = True,
    ) -> list[OntologyDocument]:
        """
        按涉事方生成随机事件
        
        参数:
        - parties: ["red", "blue"] 参与方列表
        - scenario_context: 当前场景状态（影响行为概率权重）
        - count: 生成事件数量
        - use_llm_for_description: 是否用 LLM 生成可读描述
        """
```

### 4.4 导入/导出

```python
class OntologyDocumentIO:
    """
    OntologyDocument 导入/导出管理
    
    文件格式: .odoc.json
    支持：单文档、场景包（多文档 + 版本链）、全量本体快照
    """
    
    async def export_document(self, doc_id: str) -> bytes:
        """导出单个文档为 .odoc.json"""
    
    async def export_scenario(self, scenario_id: str) -> bytes:
        """导出整个场景（含所有事件和版本链）"""
    
    async def export_ontology_snapshot(self) -> bytes:
        """导出当前全量本体快照"""
    
    async def import_file(self, content: bytes) -> list[OntologyDocument]:
        """
        导入 .odoc.json
        步骤：
        1. JSON Schema 验证
        2. 冲突检测（doc_id 去重）
        3. 版本连续性检查
        4. 批量触发热写入
        """
```

---

## 5. Layer 3: 本体热写入管道

### 5.1 热写入核心逻辑

```python
# core/ontology_hot_write_pipeline.py

class OntologyHotWritePipeline:
    """
    本体热写入管道
    
    设计目标：写入数据后立即对系统其他组件生效，无需重启服务。
    
    热生效保障：
    1. Graphiti.add_episode() 是异步写入，立即更新 Neo4j 图
    2. HookSystem.emit() 通知所有订阅者（Intelligence Agent 的 RAG 缓存刷新）
    3. OntologyVersionManager 提供版本化快照，支持回退
    4. 乐观锁（ETag）防止并发写冲突
    """
    
    def __init__(
        self,
        graph_manager: BattlefieldGraphManager,
        hook_system: HookSystem,
        version_manager: OntologyVersionManager,
    ):
        self.graph = graph_manager
        self.hooks = hook_system
        self.versions = version_manager
    
    async def ingest(self, doc: OntologyDocument) -> OntologyVersion:
        """
        完整写入流程
        """
        # 1. Schema 验证
        validated = OntologyDocumentSchema.validate(doc)
        if not validated.is_valid:
            raise OntologyValidationError(validated.errors)
        
        # 2. 版本化（写前快照，不可变）
        version = await self.versions.commit(
            doc=doc,
            parent_version=doc.ontology_version.parent_version,
            message=doc.ontology_version.commit_message,
        )
        
        # 3. 写入 Graphiti（核心图谱实时扩展）
        await self.graph.add_episode(
            content=doc.to_episode_text(),
            episode_type="ontology_document",
            metadata={
                "doc_id": doc.doc_id,
                "doc_type": doc.doc_type,
                "version_id": version.version_id,
                "source_type": doc.source.type,
            }
        )
        
        # 4. 写入实体节点和关系边（Neo4j 直接写入）
        for entity in doc.entities:
            await self.graph.upsert_entity(entity, version_id=version.version_id)
        for relation in doc.relations:
            await self.graph.upsert_relation(relation, version_id=version.version_id)
        
        # 5. 触发 Hook（异步广播，不阻塞当前请求）
        asyncio.create_task(self.hooks.emit("ontology.updated", {
            "version_id": version.version_id,
            "doc_id": doc.doc_id,
            "doc_type": doc.doc_type,
            "entity_count": len(doc.entities),
            "relation_count": len(doc.relations),
            "event_count": len(doc.events),
        }))
        
        return version
    
    async def rollback(self, version_id: str) -> OntologyVersion:
        """回退到指定版本（创建新版本指向历史快照）"""
        target = await self.versions.get(version_id)
        return await self.ingest(target.doc)
```

### 5.2 版本管理

```python
class OntologyVersionManager:
    """
    本体版本管理器
    
    版本ID格式: v{YYYYMMDD}-{seq:03d}
    版本链: 单向链表（parent_version 指针）
    存储: Neo4j 版本节点 + 本地 JSON 快照
    """
    
    async def commit(self, doc: OntologyDocument, ...) -> OntologyVersion:
        """创建版本快照，返回版本信息"""
    
    async def get(self, version_id: str) -> OntologyVersion:
        """获取指定版本"""
    
    async def list(self, limit: int = 50) -> list[OntologyVersion]:
        """列出所有版本（倒序）"""
    
    async def diff(self, version_a: str, version_b: str) -> OntologyDiff:
        """对比两版本的差异（实体/关系/事件增减）"""
    
    async def get_entity_history(self, entity_id: str) -> list[EntitySnapshot]:
        """获取实体跨版本的历史变化"""
```

### 5.3 与 Intelligence Agent 集成（热感知）

```python
# 在 Intelligence Agent 初始化时注册 Hook
def _register_ontology_hooks(self):
    """订阅本体更新事件，自动清除 RAG 缓存"""
    
    async def on_ontology_updated(event_data: dict):
        # 清除相关实体的 RAG 缓存
        self._rag_cache.invalidate_by_doc_type(event_data["doc_type"])
        logger.info(f"RAG 缓存已刷新: {event_data['version_id']}")
    
    get_hook_system().on("ontology.updated", on_ontology_updated)
```

---

## 6. API 设计（FastAPI）

### 6.1 数据写入 API

```
POST   /api/ingest/news          联网检索采集（异步任务）
POST   /api/ingest/manual        手动输入写入
POST   /api/ingest/random        随机生成写入
POST   /api/ingest/import        导入 .odoc.json 文件

GET    /api/ingest/tasks/{id}    查询采集任务状态（联网检索异步）
```

### 6.2 场景管理 API

```
POST   /api/scenarios                     创建场景
GET    /api/scenarios                     列出场景
GET    /api/scenarios/{id}                场景详情
GET    /api/scenarios/{id}/timeline       事件时间线
GET    /api/scenarios/{id}/entities       实体列表（支持 snapshot_time 参数）
GET    /api/scenarios/{id}/relations      关系图数据
GET    /api/scenarios/{id}/export         导出场景
```

### 6.3 版本管理 API

```
GET    /api/versions                      所有版本（分页）
GET    /api/versions/{id}                 版本详情
POST   /api/versions/{id}/rollback        回退到该版本
GET    /api/versions/{id_a}/diff/{id_b}   版本差异对比
GET    /api/entities/{entity_id}/history  实体历史变化
```

### 6.4 WebSocket

```
WS     /ws/events                实时事件流
  → 消息类型:
     ontology_update: {version_id, doc_id, doc_type, entity_count, relation_count}
     entity_changed:  {entity_id, old_state, new_state, version_id}
     simulation_step: {step, events, state_changes}
```

---

## 7. 数据模型

### 7.1 OntologyDocument（完整定义见 ADR-032）

核心字段汇总：

```python
@dataclass
class OntologyDocument:
    schema: str                    # "$schema"
    version: str                   # "$version"
    doc_id: str                    # 全局唯一 ID
    doc_type: DocType              # event / entity / scenario / batch
    source: DataSource             # 数据来源信息
    meta: DocumentMeta             # 标题/描述/标签
    entities: list[OntologyEntity] # 实体列表
    relations: list[OntologyRelation]  # 关系列表
    events: list[OntologyEvent]    # 事件列表
    actions: list[OntologyAction]  # 行动列表（可选）
    rules: list[OntologyRule]      # 规则集合（可选）
    constraints: list[OntologyConstraint]  # 约束集合（可选）
    ontology_version: VersionRef   # 版本引用
    
    def to_episode_text(self) -> str:
        """转换为 Graphiti Episode 文本（人机可读）"""
    
    def extract_relations(self) -> list[dict]:
        """提取实体关系边，用于 Graphiti entity edges"""
```

### 7.2 OntologyEntity 属性分层

```python
@dataclass
class OntologyEntity:
    entity_id: str
    entity_type: str              # Unit / Equipment / Location / Person / Organization
    name: str
    name_en: str
    
    basic_properties: dict        # 标识性：位置/状态/类型/归属方
    statistical_properties: dict  # 数值指标：战力/士气/损耗率
    capabilities: dict            # 能力维度：射程/穿甲/防空
    constraints: list[dict]       # 实体级约束（可覆盖全局约束）
```

---

## 8. 开源参考实践整合

| 参考项目 | 借鉴点 | 应用位置 |
|---------|--------|---------|
| **NetLogo** | 多智能体涉事方行为概率模型 | `RandomEventGenerator.PARTY_BEHAVIOR_PROFILES` |
| **oTree** | 多方交互式输入框架 | Web 界面手动输入多方视角切换 |
| **Palantir AIP** | 本体对象类型/属性/行动/规则四层结构 | `OntologyDocument` 格式设计 |
| **WorldModels** | 时序推演状态转移模型 | `SimulationEngine._simulate_step()` 增强 |
| **OpenCog AtomSpace** | 实时知识图谱更新无需重启 | `OntologyHotWritePipeline` 热写入机制 |
| **STANAG 5500** | 军事实体属性标准（位置/状态/能力） | `OntologyEntity` 基础属性命名 |

---

## 9. 实现计划（Phase 3）

### Slice 3.1：OntologyDocument 标准化（Week 1-2）

| 任务 | 内容 | 产出 |
|------|------|------|
| Schema 定义 | 完整 JSON Schema + Pydantic 模型 | `core/ontology_document.py` |
| 迁移脚本 | 现有 56 条 Episode 迁移为 OntologyDocument | `data/migrate_episodes.py` |
| Schema 验证器 | 输入验证 + 错误消息 | `OntologyDocumentSchema` |

### Slice 3.2：热写入管道（Week 2-3）

| 任务 | 内容 | 产出 |
|------|------|------|
| 热写入核心 | `OntologyHotWritePipeline` | `core/ontology_hot_write_pipeline.py` |
| 版本管理器 | `OntologyVersionManager` | `core/ontology_version_manager.py` |
| Hook 集成 | `ontology.updated` 事件广播 | `core/hook_system.py` 扩展 |
| 单元测试 | 覆盖写入/回退/并发场景 | `tests/test_hot_write.py` |

### Slice 3.3：数据采集层（Week 3-4）

| 任务 | 内容 | 产出 |
|------|------|------|
| 联网检索 | Tavily 集成 + 降级到 DuckDuckGo | `core/news_ingester.py` |
| LLM 抽取 Prompt | OntologyDocument 抽取 Prompt 工程 | `prompts/ontology_extract.md` |
| 手动输入处理 | 表单/JSON/自然语言三种输入 | `core/manual_input_handler.py` |
| 随机生成 | 涉事方行为模型 + LLM 描述生成 | `core/random_event_generator.py` |
| 导入/导出 | `.odoc.json` 格式序列化 | `core/ontology_document_io.py` |

### Slice 3.4：Web 可视化服务（Week 4-6）

| 任务 | 内容 | 产出 |
|------|------|------|
| FastAPI 服务 | REST API + WebSocket | `core/simulator_web_service.py` |
| 时间线前端 | 事件播放/暂停/快进 | `simulator_ui/timeline.html` |
| 关系图谱前端 | D3.js Force Graph | `simulator_ui/graph.html` |
| 态势地图前端 | Leaflet.js 地图叠加 | `simulator_ui/map.html` |
| 主控台 | 统一入口 + 导航 | `simulator_ui/index.html` |
| main.py 集成 | 启动 Web 服务场景 | `main.py` 场景 8 |

### 验收标准

```
1. 用户输入事件关键词 → 联网检索归纳 → 写入图谱 → Web 时间线实时更新（全流程 < 30s）
2. 手动输入动态信息 → 本体热写入 → Intelligence Agent RAG 立即感知（无需重启）
3. Web 界面导出 .odoc.json → 重新导入 → 数据一致（往返幂等）
4. 随机生成10个事件（红方/蓝方各5个）→ 关系图谱正确显示涉事方节点和边
5. 回退到历史版本 → 图谱状态恢复 → 时间线对应更新
```

---

## 10. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-12 | 初始版本，模拟推演引擎基础设计 |
| 2.0.0 | 2026-04-14 | 全面重写：Web 可视化 + 联网采集 + 热写入 + 标准本体格式 |

---

**相关文档**:
- [ADR-031: 模拟器 Web 可视化与实时本体热写入](../../adr/ADR-031_simulator_web_visualization_realtime_ontology.md)
- [ADR-032: 标准化本体文档格式](../../adr/ADR-032_standard_ontology_document_format.md)
- [ADR-018: 模拟战场数据生成引擎](../../adr/ADR-018_模拟战场数据生成引擎.md)
- [ADR-021: 战争实体标准本体库](../../adr/ADR-021_战争实体标准本体库.md)
- [Swarm 编排模块设计](../swarm_orchestrator/DESIGN.md)
- [Hook 系统设计](../hook_system/DESIGN.md)
