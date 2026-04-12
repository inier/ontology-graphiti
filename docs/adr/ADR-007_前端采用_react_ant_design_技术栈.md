# ADR-007: 前端采用 React + Ant Design 技术栈

> **来源**: `docs/ARCHITECTURE.md` 第 17 章

---


**状态**: 已接受

**上下文**: 需要构建战场前端和管理后台，面临技术选型决策

**决策**: 采用 React 19 + TypeScript + Ant Design 6 作为前端技术栈

**后果**:
- ✅ 企业级组件库，开发效率高
- ✅ TypeScript 类型安全
- ✅ AntV G6 + ECharts 支持图谱可视化
- ✅ CesiumJS 支持地理空间展示
- ❌ 包体积较大
- ❌ 学习曲线（对于新加入的团队成员）

**可逆性**: 中。前端框架切换成本较高，但组件层可抽象。

---