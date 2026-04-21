# Graphiti - 本体驱动分析决策平台

**Graphiti** 是一个通用的本体驱动分析决策平台（Ontology-Driven Analysis & Decision Platform, ODAP），旨在通过工作空间机制实现多场景隔离，支持任意领域的本体建模和分析决策。

## 核心功能

- **本体管理**：领域本体设计、新增、更新维护
- **Skill 管理**：技能注册、配置、热插拔
- **多智能体调度**：意图识别、Agent 协同、OODA 闭环
- **问答链路**：自然语言问答、图表展示、过程解释
- **权限管控**：细粒度权限、OPA 策略、角色绑定
- **可视化配置**：本体、技能、策略、规则统一管理
- **事件模拟**：随机事件、自动/手动输入
- **工作空间**：场景隔离、导入导出、切换

## 技术栈

- **后端**：Python 3.11+, FastAPI, Neo4j/NetworkX, OpenAI API
- **前端**：React, Ant Design, G6, Leaflet
- **基础设施**：OpenHarness, Graphiti, OPA, MCP

## 项目结构

```
graphiti/
├── app/                # 主应用入口
├── assets/             # 静态资源
├── docker/             # Docker配置
├── docs/               # 文档
├── frontend/           # 前端项目
│   ├── src/            # 前端源码
│   └── public/         # 前端静态资源
├── odap/               # 核心业务逻辑
│   ├── biz/            # 业务模块
│   │   ├── agent/              # Agent 协同模块
│   │   ├── audit_logging/      # 审计日志模块
│   │   ├── event_simulator/    # 事件模拟模块
│   │   ├── frontend_compat/    # 前端兼容层
│   │   ├── hook_system/        # Hook 系统模块
│   │   ├── mcp_adapter/        # MCP 适配器模块
│   │   ├── ontology/           # 本体管理模块
│   │   ├── skill_system/       # 技能系统模块
│   │   └── workspace/          # 工作空间管理模块
│   ├── infra/          # 基础设施
│   │   ├── config/             # 配置管理
│   │   ├── events/             # 事件系统
│   │   ├── graph/              # 图谱服务
│   │   ├── llm/                # LLM 服务
│   │   ├── monitoring/         # 性能监控
│   │   ├── opa/                # OPA 策略
│   │   ├── resilience/         # 韧性系统
│   │   └── security/           # 安全配置
│   ├── storage/        # 存储目录
│   ├── tools/          # 领域工具
│   └── web/            # Web 服务
├── src/                # 入口脚本
├── tests/              # 测试目录
├── .env                # 环境变量
├── .env.example        # 环境变量模板
├── .gitignore          # Git 忽略文件
├── main.py             # 主入口
├── requirements.txt    # 依赖管理
└── start.sh            # 启动脚本
```

## 快速开始

### 环境准备

1. **Python 环境**：Python 3.11+  
2. **Neo4j**：（可选）用于生产环境  
3. **API 密钥**：OpenAI API 密钥（用于 LLM 功能）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

复制 `.env.example` 文件为 `.env`，并填写相关配置：

```bash
cp .env.example .env
# 编辑 .env 文件，填写 OPENAI_API_KEY 等配置
```

### 启动服务

```bash
# 启动 Web 服务
python main.py

# 或使用启动脚本
./start.sh
```

### 访问 API

- **API 文档**：http://localhost:8001/docs
- **健康检查**：http://localhost:8001/health
- **性能监控**：http://localhost:8001/api/v1/monitoring/performance

## 核心模块

### 1. 本体管理（Ontology）

- **功能**：领域本体设计、新增、更新维护
- **API**：`/api/ontology-management`
- **模块路径**：`odap/biz/ontology/`

### 2. 工作空间管理（Workspace）

- **功能**：场景隔离、导入导出、切换
- **API**：`/api/workspace`
- **模块路径**：`odap/biz/workspace/`

### 3. Agent 协同（Agent）

- **功能**：意图识别、Agent 协同、OODA 闭环
- **API**：`/api/agent`
- **模块路径**：`odap/biz/agent/`

### 4. 技能系统（Skill）

- **功能**：技能注册、配置、热插拔
- **API**：`/api/skill`
- **模块路径**：`odap/tools/`

### 5. 审计日志（Audit）

- **功能**：操作审计、日志记录
- **API**：`/api/audit`
- **模块路径**：`odap/biz/audit_logging/`

## 安全配置

- **API 密钥管理**：通过 `.env` 文件配置，避免硬编码
- **权限控制**：基于 OPA 策略的细粒度权限控制
- **CORS 配置**：通过环境变量配置允许的来源
- **JWT 认证**：支持基于 JWT 的 API 认证

## 性能监控

- **API 端点**：`/api/v1/monitoring/performance`
- **监控指标**：LLM 调用、数据库操作、API 请求、工具执行
- **统计信息**：平均值、中位数、最小值、最大值、P95、P99

## 测试

运行所有测试：

```bash
python -m pytest tests/ -v
```

## CI/CD

项目配置了 GitHub Actions CI/CD 流程，包括：
- **测试**：运行所有单元测试和集成测试
- **代码质量**：使用 flake8、black 和 isort 检查代码质量
- **覆盖率**：上传测试覆盖率报告到 Codecov

## 贡献

1. **Fork 仓库**
2. **创建分支**：`git checkout -b feature/your-feature`
3. **提交更改**：`git commit -m "Add your feature"`
4. **推送分支**：`git push origin feature/your-feature`
5. **创建 PR**

## 许可证

