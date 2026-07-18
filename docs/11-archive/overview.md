# 统一 AI 助手与智能问答 — 架构设计总结

## 做了什么

编写了 **ADR-050**（统一 AI 助手与智能问答后端服务），并绘制了当前/目标架构对比图。

## 核心决策

将当前分裂的两套 AI 对话系统合并为单一的 `core/chat/` 模块：

| 维度 | 当前 | 目标 |
|------|------|------|
| 后端模块 | `core/assistant/` + `data/qa/` + `core/ontology/assistant/` | `core/chat/` 统一模块 |
| API 端点 | `/api/assistant/` + `/api/qa/` | `/api/chat/` |
| SSE 协议 | AG-UI + 自定义（两套） | AG-UI + CUSTOM 扩展（一套） |
| 对话引擎 | ChatService + QAEngineV2 | UnifiedChatService |
| 前端 Hook | useAIChat + useQAI | useUnifiedChat |
| 前端组件 | AIChatPanel + 13 QA 组件 | AIChatPanel + 渲染器插件 |

## 迁移策略

- **Phase A**：建立 `core/chat/`，旧路由并行保留
- **Phase B**：逐步切换前端入口到统一端点
- **Phase C**：清理旧代码

## 文件产出

- `docs/07-adr/ADR-050_统一AI助手与智能问答服务.md` — 完整 ADR
