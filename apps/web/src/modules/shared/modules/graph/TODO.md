# 图谱可视化 Phase 3 待办事项

> 基于 Sigma.js + Cytoscape.js 双引擎架构的增强功能规划

## 3.1 图算法集成（graphology）

| 功能 | 优先级 | 说明 | 依赖 | 状态 |
|------|--------|------|------|------|
| 最短路径查询 | P1 | 选中两个节点，高亮最短路径 | graphology-shortest-path | ✅ 已完成 |
| 社区发现 | P1 | Louvain 算法自动分组着色 | graphology-communities-louvain | ✅ 已完成 |
| 中心性分析 | P2 | Degree/Betweenness/Closeness 中心性排名 | graphology-metrics | ✅ 已完成（工具函数） |
| 连通分量检测 | P2 | 识别孤立子图，提示用户 | graphology-components | ✅ 已完成（工具函数） |
| 路径搜索 UI | P1 | 双击选择起止节点 → 路径高亮面板 | — | ✅ 已完成 |

## 3.2 右键菜单（Cytoscape.js 侧）

| 功能 | 优先级 | 说明 | 依赖 | 状态 |
|------|--------|------|------|------|
| 节点右键菜单 | P1 | 编辑/删除/聚焦/展开子节点 | cytoscape-cxtmenu | ✅ 已完成 |
| 边右键菜单 | P2 | 删除/编辑标签/查看详情 | cytoscape-cxtmenu | ✅ 已完成 |
| 画布右键菜单 | P2 | 新增节点/全屏/导出 | cytoscape-cxtmenu | ✅ 已完成 |

## 3.3 Tooltip / 悬浮信息

| 功能 | 优先级 | 说明 | 依赖 | 状态 |
|------|--------|------|------|------|
| 节点 Tooltip | P1 | 悬浮显示节点属性摘要 | cytoscape-popper (Cytoscape) / 自定义 (Sigma) | ✅ 已完成 |
| 边 Tooltip | P2 | 悬浮显示边类型和标签 | 同上 | ✅ 已完成 |
| 统一 Tooltip 组件 | P1 | 跨引擎统一的 Tooltip 渲染 | — | ✅ 已完成 |

## 3.4 复合节点（Cytoscape.js 侧）

| 功能 | 优先级 | 说明 | 依赖 | 状态 |
|------|--------|------|------|------|
| 领域分组 | P2 | 将同领域实体归入父节点 | Cytoscape compound nodes | ⏳ 待实现 |
| 折叠/展开 | P2 | 点击父节点折叠/展开子节点 | — | ⏳ 待实现 |
| 分组着色 | P3 | 父节点背景色标识分组 | — | ⏳ 待实现 |

## 3.5 Sigma.js 交互增强

| 功能 | 优先级 | 说明 | 依赖 | 状态 |
|------|--------|------|------|------|
| 节点拖拽 | P1 | 拖拽移动节点位置 | 自定义 DragEventHandler | ✅ 已完成 |
| 选中高亮 reducer | P1 | 点击节点 → 关联高亮 + dim 其余 | Sigma nodeReducer/edgeReducer | ✅ 已完成 |
| 边标签渲染 | P2 | 缩放到阈值后显示边标签 | sigma-edge-label | ⏳ 待实现 |
| Lasso 框选 | P3 | 拖拽框选多个节点 | 自定义交互 | ⏳ 待实现 |

## 3.6 通用增强

| 功能 | 优先级 | 说明 | 依赖 | 状态 |
|------|--------|------|------|------|
| 全屏模式 | P2 | 图谱全屏展示 | 浏览器 Fullscreen API | ✅ 已完成 |
| 书签/快照 | P3 | 保存当前视图状态（缩放/位置/选中） | localStorage | ⏳ 待实现 |
| 撤销/重做 | P3 | 布局/选中操作撤销重做 | 自定义 history stack | ⏳ 待实现 |
| 键盘快捷键 | P2 | Ctrl+F 搜索 / Ctrl+Z 撤销 / Space 适应视图 | — | ✅ 已完成 |
| 多选操作 | P2 | Ctrl+点击多选节点 → 批量操作 | — | ⏳ 待实现 |

## 实施顺序建议

```
3.1 图算法（最短路径 + 社区发现） ✅
  → 3.5 Sigma 交互增强（拖拽 + reducer 高亮） ✅
  → 3.2 右键菜单 ✅
  → 3.3 Tooltip ✅
  → 3.6 通用增强（全屏 + 快捷键） ✅
  → 3.4 复合节点 ⏳
  → 3.6 剩余（书签/撤销/多选） ⏳
```

## 已完成功能汇总

### 新增文件
- [graphAlgo.ts](file:///e:/DEMO/AI/ontology-graphiti/apps/web/src/modules/shared/modules/graph/utils/graphAlgo.ts) — 图算法工具函数（最短路径、社区发现、中心性分析、连通分量检测）
- [PathSearchPanel.tsx](file:///e:/DEMO/AI/ontology-graphiti/apps/web/src/modules/shared/modules/graph/components/PathSearchPanel.tsx) — 最短路径搜索 UI 组件
- [GraphTooltip.tsx](file:///e:/DEMO/AI/ontology-graphiti/apps/web/src/modules/shared/modules/graph/components/GraphTooltip.tsx) — 统一 Tooltip 组件

### 增强文件
- [useSigmaGraph.ts](file:///e:/DEMO/AI/ontology-graphiti/apps/web/src/modules/shared/modules/graph/hooks/useSigmaGraph.ts) — 节点拖拽、选中高亮、最短路径、社区发现着色
- [useCytoscapeGraph.ts](file:///e:/DEMO/AI/ontology-graphiti/apps/web/src/modules/shared/modules/graph/hooks/useCytoscapeGraph.ts) — 右键菜单（节点/边/画布）
- [GraphView.tsx](file:///e:/DEMO/AI/ontology-graphiti/apps/web/src/modules/shared/modules/graph/components/GraphView.tsx) — 暴露新 API 方法
- [GraphCanvas.tsx](file:///e:/DEMO/AI/ontology-graphiti/apps/web/src/modules/shared/modules/graph/components/GraphCanvas.tsx) — 集成路径搜索、社区发现、全屏、快捷键

### 键盘快捷键
- `Ctrl+F` — 打开/关闭路径搜索面板
- `Ctrl+0` — 重置缩放
- `Ctrl+[` — 缩小
- `Ctrl+]` — 放大
- `Space` — 适应视图
- `Esc` — 清除选择/退出全屏