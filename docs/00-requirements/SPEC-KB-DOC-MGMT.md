# SPEC-KB-DOC-MGMT: 知识库文档管理与图谱构建增强

> **版本**: 1.0.0 | **日期**: 2026-06-30 | **状态**: 已批准  
> **模块**: knowledge_base (数据域)  
> **作者**: ODAP 产品团队  
> **上游文档**: req-ok.md (v2.0.0), DOCUMENT_BASELINE_v1.0.0.md  
> **关联 ADR**: 待分配  

---

## 变更记录

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.0.0 | 2026-06-30 | 初始版本：知识库文档管理五项改进 |

---

## 1. 概述

### 1.1 背景

知识库（Knowledge Base）模块是 ODAP 平台的核心数据摄入入口，承担"文档上传 → 内容提取 → 图谱构建"的完整链路。在实际使用中发现以下问题：

1. 文件上传后不显示存储路径，用户无法确认文件落盘位置
2. 文件类型列显示原始 MIME 字符串（如 `application/vnd.openxmlformats-...`），且预览功能因类型判断失败而无法工作
3. 处理状态字段 (`status`) 与图谱构建状态字段 (`graph_built`) 不同步，导致文档状态始终显示"待处理"
4. 图谱查看功能无内容显示——后端使用 `GraphManager` 直接写入（违反架构规则），且实体 ID 不稳定
5. 文档处理详情页信息不完整，缺少文件大小友好格式化、下载入口等

### 1.2 目标

- 统一图谱写入链路：KB 模块必须通过 `GraphWriteProxy` 写入 Neo4j，与本体模块保持一致
- 完善文档生命周期管理：状态字段真实反映处理阶段
- 提升用户体验：友好的文件信息展示、存储路径可见、一键下载

### 1.3 范围

本 Spec 涵盖以下改动点：前端展示层（KnowledgeBase.tsx）、后端存储层（sqlite_kb_storage.py）、后端服务层（knowledge_base_service.py）。不涉及本体抽取管线（extraction module）的改动。

---

## 2. 功能需求

### 2.1 FR-01: 文件类型友好显示

**优先级**: P1  
**验收标准**: 文件类型列和详情页显示用户可理解的中文名称，而非原始 MIME 字符串。

**映射表**:

| MIME 类型 | 友好名称 |
|-----------|----------|
| application/pdf | PDF |
| application/vnd.openxmlformats-officedocument.wordprocessingml.document | Word 文档 |
| application/msword | Word 文档 (旧版) |
| application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | Excel 表格 |
| text/plain | 纯文本 |
| text/markdown | Markdown |
| text/csv | CSV 表格 |
| application/json | JSON |

**降级策略**: 未知 MIME 类型取 `subtype` 部分大写显示（如 `image/svg+xml` → `SVG+XML`）。

### 2.2 FR-02: 处理状态联合派生

**优先级**: P1  
**验收标准**: 列表和详情页的状态标签真实反映文档处理阶段，而非仅依赖 `status` 字段。

**派生规则**（按优先级从高到低）:

| 条件 | 显示标签 | 颜色 |
|------|----------|------|
| `status == 'error'` | 处理失败 | red |
| `status == 'processing'` | 处理中 | blue |
| `graph_built == true` | 图谱已构建 | green |
| `status == 'indexed'` | 已索引 | green |
| 其他 | 待处理 | default |

**后端同步**: `update_document_graph_status(doc_id, True)` 必须同时将 `status` 字段设为 `'indexed'`。

### 2.3 FR-03: 存储路径可见

**优先级**: P1  
**验收标准**: 文档详情 Drawer 中展示存储路径，支持 MinIO 对象和本地文件两种来源。

**展示规则**:
- MinIO 存储：显示 `minio://{bucket}/{key}` 格式 + 下载按钮（通过 presigned URL）
- 本地存储：显示本地文件路径 + 文件预览入口
- 文件大小：友好格式化（KB/MB/GB，保留 1 位小数）

### 2.4 FR-04: 图谱写入统一使用 GraphWriteProxy

**优先级**: P0  
**验收标准**: `_write_to_graph()` 方法通过 `get_graph_write_proxy()` 写入，禁止直接导入 `GraphManager`。

**技术要求**:
- 实体 ID 格式: `kb_{kb_id}_{entity_name}`，确保跨文档去重
- 关系写入时通过 `name_to_id` 映射解析 source/target
- 写入结果检查 `result["status"] == "success"` 而非布尔值
- 异常日志使用 `repr(e)` + `exc_info=True`

### 2.5 FR-05: 文档详情页增强

**优先级**: P2  
**验收标准**: 文档详情 Drawer 包含完整的处理信息和操作入口。

**详情项**:

| 字段 | 说明 |
|------|------|
| 文档标题 | `title` |
| 文件类型 | 友好名称（FR-01） |
| 文件大小 | 友好格式化 |
| 存储路径 | MinIO URI 或本地路径 + 下载（FR-03） |
| 处理状态 | 联合派生状态（FR-02） |
| 关键词 | `keywords` 数组，Tag 展示 |
| 摘要 | `summary` 文本 |
| 创建时间 | ISO 时间格式化 |
| 更新时间 | ISO 时间格式化 |

### 2.6 FR-06: 文档预览文件名必须包含扩展名

**优先级**: P0  
**验收标准**: DocumentViewer 传递给 jit-viewer 的 `filename` 参数必须包含正确的文件扩展名，否则 jit-viewer 无法识别文件类型（如 docx 显示"无法识别的文件类型"）。

**修复逻辑**:
- 从 `resolveExtension(fileUrl, fileType, filename)` 获取扩展名
- 如果 `filename`（通常是文档标题，如"电商产品说明文档"）不包含扩展名，自动追加 `.{ext}`
- 确保 Word/Excel/PPT/PDF 等 Office 文档均可被 jit-viewer 正确识别和渲染

**影响文件**: `frontend/src/modules/shared/components/DocumentViewer.tsx`

---

## 3. 非功能需求

### 3.1 NFR-01: 架构合规

KB 模块的图谱写入必须遵循 AGENTS.md 规则：业务模块通过 `GraphWriteProxy` 写入 Neo4j，禁止直接导入 `GraphManager`。

### 3.2 NFR-02: 向后兼容

- 前端 `deriveDocStatus()` 为纯展示层函数，不修改后端数据
- 后端 `update_document_graph_status()` 签名不变，仅内部 SQL 增加 `status` 字段更新
- 实体 ID 格式变更不影响已有查询（`get_kb_graph` 基于 `n.kb_id` 属性过滤）

### 3.3 NFR-03: 性能

- `deriveDocStatus()` 和 `friendlyFileType()` 为 O(1) 查找，无性能影响
- `_write_to_graph()` 新增 `name_to_id` 映射，内存开销为 O(n) 实体数，可忽略

---

## 4. 技术设计

### 4.1 改动文件清单

| 文件 | 层 | 改动内容 |
|------|---|----------|
| `frontend/src/modules/knowledge/pages/KnowledgeBase.tsx` | 展示层 | MIME 映射、状态派生、详情 Drawer 增强 |
| `frontend/src/modules/shared/components/DocumentViewer.tsx` | 展示层 | 确保 jit-viewer filename 包含扩展名（FR-06） |
| `odap/biz/data/knowledge_base/storage/sqlite_kb_storage.py` | 存储层 | `update_document_graph_status` 同步更新 `status` |
| `odap/biz/data/knowledge_base/services/knowledge_base_service.py` | 服务层 | `_write_to_graph` 改用 `GraphWriteProxy` |

### 4.2 数据流

```
用户上传文档
    ↓
MinIO / 本地存储（file_url 记录路径）
    ↓
LLM / 正则抽取实体和关系
    ↓
_write_to_graph()
    ↓  GraphWriteProxy.add_entity(entity_id, type, {kb_id, source_doc, name, ...})
    ↓  GraphWriteProxy.add_relationship(source_id, target_id, rel_type, props)
    ↓
update_document_graph_status(doc_id, True)
    ↓  SET graph_built=1, status='indexed', updated_at=now
    ↓
前端列表/详情刷新 → deriveDocStatus() 显示"图谱已构建"
```

### 4.3 实体 ID 设计

```
格式: kb_{kb_id}_{entity_name}
示例: kb_abc123_商品A
```

- 跨文档去重：同名实体 MERGE 为同一节点
- 关系引用：`name_to_id` 映射确保 source/target 指向正确实体
- 查询过滤：`n.kb_id = $kb_id` 属性过滤，与 ID 格式无关

---

## 5. 验收测试

### 5.1 测试用例

| 编号 | 场景 | 预期结果 |
|------|------|----------|
| TC-01 | 上传 PDF 文档 | 文件类型列显示"PDF"，非 MIME 字符串 |
| TC-02 | 构建图谱成功 | 状态列显示"图谱已构建"（green），status 字段变为 'indexed' |
| TC-03 | 查看文档详情 | Drawer 中显示存储路径（minio://...）和下载按钮 |
| TC-04 | 图谱构建后查看图谱 | ECharts 力导向图显示实体节点和关系边 |
| TC-05 | 重新构建图谱（同名实体） | 实体 MERGE 去重，不产生重复节点 |
| TC-06 | 预览 docx 文档（标题无扩展名） | jit-viewer 正确识别为 Word 文档并渲染预览，不显示"无法识别的文件类型" |

### 5.2 验证命令

```bash
# 后端导入验证
podman exec graphiti-main-app python -c \
  "from odap.biz.data.knowledge_base.services.knowledge_base_service import KnowledgeBaseService; print('OK')"

# 健康检查
podman exec graphiti-main-app python -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode()[:50])"

# 前端类型检查
podman exec graphiti-frontend-dev npx tsc --noEmit
```

---

## 6. 后续演进（不在本 Spec 范围）

以下需求已识别但不在本版本实现范围，留待后续迭代：

1. **管理员审核工作流**: 图谱构建前增加审核环节，管理员可查看抽取结果的溯源分析（provenance），确认后再写入 Neo4j
2. **抽取管线统一**: KB 文档抽取与本体抽取（HE + OntologyMapper）共用同一套管线，而非独立的 LLM prompt + 正则
3. **批量图谱构建**: 支持对整个知识库的所有文档批量构建图谱
4. **图谱增量更新**: 文档更新时仅增量写入变更的实体/关系，而非全量重建
