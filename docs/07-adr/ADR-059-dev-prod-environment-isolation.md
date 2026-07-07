# ADR-059: Dev/Prod 开发生产环境隔离架构

## 状态
已采纳（2026-07-03）

## 上下文

ODAP 使用 Podman 容器化部署（Podman 5.6.0 on WSL2），日常开发需要频繁修改前后端代码。原有方案使用 `docker-compose.yml` + `docker-compose.override.yml` 的覆盖模式，存在以下问题：

1. **环境混淆**：`bootstep.py dev` 和 `bootstep.py up` 共用基础 compose 文件，通过 override 切换，行为不一致且难以调试
2. **容器冲突**：dev 和 prod 前端使用不同端口（5173 vs 8080），但容器名可能冲突（graphiti-frontend vs graphiti-frontend-dev）
3. **误操作频繁**：开发者经常误执行 `bootstep.py up`（生产模式），导致不必要的镜像重建（3-5 min）
4. **挂载策略差异不清晰**：dev 需要 bind mount 源码实现热重载，prod 使用命名卷保证稳定性，两种策略混在 override 中难以维护
5. **停止不彻底**：切换环境时旧容器未完全清理，导致端口占用或数据不一致

## 决策

采用完全隔离的双 compose 文件方案：

### 1. 文件分离

| 文件 | 用途 | 前端策略 | 后端策略 |
|------|------|----------|----------|
| `docker-compose.yml` | 生产模式 | nginx 静态服务 (8080) | uvicorn --workers 4 |
| `docker-compose.dev.yml` | 开发模式 | Vite dev server (5173) | uvicorn --reload |
| `docker-compose.override.yml` | 旧版回退（已弃用） | — | — |

两个 compose 文件完全独立，各自定义所有服务（app, frontend, neo4j, redis, opa, minio），不互相依赖。

### 2. 互斥启动

`bootstep.py` 实现 `stop_opposing_env(mode)` 函数：
- `bootstep.py dev` → 先停止 prod 容器（graphiti-frontend）
- `bootstep.py up` → 先停止 dev 容器（graphiti-frontend-dev）
- `bootstep.py down` → 同时停止两个环境的所有容器

### 3. 容器命名隔离

| 服务 | 生产容器名 | 开发容器名 |
|------|-----------|-----------|
| 后端 | graphiti-main-app | graphiti-main-app（共用） |
| 前端 | graphiti-frontend | graphiti-frontend-dev |
| Neo4j | graphiti-neo4j | graphiti-neo4j（共用） |
| Redis | graphiti-cache | graphiti-cache（共用） |
| OPA | graphiti-policy-service | graphiti-policy-service（共用） |
| MinIO | graphiti-minio | graphiti-minio（共用） |

后端和基础设施容器共用（代码通过 bind mount 更新），仅前端容器独立（渲染策略完全不同）。

### 4. 新增命令

| 命令 | 说明 | 耗时 |
|------|------|------|
| `python bootstep.py dev` | 启动开发模式 | < 30s |
| `python bootstep.py restart-dev` | 重启开发模式（先 down 再 dev） | < 30s |
| `python bootstep.py up` | 启动生产模式（--build） | 3-5 min |
| `python bootstep.py down` | 停止所有环境 | < 10s |

### 5. 热重载策略

开发模式下：
- 后端：`../odap:/app/odap` bind mount + `uvicorn --reload`，.py 文件变更自动重载（2-3s）
- 前端：`../frontend/src:/app/src` bind mount + Vite HMR，代码变更即时刷新（< 1s）
- 注意：bind mount 有时不同步，需用 `podman cp` 手动复制新文件到容器

### 6. 环境选择决策树

```
需要修改代码？ → bootstep.py dev（日常开发）
需要部署/冒烟测试？ → bootstep.py up（生产模式）
改了 Dockerfile/requirements.txt？ → bootstep.py rebuild + dev
改了 .env.docker？ → bootstep.py restart-dev
```

## 后果

**正面**：
- 彻底消除环境混淆问题，dev/up 命令行为明确且可预测
- 开发模式启动 < 30s（复用镜像，不重建），大幅提升开发效率
- 互斥启动保证不会有残留容器造成端口冲突
- restart-dev 命令简化了日常重启流程

**负面**：
- 两个 compose 文件有部分重复（基础设施服务定义），需要手动同步
- 新开发者需要理解两套 compose 文件的存在

## 可逆性
高。可以合并回 override 模式，但强烈不建议。

**关联 ADR**：ADR-046（Modular Monolith 部署）、ADR-007（前端技术栈）

## 关联 ADR

- ADR-046：模块化单体部署
- ADR-007：前端采用 React + Ant Design 技术栈
