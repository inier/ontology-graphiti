<!--
  Sync Impact Report
  ==================
  Version change: 1.0.0 → 2.0.0
  Modified principles:
    - I. 代码质量 → removed (absorbed into 简单 + 可维护)
    - II. 测试标准 → III. 测试优先 (renamed, refocused on test-first philosophy)
    - III. 用户体验一致性 → removed as top-level principle
    - IV. 性能要求 → removed as top-level principle
    - V. 可维护性 → II. 可维护 (renamed, expanded)
    - VI. 安全边界 → moved to Security Boundaries section
    - NEW: I. 简单
    - NEW: IV. 避免过度设计
  Added sections:
    - Principle I. 简单
    - Principle IV. 避免过度设计
  Removed sections:
    - Principle 代码质量 (absorbed)
    - Principle 用户体验一致性 (removed)
    - Principle 性能要求 (removed)
    - Principle 安全边界 as top-level (moved to Security Boundaries section)
  Templates requiring updates:
    - .specify/templates/plan-template.md: ✅ compatible (Constitution Check section is dynamic)
    - .specify/templates/spec-template.md: ✅ compatible (requirements structure aligns)
    - .specify/templates/tasks-template.md: ✅ compatible (task phases align)
  Follow-up TODOs: None
-->

# ODAP Constitution

## Core Principles

### I. 简单

代码 MUST 保持简单直接。能用 10 行解决的，MUST NOT 写 50 行。能用一个函数解决的，MUST NOT 拆成三个类。

- 每个函数 MUST 只做一件事；函数体超过 40 行时 MUST 拆分
- 命名 MUST 语义明确，禁止需要注释才能理解的缩写或命名
- 代码重复出现 3 次及以上的模式 MUST 抽取为共享函数或模块
- 公共 API MUST 有完整的类型签名；`any` 类型 MUST 有注释说明原因
- 优先使用语言内置能力和项目已有依赖，MUST NOT 引入新依赖仅为了省一行代码

**理由**：简单代码易读、易审、易改。复杂度是技术债的根源，每多一层抽象就多一层理解成本。

### II. 可维护

代码架构 MUST 支持单人独立修改任意模块而不必理解全部代码。改一处不该坏另一处。

- 前端 API 调用 MUST 通过统一 API 客户端（apiClient），禁止组件内内联 fetch
- 后端路由 MUST 按领域模块注册（独立 routes.py），禁止在 app.py 直接定义路由
- 共享状态 MUST 通过 Context/Hook 或状态管理统一提供，prop 透传 MUST NOT 超过 2 层
- 配置项 MUST 集中管理（前端 config.ts / 后端环境变量），MUST NOT 在业务代码硬编码
- 模块间依赖 MUST 单向：基础设施层 ← 业务层 ← API 层，MUST NOT 反向依赖
- 错误处理 MUST 统一：前端通过 API 客户端统一处理认证和 HTTP 错误；后端通过统一异常处理器返回结构化错误

**理由**：可维护性决定项目的长期生存能力。模块边界清晰才能独立重构，否则牵一发而动全身。

### III. 测试优先

测试 MUST 先于实现编写。没有测试的代码等同于未验证的假设。

- Bug 修复 MUST 先写复现测试，确认失败后再修复
- 新增 API 端点 MUST 配套集成测试，验证状态码和响应结构
- 核心业务逻辑（实体消歧、版本管理、权限校验）MUST 有单元测试
- 测试 MUST 可独立运行，外部依赖 MUST 通过 mock 隔离
- 测试文件 MUST 与源码目录结构对应：`tests/unit/`、`tests/integration/`、`tests/e2e/`
- 代码提交前 MUST 通过 lint（零警告）+ 类型检查（零错误）+ 相关测试（全绿）

**理由**：先写测试迫使你思考接口和边界，而非实现细节。测试是重构和迭代的信心基础。

### IV. 避免过度设计

MUST NOT 为假设的未来需求预先编码。当前不需要的抽象层、配置项、扩展点，MUST NOT 创建。

- MUST NOT 创建只有一个实现的接口或抽象类
- MUST NOT 预先添加配置项或功能开关，除非当前需求明确要求
- MUST NOT 引入设计模式除非它能解决当前已存在的问题
- 重构时 MUST 优先选择最小改动方案，而非最优雅方案
- 复杂性 MUST 被证明必要——如果简单方案可行，MUST NOT 选择复杂方案
- 代码审查 MUST 挑战不必要的抽象：每多一层间接层，MUST 有明确的当前收益

**理由**：过度设计的代码比欠设计的代码更难改。每一行"以防万一"的代码都是未来必须维护和理解的债务。

## Security Boundaries

安全作为非协商性约束，任何功能实现 MUST NOT 绕过安全检查。

- 所有 API 端点 MUST 通过认证中间件校验；公开端点 MUST 显式标注 `skipAuth`
- Token 过期 MUST 自动清除本地存储并跳转登录页，MUST NOT 静默失败
- 用户输入 MUST 在服务端校验（Pydantic schema / FastAPI dependency），前端校验仅作体验优化
- 敏感操作 MUST 经过 OPA 策略校验
- 日志 MUST NOT 记录 Token、密码等敏感信息；生产环境错误响应 MUST NOT 暴露内部堆栈
- 工作空间隔离 MUST 严格执行：standard 级别以上 MUST 校验资源归属
- 认证层：JWT + Refresh Token 双令牌，Access Token 有效期 ≤ 30 分钟
- 授权层：OPA fail-close 模式，策略加载失败时拒绝所有请求
- 审计层：所有写操作 MUST 记录审计日志

## Quality Gates

- **提交前**：lint 零警告 + 类型检查零错误 + 相关测试全绿
- **代码审查**：MUST 验证宪法合规——简单性、可维护性、测试覆盖、无过度设计
- **重构验收**：MUST 运行 `tsc --noEmit` + `vite build`（前端）或 `pytest`（后端）确认零回归

## Governance

本宪法是项目最高开发准则，所有规格说明、实施计划和任务定义 MUST 遵守上述原则。

- 宪法修订 MUST 记录变更内容、版本号和修订日期
- 版本号遵循语义化版本：MAJOR（原则删除/重定义）、MINOR（新增原则/章节）、PATCH（措辞修正）
- 代码审查 MUST 验证宪法合规性，违规代码 MUST 在合并前修正
- 运行时开发指导参见 `.specify/memory/` 目录下的相关文档

**Version**: 2.0.0 | **Ratified**: 2025-06-13 | **Last Amended**: 2025-06-13
