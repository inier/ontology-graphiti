# API Contracts: 数据采集功能优化

**Branch**: `005-data-collection-opt` | **Date**: 2026-06-13

## 1. Skill 调用合约（Agent 内部）

### web_search

**调用方**: IntelligenceAgent / DomainSwarm / OpenHarness Agent

```json
{
  "name": "web_search",
  "description": "搜索互联网获取信息。当用户提问涉及外部实时信息、最新动态、或内部图谱无法回答的问题时使用此工具。",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "搜索关键词"
      },
      "max_results": {
        "type": "integer",
        "description": "最大返回结果数",
        "default": 5
      },
      "search_depth": {
        "type": "string",
        "enum": ["basic", "advanced"],
        "description": "搜索深度，advanced 更慢但更全面",
        "default": "basic"
      }
    },
    "required": ["query"]
  }
}
```

**返回格式**:
```json
{
  "success": true,
  "data": {
    "query": "搜索词",
    "results": [
      {
        "title": "结果标题",
        "url": "https://example.com/article",
        "snippet": "摘要文本",
        "source_domain": "example.com",
        "published_date": "2026-06-13"
      }
    ],
    "total_count": 5,
    "engine_used": "tavily",
    "source": "external",
    "confidence": "medium"
  },
  "execution_time_ms": 1200,
  "skill_name": "web_search",
  "request_id": "uuid"
}
```

### web_crawl

**调用方**: IntelligenceAgent / DomainSwarm / OpenHarness Agent

```json
{
  "name": "web_crawl",
  "description": "爬取指定网页内容，支持 JavaScript 渲染页面。当需要获取特定 URL 的详细内容时使用此工具。",
  "parameters": {
    "type": "object",
    "properties": {
      "url": {
        "type": "string",
        "description": "要爬取的网页 URL"
      },
      "output_format": {
        "type": "string",
        "enum": ["markdown", "fit_markdown", "html", "text"],
        "description": "输出格式，markdown 最适合 LLM 处理",
        "default": "markdown"
      },
      "css_selector": {
        "type": "string",
        "description": "仅提取匹配此选择器的内容（可选）"
      },
      "timeout": {
        "type": "integer",
        "description": "超时时间（秒）",
        "default": 30
      }
    },
    "required": ["url"]
  }
}
```

**返回格式**:
```json
{
  "success": true,
  "data": {
    "url": "https://example.com/page",
    "title": "页面标题",
    "content": "Markdown 格式的页面内容...",
    "links": [
      {"text": "链接文本", "href": "https://...", "link_type": "internal"}
    ],
    "metadata": {
      "title": "页面标题",
      "description": "meta description",
      "author": "作者",
      "published_date": "2026-06-13",
      "language": "zh"
    },
    "source": "external",
    "confidence": "medium",
    "is_complete": true,
    "crawl_method": "crawl4ai"
  },
  "execution_time_ms": 4500,
  "skill_name": "web_crawl",
  "request_id": "uuid"
}
```

---

## 2. REST API 合约（外部接口）

### POST /api/web-crawl

爬取指定 URL 的网页内容。

**请求**:
```json
{
  "url": "https://example.com/page",
  "output_format": "markdown",
  "css_selector": "article",
  "timeout": 30
}
```

**响应 200**:
```json
{
  "url": "https://example.com/page",
  "title": "页面标题",
  "content": "Markdown 内容...",
  "links": [],
  "metadata": {},
  "source": "external",
  "confidence": "medium",
  "is_complete": true,
  "crawl_method": "crawl4ai"
}
```

**响应 400** (URL 无效):
```json
{"detail": "Invalid URL format"}
```

**响应 403** (OPA 策略拒绝):
```json
{"detail": "Domain not allowed by OPA policy"}
```

**响应 408** (爬取超时):
```json
{
  "url": "https://example.com/page",
  "title": "",
  "content": "部分内容...",
  "source": "external",
  "confidence": "low",
  "is_complete": false,
  "crawl_method": "requests_fallback"
}
```

### POST /api/web-search

搜索互联网信息。

**请求**:
```json
{
  "query": "搜索关键词",
  "max_results": 5,
  "search_depth": "basic"
}
```

**响应 200**:
```json
{
  "query": "搜索关键词",
  "results": [
    {"title": "...", "url": "...", "snippet": "...", "source_domain": "...", "published_date": "..."}
  ],
  "total_count": 5,
  "engine_used": "tavily",
  "source": "external",
  "confidence": "medium"
}
```

### GET /api/web-crawl/health

检查 Crawl4AI 服务健康状态。

**响应 200**:
```json
{
  "crawl4ai_available": true,
  "fallback_available": true,
  "active_browsers": 1,
  "max_concurrent": 3
}
```

---

## 3. OPA 策略合约

### data_collection 策略

```rego
package data_collection

# 默认拒绝
default allow = false

# 允许的搜索操作
allow {
    input.action == "search"
    input.role == "admin"
}

allow {
    input.action == "search"
    input.role == "analyst"
}

# 允许的爬取操作（需域名白名单检查）
allow {
    input.action == "crawl"
    input.role == "admin"
}

allow {
    input.action == "crawl"
    input.role == "analyst"
    allowed_domain(input.target_domain)
}

# 允许的浏览器自动化操作（仅 admin）
allow {
    input.action == "browser"
    input.role == "admin"
}

# 域名白名单
allowed_domain(domain) {
    allowed_domains[i] == domain
}

allowed_domains = [
    "reuters.com",
    "bbc.com",
    "bloomberg.com",
    "xinhuanet.com",
    "people.com.cn",
    "thepaper.cn",
    "36kr.com",
    "caixin.com",
]
```

---

## 4. MCP 工具合约（browser-use MCP Server）

### browse_task

```json
{
  "name": "browse_task",
  "description": "执行 AI 驱动的浏览器自动化任务",
  "inputSchema": {
    "type": "object",
    "properties": {
      "task": {
        "type": "string",
        "description": "自然语言任务描述"
      },
      "max_steps": {
        "type": "integer",
        "description": "最大执行步数",
        "default": 20
      }
    },
    "required": ["task"]
  }
}
```

### browser_screenshot

```json
{
  "name": "browser_screenshot",
  "description": "截取当前浏览器页面截图",
  "inputSchema": {
    "type": "object",
    "properties": {}
  }
}
```

### browser_extract

```json
{
  "name": "browser_extract",
  "description": "从当前页面提取结构化数据",
  "inputSchema": {
    "type": "object",
    "properties": {
      "selector": {
        "type": "string",
        "description": "CSS 选择器"
      },
      "fields": {
        "type": "array",
        "items": {"type": "string"},
        "description": "要提取的字段名列表"
      }
    },
    "required": ["selector"]
  }
}
```
