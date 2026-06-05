# Quickstart: ODAP 本体驱动分析决策平台

**Branch**: `001-odap-platform` | **Date**: 2026-06-02 | **Plan**: [plan.md](./plan.md)

## 前置条件

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 后端运行时 |
| Node.js | 18+ | 前端构建 |
| Podman | 4.x+ | 容器运行时（替代 Docker） |
| Git | 2.x+ | 含子模块支持 |

## 1. 克隆与初始化

```bash
git clone --recursive <repo-url>
cd ontology-graphiti

git submodule update --init --recursive
```

## 2. 环境变量配置

```bash
cp .env.example .env.docker
```

必填项：

```env
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
NEO4J_URI=bolt://graphiti-neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
JWT_SECRET=your_jwt_secret_min_32_chars
```

可选项：

```env
TAVILY_API_KEY=tvly-xxx
OPA_URL=http://graphiti-opa:8181
REDIS_URL=redis://graphiti-redis:6379/0
CORS_ORIGINS=http://localhost:5173
MINIO_ENDPOINT=graphiti-minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

## 3. 容器化启动（推荐）

```bash
python bootstep.py dev
```

访问地址：
- 前端：http://localhost:5173
- 后端：http://localhost:8000
- Neo4j Browser：http://localhost:7474
- MinIO Console：http://localhost:9001

## 4. 本地开发（仅快速调试）

> ⚠️ 不推荐，仅用于快速调试。正式开发必须使用容器。

```bash
pip install -r requirements.txt
python main.py --web
```

```bash
cd frontend
npm install
npm run dev
```

## 5. 验证

```bash
curl http://localhost:8000/health
```

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

## 6. 常用命令

| 命令 | 作用 |
|------|------|
| `python bootstep.py dev` | 启动开发环境 |
| `python bootstep.py restart` | 重启服务（代码修改后） |
| `python bootstep.py rebuild` | 重建镜像（依赖变更后） |
| `python bootstep.py down` | 停止所有服务 |
| `python bootstep.py status` | 查看服务状态 |
| `python bootstep.py logs` | 查看后端日志 |
| `python bootstep.py logs fe` | 查看前端日志 |

## 7. 测试

```bash
pytest tests/unit/ -v
pytest tests/integration/ -v -m integration
pytest tests/e2e/ -v -m e2e
```

```bash
cd frontend
npm run lint
npm run typecheck
npm test
```

## 8. 数据模型参考

详见 [data-model.md](./data-model.md)

## 9. API 契约参考

详见 [contracts/](./contracts/) 目录

## 10. Phase 4 新增功能快速验证 (2026-06-05)

> Phase 4 包含 7 个新 FR（FR-031..FR-037），需在 Phase 1/2/3 完成后才能使用。

### 10.1 FR-031 Data Health

```bash
# 创建健康规则
curl -X POST http://localhost:8000/api/ontology/health/rules \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d @health-rule-sample.yaml

# 触发扫描
curl -X POST http://localhost:8000/api/ontology/health/scan \
  -H "Authorization: Bearer <token>" \
  -d '{"rule_id": "uuid", "scan_type": "incremental"}'

# 查看健康报告
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/ontology/health/reports?rule_id=uuid
```

### 10.2 FR-032 Branch & Merge

```bash
# 创建分支
curl -X POST http://localhost:8000/api/ontology/branches \
  -H "Authorization: Bearer <token>" \
  -d '{"ontology_id": "uuid", "name": "feature/team-x", "base_version_id": "v1.0.0"}'

# 创建 MR
curl -X POST http://localhost:8000/api/ontology/merge-requests \
  -H "Authorization: Bearer <token>" \
  -d '{"source_branch_id": "uuid", "target_branch_id": "uuid", "title": "Add Vehicle type"}'
```

### 10.3 FR-033 Object Type 继承

```bash
# 创建 Truck 继承 Vehicle
curl -X POST http://localhost:8000/api/ontology/model/entity-types \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "Truck",
    "inherits": ["vehicle-id"],
    "mixins": ["auditable-mixin-id"],
    "properties": [{"name": "payload_kg", "data_type": "number"}]
  }'

# 查看 effective properties (含继承)
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/ontology/model/entity-types/truck-id/effective-properties
```

### 10.4 FR-034 Action Type

```bash
# Agent 调用 Action
curl -X POST http://localhost:8000/api/ontology/action-types/assign-equipment/execute \
  -H "Authorization: Bearer <token>" \
  -d '{"equipment_id": "uuid", "mission_id": "uuid"}'
```

### 10.5 FR-035 计算属性

```bash
# 创建物化视图
curl -X POST http://localhost:8000/api/ontology/materialization/views \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "equipment_risk_score",
    "target_entity_type_id": "equipment-id",
    "computed_property": "risk_score",
    "depends_on_paths": ["status", "maintenance_history"],
    "refresh_strategy": "incremental",
    "schedule": "0 * * * *"
  }'
```

### 10.6 FR-036 OntoFlow Goal

```bash
# 创建 Goal
curl -X POST http://localhost:8000/api/ontology/goals \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "Q3 装备调度优化",
    "rationale": "通过本体建模改进装备调度效率",
    "priority": "high",
    "linked_requirements": ["REQ-2024-001"]
  }'

# 提交本体变更（MUST 关联 goal）
curl -X POST http://localhost:8000/api/ontology/changes \
  -H "Authorization: Bearer <token>" \
  -d '{
    "goal_id": "goal-uuid",
    "rationale": "新增 Vehicle 类型支持卡车调度",
    "changes": [...]
  }'
```

### 10.7 FR-037 Object View

```bash
# 创建 Commander View
curl -X POST http://localhost:8000/api/ontology/views \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "commander-view",
    "target_entity_type_id": "equipment-id",
    "included_properties": ["name", "status", "current_mission", "risk_score"],
    "role_binding": ["commander-role-id"],
    "redaction_rules": [
      {"field_path": "current_mission.location", "redaction_type": "partial", "params": {"precision": 1}}
    ]
  }'

# 解析视图
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/ontology/views/commander-view/resolve?entity_id=eq-uuid&user_id=user-uuid"
```
