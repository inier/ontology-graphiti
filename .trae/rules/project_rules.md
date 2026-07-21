<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/006-he-extraction-chain/plan.md and research at specs/006-he-extraction-chain/research.md,
plus semantic admin docs at specs/007-semantic-admin-suite/spec.md

**Active feature branch**: `006-he-extraction-chain`
For current Hyper-Extract extraction chain work, also read:
- spec at `specs/006-he-extraction-chain/spec.md`
- plan at `specs/006-he-extraction-chain/plan.md`
- research at `specs/006-he-extraction-chain/research.md`
- data model at `specs/006-he-extraction-chain/data-model.md`
- quickstart at `specs/006-he-extraction-chain/quickstart.md`
- contracts under `specs/006-he-extraction-chain/contracts/`

**Active feature branch**: `007-semantic-admin-suite`
For Semantic Admin Suite (USL management + OL 6-layer pipeline + HITL approval flywheel) work, also read:
- spec at `specs/007-semantic-admin-suite/spec.md`
- plan at `specs/007-semantic-admin-suite/plan.md`
- research at `specs/007-semantic-admin-suite/research.md`
- data model at `specs/007-semantic-admin-suite/data-model.md`
- quickstart at `specs/007-semantic-admin-suite/quickstart.md`
- contracts under `specs/007-semantic-admin-suite/contracts/`

Previous feature branch `003-ontology-redesign` (completed):
- spec at `specs/003-ontology-redesign/spec.md`
- plan at `specs/003-ontology-redesign/plan.md`
- research at `specs/003-ontology-redesign/research.md`

Previous feature branch `005-data-collection-opt` (completed):
- spec at `specs/005-data-collection-opt/spec.md`
- plan at `specs/005-data-collection-opt/plan.md`

## Podman 镜像和容器命名规范

### 镜像命名规范

**基础镜像**（从 DaoCloud 拉取后打标）:
```
localhost/{name}:{tag}
```
示例:
- `localhost/redis:6`
- `localhost/neo4j:latest`
- `localhost/openpolicyagent/opa:0.58.0`
- `localhost/python:3.10-slim`, `localhost/python:3.11-slim`
- `localhost/node:24-alpine`
- `localhost/nginx:alpine`
- `localhost/minio:latest`

**自定义基础镜像**（基于上游镜像构建）:
- `localhost/node-base:24` — 前端构建基础（含 python3/make/g++/pnpm9）

**应用镜像**（项目自行构建）:
- `localhost/docker_app:latest` — 后端应用（dev/prod 共用，唯一命名，禁止使用 ontology-graphiti 别名）
- `localhost/docker_frontend:dev` — 前端开发（Vite 热重载）
- `localhost/docker_frontend:latest` — 前端生产（Nginx 静态）

**扩展服务镜像**:
- `localhost/crawl4ai:latest` — Crawl4AI JS 渲染爬取服务
- `localhost/browser-use:latest` — Browser-Use MCP Server

### 容器命名规范

**生产环境**: `graphiti-{service}`
- `graphiti-frontend`
- `graphiti-main-app`
- `graphiti-policy-service`
- `graphiti-neo4j`
- `graphiti-cache`
- `graphiti-minio`
- `graphiti-crawl4ai`
- `graphiti-browser-use`

**开发环境**: `graphiti-dev-{service}`
- `graphiti-dev-frontend`
- `graphiti-dev-app`
- `graphiti-dev-opa`
- `graphiti-dev-neo4j`
- `graphiti-dev-redis`
- `graphiti-dev-minio`

### 规则约束

1. 所有镜像必须使用 `localhost/` 前缀，禁止使用未限定镜像名（如 `minio/minio`），避免构建时 fallback 到 docker.io 导致 GFW 超时
2. 镜像和容器命名规范一旦确定，**不得反复修改**，确保内部 DNS 解析和脚本引用稳定
3. 开发环境和生产环境通过 `-dev` 后缀隔离，端口冲突时自动停止对立环境容器
4. dangling 镜像（`<none>:<none>`）应通过 `python bootstep.py clean` 定期清理
5. 镜像重建使用 `python bootstep.py rebuild [target]`，不手动执行 `podman build`
<!-- SPECKIT END -->
