# 全链路架构审计 — Round 1 报告

> 日期: 2026-07-03  |  审计范围: 采集→存储→清洗→本体→图谱→查询→Agent→决策

## Round 1: 现状调研综合评分 — 70.2/100

| 阶段 | 得分 | 关键发现 |
|------|------|---------|
| 1. 数据采集 | 70 | 三套并行入口(KB/统一摄入/本体摄入)，功能重叠 |
| 2. 临时存储 | 65 | MinIO+SQLite+本地磁盘降级，但无版本管理 |
| 3. 数据清洗 | 40 | **最大短板** — KB路径基本无清洗，管道清洗仅空白+去重 |
| 4. 结构化存储 | 75 | Neo4j双时态架构扎实，GraphWriteProxy设计良好 |
| 5. 知识库链路 | 60 | CRUD完整，但RAG退化为SQLite关键词匹配 |
| 6. 本体定义 | 78 | CRUD完整，但5个SQLite DB存冗余数据 |
| 7. 建模设计 | 82 | 前端设计器功能丰富，属性/关系/约束定义完整 |
| 8. 图谱搭建 | 68 | 分层良好，但类型映射过于简单，EntityEdge UUID未解析 |
| 9. Smart Query | 76 | DSL统一，协议化设计清晰，但本体过滤不完整 |
| 10. Agent决策 | 85 | AG-UI集成完整，工具链路清晰，ONTOLOGY_CHANGED事件闭环 |

## 六大断点（按严重程度）

### P0 — 阻断级
1. **KB路径无清洗** — 文档上传后原样传给LLM，无预处理 (B1)
2. **RAG无向量检索** — `rag_query`用SQLite关键词匹配，与Graphiti向量能力割裂 (B2)

### P1 — 高风险
3. **三套摄入入口重复** — KB上传/统一摄入/本体摄入功能重叠，维护成本高 (B3)
4. **图谱写入未用Graphiti** — KB图谱构建用Neo4j Driver直写，损失双时态能力 (B6)

### P2 — 中风险
5. **本体类型映射简单** — Neo4j Label用自然语言名而非type_id (B8)
6. **存储冗余** — 5个独立SQLite DB存相似本体数据 (B7)

## 全链路数据流图（现状）

```
[采集]                [临时存储]           [清洗]             [结构化]        [查询&决策]
                                                                          
KB上传 ─┬─ 文本 ──→ SQLite raw ────→ ❌无清洗 ──→ LLM提取 ──→ Neo4j MERGE
        │                                                               │
        └─ 二进制 ──→ MinIO/本地 ────→ ❌无清洗 ──→             GraphWriteProxy
                                                                        │
统一摄入───────────→ PerceptionHub ──→ ⚠️基础清洗 ──→ Pipeline ──→ Neo4j │
                                                                        │
文件上传───────────→ MinIO ──→ PDF/Word处理器 ──→ ⚠️基础清洗 ──→ Graphiti│
                                                                        │
                                                                        ▼
                                                                  Smart Query DSL
                                                                  (.schema .entity .topo .temporal)
                                                                        │
                                                                        ▼
                                                                  Agent Q&A (AI Assistant Plugin)
                                                                  → 16 BaseTool → 决策建议
```

## 下一步: Round 2 — 分析问题并排列修复优先级
