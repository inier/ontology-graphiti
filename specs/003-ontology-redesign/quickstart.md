# Quickstart: 本体设计器彻底重构

**Branch**: `003-ontology-redesign` | **Date**: 2026-06-09

## 前置条件

- ODAP 开发环境已启动（`python bootstep.py dev`）
- 后端健康检查通过（`curl http://localhost:8000/health`）
- 已获取 JWT Token

## 快速验证流程

### 1. 创建本体

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.access_token')

# 创建本体
curl -X POST http://localhost:8000/api/ontologies \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"电商本体","description":"电商领域本体","workspace_id":"ws-001"}'
```

### 2. 手工定义对象类型

```bash
# 创建对象类型
curl -X POST http://localhost:8000/api/ontologies/{ontology_id}/object-types \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "User",
    "display_name": "用户",
    "properties": [
      {"name": "username", "property_type": "STRING", "required": true},
      {"name": "email", "property_type": "STRING", "required": true}
    ]
  }'
```

### 3. 查看图谱

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/ontologies/{ontology_id}/graph
```

### 4. 数据库抽取

```bash
# 测试连接
curl -X POST http://localhost:8000/api/ontologies/{ontology_id}/extract/database/test-connection \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"db_type":"sqlite","database":"/path/to/test.db"}'

# 发起抽取
curl -X POST http://localhost:8000/api/ontologies/{ontology_id}/extract/database \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"db_type":"sqlite","database":"/path/to/test.db"}'
```

### 5. 自然语言提取

```bash
curl -X POST http://localhost:8000/api/ontologies/{ontology_id}/extract/natural-language \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"电商系统需要管理用户、商品和订单","auto_search":true}'
```

### 6. 前端验证

1. 访问 http://localhost:5173/ontology/designer
2. 在本体选择器中选择刚创建的本体
3. 在"对象类型"区域点击"新增"，填写属性
4. 切换到"图谱"Tab 查看可视化
5. 访问 http://localhost:5173/business/process 验证结构定义同步可见

## 新增依赖

```bash
# 后端
pip install sqlalchemy>=2.0.0 psycopg2-binary>=2.9.0 pymysql>=1.1.0

# 前端（无新增依赖，复用 Ant Design 6 + Zustand 5 + AntV G6 5）
```
