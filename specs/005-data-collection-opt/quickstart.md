# Quickstart: 数据采集功能优化

**Branch**: `005-data-collection-opt` | **Date**: 2026-06-13

## 前置条件

- ODAP 平台已通过 `python bootstep.py dev` 启动
- `.env.docker` 中配置了 `TAVILY_API_KEY`（可选，缺失时自动降级到 DuckDuckGo）
- Crawl4AI 容器服务已启动（P2 阶段需要）

## 快速验证步骤

### Step 1: 验证 Skill 注册

```bash
# 进入后端容器
podman exec -it graphiti-main-app bash

# 验证 web_search 和 web_crawl 已注册
python -c "
from odap.tools import SKILL_CATALOG
web_skills = {k: v for k, v in SKILL_CATALOG.items() if k.startswith('web_')}
print('Registered web skills:', list(web_skills.keys()))
"
# 期望输出: Registered web skills: ['web_search', 'web_crawl']
```

### Step 2: 验证 Agent 发现工具

```bash
# 验证 IntelligenceAgent 能发现 web 类别工具
python -c "
from odap.biz.core.agent.intelligence_agent import IntelligenceAgent
agent = IntelligenceAgent()
tool_names = [t['function']['name'] for t in agent.tools]
web_tools = [n for n in tool_names if n.startswith('web_')]
print('Agent web tools:', web_tools)
"
# 期望输出: Agent web tools: ['web_search', 'web_crawl']
```

### Step 3: 通过 API 测试搜索

```bash
# 获取 Token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 调用搜索 API
curl -X POST http://localhost:8000/api/web-search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "AI 最新进展", "max_results": 3}'
```

### Step 4: 通过 API 测试爬取

```bash
# 调用爬取 API
curl -X POST http://localhost:8000/api/web-crawl \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "output_format": "markdown"}'
```

### Step 5: 通过 Agent 对话测试

```bash
# 向 Agent 提问需要联网的问题
curl -X POST http://localhost:8000/api/agent/dispatch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "搜索最新的 AI 技术动态", "mode": "auto"}'
```

### Step 6: 验证 OPA 策略

```bash
# 测试域名白名单（应成功）
curl -X POST http://localhost:8000/api/web-crawl \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.reuters.com/article/xxx"}'

# 测试非白名单域名（非 admin 应被拒绝）
curl -X POST http://localhost:8000/api/web-crawl \
  -H "Authorization: Bearer $ANALYST_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://random-site.com/page"}'
# 期望: 403 Forbidden
```

### Step 7: 验证降级机制

```bash
# 停止 Crawl4AI 服务后测试爬取（应降级到 requests+BS4）
podman stop graphiti-crawl4ai

curl -X POST http://localhost:8000/api/web-crawl \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
# 期望: 返回结果中 crawl_method="requests_fallback"
```

## 前端验证

1. 打开 http://localhost:5173 → 摄入面板
2. 验证新增"智能爬取"和"联网搜索"选项卡
3. 输入 URL 测试爬取流程
4. 输入关键词测试搜索流程
5. 验证采集进度实时显示

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| web_search 返回 Mock 数据 | TAVILY_API_KEY 未配置 | 配置 .env.docker 或接受 DuckDuckGo 降级 |
| web_crawl 返回 requests_fallback | Crawl4AI 服务未启动 | `python bootstep.py restart` 或检查容器状态 |
| Agent 不调用 web_search | allowed_categories 未包含 web | 检查 intelligence_agent.py 配置 |
| OPA 拒绝爬取请求 | 域名不在白名单 | 更新 OPA 策略或使用 admin 角色 |
