"""Web 数据采集技能模块 - 提供联网搜索、网页爬取和浏览器自动化能力"""

from .web_skills import web_search, web_crawl, browser_automate, WebSearchSkill, WebCrawlSkill, BrowserAutomateSkill

__all__ = ["web_search", "web_crawl", "browser_automate", "WebSearchSkill", "WebCrawlSkill", "BrowserAutomateSkill"]
