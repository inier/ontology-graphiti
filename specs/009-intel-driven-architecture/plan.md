# Plan 009: 情报驱动架构实施计划

> ## 版块清理说明（2026-08-07）
>
> 本 plan 的 4 个迭代已全部完成。版块清理后新增以下职责（从 006/007 移交）：
>
> | 移交项 | 来源 | 对应 FR | 状态 |
> |--------|------|---------|------|
> | HE kb 持久化（`he feed`） | 006 SqliteTemplateStorage | FR-003 | ✅ 已实现（Iter 2） |
> | Channel B 零 LLM 审计 | 006 dual_channel_writer | FR-001 | ✅ 已实现（Iter 1） |
> | 操作审计统一（audit_helper） | 007 UnifiedAudit.log_action | FR-006 | ✅ 已实现（Iter 3） |
>
> **注意**：006/007 的代码层面需按各自 spec.md 清理后版本删除应用层模板沉淀、ValidationEngine，并改为委托本 plan 已实现的能力。
> 详见 `specs/REFACTORING-NOTES.md` + `specs/009-intel-driven-architecture/spec.md` 顶部版块清理说明。

## 迭代总览

```
Iter 1 (P0) 核心修正 ✅  → Iter 2 (P1) 引擎与队列 ✅  → Iter 3 (P2) 审计与持久化 ✅  → Iter 4 (P3) 扩展能力 ✅
```

> 全部 4 个迭代已完成。Iter 4 实现：多模态处理模块（MIME 路由 + 4 类解析器 + 结果归集）+ AG-UI 协议适配（SSE 流式检索 + 多跳推理 STEP 可视化 + 低置信度 HITL Interrupt + 查询审计埋点）。
> 累计测试：Iter 4 新增 75 个 + 关联回归 154 个 = 229 个全部通过，零回归。

---

## Iter 1: 核心修正——消除 LLM 浪费和功能重叠（P0）

### 1.1 Graphiti 用法修正

**涉及文件**：
- `apps/api/odap/infra/graph/graph_service.py` — 新增 `save_audit_episode`
- `apps/api/odap/biz/data/hyper_extract/impl/dual_channel_writer.py` — Channel B 改造
- `tests/` — 新增 `test_audit_episode_save.py`

**任务清单**：
1. 在 `graph_service.py` 新增 `save_audit_episode(audit_data, valid_at)` 方法
   - 使用 `EpisodicNode.save(driver)`，零 LLM 调用
   - 参数：audit_data (dict), valid_at (datetime), source_description (str)
2. 在 `dual_channel_writer.py` Channel B 改用 `save_audit_episode`
   - content 从 `_build_episode_text(doc)` 改为 `json.dumps(audit_event)`
   - 删除 `_build_episode_text` 方法
   - 保留 Channel B 失败不影响 Channel A 的容错
3. 新增测试 `test_audit_episode_save.py`
   - 验证零 LLM 调用（mock token_tracker）
   - 验证审计数据完整性
   - 验证 Channel B 失败容错

**验收标准**：
- [x] Channel B 写入零 LLM 调用
- [x] Graphiti Episode 节点携带审计元数据
- [x] Channel B 失败不影响 Channel A

### 1.2 数据摄入纯采集化

**涉及文件**：
- `apps/api/odap/biz/core/ontology/design/ingestion_split/ingestion.py` — 删除 `_extract_with_llm`
- `apps/api/odap/biz/core/ontology/design/schema/document.py` — 确认 pending 态字段
- `tests/` — 修改 `test_ingestion.py`

**任务清单**：
1. 删除 `NewsIngester._extract_with_llm` 方法
2. `ingest()` 产出改为 `OntologyDocument(raw_text=汇总文本, transformation_status="pending", entities=[], relations=[], events=[], actions=[], rules=[], constraints=[])`
3. `ManualInputHandler` 保持不变（用户直接输入结构化 JSON）
4. `ConflictEventGenerator` 保持不变（系统生成结构化事件）
5. 修改测试验证 pending 态产出 + 无 LLM 调用

**验收标准**：
- [x] 摄入不再调用 LLM
- [x] 产出的 OntologyDocument 六字段为空，transformation_status="pending"
- [x] 下游消费者能处理 pending 状态

---

## Iter 2: 持续引擎与队列（P1）

### 2.1 HE 持续引擎化

**涉及文件**：
- `apps/api/odap/biz/data/hyper_extract/impl/he_adapter.py` — 新增 `feed_to_kb`
- `apps/api/odap/biz/data/hyper_extract/services/extract_service.py` — 改为从 kb 读取
- 新增 HE kb 存储路径规范：`data/he_kb/{workspace_id}/{ontology_id}/`

**任务清单**：
1. 新增 `feed_to_kb(kb_path, text)` 方法，调用 HE 的增量演化
2. `extract_from_document` 改为从持久化 kb 读取
3. 删除 spec 006 的 FR-017/FR-018 应用层模板沉淀逻辑
4. kb 按工作空间/本体分区持久化

**验收标准**：
- [x] `feed_to_kb` 使用 HE 原生 `Template.create` + `ka.load` + `ka.feed_text` + `ka.dump`
- [x] `load_from_kb` 读取持久化 KA 累积状态
- [x] `get_kb_path(workspace_id, ontology_id)` 解析 `data/he_kb/{ws}/{ont}/` 路径
- [x] `extract_from_document` 改为 `feed_to_kb` → `load_from_kb` → `merge_and_map` 流程
- [x] `settle_template` / `get_settled_template` / `_validate_settled` 已从 TemplateEngine 移除
- [x] `assess()` 移除 settled-template 短路，始终走全量评估
- [x] kb 按工作空间/本体分区（`data/he_kb/{workspace_id}/{ontology_id}/`）
- [x] 测试：38 template_engine + 25 kb_persistence + 115 关联测试通过

### 2.2 数据队列（Celery + Redis）

**涉及文件**：
- 新增 `apps/api/odap/infra/queue/` 模块
  - `queue_worker.py` — Celery worker 配置 + 三级队列 + `resolve_queue`
  - `tasks.py` — 3 个异步任务定义 + `_impl` 实现函数
  - `dispatcher.py` — 4 个 `dispatch_*` 函数 + `DispatchResult`
  - `__init__.py` — 公共 API 导出
- 修改 `apps/api/odap/biz/core/ontology/design/ingestion_split/news_ingester.py` — 新增 `workspace_id`/`ontology_id` 参数 + `_dispatch_to_queue` 方法
- 新增 `apps/api/tests/unit/test_queue_dispatcher.py` — 54 个测试

**任务清单**：
1. ✅ 新增 `queue_worker.py`（Celery worker 配置）
2. ✅ 定义三级队列：`high_priority` / `normal` / `batch`
3. ✅ 定义异步任务：`process_multimodal_task` / `feed_he_kb_task` / `map_to_ontology_task`
4. ✅ 数据采集层产出后投递到队列

**验收标准**：
- [x] `queue_worker.py` 配置 Celery app（`odap_queue`），支持 Redis broker/backend
- [x] 三级队列定义：`QUEUE_HIGH_PRIORITY` / `QUEUE_NORMAL` / `QUEUE_BATCH`
- [x] `resolve_queue(priority)` 支持 high/normal/batch + 别名（urgent/regular/background 等）
- [x] `CELERY_AVAILABLE` 优雅降级：未安装 celery 时返回 False，所有 dispatch 走同步路径
- [x] `tasks.py` 定义 3 个 celery 任务（`feed_he_kb_task` / `map_to_ontology_task` / `process_multimodal_task`）
- [x] 每个任务有对应 `_impl` 函数，lazy import 服务层，返回 JSON-serializable dict
- [x] `dispatcher.py` 提供 4 个 dispatch 函数 + `DispatchResult` dataclass
- [x] `dispatch_feed_he_kb` 支持 priority 路由 + 模板 + source_doc_id 透传
- [x] `dispatch_ingestion_to_queue` 是 `dispatch_feed_he_kb` 的采集层便捷封装
- [x] `NewsIngester.ingest()` 新增 `workspace_id`/`ontology_id` 参数（向后兼容）
- [x] 当 `ontology_id` 提供时，采集后自动投递到 HE KA 队列（normal 优先级）
- [x] 投递失败仅记录日志，不影响采集产出（容错降级）
- [x] 测试：54 queue_dispatcher + 53 ingestion_split + 31 ingestion + 7 audit + 25 kb + 38 template = 208 通过

---

## Iter 3: 审计与持久化（P2）

### 3.1 MinIO 原始数据持久化

**涉及文件**：
- 新增 `apps/api/odap/infra/storage/raw_data_storage.py` — MinIO 客户端封装 + 本地降级
  - `RawDataStorage` 类：`upload_raw` / `download_raw` / `get_url` / SHA-256 校验和
  - `get_raw_data_storage()` 模块级单例访问器
- 修改 `apps/api/odap/biz/core/ontology/design/schema/document.py` — `OntologyDocument` 新增 `raw_data_ref` 字段
- 修改 `apps/api/odap/biz/core/ontology/design/ingestion_split/news_ingester.py` — 新增 `_upload_raw_data` + `_build_pending_doc` 集成
- 新增 `apps/api/tests/unit/test_iter3_audit_persistence.py` — 14 个原始数据持久化测试

**任务清单**：
1. ✅ 封装 `RawDataStorage`（`upload_raw` / `download_raw` / `get_url`），支持 MinIO 不可用时本地磁盘降级
2. ✅ 摄入产出时上传原始文本，`OntologyDocument` 记录 `raw_data_ref`（格式 `minio://{bucket}/{key}` 或 `file:///{local_path}`）
3. ✅ SHA-256 校验和保证原文完整性（`checksum` 字段）
4. ✅ `OntologyDocument.to_dict()` / `from_dict()` 序列化 `raw_data_ref`，向后兼容缺失字段

**验收标准**：
- [x] `RawDataStorage.upload_raw` 优先尝试 MinIO，失败降级到本地磁盘（`storage_mode` 字段标识 `minio` / `local_fallback`）
- [x] 空文本跳过上传，返回 `status="skipped"`（不产生空文件）
- [x] 本地降级模式自动创建嵌套目录 `data/raw/{workspace_id}/{doc_id}/`
- [x] SHA-256 校验和（hex 64 字符）写入返回结果
- [x] `download_raw` 支持 `minio://` 和 `file:///` 两种 scheme，未知 scheme 返回空字符串
- [x] `OntologyDocument.raw_data_ref` 默认 `None`，`from_dict` 缺失字段时回退到 `None`（向后兼容）
- [x] `NewsIngester._build_pending_doc` 集成 `_upload_raw_data`，空文本时不写入 `raw_data_ref`
- [x] 测试：14 个原始数据持久化测试全部通过

### 3.2 审计层分层实现

**涉及文件**：
- 新增 `apps/api/odap/infra/security/graphiti_audit_writer.py` — 事实演化审计写入器
  - `GraphitiAuditWriter` 类：`log_ingestion_audit` / `log_extraction_audit` / `log_reasoning_audit`（同步）+ `_async` 变体
  - 委托给 `GraphManager.save_audit_episode()`（Iter 1.1 实现，零 LLM 调用）
  - `get_graphiti_audit_writer()` 模块级单例访问器
- 修改 `apps/api/odap/infra/security/audit_helper.py` — 新增 `confirm_audit` / `query_audit` 便捷函数
- 修改 `apps/api/odap/biz/core/ontology/design/ingestion_split/news_ingester.py` — 新增 `_audit_ingestion` 方法（#1 采集审计埋点）
- 修改 `apps/api/odap/biz/data/hyper_extract/services/extract_service.py` — 新增 `_audit_extraction` 方法（#2 抽取审计埋点）
- 新增 `apps/api/tests/unit/test_iter3_audit_persistence.py` — 26 个审计层测试

**任务清单**：
1. ✅ `audit_helper.py` 新增 `confirm_audit`（#3 确认过程审计）+ `query_audit`（#5 查询审计）便捷函数
2. ✅ 新增 `graphiti_audit_writer.py`（事实演化审计：#1 采集 + #2 抽取 + #4 推理），用 `EpisodicNode.save` 零 LLM 写入
3. ✅ 复用 Iter 1.1 `AuditEvent` 数据模型（`audit_models.py`），无需重新定义 dataclass
4. ✅ 关键流程埋点：
   - 采集埋点：`NewsIngester._audit_ingestion` → `writer.log_ingestion_audit`
   - 抽取埋点：`ExtractService._audit_extraction` → `writer.log_extraction_audit_async`
   - 确认埋点：`confirm_audit`（待 Iter 4 HITL 路由接入）
   - 推理埋点：`writer.log_reasoning_audit`（待 Iter 4 推理引擎接入）
   - 查询埋点：`query_audit`（待 Iter 4 检索服务接入）

**验收标准**：
- [x] `GraphitiAuditWriter` 单例模式，`graph_manager` 可注入（测试友好）
- [x] `log_ingestion_audit` / `log_extraction_audit` / `log_reasoning_audit` 三类审计方法均返回 `bool`，失败不抛异常
- [x] 同步版通过 `asyncio.run` / 线程池处理 async `save_audit_episode`，异步版（`_async` 后缀）直接 `await`
- [x] Graphiti 不可用时返回 `False`（degradation_flags 不阻塞业务）
- [x] `audit_data` 包含 `audit_layer` / `audit_type` / `event_type` / `audit_id`（uuid4）等元数据字段
- [x] `confirm_audit` 支持 `confirmed` / `modified` / `rejected` 三种 decision，`rejected` 记为 `denied`
- [x] `query_audit` 自动从 `query_params.retrieval_type` 推导 resource，`result_summary.count` 写入 result_message
- [x] `NewsIngester._audit_ingestion` 在采集完成后调用，审计失败仅记录日志不影响采集产出
- [x] `ExtractService._audit_extraction` 在抽取完成后调用，审计失败不影响抽取产出
- [x] 测试：40 个 Iter 3 测试全部通过（14 持久化 + 26 审计），145 关联测试无回归

---

## Iter 3 完成状态汇总

**新增文件（3 个）**：
- `apps/api/odap/infra/storage/raw_data_storage.py` — MinIO 原始数据持久化
- `apps/api/odap/infra/security/graphiti_audit_writer.py` — 事实演化审计写入器
- `apps/api/tests/unit/test_iter3_audit_persistence.py` — 40 个测试

**修改文件（4 个）**：
- `apps/api/odap/biz/core/ontology/design/schema/document.py` — `raw_data_ref` 字段
- `apps/api/odap/biz/core/ontology/design/ingestion_split/news_ingester.py` — `_upload_raw_data` + `_audit_ingestion`
- `apps/api/odap/biz/data/hyper_extract/services/extract_service.py` — `_audit_extraction`
- `apps/api/odap/infra/security/audit_helper.py` — `confirm_audit` + `query_audit`

**测试统计**：
- Iter 3 新增：40 通过（test_iter3_audit_persistence.py）
- 关联回归：145 通过（test_ingestion_split + test_queue_dispatcher + test_audit_episode_save + test_ingestion）
- **总计 185 测试全部通过，零回归**

**待后续迭代接入**：
- `confirm_audit` 待 Iter 4 HITL 路由层接入
- `log_reasoning_audit` 待 Iter 4 推理引擎接入
- `query_audit` 待 Iter 4 统一检索服务接入

---

## Iter 4: 扩展能力（P3）

### 4.1 多模态处理模块

**涉及文件**：
- 新增 `apps/api/odap/infra/data_pipeline/multimodal_router.py` — MIME 路由 + 解析器 + 归集器
  - `MultimodalRouter` 类：`route` / `route_batch`，按 MIME 前缀策略表分派
  - `TextParser` / `ImageParser`(VLM) / `AudioParser`(ASR) / `VideoParser`(关键帧抽取 → ImageParser)
  - `ResultAggregator` 类：`aggregate`，多模态文本合并 + 加权置信度 + fallback 标记
  - `ParsedModality` / `AggregatedResult` dataclass + `to_dict()` 序列化
  - `get_multimodal_router()` / `get_result_aggregator()` 模块级单例访问器
- 修改 `apps/api/odap/infra/queue/tasks.py` — `process_multimodal_impl` 接入 `MultimodalRouter`
  - text/* 短路到 `feed_he_kb_impl`（无需路由，原文透传）
  - image/audio/video 经 `MultimodalRouter.route` → `ResultAggregator.aggregate` → `feed_he_kb_impl`
  - 解析失败返回 `status="error"`，解析出空文本同样返回 error（不喂空内容给 HE）
- 修改 `apps/api/tests/unit/test_queue_dispatcher.py` — 更新 `TestDispatchProcessMultimodal`
  - 删除原 `not_implemented` 断言（已被真实路由取代）
  - 新增 image/audio/video 三个模态的路由集成测试（mock router + aggregator + feed）
- 新增 `apps/api/tests/unit/test_iter4_multimodal.py` — 47 个测试

**任务清单**：
1. ✅ `MultimodalRouter`：按 MIME 类型分派（策略表 `text/` / `image/` / `audio/` / `video/`，未知 MIME 降级为文本）
2. ✅ `TextParser`（原文透传 + `file://` 协议读取）/ `ImageParser`（复用 `MultimodalProcessor` VLM）/ `AudioParser`（复用 `MultimodalProcessor` ASR）/ `VideoParser`（ffmpeg 关键帧 → ImageParser 降级）
3. ✅ `ResultAggregator`：按模态排序（text→image→audio→video）+ 标签合并文本 + 加权平均置信度（fallback 权重 0.3）+ `all_fallback` 标记
4. ✅ `process_multimodal_impl` 接入路由器，text/* 短路、其它模态经路由后喂 HE KA

**验收标准**：
- [x] `MultimodalRouter.route(mime, source_ref)` 返回 `ParsedModality`，未知 MIME 降级为 text 不抛异常
- [x] `TextParser` 支持 `file:///` 协议读取本地文件，文件不存在时降级返回原文
- [x] `ImageParser` / `AudioParser` 复用 `MultimodalProcessor`，processor 不可用时返回 `fallback=True` 占位结果
- [x] `VideoParser` 通过 ffmpeg 抽取关键帧（失败返回 fallback，不阻塞流程），置信度 ×0.8 打折
- [x] `ResultAggregator.aggregate([])` 返回空 `AggregatedResult`（combined_text="", total_confidence=0.0）
- [x] `ResultAggregator` 按模态排序合并，每段文本带 `[原文]`/`[图像描述]`/`[音频转写]`/`[视频描述]` 标签，fallback 模态追加 `（降级）`
- [x] `ResultAggregator` 加权平均置信度：fallback 权重 0.3，正常权重 1.0，结果保留 4 位小数
- [x] `process_multimodal_impl` 对 text/* 短路到 `feed_he_kb_impl`（不走路由器，避免无谓开销）
- [x] `process_multimodal_impl` 对 image/audio/video 经路由器解析后喂 HE KA，返回 `status/ modality/ model_used/ confidence/ fallback/ extracted_text_length/ feed_result`
- [x] 解析出空文本返回 `status="error"`（不喂空内容给 HE，避免污染 KA）
- [x] 测试：47 multimodal + 8 queue dispatcher 路由集成测试全部通过

### 4.2 AG-UI 协议适配

**涉及文件**：
- 新增 `apps/api/odap/infra/openharness/agui/retrieval_adapter.py` — 检索 → AG-UI 事件流适配器
  - `RetrievalAGUIAdapter` 类：`stream_search` / `stream_chain_search`（AsyncIterator）
  - 事件序列：`RUN_STARTED → STEP_STARTED → TEXT_MESSAGE_* → STEP_FINISHED → RUN_FINISHED`
  - HITL Interrupt 触发：检索结果置信度 < `CONFIDENCE_THRESHOLD`(默认 0.5) → `RUN_FINISHED.outcome.type="interrupt"`
  - 链式推理：每个推理步骤发射 `STEP_STARTED → TEXT_MESSAGE_CONTENT → STEP_FINISHED`（多跳可视化）
  - 循环检测触发 Interrupt（`cycle_detected=True` → confirmation 中断）
  - `query_audit` 埋点（Iter 3.2 #5）fire-and-forget，使用 `result.mode` 而非请求 `mode`
  - `get_retrieval_agui_adapter()` 模块级单例
- 修改 `apps/api/odap/biz/core/ontology/semantic_retrieval/api/routes.py` — SSE 流式端点 + 查询审计埋点
  - 新增 `_emit_query_audit` 辅助函数（统一查询审计埋点，截断 query 至 100 字符不记全文 FR-013）
  - 7 个检索端点接入 `_emit_query_audit`：unified / graph / nl / chain / mdl / metric / hybrid
  - 新增 `_agui_event_stream` 辅助函数（AsyncIterator → `StreamingResponse`，复用 `sse_utils.SSE_HEADERS`）
  - 新增 `POST /stream` 端点（统一检索 SSE 流式返回，FR-008）
  - 新增 `POST /stream/chain` 端点（链式推理 SSE 流式返回 + STEP 可视化）
- 新增 `apps/api/tests/unit/test_iter4_agui_retrieval.py` — 28 个测试

**任务清单**：
1. ✅ 新增 AG-UI 事件层（`RetrievalAGUIAdapter`，复用 `agui_models` 既有事件类型）
2. ✅ 检索结果分块流式返回（SSE，每块 ~200 字符，复用 `sse_utils.SSE_HEADERS`）
3. ✅ 多跳推理步骤可视化（链式检索每个步骤发射 STEP_STARTED/STEP_FINISHED 事件）
4. ✅ 低置信度事实触发 Interrupt（HITL，阈值 0.5，`RUN_FINISHED.outcome.type="interrupt"`）
5. ✅ 循环检测触发 Interrupt（链式推理 `cycle_detected=True` → confirmation 中断）
6. ✅ 外部应用 RESTful 查询接口（`/stream` + `/stream/chain` SSE 端点，强制 `get_current_user` 认证）
7. ✅ 查询审计埋点（7 个检索端点 + 2 个流式端点全部接入 `query_audit`）

**验收标准**：
- [x] `stream_search` 事件序列完整：`RUN_STARTED`(首) → `STEP_STARTED` → `TEXT_MESSAGE_START/CONTENT/END` → `STEP_FINISHED` → `RUN_FINISHED`(尾)
- [x] `TEXT_MESSAGE_CONTENT` 按 ~200 字符分块，结果文本包含模式与数量信息
- [x] 低置信度结果（任一 row.confidence < 0.5）触发 Interrupt，`RUN_FINISHED.outcome.interrupts` 非空，message 含"低置信度"提示
- [x] 高置信度结果不触发 Interrupt，`outcome.type="success"`
- [x] `RetrievalService` 不可用时发射 `RUN_ERROR` 事件（不抛异常到调用方）
- [x] 检索异常发射 `RUN_ERROR` 事件（logger.exception 记录 + 优雅降级）
- [x] `stream_chain_search` 为每个推理步骤发射独立 STEP 事件（`step_1`/`step_2`/...）
- [x] 链式推理循环检测触发 Interrupt，message 含"推理循环"提示
- [x] 无推理步骤时不发射 `TEXT_MESSAGE_*` 事件（空链不产生消息）
- [x] `query_audit` 埋点使用 `result.mode`（实际解析后模式），不使用请求 `mode`（可能为 "auto"）
- [x] `query_audit` 失败不中断流式返回（fire-and-forget + try/except + warning 日志）
- [x] `query` 截断至 100 字符（FR-013 不记全文）
- [x] `POST /stream` 返回 `StreamingResponse`，media_type=`text/event-stream`
- [x] `POST /stream/chain` 返回 `StreamingResponse`，链式推理 STEP 可视化
- [x] 7 个检索端点（unified/graph/nl/chain/mdl/metric/hybrid）全部接入 `_emit_query_audit`
- [x] 流式端点强制认证（`user=Depends(get_current_user)`），符合 project_memory 安全约束
- [x] 测试：28 agui_retrieval 测试全部通过（含 SSE 端点 + 路由审计埋点 + 适配器事件序列）

---

## Iter 4 完成状态汇总

**新增文件（4 个）**：
- `apps/api/odap/infra/data_pipeline/multimodal_router.py` — 多模态路由 + 解析器 + 归集器
- `apps/api/odap/infra/openharness/agui/retrieval_adapter.py` — 检索 → AG-UI 事件流适配器
- `apps/api/tests/unit/test_iter4_multimodal.py` — 47 个多模态测试
- `apps/api/tests/unit/test_iter4_agui_retrieval.py` — 28 个 AG-UI 适配测试

**修改文件（2 个）**：
- `apps/api/odap/infra/queue/tasks.py` — `process_multimodal_impl` 接入 `MultimodalRouter`
- `apps/api/odap/biz/core/ontology/semantic_retrieval/api/routes.py` — SSE 流式端点 + 7 个端点查询审计埋点
- `apps/api/tests/unit/test_queue_dispatcher.py` — 更新多模态路由集成测试（删除 `not_implemented` 断言）

**测试统计**：
- Iter 4 新增：77 通过（48 multimodal + 29 agui_retrieval，含 C1/C2/M3 修复回归测试）
- 关联回归：154 通过（54 queue_dispatcher + 40 iter3_audit_persistence + 53 ingestion_split + 7 audit_episode_save）
- **总计 231 测试全部通过，零回归**

**代码审查修复（6 项）**：
- ✅ C1: TextParser 文件读取失败不再返回 URI 作为文本（改为空串 + fallback=True，避免 HE KA 污染）
- ✅ C2: process_multimodal_impl 全降级时不喂 HE KA（检查 `all_fallback`，避免占位文本污染）
- ✅ M1: VideoParser 临时帧文件改用 `mkstemp` 唯一名 + `finally` 清理（修复泄漏 + 并发竞态）
- ✅ M3: stream_search 异常路径补发 STEP_FINISHED（AG-UI 协议一致性）
- ✅ M4: 移除未使用的 `get_config` 导入 + stdlib 导入移至模块顶部
- ✅ m3: 流式端点 `/stream` + `/stream/chain` 增加 try/except + HTTPException 透传
- ✅ m4: query_audit 埋点移入 try/finally，客户端断连时保证审计执行

**Iter 3 待办接入项全部完成**：
- ✅ `query_audit` 已接入统一检索服务（7 端点 + 2 流式端点）
- ⏳ `confirm_audit` 待 HITL 路由层接入（需 Iter 5 前端 HITL 审批 UI）
- ⏳ `log_reasoning_audit` 待推理引擎独立化接入（当前 chain_search 已通过 query_audit 间接覆盖）

---

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| Graphiti `EpisodicNode.save` API 在 0.28 版本可能不稳定 | 先写 PoC 验证 API 可用性 |
| 删除 `_extract_with_llm` 可能影响下游消费者 | 先全量搜索 `_extract_with_llm` 的调用点 |
| Celery 引入增加运维复杂度 | Redis 已有依赖，Celery 是成熟方案 |
| HE `he feed` 命令的增量合并行为未验证 | Iter 2 先写 PoC 验证 `he feed` |
