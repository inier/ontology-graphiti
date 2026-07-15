"""Browser-Use MCP Server — AI 驱动浏览器自动化采集

将 browser-use 框架封装为 MCP Tool Server，提供三个工具：
- browse_task: 执行浏览器自动化任务
- browser_screenshot: 截取当前页面截图
- browser_extract: 从当前页面提取数据

通过 HTTP API 对外暴露，由 MCPServerManager 统一管理。
"""

import asyncio
import base64
import json
import logging
import os
import signal
import uuid
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ============================================================
# 请求/响应 Schema
# ============================================================

class BrowseTaskRequest(BaseModel):
    """浏览器自动化任务请求"""
    task: str = Field(..., description="自然语言描述的浏览器任务，如'登录 example.com 并提取首页新闻标题'")
    url: Optional[str] = Field(None, description="起始 URL（可选，任务描述中可包含）")
    max_steps: int = Field(25, description="最大执行步数", ge=1, le=100)
    timeout_seconds: int = Field(300, description="超时时间（秒），硬限制 5 分钟", ge=10, le=300)


class BrowserScreenshotRequest(BaseModel):
    """截图请求"""
    url: str = Field(..., description="要截图的 URL")
    full_page: bool = Field(False, description="是否截取完整页面")
    width: int = Field(1280, description="视口宽度")
    height: int = Field(720, description="视口高度")


class BrowserExtractRequest(BaseModel):
    """数据提取请求"""
    url: str = Field(..., description="目标 URL")
    extraction_prompt: str = Field(..., description="提取指令，如'提取所有产品名称和价格'")
    selector: Optional[str] = Field(None, description="CSS 选择器（可选，缩小提取范围）")
    max_steps: int = Field(15, description="最大执行步数", ge=1, le=50)


class ToolResponse(BaseModel):
    """通用工具响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


# ============================================================
# Browser-Use 执行引擎
# ============================================================

class BrowserUseEngine:
    """browser-use 执行引擎

    封装 browser-use 的 Agent + Browser 组合，
    提供任务执行、截图、数据提取能力。
    """

    def __init__(self):
        self._active_sessions: Dict[str, Any] = {}  # session_id → browser

    @staticmethod
    def is_available() -> bool:
        """检查 browser-use 是否可用"""
        try:
            import browser_use  # noqa: F401
            return True
        except ImportError:
            return False

    async def execute_task(self, request: BrowseTaskRequest) -> ToolResponse:
        """执行浏览器自动化任务"""
        if not self.is_available():
            return ToolResponse(
                success=False,
                error="browser-use not installed. Install with: pip install browser-use",
            )

        import time
        start = time.monotonic()
        session_id = str(uuid.uuid4())

        try:
            from browser_use import Agent
            from langchain_openai import ChatOpenAI

            # 创建 LLM 客户端（复用项目环境变量）
            llm = ChatOpenAI(
                model=get_config("llm.model", "gpt-4o"),
                api_key=get_config("llm.api_key", ""),
                base_url=get_config("llm.api_base"),
            )

            # 构建任务描述
            task_desc = request.task
            if request.url:
                task_desc = f"Go to {request.url} and then: {task_desc}"

            # 创建 Agent 并执行
            agent = Agent(task=task_desc, llm=llm, max_steps=request.max_steps)

            # 带超时执行
            result = await asyncio.wait_for(
                agent.run(),
                timeout=request.timeout_seconds,
            )

            execution_time = (time.monotonic() - start) * 1000

            return ToolResponse(
                success=True,
                data={
                    "session_id": session_id,
                    "result": str(result) if result else "Task completed",
                    "steps_taken": getattr(agent, "step_count", 0),
                },
                execution_time_ms=round(execution_time, 2),
            )

        except asyncio.TimeoutError:
            return ToolResponse(
                success=False,
                error=f"Browser task timed out after {request.timeout_seconds}s",
                execution_time_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as e:
            logger.error(f"Browser task failed: {e}")
            return ToolResponse(
                success=False,
                error=f"Browser task failed: {e}",
                execution_time_ms=(time.monotonic() - start) * 1000,
            )
        finally:
            # 确保释放浏览器资源
            await self._cleanup_session(session_id)

    async def take_screenshot(self, request: BrowserScreenshotRequest) -> ToolResponse:
        """截取页面截图"""
        if not self.is_available():
            return ToolResponse(success=False, error="browser-use not installed")

        import time
        start = time.monotonic()

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": request.width, "height": request.height})
                await page.goto(request.url, wait_until="networkidle", timeout=30000)

                screenshot_bytes = await page.screenshot(
                    full_page=request.full_page,
                    type="png",
                )
                await browser.close()

            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            return ToolResponse(
                success=True,
                data={
                    "screenshot_base64": screenshot_b64,
                    "url": request.url,
                    "full_page": request.full_page,
                    "size_bytes": len(screenshot_bytes),
                },
                execution_time_ms=round((time.monotonic() - start) * 1000, 2),
            )

        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return ToolResponse(
                success=False,
                error=f"Screenshot failed: {e}",
                execution_time_ms=round((time.monotonic() - start) * 1000, 2),
            )

    async def extract_data(self, request: BrowserExtractRequest) -> ToolResponse:
        """从页面提取数据"""
        if not self.is_available():
            return ToolResponse(success=False, error="browser-use not installed")

        import time
        start = time.monotonic()

        try:
            from browser_use import Agent
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=get_config("llm.model", "gpt-4o"),
                api_key=get_config("llm.api_key", ""),
                base_url=get_config("llm.api_base"),
            )

            task_desc = f"Go to {request.url} and extract: {request.extraction_prompt}"
            if request.selector:
                task_desc += f" Focus on elements matching CSS selector: {request.selector}"
            task_desc += " Return the extracted data as structured JSON."

            agent = Agent(task=task_desc, llm=llm, max_steps=request.max_steps)
            result = await asyncio.wait_for(agent.run(), timeout=180)

            return ToolResponse(
                success=True,
                data={
                    "url": request.url,
                    "extracted_data": str(result) if result else "",
                    "extraction_prompt": request.extraction_prompt,
                },
                execution_time_ms=round((time.monotonic() - start) * 1000, 2),
            )

        except asyncio.TimeoutError:
            return ToolResponse(
                success=False,
                error="Data extraction timed out after 180s",
                execution_time_ms=round((time.monotonic() - start) * 1000, 2),
            )
        except Exception as e:
            logger.error(f"Data extraction failed: {e}")
            return ToolResponse(
                success=False,
                error=f"Data extraction failed: {e}",
                execution_time_ms=round((time.monotonic() - start) * 1000, 2),
            )

    async def _cleanup_session(self, session_id: str):
        """清理会话资源"""
        browser = self._active_sessions.pop(session_id, None)
        if browser:
            try:
                await browser.close()
            except Exception:
                pass


# ============================================================
# MCP Tool Server (FastAPI)
# ============================================================

_engine = BrowserUseEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Browser-Use MCP Server starting")
    yield
    # 清理所有活跃会话
    for sid in list(_engine._active_sessions.keys()):
        await _engine._cleanup_session(sid)
    logger.info("Browser-Use MCP Server stopped")


app = FastAPI(
    title="Browser-Use MCP Server",
    description="AI 驱动浏览器自动化采集 MCP Tool Server",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy" if _engine.is_available() else "degraded",
        "browser_use_available": _engine.is_available(),
        "active_sessions": len(_engine._active_sessions),
    }


@app.get("/capabilities")
async def capabilities():
    """能力发现"""
    return {
        "tools": [
            {
                "name": "browse_task",
                "description": "Execute a browser automation task described in natural language",
                "input_schema": BrowseTaskRequest.model_json_schema(),
            },
            {
                "name": "browser_screenshot",
                "description": "Take a screenshot of a web page",
                "input_schema": BrowserScreenshotRequest.model_json_schema(),
            },
            {
                "name": "browser_extract",
                "description": "Extract structured data from a web page using AI",
                "input_schema": BrowserExtractRequest.model_json_schema(),
            },
        ],
        "resources": [],
        "prompts": [],
    }


@app.get("/tools")
async def list_tools():
    """列出可用工具"""
    caps = await capabilities()
    return caps["tools"]


@app.post("/tools/browse_task/execute")
async def execute_browse_task(request: BrowseTaskRequest):
    """执行浏览器自动化任务"""
    result = await _engine.execute_task(request)
    return result.model_dump()


@app.post("/tools/browser_screenshot/execute")
async def execute_browser_screenshot(request: BrowserScreenshotRequest):
    """截取页面截图"""
    result = await _engine.take_screenshot(request)
    return result.model_dump()


@app.post("/tools/browser_extract/execute")
async def execute_browser_extract(request: BrowserExtractRequest):
    """从页面提取数据"""
    result = await _engine.extract_data(request)
    return result.model_dump()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("BROWSER_MCP_PORT", "8030"))
    uvicorn.run(app, host="0.0.0.0", port=port)
