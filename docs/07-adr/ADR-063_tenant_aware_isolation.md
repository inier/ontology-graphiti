# ADR-063: 租户感知隔离与部署蓝图

## 状态
Accepted

## 上下文

ADR-041 解决了**单部署内**的工作空间（Workspace）隔离（图谱标签/多库、OPA Bundle 前缀、Skill 配置、本体版本）。但随着"多客户/多部门独立交付"需求出现，现有模型存在根本缺口：

- **Workspace ≠ Tenant**。Workspace 是单平台内的场景隔离；Tenant 是给不同客户/部门**独立部署并隔离数据与策略**。
- 当前无租户模型、无 per-customer 数据/策略隔离、无部署自动化，无法支撑"给多个客户独立交付"。

约束：维持 ADR-046 模块化单体（每实例单进程）；团队 3–5 人，先不引入 K8s Service Mesh。

## 决策

采用 **每租户独立部署（专用）+ 部署蓝图（GitOps）**，并预留向逻辑多租户演进的空间：

1. **隔离器升级**：将 `WorkspaceIsolator`（ADR-041）升级为 `TenantIsolator`，隔离维度从 `workspace_id` 扩展为 `tenant_id + workspace_id` 两级：
   - 图谱：企业版走多数据库（`tenant_{id}`），社区版走 `tenant_id` + `workspace_id` 标签过滤。
   - OPA：`/tenants/{t}/workspaces/{w}/policies/` Bundle 前缀。
   - 配置：`ConfigManager`（现有）命名空间按 `tenant_id` 隔离。
2. **部署蓝图（Deployment Blueprint）**：参数化 Compose / K8s 模板 + GitOps 仓库；新租户开通 = 生成带 `tenant_id` 的配置集并自动部署（复用 `bootstep.py` 思路）。
3. **默认形态**：每租户一个模块化单体实例（ADR-046）。当租户数与运维成本失衡时，再评估演进为**单部署逻辑多租户**（B 方案），届时 `TenantIsolator` 已就位，改造面可控。

## 后果

### 变得更容易
- 交付可复制：新客户 = 一份蓝图参数，自动化开通。
- 隔离最强：每租户独立进程与（可选）独立数据库，合规友好。
- 演进平滑：`TenantIsolator` 两级模型同时支撑"专用部署"与未来"逻辑多租户"。

### 变得更难
- 运维成本随租户数**线性增长**（用部署蓝图 + 开通自动化对冲）。
- 跨租户能力（如平台级统计、统一升级）需额外聚合层。
- 升级需逐租户滚动，版本矩阵需管理。

## 可逆性
**高**。每租户独立部署本就是物理隔离；若未来合并为逻辑多租户，`TenantIsolator` 接口不变，仅部署形态变化。

## 关联
- ADR-041（工作空间隔离，升级为两级隔离的基础）
- ADR-046（模块化单体，每租户实例的底座）
- ADR-012（配置组合引擎，租户命名空间隔离）
- ADR-008（审计日志，需带 `tenant_id` 维度）
