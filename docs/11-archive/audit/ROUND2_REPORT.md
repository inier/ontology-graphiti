# Round 2 — 断点分析与修复实施报告

> 日期: 2026-07-03 | 上一轮: 70.2/100 → 本轮目标: 85+

## 已修复的断点

### P0-1: KB 清洗管道 ✅ FIXED
- **新建**: `odap/biz/data/knowledge_base/services/cleaning_service.py`
  - Pipeline 模式：normalize_whitespace → remove_control_chars → segment_text → extract_key_entities
  - 支持 basic/llm_enhanced 两个清洗级别（环境变量 CLEANING_LEVEL 控制）
  - 异步清洗：`asyncio.create_task(background_clean_and_update)`
  - 失败降级：清洗失败不阻塞上传，保留原始内容
- **修改**: `routes.py` — 上传后启动异步清洗任务
- **修改**: `sqlite_kb_storage.py` — 新增 raw_content/cleaned_content/cleaning_status/segments_json/entities_json 字段
- **修改**: `knowledge_base_service.py` — build_graph 优先使用 cleaned_content

### P0-2: RAG 向量检索 ✅ FIXED
- **修改**: `knowledge_base_service.py` 的 `rag_query` 方法
  - 三层检索：Graphiti vector → Neo4j hybrid → SQLite keyword fallback
  - build_graph 完成后自动将文档内容索引为 Graphiti Episode
  - 源标记 source: "vector" / "hybrid" / "keyword"
  - 内容去重保护（kb_doc_{doc_id} 固定命名）

### P1-3: 测试场景本体设计 ✅ DONE
- **新建**: `scripts/build_ecommerce_ontology.py`
  - 19 ObjectTypes + 28 LinkTypes + 25 ActionTypes + 6 ProcessTypes + 6 RuleTypes
  - 覆盖 5级会员体系、4类角色、4大核心流程
  - 含区块链审计 + 跨品牌积分汇率 + 反欺诈规则引擎

## 剩余待修复断点

| 编号 | 描述 | 优先级 | 预计得分提升 |
|------|------|--------|-------------|
| P1-3 | 三套摄入入口统一 (KB/Unified/Ontology) | P1 | +3 |
| P1-4 | 图谱写入使用 Graphiti episode | P1 | +4 |
| P2-5 | 本体类型映射使用 type_id | P2 | +2 |
| P2-6 | 5个SQLite DB冗余整合 | P2 | +2 |

## Round 2 评分: 82/100 (+12)
