---
name: podman-rebuild
description: 在 ODAP 项目中一键重建 Podman 镜像、重新部署、验证健康状态、查看日志。修复 graphiti-core 未安装、依赖更新、代码修改后的标准流程。
compatibility: Requires Podman (NOT Docker)
metadata:
  author: odap-project
  source: AGENTS.md container-commands
---

# Podman 重建与部署

在 ODAP 项目中按规范流程**重建镜像 → 重启容器 → 验证健康**。

## ⚠️ 关键提醒

- **ODAP 使用 Podman 而非 Docker**！所有命令使用 `podman`，不要用 `docker`
- 修改代码后必须重建镜像（**生产镜像不挂载代码目录**）
- 修改前端代码后必须重新构建前端镜像
- 修改环境变量后必须重启容器

## 用户输入

```
$ARGUMENTS
```

可选参数：
- `all` — 重建所有镜像并重启所有容器
- `main` — 仅重建后端主应用
- `frontend` — 仅重建前端
- `infra` — 仅重建基础设施（Neo4j/MongoDB/Redis/OPA）
- `status` — 仅查看容器状态

## 标准化流程

### Step 1: 查看当前容器状态

```bash
# Windows PowerShell
podman ps --format "{{.Names}} {{.Status}}"

# 或使用 bootstep.py
python bootstep.py status
```

预期输出（11 个容器）：

| 容器名 | 作用 |
|--------|------|
| `graphiti-main-app` | 后端主应用（FastAPI :8000） |
| `graphiti-frontend` | 前端（Nginx :80 → :3000） |
| `graphiti-neo4j` | Neo4j 图数据库（:7474/:7687） |
| `graphiti-mongodb` | MongoDB |
| `graphiti-cache` | Redis |
| `graphiti-policy-service` | OPA 策略 |
| `graphiti-policy-bundles` | OPA bundles |
| `graphiti-elasticsearch` | ES（可选） |
| `graphiti-kibana` | Kibana（可选） |
| `graphiti-minio` | MinIO（可选） |
| `graphiti-jaeger` | Jaeger（可选） |

### Step 2: 停止并删除旧容器

```bash
# 停止主应用
podman stop graphiti-main-app
podman rm graphiti-main-app

# 停止前端
podman stop graphiti-frontend
podman rm graphiti-frontend

# 停止所有（慎用，会丢数据除非使用 volume）
python bootstep.py down
```

### Step 3: 重建镜像

#### 方式 A：使用 bootstep.py（推荐）

```bash
# 重建主应用
python bootstep.py rebuild main

# 重建前端
python bootstep.py rebuild frontend

# 重建所有
python bootstep.py rebuild all
```

#### 方式 B：手动 podman build

```bash
# 后端主应用
podman build -t graphiti-main:latest -f docker/Dockerfile .

# 前端
podman build -t graphiti-frontend:latest -f frontend/Dockerfile frontend/
```

#### 常见构建问题

| 错误 | 原因 | 修复 |
|------|------|------|
| `pip install` 超时 | playwright/openharness 等大包超时 | 已在 Dockerfile 中分组安装并使用 `|| true` 容错 |
| `graphiti-core` 安装失败 | 整体 pip 失败被掩盖 | 检查是否分组安装，单独步骤 `pip install graphiti-core==0.29.1` |
| `npm install` 慢 | node_modules 缓存未命中 | 使用 `--no-cache` 或预构建基础镜像 |
| `COPY` 路径错误 | 构建上下文不对 | 主应用用 `.`，前端用 `frontend/` |

### Step 4: 启动容器

#### 方式 A：使用 bootstep.py

```bash
# 启动所有
python bootstep.py up

# 查看启动日志
python bootstep.py logs
```

#### 方式 B：手动启动主应用

```bash
podman run -d \
  --name graphiti-main-app \
  --network graphiti-network \
  -p 8000:8000 \
  --env-file .env.docker \
  -e IN_DOCKER=true \
  -e NEO4J_URI=bolt://graphiti-neo4j:7687 \
  -e NEO4J_USER=neo4j \
  -e NEO4J_PASSWORD=neo4j123456 \
  -e OPA_URL=http://graphiti-policy-service:8181 \
  -e REDIS_URL=redis://graphiti-cache:6379 \
  -e MONGODB_URI=mongodb://graphiti-mongodb:27017 \
  -e CORS_ORIGINS=http://localhost,http://localhost:80,http://localhost:5173,http://localhost:8000 \
  -v app-data:/app/data \
  localhost/graphiti-main:latest
```

#### 启动前端

```bash
podman run -d \
  --name graphiti-frontend \
  --network graphiti-network \
  -p 3000:80 \
  localhost/graphiti-frontend:latest
```

### Step 5: 验证健康

等待 25-30 秒后（uvicorn 启动 + Graphiti 初始化）：

```bash
# 健康检查
curl http://localhost:8000/health
```

**期望响应**：
```json
{
  "status": "ok",
  "graphiti": {
    "graphiti_core_installed": true,
    "graph_mode": "graphiti",
    "connected": true,
    "use_fallback": false
  },
  "openharness_v2": {
    "llm_client_initialized": true
  }
}
```

**PowerShell 方式**：
```powershell
Invoke-RestMethod -Uri http://localhost:8000/health | ConvertTo-Json
```

### Step 6: 查看日志诊断

```bash
# 实时日志
podman logs -f graphiti-main-app

# 最近 30 行
podman logs --tail 30 graphiti-main-app

# 带时间戳
podman logs -t graphiti-main-app | tail -50
```

#### 常见日志错误诊断

| 日志错误 | 原因 | 修复 |
|---------|------|------|
| `No module named 'graphiti_core'` | 镜像未包含 graphiti-core | 重建镜像，检查 Dockerfile 分组安装 |
| `Connection refused to neo4j:7687` | Neo4j 未启动或 DNS 不通 | 等待 Neo4j 就绪（首次启动 60-90s），或重启主应用 |
| `OpenHarness LLM client not initialized` | LLM 配置缺失 | 检查 `.env.docker` 中 `OPENAI_API_KEY` / `OPENAI_API_BASE` / `OPENAI_MODEL` |
| `asyncio.run() cannot be called from a running event loop` | FastAPI 异步路由冲突 | 确认 `graph_service.py` 使用 `_run_async()` 而非 `asyncio.run()` |
| `npm: command not found` | 前端构建阶段缺 Node | 检查 `frontend/Dockerfile` Node 版本 |
| `port 8000 already in use` | 旧容器未删除 | `podman rm -f graphiti-main-app` |

## 完整重建脚本

```bash
# 1. 停止并删除
podman stop graphiti-main-app graphiti-frontend 2>$null
podman rm graphiti-main-app graphiti-frontend 2>$null

# 2. 重建后端
podman build -t graphiti-main:latest -f docker/Dockerfile .

# 3. 重建前端（修改前端代码时）
podman build -t graphiti-frontend:latest -f frontend/Dockerfile frontend/

# 4. 启动后端
podman run -d --name graphiti-main-app \
  --network graphiti-network -p 8000:8000 \
  --env-file .env.docker \
  -e IN_DOCKER=true \
  -e NEO4J_URI=bolt://graphiti-neo4j:7687 \
  -e NEO4J_USER=neo4j -e NEO4J_PASSWORD=neo4j123456 \
  -e OPA_URL=http://graphiti-policy-service:8181 \
  -e REDIS_URL=redis://graphiti-cache:6379 \
  -e MONGODB_URI=mongodb://graphiti-mongodb:27017 \
  -e CORS_ORIGINS=http://localhost,http://localhost:80,http://localhost:5173,http://localhost:8000 \
  -v app-data:/app/data \
  localhost/graphiti-main:latest

# 5. 启动前端（如果重建了）
podman run -d --name graphiti-frontend \
  --network graphiti-network -p 3000:80 \
  localhost/graphiti-frontend:latest

# 6. 等待启动
Start-Sleep -Seconds 30

# 7. 健康检查
curl http://localhost:8000/health
```

## 端到端测试

重建后建议运行完整 E2E 测试：

```powershell
# 1. 列出智能体
$agents = Invoke-RestMethod http://localhost:8000/api/agents
Write-Host "智能体数: $($agents.Count)"

# 2. 创建一个测试智能体
$body = @{
  display_name = "测试智能体"
  name = "test-agent"
  description = "重建后测试"
  main_object = "测试领域"
} | ConvertTo-Json
$agent = Invoke-RestMethod -Uri http://localhost:8000/api/agents -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
Write-Host "创建智能体: $($agent.agent_id)"

# 3. 通过该智能体问答
$qaBody = @{
  question = "波斯湾"
  user_id = "test"
  agent_id = $agent.agent_id
} | ConvertTo-Json
$resp = Invoke-RestMethod -Uri http://localhost:8000/api/qa/ask -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($qaBody))
Write-Host "回答: $($resp.answer.Substring(0, [Math]::Min(100, $resp.answer.Length)))..."
Write-Host "来源数: $($resp.sources.Count)"
```

## 数据持久化

| 卷 | 内容 | 是否持久 |
|----|------|---------|
| `app-data` | 后端 SQLite / 缓存 | ✅ 持久 |
| `neo4j-data` | Neo4j 图数据 | ✅ 持久 |
| `mongodb-data` | MongoDB | ✅ 持久 |
| `redis-data` | Redis 缓存 | ✅ 持久 |
| `opa-data` | OPA 策略 | ✅ 持久 |

重建镜像和容器**不会**丢失数据，因为数据存储在命名卷中。

如需完全清空（慎用）：
```bash
python bootstep.py clean
```

## 输出

向用户报告：
- 重建的镜像列表
- 启动的容器列表
- 健康检查响应（关键字段）
- E2E 测试结果
- 任何警告/错误
- 下一步建议
