# ADR-045: 前端可视化选型 — G6 + Leaflet

## 状态
已接受

## 上下文

ODAP 前端需要两类核心可视化能力：

1. **图谱可视化**：展示知识图谱（实体 + 关系）、本体结构、溯源链路
2. **地图可视化**：展示态势图（实体地理位置、移动轨迹、区域标注）

架构梳理阶段（ANOMALY_REPORT I-17/I-18）识别出以下待确认选型：

| 决策点 | 当前方案 | 备选方案 |
|--------|---------|---------|
| 图谱可视化 | ReGraph（商业库，DESIGN 文档中提及） | G6（蚂蚁开源）/ D3.js |
| 地图可视化 | CesiumJS（DESIGN 文档中提及） | Leaflet.js / Mapbox GL |

### 事实发现

经代码审查确认：

- `frontend/package.json` 已安装 `@antv/g6` v5.1.0 + `@ant-design/graphs` v2.1.1
- `frontend/src/components/GraphCanvas.tsx` 已使用 G6：`import { Graph } from '@antv/g6'`
- `frontend/package.json` 已安装 `leaflet` v1.9.4 + `react-leaflet` v5.0.0
- `frontend/src/components/MapView.tsx` 已使用 Leaflet
- ReGraph 是 Cambridge Intelligence 商业产品，需付费授权
- CesiumJS 引入会增加 5MB+ bundle 体积，且 3D 能力当前无需使用

## 决策

**确认维持现有选型**：

1. **图谱可视化 → G6（@antv/g6 v5 + @ant-design/graphs）**
2. **地图可视化 → Leaflet（leaflet + react-leaflet）**

不引入 ReGraph 和 CesiumJS。

## 后果

### 变得更容易

- **零迁移成本**：代码已实现，无需重写
- **无授权风险**：G6（Apache 2.0）、Leaflet（BSD-2）均为开源协议
- **生态协同**：G6 与 @ant-design/graphs、@ant-design/charts 同属 AntV 生态，API 风格统一
- **Bundle 体积可控**：Leaflet ~40KB gzipped，远小于 CesiumJS ~5MB

### 变得更难

- **超大规模图谱**：G6 在 10 万+ 节点场景下性能不如 ReGraph（WebGL 渲染可缓解）
- **3D 地图**：Leaflet 仅支持 2D，如未来需要 3D 地形/地球展示需引入 CesiumJS 或 Mapbox GL
- **高级图分析交互**：ReGraph 的 ReGraph Studio 提供可视化分析工具，G6 需自行开发

### 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 万级以上节点渲染卡顿 | G6 v5 WebGL 渲染模式 + 虚拟滚动 + 聚合 |
| 未来需要 3D 地图 | 按需引入 CesiumJS/Mapbox GL 作为独立页面，不替换 Leaflet |
| G6 v5 API 不稳定 | 锁定 v5.1.x，关注蚂蚁官方升级路线 |

## 可逆性

**高**。图谱和地图组件已封装为独立 React 组件（GraphCanvas.tsx、MapView.tsx），替换渲染引擎只需修改组件内部实现，不影响外部 API。如未来确需 ReGraph 或 CesiumJS，可在对应组件内替换。

## 关联

- 关闭 ANOMALY_REPORT I-17（图谱可视化选型）、I-18（地图可视化选型）
- 关联 ADR-007（React + Ant Design 技术栈）
- 关联 ADR-015（可扩展图表系统）
- 关联 ADR-031（模拟器 Web 可视化）
- 影响 WR-18（Web 前端 v2）
