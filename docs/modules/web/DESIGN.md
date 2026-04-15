# Web 模块 - 设计文档

> **优先级**: P1 | **相关 ADR**: ADR-007, ADR-031

**版本**: 1.0.0 | **日期**: 2026-04-16

---

## 1. 模块概述

Web 模块提供系统的 Web 服务和 API 接口。

**核心组件**:

| 组件 | 位置 | 职责 |
|------|------|------|
| API | `odap/web/api/` | REST API + WebSocket |
| Static | `odap/web/static/` | 静态文件服务 |
| WS | `odap/web/ws/` | WebSocket 处理 |
| Legacy | `odap/web/legacy/` | 遗留界面 |

---

## 2. 架构

```
odap/web/
├── api/           # FastAPI 应用
│   ├── app.py     # MockDataWebService
│   └── ...
├── static/        # 静态文件
│   └── index.html # Web UI
├── ws/            # WebSocket 处理
└── legacy/        # 遗留代码
```

---

## 3. API 端点

### 3.1 场景管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/scenarios` | 列出场景 |
| POST | `/api/scenarios` | 创建场景 |
| GET | `/api/scenarios/{id}` | 获取场景详情 |
| GET | `/api/scenarios/{id}/relations` | 获取关系图数据 |

### 3.2 WebSocket

| 端点 | 说明 |
|------|------|
| `/ws/events` | 实时事件流 |

---

## 4. 相关文档

- [ADR-007: 前端采用 React + Ant Design 技术栈](../../adr/ADR-007_前端采用_react_ant_design_技术栈.md)
- [ADR-031: 模拟器 Web 可视化与实时本体热写入](../../adr/ADR-031_simulator_web_visualization_realtime_ontology.md)
