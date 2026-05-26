# AGENTS.md — AI 代理工作规则

ODAP — 本体驱动分析决策平台。Graphiti 为双时态知识图谱组件。

---

## 技术栈

Python 3.10+, FastAPI, Pydantic v2, SQLite/Neo4j/Redis, OPA, OpenHarness v1/v2 (子模块), React 19/TypeScript/Ant Design 6/Zustand 5, Podman (非 Docker)

---

## 两个 Web 入口（极易混淆，务必区分）

| 入口 | 文件 | 端口 | 何时使用 |
|------|------|------|---------|
| 生产 | `odap/web/app.py` | 8000 | Docker/Podman 部署，uvicorn 启动 |
| 本地开发 | `odap/web/api/app.py` | 8765 | `python main.py --web` |

**规则**: 新增路由必须注册到 `odap/web/app.py`（生产入口），本地开发入口 `odap/web/api/app.py` 有独立路由注册逻辑。

---

## 命令速查

```bash
pip install -r requirements.txt          # 后端（含 -e ./openharness）
cd frontend && npm install               # 前端
python main.py --web                     # 本地后端 :8765
cd frontend && npm run dev               # 前端 :5173（代理 /api → :8000）
pytest tests/unit/ -v                    # 单元测试
pytest tests/integration/ -v             # 集成测试（需 Neo4j）
cd frontend && npm test                  # 前端 Vitest
cd frontend && npm run typecheck         # TS 类型检查
cd frontend && npm run lint              # ESLint
cd frontend && npm run build             # 前端构建
```

容器: `python bootstep.py dev|up|down|restart|rebuild|status|logs|pull|clean`（基于 Podman）

### 开发环境部署规则

前后端服务统一通过 **Podman 容器**部署运行，**禁止在宿主机直接启动 uvicorn/npm dev**：

```bash
python bootstep.py dev          # 启动开发环境（后端 + 前端 + 依赖服务）
python bootstep.py restart      # 重启所有服务（代码修改后必须执行）
python bootstep.py rebuild      # 重新构建镜像（依赖变更后执行）
python bootstep.py status       # 查看服务状态
python bootstep.py logs         # 查看日志
python bootstep.py down         # 停止所有服务
```

**关键约束**:
- 后端服务运行在容器内，端口映射 `8000:8000`，**不要在宿主机 `python -m uvicorn`**
- 前端服务运行在容器内，端口映射 `5173:5173`，**不要在宿主机 `npm run dev`**
- 代码修改后需 `bootstep.py restart` 或 `rebuild` 才能生效
- 容器间通过 Podman 网络通信，服务间引用使用容器名（如 `graphiti-neo4j:7687`，见 `.env.docker`）
- `.env.docker` 为容器环境变量文件，`NEO4J_URI` 等必须使用容器服务名而非 `localhost`

pytest 标记: `unit` / `integration` / `slow` / `e2e`

---

## 项目结构

```
odap/
├── biz/                        # 业务模块（7 个领域）
│   ├── core/                   #   ontology + cognition + agent
│   ├── decision/               #   action_service + decision_pipeline + decision_recommendation
│   ├── integration/            #   openharness_agent + mcp_adapter + hook_system + frontend_compat
│   ├── platform/               #   workspace + roles + skill_system + tool_registry + session_memory
│   ├── data/                   #   data_warehouse + knowledge_base + perception + qa
│   ├── simulation/             #   event_simulator + simulation_sandbox + feedback + visualization
│   └── management/             #   agent_management + business
├── infra/                      # 基础设施
│   ├── graph/                  #   GraphManager (Neo4j 生产 / NetworkX 回退)
│   ├── query/                  #   统一查询服务 (ADR-055)
│   ├── opa/                    #   OPA 策略 (Rego + bundles)
│   ├── security/               #   JWT + OAuth2 + 审计 (SQLite 通道)
│   ├── openharness/            #   v1/v2 适配
│   ├── llm/ monitoring/ resilience/ data_pipeline/ config/ object_service/ storage/ utils/
├── tools/                      # 领域 Skills (base.py + registry.py + 9 个技能包)
├── web/
│   ├── app.py                  #   生产入口
│   ├── api/app.py              #   本地开发入口 (MockDataWebService)
│   ├── gateway/                #   API 网关
│   └── ws/                     #   WebSocket 事件总线
├── celery_app.py + tasks.py    # 异步任务
frontend/src/modules/           # agent ontology workspace ingest qa knowledge roles audit business shared
docker/                         # Dockerfile + compose + Windows 修复
openharness/                    # Git Submodule
tests/                          # unit/ integration/ e2e/
```

---

## 系统架构与数据关系约束规范

### 核心实体关系图

```
User ─┬─ 1:N ─→ Role              (用户拥有多个角色)
      └─ 1:N ─→ Workspace         (用户属于多个工作空间)
                Workspace ─ 1:N ─→ Scenario       (工作空间包含多个场景)
                              Scenario ─ N:M ─→ Ontology     (场景绑定多个本体)
                                            Ontology ─ 1:N ─→ OntologyVersion (本体多版本)
                                            Ontology ─ 1:1 ─→ OntologyDefinition (本体定义)
                              OntologyVersion ─ 1:N ─→ SemanticMap   (语义地图)
                              OntologyVersion ─ 1:N ─→ BusinessRule  (业务规则)
                              OntologyVersion ─ 1:N ─→ LogicModel    (逻辑模型)
                              OntologyVersion ─ 1:N ─→ MetricSystem  (指标体系)
                              OntologyVersion ─ 1:N ─→ BusinessProcess(业务过程)
      Agent ─┬─ N:1 ─→ Role       (智能体关联角色)
             └─ N:1 ─→ Workspace  (智能体关联工作空间)
      Skill ─ N:1 ─→ OntologyDefinition (Skill 关联本体定义)
      Simulation ─ N:1 ─→ Ontology (模拟演练关联本体)
```

### 本体图谱与场景关联规则

- 本体图谱与场景有关，也和本体有关：一个本体有多个对象（实体/关系/事件）
- 图谱数据查询必须基于场景上下文：`场景 → 本体列表 → 图谱对象`
- 智能体问答检索范围 = 当前绑定场景的所有本体图谱数据
- 跨场景图谱数据隔离，禁止未授权跨场景查询

### 1. 用户权限与资源管理

- 每个用户账户可同时关联多个角色身份与工作空间
- 角色与工作空间共同决定用户的系统访问权限与功能可见性
- JWT Payload 必须包含 `role` + `ws_id` + `ws_role`，实现工作空间级隔离

### 2. 工作空间与场景层级关系

- 工作空间作为顶级资源容器，支持创建和管理多个独立场景
- 场景继承工作空间的基础配置，但可拥有独立的场景特定设置
- 工作空间隔离策略由 OPA 策略引擎统一管控

### 3. 场景与本体关联规则

- 单个场景支持绑定多个本体实例（N:M 关系）
- 本体与场景的绑定关系需记录 `created_at`、`bound_by`（绑定人）及 `binding_status`（关联状态）
- 解绑操作需检查是否存在依赖该本体的业务资产，存在则阻止或提示

### 4. 本体版本管理机制

- 每个本体必须支持多版本控制，版本记录需包含：`version_number`、`created_at`、`changelog`（更新内容）、`status`（draft/published/archived）
- 版本变更需保留完整历史记录，支持版本回溯（`switch_version`）与对比（`diff_version`）功能
- 版本提交与切换必须通过场景上下文操作：`/api/workspaces/{ws_id}/scenarios/{sc_id}/commit-version` 和 `switch-version`

### 5. 本体版本数据交互规范

- 本体版本需提供标准化接口接收各类数据输入（实体、关系、事件）
- 数据输入必须包含 `timestamp`、`source_id`（来源标识）及 `checksum`（数据完整性校验）
- 数据写入通过 `unified_audit.py` 记录审计日志，确保数据变更可追溯

### 6. 业务资产与本体版本关联规则

- 语义地图、业务规则、逻辑模型、指标体系及业务过程等业务资产**必须**明确关联特定本体版本（非本体定义）
- 当关联的本体版本发生变更时，相关业务资产需提供更新提示或自动适配机制
- 业务资产查询必须基于关联的本体版本上下文，禁止跨版本混查

### 7. 本体定义与管理规范

- 本体定义为跨版本共享资源，不同版本的同一本体必须使用相同的本体定义（`ontology_definition_id`）
- 本体定义更新**必须**通过创建新本体实现，**禁止**直接修改现有本体定义（不可变原则）
- 本体定义支持通过自然语言输入进行智能提炼与抽取，需提供人工审核确认机制
- 本体状态管理：启用/禁用状态变更需记录操作日志，禁用状态下该本体所有相关数据查询功能应受限

### 8. 智能体配置规则

- 智能体实例**必须**同时关联特定角色与工作空间
- 智能体的功能权限与数据访问范围由关联的角色和工作空间共同决定
- 智能体配置变更需同步更新角色权限缓存

### 9. Skill 管理与本体关联机制

- Skill 的创建、更新与删除操作**必须**关联特定本体定义
- Skill 的功能实现应基于关联本体定义的数据结构与业务规则
- Skill 热更新需同步至 SKILL_CATALOG、SkillManager、DomainHarness 三处注册表

### 10. 模拟演练与本体集成规范

- 模拟演练功能**必须**关联特定本体作为数据基础
- 演练场景的条件设置、流程定义及结果评估均需基于关联本体的结构与规则
- 演练结果需记录关联的本体版本，确保结果可复现

### 系统一致性维护要求

- 建立完整的依赖关系图谱，确保所有实体间关联关系可追溯
- 实现依赖变更自动传播机制：当某实体发生变更时，所有关联实体需同步更新或提供明确的更新提示
- 所有关联变更**必须**记录完整的审计日志，包括 `before_state`（变更前状态）、`change_content`（变更内容）、`changed_at`（变更时间）及 `changed_by`（操作人）信息
- 审计日志通过 `unified_audit.py` 统一写入，通过 `audit_api.py` 统一读取，确保读写链路一致

---

## 核心编码规则

### 1. biz 模块内部结构（必须遵循）

每个 biz 模块按以下分层组织:

```
module_name/
├── api/
│   ├── routes.py       # FastAPI 路由
│   └── schemas.py      # 请求/响应 Pydantic 模型（可选，简单模块可省略）
├── models/             # 领域模型 (Pydantic BaseModel)
├── interfaces/         # 抽象基类 (ABC)
├── impl/               # 接口实现（核心逻辑）
├── services/           # 编排层（连接路由和实现）
└── storage/            # SQLite 持久化（需要持久化的模块）
    ├── __init__.py     #   Storage = SQLiteXxxStorage（别名导出）
    └── sqlite_xxx_storage.py
```

**调用链**: `routes.py → services/ → impl/ → storage/`，禁止跨层调用。

### 2. 路由定义规则

```python
router = APIRouter(prefix="/api/xxx", tags=["xxx"])
xxx_service = XxxService()  # 模块级单例

@router.post("", response_model=XxxResponse)
async def create_xxx(request: CreateXxxRequest):
    try:
        result = xxx_service.create_xxx(...)
        return XxxResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**必须**:
- 前缀统一 `/api/{模块名}`
- `except HTTPException: raise` 透传，防止被 500 兜底吞掉
- 新路由必须在 `odap/web/app.py` 中 `include_router()`

### 3. 服务层返回值规则

**必须**返回 `Dict[str, Any]`，不直接返回 Pydantic 模型:

```python
def get_xxx(self, xxx_id: str) -> Dict[str, Any]:
    xxx = self.manager.get_xxx(xxx_id)
    if not xxx:
        return {"status": "error", "message": "Xxx not found"}  # 错误用此格式
    return {"xxx_id": xxx.id, "name": xxx.name, ...}             # 成功用扁平 dict
```

**类型转换在服务层完成**: Enum→`.value`, datetime→`.isoformat()`, BaseModel→扁平 dict

### 4. 错误处理规则

| 层 | 方式 | 示例 |
|---|------|------|
| impl/ | `raise ValueError("描述")` | 业务校验失败 |
| services/ | 返回 `{"status": "error", "message": "..."}` | 资源不存在等 |
| routes/ | `raise HTTPException(status_code=xxx, detail=...)` | 翻译为 HTTP 状态码 |
| 降级场景 | 不抛异常，返回 Mock/空数据 | 联网检索失败时降级 |

**禁止**: 在路由层直接写业务逻辑；在服务层抛 HTTPException。

### 5. SQLite 存储规则

```python
class SQLiteXxxStorage:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")), "xxx.db")
        self._init_db()

    def _init_db(self):
        # CREATE TABLE IF NOT EXISTS + 可选 _migrate_xxx()

    def save_xxx(self, xxx):       # INSERT OR REPLACE (upsert)
    def get_xxx(self, xxx_id):     # → Xxx | None
    def list_xxxs(self, filters, page, page_size):  # 带分页
```

**必须**:
- 每次操作 `sqlite3.connect()` → 用完 `conn.close()`（无连接池）
- 复杂字段 (Dict/List) → JSON TEXT 列
- Enum → `.value` 字符串存储
- datetime → ISO 字符串存储
- `storage/__init__.py` 别名导出: `Storage = SQLiteXxxStorage`

### 6. 领域模型规则

```python
class XxxStatus(str, Enum):       # 必须 (str, Enum) 双继承
    DRAFT = "draft"
    ACTIVE = "active"

class Xxx(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # uuid4 自动生成
    name: str
    status: XxxStatus = XxxStatus.DRAFT
    tags: List[str] = Field(default_factory=list)               # 容器字段必须 default_factory
    created_at: datetime = Field(default_factory=datetime.now)   # 统一用 datetime.now
```

### 7. 异步模式规则

- 关键路径: `await` 顺序执行
- 非阻塞广播: `asyncio.create_task(...)` (fire-and-forget，如 Hook 广播)
- 降级不回滚: Graphiti 写入失败时仅 log，版本记录保留
- 异步 HTTP: `aiohttp.ClientSession` + `ClientTimeout`
- 单例模式: `_instance` + `get_instance()` / `initialize()`

### 8. 认证鉴权规则

JWT 双 Token: Access 15min / Refresh 7d, HS256, Token Rotation

FastAPI 鉴权依赖:
- `Depends(get_current_user)` — 必须认证
- `Depends(optional_current_user)` — 可选认证
- `Depends(verify_admin)` — 必须 admin 角色

JWT Payload 含 `role` + `ws_id` + `ws_role`（工作空间隔离）。

---

## 测试规则

### 必须遵守

- **新增模块必须同步新增测试文件** — 在 `tests/unit/` 下创建对应 `test_{module}.py`，不允许零测试提交
- **SQLite 存储层用真实临时 DB** — 使用 `tmp_path` fixture 创建 `.db` 文件，不用 MagicMock 模拟数据库
- **修改代码后必须运行 `pytest tests/unit/ -v`** — 全部通过后才算完成
- **测试文件命名** — `test_{模块名}.py`，与 `odap/biz/{领域}/{模块名}/` 对应

### 测试编写模式

- **Fixture 级联**: `mock_storage → xxx_manager`，通过 `patch()` 替换 Storage 类
- **工厂函数**: `_make_xxx(**overrides)` 构造测试数据，默认值 + 覆盖
- **类组织**: `TestSQLiteXxxStorage`, `TestXxxService`, `TestXxxSchemas` 按层分组
- **异常断言**: `pytest.raises(ValueError, match="...")`
- **Mock SQLite**: 仅用于非存储层测试；存储层自身测试用 `tmp_path` 真实 DB
- **延迟导入**: fixture 内部 `from odap.xxx import` 避免模块级导入失败
- **外部依赖 skip**: 依赖 graphiti-core/openharness 等子模块的测试，模块级 `try/except` + `pytest.skip()`

### 每个模块必须覆盖的测试点

| 层 | 必测场景 |
|---|---------|
| storage/ | CRUD 全流程、get 不存在返回 None、delete 不存在返回 False、JSON 字段序列化/反序列化、非法 JSON 容错 |
| models/ | 必填字段验证、默认值、容器字段 default_factory、Enum 值 |
| services/ | 成功返回扁平 dict、错误返回 `{"status": "error"}`、类型转换 (Enum→.value, datetime→.isoformat) |
| routes/ | HTTP 状态码映射、`except HTTPException: raise` 透传、404/400/500 场景 |

---

## 环境变量

`.env.example` → `.env.docker`，必填: `OPENAI_API_KEY`, `OPENAI_API_BASE`, `OPENAI_MODEL`, `NEO4J_URI/USER/PASSWORD`, `JWT_SECRET`

可选: `TAVILY_API_KEY`, `OPA_URL`, `REDIS_URL`, `CORS_ORIGINS`

---

## 陷阱与禁忌

1. **Podman 非 Docker** — bootstep.py 全部使用 podman 命令，不要用 docker 命令
2. **两个 Web 入口** — 本地开发端口 8765，Docker 端口 8000，不要混淆
3. **服务层不抛 HTTPException** — 服务层返回 `{"status": "error"}` dict，由路由层翻译
4. **路由层必须 `except HTTPException: raise`** — 否则已构造的 HTTP 异常会被 500 兜底吞掉
5. **Enum 必须 `(str, Enum)`** — 便于 JSON 序列化，不要用纯 Enum
6. **容器字段必须 `Field(default_factory=...)`** — 不要用 `= []` 或 `= {}`
7. **OpenHarness 子模块** — clone 后必须 `git submodule update --init`
8. **集成测试** — 需要 Neo4j 运行，否则跳过
9. **SQLite 无连接池** — 每次 connect/close，不要保持长连接
10. **新增路由必须注册** — 在 `odap/web/app.py` 中 `include_router()`，否则不生效
11. **开发环境用 Podman 容器** — 不要在宿主机直接 `uvicorn` 或 `npm run dev`，用 `bootstep.py dev/restart`
