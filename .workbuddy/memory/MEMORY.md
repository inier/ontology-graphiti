# 项目长期记忆 — ODAP 本体驱动分析决策平台

## 项目概述
- **项目路径**: `E:\DEMO\AI\ontology-graphiti`
- **系统定位**: ODAP 本体驱动分析决策平台，参考 Palantir AIP 架构
- **核心流程**: WebUI 数据摄入 → 自动构建本体 → 本体查询问答 → 给出执行建议
- **技术核心**: OpenHarness + Graphiti + Python Skill + OPA
- **技术栈**: Python 3.10+ / FastAPI / Pydantic v2 / Neo4j+SQLite / OPA / React 19 / Ant Design 6 / Podman
- **OpenHarness 来源**: HKUDS 开源（GitHub: https://github.com/HKUDS/OpenHarness，MIT）

## 核心架构：四层组件
| 层次 | 组件 | 职责 |
|------|------|------|
| L1 | OpenHarness | Agent Loop + Swarm + Tool 调度 + Permission |
| L2 | Graphiti | 双时态知识图谱 + 时序推理 + RAG 增强 |
| L3 | Python Skills | 领域工具（情报/作战/分析/可视化） |
| L4 | OPA | 策略治理 + 权限校验 + Fail-Close |

### 三 Agent 角色
- **Commander**（强推理模型）: 决策中枢，最终拍板，OPA 校验
- **Intelligence**（快分析模型）: Observe + Orient
- **Operations**（规划模型）: Act + 回写

### OpenHarness 复用矩阵
- **完全复用**: Agent Loop、Tool框架、Skill格式、Plugin系统、Provider管理
- **适配复用**: Memory(→Graphiti)、Permissions(→OPA)、Coordinator(→三Agent)
- **独立扩展**: 战场本体、56领域Skills、时序推理、态势可视化

## Graphiti 集成经验
- ZhipuAIClient 需三层适配：URL 智能拼接 + 字段名映射(`_normalize_fields`) + 缺失字段填充(`_fill_missing_fields`)
- EpisodicNode 字段: `content`(非 episode_body)、`name`、`uuid`、`created_at`
- EntityEdge 字段: `name`、`fact`、`uuid`、`source_node_uuid`、`target_node_uuid`
- Graphiti.search() 返回 `list[EntityEdge]`
- Embedder 需从 chat base_url 推导 embedding base_url（SiliconFlow `Pro/BAAI/bge-m3`）
- Neo4j 驱动内置指数退避重试，必须 `asyncio.wait_for(timeout=15)` 快速失败

## 知识库存储架构（2026-07-01 排查）
- **三种存储路径**（`odap/biz/data/knowledge_base/api/routes.py` upload_document）：
  1. 文本类(txt/md/csv/html/json)+在线文档/网页 → SQLite `data/knowledge_bases.db` 的 `kb_documents.content`，file_url=NULL
  2. 二进制(docx/pdf/xlsx) → MinIO `odap-documents` bucket，key=`kb/{kb_id}/{name}`
  3. MinIO不可用降级 → 本地磁盘 `data/uploads/kb/{kb_id}/`，file_url=`/uploads/kb/...`
- bucket 懒创建（`minio_client.py` ensure_bucket），仅成功上传二进制文件时创建
- 已知问题：当前 docx 文档走了降级路径，MinIO 无 bucket（根因待确认：容器内 minio SDK 或连接）

## 镜像管理（2026-07-02）
- **node-base:24** 自定义基础镜像：`docker/Dockerfile.node-base`
  - 基于 `node:24-alpine`，加装 python3/make/g++/git（node-gyp 依赖）+ pnpm@9
  - 解决 canvas 等原生模块编译失败问题
  - 所有前端 Dockerfile 统一 `FROM localhost/node-base:24`
- `bootstep.py` 的 `BASE_BUILD_IMAGES` 管理自定义基础镜像，`check_missing_images()` 自动构建
- `rebuild node-base` 可单独重建基础镜像

## 演进路线
- Phase 0~3: ✅ 已完成（基础设施→四组件验证→单Agent闭环→三Agent协同→模拟器增强）
- Phase 4: ⬜ 生产化部署（文档体系九步已全部完成，23工作项+6 Sprint，关键路径 WR-01→03→04→05→17→18）

### 关键 ADR（共50个，存放 `docs/07-adr/`）
ADR-001(OpenHarness), 002(Graphiti), 003(OPA), 004(Skill), 005(分层Agent), 006(复用策略), 045(G6+Leaflet), 046(模块化单体), 047(工具注册表P0分步), 048(AI助手独立组件化), 050(统一AI助手与智能问答服务), 051(基于OpenHarness全能力的AI助手架构)
- ANOMALY_REPORT 14条待确认项已全部关闭
- Redis/消息队列 Phase 4 不引入(YAGNI)，Phase 5+ 评估

## 重要文档
- `docs/architecture/ARCHITECTURE.md`（v4.1.0，入口索引）及五层分册(INFRA/TOOLS/BIZ/WEB/EVOLVE)
- `docs/architecture/ARCHITECTURE_AI_ASSISTANT.md` — AI 助手统一架构设计
- `docs/architecture/ARCHITECTURE_AI_ASSISTANT_STANDALONE.md` — AI 助手独立组件化（Host-Plugin分层，ADR-048/049）
- `docs/adr/README.md`（ADR-001~048 索引）
- `docs/TASK_BREAKDOWN.md` / `docs/CHECKLIST.md` / `docs/COMPLETENESS_REPORT.md` / `docs/ANOMALY_REPORT.md`
- 需求三件套: `req-alpha.md`(归档) / `req-beta.md`(归档) / `req-ok.md`(⭐权威)

## 核心文件
- `odap/infra/graphiti/`: Graphiti 客户端
- `odap/infra/opa/`: OPA 策略管理
- `odap/infra/storage/minio_client.py`: MinIO 客户端单例
- `odap/biz/data/knowledge_base/`: 知识库（api/services/storage）
- `odap/biz/swarm/`: Swarm 编排器
- `odap/biz/ontology/`: 本体管理引擎（schema/services/storage/ingestion_split）

## AI 助手架构（2026-07-18 更新：ADR-050 统一方案）

### 当前状态（分裂架构）
- **AI 助手** (`core/assistant/`): ChatService (900行), 16 BaseTool, AG-UI 协议, AIChatPanel 前端
- **智能问答** (`data/qa/`): QAEngineV2 (3000行), 五阶段 RAG Pipeline, 自定义 SSE, 13 个专用组件
- **本体辅助** (`core/ontology/assistant/`): 独立路由, 类型推断/约束建议/完整性检查
- **问题**: 双 SSE 协议、双引擎、双 Hook、会话耦合、能力孤立

### ADR-050 统一方案（2026-07-18）
- **目标**: 合并为 `core/chat/` 统一模块, `/api/chat/` 端点
- **引擎**: UnifiedChatService（组合 tool-calling + RAG pipeline）
- **协议**: AG-UI + CUSTOM 扩展（保留 THINKING/SOURCES/CHART/TEMPORAL/REPORT）
- **前端**: useUnifiedChat + AIChatPanel persona 模式 + 渲染器插件
- **迁移**: 三阶段渐进（Phase A 并行 → Phase B 切换 → Phase C 清理）
- **ADR 文档**: `docs/07-adr/ADR-050_统一AI助手与智能问答服务.md`

## 系统配置与热更新（2026-06-21 修复）
- **配置存储**: SQLite (`data/config.db`)，3张表 `config_items`/`config_schema_registry`/`config_revisions`
- **配置消费链路**: 6层优先级 DB(管理员UI) > USER > WORKSPACE > FILE > ENV(环境变量) > SYSTEM(默认)
- **热更新机制**: ConfigManager 内存缓存 + subscribe/notify 模式
  - OHQueryEngineFactory 订阅 `llm.api_key`/`llm.api_base`/`llm.model`/`llm.temperature` 4个key
  - 变更时自动重建 OpenAI 兼容客户端，无需重启服务
- **前端**: `frontend/src/modules/settings/` — SettingsPage + ConfigGroup + ConfigItemForm + ConnectionTestButton
- **加密**: 敏感字段(api_key/password)通过 `config_encryption.py` AES 加密存储
- **关键文件**: `odap/infra/config_composer.py`(组合引擎), `odap/biz/platform/config/impl/config_manager.py`(核心), `odap/biz/platform/config/storage/sqlite_config_storage.py`(持久化), `odap/biz/platform/config/api/routes.py`(路由)
- **消费入口**: 所有 LLM 相关代码统一使用 `get_config("llm.api_key")` 而非 `os.environ.get()`，确保 DB 配置优先生效

## 开发环境启动排错（2026-07-08）
- **Podman SSH known_hosts Access Denied**: Windows 下 Go SSH 客户端打开 `~/.ssh/known_hosts` 会报 ACL 拒绝。修复：`~/.ssh/config` 加 `Host 127.0.0.1` → `StrictHostKeyChecking no` + `UserKnownHostsFile NUL`（Windows 下 NUL 等同于 /dev/null），并删除空 known_hosts 文件
- **podman_compose.py not found**: bootstep 用 `sys.executable`（受管 Python 3.13.12），而 podman-compose 仅装在 Miniconda。修复：受管 Python `pip install podman-compose`
- **后台任务 vs 前台**: WorkBuddy 后台 Bash 即使 `dangerouslyDisableSandbox=true` 仍可能 HOME 受限、读不到 ssh config。**必须以前台 + dangerouslyDisableSandbox=true 方式运行 `python bootstep.py dev`**（bootstep dev 会自动退出，容器持续后台运行）
- **Neo4j 启动延迟**: 容器 Up 后数据库进程还需 30-60s 初始化，app 的 neo4j 驱动带指数退避重试，最终会自动连上

## 本体模块审计与分层架构（2026-07-18）

### 当前本体模块状态
- **路径**: `odap/biz/core/ontology/` — 20 子模块，名义两层（design/ + application/）
- **L1 设计层**: `design/model/`, `design/version/`, `design/engine/`, `design/contract/` + 游离模块
- **L2 构建层**: 混在 `design/ingestion/`, `design/ingestion_split/`, `design/services/{build,ingest,pipeline,qa_ontology}*`
- **L3 推理层**: ❌ 完全缺失 — 分散在 `cognition/`, `assistant/rules/`, `health/` 4 个模块
- **L4 应用层**: 三套 AI 助手并存 + `application/{oms,runtime,servitization,query,team,harness,abution}`
- **核心问题**: 6 项（构建混入设计、推理缺失、三套助手、application 膨胀、契约不足、游离模块）

### ADR-068: 目标四层架构 (Proposed)
- `design/`(L1) → `construction/`(L2, 新建) → `reasoning/`(L3, 新建) → `application/`(L4)
- 四层契约矩阵: DesignContract → BuildResultContract → ReasoningSvcContract
- 迁移路线: Phase A(推理, 1-2w) → B(构建, 1w) → C(应用+ADR-050, 1w) → D(文档)
- 审计报告: `docs/ARCHITECTURE_AUDIT_ONTOLOGY_LAYERING_2026-07-18.md`
- ADR 文档: `docs/07-adr/ADR-068_本体模块四层分层架构.md`
