# Quickstart: LLM 与 API 密钥配置管理

**Branch**: `006-llm-config-management` | **Date**: 2026-06-14

## 前置条件

- ODAP 平台已通过 `python bootstep.py dev` 启动
- 拥有 admin 角色的用户账号

## 快速开始

### 1. 访问配置管理页面

浏览器打开 http://localhost:5173/settings

使用 admin 账号登录后，左侧导航栏出现"系统设置"入口。

### 2. 配置 LLM 服务

1. 在"LLM 大模型服务"分组中展开配置项
2. 填写：
   - API Key: 你的 OpenAI 兼容 API Key
   - API 基地址: 如 `https://api.openai.com/v1`
   - 模型名称: 如 `gpt-4o`
3. 点击"测试连接"验证配置
4. 测试通过后点击"保存"

### 3. 验证配置生效

发起一次问答请求，确认使用的是新配置的模型。

### 4. 查看变更历史

点击页面右上角"变更历史"按钮，查看所有配置变更记录。

### 5. 回滚配置

在变更历史中选择需要回滚的版本，点击"回滚"。

## API 使用示例

```bash
# 获取所有配置（脱敏）
curl -H "Authorization: Bearer <admin_token>" \
  http://localhost:8000/api/config

# 更新 LLM 配置
curl -X PUT http://localhost:8000/api/config \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"key": "llm.api_key", "value": "sk-new-key"},
      {"key": "llm.model", "value": "gpt-4o"}
    ],
    "test_connection": true
  }'

# 测试连接
curl -X POST http://localhost:8000/api/config/test \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"categories": ["llm"]}'

# 导出配置
curl -H "Authorization: Bearer <admin_token>" \
  http://localhost:8000/api/config/export
```

## 后端集成（供开发者参考）

其他模块需要读取配置时，使用 `ConfigurationComposer` 统一入口：

```python
from odap.infra.config_composer import get_config

# 读取 LLM API Key（自动解密）
api_key = get_config("llm.api_key")

# 读取模型名称
model = get_config("llm.model")

# 读取 Neo4j URI
neo4j_uri = get_config("graph_db.uri")
```

不再使用 `os.getenv("OPENAI_API_KEY")` 直接读取。

## 环境变量兼容

配置管理界面保存的值优先于环境变量。优先级从高到低：

1. **DB 层**（管理员通过界面保存）
2. **环境变量**（.env.docker 或系统环境变量）
3. **系统默认值**（代码中的默认配置）

如果界面未配置某项，系统自动降级到环境变量读取。
