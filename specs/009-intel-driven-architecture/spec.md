# Spec 009: 情报驱动架构——HE 与 Graphiti 正确定位及分层审计

## 概述

基于 ADR-074，重新定义 Hyper-Extract 和 Graphiti 在 ODAP 项目中的定位，建立分层审计体系，使两者各归其位以支撑"基于外部动态数据实时响应的辅助决策平台（情报系统）"的根本需求。

## 背景

经十轮架构 grilling 审查，发现当前对 HE 和 Graphiti 的使用方式偏离了两者的设计初衷：
- HE 被当作"一次性抽取服务"，未使用 `he feed` 增量演化能力
- Graphiti 被当作"重抽取存储"，每次审计写入门槛 3-9 次 LLM 调用
- 数据摄入与 HE 职责重叠（`NewsIngester._extract_with_llm` 与 HE 重复抽取）
- 审计体系缺失（确认/推理/查询审计均缺失，audit_helper 为占位实现）

## 功能需求

### FR-001: Graphiti 零 LLM 审计（P0）

Graphiti 审计写入必须使用 `EpisodicNode.save(driver)`，**禁止使用 `add_episode`**。

- 在 `graph_service.py` 新增 `save_audit_episode(audit_data: dict, valid_at: datetime)` 方法
- `dual_channel_writer.py` 的 Channel B 改用 `save_audit_episode`
- Channel B 的 content 从"HE 结果文本化"改为"审计事件 JSON"
- 验收：Channel B 写入零 LLM 调用（用 token_tracker 验证）

### FR-002: 数据摄入纯采集化（P0）

删除 `NewsIngester._extract_with_llm`，摄入只负责采集 + 汇总文本。

- 删除 `_extract_with_llm` 方法
- `ingest()` 产出 `OntologyDocument(raw_text=汇总文本, transformation_status="pending", 六字段为空)`
- `ManualInputHandler` 和 `ConflictEventGenerator` 保持不变
- 验收：摄入不再调用 LLM，产出为 pending 态

### FR-003: HE 持续引擎化（P1）

HE 回归"知识摘要构建器"，使用 `he feed` 增量演化。

- 新增 `feed_to_kb(kb_path, text)` 方法
- HE kb 按工作空间/本体分区持久化
- 删除 spec.md FR-017/FR-018 的应用层模板沉淀逻辑
- 验收：同一本体多次抽取复用 HE kb

### FR-004: 数据队列（P1）

Celery + Redis 三级优先级队列。

- `high_priority`：用户主动发起，实时响应
- `normal`：爬虫/订阅采集
- `batch`：历史数据导入
- 验收：失败任务自动重试，优先级正确

### FR-005: MinIO 原始数据持久化（P2）

非结构化原始数据持久化到 MinIO，支持原文回溯。

- MinIO 客户端封装
- OntologyDocument 携带 `raw_data_ref`
- 检索结果可回溯原文
- 验收：原始数据持久化，检索可回溯

### FR-006: 分层审计（P2）

五项审计需求分层实现。

- Graphiti（零 LLM）：#1 数据采集 + #2 抽取过程 + #4 推理过程
- audit_helper（SQLite）：#3 确认过程 + #5 查询过程
- 统一 `AuditEvent` schema
- 关键流程埋点
- 验收：五项审计全部有记录

### FR-007: 多模态处理（P3）

MultimodalRouter + 各类型解析器。

- 文本 → HE / 图片 → OCR / 音频 → ASR / 视频 → VLM
- 混合内容路由分派 + 归集
- 验收：图文混合内容正确路由和归集

### FR-008: AG-UI 协议适配（P3）

统一检索服务输出满足 AG-UI 协议。

- AG-UI 事件层（TEXT_MESSAGE / TOOL_CALL / STATE / STEP）
- 流式返回（SSE）
- HITL Interrupt（低置信度事实确认）
- 生成式 UI 适配
- 外部应用 RESTful 查询接口
- 验收：智能体可通过 AG-UI 消费检索结果

## 非目标

- 不重写 HE 或 Graphiti 的核心逻辑
- 不修改 packages/hyper-extract 目录（应用层适配）
- 不引入 Kafka（Celery + Redis 足够）
- 不在本 spec 实现 ADR-073 的统一检索服务总线（本 spec 仅做 AG-UI 适配层）

## 依赖

- ADR-074（本 spec 的架构决策依据）
- ADR-073（统一检索服务总线，FR-008 的基础）
- spec 006（HE 抽取链，FR-003 的基础）
