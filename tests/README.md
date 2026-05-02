# Graphiti 测试文件管理

## 📂 目录结构

```
tests/
├── README.md                # 本文档
├── __init__.py           # 测试包初始化
├── conftest.py            # pytest 配置
├── data/                 # 测试数据库文件
├── integration/          # 集成测试
└── unit/             # 单元测试
├── test_*.py            # 独立测试脚本
```

---

## 📝 测试文件说明

### 1. 审计相关测试

| 文件名 | 说明 | 运行命令 |
|--------|------|
| `test_audit.py` | 审计日志基础测试 |
| `test_audit_simple.py` | 简单版审计日志测试 |
| `test_audit_new.py` | 新版审计日志测试 |
| `test_audit_refactored.py` | 重构版审计日志测试 |
| `test_audit_isolated.py` | 隔离模式审计日志测试 |

### 2. 工作空间相关测试

| 文件名 | 说明 |
|--------|------|
| `test_workspace.py` | 工作空间服务测试 |
| `test_scenario.py` | 场景功能测试 |
| `test_scenario_create.py` | 场景创建测试 |

### 3. 本体/数据摄入相关测试

| 文件名 | 说明 |
|--------|------|
| `test_ingest.py` | 数据摄入服务测试 |
| `test_graph_service.py` | 图服务测试 |
| `test_graph_manager.py` | 图管理测试 |

### 4. 技能/OpenHarness相关测试

| 文件名 | 说明 |
|--------|------|
| `test_openharness.py` | OpenHarness 集成测试 |
| `test_skills.py` | 技能注册测试 |
| `test_opa_service.py` | OPA 服务测试 |
| `test_tool_registry.py` | 工具注册测试 |
| `test_tools.py` | 工具测试 |
| `test_utils.py` | 工具函数测试 |

### 5. API 流程测试

| 文件名 | 说明 |
|--------|------|
| `test_api_flow.py` | 完整 API 端点流程测试 |

### 6. 集成测试

| 文件名 | 说明 |
|--------|------|
| `test_integration.py` | 集成测试（v1） |
| `test_integration_v2.py` | 集成测试（v2） |

---

## 💾 测试数据库

测试数据库文件位于 `data/` 目录，用于测试存储功能：

```
data/
├── test_audit.db              # 审计数据库
├── test_audit_isolated.db      # 隔离审计数据库
├── test_refactored.db         # 重构版数据库
└── test_sqlite.db            # SQLite 测试数据库
```

---

## 🚀 运行测试

### 运行单个测试
```bash
# 运行单独的测试脚本
python tests/test_openharness.py
python tests/test_ingest.py
```

### 使用 pytest（如果已配置）
```bash
pip install pytest
pytest tests/
```

---

## 📋 新增测试文件规范

### 创建新测试文件

- **文件命名**
  - 使用 `test_` 前缀
  - 文件名清晰表达测试功能
  - 描述性命名，如 `test_<模块名_<功能>.py

- **位置选择**
  - 简单、快速、非依赖测试 → tests/ 根目录
  - 复杂、依赖单元测试 → tests/unit/
  - 全流程集成测试 → tests/integration/

---

## ⚠️ 注意事项

1. **测试数据库**：所有测试数据库位于 `tests/data/`，请勿提交到 Git，已在 `.gitignore` 中忽略
2. **测试数据**：确保测试使用临时数据，清理临时文件
3. **独立运行**：确保测试可以独立运行，不依赖外部服务
4. **清理**：测试完成后清理临时创建的资源

---

## 📝 更新日志

### 2026-04-29
- ✅ 整理根目录 test_* 开头文件到 tests/
- ✅ 移动测试数据库到 tests/data/
- ✅ 建立测试文件管理文档
