# Quickstart: 本体设计器彻底重构 — US3 Hyper-Extract 增强

**Branch**: `003-ontology-redesign` | **Date**: 2026-06-23

## 前置条件

- ODAP 开发环境已启动（`python bootstep.py dev`）
- 后端健康检查通过（`curl http://localhost:8000/health`）
- 已获取 JWT Token
- Hyper-Extract 依赖已安装（`pip install -e ./hyper-extract`）

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

### 2. 自然语言文本提取（Hyper-Extract）

```bash
# 从文本提取本体
curl -X POST http://localhost:8000/api/extraction/extract/natural-language \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ontology_id": "ont-001",
    "text": "电商系统需要管理用户、商品和订单。用户可以下单购买商品，订单包含多个商品项。库存不足时触发补货规则。",
    "source_type": "text",
    "method": "graph_rag"
  }'

# 查看提取会话
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/extraction/sessions/{session_id}

# 确认导入（双通道写入）
curl -X POST http://localhost:8000/api/extraction/sessions/{session_id}/confirm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "selected_type_ids": ["type-001", "type-002"],
    "selected_entity_ids": ["ent-001"],
    "merge_strategy": "skip",
    "write_channels": ["graph_write_proxy", "graphiti_episode"]
  }'
```

### 3. 文档上传提取

```bash
# 上传 PDF 文档提取
curl -X POST http://localhost:8000/api/extraction/extract/document \
  -H "Authorization: Bearer $TOKEN" \
  -F "ontology_id=ont-001" \
  -F "file=@/path/to/requirements.pdf" \
  -F "method=graph_rag"
```

### 4. 知识库增量提取

```bash
# 从知识库提取
curl -X POST http://localhost:8000/api/extraction/extract/knowledge-base \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ontology_id": "ont-001",
    "kb_id": "kb-001",
    "method": "graph_rag",
    "batch_size": 10
  }'
```

### 5. 模板管理

```bash
# 列出可用模板
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/extraction/templates?domain=general&auto_type=graph"

# 推荐模板
curl -X POST http://localhost:8000/api/extraction/templates/recommend \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"电商系统需要管理用户、商品和订单"}'
```

### 6. 溯源查询

```bash
# 查询实体溯源
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/extraction/provenance/{entity_id}

# 反向查询：某文档产生了哪些实体
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/extraction/provenance/by-source/{doc_id}
```

### 7. 前端验证

1. 访问 http://localhost:5173/ontology/designer
2. 在本体选择器中选择刚创建的本体
3. 选择"自然语言提取"设计方式
4. 在"文本输入"Tab 输入业务描述，点击提取
5. 切换到"文档上传"Tab，上传 PDF 文件
6. 切换到"知识库选择"Tab，选择已有知识库
7. 提取完成后在预览区查看 Schema 层定义和 Instance 层数据
8. 点击实体"溯源"图标查看来源文档和切片信息
9. 确认导入，验证双通道写入

## 新增依赖

```bash
# 后端 — Hyper-Extract + 文档解析
pip install -e ./hyper-extract
pip install langchain>=0.1.0 langchain-openai>=0.1.0 faiss-cpu>=1.7.0
pip install PyPDF2>=3.0.0 python-docx>=1.0.0 openpyxl>=3.1.0
pip install pytesseract>=0.3.10 Pillow>=10.0.0

# Docker 镜像额外系统依赖
apt-get install -y tesseract-ocr tesseract-ocr-chi-sim

# 前端（无新增依赖，复用 Ant Design 6 + Zustand 5 + AntV G6 5）
```
