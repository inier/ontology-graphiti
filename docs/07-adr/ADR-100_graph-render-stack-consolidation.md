---
id: odap.l7.adr-100-graph-render-stack-consolidation
status: active
owner: architect
version: ''
layer: L7
concern: adr
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
---

# ADR-100: 图谱与图表渲染栈收敛（拓扑浏览唯一化）

## Status

**已接受（2026-10-17）**。本轮锁定唯一图谱拓扑栈与唯一图表栈，下线零引用依赖，迁移其余栈，并要求消费设计 Token 的图谱/图表变量。

> 编号说明：任务书要求「ADR-009 起编号」，但 `docs/07-adr/` 实测已存在 ADR-001~090（缺 087，061 重号）。本条原拟自 ADR-091 起编号；2026-10-31 与同期落地的「语义发布生命周期与本体单一写入通道」（占用 ADR-091）撞号，改编为 **ADR-100**。

---

## Background

关联诊断见 `docs/12-evaluation/ARCHITECTURE-EVALUATION.md` §1.3。

**现状（文件:行证据）**：

- `apps/web/package.json:16-62` 同时安装 7 套图谱/图表栈：`cytoscape`(+6 插件)、`@antv/g6`、`sigma`+`@react-sigma/*`、`@xyflow/react`、`@ant-design/graphs`、`graphology`(+8 子包)、`echarts`。
- `@ant-design/graphs@^2.1.1`（`package.json:18`）在 `apps/web/src` **零引用**（grep 0 命中）。
- `@antv/g6@^5.1.0` 仅 `apps/web/src/modules/decision/components/DecisionChainGraph.tsx` 一处引用。
- `cytoscape@^3.34.0` 引用 4 文件（`GraphView.tsx`/`HierarchyGraph.tsx`/`useCytoscapeGraph.ts`/`types/index.ts`），其图算法能力（最短路/社区发现）与 `graphology` 重叠。
- sigma 系：`useSigmaGraph.ts:197` 直接 `new Sigma(...)`（未走 `@react-sigma/core` 上下文），暴露跨引擎 API 不对称（`GraphView.tsx:26-35`）。
- 设计侧功能契约（`docs/04-ui/UIUX-DESIGN-v2.md`）：图谱页（`/ontology/explorer`、`/ontology/semantic-map`、`/ontology/abution-graph` 等）要求图例面板（规则驱动样式 single/range/unique）、选择面板（属性+派生属性置顶 + Search Around 多步 + Reveal Relationships）、节点颜色之外叠加 shape+icon 冗余编码、键盘可达、超大图降级。
- 设计侧已定义 Token：`docs/04-ui/design-tokens.css:521-553` `--odap-graph-*`（节点/边/画布/小地图 + 8 类节点分类色）、`:555-572` `--odap-chart-*`（8 序列色 + 轴/网格/图例/阈值色）。

**问题**：包体膨胀、维护成本随栈数线性增长、跨引擎能力缺口导致组件行为不一致、渲染库自带主题色与设计 Token 冲突。

---

## Decision

采用**按语义分工收敛**（对比矩阵见架构 v2 §6.1），并**明确要求消费设计 Token**：

1. **唯一图谱拓扑栈**：`sigma` + `@react-sigma/core` + `@react-sigma/minimap` + `graphology`（数据结构与布局算法）。
   - 承接全部图谱浏览页（`/ontology/explorer`、`/ontology/semantic-map`、`/ontology/abution-graph` 等）。
   - Sigma 实例生命周期统一经 `@react-sigma/core` 上下文管理（现存 `useSigmaGraph.ts:197` 裸 `new Sigma()` 在 Phase 3 重构）。
2. **唯一编排/关系编辑器栈**：`@xyflow/react`（蓝图/流程编排，语义为「编辑」而非「浏览」，独立保留）。承接现 `BlueprintDesigner` 与由 g6/cytoscape 迁出的 DAG/层级编辑场景。
3. **唯一统计图表栈**：`echarts`（非图拓扑，独立保留）。
4. **下线**：移除 `@ant-design/graphs` 依赖（零引用）。
5. **迁移**：
   - `@antv/g6`（`DecisionChainGraph.tsx`）→ `@xyflow/react`。
   - `cytoscape`（4 文件）→ 浏览/算法迁 `sigma`+`graphology`，层级/DAG 编辑迁 `@xyflow/react`；**不再保留 cytoscape 例外**（其唯一独有能力已被 graphology 覆盖）。
6. **Token 消费（硬约束）**：图谱栈必须消费 `--odap-graph-*`（节点/边/画布/小地图/分类色），图表栈必须消费 `--odap-chart-*`（序列色/轴/网格/图例/阈值）；**禁止渲染库自带主题色**、禁止硬编码色值。颜色之外必须叠加 shape+icon 冗余编码（可访问性），满足设计契约。
7. **新增纪律**：同一语义类别只允许一个库；新增图库须走 ADR。

**备份方案**：若 sigma 系大图（十万级节点）性能不达标，回退至「cytoscape 全量承接浏览」（须重估包体与交互重建成本），但 Token 消费约束不变。

---

## Consequences

**正面**：
- 依赖去重，bundle 下降；维护面从 7 栈降到 3 语义栈（浏览/编辑/统计）。
- 消除 `@ant-design/graphs` 冗余依赖、g6 单点、cytoscape/graphology 能力重复。
- 渲染颜色统一来自设计 Token，主题切换与图谱颜色一致。
- 满足设计侧键盘可达、超大图降级、shape+icon 冗余编码的功能契约。

**负面**：
- g6/cytoscape 迁移需重建部分交互，存在能力降级风险。
- 迁移期需 Feature Flag 灰度与旧栈保留一 release。
- Sigma 上下文重构（裸实例化 → Provider）触及 Minimap 等下游消费方（`GraphCanvas.tsx:360-364`）。
- cytoscape 图算法迁移到 graphology 需验证最短路/社区发现等价性。

---

## Related ADRs

- ADR-015（可扩展图表系统）
- ADR-045（前端可视化 g6/leaflet）
- ADR-092（图标库锁定；节点类型图标与图谱栈协同）
- ADR-093（Design Token；`--odap-graph-*` / `--odap-chart-*` 来源）
