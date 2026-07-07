# ADR-060: 知识库文档存储与图谱构建架构

## 状态
已采纳（2026-07-03）

## 上下文

ODAP 知识库模块需要管理用户上传的文档，并基于文档内容构建知识图谱。存储层面面临以下挑战：

1. **文档类型多样**：文本文件（.txt/.md/.csv）和二进制文件（.docx/.pdf）的存储策略完全不同
2. **对象存储不稳定**：MinIO 作为对象存储服务，存在 bucket 未初始化、凭据配置错误等问题
3. **图谱构建链路复杂**：文档 → LLM/正则提取 → Neo4j 写入，中间环节多且可能失败
4. **提取链路不统一**：KB 模块存在两条提取路径——HE（HyperExtract，产出 {nodes, edges}）和 SL（SchemaLevelExtractor，直接产出 7 类 type），格式完全不同
5. **前后端字段名不匹配**：KB 用 kb_id/doc_id/title，而通用 API 用 id/name 等，反复出现集成问题

## 决策

### 1. 双轨存储策略

根据文件类型采用不同的存储方案：

| 文件类型 | 存储位置 | 说明 |
|----------|----------|------|
| 文本文件（.txt/.md/.csv） | SQLite `kb_documents.content` 列 | 直接存内容，无需外部依赖 |
| 二进制文件（.docx/.pdf） | MinIO 优先，本地降级 | MinIO 不可用时存本地磁盘 |

二进制文件存储优先级：
1. **MinIO**（`odap-documents` bucket）：presigned URL 支持预览，容器间通过 `graphiti-minio:9000` 通信
2. **本地磁盘**（`{DATA_DIR}/uploads/kb/{kb_id}/`）：MinIO 不可用时的降级方案
3. 删除文档时同步清理两个存储位置

### 2. 文件预览链路

```
前端请求预览 → GET /api/knowledge-bases/{kb_id}/documents/{doc_id}/preview
→ 后端从 MinIO 或本地读取文件
→ 通过 /uploads/kb/ StaticFiles 挂载提供下载
→ jit-viewer SDK 根据 filename 扩展名判断文件类型并渲染
```

注意：jit-viewer 仅通过扩展名判断类型，不读 MIME。DocumentViewer 传标题作 filename 时必须追加扩展名。

### 3. 图谱构建双链路

KB 模块存在两条独立的提取路径，合并时必须检测格式：

| 链路 | 入口 | 输出格式 | 合并策略 |
|------|------|----------|----------|
| HE（HyperExtract） | 异步任务 | `{nodes: [...], edges: [...]}` | 经 OntologyMapper 转换 |
| SL（SchemaLevelExtractor） | 同步调用 | 7 类 type 的 Dict | 按 type 键去重合并 |

合并检测逻辑：看有无 `nodes` 键 → 有则走 HE+Mapper，无则走 SL 直接按 type 合并。

### 4. 实体 ID 与去重

图谱实体 ID 格式：`kb_{kb_id}_{entity_name}`，确保跨文档 MERGE 去重。关系写入通过 name_to_id 映射解析实体引用。

### 5. 状态管理

文档状态通过 `status` + `graph_built` 双字段派生：
- `status = "pending"` → 待处理
- `status = "indexed"` + `graph_built = False` → 已索引，图谱未构建
- `status = "indexed"` + `graph_built = True` → 已完成
- `status = "failed"` → 处理失败

`_write_to_graph()` 使用 `GraphWriteProxy`（架构规则：业务模块禁止直接用 GraphManager 写 Neo4j），返回 bool 表示成功/失败。

### 6. 实现模块

后端：`odap/biz/data/knowledge_base/`（api/services/storage 三层）
前端：`frontend/src/modules/knowledge/`（components/pages/services/stores）
存储：SQLite `kb_documents` 表 + MinIO `odap-documents` bucket + 本地降级
图谱：Neo4j（通过 GraphWriteProxy 写入）

### 7. 关键陷阱

- MinIO 拒绝 `minioadmin` 凭据，.env.docker 必须设非默认凭据（≥8位）
- presigned URL 用容器内主机名 `graphiti-minio:9000`，`_attach_presigned_url()` 自动替换为 `localhost:9000`
- MinIO Console（9001）发 `X-Frame-Options: DENY`，不可 iframe 嵌入
- FastAPI multipart 路由的 Form() 参数必须显式声明，未声明字段被静默丢弃
- 生产入口 app.py 需手动挂载 `/uploads/kb` 的 StaticFiles，否则预览返回 404

## 后果

**正面**：
- 双轨存储保证文本文件零依赖、二进制文件有降级方案
- 双链路提取兼容历史实现，合并逻辑清晰
- 实体 ID 格式统一，跨文档去重可靠
- 状态双字段派生，前端展示准确

**负面**：
- 双链路增加维护复杂度，长期应统一为单一提取管线
- MinIO 降级到本地磁盘后，文件 URL 管理变复杂
- 前后端字段名映射（kb_id vs id 等）需要持续注意

## 可逆性

中。存储策略变更需要数据迁移，但提取链路可以独立调整。

## 关联 ADR

- ADR-002：Graphiti 双时态知识图谱
- ADR-019：多模态文档处理流水线
- ADR-013：多数据源统一接入
