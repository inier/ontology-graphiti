# Web 模块 - 设计文档

> **优先级**: P1 | **相关 ADR**: ADR-007, ADR-031

**版本**: 1.1.0 | **日期**: 2026-04-16

---

## 1. 模块概述

Web 模块提供系统的 Web 服务和 API 接口，支持前端可视化、实时事件推送和数据管理。

**核心组件**:

| 组件 | 位置 | 职责 |
|------|------|------|
| API | `odap/web/api/` | REST API + WebSocket |
| Static | `odap/web/static/` | 静态文件服务 |
| WS | `odap/web/ws/` | WebSocket 处理 |
| Legacy | `odap/web/legacy/` | 遗留界面 |

---

## 2. 核心架构

```
odap/web/
├── api/                    # FastAPI 应用
│   ├── app.py              # MockDataWebService (核心)
│   ├── scenario_store.py   # 场景存储
│   └── routers/            # API 路由
│       ├── scenarios.py     # 场景管理
│       ├── documents.py    # 文档管理
│       └── versions.py     # 版本管理
├── static/                 # 静态文件
│   ├── index.html          # D3.js 可视化界面
│   └── js/                 # 前端 JS
├── ws/                     # WebSocket 处理
│   └── events.py           # 事件推送
└── legacy/                 # 遗留代码
    ├── web_interface.py     # 旧版 Web 界面
    └── dialog_interface.py  # 对话界面
```

---

## 3. MockDataWebService

### 3.1 类图

```python
class MockDataWebService:
    """
    Web 服务主类 - 基于 FastAPI + Uvicorn

    功能:
    - REST API (场景管理、文档写入、版本管理)
    - WebSocket (实时本体更新事件流)
    - 前端 UI (时间线 + 关系图谱 + 态势地图)
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        static_dir: str = None
    ):
        self.host = host
        self.port = port
        self.app = FastAPI()
        self.scenario_store = ScenarioStore()
        self._setup_routes()

    def run(self):
        """启动服务"""
        uvicorn.run(self.app, host=self.host, port=self.port)

    def _setup_routes(self):
        """设置路由"""
```

### 3.2 生命周期

```
启动流程:
1. __init__()
   └── 初始化 scenario_store
2. _setup_routes()
   └── 注册 API 路由
   └── 注册 WebSocket 路由
3. run()
   └── uvicorn.run()
```

---

## 4. API 端点

### 4.1 场景管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/scenarios` | 列出所有场景 |
| POST | `/api/scenarios` | 创建新场景 |
| GET | `/api/scenarios/{id}` | 获取场景详情 |
| DELETE | `/api/scenarios/{id}` | 删除场景 |

### 4.2 文档管理

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/scenarios/{id}/documents` | 添加文档 |
| GET | `/api/scenarios/{id}/documents` | 获取所有文档 |
| GET | `/api/scenarios/{id}/documents/{doc_id}` | 获取单个文档 |
| PUT | `/api/scenarios/{id}/documents/{doc_id}` | 更新文档 |

### 4.3 关系图数据

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/scenarios/{id}/entities` | 获取实体列表 |
| GET | `/api/scenarios/{id}/relations` | 获取关系图数据 (D3.js 格式) |

**Relations API 返回格式**:

```json
{
    "nodes": [
        {
            "id": "entity-001",
            "name": "Entity Name",
            "type": "unit",
            "side": "red",
            "combat_power": 0.8
        }
    ],
    "links": [
        {
            "source": "entity-001",
            "target": "entity-002",
            "type": "located_at",
            "id": "entity-001-entity-002-located_at"
        }
    ]
}
```

### 4.4 版本管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/scenarios/{id}/versions` | 获取版本列表 |
| POST | `/api/scenarios/{id}/versions` | 创建新版本 |
| GET | `/api/scenarios/{id}/versions/{ver}` | 获取指定版本 |
| POST | `/api/scenarios/{id}/rollback/{ver}` | 回滚到指定版本 |

### 4.5 统计信息

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/stats` | 获取图谱统计 |
| GET | `/api/health` | 健康检查 |

---

## 5. WebSocket 事件

### 5.1 端点

```
ws://host:port/ws/events
```

### 5.2 事件格式

```python
@dataclass
class OntologyEvent:
    """本体事件"""
    event_type: str           # "entity_added", "relation_updated", etc.
    scenario_id: str
    document_id: str
    timestamp: datetime
    data: dict               # 事件数据

# 推送示例
{
    "event_type": "entity_added",
    "scenario_id": "default",
    "document_id": "doc-001",
    "timestamp": "2026-04-16T10:00:00",
    "data": {
        "entity_id": "entity-001",
        "entity_type": "unit"
    }
}
```

### 5.3 事件类型

| 事件类型 | 说明 |
|----------|------|
| `entity_added` | 实体添加 |
| `entity_updated` | 实体更新 |
| `entity_deleted` | 实体删除 |
| `relation_added` | 关系添加 |
| `relation_updated` | 关系更新 |
| `version_created` | 版本创建 |
| `rollback_completed` | 回滚完成 |

---

## 6. ScenarioStore

### 6.1 类图

```python
class ScenarioStore:
    """
    场景存储管理器

    职责:
    - 场景的 CRUD
    - 文档管理
    - 版本控制
    """

    def __init__(self):
        self._scenarios: Dict[str, Scenario] = {}
        self._documents: Dict[str, List[OntologyDocument]] = {}
        self._versions: Dict[str, List[Version]] = {}

    def create_scenario(self, name: str, description: str = "") -> str:
        """创建场景"""

    def add_document(self, scenario_id: str, doc: OntologyDocument):
        """添加文档到场景"""

    def get_entities(self, scenario_id: str) -> List[dict]:
        """获取场景实体"""

    def get_relations(self, scenario_id: str) -> Dict[str, Any]:
        """获取关系图数据"""
```

---

## 7. 前端 UI

### 7.1 页面结构

```
odap/web/static/
├── index.html           # D3.js 可视化主页面
├── css/                # 样式文件
│   └── styles.css
└── js/                 # 前端脚本
    ├── main.js          # 主逻辑
    ├── graph.js         # 关系图渲染
    └── timeline.js      # 时间线
```

### 7.2 可视化组件

| 组件 | 技术 | 说明 |
|------|------|------|
| 关系图谱 | D3.js Force-Directed Graph | 节点-边网状展示 |
| 态势地图 | D3.js Geo | 地理信息展示 |
| 时间线 | D3.js Timeline | 事件时间线 |
| 统计面板 | ECharts | 数据统计图表 |

### 7.3 数据流

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 (index.html)                             │
├─────────────────────────────────────────────────────────────┤
│  1. 页面加载 → 调用 /api/scenarios 获取场景                     │
│  2. 选择场景 → 调用 /api/scenarios/{id}/relations 获取图数据    │
│  3. 渲染 D3.js 关系图                                         │
│  4. 建立 WebSocket 连接 /ws/events                            │
│  5. 实时接收事件 → 动态更新图谱                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. 与其他模块的集成

```
┌─────────────────────────────────────────────────────────────┐
│                       Web 模块                                      │
├─────────────────────────────────────────────────────────────┤
│  MockDataWebService ──► ScenarioStore ──► 本地文件系统          │
│  API 端点 ──► GraphManager ──► Neo4j / Graphiti               │
│  WebSocket ──► 实时推送 ◄── OPAManager (权限事件)            │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. 配置

### 9.1 服务配置

```python
# Web 服务配置
WEB_SERVICE_CONFIG = {
    "host": "0.0.0.0",
    "port": 8765,
    "static_dir": None,  # 自动检测
    "cors_enabled": True,
    "cors_origins": ["*"],
}

# 存储配置
STORAGE_CONFIG = {
    "base_path": "./odap/storage",
    "scenario_format": "json",
    "auto_save": True,
    "save_interval_seconds": 30,
}
```

---

## 10. 相关文档

- [ADR-007: 前端采用 React + Ant Design 技术栈](../../adr/ADR-007_前端采用_react_ant_design_技术栈.md)
- [ADR-031: 模拟器 Web 可视化与实时本体热写入](../../adr/ADR-031_simulator_web_visualization_realtime_ontology.md)
- [Mock Engine 模块](../mock_engine/DESIGN.md)
- [Graphiti Client 模块](../graphiti_client/DESIGN.md)
