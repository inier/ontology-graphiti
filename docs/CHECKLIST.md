# ODAP 工作项 Checklist 汇总

> **版本**: 1.0 | **日期**: 2026-04-19 | **配套**: TASK_BREAKDOWN v2.0
> 本文档为每个 P0/P1 工作项提供逐条验收 Checklist，确保交付无遗漏。

---

## Checklist 使用说明

- 每条 Checklist 项标记 `[ ]` 待完成 / `[x]` 已完成
- **P0 必须全部 ✅** 才能标记工作项完成
- **P1 允许降级**（记录降级理由，后续迭代补齐）
- 测试类 Checklist 包括：单元测试(UT)、集成测试(IT)、端到端测试(E2E)

---

## WR-01: Graphiti 客户端 v2

### 设计与接口

- [ ] WR-01.D1: 双时态查询 API 设计完成（valid_time + transaction_time 参数签名）
- [ ] WR-01.D2: 混合检索策略文档完成（向量→关键词→内存降级规则）
- [ ] WR-01.D3: Episode 批量写入接口设计完成
- [ ] WR-01.D4: 连接池 + 断路器配置参数确定

### 实现

- [ ] WR-01.I1: `query_temporal()` 方法实现（valid_time/transaction_time 过滤）
- [ ] WR-01.I2: `search_hybrid()` 重构（向量权重 + 关键词权重可配置）
- [ ] WR-01.I3: `add_episodes_batch()` 批量写入（去重 + 幂等）
- [ ] WR-01.I4: 连接池（max_size=20, timeout=30s, idle_timeout=300s）
- [ ] WR-01.I5: 断路器（failure_threshold=5, recovery_timeout=60s）
- [ ] WR-01.I6: PerformanceMonitor（查询耗时、缓存命中率、连接池使用率）

### 测试

- [ ] WR-01.T1: 双时态查询 UT（3 种时间范围组合）
- [ ] WR-01.T2: 混合检索降级 UT（模拟 Neo4j 不可用→关键词→内存）
- [ ] WR-01.T3: 批量写入 UT（正常 + 去重 + 部分失败）
- [ ] WR-01.T4: 连接池/断路器 IT（模拟连接超时 + 恢复）
- [ ] WR-01.T5: 查询性能基准（P99 < 200ms for simple, < 1s for complex）

### 验收

- [ ] WR-01.A1: 所有 UT 通过
- [ ] WR-01.A2: IT 在 Docker Neo4j 环境通过
- [ ] WR-01.A3: 回退模式（无 Neo4j）仍可工作
- [ ] WR-01.A4: API 向后兼容（不破坏现有调用方）

---

## WR-02: OPA 策略管理 v2（含权限校验）

### 设计与接口

- [ ] WR-02.D1: 合并方案设计（permission_checker → opa_policy 接口映射）
- [ ] WR-02.D2: ABAC 策略模型设计（主体属性 + 资源属性 + 环境属性 + 操作）
- [ ] WR-02.D3: Bundle 热更新协议设计（增量 vs 全量）
- [ ] WR-02.D4: 策略沙箱接口设计（What-If 输入/输出格式）

### 实现

- [ ] WR-02.I1: permission_checker 代码合并到 opa_policy 模块
- [ ] WR-02.I2: ABAC Rego 策略 v2（支持属性条件表达式）
- [ ] WR-02.I3: Bundle 管理器（策略文件打包 + 版本 + 热推送）
- [ ] WR-02.I4: PolicySandbox（不修改真实策略，模拟决策）
- [ ] WR-02.I5: BatchEvaluator（批量权限检查 + 结果缓存）
- [ ] WR-02.I6: 旧接口兼容层（permission_checker 的公共 API 保持可用）

### 测试

- [ ] WR-02.T1: ABAC 策略 UT（10+ 场景：角色/属性/环境组合）
- [ ] WR-02.T2: Bundle 热更新 IT（推送新策略 → 10s 内生效）
- [ ] WR-02.T3: 策略沙箱 UT（What-If 不影响真实决策）
- [ ] WR-02.T4: 批量检查 UT（100 条请求 < 500ms）
- [ ] WR-02.T5: 兼容性 UT（旧 permission_checker API 全部可用）

### 验收

- [ ] WR-02.A1: 所有 UT/IT 通过
- [ ] WR-02.A2: OPA Docker 连接可用（health_check 通过）
- [ ] WR-02.A3: Mock 模式回退仍可工作
- [ ] WR-02.A4: 无循环依赖（opa_policy 不依赖上层模块）

---

## WR-03: 本体管理引擎 v2

### 设计与接口

- [ ] WR-03.D1: OntologyDocument Schema v2 设计（扩展字段、兼容 v1）
- [ ] WR-03.D2: 语义层映射表设计（业务术语 ↔ 图谱属性）
- [ ] WR-03.D3: 版本管理数据结构设计（版本链 + diff 格式）
- [ ] WR-03.D4: 验证规则引擎设计（质量/一致性/完整性检查项）

### 实现

- [ ] WR-03.I1: OntologyDocument Pydantic 模型 v2（向后兼容 v1）
- [ ] WR-03.I2: SemanticLayer（术语注册 + 属性映射 + 查询翻译）
- [ ] WR-03.I3: VersionManager（创建版本→diff→回退→合并）
- [ ] WR-03.I4: ValidationEngine（10+ 验证规则 + 分级告警）
- [ ] WR-03.I5: 可视化编辑器后端 API（CRUD + 实时预览）

### 测试

- [ ] WR-03.T1: OntologyDocument 序列化/反序列化 UT
- [ ] WR-03.T2: 语义层映射 UT（10+ 业务术语 → 图谱查询）
- [ ] WR-03.T3: 版本管理 UT（创建→修改→回退→diff 验证）
- [ ] WR-03.T4: 验证引擎 UT（有效/无效文档各 5+ 用例）
- [ ] WR-03.T5: 与 Graphiti 集成 IT（本体写入→图谱查询验证）

### 验收

- [ ] WR-03.A1: 所有 UT/IT 通过
- [ ] WR-03.A2: v1 文档可无缝加载
- [ ] WR-03.A3: 语义层查询 P99 < 500ms

---

## WR-04: 工作空间管理

### 设计与接口

- [ ] WR-04.D1: Workspace 数据模型设计（元数据 + 资源绑定 + 权限）
- [ ] WR-04.D2: Neo4j 多数据库隔离方案确认
- [ ] WR-04.D3: OPA Bundle 路径隔离方案确认

### 实现

- [ ] WR-04.I1: WorkspaceManager（CRUD + activate + deactivate）
- [ ] WR-04.I2: Neo4j 多数据库适配（create_database / switch_database）
- [ ] WR-04.I3: OPA Bundle 隔离（workspace_id 前缀路径）
- [ ] WR-04.I4: 导入/导出（.odoc.json 序列化 + 全量/增量模式）
- [ ] WR-04.I5: IWorkspaceProvider 接口（供基础设施层获取当前空间上下文）

### 测试

- [ ] WR-04.T1: Workspace CRUD UT
- [ ] WR-04.T2: 多空间切换 IT（切换后数据隔离验证）
- [ ] WR-04.T3: 导入/导出 UT（全量 + 增量 + 边界情况）
- [ ] WR-04.T4: 并发切换 IT（多请求同时切换不冲突）

### 验收

- [ ] WR-04.A1: 所有 UT/IT 通过
- [ ] WR-04.A2: 空间隔离有效性验证（A 空间查询不到 B 空间数据）
- [ ] WR-04.A3: 切换延迟 < 1s

---

## WR-05: 审计日志系统

### 设计与接口

- [ ] WR-05.D1: AuditEvent 数据模型设计（操作类型 + 主体 + 资源 + 结果 + 时间）
- [ ] WR-05.D2: 异步写入管道设计（Channel 容量 + 批量大小 + 刷盘间隔）
- [ ] WR-05.D3: 防篡改哈希链设计（链式 SHA-256 + 每 1000 条锚点）

### 实现

- [ ] WR-05.I1: AuditLogger 核心（log + start_span + end_span）
- [ ] WR-05.I2: AsyncWritePipeline（asyncio.Channel + 批量落盘）
- [ ] WR-05.I3: CRITICAL 级别同步写入保障
- [ ] WR-05.I4: HashChain（链式哈希 + 验证 + 锚点持久化）
- [ ] WR-05.I5: 查询 API（按时间/主体/操作类型/资源过滤）
- [ ] WR-05.I6: 与 Hook 系统集成（Post-Hook 自动审计）

### 测试

- [ ] WR-05.T1: AuditLogger UT（正常 + 异常 + span 嵌套）
- [ ] WR-05.T2: 异步写入 UT（批量 + 背压 + 优雅关闭）
- [ ] WR-05.T3: CRITICAL 同步写入 UT（确认写入完成后才返回）
- [ ] WR-05.T4: HashChain UT（篡改检测 + 链验证）
- [ ] WR-05.T5: 高并发 IT（1000 ops/s，无丢失）

### 验收

- [ ] WR-05.A1: 所有 UT/IT 通过
- [ ] WR-05.A2: 100% P0 操作覆盖（CRUD + 权限 + Agent 决策）
- [ ] WR-05.A3: 审计写入延迟 P99 < 50ms（异步模式）
- [ ] WR-05.A4: 防篡改验证通过

---

## WR-08: Skill 基础设施 v2

### 设计与接口

- [ ] WR-08.D1: BaseSkill v2 接口设计（execute + validate + describe + health）
- [ ] WR-08.D2: 热插拔协议设计（注册/注销/版本替换 生命周期）
- [ ] WR-08.D3: 17 个 Skill 迁移方案确认（逐个 vs 批量）

### 实现

- [ ] WR-08.I1: BaseSkill v2 抽象类实现
- [ ] WR-08.I2: SkillRegistry v2（热插拔 + 版本管理 + 健康检查）
- [ ] WR-08.I3: 17 个 Skill 逐个迁移到 BaseSkill v2
- [ ] WR-08.I4: SkillInput/SkillOutput Pydantic 模型 v2

### 测试

- [ ] WR-08.T1: BaseSkill v2 UT
- [ ] WR-08.T2: 热插拔 UT（注册→执行→注销→确认不可调用）
- [ ] WR-08.T3: 17 个 Skill 逐个回归测试
- [ ] WR-08.T4: SKILL_CATALOG 兼容性验证

### 验收

- [ ] WR-08.A1: 所有 UT 通过
- [ ] WR-08.A2: 17/17 Skill 迁移完成
- [ ] WR-08.A3: 热插拔不中断正在执行的 Skill
- [ ] WR-08.A4: 旧 Skill 调用方式向后兼容

---

## WR-11: Swarm 编排器 v2

### 设计与接口

- [ ] WR-11.D1: OODA 循环 v2 流程设计（增加 Self-Correction 环节）
- [ ] WR-11.D2: 故障恢复策略设计（Agent 级 + 阶段级 + 任务级）
- [ ] WR-11.D3: 状态持久化格式设计（检查点 JSON Schema）

### 实现

- [ ] WR-11.I1: DomainSwarm v2（Self-Correction + 增强 OODA）
- [ ] WR-11.I2: FaultRecoveryManager v2（三级恢复策略）
- [ ] WR-11.I3: StatePersistenceManager v2（增量检查点 + 压缩）
- [ ] WR-11.I4: HealthMonitor v2（Agent 心跳 + 阈值告警 + 自动降级）
- [ ] WR-11.I5: 与审计日志集成

### 测试

- [ ] WR-11.T1: OODA v2 闭环 IT
- [ ] WR-11.T2: 故障恢复 IT（Agent 崩溃→自动恢复→继续执行）
- [ ] WR-11.T3: 状态持久化 IT（检查点保存→进程重启→恢复继续）
- [ ] WR-11.T4: 流式进度 IT（execute_streaming 输出完整）

### 验收

- [ ] WR-11.A1: 所有 UT/IT 通过
- [ ] WR-11.A2: 单 Agent 崩溃不影响 Swarm 整体
- [ ] WR-11.A3: 恢复时间 < 5 分钟
- [ ] WR-11.A4: 审计日志覆盖所有 OODA 阶段

---

## WR-12: Agent Router v2

### 设计与接口

- [ ] WR-12.D1: 语义路由策略设计（意图分类 → Agent 分发）
- [ ] WR-12.D2: Self-Correction 循环设计（检测→修正→重试 → 上报）

### 实现

- [ ] WR-12.I1: IntentClassifier（意图分类：问答/分析/决策/操作）
- [ ] WR-12.I2: AgentRouter（语义路由 + Worker 工厂）
- [ ] WR-12.I3: SelfCorrectionLoop（输出校验→修正→最多 3 次→上报人工）
- [ ] WR-12.I4: 与 Swarm 编排器集成

### 测试

- [ ] WR-12.T1: 意图分类 UT（20+ 测试用例，覆盖 4 大类 + 模糊意图）
- [ ] WR-12.T2: 路由分发 UT（4 类意图正确分发到对应 Agent）
- [ ] WR-12.T3: Self-Correction UT（错误输出→自动修正→成功）
- [ ] WR-12.T4: 与 Swarm 集成 IT

### 验收

- [ ] WR-12.A1: 所有 UT/IT 通过
- [ ] WR-12.A2: 意图分类准确率 > 90%
- [ ] WR-12.A3: Self-Correction 成功率 > 70%

---

## WR-13: 问答引擎

### 设计与接口

- [ ] WR-13.D1: QAEngine 接口设计（ask / ask_with_tools / escalate）
- [ ] WR-13.D2: RAG Pipeline 设计（检索→排序→注入→生成→溯源）
- [ ] WR-13.D3: 多轮对话上下文管理设计（窗口大小 + 摘要策略）
- [ ] WR-13.D4: 升级策略设计（简单→QAEngine 直处理，复杂→升级 Agent）

### 实现

- [ ] WR-13.I1: QAEngine 核心（单轮 + 多轮对话）
- [ ] WR-13.I2: RAG Pipeline（检索→重排序→Prompt 注入→LLM 生成）
- [ ] WR-13.I3: TemporalQueryParser（"上周"/"事件发生时"→ 时间范围）
- [ ] WR-13.I4: SourceTracer（答案→源 Episode/Entity 溯源链）
- [ ] WR-13.I5: 升级策略（检测复杂度→转交 Intelligence Agent）
- [ ] WR-13.I6: 图表输出（结构化数据→ECharts 配置）

### 测试

- [ ] WR-13.T1: 单轮问答 UT（10+ 问题，覆盖实体/关系/时态查询）
- [ ] WR-13.T2: 多轮对话 UT（上下文延续 + 主题切换）
- [ ] WR-13.T3: RAG Pipeline UT（有检索/无检索/降级模式）
- [ ] WR-13.T4: 时态查询 UT（5+ 时间表达式解析）
- [ ] WR-13.T5: 溯源追踪 UT（答案可追溯到源 Episode）
- [ ] WR-13.T6: 升级策略 UT（简单问题不升级 + 复杂问题升级）
- [ ] WR-13.T7: E2E 测试（用户输入→完整回答+溯源+图表）

### 验收

- [ ] WR-13.A1: 所有 UT/IT/E2E 通过
- [ ] WR-13.A2: 问答 P99 < 3s（含 RAG 检索）
- [ ] WR-13.A3: 溯源覆盖率 100%（所有事实性陈述可溯源）
- [ ] WR-13.A4: 升级判断准确率 > 85%

---

## WR-17: API 网关

### 设计与接口

- [ ] WR-17.D1: 路由表设计（模块→路径→方法映射）
- [ ] WR-17.D2: 认证方案设计（JWT + API Key 双模式）
- [ ] WR-17.D3: 限流策略设计（令牌桶参数 + 分级限流）

### 实现

- [ ] WR-17.I1: FastAPI 路由重构（按 L4-L6 模块分组）
- [ ] WR-17.I2: AuthMiddleware（JWT 验签 + API Key 查询 + 无认证白名单）
- [ ] WR-17.I3: RateLimiter（令牌桶 + 滑动窗口 + 分级：全局/用户/IP）
- [ ] WR-17.I4: PermissionMiddleware（每请求→OPA 策略校验）
- [ ] WR-17.I5: 审计日志中间件（请求→审计事件）
- [ ] WR-17.I6: WebSocket + SSE 端点
- [ ] WR-17.I7: CORS + 错误处理 + 请求日志

### 测试

- [ ] WR-17.T1: 路由 UT（所有路径可达 + 方法匹配）
- [ ] WR-17.T2: 认证 IT（JWT 有效/过期/无效 + API Key 有效/无效）
- [ ] WR-17.T3: 限流 IT（超限返回 429 + 恢复后正常）
- [ ] WR-17.T4: 权限 IT（有权限通过 + 无权限拒绝）
- [ ] WR-17.T5: WebSocket IT（连接→推送→断开→重连）

### 验收

- [ ] WR-17.A1: 所有 UT/IT 通过
- [ ] WR-17.A2: Swagger 文档自动生成且完整
- [ ] WR-17.A3: 限流 P99 延迟增加 < 5ms
- [ ] WR-17.A4: OPA 校验不阻塞正常请求（异步模式）

---

## WR-18: Web 前端 v2

### 设计与接口

- [ ] WR-18.D1: 页面路由设计（/qa, /audit, /ontology, /workspace, /tools, /map）
- [ ] WR-18.D2: 状态管理架构设计（Zustand Store 划分）
- [ ] WR-18.D3: API Client 层设计（axios 实例 + SWR 缓存 + 错误处理）
- [ ] WR-18.D4: 组件分级方案确认（L1-L5 分级，见 COMPONENT_HIERARCHY.md）

### 实现

- [ ] WR-18.I1: 智能问答页（对话 UI + 图表渲染 + 溯源面板）
- [ ] WR-18.I2: 审计日志页（时间线 + 搜索 + 详情抽屉）
- [ ] WR-18.I3: 本体管理页（编辑器 + 版本对比 + 验证状态）
- [ ] WR-18.I4: 工作空间管理页（列表 + 切换 + 导入导出）
- [ ] WR-18.I5: 态势图页（CesiumJS 地图 + 实体标记 + 弹出详情）
- [ ] WR-18.I6: 工具管理页（注册表列表 + 能力发现 + 执行测试）
- [ ] WR-18.I7: Zustand Store 重构（按领域拆分 Store）
- [ ] WR-18.I8: API Client 层（axios + SWR + 拦截器）
- [ ] WR-18.I9: 响应式布局适配（移动端/平板/桌面）
- [ ] WR-18.I10: 国际化（zh-CN / en-US 语言包更新）

### 测试

- [ ] WR-18.T1: 组件单元测试（关键组件：QAChat, AuditTimeline）
- [ ] WR-18.T2: 页面集成测试（页面加载 + API Mock + 用户交互）
- [ ] WR-18.T3: E2E 测试（Playwright：问答→回答→溯源→审计查看）
- [ ] WR-18.T4: 响应式测试（3 种断点：移动/平板/桌面）
- [ ] WR-18.T5: 国际化测试（中英文切换 + 未翻译项检测）

### 验收

- [ ] WR-18.A1: 所有 P0 页面可交互
- [ ] WR-18.A2: 首屏加载 < 3s（本地环境）
- [ ] WR-18.A3: Lighthouse Accessibility > 90
- [ ] WR-18.A4: 无 console.error（生产构建）

---

## WR-19: ADR-039~044 创建

- [ ] ADR-039: 问答引擎架构（RAG + 多轮对话 + 图表输出）
- [ ] ADR-040: API 网关统一入口设计
- [ ] ADR-041: 工作空间资源隔离实现策略
- [ ] ADR-042: 审计日志存储与查询架构
- [ ] ADR-043: Agent Router 语义路由实现
- [ ] ADR-044: 测试策略与自动化框架选择
- [ ] 更新 `docs/adr/README.md` 索引

---

## WR-20: 集成测试框架搭建

- [ ] Docker Compose 配置（Neo4j + OPA + App + Frontend）
- [ ] pytest fixture 管理（数据库初始化/清理）
- [ ] CI Pipeline 配置（GitHub Actions / 本地脚本）
- [ ] 端到端测试脚本（问答链路 + 决策链路 + 推演链路）
- [ ] 测试数据管理（种子数据 + 数据生成器）

---

## WR-21: 性能基准测试

- [ ] 关键链路 P99 延迟基线（问答/图谱查询/OPA 校验）
- [ ] 并发测试（100 并发用户，问答 + 决策混合场景）
- [ ] 长时间稳定性测试（24h 运行，无内存泄漏）
- [ ] 性能测试报告

---

## WR-22: 安全审计与渗透测试

- [ ] OWASP Top 10 检查清单
- [ ] API 安全测试（注入/越权/信息泄露）
- [ ] 认证/鉴权测试（JWT 过期/API Key 泄露/OPA 绕过）
- [ ] 安全审计报告

---

## WR-23: 文档一致性校验

- [ ] DESIGN.md ↔ 代码接口一致性
- [ ] ADR ↔ 实现一致性
- [ ] req-ok 需求 ↔ 模块覆盖一致性
- [ ] TASK_BREAKDOWN ↔ 实际进度一致性
- [ ] 三方对齐报告

---

## 总览：Checklist 统计

| 工作项 | 设计项 | 实现项 | 测试项 | 验收项 | 合计 |
|--------|--------|--------|--------|--------|------|
| WR-01 | 4 | 6 | 5 | 4 | 19 |
| WR-02 | 4 | 6 | 5 | 4 | 19 |
| WR-03 | 4 | 5 | 5 | 3 | 17 |
| WR-04 | 3 | 5 | 4 | 3 | 15 |
| WR-05 | 3 | 6 | 5 | 4 | 18 |
| WR-08 | 3 | 4 | 4 | 4 | 15 |
| WR-11 | 3 | 5 | 4 | 4 | 16 |
| WR-12 | 2 | 4 | 4 | 3 | 13 |
| WR-13 | 4 | 6 | 7 | 4 | 21 |
| WR-17 | 3 | 7 | 5 | 4 | 19 |
| WR-18 | 4 | 10 | 5 | 4 | 23 |
| WR-19 | 7 | — | — | — | 7 |
| WR-20 | 5 | — | — | — | 5 |
| WR-21 | 4 | — | — | — | 4 |
| WR-22 | 4 | — | — | — | 4 |
| WR-23 | 5 | — | — | — | 5 |
| **合计** | **58** | **64** | **53** | **38** | **213** |
