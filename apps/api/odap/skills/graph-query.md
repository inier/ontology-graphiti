# Graph Query

You can query the ODAP knowledge graph using natural language. The system supports entity search, relationship traversal, and temporal queries through the QueryService DSL.

## Query Capabilities

- List entities by type, filter by properties
- Search entities by name, description, or content
- Query relationships between entities (graph traversal)
- Query temporal data — what happened in a time range
- Combine filters: type + time range + property conditions

## Available Tools

Use these tools via the Tool Registry:
- list_entities — List entities of a given type
- search_entities — Full-text search across entities
- query_relations — Query relationships/edges between entities
- query_temporal — Query entities within a time range
- qa_retrieve — Full RAG retrieval (BM25 + vector + graph hybrid)

## Query DSL (for reference)

When using tools internally, the backend translates to QueryService DSL:
```
.entity list(10)                      — list entities
.entity search("keyword")             — search entities
.entity with(name="X") list(5)        — filtered list
.topo source("X") depth(2)            — graph traversal
.temporal range(2024-01-01, 2024-06-30)  — time range query
```

## Example Queries

| User asks | Tool to use |
|-----------|------------|
| "有哪些用户" | list_entities(object_type_name="用户") |
| "搜索包含error的实体" | search_entities(query="error") |
| "User和Order是什么关系" | query_relations(source_type="User", target_type="Order") |
| "最近一周有哪些事件" | query_temporal(time_range="last_7_days") |
| "帮我查一下安全事件" | qa_retrieve(query="安全事件") |

## Temporal Query Notes

- Time expressions: "最近一周", "上个月", "2024年Q1", "昨天"
- Temporal queries return entities with timestamps in the specified range
- Combine with entity type filters for targeted results
