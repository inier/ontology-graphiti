# 数据摄入 API 设计规范

> **版本**: v1.0.0 | **状态**: 生效 | **最后更新**: 2026-04-26

---

## 1. 设计目标

本文档定义了本体管理系统中数据摄入 API 的设计规范，确保所有数据摄入方式（新闻、URL、手动输入、JSON、自然语言、随机事件）具有一致的输入输出结构，降低接入复杂度，提高可维护性。

### 1.1 核心原则

- **统一性**：所有摄入方式使用相同的接口结构
- **简洁性**：前端只需记忆一种调用方式
- **可扩展性**：新摄入方式可直接集成到统一结构中
- **一致性**：前后端使用相同的数据结构和命名约定

---

## 2. 统一输入结构

### 2.1 统一 API 调用格式

所有数据摄入方式使用统一的 `type` 和 `data` 字段，根据 `type` 不同，`data` 传递不同结构的数据。

```javascript
// 前端统一调用格式
await api.ingest({
  type: 'news',       // 摄入类型
  data: {...},        // 根据类型传递不同结构的数据
  scenario_id: 'xxx'  // 场景ID（可选）
});
```

### 2.2 支持的摄入类型

| type 值 | 描述 | data 结构示例 |
|---------|------|---------------|
| `news` | 新闻摄入 | 字符串 URL 或对象 `{url, event_context, max_sources}` |
| `manual` | 手动输入 | 字符串文本或对象 `{title, description}` |
| `json` | JSON 摄入 | JSON 格式字符串 |
| `natural_language` | 自然语言 | 字符串文本 |
| `random` | 随机生成 | 对象 `{parties, scenario_context, count}` |

### 2.3 输入类型详细说明

#### 2.3.1 新闻摄入 (type: 'news')

**data 为字符串时**：
```javascript
await api.ingest({
  type: 'news',
  data: 'https://example.com/news',  // 直接传递 URL
  scenario_id: currentScenario
});
```

**data 为对象时**：
```javascript
await api.ingest({
  type: 'news',
  data: {
    url: 'https://example.com/news',      // 新闻 URL
    event_context: '军事冲突',            // 事件上下文（可选）
    max_sources: 5                        // 最大源数量（可选）
  },
  scenario_id: currentScenario
});
```

#### 2.3.2 手动输入 (type: 'manual')

**data 为字符串时**：
```javascript
await api.ingest({
  type: 'manual',
  data: '红方部队进攻蓝方阵地',  // 直接传递文本
  scenario_id: currentScenario
});
```

**data 为对象时**：
```javascript
await api.ingest({
  type: 'manual',
  data: {
    title: '事件标题',
    description: '事件描述'
  },
  scenario_id: currentScenario
});
```

#### 2.3.3 JSON 摄入 (type: 'json')

```javascript
await api.ingest({
  type: 'json',
  data: '{"entities": [...], "relations": [...]}',  // JSON 字符串
  scenario_id: currentScenario
});
```

#### 2.3.4 自然语言 (type: 'natural_language')

```javascript
await api.ingest({
  type: 'natural_language',
  data: '美军航母舰队在南海进行军事演习',
  scenario_id: currentScenario
});
```

#### 2.3.5 随机生成 (type: 'random')

```javascript
await api.ingest({
  type: 'random',
  data: {
    parties: ['red', 'blue'],           // 参与方列表
    scenario_context: {type: 'war'},     // 场景上下文（可选）
    count: 3                            // 生成数量（可选）
  },
  scenario_id: currentScenario
});
```

---

## 3. 统一输出结构

### 3.1 响应结构

所有摄入方式返回一致的响应结构：

```json
{
  "ingest_id": "abc123",
  "status": "completed",
  "source_details": {...},
  "original_content": "...",
  "extracted_data": {
    "source_data": [...],
    "document_ids": [...],
    "document_count": 1,
    "entities_count": 5,
    "relations_count": 3,
    "events_count": 2
  }
}
```

### 3.2 响应字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| `ingest_id` | string | 摄入记录唯一标识 |
| `status` | string | 处理状态：pending, processing, completed, failed |
| `source_details` | object | 数据源详细信息 |
| `original_content` | string | 原始输入内容 |
| `extracted_data` | object | 提取的数据结果 |

### 3.3 extracted_data 字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `source_data` | array | 源数据数组 |
| `document_ids` | array | 生成的文档 ID 数组（复数形式） |
| `document_count` | integer | 文档数量 |
| `entities_count` | integer | 实体数量（单文档） |
| `total_entities` | integer | 实体总数（多文档） |
| `relations_count` | integer | 关系数量（单文档） |
| `total_relations` | integer | 关系总数（多文档） |
| `events_count` | integer | 事件数量（单文档） |
| `total_events` | integer | 事件总数（多文档） |

### 3.4 source_data 字段结构

所有摄入方式的 `source_data` 使用统一结构：

```json
[{
  "url": "",                    // 源 URL（无则为空字符串）
  "title": "标题",              // 数据标题
  "text": "原始内容",           // 原始文本内容
  "description": "描述",        // 数据描述
  "publish_date": "2026-04-26"  // 发布/创建日期
}]
```

---

## 4. 摄入方式输出示例

### 4.1 手动输入

```json
{
  "ingest_id": "abc123",
  "status": "completed",
  "source_details": {"form_data_keys": ["title", "description"]},
  "original_content": "红方部队在A区与蓝方部队发生冲突",
  "extracted_data": {
    "source_data": [{
      "url": "",
      "title": "手动输入事件",
      "text": "红方部队在A区与蓝方部队发生冲突",
      "description": "手动输入的事件描述",
      "publish_date": "2026-04-26T10:00:00Z"
    }],
    "document_ids": ["manual-20260426-abc123"],
    "document_count": 1,
    "entities_count": 2,
    "relations_count": 1,
    "events_count": 1
  }
}
```

### 4.2 新闻摄入

```json
{
  "ingest_id": "def456",
  "status": "completed",
  "source_details": {"query": "美伊局势", "max_sources": 5},
  "original_content": "[来源1] 美伊关系紧张...\nURL: https://example.com/news1",
  "extracted_data": {
    "source_data": [{
      "url": "https://example.com/news1",
      "title": "美伊关系紧张",
      "text": "新闻内容...",
      "description": "新闻摘要...",
      "publish_date": "2026-04-26"
    }],
    "document_ids": ["news-20260426-123abc"],
    "document_count": 1
  }
}
```

### 4.3 URL 摄入

```json
{
  "ingest_id": "ghi789",
  "status": "completed",
  "source_details": {"url": "https://example.com", "context": "军事冲突"},
  "original_content": "网页抓取的内容...",
  "extracted_data": {
    "source_data": [{
      "url": "https://example.com",
      "title": "网页标题",
      "text": "网页内容...",
      "description": "网页描述...",
      "publish_date": "2026-04-26"
    }],
    "document_ids": ["web-20260426-def456"],
    "document_count": 1
  }
}
```

### 4.4 JSON 摄入

```json
{
  "ingest_id": "jkl012",
  "status": "completed",
  "source_details": {"json_length": 256},
  "original_content": "{\"entities\": [...], \"relations\": [...]}",
  "extracted_data": {
    "source_data": [{
      "url": "",
      "title": "JSON输入",
      "text": "{\"entities\": [...], \"relations\": [...]}",
      "description": "JSON数据描述",
      "publish_date": "2026-04-26T10:00:00Z"
    }],
    "document_ids": ["json-20260426-mno345"],
    "document_count": 1,
    "entities_count": 3,
    "relations_count": 2,
    "events_count": 1
  }
}
```

### 4.5 自然语言摄入

```json
{
  "ingest_id": "pqr678",
  "status": "completed",
  "source_details": {"text_length": 50},
  "original_content": "美军航母舰队在南海进行军事演习",
  "extracted_data": {
    "source_data": [{
      "url": "",
      "title": "自然语言输入",
      "text": "美军航母舰队在南海进行军事演习",
      "description": "自然语言描述",
      "publish_date": "2026-04-26T10:00:00Z"
    }],
    "document_ids": ["nlp-20260426-stu901"],
    "document_count": 1,
    "entities_count": 2,
    "relations_count": 1,
    "events_count": 1
  }
}
```

### 4.6 随机事件生成

```json
{
  "ingest_id": "vwx234",
  "status": "completed",
  "source_details": {"parties": ["蓝方", "红方"], "count": 2},
  "original_content": "随机生成 2 个事件，参与方: ['蓝方', '红方']",
  "extracted_data": {
    "source_data": [{
      "url": "",
      "title": "随机事件生成",
      "text": "随机生成 2 个事件，参与方: ['蓝方', '红方']",
      "description": "生成了 2 个随机事件，包含 4 个实体，2 个关系，2 个事件",
      "publish_date": "2026-04-26T10:00:00Z"
    }],
    "document_ids": ["rand-20260426-abc123", "rand-20260426-def456"],
    "document_count": 2,
    "total_entities": 4,
    "total_relations": 2,
    "total_events": 2
  }
}
```

---

## 5. 状态码规范

### 5.1 处理状态

| 状态值 | 描述 |
|--------|------|
| `pending` | 等待处理 |
| `processing` | 处理中 |
| `completed` | 已完成 |
| `failed` | 失败 |

### 5.2 错误码

| 错误码 | HTTP 状态码 | 描述 |
|--------|-------------|------|
| `INVALID_PARAMETER` | 400 | 请求参数无效 |
| `MISSING_PARAMETER` | 400 | 缺少必需参数 |
| `INVALID_URL` | 400 | URL 格式无效 |
| `RESOURCE_NOT_FOUND` | 404 | 请求的资源不存在 |
| `TASK_NOT_FOUND` | 404 | 任务不存在 |
| `INGEST_FAILED` | 500 | 数据摄入失败 |
| `INTERNAL_ERROR` | 500 | 内部服务器错误 |

---

## 6. 后端实现规范

### 6.1 方法文档要求

每个摄入服务方法必须包含以下文档：

```python
async def ingest_from_manual(self, form_data: Any, scenario_id: str = None) -> str:
    """
    从手动输入摄入数据

    Args:
        form_data (Any): 手动输入的数据，可以是字典、字符串或其他类型
        scenario_id (str, optional): 场景ID，用于组织和管理摄入数据

    Returns:
        str: 摄入记录ID

    Raises:
        Exception: 当处理手动输入失败时

    Process:
        1. 创建摄入记录，设置状态为processing
        2. 自动检测并转换form_data类型
        3. 使用ManualInputHandler处理输入数据
        4. 提取实体、关系和事件
        5. 保存原始输入内容到摄入记录
        6. 保存生成的本体文档
        7. 触发本体构建过程
        8. 更新摄入记录状态为completed
        9. 处理任何异常并更新状态为failed
    """
```

### 6.2 返回结构统一

所有摄入方法必须在 `extracted_data` 中返回：

1. `source_data`：统一格式的源数据数组
2. `document_ids`：生成的文档 ID 数组（使用复数形式）
3. `document_count`：文档数量
4. 相应的统计字段（entities_count、relations_count 等）

---

## 7. 前端实现规范

### 7.1 统一 API 方法

```javascript
/**
 * 统一的数据摄入方法
 *
 * @param options 摄入选项
 * @param options.type 摄入类型：news, manual, json, natural_language, random
 * @param options.data 摄入数据（根据 type 不同，数据结构不同）
 * @param options.scenario_id 场景ID（可选）
 *
 * @returns 摄入结果
 */
async ingest(options: {
  type: 'news' | 'manual' | 'json' | 'natural_language' | 'random';
  data: any;
  scenario_id?: string;
}): Promise<{
  ingest_id: string;
  status: string;
  source_details?: Record<string, unknown>;
  original_content?: string;
  extracted_data?: Record<string, unknown>;
}>
```

### 7.2 调用示例

```javascript
// 所有摄入方式使用相同的调用格式
const result = await api.ingest({
  type: 'manual',      // 选择摄入类型
  data: '文本内容',     // 摄入数据
  scenario_id: 'xxx'   // 场景ID（可选）
});

// 处理结果
if (result.status === 'completed') {
  const documentIds = result.extracted_data.document_ids;
  // 使用 documentIds 获取详细数据
}
```

---

## 8. 设计优势

### 8.1 对前端开发者

- **降低学习成本**：只需学习一种 API 调用方式
- **简化代码**：无需为不同摄入方式编写不同处理逻辑
- **统一错误处理**：所有摄入方式使用相同的错误处理机制
- **便于维护**：接口结构统一，易于理解和维护

### 8.2 对后端开发者

- **清晰的规范**：每个方法都有详细的文档要求
- **一致的返回**：所有方法返回相同的数据结构
- **便于扩展**：新摄入方式可以直接集成到统一结构中
- **标准化的错误处理**：统一的异常处理模式

### 8.3 系统层面

- **可预测性**：所有摄入方式行为一致
- **可测试性**：统一的接口便于编写测试
- **可扩展性**：新功能可以直接复用现有结构

---

## 9. 附录

### 9.1 变更记录

| 版本 | 日期 | 描述 |
|------|------|------|
| v1.0.0 | 2026-04-26 | 初始版本，定义统一输入输出规范 |

### 9.2 参考资料

- [API_SPEC.md](./API_SPEC.md) - API 详细规范
- [ADR-050](./../07-adr/ADR-050_OADP业务语义体系架构.md) - OADP 业务语义体系架构

---

**文档维护者**: 开发团队
**下次审查时间**: 2026-05-26
