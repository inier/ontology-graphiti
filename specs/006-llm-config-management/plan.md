# Implementation Plan: LLM 与 API 密钥配置管理

**Branch**: `006-llm-config-management` | **Date**: 2026-06-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-llm-config-management/spec.md`

## Summary

将项目中分散在 15+ 个文件中的 LLM API Key/模型配置和外部服务连接参数，统一为通过配置管理界面管理。后端扩展现有 `ConfigurationComposer` 5 层配置体系，新增 SQLite 持久化存储、配置热更新、加密存储和变更审计；前端新增系统设置页面（`/settings`），支持配置分组展示、连接测试、变更历史和回滚。配置保存后立即生效，无需重启。

## Technical Context

**Language/Version**: Python 3.10+ (后端) / TypeScript (前端)

**Primary Dependencies**: FastAPI + Pydantic v2 (后端) / React 19 + Ant Design 6 + Zustand 5 (前端)

**Storage**: SQLite（配置持久化）+ 内存缓存（热更新）

**Testing**: pytest (后端) / Vitest (前端)

**Target Platform**: Podman 容器化部署 (Linux)

**Project Type**: Web 应用 (前后端分离)

**Performance Goals**: 配置保存后 5 秒内生效；连接测试 10 秒内返回

**Constraints**: 仅 admin 角色可访问；敏感配置加密存储；不引入新外部依赖

**Scale/Scope**: 8 个服务类别、30+ 配置项、单管理员操作

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 合规 | 说明 |
|------|------|------|
| I. 简单 | PASS | 配置管理本质是 CRUD + 热更新，不过度抽象。复用现有 ConfigurationComposer |
| II. 可维护 | PASS | 后端按 biz 模块 6 层结构组织；前端按 modules 结构组织；配置集中管理消除分散读取 |
| III. 测试优先 | PASS | 每层配套测试：storage CRUD、service 逻辑、routes HTTP、前端组件 |
| IV. 避免过度设计 | PASS | 不引入配置中心（Nacos/Apollo），SQLite + 内存缓存足够；不预设多租户配置隔离 |
| 安全边界 | PASS | admin-only 访问；敏感字段加密存储+脱敏展示；审计日志记录所有变更 |

## Project Structure

### Documentation (this feature)

```text
specs/006-llm-config-management/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── config-api.md    # 配置管理 API 合约
└── checklists/
    └── requirements.md  # 规格质量检查
```

### Source Code (repository root)

```text
odap/
├── biz/platform/config/               # 新增：配置管理业务模块
│   ├── api/
│   │   ├── routes.py                  # 配置管理路由 (/api/config)
│   │   └── schemas.py                 # 请求/响应 Pydantic 模型
│   ├── models/
│   │   └── config_models.py           # ServiceConfig, ConfigItem, ConfigRevision
│   ├── interfaces/
│   │   └── config_repository.py       # 配置存储抽象接口
│   ├── impl/
│   │   ├── config_manager.py          # 配置管理核心逻辑（热更新、验证、加密）
│   │   └── config_validator.py        # 外部服务连接验证器
│   ├── services/
│   │   └── config_service.py          # 编排层
│   └── storage/
│       ├── __init__.py                # Storage = SQLiteConfigStorage
│       └── sqlite_config_storage.py   # SQLite 持久化
├── infra/
│   ├── config_composer.py             # 扩展：新增 L5(DB) 层 + 热更新通知
│   └── security/
│       └── config_encryption.py       # 新增：敏感配置加密/解密工具
└── web/
    └── app.py                         # 注册 config_router

frontend/
└── src/modules/settings/              # 新增：系统设置模块
    ├── pages/
    │   └── SettingsPage.tsx           # 配置管理主页面
    ├── components/
    │   ├── ConfigGroup.tsx            # 配置分组卡片
    │   ├── ConfigItemForm.tsx         # 单个配置项表单
    │   ├── ConnectionTestButton.tsx   # 连接测试按钮
    │   ├── ConfigHistoryDrawer.tsx    # 变更历史抽屉
    │   └── ConfigImportExport.tsx     # 导入导出
    ├── services/
    │   └── configApi.ts              # 配置管理 API 客户端
    ├── stores/
    │   └── configStore.ts            # Zustand 状态管理
    ├── types/
    │   └── index.ts                  # 类型定义
    └── index.ts                      # 模块导出

tests/
├── unit/
│   ├── test_config_storage.py         # SQLiteConfigStorage 测试
│   ├── test_config_manager.py         # ConfigManager 测试
│   ├── test_config_service.py         # ConfigService 测试
│   ├── test_config_encryption.py      # 加密/解密测试
│   └── test_config_validator.py       # 连接验证测试
└── integration/
    └── test_config_api.py             # API 端点集成测试
```

**Structure Decision**: 遵循项目现有 Web 应用结构（后端 odap/biz/ 6 层 + 前端 frontend/src/modules/），配置管理作为 platform 领域下的新模块。

## Complexity Tracking

无宪法违规需要记录。
