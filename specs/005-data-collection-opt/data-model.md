# Data Model: 数据采集功能优化

**Branch**: `005-data-collection-opt` | **Date**: 2026-06-13 | **Spec**: [spec.md](spec.md)

## 实体定义

### 1. WebSearchInput

搜索 Skill 输入模型。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:----:|--------|------|
| request_id | str | 否 | uuid4 | 请求唯一标识 |
| timestamp | datetime | 否 | now | 请求时间 |
| query | str | 是 | - | 搜索关键词 |
| max_results | int | 否 | 5 | 最大返回结果数（1-20） |
| search_depth | str | 否 | "basic" | 搜索深度：basic/advanced |

验证规则：
- `query` 非空，长度 1-500
- `max_results` 范围 1-20
- `search_depth` 枚举值 ("basic", "advanced")

### 2. WebCrawlInput

爬取 Skill 输入模型。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:----:|--------|------|
| request_id | str | 否 | uuid4 | 请求唯一标识 |
| timestamp | datetime | 否 | now | 请求时间 |
| url | str | 是 | - | 目标网页 URL |
| output_format | str | 否 | "markdown" | 输出格式：markdown/fit_markdown/html/text |
| css_selector | str | 否 | None | 内容提取 CSS 选择器 |
| js_code | str | 否 | None | 自定义 JavaScript 代码 |
| wait_for | str | 否 | None | 等待条件（CSS 选择器） |
| timeout | int | 否 | 30 | 超时时间（秒） |

验证规则：
- `url` 必须是合法 HTTP/HTTPS URL
- `output_format` 枚举值 ("markdown", "fit_markdown", "html", "text")
- `timeout` 范围 5-120

### 3. WebSearchOutput

搜索 Skill 输出模型。

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |
| data | WebSearchData | 搜索结果数据 |
| error | str | 错误信息 |
| execution_time_ms | int | 执行耗时 |
| skill_name | str | Skill 名称 |
| request_id | str | 请求标识 |

### 4. WebSearchData

搜索结果数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| query | str | 原始搜索词 |
| results | List[SearchResultItem] | 搜索结果列表 |
| total_count | int | 结果总数 |
| engine_used | str | 实际使用的搜索引擎 |
| source | str | 来源标记（固定 "external"） |
| confidence | str | 可信度：high/medium/low |

### 5. SearchResultItem

单条搜索结果。

| 字段 | 类型 | 说明 |
|------|------|------|
| title | str | 结果标题 |
| url | str | 结果链接 |
| snippet | str | 摘要文本 |
| source_domain | str | 来源域名 |
| published_date | str | 发布日期（可选） |

### 6. WebCrawlOutput

爬取 Skill 输出模型。

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |
| data | WebCrawlData | 爬取结果数据 |
| error | str | 错误信息 |
| execution_time_ms | int | 执行耗时 |
| skill_name | str | Skill 名称 |
| request_id | str | 请求标识 |

### 7. WebCrawlData

爬取结果数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| url | str | 原始 URL |
| title | str | 页面标题 |
| content | str | 提取的内容（格式由 output_format 决定） |
| links | List[LinkItem] | 页面链接列表 |
| metadata | PageMetadata | 页面元数据 |
| source | str | 来源标记（固定 "external"） |
| confidence | str | 可信度：high/medium/low |
| is_complete | bool | 内容是否完整（JS 渲染超时时可能不完整） |
| crawl_method | str | 爬取方式：crawl4ai/requests_fallback |

### 8. LinkItem

页面链接。

| 字段 | 类型 | 说明 |
|------|------|------|
| text | str | 链接文本 |
| href | str | 链接地址 |
| link_type | str | 链接类型：internal/external |

### 9. PageMetadata

页面元数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| title | str | 页面标题 |
| description | str | meta description |
| author | str | 作者 |
| published_date | str | 发布日期 |
| language | str | 页面语言 |

### 10. CollectionTask

采集任务（用于任务追踪）。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:----:|--------|------|
| id | str | 否 | uuid4 | 任务 ID |
| task_type | CollectionTaskType | 是 | - | 任务类型：search/crawl/browser |
| target | str | 是 | - | 采集目标（URL 或搜索词） |
| status | CollectionTaskStatus | 否 | "pending" | 任务状态 |
| result | dict | 否 | None | 采集结果 |
| error_message | str | 否 | None | 错误信息 |
| source | str | 否 | "external" | 来源标记 |
| confidence | str | 否 | "medium" | 可信度 |
| created_at | datetime | 否 | now | 创建时间 |
| completed_at | datetime | 否 | None | 完成时间 |
| workspace_id | str | 否 | None | 所属工作空间 |
| scenario_id | str | 否 | None | 所属场景 |

### 11. CollectionTaskType (Enum)

```python
class CollectionTaskType(str, Enum):
    SEARCH = "search"
    CRAWL = "crawl"
    BROWSER = "browser"
```

### 12. CollectionTaskStatus (Enum)

```python
class CollectionTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DEGRADED = "degraded"
```

## 实体关系

```
CollectionTask
    ├── 1:1 → WebSearchData (task_type=search 时)
    ├── 1:1 → WebCrawlData (task_type=crawl 时)
    └── N:1 → Workspace (workspace_id)
    └── N:1 → Scenario (scenario_id)

WebSearchData
    └── 1:N → SearchResultItem

WebCrawlData
    ├── 1:N → LinkItem
    └── 1:1 → PageMetadata

IntelligenceAgent
    └── N:N → Skill (通过 SKILL_CATALOG)
        ├── web_search (WebSearchSkill)
        └── web_crawl (WebCrawlSkill)
```

## 状态转换

### CollectionTask 状态机

```
pending → running → completed
                  → failed
                  → timeout
                  → degraded (降级完成，如 Crawl4AI 失败回退到 requests)
```

## SkillMetadata 定义

### web_search

| 字段 | 值 |
|------|-----|
| name | "web_search" |
| description | "搜索互联网获取信息" |
| category | "web" |
| danger_level | "low" |
| requires_opa_check | True |
| opa_action | "data_collection:search" |
| version | "1.0.0" |

### web_crawl

| 字段 | 值 |
|------|-----|
| name | "web_crawl" |
| description | "爬取指定网页内容（支持 JS 渲染）" |
| category | "web" |
| danger_level | "medium" |
| requires_opa_check | True |
| opa_action | "data_collection:crawl" |
| version | "1.0.0" |

### browser_automate (P3)

| 字段 | 值 |
|------|-----|
| name | "browser_automate" |
| description | "AI 驱动的浏览器自动化采集" |
| category | "web" |
| danger_level | "high" |
| requires_opa_check | True |
| opa_action | "data_collection:browser" |
| version | "1.0.0" |
