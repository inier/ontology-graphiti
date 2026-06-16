# 图谱可视化 Phase 3 待办事项

> 基于 Sigma.js + Cytoscape.js 双引擎架构的增强功能规划

## 3.1 图算法集成（graphology）

| 功能 | 优先级 | 说明 | 依赖 |
|------|--------|------|------|
| 最短路径查询 | P1 | 选中两个节点，高亮最短路径 | graphology-shortest-path |
| 社区发现 | P1 | Louvain 算法自动分组着色 | graphology-communities-louvain |
| 中心性分析 | P2 | Degree/Betweenness/Closeness 中心性排名 | graphology-metrics |
| 连通分量检测 | P2 | 识别孤立子图，提示用户 | graphology-components |
| 路径搜索 UI | P1 | 双击选择起止节点 → 路径高亮面板 | — |

## 3.2 右键菜单（Cytoscape.js 侧）

| 功能 | 优先级 | 说明 | 依赖 |
|------|--------|------|------|
| 节点右键菜单 | P1 | 编辑/删除/聚焦/展开子节点 | cytoscape-cxtmenu |
| 边右键菜单 | P2 | 删除/编辑标签/查看详情 | cytoscape-cxtmenu |
| 画布右键菜单 | P2 | 新增节点/全屏/导出 | cytoscape-cxtmenu |

## 3.3 Tooltip / 悬浮信息

| 功能 | 优先级 | 说明 | 依赖 |
|------|--------|------|------|
| 节点 Tooltip | P1 | 悬浮显示节点属性摘要 | cytoscape-popper (Cytoscape) / 自定义 (Sigma) |
| 边 Tooltip | P2 | 悬浮显示边类型和标签 | 同上 |
| 统一 Tooltip 组件 | P1 | 跨引擎统一的 Tooltip 渲染 | — |

## 3.4 复合节点（Cytoscape.js 侧）

| 功能 | 优先级 | 说明 | 依赖 |
|------|--------|------|------|
| 领域分组 | P2 | 将同领域实体归入父节点 | Cytoscape compound nodes |
| 折叠/展开 | P2 | 点击父节点折叠/展开子节点 | — |
| 分组着色 | P3 | 父节点背景色标识分组 | — |

## 3.5 Sigma.js 交互增强

| 功能 | 优先级 | 说明 | 依赖 |
|------|--------|------|------|
| 节点拖拽 | P1 | 拖拽移动节点位置 | 自定义 DragEventHandler |
| 选中高亮 reducer | P1 | 点击节点 → 关联高亮 + dim 其余 | Sigma nodeReducer/edgeReducer |
| 边标签渲染 | P2 | 缩放到阈值后显示边标签 | sigma-edge-label |
| Lasso 框选 | P3 | 拖拽框选多个节点 | 自定义交互 |

## 3.6 通用增强

| 功能 | 优先级 | 说明 | 依赖 |
|------|--------|------|------|
| 全屏模式 | P2 | 图谱全屏展示 | 浏览器 Fullscreen API |
| 书签/快照 | P3 | 保存当前视图状态（缩放/位置/选中） | localStorage |
| 撤销/重做 | P3 | 布局/选中操作撤销重做 | 自定义 history stack |
| 键盘快捷键 | P2 | Ctrl+F 搜索 / Ctrl+Z 撤销 / Space 适应视图 | — |
| 多选操作 | P2 | Ctrl+点击多选节点 → 批量操作 | — |

## 实施顺序建议

```
3.1 图算法（最短路径 + 社区发现）
  → 3.5 Sigma 交互增强（拖拽 + reducer 高亮）
  → 3.2 右键菜单
  → 3.3 Tooltip
  → 3.6 通用增强（全屏 + 快捷键）
  → 3.4 复合节点
  → 3.6 剩余（书签/撤销/多选）
```
