# ADR-064: 可观测性基线（OpenTelemetry 统一追踪）

## 状态
Accepted

## 上下文

ADR-046 模块化单体在规模化后最大的运维风险是"看不见"：多团队 Skill（ADR-061）、读写分离图谱（ADR-062）、多租户实例（ADR-063）同时引入后，跨模块 / 跨 Skill / 跨图谱的慢调用与故障传播无法定位。

现有可观测能力：健康检查（ADR-046 提及）、审计日志（ADR-008，但缺统一 `trace_id` 关联）。尚无分布式追踪、无指标体系、日志未结构化关联。

约束：优先无外部依赖过重的方案；团队 3–5 人，运维简单。

## 决策

建立**统一可观测性基线**，作为所有扩展性工作的前置基础（Q1 最先落地）：

1. **统一追踪**：引入 OpenTelemetry（OTel），在核心链路注入并传播 `trace_id`：Agent Loop → Commander/Intelligence/Operations → Skill 调用 → Graphiti / OPA 调用。
2. **指标**：Prometheus 拉取核心指标——请求延迟/吞吐、Skill 执行时长、图谱读写延迟与复制延迟（ADR-062）、租户资源占用（ADR-063）、进程内存/重启（ADR-046 OOM 风险）。
3. **结构化日志**：日志带 `trace_id` + `tenant_id` + `workspace_id`，与现有审计日志（ADR-008）打通，便于按租户/追踪回溯。
4. **采集轻量**：OTel Collector + Prometheus +（可选）Grafana；不引入重量级 APM 厂商锁定。

## 后果

### 变得更容易
- 跨 Skill / 跨图谱慢调用可定位到具体插件与查询。
- 复制延迟（ADR-062）、租户资源（ADR-063）、OOM（ADR-046）有量化看板。
- 故障复盘有完整 trace 链。

### 变得更难
- 需在每个跨进程/跨模块边界埋点（一次性改造，但 ROI 高）。
- 新增 OTel Collector / Prometheus 组件需运维（Docker Compose 增容器）。

## 可逆性
**高**。埋点可逐步移除；组件为旁路采集，移除不影响主链路。

## 关联
- ADR-046（OOM/故障隔离监控）
- ADR-061（跨插件追踪）
- ADR-062（复制延迟/冷热命中监控）
- ADR-063（租户资源监控）
- ADR-008（审计日志带 trace_id）
