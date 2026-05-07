# 本体管理链路重构 - 检查清单

## Phase 1: 菜单结构调整

- [ ] 1.1 修改 AppLayout.tsx，将「工作空间」移至系统配置区
- [ ] 1.2 验证菜单显示正确

## Phase 2: 数据模型增强

- [ ] 2.1 IngestRecord 添加 version_id 和 logs 字段
- [ ] 2.2 OntologyVersion 添加 ingest_id 和 logs 字段
- [ ] 2.3 ProcessLog 模型定义完整

## Phase 3: 后端处理链路

- [ ] 3.1 数据摄入阶段：记录摄入日志
- [ ] 3.2 数据清洗阶段：实现清洗 Skill
- [ ] 3.3 LLM归纳阶段：实现提取 Skill
- [ ] 3.4 本体构建阶段：实现构建 Skill
- [ ] 3.5 版本管理阶段：实现版本 Skill
- [ ] 3.6 图谱生成阶段：实现图谱 Skill
- [ ] 3.7 审计日志阶段：实现审计 Skill

## Phase 4: OpenHarness SubAgent

- [ ] 4.1 OntologyBuilderAgent 协调各阶段
- [ ] 4.2 IntentRouterAgent 意图路由
- [ ] 4.3 AuditLoggerAgent 审计聚合

## Phase 5: OpenHarness Skill

- [ ] 5.1 data_ingestion_skill 实现
- [ ] 5.2 data_cleaning_skill 实现
- [ ] 5.3 llm_extraction_skill 实现
- [ ] 5.4 ontology_builder_skill 实现
- [ ] 5.5 version_manager_skill 实现
- [ ] 5.6 graph_builder_skill 实现
- [ ] 5.7 audit_logger_skill 实现

## Phase 6: 前端可视化

- [ ] 6.1 数据摄入页面重构：真实处理过程展示
- [ ] 6.2 处理日志展示区域
- [ ] 6.3 摄入历史详情页：完整链路展示
- [ ] 6.4 版本关联：摄入历史 ↔ 版本 双向关联
- [ ] 6.5 版本切换功能
- [ ] 6.6 图谱可视化与版本关联
- [ ] 6.7 审计日志页面独立入口

## Phase 7: 智能问答集成

- [ ] 7.1 认知引擎识别逻辑
- [ ] 7.2 自动路由到本体构建
- [ ] 7.3 问答界面显示构建进度

## Phase 8: 集成验证

- [ ] 8.1 端到端测试：摄入 → 图谱
- [ ] 8.2 版本切换测试
- [ ] 8.3 审计日志查询测试
- [ ] 8.4 智能问答触发本体构建测试
